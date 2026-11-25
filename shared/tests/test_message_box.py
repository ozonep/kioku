"""kioku.windows: message boxes are cards inside the screen's safe area,
clear of the status bar and Dynamic Island, the home indicator and, in
landscape, the strips at the sides. Text too long for the screen scrolls
above the buttons: QMessageBox fixes its own size, so a long message ran
past the bottom edge and took its buttons with it."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6 import sip
from PyQt6.QtCore import QMargins, QPoint, QRect
from PyQt6.QtWidgets import QApplication, QMessageBox, QScrollArea

from kioku import windows

app = QApplication.instance() or QApplication([])

# an iPhone Air, in points: the screen and its safe area insets
PORTRAIT = (QRect(0, 0, 420, 912), QMargins(0, 68, 0, 34))
LANDSCAPE = (QRect(0, 0, 912, 420), QMargins(68, 20, 68, 29))
SHORT = "Delete the deck “Japanese::Core”?"
LONG = "\n".join(f"Line {i}: a long sync or add-on message" for i in range(70))


def _settle() -> None:
    for _ in range(10):
        app.processEvents()


@pytest.fixture
def screen(monkeypatch: pytest.MonkeyPatch):  # type: ignore[no-untyped-def]
    """Sets the screen (and its insets) the window manager sees."""
    current = list(PORTRAIT)
    monkeypatch.setattr(windows, "_screen_available", lambda: QRect(current[0]))
    monkeypatch.setattr(windows, "_screen_insets", lambda: QMargins(current[1]))
    monkeypatch.setattr(windows, "_rest", None)  # set by WindowManager
    manager = windows.WindowManager(app)

    def use(geometry: tuple[QRect, QMargins]) -> QRect:
        current[:] = geometry
        return geometry[0].marginsRemoved(geometry[1])

    yield use, manager
    app.removeEventFilter(manager)
    sip.delete(manager)


def _show(text: str) -> QMessageBox:
    box = QMessageBox(
        QMessageBox.Icon.Question,
        "Kioku",
        text,
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
    )
    box.show()
    _settle()
    return box


def _inside(box: QMessageBox, safe: QRect) -> None:
    assert safe.contains(box.geometry()), box.geometry()
    for button in box.buttons():
        rect = QRect(button.mapToGlobal(QPoint(0, 0)), button.size())
        assert safe.contains(rect), (button.text(), rect)


def _scroll(box: QMessageBox) -> QScrollArea | None:
    return box.findChild(QScrollArea, windows.MESSAGE_SCROLL)


@pytest.mark.parametrize("geometry", [PORTRAIT, LANDSCAPE], ids=["portrait", "landscape"])
def test_a_short_message_is_a_card_in_the_safe_area(screen, geometry) -> None:  # type: ignore[no-untyped-def]
    use, _manager = screen
    safe = use(geometry)
    box = _show(SHORT)
    try:
        _inside(box, safe)
        assert abs(box.geometry().center().x() - safe.center().x()) <= 1
        assert _scroll(box) is None
    finally:
        box.close()
        _settle()


@pytest.mark.parametrize("geometry", [PORTRAIT, LANDSCAPE], ids=["portrait", "landscape"])
def test_a_long_message_scrolls_above_its_buttons(screen, geometry) -> None:  # type: ignore[no-untyped-def]
    use, _manager = screen
    safe = use(geometry)
    box = _show(LONG)
    try:
        _inside(box, safe)
        scroll = _scroll(box)
        assert scroll is not None
        assert scroll.widget() is box.findChild(type(scroll.widget()), "qt_msgbox_label")
        assert scroll.verticalScrollBar().maximum() > 0  # the rest is a drag away
    finally:
        box.close()
        _settle()


def test_a_long_message_fits_again_after_turning_the_phone(screen) -> None:  # type: ignore[no-untyped-def]
    """A rotation fits the box again (WindowManager._refit_all): the text
    goes back into the box to be measured, then scrolls if it must."""
    use, manager = screen
    use(PORTRAIT)
    box = _show(LONG)
    try:
        portrait_width = box.width()
        for geometry in (LANDSCAPE, PORTRAIT):
            safe = use(geometry)
            manager._refit_all()
            _settle()
            _inside(box, safe)
            assert len(box.findChildren(QScrollArea, windows.MESSAGE_SCROLL)) == 1
        assert box.width() == portrait_width
    finally:
        box.close()
        _settle()
