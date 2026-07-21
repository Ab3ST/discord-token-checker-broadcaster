from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QHBoxLayout, QPushButton, QTextEdit,
    QProgressBar, QStackedWidget, QMenu
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QAction, QTextCursor, QTextCharFormat, QColor
from PyQt6.QtWidgets import QGraphicsBlurEffect
from src.ui.components.empty_state import EmptyStateWidget
from src.ui.components.notification import NotificationWidget
from src.ui.styles import BUTTON_PRIMARY, BUTTON_SECONDARY, BUTTON_DANGER, PROGRESS_BAR, LOG_TERMINAL, LOG_COLORS
from src.core.database import Database
from src.ui.dialogs.account_selection import AccountSelectionDialog
from src.ui.dialogs.compose_message import ComposeMessageDialog
from src.workers.broadcast import BroadcastWorker
from src.ui.dialogs.broadcast_settings import BroadcastSettingsDialog


class ActionsPage(QWidget):
    def __init__(self):
        super().__init__()
        self.db = Database()
        self.has_logs = False
        self.current_action = None
        self.selected_accounts = []
        self.selected_proxies = []
        self.broadcast = None
        self.is_broadcasting = False
        self._message = ""
        self._attachments = []
        self.notification = None
        self.live_accounts = {}
        self._pending_status = {}
        self._status_timer = QTimer(self)
        self._status_timer.setSingleShot(True)
        self._status_timer.setInterval(70)
        self._status_timer.timeout.connect(self._flush_account_status)
        self.setup_ui()
        self.load_settings()

    def showEvent(self, event):
        super().showEvent(event)
        if not self.notification:
            self.notification = NotificationWidget(self.window())

    def _notify(self, message: str):
        if self.notification:
            self.notification.show_notification(message)

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(16)

        controls_layout = QHBoxLayout()
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.setSpacing(8)

        self.btn_select_accounts = self._make_button("Выбрать аккаунты")
        self.btn_select_accounts.clicked.connect(self._select_accounts)
        controls_layout.addWidget(self.btn_select_accounts)

        btn_settings = self._make_button("Настройки")
        btn_settings.clicked.connect(self._open_settings)
        controls_layout.addWidget(btn_settings)

        controls_layout.addStretch()

        self.actions_btn = QPushButton("Действие")
        self.actions_btn.setFixedHeight(40)
        self.actions_btn.setMinimumWidth(110)
        self.actions_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.actions_btn.setFont(QFont("Segoe UI", 9, QFont.Weight.DemiBold))
        self.actions_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(25, 25, 28, 0.8);
                color: rgba(255, 255, 255, 0.5);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 10px;
                padding: 0 16px;
            }
            QPushButton:hover {
                background-color: rgba(35, 35, 38, 0.9);
                color: rgba(255, 255, 255, 0.8);
                border-color: rgba(255, 255, 255, 0.15);
            }
            QPushButton:pressed { background-color: rgba(20, 20, 23, 0.95); }
            QPushButton::menu-indicator { image: none; width: 0px; }
        """)
        self._create_actions_menu()
        controls_layout.addWidget(self.actions_btn)

        self.launch_btn = self._make_button("Запуск", primary=True)
        self.launch_btn.clicked.connect(self._on_launch_clicked)
        controls_layout.addWidget(self.launch_btn)

        main_layout.addLayout(controls_layout)

        progress_container = QWidget()
        progress_container.setStyleSheet("background: transparent; border: none;")
        progress_layout = QVBoxLayout(progress_container)
        progress_layout.setContentsMargins(0, 0, 0, 0)
        progress_layout.setSpacing(4)

        self.progress_label = QLabel("")
        self.progress_label.setFont(QFont("Segoe UI", 8))
        self.progress_label.setStyleSheet("color: #555555; background: transparent; border: none;")
        progress_layout.addWidget(self.progress_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(6)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet(PROGRESS_BAR)
        progress_layout.addWidget(self.progress_bar)

        self.progress_container = progress_container
        self.progress_container.setVisible(False)
        main_layout.addWidget(self.progress_container)

        terminal_container = QWidget()
        terminal_container.setStyleSheet("""
            QWidget {
                background-color: rgba(25, 25, 28, 0.8);
                border-radius: 20px;
                border: 1px solid rgba(255, 255, 255, 0.08);
            }
        """)

        terminal_layout = QVBoxLayout(terminal_container)
        terminal_layout.setContentsMargins(24, 18, 24, 18)
        terminal_layout.setSpacing(12)

        terminal_header = QLabel("Консоль логов")
        terminal_header.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        terminal_header.setStyleSheet("color: rgba(255, 255, 255, 0.9); background: transparent; border: none;")
        terminal_layout.addWidget(terminal_header)

        self.terminal_stack = QStackedWidget()
        self.terminal_stack.setStyleSheet("background: transparent; border: none;")

        self.empty_state = EmptyStateWidget()
        self.terminal_stack.addWidget(self.empty_state)

        overlay_container = QWidget()
        overlay_container.setStyleSheet("background: transparent; border: none;")
        overlay_layout = QVBoxLayout(overlay_container)
        overlay_layout.setContentsMargins(0, 0, 0, 0)
        overlay_layout.setSpacing(0)

        self.video_background = EmptyStateWidget()
        self.blur_effect = QGraphicsBlurEffect()
        self.blur_effect.setBlurRadius(15)
        self.video_background.setGraphicsEffect(self.blur_effect)
        overlay_layout.addWidget(self.video_background)

        self.overlay_log_terminal = QTextEdit(overlay_container)
        self.overlay_log_terminal.setReadOnly(True)
        self.overlay_log_terminal.setFont(QFont("Consolas", 9))
        self.overlay_log_terminal.setStyleSheet("""
            QTextEdit {
                background-color: transparent;
                color: #3d9970;
                border: none;
                padding: 0;
            }
            QScrollBar:vertical { background-color: transparent; width: 6px; }
            QScrollBar::handle:vertical {
                background-color: rgba(255, 255, 255, 0.15);
                border-radius: 3px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover { background-color: rgba(255, 255, 255, 0.25); }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """)
        self.overlay_log_terminal.raise_()

        def position_overlay_log(event):
            size = overlay_container.size()
            self.overlay_log_terminal.setGeometry(0, 0, size.width(), size.height())

        overlay_container.resizeEvent = position_overlay_log
        self.terminal_stack.addWidget(overlay_container)

        self.log_terminal = QTextEdit()
        self.log_terminal.setReadOnly(True)
        self.log_terminal.setFont(QFont("Consolas", 9))
        self.log_terminal.setStyleSheet(LOG_TERMINAL)
        self.terminal_stack.addWidget(self.log_terminal)

        terminal_layout.addWidget(self.terminal_stack)
        main_layout.addWidget(terminal_container)

    def _make_button(self, text, primary=False):
        btn = QPushButton(text)
        btn.setFixedHeight(40)
        btn.setMinimumWidth(120 if primary else 100)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFont(QFont("Segoe UI", 9, QFont.Weight.DemiBold if primary else QFont.Weight.Normal))
        btn.setStyleSheet(BUTTON_PRIMARY if primary else BUTTON_SECONDARY)
        return btn

    def _open_settings(self):
        dialog = BroadcastSettingsDialog(self)
        dialog.exec()

    def load_settings(self):
        show_empty_video = self.db.get("show_empty_video", True)
        self.empty_state.set_video_enabled(show_empty_video)
        self.video_background.set_video_enabled(show_empty_video)

    def _create_actions_menu(self):
        self.actions_menu = QMenu(self)
        self.actions_menu.setStyleSheet("""
            QMenu {
                background-color: rgba(20, 20, 23, 0.95);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 10px;
                padding: 6px;
            }
            QMenu::item { color: rgba(255, 255, 255, 0.6); padding: 10px 24px; border-radius: 6px; }
            QMenu::item:selected { background-color: rgba(35, 35, 38, 0.9); color: rgba(255, 255, 255, 0.95); }
            QMenu::separator { height: 1px; background-color: rgba(255, 255, 255, 0.06); margin: 6px 0; }
        """)

        self.broadcast_action = QAction("Рассылка по каналам", self)
        self.broadcast_action.triggered.connect(lambda: self._select_action("broadcast", "Рассылка по каналам"))
        self.actions_menu.addAction(self.broadcast_action)

        self.actions_menu.addSeparator()

        self.actions_btn.setMenu(self.actions_menu)

    def _select_action(self, action_type, action_name):
        if self.current_action == action_type:
            self.current_action = None
            self.broadcast_action.setText("Рассылка по каналам")
            self.actions_btn.setText("Действие")
        else:
            self.current_action = action_type
            self.broadcast_action.setText("• Рассылка по каналам" if action_type == "broadcast" else "Рассылка по каналам")
            self.actions_btn.setText(f"Действие: {action_name}")

    def _select_accounts(self):
        if self.is_broadcasting:
            return
        if not self.current_action:
            self._notify("Выбери действие")
            return
        dialog = AccountSelectionDialog(self)
        if dialog.exec():
            proxies, accounts = dialog.get_result()
            if not accounts:
                self.add_log("Аккаунты не найдены", "red")
                return
            self.selected_proxies = proxies
            self.selected_accounts = accounts
            self.add_log(f"Загружено {len(accounts)} аккаунтов, {len(proxies)} прокси", "blue")
            compose = ComposeMessageDialog(self)
            if compose.exec():
                self._message, self._attachments = compose.get_result()
                self.add_log(f"Сообщение готово, вложений: {len(self._attachments)}", "blue")
            else:
                self.selected_accounts = []
                self.selected_proxies = []

    def _on_launch_clicked(self):
        if self.is_broadcasting:
            self._stop_broadcast()
        else:
            self._start_broadcast()

    def _start_broadcast(self):
        if not self.current_action:
            self._notify("Выбери действие")
            return
        if not self.selected_accounts:
            self._notify("Выбери аккаунты")
            return
        if not self._message and not self._attachments:
            self._notify("Составь сообщение")
            return

        message, attachments = self._message, self._attachments
        max_workers = int(self.db.get("broadcast_threads", 100))
        delay = float(self.db.get("broadcast_delay", 0.0))
        target_guild_id = None
        if self.db.get("broadcast_target_guild_enabled", False):
            target_guild_id = self.db.get("broadcast_target_guild_id", "") or ""

        self.is_broadcasting = True
        self.btn_select_accounts.setEnabled(False)
        self.progress_bar.setValue(0)
        self.progress_label.setText("Рассылка...")
        self.progress_container.setVisible(True)

        self.launch_btn.setText("Остановить")
        self.launch_btn.setStyleSheet(BUTTON_DANGER)

        self.live_accounts = {}
        self._pending_status = {}

        self.broadcast = BroadcastWorker(
            self.selected_accounts, self.selected_proxies,
            message, attachments, max_workers, delay,
            target_guild_id=target_guild_id, parent=self
        )
        self.broadcast.progress_signal.connect(self._on_broadcast_progress)
        self.broadcast.log_signal.connect(self._on_broadcast_log)
        self.broadcast.account_status.connect(self._on_account_status)
        self.broadcast.finished_signal.connect(self._on_broadcast_finished)
        self.broadcast.start()

        self.add_log(f"Рассылка запущена: {len(self.selected_accounts)} аккаунтов", "blue")

    def _stop_broadcast(self):
        if self.broadcast:
            self.broadcast.stop()
            self.add_log("Остановка рассылки...", "yellow")

    def _on_broadcast_progress(self, sent: int, total: int):
        if total > 0:
            self.progress_bar.setValue(int(sent / total * 100))
        self.progress_label.setText(f"Отправлено: {sent} / {total}")

    def _on_broadcast_log(self, message: str, color: str):
        self.add_log(message, color)

    def _on_account_status(self, data: dict):
        self._pending_status[data["id"]] = data
        if data.get("final"):
            self._flush_account_status()
        elif not self._status_timer.isActive():
            self._status_timer.start()

    def _flush_account_status(self):
        if not self._pending_status:
            return
        terminal = self._current_terminal()

        for account_id, data in self._pending_status.items():
            text, color = self._format_status_text(data)
            if account_id not in self.live_accounts:
                block_num = self._append_live_line(terminal, text, color)
                self.live_accounts[account_id] = {"block": block_num, "final": data["final"]}
            else:
                info = self.live_accounts[account_id]
                self._replace_live_line(terminal, info["block"], text, color)
                info["final"] = data["final"]
        self._pending_status.clear()

    def _format_status_text(self, data: dict) -> tuple:
        color = "#4ade80" if data["final"] else "#f2f2f2"
        text = (
            f"{data['token']} | Серверов: {data['servers']} | "
            f"Каналов: {data['channels']} | Отправлено: {data['sent']} | "
            f"Нет прав: {data['forbidden']} | Ошибок: {data['failed']}"
        )
        return text, color

    def _append_live_line(self, terminal, text: str, color: str) -> int:
        cursor = QTextCursor(terminal.document())
        cursor.movePosition(QTextCursor.MoveOperation.End)
        if cursor.block().text():
            cursor.insertBlock()
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color))
        cursor.insertText(text, fmt)
        return cursor.block().blockNumber()

    def _replace_live_line(self, terminal, block_num: int, text: str, color: str):
        block = terminal.document().findBlockByNumber(block_num)
        if not block.isValid():
            return
        cursor = QTextCursor(block)
        cursor.select(QTextCursor.SelectionType.LineUnderCursor)
        cursor.removeSelectedText()
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color))
        cursor.insertText(text, fmt)

    def _current_terminal(self):
        if self.terminal_stack.currentIndex() == 1:
            return self.overlay_log_terminal
        return self.log_terminal

    def _on_broadcast_finished(self, stats: dict):
        self._status_timer.stop()
        self._flush_account_status()
        self.is_broadcasting = False
        self.btn_select_accounts.setEnabled(True)
        self.launch_btn.setText("Запуск")
        self.launch_btn.setStyleSheet(BUTTON_PRIMARY)
        self.progress_container.setVisible(False)
        sent = stats.get("sent", 0)
        failed = stats.get("failed", 0)
        forbidden = stats.get("forbidden", 0)
        self.add_log(
            f"Рассылка завершена | Отправлено: {sent} | Нет прав: {forbidden} | Ошибок: {failed}",
            "green",
        )
        main_window = self.window()
        if hasattr(main_window, 'accounts_page'):
            main_window.accounts_page._update_stats()

    def add_log(self, message: str, color: str = "white"):
        if not self.has_logs:
            self.has_logs = True
            show_video = self.db.get("show_empty_video", True)
            if show_video:
                self.terminal_stack.setCurrentIndex(1)
                terminal = self.overlay_log_terminal
            else:
                self.terminal_stack.setCurrentIndex(2)
                terminal = self.log_terminal
        else:
            if self.terminal_stack.currentIndex() == 1:
                terminal = self.overlay_log_terminal
            else:
                terminal = self.log_terminal

        hex_color = LOG_COLORS.get(color, "#ffffff")
        cursor = QTextCursor(terminal.document())
        cursor.movePosition(QTextCursor.MoveOperation.End)
        if cursor.block().text():
            cursor.insertBlock()
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(hex_color))
        cursor.insertText(message, fmt)
        cursor.movePosition(QTextCursor.MoveOperation.End)
