"""SVG preview widgets for the desktop before/impact rendering page."""

from __future__ import annotations

import base64
import mimetypes
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

from PySide6.QtCore import QEvent, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QImage, QMouseEvent, QPainter, QPaintEvent, QPen, QTransform, QWheelEvent
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QToolTip, QWidget
from svg_to_drawio.css import AncestorInfo, apply_css, collect_css, extract_custom_props, index_css_rules
from svg_to_drawio.diagnostics import PreviewAnnotation
from svg_to_drawio.styles import get_visual, normalize_color
from svg_to_drawio.utils import format_style_attr, parse_style_attr, strip_ns

from .preview_text import rewrite_advanced_preview_text

SVG_NS = "http://www.w3.org/2000/svg"
XLINK_NS = "http://www.w3.org/1999/xlink"
_PREVIEW_TEXT_ATTRS = (
    "font-family",
    "font-size",
    "font-style",
    "font-weight",
    "letter-spacing",
    "text-anchor",
    "text-decoration",
    "baseline-shift",
    "dominant-baseline",
)
_PREVIEW_STROKE_ATTRS = (
    "stroke-dasharray",
    "stroke-linecap",
    "stroke-linejoin",
    "stroke-miterlimit",
)
_PREVIEW_STROKE_RELATED_ATTRS = ("stroke-width",) + _PREVIEW_STROKE_ATTRS


def _format_number(value: float) -> str:
    """Serialize a preview numeric value compactly and stably."""
    return f"{value:.6g}"


def _data_uri_from_bytes(mime: str, raw_bytes: bytes) -> str:
    """Encode binary content as a base64 data URI for preview self-containment."""
    payload = base64.b64encode(raw_bytes).decode("ascii")
    return f"data:{mime};base64,{payload}"


def _resolve_local_asset(svg_file: Path, href: str) -> Path | None:
    """Resolve one local preview asset path relative to the source SVG file."""
    candidate = Path(href)
    if not candidate.is_absolute():
        candidate = svg_file.parent / candidate
    candidate = candidate.resolve()
    return candidate if candidate.is_file() else None


def _rasterize_svg_asset(asset_path: Path) -> str | None:
    """Rasterize one standalone SVG asset to a PNG data URI for Qt preview rendering."""
    renderer = QSvgRenderer()
    if not renderer.load(str(asset_path)):
        return None

    view_box = renderer.viewBoxF()
    if view_box.isValid() and view_box.width() > 0.0 and view_box.height() > 0.0:
        width = max(int(round(view_box.width())), 1)
        height = max(int(round(view_box.height())), 1)
    else:
        default_size = renderer.defaultSize()
        width = max(default_size.width(), 1)
        height = max(default_size.height(), 1)

    image = QImage(width, height, QImage.Format.Format_ARGB32)
    image.fill(0x00000000)
    painter = QPainter(image)
    renderer.render(painter, QRectF(0.0, 0.0, float(width), float(height)))
    painter.end()

    with tempfile.TemporaryDirectory(prefix="svg-to-drawio-preview-asset-") as temp_dir:
        temp_png = Path(temp_dir) / f"{asset_path.stem}.png"
        if not image.save(str(temp_png)):
            return None
        raw_bytes = temp_png.read_bytes()
    return _data_uri_from_bytes("image/png", raw_bytes)


def _preview_href_for_local_asset(svg_file: Path, href: str) -> str | None:
    """Build a Qt-friendly preview reference for one local `<image>` asset."""
    asset_path = _resolve_local_asset(svg_file, href)
    if asset_path is None:
        return None

    if asset_path.suffix.lower() == ".svg":
        return _rasterize_svg_asset(asset_path)

    mime = mimetypes.guess_type(asset_path.name)[0] or "application/octet-stream"
    return _data_uri_from_bytes(mime, asset_path.read_bytes())


def _set_preview_attr(
    elem: ET.Element,
    style_map: dict[str, str],
    name: str,
    value: str,
) -> bool:
    """Set one normalized preview attribute and mirror it into the inline style when needed."""
    changed = False
    if elem.get(name) != value:
        elem.set(name, value)
        changed = True
    if name in style_map and style_map[name] != value:
        style_map[name] = value
        changed = True
    return changed


