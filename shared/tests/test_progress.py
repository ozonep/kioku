"""kioku.windows: Anki's progress window (sync, Check Media) gets a Cancel
button, so it shows as a small card instead of filling the screen; Cancel
asks the task to stop as the desktop window's close button does. The card
is placed again when the Anki fork adds to it, so Cancel stays on the
screen."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from aqt import progress  # before the QApplication: aqt.qt imports Qt WebEngine
from PyQt6 import sip
from PyQt6.QtCore import QMargins, QPoint, QRect
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QProgressBar,
    QVBoxLayout,
)

from kioku import windows
from kioku.windows import _add_cancel, _is_small_dialog

app = QApplication.instance() or QApplication([])


class ProgressDialog(QDialog):
    """Anki's aqt.progress.ProgressDialog: a label and a bar; closing it
    only sets wantCancel."""

    def __init__(self) -> None:
        super().__init__()
        self.wantCancel = False
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Syncing..."))
        layout.addWidget(QProgressBar())

    def closeEvent(self, evt) -> None:  # type: ignore[no-untyped-def]
        self.wantCancel = True
        evt.ignore()


def test_progress_becomes_a_card_with_cancel() -> None:
    avail = QRect(0, 0, 430, 900)
    dialog = ProgressDialog()
    assert not _is_small_dialog(dialog, avail)
    _add_cancel(dialog)
    assert _is_small_dialog(dialog, avail)
    dialog.show()
    box = dialog.findChild(QDialogButtonBox)
    box.button(QDialogButtonBox.StandardButton.Cancel).click()
    assert dialog.wantCancel
    assert dialog.isVisible()  # stays until the task stops


def _settle() -> None:
    for _ in range(10):
        app.processEvents()


def _bars(count: int) -> list[progress.ProgressBarUpdate]:
    return [
        progress.ProgressBarUpdate(label=f"Preset {i} (1234 reviews)", value=3, max=10)
        for i in range(count)
    ]


# an iPhone Air, in points: the screen and its safe area insets
AIR = [
    (QRect(0, 0, 420, 912), QMargins(0, 68, 0, 34)),
    (QRect(0, 0, 912, 420), QMargins(68, 20, 68, 29)),
]


@pytest.mark.parametrize("screen,insets", AIR, ids=["portrait", "landscape"])
def test_progress_card_stays_on_screen_as_the_fork_adds_to_it(
    monkeypatch: pytest.MonkeyPatch, screen: QRect, insets: QMargins
) -> None:
    """The Anki fork's Optimize All Presets adds to its progress window after
    Kioku placed it: a status line that doesn't wrap, a bar for each preset
    being optimized and a log with an 80-character minimum width. On an
    iPhone Air the card grew to 641 points wide (or past the bottom, in
    landscape) and took Cancel off the screen. When a preset is done, the
    window shrinks to its contents, which left it at the screen's edge.
    The card stays inside the safe area: in landscape, three presets'
    bars took it into the home indicator's strip."""
    monkeypatch.setattr(windows, "_screen_available", lambda: QRect(screen))
    monkeypatch.setattr(windows, "_screen_insets", lambda: QMargins(insets))
    monkeypatch.setattr(windows, "_rest", None)  # set by WindowManager
    safe = screen.marginsRemoved(insets)
    manager = windows.WindowManager(app)
    dialog = progress.ProgressDialog(None)
    try:
        dialog.setMinimumWidth(520)  # as ProgressManager.start()
        dialog.show()
        _settle()
        cancel = dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Cancel)

        def check(step: str) -> None:
            _settle()
            rect = dialog.geometry()
            assert safe.contains(rect), (step, rect)
            assert safe.contains(QRect(cancel.mapToGlobal(QPoint(0, 0)), cancel.size())), step
            assert abs(rect.center().x() - safe.center().x()) <= 1, (step, rect)

        check("shown")
        dialog.form.label.setText(
            "Optimizing presets: 1234/5000 (24%) | elapsed: 2m 05s | remaining: 6m 40s"
        )
        dialog.set_multi_progress_bars(_bars(2))
        check("status and bars")
        dialog.set_multi_progress_bars(_bars(3))
        check("three presets")
        dialog.set_details_text("[SKIP] 1 Presets with 0 reviews")
        check("log")
        dialog.set_multi_progress_bars(_bars(1))
        check("a preset done")
    finally:
        dialog.cancel()
        _settle()
        app.removeEventFilter(manager)
        sip.delete(manager)
