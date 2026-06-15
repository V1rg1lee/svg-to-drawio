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
    QIcon,
    QPainter,
    QPainterPath,
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

_CARD_VARIANTS: dict[str, dict[str, str]] = {
    "success": {"bg": "#f0fdf4", "border": "#86efac", "label_color": "#15803d", "value_color": "#166534"},
    "warning": {"bg": "#fffbeb", "border": "#fde68a", "label_color": "#92400e", "value_color": "#78350f"},
    "error": {"bg": "#fff1f2", "border": "#fecdd3", "label_color": "#be123c", "value_color": "#9f1239"},
    "neutral": {"bg": "#f8fafc", "border": "#e2e8f0", "label_color": "#475569", "value_color": "#334155"},
}


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
    """Load the window/taskbar icon.

    Windows: ICO (multi-resolution, native format).
    Linux:   ICO decoded by Qt, then PNG fallback.
    Both fall back to a procedurally drawn icon if no asset is found.
    """
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
    """Load the logo displayed in the hero area.

    Prefers the PNG (already the right format for on-screen display),
    then falls back to ICO decoded by Qt, then the procedural icon.
    """
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

        self.setWindowTitle(APP_TITLE)
        self.setWindowIcon(_load_app_icon())
        self.resize(1180, 780)
        self.setMinimumSize(960, 640)
        self._build_ui()
        self._install_actions()
        self._apply_styles()
        self._update_summary_labels()
        self._set_idle_state("Drop SVG files or folders to get started.")

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
        central = QWidget()
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

        title = QLabel(
            f'{APP_TITLE} <span style="font-size:11px; color:#94a3b8; font-weight:normal;">v{__version__}</span>'
        )
        title.setTextFormat(Qt.TextFormat.RichText)
        title_font = QFont()
        title_font.setPointSize(20)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setStyleSheet("color: #1e3a8a; background: transparent; border: none;")

        subtitle = QLabel(
            "Convert SVG files to draw.io diagrams - individually or in batch. "
            "Drop files, pick options, then hit “Start Conversion”."
        )
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("color: #3b82f6; background: transparent; border: none; font-size: 12px;")

        text_layout.addWidget(title)
        text_layout.addWidget(subtitle)
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

        self.setCentralWidget(central)

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

        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setMinimumHeight(220)
        self.log_output.setPlaceholderText("Conversion events will appear here…")
        mono_font = QFont("Consolas")
        mono_font.setStyleHint(QFont.StyleHint.Monospace)
        mono_font.setPointSize(9)
        self.log_output.setFont(mono_font)
        layout.addWidget(self.log_output)
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
        self.summary_label.setWordWrap(True)
        self.summary_label.setStyleSheet("color: #64748b; font-size: 11px; font-style: italic;")
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
        """Populate the menu bar with common actions."""
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

    def _apply_styles(self) -> None:
        """Apply a modern, polished application stylesheet."""
        self.setStyleSheet(
            """
            QMainWindow {
                background: #f1f5f9;
            }
            QWidget {
                font-size: 12px;
            }
            /* Hero banner */
            QFrame#hero {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #eff6ff, stop:1 #e0f2fe);
                border: 1.5px solid #bae6fd;
                border-radius: 16px;
            }
            /* Panel cards - only padding-top is set here so Qt reserves
               space for the inside title; left/right/bottom are handled
               exclusively by setContentsMargins on each group's layout. */
            QGroupBox {
                background: white;
                border: 1.5px solid #e2e8f0;
                border-radius: 14px;
                margin-top: 0;
                padding-top: 40px;
            }
            QGroupBox::title {
                subcontrol-origin: padding;
                subcontrol-position: top left;
                left: 16px;
                top: 12px;
                padding: 0;
                background: transparent;
                border: none;
                color: #64748b;
                font-size: 11px;
                font-weight: 700;
            }
            /* Default / secondary buttons */
            QPushButton, QToolButton {
                background: #f8fafc;
                color: #374151;
                border: 1.5px solid #d1d5db;
                border-radius: 8px;
                padding: 7px 14px;
                font-weight: 500;
            }
            QPushButton:hover:!disabled, QToolButton:hover:!disabled {
                background: #f0f9ff;
                border-color: #93c5fd;
                color: #1d4ed8;
            }
            QPushButton:pressed, QToolButton:pressed {
                background: #dbeafe;
            }
            QPushButton:disabled, QToolButton:disabled {
                background: #f8fafc;
                color: #9ca3af;
                border-color: #e5e7eb;
            }
            /* Primary action */
            QPushButton#startButton {
                background: #2563eb;
                color: white;
                border: none;
                border-radius: 10px;
                padding: 10px 22px;
                font-weight: 700;
                font-size: 13px;
            }
            QPushButton#startButton:hover:!disabled {
                background: #1d4ed8;
                color: white;
            }
            QPushButton#startButton:disabled {
                background: #93c5fd;
                color: #dbeafe;
                border: none;
            }
            /* Destructive action */
            QPushButton#cancelButton {
                background: #fff1f2;
                color: #e11d48;
                border: 1.5px solid #fecdd3;
            }
            QPushButton#cancelButton:hover:!disabled {
                background: #ffe4e6;
                border-color: #fda4af;
                color: #be123c;
            }
            QPushButton#cancelButton:disabled {
                background: #f8fafc;
                color: #9ca3af;
                border-color: #e5e7eb;
            }
            /* Success action */
            QPushButton#openOutputButton:enabled {
                background: #f0fdf4;
                color: #15803d;
                border: 1.5px solid #bbf7d0;
            }
            QPushButton#openOutputButton:hover:!disabled {
                background: #dcfce7;
                border-color: #86efac;
                color: #166534;
            }
            QPushButton#openOutputButton:disabled {
                background: #f8fafc;
                color: #9ca3af;
                border-color: #e5e7eb;
            }
            /* Inputs */
            QListWidget, QLineEdit {
                background: white;
                border: 1.5px solid #e2e8f0;
                border-radius: 10px;
                color: #1e293b;
                padding: 6px;
                selection-background-color: #dbeafe;
                selection-color: #1e40af;
            }
            QListWidget:focus, QLineEdit:focus {
                border-color: #3b82f6;
            }
            QListWidget::item {
                padding: 7px 10px;
                border-radius: 6px;
                color: #334155;
            }
            QListWidget::item:selected {
                background: #eff6ff;
                color: #1e40af;
            }
            QListWidget::item:hover:!selected {
                background: #f8fafc;
            }
            QTextEdit {
                background: white;
                border: 1.5px solid #e2e8f0;
                border-radius: 10px;
                color: #1e293b;
                padding: 8px;
                selection-background-color: #dbeafe;
            }
            /* Progress bar */
            QProgressBar {
                border: none;
                border-radius: 7px;
                background: #e2e8f0;
                min-height: 12px;
                max-height: 12px;
            }
            QProgressBar::chunk {
                border-radius: 7px;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #3b82f6, stop:1 #8b5cf6);
            }
            /* Checkboxes */
            QCheckBox {
                spacing: 8px;
                color: #374151;
            }
            QCheckBox::indicator {
                width: 17px;
                height: 17px;
                border: 2px solid #d1d5db;
                border-radius: 5px;
                background: white;
            }
            QCheckBox::indicator:checked {
                background: #2563eb;
                border-color: #2563eb;
            }
            QCheckBox::indicator:hover {
                border-color: #3b82f6;
            }
            QLabel {
                color: #374151;
                background: transparent;
            }
            /* Menu bar */
            QMenuBar {
                background: white;
                color: #374151;
                border-bottom: 1px solid #e2e8f0;
                padding: 2px 4px;
            }
            QMenuBar::item {
                padding: 6px 12px;
                border-radius: 6px;
            }
            QMenuBar::item:selected {
                background: #eff6ff;
                color: #1d4ed8;
            }
            QMenu {
                background: white;
                border: 1px solid #e2e8f0;
                border-radius: 10px;
                padding: 4px;
            }
            QMenu::item {
                padding: 8px 20px;
                color: #374151;
                border-radius: 6px;
            }
            QMenu::item:selected {
                background: #eff6ff;
                color: #1d4ed8;
            }
            /* Source list add buttons */
            QPushButton#addFilesButton, QPushButton#addFolderButton {
                background: #eff6ff;
                color: #1d4ed8;
                border: 1.5px solid #bfdbfe;
                font-weight: 600;
            }
            QPushButton#addFilesButton:hover:!disabled, QPushButton#addFolderButton:hover:!disabled {
                background: #dbeafe;
                border-color: #93c5fd;
                color: #1e40af;
            }
            /* Source list remove buttons */
            QPushButton#removeSelectedButton {
                background: #f8fafc;
                color: #64748b;
                border: 1.5px solid #e2e8f0;
            }
            QPushButton#removeSelectedButton:hover:!disabled {
                background: #f1f5f9;
                color: #475569;
                border-color: #cbd5e1;
            }
            QPushButton#clearQueueButton {
                background: #fff7ed;
                color: #c2410c;
                border: 1.5px solid #fed7aa;
            }
            QPushButton#clearQueueButton:hover:!disabled {
                background: #ffedd5;
                border-color: #fb923c;
                color: #9a3412;
            }
            /* Thin, modern scrollbars */
            QScrollBar:vertical {
                background: transparent;
                width: 8px;
            }
            QScrollBar::handle:vertical {
                background: #cbd5e1;
                border-radius: 4px;
                min-height: 24px;
            }
            QScrollBar::handle:vertical:hover {
                background: #94a3b8;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }
            QScrollBar:horizontal {
                background: transparent;
                height: 8px;
            }
            QScrollBar::handle:horizontal {
                background: #cbd5e1;
                border-radius: 4px;
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: none; }
            """
        )

    def _make_counter_card(self, label: str, value_label: QLabel, variant: str = "neutral") -> QWidget:
        """Create one summary counter tile with variant colour coding."""
        colors = _CARD_VARIANTS.get(variant, _CARD_VARIANTS["neutral"])
        container = QFrame()
        container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        container.setStyleSheet(
            f"QFrame {{ background: {colors['bg']}; border: 1.5px solid {colors['border']}; border-radius: 12px; }}"
        )
        layout = QVBoxLayout(container)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(4)

        title = QLabel(label.upper())
        title.setStyleSheet(
            f"color: {colors['label_color']}; font-size: 10px; font-weight: 700;"
            " background: transparent; border: none; letter-spacing: 0.5px;"
        )
        value_label.setStyleSheet(f"color: {colors['value_color']}; background: transparent; border: none;")
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
        color = {
            "converted": "#15803d",
            "failed": "#dc2626",
            "warning": "#d97706",
            "skipped": "#6b7280",
            "info": "#2563eb",
        }.get(tone, "#374151")
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_output.append(
            f'<span style="color: #94a3b8;">[{ts}]</span> <span style="color: {color};">{html.escape(message)}</span>'
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
    created.setWindowIcon(_load_app_icon())
    created.setStyle("Fusion")
    return created


def main() -> int:
    """Launch the desktop application."""
    app = create_application()
    window = MainWindow()
    window.show()
    return int(app.exec())
