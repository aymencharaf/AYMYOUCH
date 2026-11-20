"""Building blocks for the professional tool pages.

The older pages hand-build a header, a device combo and a stack of buttons.
The new service pages (Fastboot, Unlock & FRP, Device Control, Packages &
Files, Logs & Reports) are big, so they share one builder instead of
duplicating a thousand lines: grouped action rows, notes, a result console
and a per-page device selector bound to the shared registry.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .busy import BusySpinner
from .devices import fill_device_combo


class ToolPage:
    """Assembles one professional page and keeps its widgets together."""

    def __init__(self, app, title, description, combo_attr, icon=None):
        self.app = app
        self.title = title
        self.combo_attr = combo_attr
        self.page = QWidget()
        self.layout = QVBoxLayout(self.page)
        self.layout.setContentsMargins(30, 25, 30, 25)
        self.layout.setSpacing(10)
        self.spinner = None
        self.combo = None
        self.result_box = None
        self._section_rows = {}

        self.layout.addLayout(
            app.create_page_header(title, description)
        )

    # ------------------------------------------------------------------
    # device selector
    # ------------------------------------------------------------------

    def with_device_selector(self, label="Connected Device"):
        """Add the shared device list + spinner + refresh row."""
        app = self.app
        self.combo = QComboBox()
        self.spinner = BusySpinner(app.palette, 18)
        setattr(app, self.combo_attr, self.combo)

        refresh = QPushButton("Refresh")
        refresh.setObjectName("Primary")
        refresh.clicked.connect(app.refresh_all_devices)

        row = QHBoxLayout()
        row.setSpacing(8)
        row.addWidget(self.combo, 1)
        row.addWidget(self.spinner)
        row.addWidget(refresh)

        self.layout.addWidget(QLabel(label))
        self.layout.addLayout(row)
        fill_device_combo(
            self.combo, app.devices.devices,
            app.tr("No authorized device connected"),
        )
        return self

    # ------------------------------------------------------------------
    # sections
    # ------------------------------------------------------------------

    def add_section(self, title, columns=None):
        """Add a titled block; *columns* is a list of ``(label, callable)``."""

        if title:
            heading = QLabel(title)
            heading.setObjectName("SectionTitle")
            self.layout.addWidget(heading)

        if not columns:
            return self

        # a fixed 3-per-row grid keeps every row inside the page width,
        # whatever the window size or the label language
        per_row = 3 if len(columns) > 2 else len(columns)
        grid = QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(8)

        for index, (label, function) in enumerate(columns):
            # "&" is an accelerator marker in Qt, so escape it in labels
            button = QPushButton(label.replace("&", "&&"))
            button.setMinimumHeight(36)
            button.setCursor(Qt.PointingHandCursor)
            button.clicked.connect(function)
            grid.addWidget(button, index // per_row, index % per_row)

        for column in range(per_row):
            grid.setColumnStretch(column, 1)

        self.layout.addLayout(grid)
        return self

    def add_note(self, text, kind="hint"):
        note = QLabel(text)
        note.setWordWrap(True)
        note.setProperty(kind, "true")
        self.layout.addWidget(note)
        return self

    def add_row(self, widgets, stretch_last=True):
        """Horizontal row whose first widget takes the free width."""

        row = QHBoxLayout()
        row.setSpacing(8)
        for index, widget in enumerate(widgets):
            stretch = 1 if index == 0 else 0
            row.addWidget(widget, stretch)
        self.layout.addLayout(row)
        return self

    # ------------------------------------------------------------------
    # output console
    # ------------------------------------------------------------------

    def with_console(self, placeholder="Results will appear here..."):
        self.result_box = QTextEdit()
        self.result_box.setReadOnly(True)
        self.result_box.setPlaceholderText(self.app.tr(placeholder))
        self.layout.addWidget(self.result_box, 1)
        setattr(self.app, self.combo_attr.replace("_combo", "_result_box"),
                self.result_box)
        return self

    def finish(self):

        if self.result_box is None:
            self.layout.addStretch()
        return self.page


def labelled(text, widget):
    """Small vertical ``label + widget`` group used in the new pages."""

    holder = QWidget()
    box = QVBoxLayout(holder)
    box.setContentsMargins(0, 0, 0, 0)
    box.setSpacing(3)
    caption = QLabel(text)
    caption.setProperty("hint", "true")
    box.addWidget(caption)
    box.addWidget(widget)
    return holder
