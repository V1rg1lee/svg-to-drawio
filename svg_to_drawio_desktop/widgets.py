"""Reusable widgets for the desktop converter application."""

from __future__ import annotations

from os import path

from PySide6.QtCore import QRect, Qt, Signal
from PySide6.QtGui import QColor, QDragEnterEvent, QDragMoveEvent, QDropEvent, QFont, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import QListWidget


class SourceListWidget(QListWidget):
    """List widget that accepts dropped SVG files and folders."""

    paths_dropped = Signal(list)

    def __init__(self) -> None:
        super().__init__()
        self.setAcceptDrops(True)
        self.setAlternatingRowColors(False)
        self.setSelectionMode(self.SelectionMode.ExtendedSelection)

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
