"""PySide6 desktop application for the SVG-to-draw.io converter."""

from __future__ import annotations

import ctypes
import html
import json
import os
import sys
import traceback
from datetime import datetime
from os import path
from typing import Any, cast

from PySide6.QtCore import QSettings, QSignalBlocker, Qt, QThread, QUrl, qInstallMessageHandler
from PySide6.QtGui import QAction, QCloseEvent, QDesktopServices, QGuiApplication
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QFrame,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)
from svg_to_drawio import REPORT_SCHEMA_VERSION, RenderingOptions, __version__
from svg_to_drawio.capabilities import rendering_preflight_lines
from svg_to_drawio.compatibility import (
    CompatibilityRow,
    build_compatibility_overview,
    build_compatibility_rows,
)
from svg_to_drawio.conversion_service import (
    ConversionEvent,
    ConversionEventKind,
    ConversionOptions,
    ConversionSummary,
)
from svg_to_drawio.diagnostics import ConversionReport, PreviewAnnotation
from svg_to_drawio.rendering_options import (
    as_filter_policy,
    as_gradient_policy,
    as_text_metrics_policy,
    detect_rendering_preset,
    rendering_preset_label,
    rendering_preset_options,
)

from .app_settings import parse_bool_setting, parse_int_setting
from .cli_command import CliCommandOptions, build_equivalent_cli_command
from .compatibility_view import build_feature_dialog_text, render_compatibility_html
from .pages import ConvertPage, PreviewPage, ResultsPage, SettingsPage
from .theme import DARK, LIGHT, build_stylesheet, detect_system_dark, load_app_icon, load_brand_pixmap
from .widgets import NavBar
from .worker import ConversionWorker, ParallelConversionWorker, WatchConversionWorker

APP_TITLE = "SVG to draw.io"
GITHUB_URL = "https://github.com/V1rg1lee/svg-to-drawio"
DRAWIO_URL = "https://app.diagrams.net"

PAGE_CONVERT = 0
PAGE_RESULTS = 1
PAGE_PREVIEW = 2
PAGE_SETTINGS = 3

_QT_MESSAGE_FILTER_INSTALLED = False
_PREVIOUS_QT_MESSAGE_HANDLER: Any = None

_CRASH_LOG_DIR = path.join(path.expanduser("~"), ".svg-to-drawio")
_CRASH_LOG_PATH = path.join(_CRASH_LOG_DIR, "crash.log")


def _install_crash_handler() -> None:
    """Log uncaught exceptions to a file and show a dialog instead of vanishing silently.

    The packaged (PyInstaller) build has no console, so without this an unhandled
    exception just kills the process with zero trace for the user to report.
    """

    def _handle_exception(exc_type: type[BaseException], exc_value: BaseException, exc_tb: Any) -> None:
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return

        details = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        try:
            os.makedirs(_CRASH_LOG_DIR, exist_ok=True)
            with open(_CRASH_LOG_PATH, "a", encoding="utf-8") as handle:
                handle.write(f"\n--- {datetime.now().isoformat()} (v{__version__}) ---\n{details}")
        except OSError:
            pass

        app = QApplication.instance()
        if isinstance(app, QApplication):
            try:
                QMessageBox.critical(
                    None,
                    APP_TITLE,
                    "Something went wrong and the application needs to close.\n\n"
                    f"Details were written to:\n{_CRASH_LOG_PATH}",
                )
            except Exception:
                pass

        sys.__excepthook__(exc_type, exc_value, exc_tb)

    sys.excepthook = _handle_exception


def _install_qt_message_filter() -> None:
    """Suppress known benign Qt preview warnings that only spam the desktop console."""
    global _QT_MESSAGE_FILTER_INSTALLED, _PREVIOUS_QT_MESSAGE_HANDLER
    if _QT_MESSAGE_FILTER_INSTALLED:
        return

    def _handler(message_type: object, context: object, message: str) -> None:
        stripped = message.strip()
        if stripped.startswith("qt.svg: Could not create image from "):
            return
        if stripped.startswith("QFont::setPointSizeF: Point size <= 0"):
            return
        if _PREVIOUS_QT_MESSAGE_HANDLER is not None:
            _PREVIOUS_QT_MESSAGE_HANDLER(message_type, context, message)

    _PREVIOUS_QT_MESSAGE_HANDLER = qInstallMessageHandler(_handler)
    _QT_MESSAGE_FILTER_INSTALLED = True


def _fmt_size(n: int) -> str:
    """Format a byte count as a human-readable string (B / KB / MB / GB)."""
    size = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024.0:
            return f"{int(size)} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} PB"


