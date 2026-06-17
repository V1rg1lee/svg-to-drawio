"""Main SVG-to-draw.io conversion orchestration."""

from __future__ import annotations

import re
import warnings
import xml.etree.ElementTree as ET
from collections.abc import Callable
from os import PathLike, fspath, path
from xml.etree.ElementTree import Element

from .cell_factory import make_bounds_vertex, make_layer_cell
from .compatibility import note_reference_usage
from .conversion_result import ConversionResult
from .css import AncestorInfo, CssRule, apply_css, collect_css, extract_custom_props
from .defs import DefsIndex
from .diagnostics import ConversionReport
from .drawio_model import Cell, group_bbox, shift_cells
from .drawio_output import make_xml
from .element_geometry import BoundsBox
from .elements.gradient_approx import is_multi_stop_gradient, supports_multi_stop_gradient_approximation
from .elements.image import emit_embedded_image_uri, emit_image
from .elements.path import emit_path
from .elements.poly import emit_polyline
from .elements.shapes import emit_circle, emit_ellipse, emit_line, emit_rect
from .elements.text import emit_text
from .emitter_context import EmitterContext
from .rendering_options import RenderingOptions, normalize_filter_ref
from .svg_fallback import build_fallback_svg_data_uri
from .transforms import Matrix, mat_mul, parse_transform, viewbox_transform
from .utils import parse_length, strip_ns

_SKIP_TAGS: frozenset[str] = frozenset(
    {
        "defs",
        "title",
        "desc",
        "metadata",
        "style",
        "symbol",
        "clipPath",
        "mask",
        "linearGradient",
        "radialGradient",
        "marker",
        "pattern",
        "filter",
        "animate",
        "animateTransform",
    }
)

_INKSCAPE_NS = "http://www.inkscape.org/namespaces/inkscape"

ElementEmitter = Callable[[EmitterContext, Element, Matrix, dict[str, str] | None], None]


def _emit_open_polyline(
    ctx: EmitterContext,
    elem: Element,
    matrix: Matrix,
    css: dict[str, str] | None,
) -> None:
    """Dispatch a `<polyline>` element."""
    emit_polyline(ctx, elem, matrix, closed=False, css=css)


def _emit_closed_polygon(
    ctx: EmitterContext,
    elem: Element,
    matrix: Matrix,
    css: dict[str, str] | None,
) -> None:
    """Dispatch a `<polygon>` element."""
    emit_polyline(ctx, elem, matrix, closed=True, css=css)


_DISPATCH: dict[str, ElementEmitter] = {
    "line": emit_line,
    "circle": emit_circle,
    "ellipse": emit_ellipse,
    "rect": emit_rect,
    "text": emit_text,
    "polyline": _emit_open_polyline,
    "polygon": _emit_closed_polygon,
    "path": emit_path,
    "image": emit_image,
}

_FALLBACK_PAINT_PROPS: tuple[str, str] = ("fill", "stroke")
_SIMPLE_CLIP_TAGS: frozenset[str] = frozenset({"rect", "circle", "ellipse", "polygon"})


def _inkscape_layer_label(elem: Element) -> str | None:
    """Return the Inkscape layer label if this `<g>` is an Inkscape layer, else None."""
    groupmode = elem.get(f"{{{_INKSCAPE_NS}}}groupmode") or elem.get("inkscape:groupmode")
    if groupmode == "layer":
        return elem.get(f"{{{_INKSCAPE_NS}}}label") or elem.get("inkscape:label") or ""
    return None


