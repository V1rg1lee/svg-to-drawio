"""Design tokens, stylesheet, and icon/asset helpers shared across desktop pages."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QGuiApplication, QIcon, QPainter, QPainterPath, QPalette, QPen, QPixmap
from PySide6.QtWidgets import QApplication

LIGHT: dict[str, str] = {
    "bg": "#f1f5f9",
    "card_bg": "white",
    "card_border": "#e2e8f0",
    "title_color": "#1e3a8a",
    "version_color": "#94a3b8",
    "text": "#1f2937",
    "text_muted": "#64748b",
    "input_bg": "white",
    "input_border": "#e2e8f0",
    "input_color": "#1e293b",
    "log_surface_bg": "#fbfdff",
    "log_surface_border": "#d7e0ec",
    "scrollbar_handle": "#cbd5e1",
    "scrollbar_hover": "#94a3b8",
    "menubar_bg": "white",
    "menubar_border": "#e2e8f0",
    "menu_bg": "white",
    "menu_border": "#e2e8f0",
    "menu_selected_bg": "#eff6ff",
    "menu_selected_color": "#1d4ed8",
    "btn_bg": "#f8fafc",
    "btn_color": "#374151",
    "btn_border": "#d1d5db",
    "btn_hover_bg": "#f0f9ff",
    "btn_hover_border": "#93c5fd",
    "btn_hover_color": "#1d4ed8",
    "btn_pressed_bg": "#dbeafe",
    "btn_disabled_bg": "#f8fafc",
    "btn_disabled_color": "#9ca3af",
    "btn_disabled_border": "#e5e7eb",
    "progress_track": "#e2e8f0",
    "selection_bg": "#dbeafe",
    "selection_color": "#1e40af",
    "list_selected_bg": "#eff6ff",
    "list_selected_color": "#1e40af",
    "list_hover_bg": "#f8fafc",
    "checkbox_color": "#374151",
    "checkbox_border": "#d1d5db",
    "checkbox_bg": "white",
    "success_bg": "#f0fdf4",
    "success_border": "#86efac",
    "success_label": "#15803d",
    "success_value": "#166534",
    "warning_bg": "#fffbeb",
    "warning_border": "#fde68a",
    "warning_label": "#92400e",
    "warning_value": "#78350f",
    "error_bg": "#fff1f2",
    "error_border": "#fecdd3",
    "error_label": "#be123c",
    "error_value": "#9f1239",
    "neutral_bg": "#f8fafc",
    "neutral_border": "#e2e8f0",
    "neutral_label": "#475569",
    "neutral_value": "#334155",
    "add_btn_bg": "#eff6ff",
    "add_btn_color": "#1d4ed8",
    "add_btn_border": "#bfdbfe",
    "add_btn_hover_bg": "#dbeafe",
    "add_btn_hover_border": "#93c5fd",
    "add_btn_hover_color": "#1e40af",
    "remove_btn_bg": "#f8fafc",
    "remove_btn_color": "#64748b",
    "remove_btn_border": "#e2e8f0",
    "remove_btn_hover_bg": "#f1f5f9",
    "remove_btn_hover_color": "#475569",
    "remove_btn_hover_border": "#cbd5e1",
    "clear_btn_bg": "#fff7ed",
    "clear_btn_color": "#c2410c",
    "clear_btn_border": "#fed7aa",
    "clear_btn_hover_bg": "#ffedd5",
    "clear_btn_hover_border": "#fb923c",
    "clear_btn_hover_color": "#9a3412",
    "log_converted": "#15803d",
    "log_failed": "#dc2626",
    "log_warning": "#d97706",
    "log_skipped": "#6b7280",
    "log_info": "#2563eb",
    "log_default": "#374151",
    "log_ts": "#94a3b8",
}

DARK: dict[str, str] = {
    "bg": "#0f172a",
    "card_bg": "#1e293b",
    "card_border": "#334155",
    "title_color": "#93c5fd",
    "version_color": "#64748b",
    "text": "#e8edf4",
    "text_muted": "#94a3b8",
    "input_bg": "#1e293b",
    "input_border": "#334155",
    "input_color": "#f1f5f9",
    "log_surface_bg": "#0f172a",
    "log_surface_border": "#1e293b",
    "scrollbar_handle": "#334155",
    "scrollbar_hover": "#475569",
    "menubar_bg": "#1e293b",
    "menubar_border": "#334155",
    "menu_bg": "#1e293b",
    "menu_border": "#334155",
    "menu_selected_bg": "#1e3a5f",
    "menu_selected_color": "#93c5fd",
    "btn_bg": "#1e293b",
    "btn_color": "#cbd5e1",
    "btn_border": "#334155",
    "btn_hover_bg": "#1e3a5f",
    "btn_hover_border": "#3b82f6",
    "btn_hover_color": "#93c5fd",
    "btn_pressed_bg": "#1e3a5f",
    "btn_disabled_bg": "#1e293b",
    "btn_disabled_color": "#475569",
    "btn_disabled_border": "#334155",
    "progress_track": "#334155",
    "selection_bg": "#1e40af",
    "selection_color": "#e0f2fe",
    "list_selected_bg": "#1e3a5f",
    "list_selected_color": "#93c5fd",
    "list_hover_bg": "#334155",
    "checkbox_color": "#cbd5e1",
    "checkbox_border": "#475569",
    "checkbox_bg": "#334155",
    "success_bg": "#052e16",
    "success_border": "#166534",
    "success_label": "#86efac",
    "success_value": "#4ade80",
    "warning_bg": "#431407",
    "warning_border": "#92400e",
    "warning_label": "#fde68a",
    "warning_value": "#fbbf24",
    "error_bg": "#4c0519",
    "error_border": "#9f1239",
    "error_label": "#fecdd3",
    "error_value": "#fb7185",
    "neutral_bg": "#1e293b",
    "neutral_border": "#334155",
    "neutral_label": "#94a3b8",
    "neutral_value": "#cbd5e1",
    "add_btn_bg": "#1e3a5f",
    "add_btn_color": "#93c5fd",
    "add_btn_border": "#1e40af",
    "add_btn_hover_bg": "#1e40af",
    "add_btn_hover_border": "#3b82f6",
    "add_btn_hover_color": "#bfdbfe",
    "remove_btn_bg": "#1e293b",
    "remove_btn_color": "#94a3b8",
    "remove_btn_border": "#334155",
    "remove_btn_hover_bg": "#334155",
    "remove_btn_hover_color": "#cbd5e1",
    "remove_btn_hover_border": "#475569",
    "clear_btn_bg": "#431407",
    "clear_btn_color": "#fb923c",
    "clear_btn_border": "#7c2d12",
    "clear_btn_hover_bg": "#7c2d12",
    "clear_btn_hover_border": "#ea580c",
    "clear_btn_hover_color": "#fed7aa",
    "log_converted": "#4ade80",
    "log_failed": "#f87171",
    "log_warning": "#fbbf24",
    "log_skipped": "#9ca3af",
    "log_info": "#60a5fa",
    "log_default": "#e2e8f0",
    "log_ts": "#64748b",
}

# Status glyphs paired with color tokens so state never relies on color alone.
STATUS_ICON: dict[str, str] = {
    "success": "✓",  # check mark
    "warning": "⚠",  # warning triangle
    "error": "✕",  # multiplication x
    "neutral": "ℹ",  # info
}


def tokens(is_dark: bool) -> dict[str, str]:
    """Return the active color token dictionary for the given theme mode."""
    return DARK if is_dark else LIGHT


def detect_system_dark() -> bool:
    """Return True when the OS is currently using a dark colour scheme."""
    try:
        return bool(QGuiApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark)
    except AttributeError:
        palette = QApplication.palette()
        return bool(palette.color(QPalette.ColorRole.Window).lightness() < 128)


def asset_path(name: str) -> Path:
    """Return the path to a bundled desktop asset."""
    if hasattr(sys, "_MEIPASS"):
        return Path(getattr(sys, "_MEIPASS")) / "svg_to_drawio_desktop" / "assets" / name
    return Path(__file__).resolve().parent / "assets" / name


def create_fallback_icon() -> QIcon:
    """Build a procedural fallback icon when no asset file is available."""
    pixmap = QPixmap(128, 128)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#0f172a"))
    painter.drawRoundedRect(12, 12, 104, 104, 28, 28)

    painter.setBrush(QColor("#22c55e"))
    painter.drawEllipse(22, 24, 28, 28)
    painter.drawEllipse(78, 24, 28, 28)
    painter.drawEllipse(50, 74, 28, 28)

    edge_pen = QPen(QColor("#e2e8f0"), 9)
    edge_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(edge_pen)
    painter.drawLine(38, 50, 64, 74)
    painter.drawLine(90, 50, 64, 74)

    path_overlay = QPainterPath()
    path_overlay.addRoundedRect(18, 18, 92, 92, 22, 22)
    painter.setPen(QPen(QColor("#38bdf8"), 4))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawPath(path_overlay)
    painter.end()

    return QIcon(pixmap)


def load_app_icon() -> QIcon:
    """Load the window/taskbar icon."""
    ico_path = asset_path("app_logo.ico")
    png_path = asset_path("app_logo_256x256.png")

    if ico_path.is_file():
        icon = QIcon(str(ico_path))
        if not icon.isNull():
            return icon

    if png_path.is_file():
        icon = QIcon(str(png_path))
        if not icon.isNull():
            return icon

    return create_fallback_icon()


def load_brand_pixmap(size: int = 40) -> QPixmap:
    """Load the logo displayed in the header and welcome panel."""
    png_path = asset_path("app_logo_256x256.png")
    if png_path.is_file():
        pixmap = QPixmap(str(png_path))
        if not pixmap.isNull():
            return pixmap.scaled(
                size,
                size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )

    ico_path = asset_path("app_logo.ico")
    if ico_path.is_file():
        icon = QIcon(str(ico_path))
        if not icon.isNull():
            return icon.pixmap(size, size)

    return create_fallback_icon().pixmap(size, size)


def build_stylesheet(t: dict[str, str]) -> str:
    """Build the application-wide stylesheet for the given color token set."""
    return f"""
        QMainWindow {{
            background: {t["bg"]};
        }}
        QWidget {{
            font-size: 13px;
            color: {t["text"]};
        }}
        QScrollArea {{
            background: {t["bg"]};
            border: none;
        }}
        QScrollArea > QWidget {{
            background: {t["bg"]};
        }}
        QStackedWidget {{
            background: {t["bg"]};
        }}
        QWidget#contentRoot, QWidget#pageRoot {{
            background: {t["bg"]};
        }}
        /* Top header bar */
        QFrame#headerBar {{
            background: {t["menubar_bg"]};
            border-bottom: 1px solid {t["menubar_border"]};
        }}
        QLabel#headerTitle {{
            color: {t["title_color"]};
            background: transparent;
            border: none;
            font-size: 14px;
            font-weight: 700;
        }}
        QLabel#headerVersion {{
            color: {t["version_color"]};
            background: transparent;
            border: none;
            font-size: 11px;
        }}
        /* Nav pills */
        QPushButton#navPill {{
            background: transparent;
            color: {t["text_muted"]};
            border: none;
            border-radius: 8px;
            padding: 7px 18px;
            font-weight: 600;
            font-size: 13px;
        }}
        QPushButton#navPill:hover {{
            background: {t["btn_hover_bg"]};
            color: {t["btn_hover_color"]};
        }}
        QPushButton#navPill:checked {{
            background: {t["menu_selected_bg"]};
            color: {t["menu_selected_color"]};
        }}
        /* Welcome / page intro */
        QLabel#pageHeading {{
            color: {t["title_color"]};
            background: transparent;
            border: none;
            font-size: 19px;
            font-weight: 700;
        }}
        QLabel#pageSubheading {{
            color: {t["text_muted"]};
            background: transparent;
            border: none;
            font-size: 13px;
        }}
        /* Panel cards */
        QGroupBox, QFrame#card {{
            background: {t["card_bg"]};
            border: 1.5px solid {t["card_border"]};
            border-radius: 14px;
        }}
        QGroupBox {{
            margin-top: 0;
            padding-top: 40px;
        }}
        QGroupBox::title {{
            subcontrol-origin: padding;
            subcontrol-position: top left;
            left: 16px;
            top: 12px;
            padding: 0;
            background: transparent;
            border: none;
            color: {t["text_muted"]};
            font-size: 11.5px;
            font-weight: 700;
        }}
        QFrame#logSurface, QFrame#compatibilitySurface {{
            background: {t["log_surface_bg"]};
            border: 1.5px solid {t["log_surface_border"]};
            border-radius: 12px;
        }}
        /* Disclosure / collapsible section */
        QToolButton#disclosureHeader {{
            background: transparent;
            border: none;
            color: {t["text"]};
            font-weight: 600;
            font-size: 12.5px;
            padding: 4px 2px;
            text-align: left;
        }}
        QToolButton#disclosureHeader:hover {{
            color: {t["btn_hover_color"]};
        }}
        /* Summary label */
        QLabel#summaryLabel {{
            color: {t["text_muted"]};
            font-size: 11.5px;
            font-style: italic;
        }}
        QLabel#compatibilityHeading {{
            color: {t["title_color"]};
            font-size: 13px;
            font-weight: 700;
            background: transparent;
            border: none;
        }}
        QLabel#compatibilitySummaryLabel {{
            color: {t["text"]};
            background: transparent;
            border: none;
        }}
        QTextBrowser#compatibilityOutput {{
            background: transparent;
            border: none;
            color: {t["text"]};
        }}
        /* Counter cards */
        QFrame#successCard {{
            background: {t["success_bg"]};
            border: 1.5px solid {t["success_border"]}; border-radius: 12px;
        }}
        QLabel#successCardTitle {{
            color: {t["success_label"]}; font-size: 10.5px; font-weight: 700;
            letter-spacing: 0.5px; background: transparent; border: none;
        }}
        QLabel#successCardValue {{ color: {t["success_value"]}; background: transparent; border: none; }}
        QFrame#warningCard {{
            background: {t["warning_bg"]};
            border: 1.5px solid {t["warning_border"]}; border-radius: 12px;
        }}
        QLabel#warningCardTitle {{
            color: {t["warning_label"]}; font-size: 10.5px; font-weight: 700;
            letter-spacing: 0.5px; background: transparent; border: none;
        }}
        QLabel#warningCardValue {{ color: {t["warning_value"]}; background: transparent; border: none; }}
        QFrame#errorCard {{
            background: {t["error_bg"]};
            border: 1.5px solid {t["error_border"]}; border-radius: 12px;
        }}
        QLabel#errorCardTitle {{
            color: {t["error_label"]}; font-size: 10.5px; font-weight: 700;
            letter-spacing: 0.5px; background: transparent; border: none;
        }}
        QLabel#errorCardValue {{ color: {t["error_value"]}; background: transparent; border: none; }}
        QFrame#neutralCard {{
            background: {t["neutral_bg"]};
            border: 1.5px solid {t["neutral_border"]}; border-radius: 12px;
        }}
        QLabel#neutralCardTitle {{
            color: {t["neutral_label"]}; font-size: 10.5px; font-weight: 700;
            letter-spacing: 0.5px; background: transparent; border: none;
        }}
        QLabel#neutralCardValue {{ color: {t["neutral_value"]}; background: transparent; border: none; }}
        /* Default / secondary buttons */
        QPushButton, QToolButton {{
            background: {t["btn_bg"]};
            color: {t["btn_color"]};
            border: 1.5px solid {t["btn_border"]};
            border-radius: 8px;
            padding: 7px 14px;
            font-weight: 500;
        }}
        QPushButton:hover:!disabled, QToolButton:hover:!disabled {{
            background: {t["btn_hover_bg"]};
            border-color: {t["btn_hover_border"]};
            color: {t["btn_hover_color"]};
        }}
        QPushButton:pressed, QToolButton:pressed {{
            background: {t["btn_pressed_bg"]};
        }}
        QPushButton:focus, QToolButton:focus {{
            border-color: #3b82f6;
        }}
        QPushButton:disabled, QToolButton:disabled {{
            background: {t["btn_disabled_bg"]};
            color: {t["btn_disabled_color"]};
            border-color: {t["btn_disabled_border"]};
        }}
        /* Theme toggle and overflow menu - blend into header */
        QPushButton#themeButton, QToolButton#overflowButton {{
            background: transparent;
            border: none;
            border-radius: 6px;
            padding: 4px 8px;
            color: {t["text_muted"]};
        }}
        QPushButton#themeButton:hover, QToolButton#overflowButton:hover {{
            background: {t["btn_hover_bg"]};
            color: {t["btn_hover_color"]};
            border: none;
        }}
        QToolButton#helpBadge {{
            min-width: 20px;
            max-width: 20px;
            min-height: 20px;
            max-height: 20px;
            padding: 0;
            border-radius: 10px;
            border: 1.5px solid {t["btn_border"]};
            background: {t["card_bg"]};
            color: {t["text_muted"]};
            font-weight: 700;
        }}
        QToolButton#helpBadge:hover:!disabled {{
            background: {t["btn_hover_bg"]};
            border-color: {t["btn_hover_border"]};
            color: {t["btn_hover_color"]};
        }}
        /* Primary action */
        QPushButton#startButton {{
            background: #2563eb;
            color: white;
            border: none;
            border-radius: 10px;
            padding: 11px 24px;
            font-weight: 700;
            font-size: 13.5px;
        }}
        QPushButton#startButton:hover:!disabled {{
            background: #1d4ed8;
            color: white;
        }}
        QPushButton#startButton:disabled {{
            background: #93c5fd;
            color: #dbeafe;
            border: none;
        }}
        /* Destructive action */
        QPushButton#cancelButton {{
            background: {t["error_bg"]};
            color: {t["error_label"]};
            border: 1.5px solid {t["error_border"]};
        }}
        QPushButton#cancelButton:hover:!disabled {{
            background: {t["error_border"]};
            border-color: {t["error_label"]};
            color: {t["error_value"]};
        }}
        QPushButton#cancelButton:disabled {{
            background: {t["btn_disabled_bg"]};
            color: {t["btn_disabled_color"]};
            border-color: {t["btn_disabled_border"]};
        }}
        /* Success action */
        QPushButton#openOutputButton:enabled {{
            background: {t["success_bg"]};
            color: {t["success_label"]};
            border: 1.5px solid {t["success_border"]};
        }}
        QPushButton#openOutputButton:hover:!disabled {{
            background: {t["success_border"]};
            border-color: {t["success_label"]};
            color: {t["success_value"]};
        }}
        QPushButton#openOutputButton:disabled {{
            background: {t["btn_disabled_bg"]};
            color: {t["btn_disabled_color"]};
            border-color: {t["btn_disabled_border"]};
        }}
        /* Inputs */
        QListWidget, QLineEdit {{
            background: {t["input_bg"]};
            border: 1.5px solid {t["input_border"]};
            border-radius: 10px;
            color: {t["input_color"]};
            padding: 6px;
            selection-background-color: {t["selection_bg"]};
            selection-color: {t["selection_color"]};
        }}
        QListWidget:focus, QLineEdit:focus {{
            border-color: #3b82f6;
        }}
        QListWidget::item {{
            padding: 7px 10px;
            border-radius: 6px;
            color: {t["input_color"]};
        }}
        QListWidget::item:selected {{
            background: {t["list_selected_bg"]};
            color: {t["list_selected_color"]};
        }}
        QListWidget::item:hover:!selected {{
            background: {t["list_hover_bg"]};
        }}
        QTextBrowser {{
            background: {t["input_bg"]};
            border: 1.5px solid {t["input_border"]};
            border-radius: 10px;
            color: {t["input_color"]};
            padding: 8px;
            selection-background-color: {t["selection_bg"]};
        }}
        QTextBrowser#logOutput {{
            background: transparent;
            border: none;
            padding: 0;
        }}
        /* Progress bar */
        QProgressBar {{
            border: none;
            border-radius: 7px;
            background: {t["progress_track"]};
            min-height: 12px;
            max-height: 12px;
        }}
        QProgressBar::chunk {{
            border-radius: 7px;
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 #3b82f6, stop:1 #8b5cf6);
        }}
        /* Checkboxes */
        QCheckBox {{
            spacing: 8px;
            color: {t["checkbox_color"]};
        }}
        QCheckBox::indicator {{
            width: 17px;
            height: 17px;
            border: 2px solid {t["checkbox_border"]};
            border-radius: 5px;
            background: {t["checkbox_bg"]};
        }}
        QCheckBox::indicator:checked {{
            background: #2563eb;
            border-color: #2563eb;
        }}
        QCheckBox::indicator:hover {{
            border-color: #3b82f6;
        }}
        QLabel {{
            color: {t["text"]};
            background: transparent;
        }}
        QMenu {{
            background: {t["menu_bg"]};
            border: 1px solid {t["menu_border"]};
            border-radius: 10px;
            padding: 4px;
        }}
        QMenu::item {{
            padding: 8px 20px;
            color: {t["text"]};
            border-radius: 6px;
        }}
        QMenu::item:selected {{
            background: {t["menu_selected_bg"]};
            color: {t["menu_selected_color"]};
        }}
        /* Source list buttons */
        QPushButton#addFilesButton, QPushButton#addFolderButton {{
            background: {t["add_btn_bg"]};
            color: {t["add_btn_color"]};
            border: 1.5px solid {t["add_btn_border"]};
            font-weight: 600;
        }}
        QPushButton#addFilesButton:hover:!disabled, QPushButton#addFolderButton:hover:!disabled {{
            background: {t["add_btn_hover_bg"]};
            border-color: {t["add_btn_hover_border"]};
            color: {t["add_btn_hover_color"]};
        }}
        QPushButton#removeSelectedButton {{
            background: {t["remove_btn_bg"]};
            color: {t["remove_btn_color"]};
            border: 1.5px solid {t["remove_btn_border"]};
        }}
        QPushButton#removeSelectedButton:hover:!disabled {{
            background: {t["remove_btn_hover_bg"]};
            color: {t["remove_btn_hover_color"]};
            border-color: {t["remove_btn_hover_border"]};
        }}
        QPushButton#clearQueueButton {{
            background: {t["clear_btn_bg"]};
            color: {t["clear_btn_color"]};
            border: 1.5px solid {t["clear_btn_border"]};
        }}
        QPushButton#clearQueueButton:hover:!disabled {{
            background: {t["clear_btn_hover_bg"]};
            border-color: {t["clear_btn_hover_border"]};
            color: {t["clear_btn_hover_color"]};
        }}
        /* Thin modern scrollbars */
        QScrollBar:vertical {{
            background: transparent;
            width: 8px;
        }}
        QScrollBar::handle:vertical {{
            background: {t["scrollbar_handle"]};
            border-radius: 4px;
            min-height: 24px;
        }}
        QScrollBar::handle:vertical:hover {{
            background: {t["scrollbar_hover"]};
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}
        QScrollBar:horizontal {{
            background: transparent;
            height: 8px;
        }}
        QScrollBar::handle:horizontal {{
            background: {t["scrollbar_handle"]};
            border-radius: 4px;
        }}
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
        QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{ background: none; }}
        /* Clear log button - small, neutral */
        QPushButton#clearLogButton {{
            background: transparent;
            color: {t["text_muted"]};
            border: 1px solid {t["btn_border"]};
            border-radius: 6px;
            padding: 2px 10px;
            font-size: 11px;
        }}
        QPushButton#clearLogButton:hover {{
            background: {t["btn_hover_bg"]};
            color: {t["btn_hover_color"]};
            border-color: {t["btn_hover_border"]};
        }}
        /* SpinBox */
        QSpinBox {{
            background: {t["input_bg"]};
            color: {t["input_color"]};
            border: 1.5px solid {t["input_border"]};
            border-radius: 6px;
            padding: 3px 6px;
        }}
    """
