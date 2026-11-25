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
from PyQt6.QtCore import QMargins, QObject, QPoint, QRect, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QMessageBox,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

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
        assert box.height() == safe.height() - 2 * windows.CARD_MARGIN
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
            assert box.height() == safe.height() - 2 * windows.CARD_MARGIN
            assert len(box.findChildren(QScrollArea, windows.MESSAGE_SCROLL)) == 1
        assert box.width() == portrait_width
    finally:
        box.close()
        _settle()


def test_a_medium_message_unscrolls_when_turning_to_portrait(screen) -> None:  # type: ignore[no-untyped-def]
    """Text that only overflows landscape scrolls there and becomes a plain
    card again in portrait."""
    use, manager = screen
    medium = "\n".join(f"Line {i}: medium message" for i in range(25))
    safe = use(LANDSCAPE)
    box = _show(medium)
    try:
        _inside(box, safe)
        assert _scroll(box) is not None
        safe = use(PORTRAIT)
        manager._refit_all()
        _settle()
        _inside(box, safe)
        assert _scroll(box) is None
    finally:
        box.close()
        _settle()


def test_a_wide_informative_message_stays_inside_the_safe_area(screen) -> None:  # type: ignore[no-untyped-def]
    """QMessageBox wraps against the whole screen width, not the safe area:
    wide informative text must still stay inside the side insets."""
    use, _manager = screen
    safe = use(LANDSCAPE)
    box = QMessageBox(
        QMessageBox.Icon.Warning,
        "Kioku",
        "Short title",
        QMessageBox.StandardButton.Ok,
    )
    box.setInformativeText("A" * 120)
    box.show()
    _settle()
    try:
        _inside(box, safe)
    finally:
        box.close()
        _settle()


@pytest.mark.parametrize("geometry", [PORTRAIT, LANDSCAPE], ids=["portrait", "landscape"])
def test_long_informative_message_scrolls_and_keeps_heading(
    screen, geometry
) -> None:  # type: ignore[no-untyped-def]
    """Long informativeText scrolls inside the safe area while keeping the
    main heading visible and the buttons on screen."""
    use, _manager = screen
    safe = use(geometry)
    box = QMessageBox(
        QMessageBox.Icon.Warning,
        "Kioku",
        "Short heading",
        QMessageBox.StandardButton.Ok,
    )
    box.setInformativeText(LONG)
    box.show()
    _settle()
    try:
        _inside(box, safe)
        assert box.height() == safe.height() - 2 * windows.CARD_MARGIN
        scroll = _scroll(box)
        assert scroll is not None
        info = box.findChild(QLabel, "qt_msgbox_informativelabel")
        label = box.findChild(QLabel, "qt_msgbox_label")
        assert scroll.widget() is info
        assert scroll.verticalScrollBar().maximum() > 0
        assert label is not None and label.height() > 0
        assert safe.contains(QRect(label.mapToGlobal(QPoint(0, 0)), label.size()))
    finally:
        box.close()
        _settle()


def test_small_dialog_is_judged_against_the_safe_area(screen) -> None:  # type: ignore[no-untyped-def]
    """A dialog taller than 70% of the safe area height (260 pt in landscape)
    but under 70% of the whole screen (294 pt) gets a full-screen window,
    not a card that could clip its buttons."""
    use, _manager = screen
    use(LANDSCAPE)
    dialog = QDialog()
    layout = QVBoxLayout(dialog)
    body = QWidget(dialog)
    body.setMinimumHeight(230)
    layout.addWidget(body)
    layout.addWidget(QDialogButtonBox(QDialogButtonBox.StandardButton.Ok, dialog))
    dialog.show()
    _settle()
    try:
        assert windows.WindowManager._bar(dialog) is not None
    finally:
        dialog.close()
        _settle()


def test_card_promoted_to_window_on_rotation_drops_border_and_ignores_recenter(
    screen,
) -> None:  # type: ignore[no-untyped-def]
    """A dialog that fits as a card in portrait becomes a full-screen window
    in landscape: its card border must be removed so _recenter_cards() and
    _refit_card() leave the full-screen window alone."""
    use, manager = screen
    use(PORTRAIT)
    dialog = QDialog()
    layout = QVBoxLayout(dialog)
    body = QWidget(dialog)
    body.setMinimumHeight(230)
    layout.addWidget(body)
    layout.addWidget(QDialogButtonBox(QDialogButtonBox.StandardButton.Ok, dialog))
    dialog.show()
    _settle()
    try:
        assert windows.WindowManager._bar(dialog) is None
        assert windows.WindowManager._border(dialog) is not None
        use(LANDSCAPE)
        manager._refit_all()
        _settle()
        assert windows.WindowManager._bar(dialog) is not None
        assert windows.WindowManager._border(dialog) is None
        assert dialog.geometry() == LANDSCAPE[0]
        manager._recenter_cards()
        manager._refit_card(dialog)
        _settle()
        assert dialog.geometry() == LANDSCAPE[0]
    finally:
        dialog.close()
        _settle()


class _FakeHandle(QObject):
    safeAreaMarginsChanged = pyqtSignal(QMargins)

    def __init__(self, margins: QMargins) -> None:
        super().__init__()
        self._margins = QMargins(margins)

    def safeAreaMargins(self) -> QMargins:
        return QMargins(self._margins)

    def set_margins(self, margins: QMargins) -> None:
        self._margins = QMargins(margins)
        self.safeAreaMarginsChanged.emit(QMargins(margins))


class _FakeMainWindow(QWidget):
    def __init__(self, handle: _FakeHandle) -> None:
        super().__init__()
        self._handle = handle

    def windowHandle(self):  # type: ignore[override]
        return self._handle


def test_safe_area_change_refits_open_cards_and_falls_back_when_mw_hidden(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """safeAreaMarginsChanged arrives separately from availableGeometryChanged:
    open cards refit when the margins update. While the main window is hidden
    (Switch Profile, first run), _screen_insets reads from a visible managed
    full-screen window instead of returning zero."""
    import aqt

    screen_rect = [QRect(PORTRAIT[0])]
    monkeypatch.setattr(windows, "_screen_available", lambda: QRect(screen_rect[0]))
    monkeypatch.setattr(windows, "_rest", None)

    handle = _FakeHandle(PORTRAIT[1])
    mw = _FakeMainWindow(handle)
    mw.show()
    _settle()
    monkeypatch.setattr(aqt, "mw", mw, raising=False)

    manager = windows.WindowManager(app)
    box = _show(SHORT)
    managed: _FakeMainWindow | None = None
    try:
        # Screen switched to landscape before safeAreaMargins updated (stale portrait insets)
        screen_rect[0] = QRect(LANDSCAPE[0])
        manager._refit_all()
        _settle()
        landscape_safe = LANDSCAPE[0].marginsRemoved(LANDSCAPE[1])
        assert not landscape_safe.contains(box.geometry())

        # Margins arrive next: WindowManager refits the open card into the real safe area
        handle.set_margins(LANDSCAPE[1])
        _settle()
        _inside(box, landscape_safe)

        # Hide main window (as Switch Profile does): fall back to a full-screen managed window
        mw.hide()
        assert windows._screen_insets() == QMargins()
        managed = _FakeMainWindow(_FakeHandle(LANDSCAPE[1]))
        windows.TitleBar(managed)
        managed.show()
        _settle()
        assert windows._screen_insets() == LANDSCAPE[1]
    finally:
        box.close()
        if managed is not None:
            managed.close()
        mw.close()
        _settle()
        app.removeEventFilter(manager)
        sip.delete(manager)
