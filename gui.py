import sys
import queue
import threading
from PyQt5 import QtWidgets, uic, QtCore, QtGui

from alarm import info


message_queue = queue.Queue()


class Ui_MainWindow(QtWidgets.QMainWindow):

    message_received = QtCore.pyqtSignal(str)

    def __init__(self, *args, **kwargs):

        super(Ui_MainWindow, self).__init__(*args, **kwargs)
        info.put("--- СОЗДАНИЕ ЭКЗЕМПЛЯРА ОКНА Ui_MainWindow ---")

        uic.loadUi(r"C:\Bots\commonData\DnD\ui.ui", self)

        self.setWindowFlag(QtCore.Qt.FramelessWindowHint)
        self.setWindowTitle("DnD bot")
        app_icon = QtGui.QIcon(r"C:\Bots\commonData\DnD\icon.png")
        self.setWindowIcon(app_icon)



        self.tray_icon = QtWidgets.QSystemTrayIcon(self)

        self.tray_icon.setIcon(QtGui.QIcon(r"C:\Bots\commonData\DnD\icon.png"))


        tray_menu = QtWidgets.QMenu()

        exit_action = tray_menu.addAction("Выход")

        exit_action.triggered.connect(self.close)


        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.show()


        self.pushButton.clicked.connect(self.hide)


        self.pushButton_2.clicked.connect(self.close)


        self.tray_icon.activated.connect(self.on_tray_icon_activated)


        self.message_received.connect(self.append_message)


        self.queue_thread = threading.Thread(target=self.process_queue, daemon=True)
        self.queue_thread.start()

        self.drag_pos = None

    def process_queue(self):

        while True:

            message = message_queue.get()
            if message is None:
                break

            self.message_received.emit(message)

    def closeEvent(self, event: QtGui.QCloseEvent):

        info.put("Окно получило команду на закрытие, останавливаем внутренние потоки...")


        message_queue.put(None)


        self.queue_thread.join(timeout=1)


        event.accept()

    @QtCore.pyqtSlot(str)
    def append_message(self, message):

        self.textBrowser.append(message)

    def on_tray_icon_activated(self, reason):

        if reason == QtWidgets.QSystemTrayIcon.Trigger:
            self.show()

    def hideEvent(self, event):

        self.tray_icon.show()
        super().hideEvent(event)

    def showEvent(self, event):

        self.tray_icon.hide()
        super().showEvent(event)

    def mousePressEvent(self, event: QtGui.QMouseEvent):

        if event.button() == QtCore.Qt.LeftButton:

            if self.pushButton.geometry().contains(event.pos()) or \
                    self.pushButton_2.geometry().contains(event.pos()) or \
                    self.textBrowser.geometry().contains(event.pos()):
                super().mousePressEvent(event)
                return


            self.drag_pos = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event: QtGui.QMouseEvent):

        if event.buttons() == QtCore.Qt.LeftButton and self.drag_pos is not None:

            self.move(event.globalPos() - self.drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent):

        self.drag_pos = None
        event.accept()


def start_gui_thread():

    app = QtWidgets.QApplication.instance()
    if not app:
        app = QtWidgets.QApplication(sys.argv)


    app.setQuitOnLastWindowClosed(True)

    window = Ui_MainWindow()
    window.show()
    app.exec_()