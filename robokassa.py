import json

from telethon import Button

from alarm import info
from robo_utils import create_robokassa_url
from sql_utils import status_manager


async def robokassa_page(client, event, user_id):
    bills_scheme_path = r"C:\Bots\commonData\DnD\rub_bills.json"
    with open(bills_scheme_path, "r", encoding="utf-8") as f:
        bills_scheme = json.load(f)
    buttons = []
    for key, value in bills_scheme.items():
        buttons.append([Button.inline(f"ROBOKASSA -> {key} ходов за {value} RUB", data=f"robobill:{key}:{value}")])
    buttons.append([Button.inline("Назад", data="store")])
    buttons.append([Button.inline("В главное меню", data="tostart")])

    text = (f"Robokassa — это надежная платежная система для быстрых покупок в рублях "
            f"через карты, СБП, QIWI, ЮMoney и другие способы. Поддержка РФ-банков и электронных кошельков."
            f"\n\nПри нажатии на любой из вариантов ниже, откроется страница оплаты. "
            f"После успешной оплаты ходы зачислятся автоматически в течение нескольких минут. "
            f"Если ходы не появились в течение часа или возникли проблемы с оплатой, "
            f"напиши об этом в чат [канала](t.me/masterdiceofficial).")

    msg = await client.send_message(user_id, text, buttons=buttons, link_preview=False)
    ids = [event.message_id]
    ids.append(msg.id)
    await status_manager(client, event, ids, "outgame")
    comm = await event.get_message()
    await comm.delete()

async def robo_bill_page(client, event, user_id, data):
    prefix,moves,cost = data.split(":")
    info.put(data)
    del prefix
    text = (f"Создана ссылка на оплату в Robokassa на {cost} ₽.\n"
            f"После успешной оплаты ходы зачислятся автоматически в течение 2-5 минут.\n"
            f"Бот проверяет статус платежа в реальном времени."
            f"Если ходы не появились в течение 30 минут или возникли проблемы, "
            f"напиши об этом в чат [канала](t.me/masterdiceofficial)."
            f"\n\nДля оплаты перейди по ссылке в кнопке ниже:")

    bill_link = create_robokassa_url(user_id, cost)
    buttons = [[Button.url(f"Оплатить счет ({cost} ₽)", url=bill_link)]]
    buttons.append([Button.inline("В главное меню", data="tostart")])


    msg = await client.send_message(user_id, text, buttons=buttons, link_preview=False)
    ids = [event.message_id]
    ids.append(msg.id)
    await status_manager(client, event, ids, "outgame")
    comm = await event.get_message()
    await comm.delete()