def _normalize_stop_element(elem: ET.Element, style_map: dict[str, str], computed: dict[str, str]) -> bool:
    """Inline normalized stop colors so gradients survive Qt's narrower CSS support."""
    changed = False
    stop_color = computed.get("stop-color") or style_map.get("stop-color") or elem.get("stop-color")
    if stop_color:
        normalized = normalize_color(stop_color)
        if normalized:
            changed |= _set_preview_attr(elem, style_map, "stop-color", normalized)

    stop_opacity = computed.get("stop-opacity") or style_map.get("stop-opacity") or elem.get("stop-opacity")
    if stop_opacity:
        changed |= _set_preview_attr(elem, style_map, "stop-opacity", str(stop_opacity))
    return changed


def _normalize_element_style(elem: ET.Element, computed: dict[str, str]) -> bool:
    """Inline one element's resolved CSS into plain SVG attributes for Qt preview."""
    tag = strip_ns(elem.tag)
    if tag == "style":
        return False

    style_map = parse_style_attr(elem.get("style"))
    original_style = dict(style_map)
    changed = False

    if tag == "stop":
        changed |= _normalize_stop_element(elem, style_map, computed)
    else:
        visual = get_visual(elem, computed)
        if "fill" in computed or "fill" in style_map or elem.get("fill") is not None:
            changed |= _set_preview_attr(elem, style_map, "fill", visual["fill"] or "none")
            changed |= _set_preview_attr(elem, style_map, "fill-opacity", _format_number(visual["fill_opacity"]))
        if "stroke" in computed or "stroke" in style_map or elem.get("stroke") is not None:
            changed |= _set_preview_attr(elem, style_map, "stroke", visual["stroke"] or "none")
            changed |= _set_preview_attr(elem, style_map, "stroke-opacity", _format_number(visual["stroke_opacity"]))
        if any(
            key in computed or key in style_map or elem.get(key) is not None for key in _PREVIEW_STROKE_RELATED_ATTRS
        ):
            changed |= _set_preview_attr(elem, style_map, "stroke-width", _format_number(visual["stroke_width"]))
        if "opacity" in computed or "opacity" in style_map or elem.get("opacity") is not None:
            changed |= _set_preview_attr(elem, style_map, "opacity", _format_number(visual["opacity"]))

        color_value = computed.get("color") or style_map.get("color") or elem.get("color")
        if color_value:
            normalized = normalize_color(color_value)
            if normalized:
                changed |= _set_preview_attr(elem, style_map, "color", normalized)

        for attr_name in _PREVIEW_TEXT_ATTRS:
            if attr_name not in computed and attr_name not in style_map and elem.get(attr_name) is None:
                continue
            value = computed.get(attr_name) or style_map.get(attr_name) or elem.get(attr_name)
            if value is None:
                continue
            changed |= _set_preview_attr(elem, style_map, attr_name, str(value))

        for attr_name in _PREVIEW_STROKE_ATTRS:
            if attr_name not in computed and attr_name not in style_map and elem.get(attr_name) is None:
                continue
            value = computed.get(attr_name) or style_map.get(attr_name) or elem.get(attr_name)
            if value is None:
                continue
            changed |= _set_preview_attr(elem, style_map, attr_name, str(value))

    custom_prop_keys = [key for key in style_map if key.startswith("--")]
    for key in custom_prop_keys:
        del style_map[key]
        changed = True

    rewritten_style = format_style_attr(style_map)
    if rewritten_style:
        if elem.get("style") != rewritten_style:
            elem.set("style", rewritten_style)
            changed = True
    elif original_style and "style" in elem.attrib:
        del elem.attrib["style"]
        changed = True

    return changed


def _inline_preview_styles(root: ET.Element) -> bool:
    """Resolve stylesheet-driven preview styling into plain SVG attributes."""
    css_rules = collect_css(root)
    custom_props = extract_custom_props(css_rules)
    match_cache: dict = {}
    rule_index = index_css_rules(css_rules)

    def visit(elem: ET.Element, inherited: dict[str, str], ancestors: list[AncestorInfo]) -> bool:
        tag = strip_ns(elem.tag)
        computed = apply_css(
            elem,
            css_rules,
            tag,
            inherited_styles=inherited,
            ancestors=ancestors,
            custom_props=custom_props,
            _match_cache=match_cache,
            rule_index=rule_index,
        )
        changed_here = _normalize_element_style(elem, computed)
        next_ancestors = [*ancestors, (tag, set((elem.get("class") or "").split()))]
        for child in elem:
            changed_here |= visit(child, computed, next_ancestors)
        return changed_here

    return visit(root, {}, [])


