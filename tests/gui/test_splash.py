"""Optional GUI splash tests; skipped when Qt extras are not installed."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
pytest.importorskip("PySide6")
pytest.importorskip("pytestqt")

from peke.gui.splash import SplashScreen  # noqa: E402


def test_splash_shows_final_frame_for_reduced_motion(qtbot):
    splash = SplashScreen(reduced_motion=True)
    qtbot.addWidget(splash)
    splash.show()
    assert "Clean JSON Formatted" in splash.label.text()


def test_splash_closes_on_key(qtbot):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    splash = SplashScreen(reduced_motion=True)
    qtbot.addWidget(splash)
    splash.show()
    QTest.keyClick(splash, Qt.Key.Key_Space)
    assert not splash.isVisible()
