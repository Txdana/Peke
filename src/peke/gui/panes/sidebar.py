"""Collapsible navigation rail for Peke."""
from PySide6.QtCore import QEasingCurve, QPropertyAnimation
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget
from peke.banner import rea_available
from peke.config import load_settings
from peke.gui import theme
from peke.gui.widgets.icons import svg_icon
from peke.gui.widgets.vram_card import VramCard

NAV_ITEMS = [("Target Inspection (REA)", "target"), ("Stealth Scraper", "scraper"), ("Model Pipeline (llama.cpp)", "model"), ("JSON Schemas", "schema")]


class Sidebar(QFrame):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("sidebar")
        self.setMinimumWidth(64)
        self.setMaximumWidth(240)
        self.resize(240, self.height())
        self.collapsed = False
        self.buttons: list[QPushButton] = []
        self.animation = QPropertyAnimation(self, b"maximumWidth", self)
        self.animation.setDuration(180)
        self.animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self.setStyleSheet(f"QFrame#sidebar {{background:{theme.SIDEBAR}; border-radius:20px;}}")
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 18, 14, 14)
        root.setSpacing(12)
        head = QHBoxLayout()
        self.brand = QLabel("Peke")
        self.brand.setStyleSheet("font-family:'Fraunces',serif;font-size:23px;font-weight:700")
        rea_found = rea_available(load_settings().rea_command)
        self.chip = QLabel("●  REA CLI Found" if rea_found else "●  REA CLI Missing")
        self.chip.setStyleSheet(f"background:{theme.SAGE if rea_found else theme.MUTED_TEXT};color:white;border-radius:10px;padding:4px 7px;font-size:10px")
        head.addWidget(self.brand)
        head.addStretch(1)
        head.addWidget(self.chip)
        root.addLayout(head)
        root.addSpacing(14)
        self.nav_container = QWidget()
        nav_layout = QVBoxLayout(self.nav_container)
        nav_layout.setContentsMargins(0, 0, 0, 0)
        nav_layout.setSpacing(6)
        for index, (label, icon) in enumerate(NAV_ITEMS):
            button = QPushButton(f"  {label}")
            button.setObjectName("navButton")
            button.setCheckable(True)
            button.setChecked(index == 0)
            button.setIcon(svg_icon(icon, theme.TERRACOTTA if index == 0 else theme.MUTED_TEXT))
            button.setIconSize(button.iconSize().expandedTo(button.iconSize()))
            button.setMinimumHeight(44)
            button.setAccessibleName(label)
            self.buttons.append(button)
            nav_layout.addWidget(button)
        nav_layout.addStretch(1)
        root.addWidget(self.nav_container, 1)
        self.vram = VramCard()
        root.addWidget(self.vram)
        self.collapse_button = QPushButton("‹  Collapse sidebar")
        self.collapse_button.setAccessibleName("Collapse sidebar")
        self.collapse_button.clicked.connect(self.toggle_collapsed)
        root.addWidget(self.collapse_button)

    def toggle_collapsed(self) -> None:
        self.collapsed = not self.collapsed
        start, end = (self.maximumWidth(), 64) if self.collapsed else (self.maximumWidth(), 240)
        self.animation.stop()
        self.animation.setStartValue(start)
        self.animation.setEndValue(end)
        self.animation.start()
        self.collapse_button.setText("›" if self.collapsed else "‹  Collapse sidebar")
        self.collapse_button.setAccessibleName("Expand sidebar" if self.collapsed else "Collapse sidebar")
        self.brand.setVisible(not self.collapsed)
        self.chip.setVisible(not self.collapsed)
        self.vram.setVisible(not self.collapsed)
        for button, (label, icon) in zip(self.buttons, NAV_ITEMS):
            button.setText("" if self.collapsed else f"  {label}")
            button.setToolTip(label if self.collapsed else "")
            button.setAccessibleName(label)
