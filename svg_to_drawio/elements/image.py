"""Emitters and helpers for SVG image elements."""

from __future__ import annotations

import base64
import binascii
import mimetypes
from os import path
from urllib.parse import quote_from_bytes, unquote_to_bytes
from xml.etree.ElementTree import Element

from ..cell_factory import make_box_vertex
from ..element_geometry import BoundsBox, image_bounds
from ..emitter_context import EmitterContext
from ..style_builder import StyleBuilder
from ..styles import get_visual, opacity_pct
from ..transforms import Matrix
from ..utils import parse_length
from .style_support import add_metadata_styles


def _data_uri_from_bytes(mime: str, raw_bytes: bytes) -> str:
    """Encode bytes as a percent-escaped data URI."""
    return f"data:{mime},{quote_from_bytes(raw_bytes, safe='')}"


def _base64_data_uri_from_bytes(mime: str, raw_bytes: bytes) -> str:
    """Encode bytes as a base64 data URI."""
    payload = base64.b64encode(raw_bytes).decode("ascii")
    return f"data:{mime};base64,{payload}"


def _normalize_data_uri(href: str) -> tuple[str | None, str | None]:
    """Normalize a data URI to a draw.io-safe representation."""
    try:
        header, payload = href.split(",", 1)
    except ValueError:
        return None, None

    media = header[5:] or "text/plain"
    media_type = media.split(";", 1)[0] or "text/plain"

    if ";base64" in media.lower():
        try:
            raw = base64.b64decode(payload)
        except (ValueError, binascii.Error):
            return None, None
    else:
        raw = unquote_to_bytes(payload)

    if media_type == "image/svg+xml":
        return _data_uri_from_bytes(media_type, raw), media_type
    return _base64_data_uri_from_bytes(media_type, raw), media_type


def _escape_xml_attr(value: str) -> str:
    """Escape a string for use inside an XML attribute."""
    return value.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;").replace(">", "&gt;")


def _svg_wrapper_data_uri(image_ref: str, width: float, height: float, preserve: str) -> str:
    """Wrap a raster image in a tiny SVG so draw.io can preserve aspect settings."""
    preserve = preserve or "xMidYMid meet"
    safe_href = _escape_xml_attr(image_ref)
    safe_preserve = _escape_xml_attr(preserve)
    svg = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width:.6f} {height:.6f}" '
        f'width="{width:.6f}" height="{height:.6f}">\n'
        f'  <image href="{safe_href}" x="0" y="0" width="{width:.6f}" height="{height:.6f}" '
        f'preserveAspectRatio="{safe_preserve}"/>\n'
        "</svg>\n"
    )
    return _data_uri_from_bytes("image/svg+xml", svg.encode("utf-8"))


def emit_embedded_image_uri(
    ctx: EmitterContext,
    elem: Element,
    *,
    image_ref: str,
    box: BoundsBox,
    opacity: int = 100,
    aspect_style: int = 1,
) -> None:
    """Emit a draw.io image cell from a pre-built embeddable image URI."""
    style = StyleBuilder()
    style.add("shape", "image").add("html", 1).add("image", image_ref).add("aspect", "fixed")
    style.add("imageAspect", aspect_style).add("opacity", opacity)
    style.add("strokeColor", "none").add("fillColor", "none")
    add_metadata_styles(style, elem, ctx)
    ctx.add(make_box_vertex(ctx, style.build(), box))


def _resolve_image_href(ctx: EmitterContext, href: str | None) -> tuple[str | None, str | None]:
    """Resolve an image href to a safe embeddable reference and MIME type."""
    if not href:
        return None, None

    href = href.strip()
    if not href:
        return None, None

    if href.startswith("data:"):
        image_ref, mime = _normalize_data_uri(href)
        if image_ref:
            ctx.report.add_asset(href=href, status="embedded", mime_type=mime)
        else:
            ctx.report.add_asset(href=href, status="invalid", message="Invalid image data URI.")
        return image_ref, mime

    if "://" in href:
        mime = mimetypes.guess_type(href)[0] or ""
        ctx.report.add_asset(href=href, status="remote", mime_type=mime or None)
        return href, mime

    asset_path = href
    if not path.isabs(asset_path):
        asset_path = path.join(ctx.source_dir, asset_path)
    asset_path = path.abspath(path.normpath(asset_path))
    base_dir = path.abspath(ctx.source_dir) if ctx.source_dir else ""
    if base_dir:
        try:
            if path.commonpath([base_dir, asset_path]) != base_dir:
                ctx.report.add_asset(
                    href=href,
                    status="rejected",
                    resolved_path=asset_path,
                    message="Local image is outside the source directory tree.",
                )
                return None, None
        except ValueError:
            ctx.report.add_asset(
                href=href,
                status="rejected",
                resolved_path=asset_path,
                message="Local image could not be resolved safely.",
            )
            return None, None
    if not path.isfile(asset_path):
        ctx.report.add_asset(
            href=href,
            status="missing",
            resolved_path=asset_path,
            message="Local image file does not exist.",
        )
        return None, None

    mime = mimetypes.guess_type(asset_path)[0] or "application/octet-stream"
    with open(asset_path, "rb") as handle:
        raw = handle.read()
    ctx.report.add_dependency(asset_path)
    ctx.report.add_asset(href=href, status="embedded", resolved_path=asset_path, mime_type=mime)
    if mime == "image/svg+xml":
        return _data_uri_from_bytes(mime, raw), mime
    return _base64_data_uri_from_bytes(mime, raw), mime


def emit_image(ctx: EmitterContext, elem: Element, matrix: Matrix, css: dict[str, str] | None = None) -> None:
    """Emit an SVG `<image>`."""
    href = elem.get("href") or elem.get("{http://www.w3.org/1999/xlink}href") or ""
    image_ref, mime = _resolve_image_href(ctx, href)
    if not image_ref:
        return

    x0 = parse_length(elem.get("x"))
    y0 = parse_length(elem.get("y"))
    width0 = parse_length(elem.get("width"))
    height0 = parse_length(elem.get("height"))
    if width0 <= 0 or height0 <= 0:
        return

    visual = get_visual(elem, css)
    opacity = opacity_pct(visual["opacity"])

    box = image_bounds(matrix, x0, y0, width0, height0)
    rotation = box.rotation_if_visible()
    rotation_style = f"{rotation:.2f}" if rotation is not None else None

    preserve_raw = (elem.get("preserveAspectRatio") or "").strip()
    preserve = preserve_raw.lower()
    aspect_style = 0 if preserve == "none" else 1
    if mime and mime != "image/svg+xml":
        image_ref = _svg_wrapper_data_uri(image_ref, width0, height0, preserve_raw)

    style = StyleBuilder()
    style.add("shape", "image").add("html", 1).add("image", image_ref).add("aspect", "fixed")
    style.add("imageAspect", aspect_style).add("opacity", opacity)
    style.add("strokeColor", "none").add("fillColor", "none")
    style.add("rotation", rotation_style, when=rotation_style is not None)
    add_metadata_styles(style, elem, ctx)
    ctx.add(make_box_vertex(ctx, style.build(), box))
