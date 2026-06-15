"""PySide6 desktop application for the SVG-to-draw.io converter."""

from __future__ import annotations

import html
import sys
from datetime import datetime
from os import path
from pathlib import Path
from typing import cast

from PySide6.QtCore import Qt, QThread, QUrl
from PySide6.QtGui import (
    QAction,
    QCloseEvent,
    QColor,
    QDesktopServices,
    QFont,
    QGuiApplication,
    QIcon,
    QPainter,
    QPainterPath,
    QPalette,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)
from svg_to_drawio import __version__
from svg_to_drawio.conversion_service import (
    ConversionEvent,
    ConversionEventKind,
    ConversionOptions,
    ConversionSummary,
)

from .widgets import SourceListWidget
from .worker import ConversionWorker

APP_TITLE = "SVG to draw.io"
GITHUB_URL = "https://github.com/V1rg1lee/svg-to-drawio"

_LIGHT: dict[str, str] = {
    "bg": "#f1f5f9",
    "card_bg": "white",
    "card_border": "#e2e8f0",
    "hero_start": "#eff6ff",
    "hero_end": "#e0f2fe",
    "hero_border": "#bae6fd",
    "title_color": "#1e3a8a",
    "version_color": "#94a3b8",
    "subtitle_color": "#3b82f6",
    "text": "#374151",
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

_DARK: dict[str, str] = {
    "bg": "#0f172a",
    "card_bg": "#1e293b",
    "card_border": "#334155",
    "hero_start": "#1a2744",
    "hero_end": "#0f1f3d",
    "hero_border": "#1e40af",
    "title_color": "#93c5fd",
    "version_color": "#64748b",
    "subtitle_color": "#60a5fa",
    "text": "#e2e8f0",
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


def _detect_system_dark() -> bool:
    """Return True when the OS is currently using a dark colour scheme."""
    try:
        return bool(QGuiApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark)
    except AttributeError:
        palette = QApplication.palette()
        return bool(palette.color(QPalette.ColorRole.Window).lightness() < 128)


def _asset_path(name: str) -> Path:
    """Return the path to a bundled desktop asset."""
    if hasattr(sys, "_MEIPASS"):
        return Path(getattr(sys, "_MEIPASS")) / "svg_to_drawio_desktop" / "assets" / name
    return Path(__file__).resolve().parent / "assets" / name


def _create_fallback_icon() -> QIcon:
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


def _load_app_icon() -> QIcon:
    """Load the window/taskbar icon."""
    ico_path = _asset_path("app_logo.ico")
    png_path = _asset_path("app_logo_256x256.png")

    if ico_path.is_file():
        icon = QIcon(str(ico_path))
        if not icon.isNull():
            return icon

    if png_path.is_file():
        icon = QIcon(str(png_path))
        if not icon.isNull():
            return icon

    return _create_fallback_icon()


def _load_brand_pixmap(size: int = 80) -> QPixmap:
    """Load the logo displayed in the hero area."""
    png_path = _asset_path("app_logo_256x256.png")
    if png_path.is_file():
        pixmap = QPixmap(str(png_path))
        if not pixmap.isNull():
            return pixmap.scaled(
                size,
                size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )

    ico_path = _asset_path("app_logo.ico")
    if ico_path.is_file():
        icon = QIcon(str(ico_path))
        if not icon.isNull():
            return icon.pixmap(size, size)

    return _create_fallback_icon().pixmap(size, size)


class MainWindow(QMainWindow):
    """Desktop front-end for batch SVG-to-draw.io conversions."""

    def __init__(self) -> None:
        super().__init__()
        self._thread: QThread | None = None
        self._worker: ConversionWorker | None = None
        self._converted = 0
        self._skipped = 0
        self._failed = 0
        self._close_after_run = False
        self._last_openable_directory: str | None = None
        self._is_dark = _detect_system_dark()

        self.setWindowTitle(APP_TITLE)
        self.setWindowIcon(_load_app_icon())
        self.resize(1180, 780)
        self.setMinimumSize(960, 640)
        self._build_ui()
        self._install_actions()
        self._apply_styles()
        self._update_summary_labels()
        self._set_idle_state("Drop SVG files or folders to get started.")

        try:
            QGuiApplication.styleHints().colorSchemeChanged.connect(self._on_system_theme_changed)
        except AttributeError:
            pass  # Qt < 6.5

    def closeEvent(self, event: QCloseEvent) -> None:
        """Warn before closing while a conversion is still in progress."""
        if self._worker is None:
            super().closeEvent(event)
            return

        answer = QMessageBox.question(
            self,
            "Conversion in progress",
            "A conversion is still running. Cancel it and close the application?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self._close_after_run = True
            self._request_cancel()
            self.status_label.setText("Cancellation requested. The window will close after the worker stops.")
            event.ignore()
            return
        event.ignore()

    def _build_ui(self) -> None:
        """Create the window layout and child widgets."""
        scroll_area = QScrollArea()
        scroll_area.setObjectName("mainScrollArea")
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        central = QWidget()
        central.setObjectName("contentRoot")
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(24, 24, 24, 24)
        root_layout.setSpacing(18)

        hero = QFrame()
        hero.setObjectName("hero")
        hero_layout = QHBoxLayout(hero)
        hero_layout.setContentsMargins(28, 24, 28, 24)
        hero_layout.setSpacing(20)

        logo_label = QLabel()
        logo_label.setPixmap(_load_brand_pixmap(80))
        logo_label.setFixedSize(80, 80)
        logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hero_layout.addWidget(logo_label, alignment=Qt.AlignmentFlag.AlignVCenter)

        text_layout = QVBoxLayout()
        text_layout.setSpacing(6)

        self.title_label = QLabel()
        self.title_label.setObjectName("heroTitle")
        self.title_label.setTextFormat(Qt.TextFormat.RichText)
        title_font = QFont()
        title_font.setPointSize(20)
        title_font.setBold(True)
        self.title_label.setFont(title_font)

        self.subtitle_label = QLabel(
            "Convert SVG files to draw.io diagrams - individually or in batch. "
            "Drop files, pick options, then hit “Start Conversion”."
        )
        self.subtitle_label.setObjectName("heroSubtitle")
        self.subtitle_label.setWordWrap(True)

        text_layout.addWidget(self.title_label)
        text_layout.addWidget(self.subtitle_label)
        hero_layout.addLayout(text_layout, stretch=1)
        root_layout.addWidget(hero)

        content_layout = QHBoxLayout()
        content_layout.setSpacing(18)
        root_layout.addLayout(content_layout, stretch=1)

        left_panel = QVBoxLayout()
        left_panel.setSpacing(18)
        content_layout.addLayout(left_panel, stretch=5)

        right_panel = QVBoxLayout()
        right_panel.setSpacing(18)
        content_layout.addLayout(right_panel, stretch=3)

        left_panel.addWidget(self._build_sources_group(), stretch=3)
        left_panel.addWidget(self._build_log_group(), stretch=4)

        right_panel.addWidget(self._build_options_group())
        right_panel.addWidget(self._build_progress_group(), stretch=1)

        central.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.MinimumExpanding)
        central.setMinimumHeight(central.sizeHint().height())
        scroll_area.setWidget(central)
        self.setCentralWidget(scroll_area)

    def _build_sources_group(self) -> QGroupBox:
        """Create the source queue panel."""
        group = QGroupBox("Sources")
        layout = QVBoxLayout(group)
        layout.setContentsMargins(14, 6, 14, 14)
        layout.setSpacing(10)

        self.add_files_button = QPushButton("+ Add SVG Files")
        self.add_files_button.setObjectName("addFilesButton")
        self.add_folder_button = QPushButton("+ Add Folder")
        self.add_folder_button.setObjectName("addFolderButton")
        self.remove_selected_button = QPushButton("Remove Selected")
        self.remove_selected_button.setObjectName("removeSelectedButton")
        self.clear_sources_button = QPushButton("Clear Queue")
        self.clear_sources_button.setObjectName("clearQueueButton")

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)
        toolbar.addWidget(self.add_files_button)
        toolbar.addWidget(self.add_folder_button)
        toolbar.addStretch(1)
        toolbar.addWidget(self.remove_selected_button)
        toolbar.addWidget(self.clear_sources_button)
        layout.addLayout(toolbar)

        self.source_list = SourceListWidget()
        self.source_list.setMinimumHeight(160)
        self.source_list.paths_dropped.connect(self._add_paths)
        layout.addWidget(self.source_list, stretch=1)

        self.add_files_button.clicked.connect(self._choose_files)
        self.add_folder_button.clicked.connect(self._choose_folder)
        self.remove_selected_button.clicked.connect(self._remove_selected_sources)
        self.clear_sources_button.clicked.connect(self.source_list.clear)
        return group

    def _build_log_group(self) -> QGroupBox:
        """Create the scrolling event log."""
        group = QGroupBox("Live Log")
        layout = QVBoxLayout(group)
        layout.setContentsMargins(14, 6, 14, 14)
        layout.setSpacing(12)
        log_surface = QFrame()
        log_surface.setObjectName("logSurface")
        log_layout = QVBoxLayout(log_surface)
        log_layout.setContentsMargins(12, 12, 12, 16)
        log_layout.setSpacing(0)

        self.log_output = QTextEdit()
        self.log_output.setObjectName("logOutput")
        self.log_output.setReadOnly(True)
        self.log_output.setMinimumHeight(220)
        self.log_output.setFrameShape(QFrame.Shape.NoFrame)
        mono_font = QFont("Consolas")
        mono_font.setStyleHint(QFont.StyleHint.Monospace)
        mono_font.setPointSize(9)
        self.log_output.setFont(mono_font)
        self.log_output.setPlaceholderText("Conversion events will appear here...")
        log_layout.addWidget(self.log_output)
        layout.addWidget(log_surface)
        return group

    def _build_options_group(self) -> QGroupBox:
        """Create conversion option controls."""
        group = QGroupBox("Options")
        layout = QVBoxLayout(group)
        layout.setContentsMargins(14, 6, 14, 14)
        layout.setSpacing(14)

        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)

        output_row = QHBoxLayout()
        output_row.setSpacing(8)
        self.output_dir_edit = QLineEdit()
        self.output_dir_edit.setPlaceholderText("Optional: choose a dedicated output folder")
        browse_button = QToolButton()
        browse_button.setText("Browse")
        browse_button.clicked.connect(self._choose_output_dir)
        output_row.addWidget(self.output_dir_edit, stretch=1)
        output_row.addWidget(browse_button)

        output_container = QWidget()
        output_container.setLayout(output_row)
        form.addRow("Output directory", output_container)

        self.recursive_checkbox = QCheckBox("Recurse into subfolders when a queued item is a directory")
        self.overwrite_checkbox = QCheckBox("Overwrite existing `.drawio` files")
        self.flatten_checkbox = QCheckBox("Flatten groups - emit all shapes at the root level")
        form.addRow("", self.recursive_checkbox)
        form.addRow("", self.overwrite_checkbox)
        form.addRow("", self.flatten_checkbox)

        max_el_row = QHBoxLayout()
        max_el_row.setSpacing(6)
        max_el_row.setContentsMargins(0, 0, 0, 0)
        self.max_elements_checkbox = QCheckBox("Limit output to")
        self.max_elements_spinbox = QSpinBox()
        self.max_elements_spinbox.setRange(1, 999_999)
        self.max_elements_spinbox.setValue(1000)
        self.max_elements_spinbox.setSingleStep(500)
        self.max_elements_spinbox.setFixedWidth(80)
        self.max_elements_spinbox.setEnabled(False)
        self.max_elements_checkbox.toggled.connect(self.max_elements_spinbox.setEnabled)
        max_el_row.addWidget(self.max_elements_checkbox)
        max_el_row.addWidget(self.max_elements_spinbox)
        max_el_row.addWidget(QLabel("elements"))
        max_el_row.addStretch()
        max_el_container = QWidget()
        max_el_container.setLayout(max_el_row)
        form.addRow("", max_el_container)

        layout.addLayout(form)

        actions = QHBoxLayout()
        actions.setSpacing(10)
        self.start_button = QPushButton("Start Conversion")
        self.start_button.setObjectName("startButton")
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setObjectName("cancelButton")
        self.cancel_button.setEnabled(False)
        self.open_output_button = QPushButton("Open Output Folder")
        self.open_output_button.setObjectName("openOutputButton")
        self.open_output_button.setEnabled(False)

        self.start_button.clicked.connect(self._start_conversion)
        self.cancel_button.clicked.connect(self._request_cancel)
        self.open_output_button.clicked.connect(self._open_output_directory)

        actions.addWidget(self.start_button)
        actions.addWidget(self.cancel_button)
        actions.addWidget(self.open_output_button)
        layout.addLayout(actions)
        return group

    def _build_progress_group(self) -> QGroupBox:
        """Create progress and summary indicators."""
        group = QGroupBox("Progress")
        layout = QVBoxLayout(group)
        layout.setContentsMargins(14, 6, 14, 14)
        layout.setSpacing(14)

        self.status_label = QLabel()
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(False)
        layout.addWidget(self.progress_bar)

        self.summary_label = QLabel()
        self.summary_label.setObjectName("summaryLabel")
        self.summary_label.setWordWrap(True)
        layout.addWidget(self.summary_label)

        counts = QGridLayout()
        counts.setHorizontalSpacing(10)
        counts.setVerticalSpacing(10)

        self.converted_value = self._make_counter_label()
        self.skipped_value = self._make_counter_label()
        self.failed_value = self._make_counter_label()

        counts.addWidget(self._make_counter_card("Converted", self.converted_value, "success"), 0, 0)
        counts.addWidget(self._make_counter_card("Skipped", self.skipped_value, "warning"), 0, 1)
        counts.addWidget(self._make_counter_card("Failed", self.failed_value, "error"), 0, 2)
        layout.addLayout(counts)
        return group

    def _install_actions(self) -> None:
        """Populate the menu bar with common actions and the theme toggle."""
        file_menu = self.menuBar().addMenu("&File")
        add_files_action = QAction("Add SVG Files...", self)
        add_folder_action = QAction("Add Folder...", self)
        quit_action = QAction("Quit", self)

        add_files_action.triggered.connect(self._choose_files)
        add_folder_action.triggered.connect(self._choose_folder)
        quit_action.triggered.connect(self.close)

        file_menu.addAction(add_files_action)
        file_menu.addAction(add_folder_action)
        file_menu.addSeparator()
        file_menu.addAction(quit_action)

        run_menu = self.menuBar().addMenu("&Run")
        start_action = QAction("Start Conversion", self)
        start_action.setShortcut("Ctrl+R")
        cancel_action = QAction("Cancel", self)
        open_output_action = QAction("Open Output Folder", self)
        start_action.triggered.connect(self._start_conversion)
        cancel_action.triggered.connect(self._request_cancel)
        open_output_action.triggered.connect(self._open_output_directory)
        run_menu.addAction(start_action)
        run_menu.addAction(cancel_action)
        run_menu.addSeparator()
        run_menu.addAction(open_output_action)

        help_menu = self.menuBar().addMenu("&Help")
        about_action = QAction("About", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

        github_action = QAction("GitHub ↗", self)
        github_action.triggered.connect(lambda: QDesktopServices.openUrl(QUrl(GITHUB_URL)))
        self.menuBar().addAction(github_action)

        # Theme toggle in the menu bar — wrapped in a container for right-side breathing room.
        self.theme_button = QPushButton()
        self.theme_button.setObjectName("themeButton")
        self.theme_button.setFixedHeight(26)
        self.theme_button.clicked.connect(self._toggle_theme)

        self._theme_corner = QWidget()
        corner_layout = QHBoxLayout(self._theme_corner)
        corner_layout.setContentsMargins(0, 0, 10, 0)
        corner_layout.setSpacing(0)
        corner_layout.addWidget(self.theme_button)
        self.menuBar().setCornerWidget(self._theme_corner, Qt.Corner.TopRightCorner)

    def _toggle_theme(self) -> None:
        """Manually flip between light and dark."""
        self._is_dark = not self._is_dark
        self._apply_styles()

    def _on_system_theme_changed(self, scheme: object) -> None:
        """Follow OS-level light/dark changes automatically."""
        self._is_dark = scheme == Qt.ColorScheme.Dark
        self._apply_styles()

    def _apply_styles(self) -> None:
        """Apply the current theme stylesheet and update dynamic widget text."""
        t = _DARK if self._is_dark else _LIGHT

        # Show the mode you'll switch TO: "☀ Light" when dark, "☽ Dark" when light.
        self.theme_button.setText("☀  Light" if self._is_dark else "☽  Dark")
        self.theme_button.setToolTip("Switch to light mode" if self._is_dark else "Switch to dark mode")

        # Title rich text: version span colour changes with the theme.
        self.title_label.setText(
            f'{APP_TITLE} <span style="font-size:11px; color:{t["version_color"]}; font-weight:normal;">'
            f"v{__version__}</span>"
        )

        self.setStyleSheet(f"""
            QMainWindow {{
                background: {t["bg"]};
            }}
            QWidget {{
                font-size: 12px;
                color: {t["text"]};
            }}
            QScrollArea#mainScrollArea {{
                background: transparent;
                border: none;
            }}
            QWidget#contentRoot {{
                background: transparent;
            }}
            /* Hero banner */
            QFrame#hero {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 {t["hero_start"]}, stop:1 {t["hero_end"]});
                border: 1.5px solid {t["hero_border"]};
                border-radius: 16px;
            }}
            QLabel#heroTitle {{
                color: {t["title_color"]};
                background: transparent;
                border: none;
            }}
            QLabel#heroSubtitle {{
                color: {t["subtitle_color"]};
                background: transparent;
                border: none;
                font-size: 12px;
            }}
            /* Panel cards */
            QGroupBox {{
                background: {t["card_bg"]};
                border: 1.5px solid {t["card_border"]};
                border-radius: 14px;
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
                font-size: 11px;
                font-weight: 700;
            }}
            QFrame#logSurface {{
                background: {t["log_surface_bg"]};
                border: 1.5px solid {t["log_surface_border"]};
                border-radius: 12px;
            }}
            /* Summary label */
            QLabel#summaryLabel {{
                color: {t["text_muted"]};
                font-size: 11px;
                font-style: italic;
            }}
            /* Counter cards */
            QFrame#successCard {{
                background: {t["success_bg"]};
                border: 1.5px solid {t["success_border"]}; border-radius: 12px;
            }}
            QLabel#successCardTitle {{
                color: {t["success_label"]}; font-size: 10px; font-weight: 700;
                letter-spacing: 0.5px; background: transparent; border: none;
            }}
            QLabel#successCardValue {{ color: {t["success_value"]}; background: transparent; border: none; }}
            QFrame#warningCard {{
                background: {t["warning_bg"]};
                border: 1.5px solid {t["warning_border"]}; border-radius: 12px;
            }}
            QLabel#warningCardTitle {{
                color: {t["warning_label"]}; font-size: 10px; font-weight: 700;
                letter-spacing: 0.5px; background: transparent; border: none;
            }}
            QLabel#warningCardValue {{ color: {t["warning_value"]}; background: transparent; border: none; }}
            QFrame#errorCard {{
                background: {t["error_bg"]};
                border: 1.5px solid {t["error_border"]}; border-radius: 12px;
            }}
            QLabel#errorCardTitle {{
                color: {t["error_label"]}; font-size: 10px; font-weight: 700;
                letter-spacing: 0.5px; background: transparent; border: none;
            }}
            QLabel#errorCardValue {{ color: {t["error_value"]}; background: transparent; border: none; }}
            QFrame#neutralCard {{
                background: {t["neutral_bg"]};
                border: 1.5px solid {t["neutral_border"]}; border-radius: 12px;
            }}
            QLabel#neutralCardTitle {{
                color: {t["neutral_label"]}; font-size: 10px; font-weight: 700;
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
            QPushButton:disabled, QToolButton:disabled {{
                background: {t["btn_disabled_bg"]};
                color: {t["btn_disabled_color"]};
                border-color: {t["btn_disabled_border"]};
            }}
            /* Theme toggle — no border, blends into menu bar */
            QPushButton#themeButton {{
                background: transparent;
                border: none;
                border-radius: 6px;
                padding: 2px 4px;
                color: {t["text_muted"]};
            }}
            QPushButton#themeButton:hover {{
                background: {t["btn_hover_bg"]};
                color: {t["btn_hover_color"]};
                border: none;
            }}
            /* Primary action */
            QPushButton#startButton {{
                background: #2563eb;
                color: white;
                border: none;
                border-radius: 10px;
                padding: 10px 22px;
                font-weight: 700;
                font-size: 13px;
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
            QTextEdit {{
                background: {t["input_bg"]};
                border: 1.5px solid {t["input_border"]};
                border-radius: 10px;
                color: {t["input_color"]};
                padding: 8px;
                selection-background-color: {t["selection_bg"]};
            }}
            QTextEdit#logOutput {{
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
            /* Menu bar */
            QMenuBar {{
                background: {t["menubar_bg"]};
                color: {t["text"]};
                border-bottom: 1px solid {t["menubar_border"]};
                padding: 2px 4px;
            }}
            QMenuBar::item {{
                padding: 6px 12px;
                border-radius: 6px;
                background: transparent;
            }}
            QMenuBar::item:selected {{
                background: {t["menu_selected_bg"]};
                color: {t["menu_selected_color"]};
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
            /* SpinBox */
            QSpinBox {{
                background: {t["input_bg"]};
                color: {t["input_color"]};
                border: 1.5px solid {t["input_border"]};
                border-radius: 6px;
                padding: 3px 6px;
            }}
        """)

    def _make_counter_card(self, label: str, value_label: QLabel, variant: str = "neutral") -> QWidget:
        """Create one summary counter tile; colours are driven by the theme stylesheet."""
        container = QFrame()
        container.setObjectName(f"{variant}Card")
        container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(4)

        title = QLabel(label.upper())
        title.setObjectName(f"{variant}CardTitle")
        value_label.setObjectName(f"{variant}CardValue")
        layout.addWidget(title)
        layout.addWidget(value_label)
        return container

    def _make_counter_label(self) -> QLabel:
        """Create a large numeric label for a summary tile."""
        label = QLabel("0")
        font = QFont()
        font.setPointSize(20)
        font.setBold(True)
        label.setFont(font)
        return label

    def _sources(self) -> list[str]:
        """Return the queued input paths in their current order."""
        return [
            self.source_list.item(index).data(Qt.ItemDataRole.UserRole) for index in range(self.source_list.count())
        ]

    def _add_paths(self, paths_to_add: list[str]) -> None:
        """Normalize and append new source paths to the queue."""
        existing = set(self._sources())
        added = 0
        for raw_path in paths_to_add:
            normalized = path.abspath(raw_path)
            if normalized in existing:
                continue
            if not (path.isdir(normalized) or normalized.lower().endswith(".svg")):
                self._append_log(f"Ignored unsupported path: {normalized}", "skipped")
                continue
            item = QListWidgetItem(normalized)
            item.setData(Qt.ItemDataRole.UserRole, normalized)
            self.source_list.addItem(item)
            existing.add(normalized)
            added += 1

        if added:
            self._append_log(f"Queued {added} source path(s).", "info")
            self._set_idle_state("Ready to convert the current queue.")

    def _remove_selected_sources(self) -> None:
        """Remove selected queue entries from the source list."""
        selected_items = self.source_list.selectedItems()
        if not selected_items:
            return
        for item in selected_items:
            row = self.source_list.row(item)
            self.source_list.takeItem(row)
        self._append_log(f"Removed {len(selected_items)} queued path(s).", "info")

    def _choose_files(self) -> None:
        """Open a file picker for one or more SVG inputs."""
        file_paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Choose SVG files",
            "",
            "SVG files (*.svg)",
        )
        if file_paths:
            self._add_paths(file_paths)

    def _choose_folder(self) -> None:
        """Open a folder picker and add the selected directory to the queue."""
        directory = QFileDialog.getExistingDirectory(self, "Choose a folder")
        if directory:
            self._add_paths([directory])

    def _choose_output_dir(self) -> None:
        """Open a folder picker for the optional output directory."""
        directory = QFileDialog.getExistingDirectory(self, "Choose an output folder")
        if directory:
            self.output_dir_edit.setText(directory)

    def _start_conversion(self) -> None:
        """Launch the worker thread for the current queue."""
        source_paths = self._sources()
        if not source_paths:
            QMessageBox.information(self, "No sources", "Add at least one SVG file or folder first.")
            return

        output_dir = self.output_dir_edit.text().strip() or None
        options = ConversionOptions(
            output_dir=path.abspath(output_dir) if output_dir else None,
            recursive=self.recursive_checkbox.isChecked(),
            overwrite=self.overwrite_checkbox.isChecked(),
            flatten=self.flatten_checkbox.isChecked(),
            max_elements=self.max_elements_spinbox.value() if self.max_elements_checkbox.isChecked() else None,
        )

        self._reset_run_state()
        self._set_running_state("Preparing conversion queue...")
        self._append_log(f"Starting batch with {len(source_paths)} source path(s).", "info")

        self._thread = QThread(self)
        self._worker = ConversionWorker(source_paths, options)
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.event_emitted.connect(self._handle_event)
        self._worker.finished.connect(self._handle_finished)
        self._worker.failed.connect(self._handle_failure)
        self._worker.finished.connect(self._thread.quit)
        self._worker.failed.connect(self._thread.quit)
        self._thread.finished.connect(self._cleanup_worker)

        self._thread.start()

    def _request_cancel(self) -> None:
        """Request cooperative cancellation of the active worker."""
        if self._worker is None:
            return
        self._worker.request_cancel()
        self.cancel_button.setEnabled(False)
        self.status_label.setText("Cancellation requested. The current file will finish first.")
        self._append_log("Cancellation requested by the user.", "warning")

    def _handle_event(self, event: ConversionEvent) -> None:
        """Update the UI in response to one service progress event."""
        if event.total:
            self.progress_bar.setMaximum(event.total)
        else:
            self.progress_bar.setMaximum(1)
        self.progress_bar.setValue(event.completed)

        if event.kind == ConversionEventKind.STARTED:
            self.status_label.setText(event.message)
            self._append_log(event.message, "info")
            return

        if event.kind == ConversionEventKind.CONVERTED:
            self._converted += 1
            if event.output_path:
                self._last_openable_directory = path.dirname(event.output_path)
                self.open_output_button.setEnabled(True)
            self._append_log(event.message, "converted")
        elif event.kind == ConversionEventKind.SKIPPED:
            self._skipped += 1
            if event.output_path:
                self._last_openable_directory = path.dirname(event.output_path)
                self.open_output_button.setEnabled(True)
            self._append_log(event.message, "skipped")
        elif event.kind == ConversionEventKind.FAILED:
            self._failed += 1
            self._append_log(event.message, "failed")
        elif event.kind == ConversionEventKind.CANCELLED:
            self._append_log(event.message, "warning")
        elif event.kind == ConversionEventKind.DISCOVERED:
            self._append_log(event.message, "info")

        self._update_summary_labels()
        if event.summary is None:
            self.status_label.setText(event.message)

    def _handle_finished(self, summary: ConversionSummary) -> None:
        """Finalize the UI after a successful worker shutdown."""
        self._converted = summary.converted
        self._skipped = summary.skipped
        self._failed = summary.failed
        self._update_summary_labels()
        self.summary_label.setText(summary.to_status_line())
        self.progress_bar.setMaximum(summary.total or 1)
        self.progress_bar.setValue(summary.converted + summary.skipped + summary.failed)
        if summary.cancelled:
            self.status_label.setText("Batch cancelled after the current file completed.")
            self._append_log(summary.to_status_line(), "warning")
        elif summary.failed:
            self.status_label.setText("Batch finished with at least one failure.")
            self._append_log(summary.to_status_line(), "failed")
        elif summary.total == 0:
            self.status_label.setText("No SVG files were found in the queued sources.")
        else:
            self.status_label.setText("Batch completed successfully.")
            self._append_log(summary.to_status_line(), "converted")
        self._set_controls_enabled(True)

    def _handle_failure(self, error_message: str) -> None:
        """Show unrecoverable worker errors."""
        self._append_log(f"Batch aborted: {error_message}", "failed")
        self.status_label.setText("Batch aborted before conversion could complete.")
        self.summary_label.setText(error_message)
        self._set_controls_enabled(True)
        QMessageBox.critical(self, "Conversion failed", error_message)

    def _cleanup_worker(self) -> None:
        """Release thread-owned worker objects after the run ends."""
        if self._worker is not None:
            self._worker.deleteLater()
        if self._thread is not None:
            self._thread.deleteLater()
        self._worker = None
        self._thread = None
        self.cancel_button.setEnabled(False)
        if self._close_after_run:
            self._close_after_run = False
            self.close()

    def _reset_run_state(self) -> None:
        """Clear counters and progress before starting a new batch."""
        self._converted = 0
        self._skipped = 0
        self._failed = 0
        self._last_openable_directory = None
        self.open_output_button.setEnabled(False)
        self.progress_bar.setValue(0)
        self.summary_label.clear()
        self._update_summary_labels()

    def _set_running_state(self, status_text: str) -> None:
        """Switch the window into its busy state."""
        self.status_label.setText(status_text)
        self._set_controls_enabled(False)
        self.cancel_button.setEnabled(True)

    def _set_idle_state(self, status_text: str) -> None:
        """Switch the window into its idle state."""
        self.status_label.setText(status_text)
        self._set_controls_enabled(True)
        self.cancel_button.setEnabled(False)

    def _set_controls_enabled(self, enabled: bool) -> None:
        """Enable or disable controls that should not change mid-run."""
        for widget in (
            self.add_files_button,
            self.add_folder_button,
            self.remove_selected_button,
            self.clear_sources_button,
            self.source_list,
            self.output_dir_edit,
            self.recursive_checkbox,
            self.overwrite_checkbox,
            self.start_button,
        ):
            widget.setEnabled(enabled)

    def _update_summary_labels(self) -> None:
        """Refresh the counter tiles from the current totals."""
        self.converted_value.setText(str(self._converted))
        self.skipped_value.setText(str(self._skipped))
        self.failed_value.setText(str(self._failed))
        self.summary_label.setText(
            f"Converted: {self._converted}   |   Skipped: {self._skipped}   |   Failed: {self._failed}"
        )

    def _append_log(self, message: str, tone: str) -> None:
        """Append a timestamped, styled log line to the output panel."""
        t = _DARK if self._is_dark else _LIGHT
        color = {
            "converted": t["log_converted"],
            "failed": t["log_failed"],
            "warning": t["log_warning"],
            "skipped": t["log_skipped"],
            "info": t["log_info"],
        }.get(tone, t["log_default"])
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_output.append(
            f'<span style="color: {t["log_ts"]};">[{ts}]</span>'
            f' <span style="color: {color};">{html.escape(message)}</span>'
        )

    def _open_output_directory(self) -> None:
        """Open the most recently written output directory in the OS file manager."""
        if not self._last_openable_directory:
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(self._last_openable_directory))

    def _show_about(self) -> None:
        """Display the About dialog with the application version."""
        QMessageBox.about(
            self,
            f"About {APP_TITLE}",
            f"<b>{APP_TITLE}</b><br>Version {__version__}<br><br>Convert SVG files into editable draw.io diagrams.",
        )


def create_application() -> QApplication:
    """Create and configure the desktop QApplication instance."""
    app = QApplication.instance()
    if isinstance(app, QApplication):
        return cast(QApplication, app)

    created = QApplication(sys.argv)
    created.setApplicationName(APP_TITLE)
    created.setOrganizationName("svg-to-drawio")
    created.setDesktopFileName("io.github.v1rg1lee.svg-to-drawio")
    created.setWindowIcon(_load_app_icon())
    created.setStyle("Fusion")
    return created


def main() -> int:
    """Launch the desktop application."""
    app = create_application()
    window = MainWindow()
    window.show()
    return int(app.exec())
