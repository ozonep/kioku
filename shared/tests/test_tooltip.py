"""Anki's tooltip() on a phone: Qt sizes a window to at most 2/3 of the
screen, which cut longer tooltips off; Anki puts it 100 px above the
window's bottom edge, which on an iPhone is on the bottom bar's buttons
(kioku.patches)."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import aqt
import aqt.utils
import pytest
from aqt.qt import QApplication, QMargins, QPoint, QWidget

from kioku import patches, windows

app = QApplication.instance() or QApplication([])


class Progress:
    def timer(self, *args, **kwargs) -> None:  # type: ignore[no-untyped-def]
        return None


@pytest.fixture(scope="module", autouse=True)
def patched() -> None:
    # once: a second apply() would wrap tooltip() in itself
    patches.apply()


def test_tooltip_fits_the_screen() -> None:
    mw = QWidget()
    mw.progress = Progress()  # type: ignore[attr-defined]
    aqt.mw = mw  # type: ignore[assignment]
    try:
        screen = app.primaryScreen().availableGeometry()
        aqt.utils.tooltip("word " * 200, parent=mw)
        label = aqt.utils._tooltipLabel
        assert label.wordWrap()
        assert screen.left() + 8 <= label.x()
        assert label.x() + label.width() <= screen.left() + screen.width() - 8

        aqt.utils.tooltip("short", parent=mw)
        label = aqt.utils._tooltipLabel
        assert not label.wordWrap()
        assert label.width() == label.sizeHint().width()
    finally:
        aqt.utils.closeTooltip()
        aqt.mw = None  # type: ignore[assignment]


@pytest.mark.parametrize("bar_height", [92, 111], ids=["landscape bar", "portrait bar"])
def test_tooltip_stays_above_the_bottom_bar_and_in_the_safe_area(
    monkeypatch: pytest.MonkeyPatch, bar_height: int
) -> None:
    """The review screen's bottom bar reaches into the home indicator's
    area: 111 points tall in portrait on an iPhone Air, 92 in landscape.
    "Card buried" covered its answer buttons, and a tap on them only
    closed the tooltip. In landscape it also started in the strip beside
    the Dynamic Island."""
    insets = QMargins(68, 20, 68, 29)  # an iPhone Air in landscape
    monkeypatch.setattr(windows, "_screen_insets", lambda: QMargins(insets))
    screen = app.primaryScreen().availableGeometry()
    mw = QWidget()
    mw.progress = Progress()  # type: ignore[attr-defined]
    mw.setGeometry(screen)
    mw.bottomWeb = QWidget(mw)  # type: ignore[attr-defined]
    mw.bottomWeb.setGeometry(0, mw.height() - bar_height, mw.width(), bar_height)
    mw.show()
    aqt.mw = mw  # type: ignore[assignment]
    try:
        aqt.utils.tooltip("Card buried.", parent=mw)
        label = aqt.utils._tooltipLabel
        bar_top = mw.bottomWeb.mapToGlobal(QPoint(0, 0)).y()
        assert label.y() + label.height() <= bar_top - 8
        safe = screen.marginsRemoved(insets)
        assert safe.left() + 8 <= label.x()
        assert safe.top() + 8 <= label.y()

        # Anki "hides" the bar by shrinking it to 1 px: Anki's place again
        mw.bottomWeb.setGeometry(0, mw.height() - 1, mw.width(), 1)
        aqt.utils.tooltip("Card buried.", parent=mw)
        label = aqt.utils._tooltipLabel
        assert label.y() == mw.mapToGlobal(QPoint(0, mw.height() - 100)).y()
    finally:
        aqt.utils.closeTooltip()
        mw.close()
        aqt.mw = None  # type: ignore[assignment]
