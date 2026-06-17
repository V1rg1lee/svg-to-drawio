"""Page widgets for the desktop application: Convert, Results, and Settings."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QTextBrowser,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .widgets import CollapsibleSection, CounterCard, SourceListWidget


def make_help_badge(tooltip_text: str) -> QToolButton:
    """Create a compact round help badge that shows an explanatory tooltip on hover."""
    button = QToolButton()
    button.setObjectName("helpBadge")
    button.setText("?")
    button.setToolTip(tooltip_text)
    button.setCursor(Qt.CursorShape.WhatsThisCursor)
    button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    button.setFixedSize(20, 20)
    return button


def make_policy_combo(items: list[tuple[str, str]], current_value: str) -> QComboBox:
    """Create a combo box initialized to the given persisted policy value."""
    combo = QComboBox()
    for label, value in items:
        combo.addItem(label, value)
    index = combo.findData(current_value)
    combo.setCurrentIndex(index if index >= 0 else 0)
    return combo


def make_policy_field(combo: QComboBox, tooltip_text: str) -> QWidget:
    """Create one field row with a combo box and an inline help badge."""
    container = QWidget()
    layout = QHBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(8)
    layout.addWidget(combo, stretch=1)
    layout.addWidget(make_help_badge(tooltip_text))
    return container


class ConvertPage(QWidget):
    """Landing page: queue sources, pick the essentials, and start a batch."""

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("pageRoot")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 24)
        layout.setSpacing(16)

        heading = QLabel("Convert your SVG files")
        heading.setObjectName("pageHeading")
        layout.addWidget(heading)

        subheading = QLabel("Drop files or folders, choose where to save the result, then start the batch.")
        subheading.setObjectName("pageSubheading")
        subheading.setWordWrap(True)
        layout.addWidget(subheading)

        layout.addWidget(self._build_sources_group(), stretch=1)
        layout.addWidget(self._build_essentials_group())
        layout.addWidget(self._build_more_options_section())
        layout.addWidget(self._build_preflight_group())
        layout.addLayout(self._build_actions_row())

    def _build_sources_group(self) -> QGroupBox:
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
        self.source_list.setMinimumHeight(150)
        layout.addWidget(self.source_list, stretch=1)

        self.remove_selected_button.clicked.connect(self._remove_selected_sources)
        self.clear_sources_button.clicked.connect(self.source_list.clear)
        return group

    def _remove_selected_sources(self) -> None:
        """Remove the currently selected queue entries."""
        for item in self.source_list.selectedItems():
            self.source_list.takeItem(self.source_list.row(item))

    def _build_essentials_group(self) -> QGroupBox:
        group = QGroupBox("Output")
        layout = QFormLayout(group)
        layout.setContentsMargins(14, 6, 14, 14)
        layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        output_row = QHBoxLayout()
        output_row.setSpacing(8)
        self.output_dir_edit = QLineEdit()
        self.output_dir_edit.setPlaceholderText("Optional: choose a dedicated output folder")
        self.browse_output_button = QToolButton()
        self.browse_output_button.setText("Browse")
        output_row.addWidget(self.output_dir_edit, stretch=1)
        output_row.addWidget(self.browse_output_button)
        output_container = QWidget()
        output_container.setLayout(output_row)
        layout.addRow("Output directory", output_container)

        self.overwrite_checkbox = QCheckBox("Overwrite existing `.drawio` files")
        layout.addRow("", self.overwrite_checkbox)
        return group

    def _build_more_options_section(self) -> CollapsibleSection:
        section = CollapsibleSection("More options", expanded=False)

        self.recursive_checkbox = QCheckBox("Recurse into subfolders when a queued item is a directory")
        self.flatten_checkbox = QCheckBox("Flatten groups - emit all shapes at the root level")
        self.watch_checkbox = QCheckBox("Keep watching source files and auto-convert them on change")
        self.cache_checkbox = QCheckBox("Reuse the persistent cache and skip unchanged inputs")
        self.cache_checkbox.setChecked(True)
        for checkbox in (
            self.recursive_checkbox,
            self.flatten_checkbox,
            self.watch_checkbox,
            self.cache_checkbox,
        ):
            section.content_layout.addWidget(checkbox)

        workers_row = QHBoxLayout()
        workers_row.setSpacing(6)
        self.workers_spinbox = QSpinBox()
        self.workers_spinbox.setRange(1, 8)
        self.workers_spinbox.setValue(1)
        self.workers_spinbox.setFixedWidth(56)
        self.workers_spinbox.setToolTip(
            "Use multiple workers for one-shot batch conversions. "
            "Watch mode processes changes sequentially as they arrive."
        )
        self.workers_label = QLabel("parallel workers  (1 = sequential)")
        self.workers_label.setToolTip(self.workers_spinbox.toolTip())
        workers_row.addWidget(self.workers_spinbox)
        workers_row.addWidget(self.workers_label)
        workers_row.addStretch()
        section.content_layout.addLayout(workers_row)

        max_el_row = QHBoxLayout()
        max_el_row.setSpacing(6)
        self.max_elements_checkbox = QCheckBox("Limit output to")
        self.max_elements_spinbox = QSpinBox()
        self.max_elements_spinbox.setRange(1, 999_999)
        self.max_elements_spinbox.setValue(1000)
        self.max_elements_spinbox.setSingleStep(500)
        self.max_elements_spinbox.setFixedWidth(84)
        self.max_elements_spinbox.setEnabled(False)
        self.max_elements_checkbox.toggled.connect(self.max_elements_spinbox.setEnabled)
        max_el_row.addWidget(self.max_elements_checkbox)
        max_el_row.addWidget(self.max_elements_spinbox)
        max_el_row.addWidget(QLabel("elements"))
        max_el_row.addStretch()
        section.content_layout.addLayout(max_el_row)

        return section

    def _build_actions_row(self) -> QHBoxLayout:
        actions = QHBoxLayout()
        actions.setSpacing(10)
        self.start_button = QPushButton("Start Conversion")
        self.start_button.setObjectName("startButton")
        self.copy_cli_button = QPushButton("Copy CLI Command")
        self.copy_cli_button.setObjectName("copyCliButton")
        actions.addWidget(self.start_button)
        actions.addWidget(self.copy_cli_button)
        actions.addStretch(1)
        return actions

    def _build_preflight_group(self) -> QGroupBox:
        group = QGroupBox("Conversion summary")
        layout = QVBoxLayout(group)
        layout.setContentsMargins(14, 10, 14, 14)
        layout.setSpacing(8)

        self.preflight_summary_label = QLabel()
        self.preflight_summary_label.setObjectName("preflightSummaryLabel")
        self.preflight_summary_label.setWordWrap(True)
        self.preflight_summary_label.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(self.preflight_summary_label)
        return group

    def controls(self) -> list[QWidget]:
        """Return the widgets that should be disabled while a batch is running."""
        return [
            self.add_files_button,
            self.add_folder_button,
            self.remove_selected_button,
            self.clear_sources_button,
            self.source_list,
            self.output_dir_edit,
            self.browse_output_button,
            self.recursive_checkbox,
            self.overwrite_checkbox,
            self.flatten_checkbox,
            self.watch_checkbox,
            self.cache_checkbox,
            self.workers_spinbox,
            self.max_elements_checkbox,
            self.max_elements_spinbox,
            self.start_button,
            self.copy_cli_button,
        ]


class ResultsPage(QWidget):
    """Shows live progress, plain-English compatibility results, and the technical log."""

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("pageRoot")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 24)
        layout.setSpacing(16)

        heading = QLabel("Results")
        heading.setObjectName("pageHeading")
        layout.addWidget(heading)

        layout.addWidget(self._build_progress_group())
        layout.addWidget(self._build_compatibility_group(), stretch=1)
        layout.addWidget(self._build_log_section())

    def _build_progress_group(self) -> QGroupBox:
        group = QGroupBox("Progress")
        layout = QVBoxLayout(group)
        layout.setContentsMargins(14, 6, 14, 14)
        layout.setSpacing(12)

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
        self.converted_card = CounterCard("Converted", "success")
        self.skipped_card = CounterCard("Skipped", "warning")
        self.failed_card = CounterCard("Failed", "error")
        self.warnings_card = CounterCard("Warnings", "neutral")
        counts.addWidget(self.converted_card, 0, 0)
        counts.addWidget(self.skipped_card, 0, 1)
        counts.addWidget(self.failed_card, 0, 2)
        counts.addWidget(self.warnings_card, 1, 0, 1, 3)
        layout.addLayout(counts)

        actions = QHBoxLayout()
        actions.setSpacing(10)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setObjectName("cancelButton")
        self.cancel_button.setEnabled(False)
        self.open_output_button = QPushButton("Open Output Folder")
        self.open_output_button.setObjectName("openOutputButton")
        self.open_output_button.setEnabled(False)
        self.export_report_button = QPushButton("Export Last Report")
        self.export_report_button.setObjectName("exportReportButton")
        self.export_report_button.setEnabled(False)
        actions.addWidget(self.cancel_button)
        actions.addWidget(self.open_output_button)
        actions.addWidget(self.export_report_button)
        actions.addStretch(1)
        layout.addLayout(actions)
        return group

    def _build_compatibility_group(self) -> QFrame:
        surface = QFrame()
        surface.setObjectName("compatibilitySurface")
        layout = QVBoxLayout(surface)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        self.compatibility_heading = QLabel("Compatibility At A Glance")
        self.compatibility_heading.setObjectName("compatibilityHeading")
        layout.addWidget(self.compatibility_heading)

        self.compatibility_summary_label = QLabel()
        self.compatibility_summary_label.setObjectName("compatibilitySummaryLabel")
        self.compatibility_summary_label.setWordWrap(True)
        layout.addWidget(self.compatibility_summary_label)

        self.compatibility_hint_label = QLabel(
            "Click any capability row below to see the affected elements and details."
        )
        self.compatibility_hint_label.setObjectName("compatibilityHintLabel")
        self.compatibility_hint_label.setWordWrap(True)
        layout.addWidget(self.compatibility_hint_label)

        self.compatibility_output = QTextBrowser()
        self.compatibility_output.setObjectName("compatibilityOutput")
        self.compatibility_output.setFrameShape(QFrame.Shape.NoFrame)
        self.compatibility_output.setMinimumHeight(160)
        self.compatibility_output.setOpenLinks(False)
        self.compatibility_output.setOpenExternalLinks(False)
        layout.addWidget(self.compatibility_output, stretch=1)
        return surface

    def _build_log_section(self) -> CollapsibleSection:
        section = CollapsibleSection("Technical log", expanded=False)

        log_toolbar = QHBoxLayout()
        log_toolbar.addStretch(1)
        self.clear_log_button = QPushButton("Clear Log")
        self.clear_log_button.setObjectName("clearLogButton")
        log_toolbar.addWidget(self.clear_log_button)
        section.content_layout.addLayout(log_toolbar)

        log_surface = QFrame()
        log_surface.setObjectName("logSurface")
        log_layout = QVBoxLayout(log_surface)
        log_layout.setContentsMargins(12, 12, 12, 16)
        log_layout.setSpacing(0)

        self.log_output = QTextBrowser()
        self.log_output.setObjectName("logOutput")
        self.log_output.setMinimumHeight(180)
        self.log_output.setFrameShape(QFrame.Shape.NoFrame)
        self.log_output.setOpenLinks(False)
        self.log_output.setPlaceholderText("Conversion events will appear here...")
        mono_font = QFont("Consolas")
        mono_font.setStyleHint(QFont.StyleHint.Monospace)
        mono_font.setPointSize(9)
        self.log_output.setFont(mono_font)
        log_layout.addWidget(self.log_output)

        self.clear_log_button.clicked.connect(self.log_output.clear)
        section.content_layout.addWidget(log_surface)
        return section


class SettingsPage(QWidget):
    """Rendering policies that trade native editability against visual fidelity."""

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("pageRoot")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 24)
        layout.setSpacing(16)

        heading = QLabel("Rendering settings")
        heading.setObjectName("pageHeading")
        layout.addWidget(heading)

        subheading = QLabel(
            "Choose how the engine balances native editability, visual fidelity, and deterministic "
            "text sizing. These settings apply to the desktop app, the CLI, and the Python API alike."
        )
        subheading.setObjectName("pageSubheading")
        subheading.setWordWrap(True)
        layout.addWidget(subheading)

        layout.addWidget(self._build_policies_group())
        layout.addStretch(1)

    def _build_policies_group(self) -> QGroupBox:
        group = QGroupBox("Rendering policies")
        form = QFormLayout(group)
        form.setContentsMargins(14, 10, 14, 16)
        form.setSpacing(14)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        self.preset_combo = make_policy_combo(
            [
                ("Balanced", "balanced"),
                ("Best editability", "editability"),
                ("Best visual fidelity", "fidelity"),
                ("Custom", "custom"),
            ],
            "balanced",
        )
        form.addRow(
            "Preset",
            make_policy_field(
                self.preset_combo,
                "Choose a ready-made rendering profile.\n\n"
                "Balanced: keeps the default mix of editability and fidelity.\n\n"
                "Best editability: favors native draw.io content whenever possible, even when this means "
                "simplifying unsupported gradients or filters.\n\n"
                "Best visual fidelity: prefers embedded SVG fallback more aggressively so the result looks "
                "closer to the source SVG.\n\n"
                "Custom: appears automatically when you tweak the advanced policies manually.",
            ),
        )

        self.gradient_combo = make_policy_combo(
            [
                ("Auto", "auto"),
                ("Prefer native editability", "prefer-native"),
                ("Prefer SVG fallback fidelity", "prefer-fallback"),
            ],
            "auto",
        )
        form.addRow(
            "Gradients",
            make_policy_field(
                self.gradient_combo,
                "Controls how multi-stop gradients balance editability and visual fidelity.\n\n"
                "Auto: Use native draw.io gradients when the engine can approximate them well; "
                "otherwise preserve the gradient through embedded SVG fallback.\n\n"
                "Prefer native editability: Keep the output editable even when an exact multi-stop "
                "gradient is not supported. The engine may simplify the gradient to a more basic "
                "draw.io-native version.\n\n"
                "Prefer SVG fallback fidelity: Preserve the multi-stop gradient through embedded SVG "
                "fallback whenever needed. This keeps the look closer to the source SVG, but the "
                "result is less editable in draw.io.",
            ),
        )

        self.filter_combo = make_policy_combo(
            [
                ("Auto", "auto"),
                ("Prefer native editability", "prefer-native"),
                ("Force SVG fallback", "force-fallback"),
            ],
            "auto",
        )
        form.addRow(
            "Filters",
            make_policy_field(
                self.filter_combo,
                "Controls what happens when SVG filters are present.\n\n"
                "Auto: Keep supported filters natively when possible and use embedded SVG fallback "
                "for unsupported ones.\n\n"
                "Prefer native editability: Ignore unsupported filters instead of falling back, so "
                "the surrounding shapes stay editable. This can reduce visual fidelity if the filter "
                "effect is important.\n\n"
                "Force SVG fallback: Preserve filtered content through embedded SVG fallback whenever "
                "a filter is present. This gives the most faithful visual result, but it is less "
                "editable in draw.io.",
            ),
        )

        self.text_metrics_combo = make_policy_combo(
            [
                ("Auto", "auto"),
                ("System font metrics", "system"),
                ("Heuristic only", "heuristic"),
            ],
            "auto",
        )
        form.addRow(
            "Text sizing",
            make_policy_field(
                self.text_metrics_combo,
                "Controls how text bounds are estimated before they are turned into draw.io text cells.\n\n"
                "Auto: Use system font metrics when available and fall back to the built-in heuristic "
                "otherwise.\n\n"
                "System font metrics: Prefer real platform font measurements for the most visually "
                "accurate text sizing on the current machine.\n\n"
                "Heuristic only: Use the built-in estimator without asking the system font backend. "
                "This is useful when you want more deterministic results across environments, even if "
                "the sizing is slightly less precise.",
            ),
        )
        return group
