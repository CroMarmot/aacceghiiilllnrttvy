# https://doc.qt.io/qtforpython-6/examples/example_widgets_desktop_systray.html

import logging
import os
import subprocess

from PySide6.QtCore import Slot
from PySide6.QtGui import QAction, QCursor, QIcon
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QMenu,
    QSystemTrayIcon,
    QVBoxLayout,
)

# https://stackoverflow.com/questions/63164785/why-the-icon-doesnt-display-in-system-tray-although-the-python-code-is-executin
logging.basicConfig(level=logging.INFO, format="%(message)s")


class Window(QDialog):  # 也可以不要Dialog 做纯的tray 应用
    def __init__(self, parent=None):
        super().__init__(parent)
        # TODO host
        self.urls = [
            "https://www.youtube.com",
            "https://www.javbus.com",
            "https://javdb.com",
            "https://fc2ppvdb.com",
            "https://x.com",
            "https://missav.com",
            "https://njav.tv",
            "http://www.gstatic.com/generate_204",
        ]
        self.title = "v2ctl tray"
        self.icons = ["bad.png", "heart.png", "trash.png"]
        self.CURRENT_DIRECTORY = os.path.dirname(os.path.realpath(__file__))
        self.logger = logging.getLogger("v2raya_cli_client.systray")
        self.logger.setLevel(logging.INFO)

        self.create_icon_group_box()
        self.create_tray_icon()
        self._tray_icon_menu = QMenu()

        self._tray_icon.activated.connect(self.icon_activated)  # 点击tray, 左键

        self._main_layout = QVBoxLayout()
        self._main_layout.addWidget(self._icon_group_box)
        self.setLayout(self._main_layout)

        self._icon_combo_box.setCurrentIndex(1)
        self._tray_icon.show()

        self.setWindowTitle(self.title)

    # @override python3.12
    def setVisible(self, visible):  # 这个和 _tray_icon 的是两个，这个是窗口的
        self._restore_action.setEnabled(self.isMaximized() or not visible)
        super().setVisible(visible)

    # @override python3.12
    def closeEvent(self, event):  # 点击关闭时
        if not event.spontaneous() or not self.isVisible():
            return
        # 点击关闭时的提醒按钮 # QMessageBox.information
        self.hide()
        event.ignore()  # 不真的关闭

    @Slot(int)
    def set_icon(self, index):
        icon = self._icon_combo_box.itemIcon(index)
        self._tray_icon.setIcon(icon)
        self.setWindowIcon(icon)
        self._tray_icon.setToolTip(self._icon_combo_box.itemText(index))

    @Slot(str)
    def icon_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            # https://doc.qt.io/qt-6/qsystemtrayicon.html#public-functions
            self._tray_icon.contextMenu().popup(QCursor.pos())
        # kde 上似乎触发不了 双击?  if reason == QSystemTrayIcon.DoubleClick:

    @Slot()
    def show_message(self, msg: str):  # 显示系统消息
        # PySide6.QtWidgets.QSystemTrayIcon.showMessage():
        #   not enough arguments. Note: keyword arguments are only supported for optional parameters
        self._tray_icon.showMessage(
            self.title,
            msg,
            QSystemTrayIcon.MessageIcon.NoIcon,
            10 * 1000,  # 10s
        )

    def create_icon_group_box(self):
        self._icon_group_box = QGroupBox("Tray Icon")

        # https://doc.qt.io/qtforpython-6/overviews/qtquickcontrols-input.html#combobox-control
        self._icon_combo_box = QComboBox()
        for icon in self.icons:
            self._icon_combo_box.addItem(QIcon(os.path.join(self.CURRENT_DIRECTORY, f"images/{icon}")), icon)

        icon_layout = QHBoxLayout()
        icon_layout.addWidget(self._icon_combo_box)
        self._icon_combo_box.currentIndexChanged.connect(self.set_icon)  # 切换选择
        self._icon_group_box.setLayout(icon_layout)

    @Slot()
    def debug(self):
        pwd_res = subprocess.run(["/usr/bin/pwd"], capture_output=True, text=True, check=True)  # 运行目录
        path = os.environ["PATH"]  # 环境变量PATH
        which_v2ctl_res = subprocess.run(
            ["/usr/bin/which", "v2ctl"], capture_output=True, text=True, check=True
        )  # 查看cli工具是否存在
        msg = f"{pwd_res.stdout=}\n{path=}\n{which_v2ctl_res.stdout=}"
        self.logger.info(msg)
        self.show_message(msg)

    def on_url_click(self, url):
        self.logger.info(url)
        res = subprocess.run(
            [
                "v2ctl",  # Starting a process with a partial executable path Ruff(S607)
                "smart",
                "--fast-server",
                "1",
                "--tz-delta=8",
                "--sub-idx",
                "0",
                "--test-url",
                url,
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        self.logger.info(url + " Done")
        self.show_message(f"{res.stdout=},{res.stderr=}")

    def create_tray_icon(self):
        # create_actions
        self._restore_action = QAction("Restore", self)
        self._restore_action.triggered.connect(self.showNormal)

        self._debug_action = QAction("Debug", self)
        self._debug_action.triggered.connect(self.debug)

        self._quit_action = QAction("Quit", self)
        self._quit_action.triggered.connect(qApp.quit)  # noqa: F821

        # sub menu
        self._dynamic_menu = QMenu("v2ctl smart", self)
        for url in self.urls:
            # Function definition does not bind loop variable `url`RuffB023
            self._dynamic_menu.addAction(url, lambda url=url: self.on_url_click(url))

        # create menu
        self._tray_icon_menu = QMenu(self)
        self._tray_icon_menu.addMenu(self._dynamic_menu)
        self._tray_icon_menu.addAction(self._restore_action)
        self._tray_icon_menu.addAction(self._debug_action)
        self._tray_icon_menu.addSeparator()
        self._tray_icon_menu.addAction(self._quit_action)
        # https://doc.qt.io/qt-6/qsystemtrayicon.html#public-functions
        self._tray_icon = QSystemTrayIcon(self)  # !!?? self = 自己的?
        self._tray_icon.setContextMenu(self._tray_icon_menu)