def _strip_style_elements(root: ET.Element) -> bool:
    """Remove stylesheet nodes after their resolved effects were inlined."""
    changed = False
    for parent in root.iter():
        style_children = [child for child in list(parent) if strip_ns(child.tag) == "style"]
        for child in style_children:
            parent.remove(child)
            changed = True
    return changed


def _prepare_preview_svg(
    svg_path: str, text_metrics_policy: str = "auto"
) -> tuple[str, tempfile.TemporaryDirectory[str] | None]:
    """Normalize local image references so Qt can render the preview more faithfully."""
    svg_file = Path(svg_path).resolve()
    try:
        root = ET.parse(svg_file).getroot()
    except ET.ParseError:
        return str(svg_file), None

    changed = False
    for elem in root.iter():
        if elem.tag != f"{{{SVG_NS}}}image":
            continue
        href_attr = "href" if elem.get("href") else f"{{{XLINK_NS}}}href"
        href = (elem.get(href_attr) or "").strip()
        if not href or href.startswith("data:") or "://" in href:
            continue

        preview_href = _preview_href_for_local_asset(svg_file, href)
        if not preview_href:
            continue
        elem.set("href", preview_href)
        if f"{{{XLINK_NS}}}href" in elem.attrib:
            del elem.attrib[f"{{{XLINK_NS}}}href"]
        changed = True

    changed |= _inline_preview_styles(root)
    changed |= rewrite_advanced_preview_text(root, text_metrics_policy)
    changed |= _strip_style_elements(root)

    if not changed:
        return str(svg_file), None

    temp_dir = tempfile.TemporaryDirectory(prefix="svg-to-drawio-preview-")
    preview_path = Path(temp_dir.name) / svg_file.name
    ET.register_namespace("", SVG_NS)
    ET.register_namespace("xlink", XLINK_NS)
    ET.ElementTree(root).write(preview_path, encoding="utf-8", xml_declaration=True)
    return str(preview_path), temp_dir


