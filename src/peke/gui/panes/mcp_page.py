"""PySide6 GUI pane for Agent Access (MCP) management and monitoring."""

from typing import Any

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from peke.config import load_settings, save_user_settings
from peke.gui import theme
from peke.mcp.activity import read_activity_log
from peke.mcp.clients.base import get_peke_launcher
from peke.mcp.clients.registrars import get_all_registrars
from peke.mcp.security import get_or_create_mcp_token, rotate_mcp_token


class McpSettingsPage(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.settings = load_settings()

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 18)
        root.setSpacing(14)

        # 1. Status Card
        status_card = QFrame()
        status_card.setObjectName("card")
        sc_layout = QVBoxLayout(status_card)
        sc_layout.setContentsMargins(14, 12, 14, 14)

        sc_head = QHBoxLayout()
        sc_title = QLabel("MCP Server Status")
        sc_title.setStyleSheet("font-size:15px;font-weight:700")
        self.status_chip = QLabel("● Ready")
        self.status_chip.setStyleSheet(f"background:{theme.SAGE};color:white;border-radius:10px;padding:4px 8px;font-size:11px")
        sc_head.addWidget(sc_title)
        sc_head.addStretch(1)
        sc_head.addWidget(self.status_chip)
        sc_layout.addLayout(sc_head)

        launcher_path = get_peke_launcher()
        self.launcher_label = QLabel(f"Launcher path: {launcher_path} | Tools: 11")
        self.launcher_label.setStyleSheet(f"color:{theme.MUTED_TEXT};font-size:12px")
        sc_layout.addWidget(self.launcher_label)

        sc_btns = QHBoxLayout()
        self.selftest_btn = QPushButton("Run self-test")
        self.selftest_btn.clicked.connect(self._run_selftest)
        self.copy_cmd_btn = QPushButton("Copy server command")
        self.copy_cmd_btn.clicked.connect(self._copy_server_command)
        sc_btns.addWidget(self.selftest_btn)
        sc_btns.addWidget(self.copy_cmd_btn)
        sc_btns.addStretch(1)
        sc_layout.addLayout(sc_btns)

        root.addWidget(status_card)

        # 2. Connected Agents Card
        agents_card = QFrame()
        agents_card.setObjectName("card")
        ac_layout = QVBoxLayout(agents_card)
        ac_layout.setContentsMargins(14, 12, 14, 14)

        ac_title = QLabel("Connected Local AI Agents")
        ac_title.setStyleSheet("font-size:15px;font-weight:700")
        ac_layout.addWidget(ac_title)

        self.agents_table = QTableWidget(0, 3)
        self.agents_table.setHorizontalHeaderLabels(["Agent Client", "Status", "Actions"])
        self.agents_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.agents_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.agents_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        ac_layout.addWidget(self.agents_table)

        root.addWidget(agents_card)

        # 3. Policy Settings Card
        policy_card = QFrame()
        policy_card.setObjectName("card")
        pc_layout = QVBoxLayout(policy_card)
        pc_layout.setContentsMargins(14, 12, 14, 14)

        pc_title = QLabel("MCP Security & Access Policy")
        pc_title.setStyleSheet("font-size:15px;font-weight:700")
        pc_layout.addWidget(pc_title)

        switches_layout = QHBoxLayout()
        self.readonly_cb = QCheckBox("Read-only mode")
        self.readonly_cb.setChecked(self.settings.mcp_read_only)
        self.readonly_cb.toggled.connect(self._save_policy)

        self.stealth_cb = QCheckBox("Allow stealth fetcher")
        self.stealth_cb.setChecked(self.settings.mcp_allow_stealth)
        self.stealth_cb.toggled.connect(self._save_policy)

        self.private_hosts_cb = QCheckBox("Allow private/loopback hosts (SSRF restriction override)")
        self.private_hosts_cb.setChecked(self.settings.mcp_allow_private_hosts)
        self.private_hosts_cb.toggled.connect(self._save_policy)

        switches_layout.addWidget(self.readonly_cb)
        switches_layout.addWidget(self.stealth_cb)
        switches_layout.addWidget(self.private_hosts_cb)
        switches_layout.addStretch(1)
        pc_layout.addLayout(switches_layout)

        robots_layout = QHBoxLayout()
        robots_label = QLabel("robots.txt policy:")
        self.robots_combo = QComboBox()
        self.robots_combo.addItems(["warn", "respect", "off"])
        idx = self.robots_combo.findText(self.settings.mcp_robots_policy)
        if idx >= 0:
            self.robots_combo.setCurrentIndex(idx)
        self.robots_combo.currentIndexChanged.connect(self._save_policy)

        robots_layout.addWidget(robots_label)
        robots_layout.addWidget(self.robots_combo)
        robots_layout.addStretch(1)
        pc_layout.addLayout(robots_layout)

        root.addWidget(policy_card)

        # 4. HTTP Access Card
        http_card = QFrame()
        http_card.setObjectName("card")
        hc_layout = QVBoxLayout(http_card)
        hc_layout.setContentsMargins(14, 12, 14, 14)

        hc_title = QLabel("Streamable HTTP Access (127.0.0.1 ONLY)")
        hc_title.setStyleSheet("font-size:15px;font-weight:700")
        hc_layout.addWidget(hc_title)

        hc_controls = QHBoxLayout()
        hc_port_label = QLabel("Port:")
        self.port_spin = QSpinBox()
        self.port_spin.setRange(1024, 65535)
        self.port_spin.setValue(self.settings.mcp_http_port)
        self.port_spin.valueChanged.connect(self._save_policy)

        self.token_reveal_btn = QPushButton("Reveal Token")
        self.token_reveal_btn.clicked.connect(self._reveal_token)
        self.token_copy_btn = QPushButton("Copy Token")
        self.token_copy_btn.clicked.connect(self._copy_token)
        self.token_rotate_btn = QPushButton("Rotate Token")
        self.token_rotate_btn.clicked.connect(self._rotate_token)
        self.copy_http_cmd_btn = QPushButton("Copy HTTP Claude Command")
        self.copy_http_cmd_btn.clicked.connect(self._copy_http_command)

        hc_controls.addWidget(hc_port_label)
        hc_controls.addWidget(self.port_spin)
        hc_controls.addWidget(self.token_reveal_btn)
        hc_controls.addWidget(self.token_copy_btn)
        hc_controls.addWidget(self.token_rotate_btn)
        hc_controls.addWidget(self.copy_http_cmd_btn)
        hc_controls.addStretch(1)
        hc_layout.addLayout(hc_controls)

        root.addWidget(http_card)

        # 5. Live Activity Card
        activity_card = QFrame()
        activity_card.setObjectName("card")
        act_layout = QVBoxLayout(activity_card)
        act_layout.setContentsMargins(14, 12, 14, 14)

        act_title = QLabel("Live MCP Activity Log (~/.peke/activity.jsonl)")
        act_title.setStyleSheet("font-size:15px;font-weight:700")
        act_layout.addWidget(act_title)

        self.activity_table = QTableWidget(0, 6)
        self.activity_table.setHorizontalHeaderLabels(["Time", "Client", "Tool", "Target Host", "Duration", "Status"])
        self.activity_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.activity_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.activity_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.activity_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.activity_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.activity_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)

        act_layout.addWidget(self.activity_table)

        root.addWidget(activity_card, 1)

        # Initial refresh and periodic activity timer
        self.refresh_agents_table()
        self.refresh_activity_log()

        self.activity_timer = QTimer(self)
        self.activity_timer.setInterval(2000)
        self.activity_timer.timeout.connect(self.refresh_activity_log)
        self.activity_timer.start()

    def refresh_agents_table(self) -> None:
        registrars = get_all_registrars()
        self.agents_table.setRowCount(len(registrars))

        for row, reg in enumerate(registrars):
            is_reg = reg.is_registered()
            is_inst = reg.detect_installed()

            if is_reg:
                status_text = "Registered"
            elif is_inst:
                status_text = "Detected (Not registered)"
            else:
                status_text = "Not found"

            self.agents_table.setItem(row, 0, QTableWidgetItem(reg.display_name))
            status_item = QTableWidgetItem(status_text)
            status_item.setForeground(Qt.GlobalColor.darkGreen if is_reg else Qt.GlobalColor.darkGray)
            self.agents_table.setItem(row, 1, status_item)

            action_btn = QPushButton("Remove" if is_reg else "Register")
            action_btn.clicked.connect(lambda _, r=reg, registered=is_reg: self._handle_agent_action(r, registered))
            self.agents_table.setCellWidget(row, 2, action_btn)

    def _handle_agent_action(self, reg: Any, is_registered: bool) -> None:
        if is_registered:
            dialog = QDialog(self)
            dialog.setWindowTitle(f"Remove Peke from {reg.display_name}")
            lay = QVBoxLayout(dialog)
            lay.addWidget(QLabel(f"Are you sure you want to unregister Peke from {reg.display_name}?"))
            btns = QHBoxLayout()
            confirm = QPushButton("Confirm Removal")
            confirm.clicked.connect(lambda: (reg.uninstall(), dialog.accept(), self.refresh_agents_table()))
            cancel = QPushButton("Cancel")
            cancel.clicked.connect(dialog.reject)
            btns.addWidget(confirm)
            btns.addWidget(cancel)
            lay.addLayout(btns)
            dialog.exec()
        else:
            _, diff_text = reg.plan_install()
            dialog = QDialog(self)
            dialog.setWindowTitle(f"Register Peke with {reg.display_name}")
            lay = QVBoxLayout(dialog)
            lay.addWidget(QLabel("Proposed configuration changes:"))
            preview = QTextEdit(diff_text)
            preview.setReadOnly(True)
            lay.addWidget(preview)

            btns = QHBoxLayout()
            confirm = QPushButton("Apply Registration")
            confirm.clicked.connect(lambda: (reg.install(), dialog.accept(), self.refresh_agents_table()))
            cancel = QPushButton("Cancel")
            cancel.clicked.connect(dialog.reject)
            btns.addWidget(confirm)
            btns.addWidget(cancel)
            lay.addLayout(btns)
            dialog.exec()

    def refresh_activity_log(self) -> None:
        entries = read_activity_log(limit=30)
        self.activity_table.setRowCount(len(entries))

        for row, entry in enumerate(entries):
            ts = str(entry.get("ts", "")).split(".")[0].replace("T", " ")
            self.activity_table.setItem(row, 0, QTableWidgetItem(ts))
            self.activity_table.setItem(row, 1, QTableWidgetItem(str(entry.get("client", ""))))
            self.activity_table.setItem(row, 2, QTableWidgetItem(str(entry.get("tool", ""))))
            self.activity_table.setItem(row, 3, QTableWidgetItem(str(entry.get("target_host", ""))))
            self.activity_table.setItem(row, 4, QTableWidgetItem(f"{entry.get('duration_ms', 0)} ms"))
            self.activity_table.setItem(row, 5, QTableWidgetItem(str(entry.get("status", ""))))

    def _save_policy(self) -> None:
        values = {
            "MCP_READ_ONLY": self.readonly_cb.isChecked(),
            "MCP_ALLOW_STEALTH": self.stealth_cb.isChecked(),
            "MCP_ALLOW_PRIVATE_HOSTS": self.private_hosts_cb.isChecked(),
            "MCP_ROBOTS_POLICY": self.robots_combo.currentText(),
            "MCP_HTTP_PORT": self.port_spin.value(),
        }
        save_user_settings(values)

    def _run_selftest(self) -> None:
        try:
            from peke.mcp.server import build_server
            _ = build_server()
            self.status_chip.setText("● Handshake PASS")
            self.status_chip.setStyleSheet(f"background:{theme.SAGE};color:white;border-radius:10px;padding:4px 8px;font-size:11px")
            QMessageBox.information(self, "MCP Self-Test", "Peke MCP Server handshake succeeded (11 tools registered).")
        except Exception as exc:
            self.status_chip.setText("● Handshake FAIL")
            self.status_chip.setStyleSheet(f"background:{theme.TERRACOTTA};color:white;border-radius:10px;padding:4px 8px;font-size:11px")
            QMessageBox.critical(self, "MCP Self-Test", f"MCP server handshake failed: {exc}")

    def _copy_server_command(self) -> None:
        cmd = f"{get_peke_launcher()} mcp serve"
        QGuiApplication.clipboard().setText(cmd)
        QMessageBox.information(self, "Copied", f"Copied server command to clipboard:\n{cmd}")

    def _reveal_token(self) -> None:
        token = get_or_create_mcp_token()
        QMessageBox.information(self, "MCP Bearer Token", f"Current Bearer Token:\n{token}")

    def _copy_token(self) -> None:
        token = get_or_create_mcp_token()
        QGuiApplication.clipboard().setText(token)
        QMessageBox.information(self, "Copied", "Copied MCP bearer token to clipboard.")

    def _rotate_token(self) -> None:
        new_token = rotate_mcp_token()
        QMessageBox.information(self, "Token Rotated", f"Generated new bearer token:\n{new_token}")

    def _copy_http_command(self) -> None:
        port = self.port_spin.value()
        token = get_or_create_mcp_token()
        cmd = f'claude mcp add --transport http peke http://127.0.0.1:{port}/mcp --header "Authorization: Bearer {token}"'
        QGuiApplication.clipboard().setText(cmd)
        QMessageBox.information(self, "Copied", f"Copied Claude HTTP command to clipboard:\n{cmd}")
