"""Reusable widgets for the desktop converter application."""

from __future__ import annotations

from os import path

from PySide6.QtCore import QRect, Qt, Signal
from PySide6.QtGui import QColor, QDragEnterEvent, QDragMoveEvent, QDropEvent, QFont, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .theme import STATUS_ICON, load_brand_pixmap


class SourceListWidget(QListWidget):
    """List widget that accepts dropped SVG files and folders."""

    paths_dropped = Signal(list)

    def __init__(self) -> None:
        super().__init__()
        self.setAcceptDrops(True)
        self.setAlternatingRowColors(False)
        self.setSelectionMode(self.SelectionMode.ExtendedSelection)
        self.setDragEnabled(True)
        self.setDragDropMode(self.DragDropMode.InternalMove)

    def paintEvent(self, event: QPaintEvent) -> None:
        super().paintEvent(event)
        if self.count() > 0:
            return

        vp = self.viewport()
        painter = QPainter(vp)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = vp.rect()
        margin = 16
        inner = rect.adjusted(margin, margin, -margin, -margin)

        # Dashed drop-zone border
        pen = QPen(QColor("#cbd5e1"), 2, Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(inner, 10, 10)

        cx = rect.center().x()

        # Compute block height to center the whole thing precisely
        ICON_H = 26  # arrow icon height
        GAP1 = 10
        TEXT1_H = 24  # primary text
        GAP2 = 6
        TEXT2_H = 18  # secondary text
        TOTAL = ICON_H + GAP1 + TEXT1_H + GAP2 + TEXT2_H  # 84 px

        top = (rect.height() - TOTAL) // 2
        icon_cy = top + ICON_H // 2

        # Arrow icon
        icon_pen = QPen(QColor("#94a3b8"), 2.5, Qt.PenStyle.SolidLine)
        icon_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        icon_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(icon_pen)
        painter.drawLine(cx, icon_cy - 10, cx, icon_cy + 6)
        painter.drawLine(cx - 8, icon_cy - 2, cx, icon_cy + 6)
        painter.drawLine(cx + 8, icon_cy - 2, cx, icon_cy + 6)
        painter.drawLine(cx - 12, icon_cy + 12, cx + 12, icon_cy + 12)

        # Primary text
        text1_y = top + ICON_H + GAP1
        painter.setPen(QColor("#475569"))
        font = QFont()
        font.setPointSize(11)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(
            QRect(rect.left() + 24, text1_y, rect.width() - 48, TEXT1_H),
            int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter),
            "Drop SVG files or folders here",
        )

        # Secondary text
        text2_y = text1_y + TEXT1_H + GAP2
        font.setBold(False)
        font.setPointSize(10)
        painter.setFont(font)
        painter.setPen(QColor("#94a3b8"))
        painter.drawText(
            QRect(rect.left() + 24, text2_y, rect.width() - 48, TEXT2_H),
            int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter),
            "or use the buttons above to browse",
        )

        painter.end()

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        """Accept drags that contain local file URLs."""
        if self._has_file_urls(event):
            event.acceptProposedAction()
            return
        super().dragEnterEvent(event)

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:
        """Keep accepting valid drags while they move over the widget."""
        if self._has_file_urls(event):
            event.acceptProposedAction()
            return
        super().dragMoveEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:
        """Emit all dropped local paths for the main window to normalize."""
        mime_data = event.mimeData()
        if not mime_data.hasUrls():
            super().dropEvent(event)
            return

        paths = [
            local_path
            for url in mime_data.urls()
            if (local_path := url.toLocalFile()) and (path.isdir(local_path) or local_path.lower().endswith(".svg"))
        ]
        if paths:
            self.paths_dropped.emit(paths)
            event.acceptProposedAction()
            return
        super().dropEvent(event)

    def _has_file_urls(self, event: QDragEnterEvent | QDragMoveEvent) -> bool:
        """Return whether the drag payload contains at least one local path."""
        mime_data = event.mimeData()
        return mime_data.hasUrls() and any(url.isLocalFile() for url in mime_data.urls())