class SvgPreviewWidget(QWidget):
    """Render an SVG file with optional reliable conversion-impact overlays."""

    annotation_clicked = Signal(object)

    def __init__(self, placeholder_text: str) -> None:
        super().__init__()
        self.setMouseTracking(True)
        self.setMinimumHeight(260)
        self._placeholder_text = placeholder_text
        self._renderer: QSvgRenderer | None = None
        self._preview_temp_dir: tempfile.TemporaryDirectory[str] | None = None
        self._annotations: list[PreviewAnnotation] = []
        self._mapped_annotations: list[tuple[QRectF, PreviewAnnotation]] = []
        self._is_dark = False
        self._zoom = 1.0
        self._min_zoom = 1.0
        self._max_zoom = 12.0
        self._pan_offset = QPointF(0.0, 0.0)
        self._drag_last_position: QPointF | None = None
        self._press_position: QPointF | None = None
        self._pressed_annotation: PreviewAnnotation | None = None

    def set_dark_mode(self, is_dark: bool) -> None:
        """Update the preview palette to match the surrounding theme."""
        self._is_dark = is_dark
        self.update()

    def clear_preview(self, placeholder_text: str | None = None) -> None:
        """Reset the widget to its empty placeholder state."""
        if placeholder_text is not None:
            self._placeholder_text = placeholder_text
        self._renderer = None
        if self._preview_temp_dir is not None:
            self._preview_temp_dir.cleanup()
            self._preview_temp_dir = None
        self._annotations = []
        self._mapped_annotations = []
        self.reset_view()
        self.update()

    def set_preview(
        self,
        svg_path: str | None,
        annotations: list[PreviewAnnotation] | None = None,
        text_metrics_policy: str = "auto",
    ) -> None:
        """Load one SVG file and the overlay annotations to display on top of it.

        `text_metrics_policy` should match the user's selected rendering policy so the
        preview's text layout uses the same font-metrics backend as the real conversion.
        """
        self._annotations = list(annotations or [])
        self._mapped_annotations = []
        self.reset_view()
        if not svg_path:
            self._renderer = None
            self.update()
            return

        svg_file = Path(svg_path)
        if not svg_file.is_file():
            self._renderer = None
            self.update()
            return

        if self._preview_temp_dir is not None:
            self._preview_temp_dir.cleanup()
            self._preview_temp_dir = None

        renderer = QSvgRenderer(self)
        preview_path, temp_dir = _prepare_preview_svg(str(svg_file), text_metrics_policy)
        if not renderer.load(preview_path):
            if temp_dir is not None:
                temp_dir.cleanup()
            self._renderer = None
            self.update()
            return
        self._preview_temp_dir = temp_dir
        self._renderer = renderer
        self.update()

    def reset_view(self) -> None:
        """Restore the default fit-to-frame preview transform."""
        self._zoom = 1.0
        self._pan_offset = QPointF(0.0, 0.0)
        self._drag_last_position = None
        self._press_position = None
        self._pressed_annotation = None
        self.unsetCursor()

    def paintEvent(self, event: QPaintEvent) -> None:
        """Render the SVG content and any reliable overlay annotations."""
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        palette = self._palette()
        frame_rect = self.rect().adjusted(1, 1, -1, -1)
        painter.fillRect(self.rect(), palette["bg"])
        painter.setPen(QPen(palette["frame"], 1.5))
        painter.setBrush(palette["surface"])
        painter.drawRoundedRect(frame_rect, 12, 12)

        content_rect = QRectF(frame_rect.adjusted(12, 12, -12, -12))
        if self._renderer is None:
            painter.setPen(palette["text"])
            text_flags = int(Qt.AlignmentFlag.AlignCenter) | int(Qt.TextFlag.TextWordWrap)
            painter.drawText(content_rect, text_flags, self._placeholder_text)
            painter.end()
            return

        view_box = self._renderer.viewBoxF()
        if not view_box.isValid() or view_box.width() <= 0 or view_box.height() <= 0:
            default_size = self._renderer.defaultSize()
            view_box = QRectF(0.0, 0.0, max(float(default_size.width()), 1.0), max(float(default_size.height()), 1.0))

        target_rect = self._current_target_rect(content_rect, view_box)
        svg_to_widget = self._svg_to_widget_transform(view_box, target_rect)
        painter.save()
        painter.setClipRect(content_rect)
        painter.setTransform(svg_to_widget, True)
        self._renderer.render(painter, view_box)
        painter.restore()
        painter.setPen(QPen(palette["outline"], 1.0))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(target_rect, 6, 6)

        self._mapped_annotations = []
        for annotation in self._annotations:
            mapped_rect = self._map_annotation_rect(annotation, svg_to_widget)
            self._mapped_annotations.append((mapped_rect, annotation))
            painter.save()
            painter.setClipRect(content_rect)
            self._paint_annotation(painter, mapped_rect, annotation)
            painter.restore()

        painter.end()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Show a tooltip when hovering a highlighted conversion-impact region."""
        if (
            self._press_position is not None
            and self._drag_last_position is None
            and self._zoom > self._min_zoom
            and event.buttons() & Qt.MouseButton.LeftButton
        ):
            delta_x = event.position().x() - self._press_position.x()
            delta_y = event.position().y() - self._press_position.y()
            if max(abs(delta_x), abs(delta_y)) >= 4.0:
                self._drag_last_position = event.position()
                self._pressed_annotation = None
                self.setCursor(Qt.CursorShape.ClosedHandCursor)

        if self._drag_last_position is not None:
            self._pan_offset = QPointF(
                self._pan_offset.x() + event.position().x() - self._drag_last_position.x(),
                self._pan_offset.y() + event.position().y() - self._drag_last_position.y(),
            )
            self._drag_last_position = event.position()
            self._clamp_pan_offset()
            QToolTip.hideText()
            self.update()
            return

        position = event.position()
        annotation = self._annotation_at(position)
        if annotation is not None:
            label = annotation.label
            details = annotation.message
            if annotation.element_id:
                details += f"\nSource id: {annotation.element_id}"
            QToolTip.showText(event.globalPosition().toPoint(), f"{label}\n\n{details}", self)
            return
        QToolTip.hideText()
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Track clicks and start panning when a drag gesture begins."""
        if event.button() == Qt.MouseButton.LeftButton and self._renderer is not None:
            self._press_position = event.position()
            self._pressed_annotation = self._annotation_at(event.position())
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """Stop panning, or emit a clicked annotation when the user simply clicks."""
        if event.button() == Qt.MouseButton.LeftButton:
            released_annotation = self._annotation_at(event.position())
            clicked_annotation = (
                self._pressed_annotation
                if self._drag_last_position is None and self._pressed_annotation == released_annotation
                else None
            )
            self._drag_last_position = None
            self._press_position = None
            self._pressed_annotation = None
            self.setCursor(Qt.CursorShape.OpenHandCursor if self._zoom > self._min_zoom else Qt.CursorShape.ArrowCursor)
            if clicked_annotation is not None:
                self.annotation_clicked.emit(clicked_annotation)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        """Reset the zoom and pan transform on double click."""
        if event.button() == Qt.MouseButton.LeftButton and self._renderer is not None:
            self.reset_view()
            self.update()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def wheelEvent(self, event: QWheelEvent) -> None:
        """Zoom in or out around the cursor position with the mouse wheel."""
        if self._renderer is None:
            super().wheelEvent(event)
            return

        delta_y = event.angleDelta().y()
        if delta_y == 0:
            super().wheelEvent(event)
            return

        zoom_factor = 1.15 if delta_y > 0 else 1.0 / 1.15
        previous_zoom = self._zoom
        next_zoom = min(max(previous_zoom * zoom_factor, self._min_zoom), self._max_zoom)
        if abs(next_zoom - previous_zoom) < 1e-6:
            event.accept()
            return

        content_rect = self._content_rect()
        view_box = self._effective_view_box()
        if view_box is None:
            event.accept()
            return

        old_target_rect = self._current_target_rect(content_rect, view_box)
        self._zoom = next_zoom
        new_target_rect = self._current_target_rect(content_rect, view_box)
        cursor = event.position()

        if old_target_rect.width() > 0.0 and old_target_rect.height() > 0.0:
            x_ratio = (cursor.x() - old_target_rect.x()) / old_target_rect.width()
            y_ratio = (cursor.y() - old_target_rect.y()) / old_target_rect.height()
            new_center = QPointF(
                cursor.x() - x_ratio * new_target_rect.width() + new_target_rect.width() / 2.0,
                cursor.y() - y_ratio * new_target_rect.height() + new_target_rect.height() / 2.0,
            )
            base_rect = self._fit_rect(content_rect, view_box.width(), view_box.height())
            self._pan_offset = QPointF(
                new_center.x() - base_rect.center().x(),
                new_center.y() - base_rect.center().y(),
            )

        self._clamp_pan_offset()
        self.setCursor(Qt.CursorShape.OpenHandCursor if self._zoom > self._min_zoom else Qt.CursorShape.ArrowCursor)
        self.update()
        event.accept()

    def leaveEvent(self, event: QEvent) -> None:
        """Hide the hover tooltip when the cursor leaves the preview surface."""
        QToolTip.hideText()
        super().leaveEvent(event)

    def _content_rect(self) -> QRectF:
        """Return the inner preview area that can show rendered SVG content."""
        frame_rect = self.rect().adjusted(1, 1, -1, -1)
        return QRectF(frame_rect.adjusted(12, 12, -12, -12))

    def _effective_view_box(self) -> QRectF | None:
        """Return the active SVG view box used by the renderer."""
        if self._renderer is None:
            return None
        view_box = self._renderer.viewBoxF()
        if view_box.isValid() and view_box.width() > 0.0 and view_box.height() > 0.0:
            return view_box
        default_size = self._renderer.defaultSize()
        return QRectF(
            0.0,
            0.0,
            max(float(default_size.width()), 1.0),
            max(float(default_size.height()), 1.0),
        )

    def _fit_rect(self, rect: QRectF, source_width: float, source_height: float) -> QRectF:
        """Return the largest centered target rectangle that preserves aspect ratio."""
        if source_width <= 0.0 or source_height <= 0.0:
            return rect
        scale = min(rect.width() / source_width, rect.height() / source_height)
        width = source_width * scale
        height = source_height * scale
        return QRectF(
            rect.center().x() - width / 2.0,
            rect.center().y() - height / 2.0,
            width,
            height,
        )

    def _current_target_rect(self, content_rect: QRectF, view_box: QRectF) -> QRectF:
        """Return the zoomed and panned target rectangle for the current SVG."""
        base_rect = self._fit_rect(content_rect, view_box.width(), view_box.height())
        zoomed_width = base_rect.width() * self._zoom
        zoomed_height = base_rect.height() * self._zoom
        center = QPointF(
            base_rect.center().x() + self._pan_offset.x(),
            base_rect.center().y() + self._pan_offset.y(),
        )
        return QRectF(
            center.x() - zoomed_width / 2.0,
            center.y() - zoomed_height / 2.0,
            zoomed_width,
            zoomed_height,
        )

    def _svg_to_widget_transform(self, view_box: QRectF, target_rect: QRectF) -> QTransform:
        """Build the exact SVG-to-widget transform shared by the renderer and overlays."""
        scale_x = target_rect.width() / view_box.width()
        scale_y = target_rect.height() / view_box.height()
        transform = QTransform()
        transform.translate(target_rect.x(), target_rect.y())
        transform.scale(scale_x, scale_y)
        transform.translate(-view_box.x(), -view_box.y())
        return transform

    def _clamp_pan_offset(self) -> None:
        """Keep the zoomed image covering the preview surface without empty gaps."""
        view_box = self._effective_view_box()
        if view_box is None:
            return

        content_rect = self._content_rect()
        base_rect = self._fit_rect(content_rect, view_box.width(), view_box.height())
        zoomed_width = base_rect.width() * self._zoom
        zoomed_height = base_rect.height() * self._zoom
        content_center = content_rect.center()

        if zoomed_width <= content_rect.width():
            clamped_x = 0.0
        else:
            min_center_x = content_rect.right() - zoomed_width / 2.0
            max_center_x = content_rect.left() + zoomed_width / 2.0
            target_center_x = min(
                max(content_center.x() + self._pan_offset.x(), min_center_x),
                max_center_x,
            )
            clamped_x = target_center_x - content_center.x()

        if zoomed_height <= content_rect.height():
            clamped_y = 0.0
        else:
            min_center_y = content_rect.bottom() - zoomed_height / 2.0
            max_center_y = content_rect.top() + zoomed_height / 2.0
            target_center_y = min(
                max(content_center.y() + self._pan_offset.y(), min_center_y),
                max_center_y,
            )
            clamped_y = target_center_y - content_center.y()

        self._pan_offset = QPointF(clamped_x, clamped_y)

    def _annotation_at(self, position: QPointF) -> PreviewAnnotation | None:
        """Return the top-most annotation currently under the given widget position."""
        for rect, annotation in reversed(self._mapped_annotations):
            if rect.contains(position):
                return annotation
        return None

    def _map_annotation_rect(
        self,
        annotation: PreviewAnnotation,
        svg_to_widget: QTransform,
    ) -> QRectF:
        """Map one SVG-space annotation rectangle into widget-space coordinates."""
        return svg_to_widget.mapRect(QRectF(annotation.x, annotation.y, annotation.width, annotation.height))

    def _paint_annotation(self, painter: QPainter, rect: QRectF, annotation: PreviewAnnotation) -> None:
        """Draw one highlighted conversion-impact region."""
        status_palette = self._annotation_palette(annotation.status)
        painter.setPen(QPen(status_palette["stroke"], 2.0))
        painter.setBrush(status_palette["fill"])
        painter.drawRoundedRect(rect, 6, 6)

        badge_center = QPointF(rect.left() + 12.0, rect.top() + 12.0)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(status_palette["stroke"])
        painter.drawEllipse(badge_center, 8.0, 8.0)

    def _palette(self) -> dict[str, QColor]:
        """Return the preview frame colors for the current theme."""
        if self._is_dark:
            return {
                "bg": QColor("#0f172a"),
                "surface": QColor("#111827"),
                "frame": QColor("#334155"),
                "outline": QColor("#475569"),
                "text": QColor("#cbd5e1"),
            }
        return {
            "bg": QColor("#f1f5f9"),
            "surface": QColor("#ffffff"),
            "frame": QColor("#dbe3ef"),
            "outline": QColor("#cbd5e1"),
            "text": QColor("#64748b"),
        }

    def _annotation_palette(self, status: str) -> dict[str, QColor]:
        """Return overlay colors for one annotation status."""
        if status == "fallback":
            return {
                "stroke": QColor("#dc2626"),
                "fill": QColor(220, 38, 38, 45),
            }
        return {
            "stroke": QColor("#d97706"),
            "fill": QColor(217, 119, 6, 40),
        }
