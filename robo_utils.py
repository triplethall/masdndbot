import sqlite3
import asyncio
import urllib.parse

import xml.etree.ElementTree as ET
import aiohttp
import json
import time
from datetime import datetime, timedelta
import hashlib
import hmac
from pathlib import Path

from telethon import Button

from alarm import info
from sql_utils import add_moves_value

# Пути к файлам
RUB_BILLS_PATH = r"C:\Bots\commonData\DnD\rub_bills.json"
ROBOKASSA_DATA_PATH = r"C:\Bots\commonData\DnD\robokassa.madata"
DB_PATH = r"C:\Bots\commonData\DnD\invoices.db"

# Глобальные данные
rub_bills = {}
robokassa_data = {}


async def load_config():
    """Загрузка конфигов при старте"""
    global rub_bills, robokassa_data
    with open(RUB_BILLS_PATH, 'r', encoding='utf-8') as f:
        rub_bills = json.load(f)
    with open(ROBOKASSA_DATA_PATH, 'r', encoding='utf-8') as f:
        robokassa_data = json.load(f)



def create_invoices_table():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS invoices (
            inv_id INTEGER PRIMARY KEY AUTOINCREMENT,  -- <-- чистый int
            user_id INTEGER,
            moves INTEGER,
            cost REAL,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()



def save_invoice(invoice_data):
    """invoice_data = {'inv_id': '123', 'user_id': 456, 'moves': 50, 'cost': 299.0}"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO invoices (inv_id, user_id, moves, cost, status, created_at)
        VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
    ''', (invoice_data['inv_id'], invoice_data['user_id'], invoice_data['moves'],
          invoice_data['cost'], invoice_data['status']))
    conn.commit()
    conn.close()



def get_pending_invoices():
    """Возвращает list словарей pending инвойсов <24ч, удаляет expired"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Удаляем expired >24ч
    cursor.execute("""
        UPDATE invoices
        SET status = 'expired'
        WHERE status = 'pending'
          AND created_at < datetime('now', '-24 hours')
    """)

    # Берем pending
    cursor.execute('''
        SELECT inv_id, user_id, moves, cost, status, created_at 
        FROM invoices 
        WHERE status = 'pending'
    ''')

    rows = cursor.fetchall()
    invoices = []
    for row in rows:
        invoices.append({
            'inv_id': row[0],
            'user_id': row[1],
            'moves': row[2],
            'cost': row[3],
            'status': row[4],
            'created_at': row[5]
        })

    conn.commit()
    conn.close()
    return invoices



def create_robokassa_url(user_id: int, cost: int):
    """cost в рублях. Возвращает корректный payment_url для Robokassa"""
    global robokassa_data



    # Находим moves по cost
    moves = next((int(k) for k, v in rub_bills.items() if v == cost), 50)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO invoices (user_id, moves, cost, status) VALUES (?, ?, ?, 'pending')",
        (user_id, moves, float(cost)),
    )
    inv_id = cursor.lastrowid  # УНИКАЛЬНЫЙ int для магазина
    conn.commit()
    conn.close()

    # Формируем параметры
    merchant_login = robokassa_data['merchant_login']
    password1 = robokassa_data['password1']

    # OutSum строго в формате с точкой и двумя знаками после запятой
    out_sum = f"{cost}.00"          # например, '299.00'
    description = f"TTs_MASTER_DICE_{moves}_pokupka_hodov"

    # Подпись по доке: MerchantLogin:OutSum:InvId:Password1
    sign_str = f"{merchant_login}:{out_sum}:{inv_id}:{password1}"
    info.put(sign_str)
    signature = hashlib.md5(sign_str.encode()).hexdigest()
    info.put(out_sum)
    # Собираем URL через urlencode (правильное кодирование параметров)
    params = {
        "MerchantLogin": merchant_login,
        "OutSum": out_sum,
        "InvId": inv_id,
        "Desc": description,
        "SignatureValue": signature,
        'IsTest': 0
    }
    payment_url = "https://auth.robokassa.ru/Merchant/Index.aspx?" + urllib.parse.urlencode(params)

    # Сохраняем в БД
    invoice_data = {
        'inv_id': inv_id,
        'user_id': user_id,
        'moves': moves,
        'cost': float(cost),
        'status': 'pending',
    }
    save_invoice(invoice_data)

    return payment_url



async def check_robokassa_status(inv_id: str):
    """
    Проверяет статус инвойса через XML API OpStateExt.
    Возвращает: 'paid', 'pending', 'failed', 'unknown'.
    """
    global robokassa_data

    merchant_login = robokassa_data['merchant_login']
    password2 = robokassa_data['password2']
    invoice_id = str(inv_id)

    # Подпись: MD5(MerchantLogin:InvoiceID:Password2)
    sign_str = f"{merchant_login}:{invoice_id}:{password2}"
    signature = hashlib.md5(sign_str.encode()).hexdigest()

    url = (
        "https://auth.robokassa.ru/Merchant/WebService/Service.asmx/OpStateExt"
        f"?MerchantLogin={merchant_login}"
        f"&InvoiceID={invoice_id}"
        f"&Signature={signature}"
    )

    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            text = await resp.text()

    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return 'unknown'

    ns = {"r": "http://merchant.roboxchange.com/WebService/"}

    # Результат запроса (0 — запрос корректен)
    result_code = root.findtext("r:Result/r:Code", default="", namespaces=ns)
    if result_code != "0":
        # 3 = операция не найдена, 1 и др. — ошибки запроса
        return 'pending'

    # Состояние платежа
    state_code = root.findtext("r:State/r:Code", default="", namespaces=ns)

    # 100 и 5 — операция успешно завершена / деньги зачислены
    if state_code in ("5", "100"):
        return 'paid'
    # 0,3,6 — ещё не оплачено / в обработке / hold
    if state_code in ("0", "3", "6"):
        return 'pending'
    # 1,2,4 — отменено / отказ / возврат
    if state_code in ("1", "2", "4"):
        return 'failed'

    return 'unknown'


# 5. Поллинг таск
async def robo_polling_task(client):
    """Запуск: asyncio.create_task(robo_polling_task())"""
    await load_config()
    create_invoices_table()

    while True:
        try:
            pending = get_pending_invoices()
            for inv in pending:
                info.put("Провожу опрос статусов оплат робокассы")
                status = await check_robokassa_status(inv['inv_id'])

                if status == 'paid':
                    # Начисляем ходы
                    add_moves_value(inv['user_id'], "movecoin", inv['moves'])
                    add_moves_value(inv['user_id'], 'bought_times', 1)
                    add_moves_value(inv['user_id'], 'bought_moves', inv['moves'])

                    # Обновляем статус
                    conn = sqlite3.connect(DB_PATH)
                    cursor = conn.cursor()
                    cursor.execute(
                        "UPDATE invoices SET status = 'paid' WHERE inv_id = ?",
                        (inv['inv_id'],)
                    )
                    conn.commit()
                    conn.close()
                    buttons = [Button.inline("Закрыть", data="stephome")]
                    await client.send_message(inv['user_id'], f"Оплата прошла успешно, {inv['moves']} ходов зачислено", buttons=buttons)
                    info.put(f"✅ Paid: user {inv['user_id']}, inv {inv['inv_id']}, {inv['moves']} moves")

        except Exception as e:
            info.put(f"Pobo polling error: {e}")

        await asyncio.sleep(120)  # 2 минуты