class NavBar(QFrame):
    """Slim top app bar: brand mark, page switcher, theme toggle, and overflow menu."""

    page_changed = Signal(int)

    def __init__(self, page_labels: list[str]) -> None:
        super().__init__()
        self.setObjectName("headerBar")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 10, 12, 10)
        layout.setSpacing(16)

        brand_logo = QLabel()
        brand_logo.setPixmap(load_brand_pixmap(30))
        brand_logo.setFixedSize(30, 30)
        layout.addWidget(brand_logo)

        self.title_label = QLabel()
        self.title_label.setObjectName("headerTitle")
        self.title_label.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(self.title_label)

        layout.addStretch(1)

        self._pill_group = QButtonGroup(self)
        self._pill_group.setExclusive(True)
        pill_row = QHBoxLayout()
        pill_row.setSpacing(4)
        for index, label in enumerate(page_labels):
            pill = QPushButton(label)
            pill.setObjectName("navPill")
            pill.setCheckable(True)
            pill.setCursor(Qt.CursorShape.PointingHandCursor)
            pill.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            self._pill_group.addButton(pill, index)
            pill_row.addWidget(pill)
        self._pill_group.button(0).setChecked(True)
        self._pill_group.idClicked.connect(self.page_changed)
        layout.addLayout(pill_row)

        layout.addStretch(1)

        self.overflow_button = QToolButton()
        self.overflow_button.setObjectName("overflowButton")
        self.overflow_button.setText("⋯")  # midline horizontal ellipsis
        self.overflow_button.setToolTip("More actions")
        self.overflow_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        layout.addWidget(self.overflow_button)

        self.theme_button = QPushButton()
        self.theme_button.setObjectName("themeButton")
        self.theme_button.setFixedHeight(28)
        layout.addWidget(self.theme_button)

    def set_current_page(self, index: int) -> None:
        """Sync the checked pill without re-emitting `page_changed`."""
        button = self._pill_group.button(index)
        if button is not None and not button.isChecked():
            button.setChecked(True)

    def set_title(self, title_html: str) -> None:
        """Update the brand title text (rich text, e.g. includes a version span)."""
        self.title_label.setText(title_html)


class CollapsibleSection(QWidget):
    """A disclosure widget that shows/hides a body of content behind a header toggle."""

    def __init__(self, title: str, *, expanded: bool = False) -> None:
        super().__init__()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(6)

        self._collapsed_text = f"▸  {title}"
        self._expanded_text = f"▾  {title}"

        self.header_button = QToolButton()
        self.header_button.setObjectName("disclosureHeader")
        self.header_button.setCheckable(True)
        self.header_button.setChecked(expanded)
        self.header_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.header_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.header_button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        outer.addWidget(self.header_button)

        self.content = QWidget()
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(0, 4, 0, 0)
        self.content_layout.setSpacing(10)
        outer.addWidget(self.content)

        self.header_button.toggled.connect(self._on_toggled)
        self._on_toggled(expanded)

    def _on_toggled(self, checked: bool) -> None:
        self.header_button.setText(self._expanded_text if checked else self._collapsed_text)
        self.content.setVisible(checked)


class CounterCard(QFrame):
    """One colour-coded summary tile, paired with a status glyph for accessibility."""

    def __init__(self, label: str, variant: str = "neutral") -> None:
        super().__init__()
        self.setObjectName(f"{variant}Card")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(4)

        icon = STATUS_ICON.get(variant, "")
        title = QLabel(f"{icon}  {label.upper()}" if icon else label.upper())
        title.setObjectName(f"{variant}CardTitle")
        layout.addWidget(title)

        self.value_label = QLabel("0")
        self.value_label.setObjectName(f"{variant}CardValue")
        font = QFont()
        font.setPointSize(20)
        font.setBold(True)
        self.value_label.setFont(font)
        layout.addWidget(self.value_label)

    def set_value(self, value: int | str) -> None:
        """Update the displayed count."""
        self.value_label.setText(str(value))
