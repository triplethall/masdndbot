

import os
import queue
import threading
import time
from datetime import datetime

alarm = queue.Queue()
debugin = queue.Queue()
info = queue.Queue()

# --- Переменная для хранения внешней GUI-очереди ---
_gui_queue = None


def set_log_queue(q: queue.Queue):
    """
    Устанавливает внешнюю очередь для отправки логов в GUI.
    """
    global _gui_queue
    _gui_queue = q


def _send_to_gui(log_message: str):
    """Проверяет, установлена ли GUI-очередь, и отправляет сообщение."""
    if _gui_queue:
        _gui_queue.put(log_message)


def alarm_handler():
    while True:
        error = alarm.get()
        # Формируем сообщение с датой и временем
        log_message = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [FATAL] {error}"

        print(log_message)  # Оставляем вывод в консоль
        _send_to_gui(log_message)  # Отправляем в GUI



def debug_handler():
    while True:
        debugtxt = debugin.get()
        # Формируем сообщение с датой и временем
        log_message = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [DEBUG] {debugtxt}"

        print(log_message)  # Оставляем вывод в консоль
        _send_to_gui(log_message)  # Отправляем в GUI


def info_handler():
    while True:
        infor = info.get()
        # Формируем сообщение с датой и временем
        log_message = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [INFO] {infor}"

        print(log_message)  # Оставляем вывод в консоль
        _send_to_gui(log_message)  # Отправляем в GUI


def route():
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Программа завершена вручную")


alarmer = threading.Thread(target=alarm_handler, daemon=True)
debuger = threading.Thread(target=debug_handler, daemon=True)
infoer = threading.Thread(target=info_handler, daemon=True)
router = threading.Thread(target=route, daemon=True)

alarmer.start()
debuger.start()
infoer.start()
router.start()