class Converter:
    """Convert SVG files into draw.io XML by walking the SVG element tree."""

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        """Reset all per-file conversion state."""
        self._id: int = 2
        self.cells: list[Cell] = []
        self.defs = DefsIndex()
        self.report = ConversionReport()
        self.source_dir: str = ""
        self.css_rules: list[CssRule] = []
        self._custom_props: dict[str, str] = {}
        self._css_match_cache: dict = {}
        self._element_count: int = 0
        self._flatten: bool = False
        self._max_elements: int | None = None
        self._root: Element | None = None
        self._root_matrix: Matrix = [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]
        self.rendering_options = RenderingOptions()

    def next_id(self) -> str:
        """Return the next unique draw.io cell identifier."""
        cell_id = str(self._id)
        self._id += 1
        return cell_id

    def _make_context(self) -> EmitterContext:
        """Create the root emitter context for the current conversion run."""
        return EmitterContext(
            defs=self.defs,
            parent_id="1",
            link_url="",
            source_dir=self.source_dir,
            css_rules=self.css_rules,
            custom_props=self._custom_props,
            report=self.report,
            rendering_options=self.rendering_options,
            add_cell=self.cells.append,
            next_id_callback=self.next_id,
        )

    def _prepare_root(
        self,
        root: Element,
        *,
        source_path: str | None,
        base_dir: str | None = None,
    ) -> None:
        """Prepare converter state from a parsed SVG root element."""
        self._root = root
        self.report.source_path = source_path or ""
        if base_dir:
            self.source_dir = path.abspath(base_dir)
        elif source_path:
            self.source_dir = path.dirname(path.abspath(source_path))
        else:
            self.source_dir = ""
        self.defs.index(root)
        self.css_rules = collect_css(root)
        self._custom_props = extract_custom_props(self.css_rules)
        self._root_matrix = viewbox_transform(root)

    def _convert_root(self, root: Element, title: str, *, source_path: str | None, base_dir: str | None = None) -> str:
        """Convert a parsed SVG root element into draw.io XML."""
        self._prepare_root(root, source_path=source_path, base_dir=base_dir)
        context = self._make_context()
        for child in root:
            self._convert(child, context, self._root_matrix, {}, ancestors=[])
        xml = make_xml(self.cells, title)
        self.report.emitted_cells = len(self.cells)
        return xml

    def _parse_and_convert(self, svg_path_str: str, title: str) -> str:
        """Parse an SVG file and return the draw.io XML as a string."""
        tree = ET.parse(svg_path_str)
        return self._convert_root(tree.getroot(), title, source_path=path.abspath(svg_path_str))

    def _build_result(self, xml: str, *, source_path: str | None, output_path: str | None) -> ConversionResult:
        """Build a detached rich conversion result object for the latest run."""
        report = self.get_report()
        return ConversionResult(xml=xml, report=report, source_path=source_path, output_path=output_path)

    def convert_file(
        self,
        svg_path: str | PathLike[str],
        out_path: str | PathLike[str] | None = None,
        *,
        flatten: bool = False,
        max_elements: int | None = None,
        rendering_options: RenderingOptions | None = None,
    ) -> str:
        """Convert one SVG file into a `.drawio` file and return the output path."""
        return (
            self.convert_file_result(
                svg_path,
                out_path,
                flatten=flatten,
                max_elements=max_elements,
                rendering_options=rendering_options,
            ).output_path
            or ""
        )

    def convert_file_result(
        self,
        svg_path: str | PathLike[str],
        out_path: str | PathLike[str] | None = None,
        *,
        flatten: bool = False,
        max_elements: int | None = None,
        rendering_options: RenderingOptions | None = None,
    ) -> ConversionResult:
        """Convert one SVG file, write it to disk, and return a rich conversion result."""
        self.reset()
        self._flatten = flatten
        self._max_elements = max_elements
        self.rendering_options = rendering_options or RenderingOptions()

        svg_path_str = fspath(svg_path)
        title = path.splitext(path.basename(svg_path_str))[0]
        xml = self._parse_and_convert(svg_path_str, title)
        output_path = fspath(out_path) if out_path is not None else path.splitext(svg_path_str)[0] + ".drawio"
        with open(output_path, "w", encoding="utf-8") as handle:
            handle.write(xml)
        self.report.output_path = output_path
        return self._build_result(xml, source_path=path.abspath(svg_path_str), output_path=output_path)

    def convert_to_string(
        self,
        svg_path: str | PathLike[str],
        *,
        flatten: bool = False,
        max_elements: int | None = None,
        rendering_options: RenderingOptions | None = None,
    ) -> str:
        """Convert one SVG file and return the draw.io XML as a string."""
        return self.convert_to_string_result(
            svg_path,
            flatten=flatten,
            max_elements=max_elements,
            rendering_options=rendering_options,
        ).xml

    def convert_to_string_result(
        self,
        svg_path: str | PathLike[str],
        *,
        flatten: bool = False,
        max_elements: int | None = None,
        rendering_options: RenderingOptions | None = None,
    ) -> ConversionResult:
        """Convert one SVG file and return a rich in-memory conversion result."""
        self.reset()
        self._flatten = flatten
        self._max_elements = max_elements
        self.rendering_options = rendering_options or RenderingOptions()

        svg_path_str = fspath(svg_path)
        title = path.splitext(path.basename(svg_path_str))[0]
        xml = self._parse_and_convert(svg_path_str, title)
        return self._build_result(xml, source_path=path.abspath(svg_path_str), output_path=None)

    def convert_svg_string_result(
        self,
        svg_text: str,
        *,
        base_dir: str | PathLike[str] | None = None,
        title: str = "diagram",
        source_label: str | None = None,
        flatten: bool = False,
        max_elements: int | None = None,
        rendering_options: RenderingOptions | None = None,
    ) -> ConversionResult:
        """Convert SVG markup already loaded in memory and return a rich conversion result."""
        self.reset()
        self._flatten = flatten
        self._max_elements = max_elements
        self.rendering_options = rendering_options or RenderingOptions()
        root = ET.fromstring(svg_text)
        memory_source = source_label or f"memory:{title}.svg"
        xml = self._convert_root(
            root, title, source_path=memory_source, base_dir=fspath(base_dir) if base_dir else None
        )
        return self._build_result(xml, source_path=memory_source, output_path=None)

    def convert_svg_bytes_result(
        self,
        svg_bytes: bytes,
        *,
        base_dir: str | PathLike[str] | None = None,
        title: str = "diagram",
        source_label: str | None = None,
        flatten: bool = False,
        max_elements: int | None = None,
        rendering_options: RenderingOptions | None = None,
    ) -> ConversionResult:
        """Convert SVG bytes already loaded in memory and return a rich conversion result."""
        return self.convert_svg_string_result(
            svg_bytes.decode("utf-8"),
            base_dir=base_dir,
            title=title,
            source_label=source_label,
            flatten=flatten,
            max_elements=max_elements,
            rendering_options=rendering_options,
        )

    def analyze_file(
        self,
        svg_path: str | PathLike[str],
        *,
        flatten: bool = False,
        max_elements: int | None = None,
        rendering_options: RenderingOptions | None = None,
    ) -> ConversionReport:
        """Analyze one SVG file without writing output, returning its structured report."""
        self.reset()
        self._flatten = flatten
        self._max_elements = max_elements
        self.report.analyze_only = True
        self.rendering_options = rendering_options or RenderingOptions()

        svg_path_str = fspath(svg_path)
        title = path.splitext(path.basename(svg_path_str))[0]
        self._parse_and_convert(svg_path_str, title)
        return self.get_report()

    def get_report(self) -> ConversionReport:
        """Return a detached report for the most recent conversion run."""
        return self.report.clone()

    def _record_issue(
        self,
        code: str,
        message: str,
        *,
        severity: str = "warning",
        elem: Element | None = None,
        fallback_used: bool = False,
    ) -> None:
        """Record one structured issue against the current conversion report."""
        self.report.add_issue(
            code=code,
            severity=severity,
            message=message,
            element_tag=strip_ns(elem.tag) if elem is not None else None,
            element_id=elem.get("id") if elem is not None else None,
            fallback_used=fallback_used,
        )

    @staticmethod
    def _local_shape_bounds(elem: Element) -> tuple[float, float, float, float] | None:
        """Return local untransformed bounds for a simple SVG geometry element."""
        tag = strip_ns(elem.tag)
        if tag == "rect":
            x = parse_length(elem.get("x"))
            y = parse_length(elem.get("y"))
            width = parse_length(elem.get("width"))
            height = parse_length(elem.get("height"))
            return x, y, width, height
        if tag == "circle":
            cx = parse_length(elem.get("cx"))
            cy = parse_length(elem.get("cy"))
            radius = parse_length(elem.get("r"))
            return cx - radius, cy - radius, radius * 2.0, radius * 2.0
        if tag == "ellipse":
            cx = parse_length(elem.get("cx"))
            cy = parse_length(elem.get("cy"))
            rx = parse_length(elem.get("rx"))
            ry = parse_length(elem.get("ry"))
            return cx - rx, cy - ry, rx * 2.0, ry * 2.0
        if tag == "polygon":
            coords = [float(item) for item in re.findall(r"[-\d.eE+]+", elem.get("points", ""))]
            if len(coords) < 6:
                return None
            xs = coords[0::2]
            ys = coords[1::2]
            x = min(xs)
            y = min(ys)
            return x, y, max(xs) - x, max(ys) - y
        return None

    @staticmethod
    def _bounds_contains(outer: tuple[float, float, float, float], inner: tuple[float, float, float, float]) -> bool:
        """Return whether one bounds tuple fully contains another."""
        ox, oy, ow, oh = outer
        ix, iy, iw, ih = inner
        epsilon = 1e-6
        return (
            ix >= ox - epsilon and iy >= oy - epsilon and ix + iw <= ox + ow + epsilon and iy + ih <= oy + oh + epsilon
        )

    def _simple_clip_candidate(self, clip_ref: str) -> Element | None:
        """Return a single simple clip geometry eligible for editable replacement."""
        match = re.match(r"url\(#([^)]+)\)", clip_ref)
        if not match:
            return None
        clip_elem = self.defs.get_element(match.group(1))
        if clip_elem is None or strip_ns(clip_elem.tag) != "clipPath":
            return None
        units = (clip_elem.get("clipPathUnits") or "userSpaceOnUse").strip()
        if units != "userSpaceOnUse":
            return None
        drawable_children = [child for child in clip_elem if strip_ns(child.tag) in _SIMPLE_CLIP_TAGS]
        if len(drawable_children) != 1:
            return None
        return drawable_children[0]

    def _simple_mask_candidate(self, mask_ref: str) -> Element | None:
        """Return a single simple mask geometry eligible for editable replacement."""
        match = re.match(r"url\(#([^)]+)\)", mask_ref)
        if not match:
            return None
        mask_elem = self.defs.get_element(match.group(1))
        if mask_elem is None or strip_ns(mask_elem.tag) != "mask":
            return None
        units = (mask_elem.get("maskUnits") or "userSpaceOnUse").strip()
        if units != "userSpaceOnUse":
            return None
        drawable_children = [child for child in mask_elem if strip_ns(child.tag) in _SIMPLE_CLIP_TAGS]
        if len(drawable_children) != 1:
            return None
        candidate = drawable_children[0]
        fill = ((candidate.get("fill") or "") or "").strip().lower()
        if fill and fill not in {"#fff", "#ffffff", "white"}:
            return None
        return candidate

    def _can_replace_clipped_shape(self, elem: Element, css: dict[str, str], replacement: Element) -> bool:
        """Return whether a simple clipped/masked shape can stay editable through replacement geometry."""
        if strip_ns(elem.tag) not in {"rect", "circle", "ellipse"}:
            return False
        fill_value = (css.get("fill") or elem.get("fill") or "").strip().lower()
        if not fill_value or fill_value == "none" or fill_value.startswith("url("):
            return False
        stroke_value = (css.get("stroke") or elem.get("stroke") or "").strip().lower()
        if stroke_value and stroke_value != "none":
            return False
        if normalize_filter_ref(css.get("filter") or elem.get("filter")) is not None:
            return False
        element_bounds = self._local_shape_bounds(elem)
        replacement_bounds = self._local_shape_bounds(replacement)
        if element_bounds is None or replacement_bounds is None:
            return False
        return self._bounds_contains(element_bounds, replacement_bounds)

    def _emit_replacement_geometry(
        self,
        replacement: Element,
        ctx: EmitterContext,
        matrix: Matrix,
        css: dict[str, str],
    ) -> bool:
        """Emit one synthetic replacement shape using the original element's resolved style."""
        tag = strip_ns(replacement.tag)
        if tag in _DISPATCH:
            _DISPATCH[tag](ctx, replacement, matrix, css)
            return True
        if tag == "polygon":
            _emit_closed_polygon(ctx, replacement, matrix, css)
            return True
        return False

    def _emit_simple_clip_or_mask_replacement(
        self,
        elem: Element,
        ctx: EmitterContext,
        matrix: Matrix,
        css: dict[str, str],
        *,
        record_issues: bool,
    ) -> bool:
        """Try to keep a very simple clip path or mask editable by rewriting the geometry."""
        clip_path = css.get("clip-path") or elem.get("clip-path") or ""
        if clip_path and clip_path.lower() != "none":
            candidate = self._simple_clip_candidate(clip_path)
            if candidate is not None and self._can_replace_clipped_shape(elem, css, candidate):
                emitted = self._emit_replacement_geometry(candidate, ctx, matrix, css)
                if emitted and record_issues:
                    self._record_issue(
                        "clip-path-simplified-native",
                        "A simple clip path was rewritten into an editable replacement shape.",
                        elem=elem,
                    )
                return emitted

        mask = css.get("mask") or elem.get("mask") or ""
        if mask and mask.lower() != "none":
            candidate = self._simple_mask_candidate(mask)
            if candidate is not None and self._can_replace_clipped_shape(elem, css, candidate):
                emitted = self._emit_replacement_geometry(candidate, ctx, matrix, css)
                if emitted and record_issues:
                    self._record_issue(
                        "mask-simplified-native",
                        "A simple mask was rewritten into an editable replacement shape.",
                        elem=elem,
                    )
                return emitted

        return False

    def _fallback_reason(self, elem: Element, css: dict[str, str]) -> tuple[str, str] | None:
        """Return the first unsupported visual feature that should trigger SVG fallback."""
        clip_path = css.get("clip-path") or elem.get("clip-path") or ""
        if clip_path and clip_path.lower() != "none":
            return "clip-path-fallback", "Embedded SVG fallback used because `clip-path` is not natively supported."

        mask = css.get("mask") or elem.get("mask") or ""
        if mask and mask.lower() != "none":
            return "mask-fallback", "Embedded SVG fallback used because `mask` is not natively supported."

        filter_ref = normalize_filter_ref(css.get("filter") or elem.get("filter"))
        if filter_ref is not None:
            if self.rendering_options.should_force_filter_fallback(filter_ref):
                return (
                    "filter-fallback",
                    "Embedded SVG fallback used because the current filter policy preserves filters through SVG.",
                )
            if not self.defs.supports_filter(filter_ref) and not self.rendering_options.should_prefer_native_filter():
                return (
                    "filter-fallback",
                    "Embedded SVG fallback used because this SVG filter cannot be approximated by draw.io.",
                )

        for prop_name in _FALLBACK_PAINT_PROPS:
            paint_value = css.get(prop_name) or elem.get(prop_name) or ""
            referenced_tag = self.defs.referenced_tag(paint_value)
            if referenced_tag == "pattern":
                return (
                    "pattern-fallback",
                    f"Embedded SVG fallback used because `{prop_name}` references an SVG pattern.",
                )
        return None

    def _multi_stop_gradient_fallback_reason(
        self,
        elem: Element,
        css: dict[str, str],
        matrix: Matrix,
    ) -> tuple[str, str] | None:
        """Return the fallback reason for multi-stop gradients that cannot stay native."""
        fill_value = css.get("fill") or elem.get("fill") or ""
        _, gradient = self.defs.resolve_fill(fill_value)
        if not is_multi_stop_gradient(gradient):
            return None

        if self.rendering_options.should_force_gradient_fallback():
            return (
                "multi-stop-gradient-fallback",
                "Embedded SVG fallback used because the current gradient policy prefers exact multi-stop rendering.",
            )

        filter_ref = self._gradient_filter_ref_for_policy(css.get("filter") or elem.get("filter"))
        if supports_multi_stop_gradient_approximation(
            strip_ns(elem.tag),
            matrix,
            gradient,
            filter_ref=filter_ref,
        ):
            return None

        if self.rendering_options.should_prefer_native_gradient():
            return None

        return (
            "multi-stop-gradient-fallback",
            "Embedded SVG fallback used because this multi-stop gradient cannot be preserved natively "
            "under the current rendering policy.",
        )

    def _gradient_filter_ref_for_policy(self, filter_ref: str | None) -> str | None:
        """Return the filter reference that should constrain native gradient approximations."""
        normalized = normalize_filter_ref(filter_ref)
        if normalized is None:
            return None
        if self.rendering_options.should_prefer_native_filter():
            return None
        return normalized

    def _record_policy_notes(
        self,
        elem: Element,
        css: dict[str, str],
        matrix: Matrix,
        *,
        record_issues: bool,
    ) -> None:
        """Record non-fallback rendering compromises chosen by the active policy set."""
        if not record_issues:
            return

        filter_ref = normalize_filter_ref(css.get("filter") or elem.get("filter"))
        if (
            filter_ref is not None
            and not self.defs.supports_filter(filter_ref)
            and self.rendering_options.should_prefer_native_filter()
        ):
            self._record_issue(
                "filter-ignored-for-editability",
                "Unsupported SVG filter was ignored because the filter policy prefers editable native output.",
                elem=elem,
            )

        fill_value = css.get("fill") or elem.get("fill") or ""
        _, gradient = self.defs.resolve_fill(fill_value)
        if not is_multi_stop_gradient(gradient) or not self.rendering_options.should_prefer_native_gradient():
            return

        if supports_multi_stop_gradient_approximation(
            strip_ns(elem.tag),
            matrix,
            gradient,
            filter_ref=self._gradient_filter_ref_for_policy(filter_ref),
        ):
            return

        self._record_issue(
            "multi-stop-gradient-reduced",
            "Multi-stop gradient was reduced to draw.io's native two-colour gradient because the gradient policy "
            "prefers editability over exact fidelity.",
            elem=elem,
        )

    def _emit_svg_fallback(
        self,
        elem: Element,
        ctx: EmitterContext,
        parent_matrix: Matrix,
        css: dict[str, str],
        inherited_css: dict[str, str],
        ancestors: list[AncestorInfo],
        issue_code: str,
        issue_message: str,
    ) -> bool:
        """Emit an embedded SVG image for one unsupported-but-renderable fragment."""
        if self._root is None:
            return False

        bbox = self._estimate_subtree_bounds(elem, parent_matrix, inherited_css, ancestors)
        if bbox is None:
            self._record_issue(
                "fallback-bounds-missing",
                "Could not estimate bounds for an embedded SVG fallback, so the element was skipped.",
                severity="error",
                elem=elem,
            )
            return False

        # Compute padding to avoid clipping stroke edges and filter halos.
        stroke_w = parse_length(css.get("stroke-width") or elem.get("stroke-width") or "1") or 1.0
        padding = stroke_w / 2.0
        filter_val = css.get("filter") or elem.get("filter") or ""
        if filter_val and filter_val.lower() != "none":
            padding = max(padding, self._estimate_filter_padding(filter_val, bbox))
        marker_values = [
            (css.get(name) or elem.get(name) or "").strip().lower()
            for name in ("marker-start", "marker-mid", "marker-end")
        ]
        if any(value and value != "none" for value in marker_values):
            padding = max(padding, stroke_w * 2.5)
        if (css.get("stroke-linejoin") or elem.get("stroke-linejoin") or "").strip().lower() == "miter":
            padding = max(padding, stroke_w)

        image_ref = build_fallback_svg_data_uri(
            self._root,
            elem,
            parent_matrix=parent_matrix,
            bbox=bbox,
            computed_css=css,
            padding=padding,
            report=self.report,
        )
        self.report.fallback_count += 1
        self._record_issue(issue_code, issue_message, elem=elem, fallback_used=True)

        x, y, width, height = bbox
        emit_embedded_image_uri(
            ctx,
            elem,
            image_ref=image_ref,
            box=BoundsBox(x=x - padding, y=y - padding, width=width + 2.0 * padding, height=height + 2.0 * padding),
        )
        return True

    def _estimate_filter_padding(
        self,
        filter_ref: str,
        bbox: tuple[float, float, float, float],
    ) -> float:
        """Estimate how much one SVG filter may extend beyond the raw geometry bounds."""
        normalized = normalize_filter_ref(filter_ref)
        if normalized is None:
            return 0.0

        match = re.match(r"url\(#([^)]+)\)", normalized)
        if not match:
            _, _, width, height = bbox
            return max(width, height) * 0.12

        filter_elem = self.defs.get_element(match.group(1))
        if filter_elem is None:
            _, _, width, height = bbox
            return max(width, height) * 0.12

        padding = 0.0
        for child in filter_elem.iter():
            child_tag = strip_ns(child.tag)
            if child_tag == "feGaussianBlur":
                padding = max(padding, parse_length(child.get("stdDeviation"), 0.0) * 3.0)
            elif child_tag == "feDropShadow":
                std_deviation = parse_length(child.get("stdDeviation"), 0.0)
                dx = abs(parse_length(child.get("dx"), 0.0))
                dy = abs(parse_length(child.get("dy"), 0.0))
                padding = max(padding, max(dx, dy) + std_deviation * 3.0)

        if padding > 0.0:
            return padding

        _, _, width, height = bbox
        return max(width, height) * 0.12

    def _estimate_subtree_bounds(
        self,
        elem: Element,
        parent_matrix: Matrix,
        inherited_css: dict[str, str],
        ancestors: list[AncestorInfo],
    ) -> tuple[float, float, float, float] | None:
        """Estimate one subtree's world-space bounds by reusing the existing emitters in flatten mode."""
        temp_cells: list[Cell] = []
        local_id = 1000000
        temp_report = ConversionReport(source_path=self.report.source_path)

        def next_temp_id() -> str:
            nonlocal local_id
            local_id += 1
            return str(local_id)

        temp_ctx = EmitterContext(
            defs=self.defs,
            parent_id="1",
            link_url="",
            source_dir=self.source_dir,
            css_rules=self.css_rules,
            custom_props=self._custom_props,
            report=temp_report,
            rendering_options=self.rendering_options,
            add_cell=temp_cells.append,
            next_id_callback=next_temp_id,
        )

        old_flatten = self._flatten
        old_max_elements = self._max_elements
        old_element_count = self._element_count
        try:
            self._flatten = True
            self._max_elements = None
            self._convert(
                elem,
                temp_ctx,
                parent_matrix,
                inherited_css,
                ancestors=ancestors,
                allow_fallback=False,
                record_issues=False,
                enforce_max_elements=False,
            )
        finally:
            self._flatten = old_flatten
            self._max_elements = old_max_elements
            self._element_count = old_element_count

        if not temp_cells:
            return None
        return group_bbox(temp_cells)

    def _convert(
        self,
        elem: Element,
        ctx: EmitterContext,
        parent_matrix: Matrix,
        inherited_css: dict[str, str],
        ancestors: list[AncestorInfo] | None = None,
        *,
        allow_fallback: bool = True,
        record_issues: bool = True,
        enforce_max_elements: bool = True,
    ) -> None:
        """Convert a single SVG element and recurse into its children when needed."""
        ancestor_list = list(ancestors or [])
        tag = strip_ns(elem.tag)
        if tag in _SKIP_TAGS:
            return

        matrix = mat_mul(parent_matrix, parse_transform(elem.get("transform")))
        css = apply_css(
            elem,
            ctx.css_rules,
            tag,
            inherited_css,
            ancestors=ancestor_list,
            custom_props=ctx.custom_props,
            _match_cache=self._css_match_cache,
        )

        display_value = css.get("display") or elem.get("display") or ""
        visibility_value = css.get("visibility") or elem.get("visibility") or ""
        if display_value == "none" or visibility_value == "hidden":
            return

        if allow_fallback:
            if self._emit_simple_clip_or_mask_replacement(elem, ctx, matrix, css, record_issues=record_issues):
                return
            fallback_reason = self._fallback_reason(elem, css)
            if fallback_reason is None:
                fallback_reason = self._multi_stop_gradient_fallback_reason(elem, css, matrix)
            if fallback_reason is not None and self._emit_svg_fallback(
                elem,
                ctx,
                parent_matrix,
                css,
                inherited_css,
                ancestor_list,
                fallback_reason[0],
                fallback_reason[1],
            ):
                return

        self._record_policy_notes(elem, css, matrix, record_issues=record_issues)

        elem_classes = set((elem.get("class") or "").split())
        child_ancestors = ancestor_list + [(tag, elem_classes)]

        if tag == "g":
            self._convert_group(
                elem,
                ctx,
                matrix,
                css,
                child_ancestors,
                allow_fallback=allow_fallback,
                record_issues=record_issues,
                enforce_max_elements=enforce_max_elements,
            )
        elif tag == "a":
            self._convert_link(
                elem,
                ctx,
                matrix,
                css,
                child_ancestors,
                allow_fallback=allow_fallback,
                record_issues=record_issues,
                enforce_max_elements=enforce_max_elements,
            )
        elif tag == "use":
            self._resolve_use(
                elem,
                ctx,
                matrix,
                css,
                child_ancestors,
                allow_fallback=allow_fallback,
                record_issues=record_issues,
                enforce_max_elements=enforce_max_elements,
            )
        elif tag == "svg":
            ctx.report.record_feature_observation(note_reference_usage())
            inner_matrix = mat_mul(matrix, viewbox_transform(elem))
            for child in elem:
                self._convert(
                    child,
                    ctx,
                    inner_matrix,
                    css,
                    ancestors=child_ancestors,
                    allow_fallback=allow_fallback,
                    record_issues=record_issues,
                    enforce_max_elements=enforce_max_elements,
                )
        elif tag in _DISPATCH:
            if enforce_max_elements and self._max_elements is not None:
                self._element_count += 1
                if self._element_count > self._max_elements:
                    if self._element_count == self._max_elements + 1:
                        warnings.warn(
                            f"SVG has more than {self._max_elements} drawable elements; output truncated.",
                            RuntimeWarning,
                            stacklevel=2,
                        )
                        if record_issues:
                            self.report.truncated = True
                            self._record_issue(
                                "max-elements-truncated",
                                f"Output was truncated after {self._max_elements} drawable elements.",
                                elem=elem,
                            )
                    return
            try:
                _DISPATCH[tag](ctx, elem, matrix, css)
            except Exception as exc:
                elem_id = elem.get("id")
                id_hint = f" id={elem_id!r}" if elem_id else ""
                raise RuntimeError(f"Failed to convert <{tag}{id_hint}>: {exc}") from exc
        elif record_issues:
            self._record_issue(
                "ignored-unsupported-element",
                f"Ignored unsupported SVG element <{tag}>.",
                elem=elem,
            )

    def _convert_group(
        self,
        elem: Element,
        ctx: EmitterContext,
        matrix: Matrix,
        css: dict[str, str],
        ancestors: list[AncestorInfo],
        *,
        allow_fallback: bool = True,
        record_issues: bool = True,
        enforce_max_elements: bool = True,
    ) -> None:
        """Render an SVG group as a draw.io container with relative child coordinates.

        Inkscape layers are emitted as proper draw.io layers (no geometry, absolute children).
        When flatten mode is active, groups are dissolved and their children are emitted directly.
        """
        # Inkscape layers → draw.io layer cells
        layer_label = _inkscape_layer_label(elem)
        if layer_label is not None:
            self._convert_layer(
                elem,
                ctx,
                matrix,
                css,
                ancestors,
                layer_label,
                allow_fallback=allow_fallback,
                record_issues=record_issues,
                enforce_max_elements=enforce_max_elements,
            )
            return

        # Flatten mode: dissolve the group and emit children directly under the current parent
        if self._flatten:
            for child in elem:
                self._convert(
                    child,
                    ctx,
                    matrix,
                    css,
                    ancestors=ancestors,
                    allow_fallback=allow_fallback,
                    record_issues=record_issues,
                    enforce_max_elements=enforce_max_elements,
                )
            return

        group_id = ctx.next_id()
        start_index = len(self.cells)

        group_ctx = ctx.with_parent(group_id)
        for child in elem:
            self._convert(
                child,
                group_ctx,
                matrix,
                css,
                ancestors=ancestors,
                allow_fallback=allow_fallback,
                record_issues=record_issues,
                enforce_max_elements=enforce_max_elements,
            )

        new_cells = list(self.cells[start_index:])
        del self.cells[start_index:]

        direct_children = [cell for cell in new_cells if cell.parent == group_id]
        gx, gy, gw, gh = group_bbox(direct_children)

        self.cells.append(
            make_bounds_vertex(
                ctx,
                "group;",
                gx,
                gy,
                gw,
                gh,
                cell_id=group_id,
            )
        )

        shift_cells(direct_children, gx, gy)
        self.cells.extend(new_cells)

    def _convert_layer(
        self,
        elem: Element,
        ctx: EmitterContext,
        matrix: Matrix,
        css: dict[str, str],
        ancestors: list[AncestorInfo],
        label: str,
        *,
        allow_fallback: bool = True,
        record_issues: bool = True,
        enforce_max_elements: bool = True,
    ) -> None:
        """Render an Inkscape layer as a draw.io layer cell with absolute-coordinate children."""
        layer_id = ctx.next_id()
        self.cells.append(make_layer_cell(ctx, label=label, cell_id=layer_id))
        layer_ctx = ctx.with_parent(layer_id)
        for child in elem:
            self._convert(
                child,
                layer_ctx,
                matrix,
                css,
                ancestors=ancestors,
                allow_fallback=allow_fallback,
                record_issues=record_issues,
                enforce_max_elements=enforce_max_elements,
            )

    def _convert_link(
        self,
        elem: Element,
        ctx: EmitterContext,
        matrix: Matrix,
        css: dict[str, str],
        ancestors: list[AncestorInfo],
        *,
        allow_fallback: bool = True,
        record_issues: bool = True,
        enforce_max_elements: bool = True,
    ) -> None:
        """Propagate the current `<a>` link target to all nested drawable children."""
        href = elem.get("href") or elem.get("{http://www.w3.org/1999/xlink}href") or ""
        link_ctx = ctx.with_link(href or ctx.link_url)
        for child in elem:
            self._convert(
                child,
                link_ctx,
                matrix,
                css,
                ancestors=ancestors,
                allow_fallback=allow_fallback,
                record_issues=record_issues,
                enforce_max_elements=enforce_max_elements,
            )

    def _resolve_use(
        self,
        elem: Element,
        ctx: EmitterContext,
        matrix: Matrix,
        inherited_css: dict[str, str],
        ancestors: list[AncestorInfo] | None = None,
        *,
        allow_fallback: bool = True,
        record_issues: bool = True,
        enforce_max_elements: bool = True,
    ) -> None:
        """Resolve and render the target of a `<use>` element."""
        href = elem.get("href") or elem.get("{http://www.w3.org/1999/xlink}href") or ""
        if not href.startswith("#"):
            return

        ref_elem = self.defs.get_element(href[1:])
        if ref_elem is None:
            return

        ctx.report.record_feature_observation(note_reference_usage())

        use_x = parse_length(elem.get("x", "0"))
        use_y = parse_length(elem.get("y", "0"))
        use_translate: Matrix = [1.0, 0.0, 0.0, 1.0, use_x, use_y]

        ref_tag = strip_ns(ref_elem.tag)
        if ref_tag == "symbol":
            use_width = parse_length(elem.get("width", "0")) or None
            use_height = parse_length(elem.get("height", "0")) or None
            symbol_matrix = mat_mul(matrix, use_translate)
            inner_matrix = mat_mul(
                symbol_matrix,
                viewbox_transform(ref_elem, override_w=use_width, override_h=use_height),
            )
            for child in ref_elem:
                self._convert(
                    child,
                    ctx,
                    inner_matrix,
                    inherited_css,
                    ancestors=ancestors or [],
                    allow_fallback=allow_fallback,
                    record_issues=record_issues,
                    enforce_max_elements=enforce_max_elements,
                )
            return

        use_matrix = mat_mul(matrix, use_translate)
        self._convert(
            ref_elem,
            ctx,
            use_matrix,
            inherited_css,
            ancestors=ancestors or [],
            allow_fallback=allow_fallback,
            record_issues=record_issues,
            enforce_max_elements=enforce_max_elements,
        )
