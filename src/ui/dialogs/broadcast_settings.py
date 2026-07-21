from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QWidget,
    QDoubleSpinBox, QLineEdit,
)
from PyQt6.QtCore import Qt, QByteArray
from PyQt6.QtGui import QFont, QPixmap, QPainter, QIcon
from PyQt6.QtSvg import QSvgRenderer
from pathlib import Path
from src.ui.dialogs.settings import SettingRowWithSpinBox, SettingRowWithToggle
from src.core.database import Database


class SettingRowWithDoubleSpinBox(QWidget):
    def __init__(self, title, min_val=0.5, max_val=30.0, default_val=2.0, step=0.5):
        super().__init__()
        self.title = title
        self.setup_ui(min_val, max_val, default_val, step)

    def setup_ui(self, min_val, max_val, default_val, step):
        from PyQt6.QtWidgets import QHBoxLayout, QVBoxLayout
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 12, 0, 12)
        layout.setSpacing(0)

        text_container = QWidget()
        text_layout = QVBoxLayout(text_container)
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(4)

        title_label = QLabel(self.title)
        title_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Medium))
        title_label.setStyleSheet("color: rgba(255, 255, 255, 0.9); background: transparent; border: none;")
        text_layout.addWidget(title_label)
        layout.addWidget(text_container)
        layout.addStretch()

        self.spinbox = QDoubleSpinBox()
        self.spinbox.setMinimum(min_val)
        self.spinbox.setMaximum(max_val)
        self.spinbox.setValue(default_val)
        self.spinbox.setSingleStep(step)
        self.spinbox.setFixedWidth(90)
        self.spinbox.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
        self.spinbox.setSuffix(" с")
        self.spinbox.setStyleSheet("""
            QDoubleSpinBox {
                background-color: rgba(255, 255, 255, 0.08);
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 8px;
                color: rgba(255, 255, 255, 0.9);
                padding: 6px 10px;
                font-size: 10pt;
                font-family: "Segoe UI";
            }
            QDoubleSpinBox:hover {
                background-color: rgba(255, 255, 255, 0.12);
                border: 1px solid rgba(255, 255, 255, 0.18);
            }
            QDoubleSpinBox:focus {
                background-color: rgba(255, 255, 255, 0.12);
                border: 1px solid rgba(88, 101, 242, 0.8);
            }
        """)
        layout.addWidget(self.spinbox)


class BroadcastSettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.db = Database()
        self.setWindowTitle("")
        self.setModal(True)
        self.setFixedSize(600, 460)
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setStyleSheet("QDialog { background: transparent; }")
        self._build_ui()
        self._load_settings()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(0)

        container = QLabel()
        container.setFixedSize(580, 440)
        container.setStyleSheet("""
            QLabel {
                background-color: rgba(20, 20, 23, 252);
                border-radius: 28px;
                border: 1px solid rgba(255, 255, 255, 0.08);
            }
        """)
        layout.addWidget(container)

        content_layout = QVBoxLayout(container)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        header_container = QLabel()
        header_container.setFixedHeight(60)
        header_container.setStyleSheet("background: transparent; border: none;")
        header_layout = QHBoxLayout(header_container)
        header_layout.setContentsMargins(24, 18, 18, 0)
        header_layout.setSpacing(0)

        title_label = QLabel("Настройки рассылки")
        title_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Medium))
        title_label.setStyleSheet("color: rgba(255, 255, 255, 0.9); background: transparent; border: none;")
        header_layout.addWidget(title_label)
        header_layout.addStretch()

        close_btn = QPushButton()
        close_btn.setFixedSize(32, 32)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet("""
            QPushButton { background-color: transparent; border: none; border-radius: 8px; }
            QPushButton:hover { background-color: rgba(255, 255, 255, 0.08); }
            QPushButton:pressed { background-color: rgba(255, 255, 255, 0.12); }
        """)
        close_icon_path = Path(__file__).parent.parent.parent.parent / "assets" / "icons" / "close.svg"
        svg_data = close_icon_path.read_text()
        colored_svg = svg_data.replace('stroke="currentColor"', 'stroke="#999999"')
        renderer = QSvgRenderer(QByteArray(colored_svg.encode()))
        pixmap = QPixmap(18, 18)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()
        close_btn.setIcon(QIcon(pixmap))
        close_btn.setIconSize(pixmap.size())
        close_btn.clicked.connect(self.reject)
        header_layout.addWidget(close_btn)
        content_layout.addWidget(header_container)

        sep = QLabel()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background-color: rgba(255, 255, 255, 0.06); border: none;")
        content_layout.addWidget(sep)

        body = QLabel()
        body.setStyleSheet("background: transparent; border: none;")
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(24, 20, 24, 24)
        body_layout.setSpacing(0)

        self.threads_row = SettingRowWithSpinBox(
            "Количество потоков", "", min_val=1, max_val=200, default_val=100
        )
        self.threads_row.spinbox.valueChanged.connect(lambda v: self.db.set("broadcast_threads", v))
        body_layout.addWidget(self.threads_row)

        sep1 = QLabel()
        sep1.setFixedHeight(1)
        sep1.setStyleSheet("background-color: rgba(255, 255, 255, 0.08); border: none;")
        body_layout.addWidget(sep1)

        self.delay_row = SettingRowWithDoubleSpinBox(
            "Задержка между сообщениями", min_val=0.0, max_val=30.0, default_val=0.0, step=0.1
        )
        self.delay_row.spinbox.valueChanged.connect(lambda v: self.db.set("broadcast_delay", v))
        body_layout.addWidget(self.delay_row)

        sep2 = QLabel()
        sep2.setFixedHeight(1)
        sep2.setStyleSheet("background-color: rgba(255, 255, 255, 0.08); border: none;")
        body_layout.addWidget(sep2)

        self.target_guild_row = SettingRowWithToggle(
            "Рассылка на определенный сервер", ""
        )
        self.target_guild_row.toggle.toggled.connect(self._on_target_guild_toggled)
        body_layout.addWidget(self.target_guild_row)

        self.guild_id_container = QWidget()
        self.guild_id_container.setStyleSheet("background: transparent; border: none;")
        guild_id_layout = QHBoxLayout(self.guild_id_container)
        guild_id_layout.setContentsMargins(0, 0, 0, 12)
        guild_id_layout.setSpacing(0)

        self.guild_id_input = QLineEdit()
        self.guild_id_input.setPlaceholderText("ID сервера")
        self.guild_id_input.setFont(QFont("Segoe UI", 10))
        self.guild_id_input.setStyleSheet("""
            QLineEdit {
                background-color: rgba(255, 255, 255, 0.08);
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 8px;
                color: rgba(255, 255, 255, 0.9);
                padding: 8px 12px;
                font-size: 10pt;
                font-family: "Segoe UI";
            }
            QLineEdit:hover {
                background-color: rgba(255, 255, 255, 0.12);
                border: 1px solid rgba(255, 255, 255, 0.18);
            }
            QLineEdit:focus {
                background-color: rgba(255, 255, 255, 0.12);
                border: 1px solid rgba(88, 101, 242, 0.8);
            }
        """)
        self.guild_id_input.textChanged.connect(self._on_guild_id_changed)
        guild_id_layout.addWidget(self.guild_id_input)
        body_layout.addWidget(self.guild_id_container)
        self.guild_id_container.setVisible(False)

        body_layout.addStretch()
        content_layout.addWidget(body)

    def _on_target_guild_toggled(self, checked: bool):
        self.db.set("broadcast_target_guild_enabled", checked)
        self.guild_id_container.setVisible(checked)

    def _on_guild_id_changed(self, text: str):
        self.db.set("broadcast_target_guild_id", text.strip())

    def _load_settings(self):
        threads = int(self.db.get("broadcast_threads", 100))
        delay = float(self.db.get("broadcast_delay", 0.0))
        target_enabled = self.db.get("broadcast_target_guild_enabled", False)
        target_guild_id = self.db.get("broadcast_target_guild_id", "") or ""

        self.threads_row.spinbox.setValue(threads)
        self.delay_row.spinbox.setValue(delay)
        self.target_guild_row.toggle.set_checked(target_enabled)
        self.guild_id_input.setText(target_guild_id)
        self.guild_id_container.setVisible(target_enabled)
