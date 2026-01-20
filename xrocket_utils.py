import os.path
from datetime import datetime
from pathlib import Path

import httpx
import json
import asyncio

from telethon import Button

from alarm import info
from sql_utils import add_moves_value, status_manager

api_file = r"C:\Bots\commonData\DnD\xrocket.madata"
with open(api_file, "r", encoding="utf-8") as f:
    API_KEY = f.read()
    print("API_KEY =", API_KEY)

API_URL = r"https://pay.xrocket.tg/tg-invoices"
invoice_folder = r"C:\Bots\commonData\DnD\bills"

async def create_xrocket_invoice(user_id: int, amount: float, currency="USDT", expire_in=86400):
    headers = {
        "Rocket-Pay-Key": API_KEY,
        "Content-Type": "application/json"
    }

    data = {
        "amount": amount,
        "numPayments": 1,           # одноразовый чек
        "currency": currency,
        "description": f"TT MASTER DICE: покупка ходов пользователем {user_id}",
        "hiddenMessage": "thank you",
        "commentsEnabled": True,
        "payload": str(user_id),        # для связи с пользователем
        "expiredIn": expire_in
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(API_URL, headers=headers, json=data)
    if response.status_code != 201:
        # Можно вывести текст ошибки
        return (f"xRocket: ошибка при создании счета — код {response.status_code}, ответ: {response.text}")

    result = response.json()
    data_obj = result.get("data", {})
    invoice_id = data_obj.get("id")
    payment_url = data_obj.get("link")
    payload_val = data_obj.get("payload")

    if not invoice_id or not payment_url:
        raise ValueError("Ошибка: нет id или ссылки оплаты в ответе xRocket")

    filename = f"order_xrocket&{user_id}&{int(amount)}&{currency}.json"
    with open(os.path.join(invoice_folder,filename), "w", encoding="utf-8") as f:
        json.dump({
            "user_id": user_id,
            "invoice_id": invoice_id,
            "payment_url": payment_url,
            "amount": amount,
            "currency": currency,
            "payload": payload_val
        }, f, ensure_ascii=False, indent=4)

    return [invoice_id, payment_url]

# не звать напрямую!
async def _invoice_status_worker(client, user_id, moves, amount, invoice_id, interval=1800, max_checks=48):
    filename = f"order_xrocket&{user_id}&{int(amount)}&USDT.json"
    fullpath = os.path.join(invoice_folder, filename)
    headers = {
        "Rocket-Pay-Key": API_KEY,
        "Content-Type": "application/json"
    }
    for attempt in range(max_checks):
        url = f"{API_URL}/{invoice_id}"
        async with httpx.AsyncClient() as http_client:
            response = await http_client.get(url, headers=headers)
        if response.status_code != 200:
            await asyncio.sleep(interval)
            continue

        data = response.json().get("data", {})
        payments = data.get("payments", [])
        is_paid = False
        for p in payments:
            # Если пришла оплата, и получена сумма больше нуля
            if p.get("paymentAmountReceived", 0) > 0 and p.get("paid"):
                is_paid = True
                break

        if is_paid:
            buttons = [Button.inline(f"Закрыть", data=f"stephome")]
            await client.send_message(user_id, f"✅ Ваш счет #{invoice_id} успешно оплачен! Вам начислено {moves} ходов", buttons=buttons)
            add_moves_value(user_id, "movecoin", moves)
            add_moves_value(user_id, 'bought_times', 1)
            add_moves_value(user_id, 'bought_moves', moves)
            os.remove(fullpath)
            return

        await asyncio.sleep(interval)

    os.remove(fullpath)
    buttons = [Button.inline(f"Закрыть", data=f"stephome")]
    await client.send_message(user_id, f"⏳ Время ожидания истекло: счет #{invoice_id} так и не был оплачен.",buttons=buttons)


async def invoice_polling(client, user_id, moves, amount, invoice_id, interval=1800, max_checks=48):
    """
    Запускает фоновое слежение за оплатой (создаёт task) и сразу завершает выполнение;
    не ожидает результат, ничего не возвращает.
    """
    asyncio.create_task(_invoice_status_worker(client, user_id, moves, amount, invoice_id, interval, max_checks), name=f"rocket_{invoice_id}")


def xrocket_bill_check(cost, user_id):
    filename = f"order_xrocket&{user_id}&{cost}&USDT.json"
    fullpath = os.path.join(invoice_folder, filename)

    if os.path.isfile(fullpath):
        # Проверяем время создания (Windows) или изменения
        file_stat = Path(fullpath).stat()
        file_age = datetime.now().timestamp() - file_stat.st_ctime

        if file_age > 86400:  # больше 24 часов (сутки)
            os.remove(fullpath)
            info.put(f"Удален expired файл: {fullpath}")
            return None

        # Файл свежий — читаем
        with open(fullpath, "r", encoding="utf-8") as f:
            return json.load(f)
    else:
        return None

async def xrocket_page(client, event, user_id):
    bills_scheme_path = r"C:\Bots\commonData\DnD\xrocket_bills.json"
    with open(bills_scheme_path, "r", encoding="utf-8") as f:
        bills_scheme = json.load(f)
    buttons = []
    for key, value in bills_scheme.items():
        buttons.append([Button.inline(f"XROCKET -> {key} ходов за {value} USDT", data=f"rocketbill:{key}:{value}")])
    buttons.append([Button.inline("Назад", data="store")])
    buttons.append([Button.inline("В главное меню", data="tostart")])


    text = (f"xRocket — это универсальный Telegram-бот и кошелек для быстрой и безопасной "
            f"работы с криптовалютой: покупка, продажи, чеки, P2P, счета. Возможно P2P пополнение кошелька через СБП."
            f"\n\nПри нажатии на любой из вариантов ниже, создастся счет, который будет действителен сутки. "
            f"Если счет оплачен, но ходы в течение часа не появились в боте и не пришло уведомление об успешной оплате, "
            f"напиши об этом в чат [канала](t.me/masterdiceofficial).")

    msg = await client.send_message(user_id, text, buttons=buttons, link_preview=False)
    ids = [event.message_id]
    ids.append(msg.id)
    await status_manager(client, event, ids, "outgame")
    comm = await event.get_message()
    await comm.delete()

def is_invoice_task_running(name):
    for t in asyncio.all_tasks():
        if t.get_name() == name and not t.done():
            return True
    return False

async def xrocket_bill_page(client, event, user_id, data):
    prefix,moves,cost = data.split(":")
    del prefix
    text = (f"Создан счет в XROCKET на {cost} USDT.\n"
            f"Он будет действителен в течение суток. "
            f"Оплата проверяется ботом автоматически каждые полчаса, в случае задержки "
            f"начисления ходов (как только боту поступит сигнал об успешной оплате, "
            f"он пришлет тебе уведомление и начислит ходы) "
            f"или других проблем напиши об этом в чат [канала](t.me/masterdiceofficial)."
            f"\n\n Для оплаты пройди по ссылке в кнопке ниже:")

    bill = xrocket_bill_check(cost, user_id)
    if bill is not None:
        buttons=[[Button.url(f"Оплатить счет ({cost} USDT)", url=bill.get("payment_url"))]]
        task = is_invoice_task_running(f"rocket_{bill.get('invoice_id')}")
        if task == False:
            await invoice_polling(client, user_id, moves, cost, bill.get('invoice_id'))

    else:
        data = await create_xrocket_invoice(user_id, cost)
        await invoice_polling(client, user_id, moves, cost, data[0])
        buttons = [[Button.url(f"Оплатить счет ({cost} USDT)", url=data[1])]]
        buttons.append([Button.inline("В главное меню", data="tostart")])

    msg = await client.send_message(user_id, text, buttons=buttons, link_preview=False)
    ids = [event.message_id]
    ids.append(msg.id)
    await status_manager(client, event, ids, "outgame")
    comm = await event.get_message()
    await comm.delete()