class MainWindow(QMainWindow):
    """Desktop front-end for batch SVG-to-draw.io conversions."""

    def __init__(self) -> None:
        super().__init__()
        self._thread: QThread | None = None
        self._worker: ConversionWorker | ParallelConversionWorker | WatchConversionWorker | None = None
        self._converted = 0
        self._skipped = 0
        self._failed = 0
        self._close_after_run = False
        self._last_openable_directory: str | None = None
        self._last_reports: list[ConversionReport] = []
        self._active_preview_report: ConversionReport | None = None
        self._preview_selected_report_index: int | None = None
        self._warning_count = 0
        self._watch_mode_active = False
        self._tray: QSystemTrayIcon | None = None
        self._last_compatibility_rows: list[CompatibilityRow] = []
        self._settings = QSettings()
        self._is_dark = detect_system_dark()

        self.setWindowTitle(APP_TITLE)
        self.setWindowIcon(load_app_icon())
        self.resize(1180, 780)
        self.setMinimumSize(960, 640)
        self._build_ui()
        self._restore_settings()
        self._install_shortcuts_and_menu()
        self._apply_styles()
        self._update_summary_labels()
        self._update_compatibility_panel()
        self._update_preview_panel()
        self._set_idle_state("Drop SVG files or folders to get started.")
        self._setup_tray()

        try:
            QGuiApplication.styleHints().colorSchemeChanged.connect(self._on_system_theme_changed)
        except AttributeError:
            pass  # Qt < 6.5

    # ------------------------------------------------------------------ UI

    def _build_ui(self) -> None:
        """Create the header bar, page stack, and wire page-local actions."""
        central = QWidget()
        central.setObjectName("contentRoot")
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self.nav_bar = NavBar(["Convert", "Results", "Preview", "Settings"])
        self.nav_bar.page_changed.connect(self._goto_page)
        self.nav_bar.overflow_button.setMenu(self._build_overflow_menu())
        self.nav_bar.theme_button.clicked.connect(self._toggle_theme)
        root_layout.addWidget(self.nav_bar)

        self.convert_page = ConvertPage()
        self.results_page = ResultsPage()
        self.preview_page = PreviewPage()
        self.settings_page = SettingsPage()

        self.stack = QStackedWidget()
        self.stack.addWidget(self.convert_page)
        self.stack.addWidget(self.results_page)
        self.stack.addWidget(self.preview_page)
        self.stack.addWidget(self.settings_page)

        scroll_area = QScrollArea()
        scroll_area.setObjectName("mainScrollArea")
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setWidget(self.stack)
        self.stack.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.MinimumExpanding)
        root_layout.addWidget(scroll_area, stretch=1)

        self.setCentralWidget(central)

        self.convert_page.add_files_button.clicked.connect(self._choose_files)
        self.convert_page.add_folder_button.clicked.connect(self._choose_folder)
        self.convert_page.source_list.paths_dropped.connect(self._add_paths)
        self.convert_page.browse_output_button.clicked.connect(self._choose_output_dir)
        self.convert_page.start_button.clicked.connect(self._start_conversion)
        self.convert_page.copy_cli_button.clicked.connect(self._copy_equivalent_cli_command)
        self.convert_page.watch_checkbox.toggled.connect(self._sync_runtime_option_state)

        self.results_page.cancel_button.clicked.connect(self._request_cancel)
        self.results_page.open_output_button.clicked.connect(self._open_output_directory)
        self.results_page.export_report_button.clicked.connect(self._export_last_report)
        self.results_page.log_output.anchorClicked.connect(self._on_log_link_clicked)
        self.results_page.compatibility_output.anchorClicked.connect(self._on_compatibility_link_clicked)
        self.preview_page.annotation_clicked.connect(self._on_preview_annotation_clicked)
        self.preview_page.preview_report_selected.connect(self._on_preview_report_selected)

        self.settings_page.preset_combo.currentIndexChanged.connect(self._apply_selected_rendering_preset)
        self.settings_page.gradient_combo.currentIndexChanged.connect(self._mark_rendering_preset_custom)
        self.settings_page.filter_combo.currentIndexChanged.connect(self._mark_rendering_preset_custom)
        self.settings_page.text_metrics_combo.currentIndexChanged.connect(self._mark_rendering_preset_custom)
        self._sync_runtime_option_state()

    def _build_overflow_menu(self) -> QMenu:
        """Build the compact menu replacing the classic File/Run/Help menu bar."""
        menu = QMenu(self)
        add_files_action = QAction("Add SVG Files...", self)
        add_folder_action = QAction("Add Folder...", self)
        add_files_action.triggered.connect(self._choose_files)
        add_folder_action.triggered.connect(self._choose_folder)
        menu.addAction(add_files_action)
        menu.addAction(add_folder_action)
        menu.addSeparator()

        about_action = QAction("About", self)
        about_action.triggered.connect(self._show_about)
        menu.addAction(about_action)

        github_action = QAction("GitHub ↗", self)
        github_action.triggered.connect(lambda: QDesktopServices.openUrl(QUrl(GITHUB_URL)))
        menu.addAction(github_action)

        drawio_action = QAction("draw.io ↗", self)
        drawio_action.triggered.connect(lambda: QDesktopServices.openUrl(QUrl(DRAWIO_URL)))
        menu.addAction(drawio_action)
        menu.addSeparator()

        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self.close)
        menu.addAction(quit_action)
        return menu

    def _install_shortcuts_and_menu(self) -> None:
        """Install window-wide keyboard shortcuts that stay active regardless of the visible page."""
        start_action = QAction(self)
        start_action.setShortcut("Ctrl+R")
        start_action.triggered.connect(self._start_conversion)
        self.addAction(start_action)

        cancel_action = QAction(self)
        cancel_action.setShortcut("Esc")
        cancel_action.triggered.connect(self._cancel_via_shortcut)
        self.addAction(cancel_action)

    def _cancel_via_shortcut(self) -> None:
        """Cancel the active run when Escape is pressed, if a conversion is in progress."""
        if self._worker is not None and self.results_page.cancel_button.isEnabled():
            self._request_cancel()

    def _goto_page(self, index: int) -> None:
        """Switch the visible page and keep the nav bar in sync."""
        self.stack.setCurrentIndex(index)
        self.nav_bar.set_current_page(index)

    # ----------------------------------------------------------- lifecycle

    def closeEvent(self, event: QCloseEvent) -> None:
        """Warn before closing while a conversion is still in progress."""
        if self._worker is None:
            self._save_settings()
            super().closeEvent(event)
            return

        answer = self._show_running_close_dialog()
        if answer == "finish":
            self._schedule_close_after_run()
            event.ignore()
            return
        if answer == "force":
            event.accept()
            self._force_close_application()
            return
        event.ignore()

    def _show_running_close_dialog(self) -> str:
        """Ask how the window should close while background work is still active."""
        dialog = QMessageBox(self)
        dialog.setIcon(QMessageBox.Icon.Warning)
        dialog.setWindowTitle("Conversion in progress")
        dialog.setText(
            "A conversion is still running. Finish safely and close later, or force the application to close right now."
        )
        finish_label = "Stop and Close" if self._watch_mode_active else "Finish and Close"
        finish_button = dialog.addButton(finish_label, QMessageBox.ButtonRole.AcceptRole)
        force_button = dialog.addButton("Close Anyway", QMessageBox.ButtonRole.DestructiveRole)
        cancel_button = dialog.addButton(QMessageBox.StandardButton.Cancel)
        dialog.setDefaultButton(cancel_button)
        dialog.exec()
        clicked = dialog.clickedButton()
        if clicked is finish_button:
            return "finish"
        if clicked is force_button:
            return "force"
        return "cancel"

    def _schedule_close_after_run(self) -> None:
        """Close the window automatically once the active work reaches a safe stop."""
        if self._close_after_run:
            return
        self._close_after_run = True
        if self._watch_mode_active:
            self._request_cancel()
            self.results_page.status_label.setText("Stopping watch mode. The window will close after the worker stops.")
            self._append_log("Window close requested. Watch mode will stop and then close the application.", "warning")
            return
        self.results_page.status_label.setText("The window will close automatically after the current batch finishes.")
        self._append_log(
            "Window close requested. The application will close after the current batch finishes.",
            "warning",
        )

    def _force_close_application(self) -> None:
        """Force the process to exit as a last-resort escape hatch.

        Cancellation is cooperative, so the worker thread gets a brief bounded window to
        finish writing its current output file before the hard exit below. Without this,
        `os._exit` can kill the process mid-write and leave a truncated `.drawio` file.
        """
        self._close_after_run = False
        try:
            self._save_settings()
        except Exception:
            pass
        if self._worker is not None:
            try:
                self._worker.request_cancel()
            except Exception:
                pass
        if self._thread is not None:
            self._thread.wait(2000)
        app = QApplication.instance()
        if isinstance(app, QApplication):
            app.quit()
        os._exit(0)

    # ------------------------------------------------------------ settings

    def _restore_settings(self) -> None:
        """Restore persisted UI preferences from the previous desktop session."""
        geometry = self._settings.value("window/geometry")
        if geometry:
            self.restoreGeometry(geometry)

        theme_value = self._settings.value("ui/dark")
        if theme_value is not None:
            self._is_dark = str(theme_value).lower() in {"1", "true", "yes"}

        cp = self.convert_page
        output_dir = self._settings.value("options/output_dir", "")
        cp.output_dir_edit.setText(str(output_dir or ""))
        cp.recursive_checkbox.setChecked(self._setting_bool("options/recursive"))
        cp.overwrite_checkbox.setChecked(self._setting_bool("options/overwrite"))
        cp.flatten_checkbox.setChecked(self._setting_bool("options/flatten"))
        cp.watch_checkbox.setChecked(self._setting_bool("options/watch"))
        cp.cache_checkbox.setChecked(self._setting_bool("options/use_cache", default=True))
        cp.workers_spinbox.setValue(self._setting_int("options/workers", default=1))
        cp.max_elements_checkbox.setChecked(self._setting_bool("options/max_enabled"))
        cp.max_elements_spinbox.setValue(self._setting_int("options/max_value", default=1000))

        sp = self.settings_page
        preset_value = str(self._settings.value("rendering/preset", "balanced"))
        if preset_value != "custom":
            try:
                self._apply_rendering_preset(preset_value, persist=False)
            except ValueError:
                # A persisted preset from an older/incompatible version of the app
                # is no longer recognized - fall back to the default instead of
                # crashing on startup.
                self._apply_rendering_preset("balanced", persist=False)
        else:
            self._set_combo_value(sp.gradient_combo, str(self._settings.value("rendering/gradient_policy", "auto")))
            self._set_combo_value(sp.filter_combo, str(self._settings.value("rendering/filter_policy", "auto")))
            self._set_combo_value(
                sp.text_metrics_combo, str(self._settings.value("rendering/text_metrics_policy", "auto"))
            )
            self._set_combo_value(sp.preset_combo, "custom")
        self._sync_rendering_preset_label()
        self._sync_runtime_option_state()
        self._update_preflight_summary()

    def _save_settings(self) -> None:
        """Persist the current UI preferences for the next application launch."""
        cp = self.convert_page
        sp = self.settings_page
        self._settings.setValue("window/geometry", self.saveGeometry())
        self._settings.setValue("ui/dark", self._is_dark)
        self._settings.setValue("options/output_dir", cp.output_dir_edit.text().strip())
        self._settings.setValue("options/recursive", cp.recursive_checkbox.isChecked())
        self._settings.setValue("options/overwrite", cp.overwrite_checkbox.isChecked())
        self._settings.setValue("options/flatten", cp.flatten_checkbox.isChecked())
        self._settings.setValue("options/watch", cp.watch_checkbox.isChecked())
        self._settings.setValue("options/use_cache", cp.cache_checkbox.isChecked())
        self._settings.setValue("options/workers", cp.workers_spinbox.value())
        self._settings.setValue("options/max_enabled", cp.max_elements_checkbox.isChecked())
        self._settings.setValue("options/max_value", cp.max_elements_spinbox.value())
        self._settings.setValue("rendering/preset", sp.preset_combo.currentData())
        self._settings.setValue("rendering/gradient_policy", sp.gradient_combo.currentData())
        self._settings.setValue("rendering/filter_policy", sp.filter_combo.currentData())
        self._settings.setValue("rendering/text_metrics_policy", sp.text_metrics_combo.currentData())
        self._settings.sync()

    def _setting_bool(self, key: str, *, default: bool = False) -> bool:
        """Read one persisted boolean setting with tolerant string parsing."""
        return parse_bool_setting(self._settings.value(key, default))

    def _setting_int(self, key: str, *, default: int) -> int:
        """Read one persisted integer setting with a safe fallback."""
        return parse_int_setting(self._settings.value(key, default), default=default)

    @staticmethod
    def _set_combo_value(combo: QComboBox, value: str) -> None:
        """Select the combo-box row matching the persisted option value."""
        index = combo.findData(value)
        combo.setCurrentIndex(index if index >= 0 else 0)

    def _current_rendering_options(self) -> RenderingOptions:
        """Read the rendering policies currently selected in the settings page."""
        sp = self.settings_page
        return RenderingOptions(
            gradient_policy=as_gradient_policy(str(sp.gradient_combo.currentData())),
            filter_policy=as_filter_policy(str(sp.filter_combo.currentData())),
            text_metrics_policy=as_text_metrics_policy(str(sp.text_metrics_combo.currentData())),
        )

    def _apply_selected_rendering_preset(self, *_: object) -> None:
        """Apply the preset currently selected by the user."""
        preset = str(self.settings_page.preset_combo.currentData())
        if preset == "custom":
            self._update_preflight_summary()
            return
        self._apply_rendering_preset(preset, persist=False)

    def _apply_rendering_preset(self, preset: str, *, persist: bool) -> None:
        """Apply one named preset to the rendering-policy combo boxes."""
        options = rendering_preset_options(preset)
        blockers = [
            QSignalBlocker(self.settings_page.preset_combo),
            QSignalBlocker(self.settings_page.gradient_combo),
            QSignalBlocker(self.settings_page.filter_combo),
            QSignalBlocker(self.settings_page.text_metrics_combo),
        ]
        self._set_combo_value(self.settings_page.gradient_combo, options.gradient_policy)
        self._set_combo_value(self.settings_page.filter_combo, options.filter_policy)
        self._set_combo_value(self.settings_page.text_metrics_combo, options.text_metrics_policy)
        self._set_combo_value(self.settings_page.preset_combo, preset)
        del blockers
        if persist:
            self._save_settings()
        self._sync_rendering_preset_label()
        self._update_preflight_summary()
        self._update_preview_panel()

    def _mark_rendering_preset_custom(self, *_: object) -> None:
        """Switch the preset selector to a named preset or to Custom after manual tweaks."""
        preset = detect_rendering_preset(self._current_rendering_options())
        blocker = QSignalBlocker(self.settings_page.preset_combo)
        self._set_combo_value(self.settings_page.preset_combo, preset or "custom")
        del blocker
        self._sync_rendering_preset_label()
        self._update_preflight_summary()
        self._update_preview_panel()

    def _sync_rendering_preset_label(self) -> None:
        """Refresh the preset combo tooltip so the current choice reads clearly."""
        preset = str(self.settings_page.preset_combo.currentData())
        if preset == "custom":
            self.settings_page.preset_combo.setToolTip("You are using a custom mix of advanced rendering policies.")
            return
        self.settings_page.preset_combo.setToolTip(f"Current preset: {rendering_preset_label(preset)}.")

    def _update_preflight_summary(self) -> None:
        """Explain the current conversion tradeoffs before the user starts a run."""
        cp = self.convert_page
        preset = str(self.settings_page.preset_combo.currentData())
        if preset == "custom":
            headline = "<b>Rendering preset:</b> Custom"
        else:
            headline = f"<b>Rendering preset:</b> {html.escape(rendering_preset_label(preset))}"
        details = "".join(
            f"<li>{html.escape(line)}</li>" for line in rendering_preflight_lines(self._current_rendering_options())
        )
        cp.preflight_summary_label.setText(f"{headline}<br><ul>{details}</ul>")

    def _sync_runtime_option_state(self) -> None:
        """Keep runtime-only options visually aligned with the selected mode."""
        cp = self.convert_page
        watch_enabled = cp.watch_checkbox.isChecked()
        tooltip = (
            "Watch mode processes changes sequentially as they arrive, so parallel workers are not used. "
            "Turn off Watch to enable multi-worker batch conversion."
            if watch_enabled
            else "Use multiple workers for one-shot batch conversions. "
            "Watch mode processes changes sequentially as they arrive."
        )
        cp.workers_spinbox.setEnabled(not watch_enabled)
        cp.workers_spinbox.setToolTip(tooltip)
        cp.workers_label.setToolTip(tooltip)
        cp.workers_label.setText(
            "parallel workers  (disabled in watch mode)" if watch_enabled else "parallel workers  (1 = sequential)"
        )

    # --------------------------------------------------------------- theme

    def _toggle_theme(self) -> None:
        """Manually flip between light and dark."""
        self._is_dark = not self._is_dark
        self._apply_styles()

    def _on_system_theme_changed(self, scheme: object) -> None:
        """Follow OS-level light/dark changes automatically."""
        self._is_dark = scheme == Qt.ColorScheme.Dark
        self._apply_styles()

    def _apply_styles(self) -> None:
        """Apply the current theme stylesheet and update theme-dependent text."""
        t = DARK if self._is_dark else LIGHT
        self.nav_bar.theme_button.setText("☀  Light" if self._is_dark else "☽  Dark")
        self.nav_bar.theme_button.setToolTip("Switch to light mode" if self._is_dark else "Switch to dark mode")
        self.nav_bar.set_title(
            f'{APP_TITLE} <span style="font-size:10px; color:{t["version_color"]}; font-weight:normal;">'
            f"v{__version__}</span>"
        )
        stylesheet = build_stylesheet(t)
        app = QApplication.instance()
        if isinstance(app, QApplication):
            app.setStyleSheet(stylesheet)
        else:
            self.setStyleSheet(stylesheet)
        self.preview_page.set_dark_mode(self._is_dark)
        self._apply_titlebar_theme()
        self._update_compatibility_panel()
        self._update_preview_panel()

    def _apply_titlebar_theme(self) -> None:
        """Match the native Windows title bar to the in-app theme via a DWM dark-mode hint.

        Windows draws the title bar itself (outside Qt's stylesheet reach) and defaults to the
        OS-wide light/dark setting, which can mismatch the in-app theme the user picked here.
        """
        if sys.platform != "win32":
            return
        try:  # type: ignore[unreachable]  # reachable at runtime on Windows; mypy's host platform may differ
            hwnd = int(self.winId())
            value = ctypes.c_int(1 if self._is_dark else 0)
            dwmapi = ctypes.windll.dwmapi
            for attribute in (20, 19):  # DWMWA_USE_IMMERSIVE_DARK_MODE: 20 on 20H1+, 19 on older builds
                if dwmapi.DwmSetWindowAttribute(hwnd, attribute, ctypes.byref(value), ctypes.sizeof(value)) == 0:
                    break
            user32 = ctypes.windll.user32
            flags = 0x0001 | 0x0002 | 0x0004 | 0x0020  # NOSIZE | NOMOVE | NOZORDER | FRAMECHANGED
            user32.SetWindowPos(hwnd, None, 0, 0, 0, 0, flags)
        except OSError:
            pass  # best-effort cosmetic hint; never block the app on platform quirks

    # -------------------------------------------------------------- queue

    def _sources(self) -> list[str]:
        """Return the queued input paths in their current order."""
        source_list = self.convert_page.source_list
        return [source_list.item(index).data(Qt.ItemDataRole.UserRole) for index in range(source_list.count())]

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
            if path.isfile(normalized):
                label = f"{path.basename(normalized)}  ({_fmt_size(path.getsize(normalized))})"
                tooltip = normalized
            else:
                label = normalized
                tooltip = f"{normalized}  (folder)"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, normalized)
            item.setToolTip(tooltip)
            self.convert_page.source_list.addItem(item)
            existing.add(normalized)
            added += 1

        if added:
            self._append_log(f"Queued {added} source path(s).", "info")
            self._set_idle_state("Ready to convert the current queue.")

    def _choose_files(self) -> None:
        """Open a file picker for one or more SVG inputs."""
        file_paths, _ = QFileDialog.getOpenFileNames(self, "Choose SVG files", "", "SVG files (*.svg)")
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
            self.convert_page.output_dir_edit.setText(directory)

    def _build_equivalent_cli_command(self) -> str:
        """Build a copy-paste-friendly CLI command matching the current desktop settings."""
        cp = self.convert_page
        output_dir = cp.output_dir_edit.text().strip()
        options = CliCommandOptions(
            sources=tuple(self._sources()),
            output_dir=path.abspath(output_dir) if output_dir else None,
            recursive=cp.recursive_checkbox.isChecked(),
            overwrite=cp.overwrite_checkbox.isChecked(),
            flatten=cp.flatten_checkbox.isChecked(),
            watch=cp.watch_checkbox.isChecked(),
            use_cache=cp.cache_checkbox.isChecked(),
            max_elements=cp.max_elements_spinbox.value() if cp.max_elements_checkbox.isChecked() else None,
            workers=cp.workers_spinbox.value(),
            preset=str(self.settings_page.preset_combo.currentData()),
            rendering_options=self._current_rendering_options(),
        )
        return build_equivalent_cli_command(options)

    def _copy_equivalent_cli_command(self) -> None:
        """Copy the matching CLI command for the current desktop configuration."""
        cp = self.convert_page
        command = self._build_equivalent_cli_command()
        QGuiApplication.clipboard().setText(command)
        self._append_log("Copied the equivalent CLI command to the clipboard.", "info")
        message = command
        if cp.watch_checkbox.isChecked() and cp.workers_spinbox.value() > 1:
            message += (
                "\n\nNote: watch mode does not use parallel workers, "
                "so the copied command intentionally omits --workers."
            )
        self._show_plain_text_dialog(QMessageBox.Icon.Information, "CLI command copied", message)

    # ----------------------------------------------------------- workflow

    def _start_conversion(self) -> None:
        """Launch the worker thread for the current queue."""
        source_paths = self._sources()
        if not source_paths:
            QMessageBox.information(self, "No sources", "Add at least one SVG file or folder first.")
            return

        cp = self.convert_page
        output_dir = cp.output_dir_edit.text().strip() or None
        rendering_options = self._current_rendering_options()
        options = ConversionOptions(
            output_dir=path.abspath(output_dir) if output_dir else None,
            recursive=cp.recursive_checkbox.isChecked(),
            overwrite=cp.overwrite_checkbox.isChecked(),
            flatten=cp.flatten_checkbox.isChecked(),
            max_elements=cp.max_elements_spinbox.value() if cp.max_elements_checkbox.isChecked() else None,
            use_cache=cp.cache_checkbox.isChecked(),
            rendering=rendering_options,
        )

        self._reset_run_state()
        self._goto_page(PAGE_RESULTS)
        live_watch = cp.watch_checkbox.isChecked()
        self._watch_mode_active = live_watch
        self._set_running_state("Preparing watch queue..." if live_watch else "Preparing conversion queue...")
        self._append_log(
            f"Starting {'watch session' if live_watch else 'batch'} with {len(source_paths)} source path(s).",
            "info",
        )
        for line in rendering_preflight_lines(rendering_options):
            self._append_log(f"Rendering: {line}", "info")

        self._thread = QThread(self)
        workers = cp.workers_spinbox.value()
        if live_watch:
            self._worker = WatchConversionWorker(source_paths, options)
        elif workers > 1:
            self._worker = ParallelConversionWorker(source_paths, options, max_workers=workers)
        else:
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
        self.results_page.cancel_button.setEnabled(False)
        self.results_page.status_label.setText("Cancellation requested. The current file will finish first.")
        self._append_log("Cancellation requested by the user.", "warning")

    def _handle_event(self, event: ConversionEvent) -> None:
        """Update the UI in response to one service progress event."""
        rp = self.results_page
        rp.progress_bar.setMaximum(event.total if event.total else 1)
        rp.progress_bar.setValue(event.completed)

        if event.kind == ConversionEventKind.STARTED:
            rp.status_label.setText(event.message)
            self._append_log(event.message, "info")
            return

        if event.kind == ConversionEventKind.CONVERTED:
            self._converted += 1
            if event.output_path:
                self._last_openable_directory = path.dirname(event.output_path)
                rp.open_output_button.setEnabled(True)
            self._append_log(event.message, "converted", link_path=event.output_path)
        elif event.kind == ConversionEventKind.SKIPPED:
            self._skipped += 1
            if event.output_path:
                self._last_openable_directory = path.dirname(event.output_path)
                rp.open_output_button.setEnabled(True)
            self._append_log(event.message, "skipped", link_path=event.output_path)
        elif event.kind == ConversionEventKind.FAILED:
            self._failed += 1
            self._append_log(event.message, "failed")
        elif event.kind == ConversionEventKind.CANCELLED:
            self._append_log(event.message, "warning")
        elif event.kind == ConversionEventKind.DISCOVERED:
            self._append_log(event.message, "info")

        if event.report is not None:
            self._last_reports.append(event.report)
            rp.export_report_button.setEnabled(True)
            self._warning_count += event.report.warning_count
            self._append_report_diagnostics(event.report)
            self._update_preview_panel(event.report)

        self._update_summary_labels()
        self._update_compatibility_panel()
        if event.summary is None:
            rp.status_label.setText(event.message)

    def _handle_finished(self, summary: ConversionSummary) -> None:
        """Finalize the UI after a successful worker shutdown."""
        rp = self.results_page
        self._converted = summary.converted
        self._skipped = summary.skipped
        self._failed = summary.failed
        self._last_reports = list(summary.reports)
        rp.export_report_button.setEnabled(bool(self._last_reports))
        self._warning_count = sum(report.warning_count for report in self._last_reports)
        self._update_summary_labels()
        self._update_compatibility_panel()
        self._update_preview_panel(summary.reports[-1] if summary.reports else None)
        rp.summary_label.setText(summary.to_status_line())
        rp.progress_bar.setMaximum(summary.total or 1)
        rp.progress_bar.setValue(summary.converted + summary.skipped + summary.failed)
        if summary.cancelled:
            status_text = (
                "Watch mode stopped."
                if self._watch_mode_active
                else "Batch cancelled after the current file completed."
            )
            rp.status_label.setText(status_text)
            self._append_log(summary.to_status_line(), "warning")
        elif summary.failed:
            rp.status_label.setText("Batch finished with at least one failure.")
            self._append_log(summary.to_status_line(), "failed")
        elif summary.total == 0:
            rp.status_label.setText("No SVG files were found in the queued sources.")
        else:
            rp.status_label.setText("Batch completed successfully.")
            self._append_log(summary.to_status_line(), "converted")
        self._set_controls_enabled(True)
        if self._tray and not self.isActiveWindow() and summary.total > 0:
            if summary.failed:
                self._tray.showMessage(
                    APP_TITLE,
                    f"Done: {summary.converted} converted, {summary.failed} failed.",
                    QSystemTrayIcon.MessageIcon.Warning,
                    5000,
                )
            else:
                self._tray.showMessage(
                    APP_TITLE,
                    f"Done: {summary.converted} file(s) converted successfully.",
                    QSystemTrayIcon.MessageIcon.Information,
                    4000,
                )

    def _handle_failure(self, error_message: str) -> None:
        """Show unrecoverable worker errors."""
        self._append_log(f"Batch aborted: {error_message}", "failed")
        self.results_page.status_label.setText("Batch aborted before conversion could complete.")
        self.results_page.summary_label.setText(error_message)
        self._set_controls_enabled(True)
        self._show_plain_text_dialog(QMessageBox.Icon.Critical, "Conversion failed", error_message)

    def _cleanup_worker(self) -> None:
        """Release thread-owned worker objects after the run ends."""
        if self._worker is not None:
            self._worker.deleteLater()
        if self._thread is not None:
            self._thread.deleteLater()
        self._worker = None
        self._thread = None
        self._watch_mode_active = False
        self.results_page.cancel_button.setEnabled(False)
        if self._close_after_run:
            self._close_after_run = False
            self.close()

    def _reset_run_state(self) -> None:
        """Clear counters and progress before starting a new batch."""
        self._converted = 0
        self._skipped = 0
        self._failed = 0
        self._warning_count = 0
        self._last_openable_directory = None
        self._last_reports = []
        self._preview_selected_report_index = None
        rp = self.results_page
        rp.open_output_button.setEnabled(False)
        rp.export_report_button.setEnabled(False)
        rp.progress_bar.setValue(0)
        rp.summary_label.clear()
        self._update_summary_labels()
        self._update_compatibility_panel()
        self._update_preview_panel()

    def _set_running_state(self, status_text: str) -> None:
        """Switch the window into its busy state."""
        self.results_page.status_label.setText(status_text)
        self._set_controls_enabled(False)
        self.results_page.cancel_button.setEnabled(True)

    def _set_idle_state(self, status_text: str) -> None:
        """Switch the window into its idle state."""
        self.results_page.status_label.setText(status_text)
        self._set_controls_enabled(True)
        self.results_page.cancel_button.setEnabled(False)

    def _set_controls_enabled(self, enabled: bool) -> None:
        """Enable or disable controls that should not change mid-run."""
        for widget in self.convert_page.controls():
            widget.setEnabled(enabled)
        self.results_page.export_report_button.setEnabled(enabled)

    # ------------------------------------------------------------- output

    def _update_summary_labels(self) -> None:
        """Refresh the counter tiles from the current totals."""
        rp = self.results_page
        rp.converted_card.set_value(self._converted)
        rp.skipped_card.set_value(self._skipped)
        rp.failed_card.set_value(self._failed)
        rp.warnings_card.set_value(self._warning_count)
        rp.summary_label.setText(
            "Converted: "
            f"{self._converted}   |   Skipped: {self._skipped}   |   Failed: {self._failed}"
            f"   |   Warnings: {self._warning_count}"
        )

    def _update_compatibility_panel(self) -> None:
        """Refresh the beginner-friendly compatibility summary for the latest run."""
        rp = self.results_page
        if not self._last_reports:
            self._last_compatibility_rows = []
            rp.compatibility_summary_label.setText(
                "Run a conversion to see what stayed editable, what was simplified, "
                "and what had to fall back to embedded SVG."
            )
            rp.compatibility_output.setHtml(
                '<div style="line-height:1.45;">'
                "No conversion data yet. After a run, this panel will explain the result in plain English."
                "</div>"
            )
            return

        observations = []
        for report in self._last_reports:
            observations.extend(report.feature_observations)

        rows = build_compatibility_rows(observations)
        self._last_compatibility_rows = rows
        overview = build_compatibility_overview(rows)
        file_count = len(self._last_reports)
        scope_text = "last file" if file_count == 1 else f"last {file_count} files"
        rp.compatibility_summary_label.setText(f"{overview.headline} {overview.summary} Based on the {scope_text}.")
        rp.compatibility_output.setHtml(self._compatibility_html(rows))

    def _update_preview_panel(self, report: ConversionReport | None = None) -> None:
        """Refresh the preview page from the selected report or the latest live result."""
        self._sync_preview_file_selector()
        active_report = self._resolve_preview_report(report)
        if active_report is None:
            self._active_preview_report = None
            self.preview_page.clear_preview()
            return

        self._active_preview_report = active_report
        source_path = (
            active_report.source_path if active_report.source_path and path.isfile(active_report.source_path) else None
        )
        file_label = active_report.source_path or "No local SVG source path recorded."
        self.preview_page.set_preview(
            svg_path=source_path,
            file_label=f"{file_label} - {active_report.short_status()}",
            annotations=active_report.preview_annotations,
            text_metrics_policy=self._current_rendering_options().text_metrics_policy,
        )

    def _sync_preview_file_selector(self) -> None:
        """Keep the preview selector aligned with the current batch history."""
        if self._preview_selected_report_index is not None and not (
            0 <= self._preview_selected_report_index < len(self._last_reports)
        ):
            self._preview_selected_report_index = None

        labels = [self._preview_selector_label(index, report) for index, report in enumerate(self._last_reports)]
        self.preview_page.set_preview_choices(labels, self._preview_selected_report_index)

    def _resolve_preview_report(self, latest_report: ConversionReport | None = None) -> ConversionReport | None:
        """Return the report that should currently drive the preview page."""
        if not self._last_reports:
            return None
        if self._preview_selected_report_index is not None:
            return self._last_reports[self._preview_selected_report_index]
        if latest_report is not None:
            return latest_report
        return self._last_reports[-1]

    def _preview_selector_label(self, index: int, report: ConversionReport) -> str:
        """Build a compact label for one previewable conversion report."""
        display_name = path.basename(report.source_path) if report.source_path else f"Item {index + 1}"
        return f"{index + 1}. {display_name} - {report.short_status()}"

    def _on_preview_report_selected(self, report_index: int) -> None:
        """Lock the preview onto one processed file, or switch back to auto-follow mode."""
        self._preview_selected_report_index = report_index if report_index >= 0 else None
        self._update_preview_panel()

    def _compatibility_html(self, rows: list[CompatibilityRow]) -> str:
        """Render the compatibility matrix as compact rich text for the results page."""
        return render_compatibility_html(rows, palette=DARK if self._is_dark else LIGHT)

    def _show_plain_text_dialog(self, icon: QMessageBox.Icon, title: str, text: str) -> None:
        """Show a message dialog that always renders *text* as plain text.

        `QMessageBox.information`/`.critical` auto-detect rich text via Qt's
        `mightBeRichText()` heuristic, so SVG-derived content (an element id, a file
        path) containing something that looks like an HTML tag could be silently
        misrendered instead of shown literally. Forcing plain text avoids that.
        """
        box = QMessageBox(self)
        box.setIcon(icon)
        box.setWindowTitle(title)
        box.setText(text)
        box.setTextFormat(Qt.TextFormat.PlainText)
        box.exec()

    def _on_compatibility_link_clicked(self, url: QUrl) -> None:
        """Show a detailed explanation for one clicked compatibility capability."""
        if url.scheme() != "capability":
            return
        feature_key = url.path().lstrip("/") or url.toString().split(":", 1)[-1]
        row = next((item for item in self._last_compatibility_rows if item.feature_key == feature_key), None)
        if row is None:
            return

        self._show_plain_text_dialog(
            QMessageBox.Icon.Information, row.label, build_feature_dialog_text(row, self._last_reports)
        )

    def _on_preview_annotation_clicked(self, annotation: PreviewAnnotation) -> None:
        """Show the compatibility explanation that best matches one clicked preview region."""
        active_report = self._active_preview_report
        lines = [annotation.label, annotation.message]
        if annotation.element_id:
            lines.append(f"Source id: {annotation.element_id}")
        if annotation.element_tag:
            lines.append(f"Source tag: <{annotation.element_tag}>")

        if active_report is None or not annotation.feature_key:
            self._show_plain_text_dialog(QMessageBox.Icon.Information, annotation.label, "\n".join(lines))
            return

        row = next(
            (item for item in active_report.compatibility_matrix if item.feature_key == annotation.feature_key),
            None,
        )
        if row is None:
            self._show_plain_text_dialog(QMessageBox.Icon.Information, annotation.label, "\n".join(lines))
            return

        dialog_text = "\n".join(lines + ["", build_feature_dialog_text(row, [active_report])])
        self._show_plain_text_dialog(QMessageBox.Icon.Information, row.label, dialog_text)

    def _append_report_diagnostics(self, report: ConversionReport) -> None:
        """Append one compact diagnostics block for a finished file conversion."""
        if not report.issues:
            if report.cached:
                self._append_log(f"Diagnostics: {report.short_status()}", "info")
            return
        self._append_log(f"Diagnostics: {report.short_status()}", "warning")
        for issue in report.issues:
            tone = "failed" if issue.severity == "error" else "warning"
            self._append_log(f"{issue.message}", tone)

    def _append_log(self, message: str, tone: str, link_path: str | None = None) -> None:
        """Append a timestamped, styled log line; optionally make it a clickable file link."""
        t = DARK if self._is_dark else LIGHT
        color = {
            "converted": t["log_converted"],
            "failed": t["log_failed"],
            "warning": t["log_warning"],
            "skipped": t["log_skipped"],
            "info": t["log_info"],
        }.get(tone, t["log_default"])
        ts = datetime.now().strftime("%H:%M:%S")
        escaped = html.escape(message)
        if link_path:
            url = QUrl.fromLocalFile(link_path).toString()
            body = f'<a href="{url}" style="color:{color}; text-decoration:none;">{escaped}</a>'
        else:
            body = f'<span style="color:{color};">{escaped}</span>'
        self.results_page.log_output.append(f'<span style="color:{t["log_ts"]};">[{ts}]</span> {body}')

    def _on_log_link_clicked(self, url: QUrl) -> None:
        """Open the file linked from a log line with the default OS application."""
        QDesktopServices.openUrl(url)

    def _open_output_directory(self) -> None:
        """Open the most recently written output directory in the OS file manager."""
        if not self._last_openable_directory:
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(self._last_openable_directory))

    def _export_last_report(self) -> None:
        """Write the latest structured diagnostics report to a JSON file."""
        if not self._last_reports:
            QMessageBox.information(self, "No report", "Run at least one conversion first.")
            return
        target_path, _ = QFileDialog.getSaveFileName(
            self, "Export conversion report", "svg-to-drawio-report.json", "JSON files (*.json)"
        )
        if not target_path:
            return
        payload = {
            "report_schema_version": REPORT_SCHEMA_VERSION,
            "mode": "desktop",
            "converted": self._converted,
            "skipped": self._skipped,
            "failed": self._failed,
            "warnings": self._warning_count,
            "reports": [report.to_dict() for report in self._last_reports],
        }
        with open(target_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
        self._append_log(f"Exported structured report to: {target_path}", "info", link_path=target_path)

    # --------------------------------------------------------------- tray

    def _setup_tray(self) -> None:
        """Create a system tray icon if the desktop environment supports it."""
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        self._tray = QSystemTrayIcon(self)
        self._tray.setIcon(load_app_icon())
        self._tray.setToolTip(APP_TITLE)
        self._tray.activated.connect(self._on_tray_activated)
        self._tray.show()

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        """Restore the window when the user double-clicks the tray icon."""
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.showNormal()
            self.raise_()
            self.activateWindow()

    def _show_about(self) -> None:
        """Display the About dialog with the application version."""
        dialog = QMessageBox(self)
        dialog.setWindowTitle(f"About {APP_TITLE}")
        dialog.setIconPixmap(load_brand_pixmap(72))
        dialog.setTextFormat(Qt.TextFormat.RichText)
        dialog.setText(
            f"<div style='font-size:18px; font-weight:700;'>{APP_TITLE}</div>"
            f"<div style='margin-top:4px;'>Version {__version__}</div>"
        )
        dialog.setInformativeText(
            "Convert SVG files into editable draw.io diagrams.\n\n"
            "Use the desktop app for interactive batch work, previews, and compatibility guidance."
        )
        dialog.setStandardButtons(QMessageBox.StandardButton.Ok)
        dialog.exec()


def create_application() -> QApplication:
    """Create and configure the desktop QApplication instance."""
    _install_qt_message_filter()
    app = QApplication.instance()
    if isinstance(app, QApplication):
        return cast(QApplication, app)

    created = QApplication(sys.argv)
    created.setApplicationName(APP_TITLE)
    created.setOrganizationName("svg-to-drawio")
    created.setDesktopFileName("io.github.v1rg1lee.svg-to-drawio")
    created.setWindowIcon(load_app_icon())
    created.setStyle("Fusion")
    return created


def main() -> int:
    """Launch the desktop application."""
    _install_crash_handler()
    app = create_application()
    window = MainWindow()
    window.show()
    return int(app.exec())
