import os
import random
from datetime import datetime
import json
import asyncio
import concurrent.futures
import queue  # Для совместимости с API multiprocessing.Queue
import sqlite3

from telethon import TelegramClient, events, Button
from telethon.events import StopPropagation

from alarm import info, debugin, alarm, set_log_queue
from chargen import newchar

from common_utils import delete_files_with_substring, get_lore_preset, startmenu, delete_all_with_progress, is_busy, \
    clear_busy, last_move
from ingame import gogame, restore_game, store, ask_promo, promocode_job, referal_info, send_portal_intro
from no_context_utils import newlore, save_temp_msg, load_temp_msg, attrlist, summary_on_start, ingame_summary
from robo_utils import robo_polling_task
from robokassa import robokassa_page, robo_bill_page
from sql_utils import is_user_registered, register_user, get_dnd_status, set_dnd_status, status_manager, set_input_mode, \
    get_input_mode, set_moves_value, add_moves_value, increment_total_refs, acquire_lock, cleanup_old_locks, \
    release_lock
from xrocket_utils import xrocket_page, xrocket_bill_page

# Пути к файлам
CONFIG_PATH = r"C:\Bots\commonData\DnD\bot.madata"
START_IMG = r"C:\Bots\commonData\DnD\pics\start.png"

temp_msg = None

#для dim = 10, num генерить от 0 до 9
async def roll(client, event, num, dim):
    sender = event.sender
    user_id = sender.id
    # Путь к папке с видео
    base_path = r"C:\Bots\commonData\DnD\videorolls"

    # Формируем имя файла по паттерну
    video_filename = f"d{dim}-{num}.mp4"
    video_path = os.path.join(base_path, video_filename)
    try:
    # Отправляем video note с нужным видео
        msg = await client.send_file(
            event.chat_id,
            video_path,
            video_note=True
        )
    except:
        buttons = [Button.inline("Назад", data="stephome")]
        msg = await client.send_message(event.chat_id,
                                  "Вы заблокировали отправку голосовых сообщений и не можете увидеть ролл",
                                  buttons=buttons)

    return msg

# Функция для загрузки конфига
def load_config():
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)

def isgame(user_id):
    folderpath = r"C:\Bots\commonData\DnD\gamedata"
    filename = f"{user_id}_common_context.json"
    if os.path.isfile(os.path.join(folderpath, filename)):
        return True
    else:
        return False

#функция для создания клиента из конфига
async def create_client():
    config = load_config()
    api_id = config['api_id']
    api_hash = config['api_hash']
    bot_token = config['token']


    client = TelegramClient('bot_session', api_id, api_hash)
    await client.start(bot_token=bot_token)
    return client

async def main(broadcast_queue):
    client = await create_client()
    info.put("Бот запущен.")
    asyncio.create_task(robo_polling_task(client))
    info.put("robo_task polling")
    @client.on(events.CallbackQuery)
    async def callback_handler(event):
        await event.answer()
        user_id = event.chat_id
        request_id = await acquire_lock(user_id)

        if not request_id:
            return

        try:

            await cleanup_old_locks(user_id)
            data = event.data.decode('utf-8') if event.data else ''

            if data == "comslist":
                ids = [event.message_id]
                comm = await event.get_message()
                await comm.delete()
                msg = await client.send_message(
                    event.chat_id,
                    r"""Команды бота:
                /start - главное меню (не сбрасывает текущую игру!)
                /campaign_restore - восстанавливает кампанию, если произошел сбой
                /summary - показывает информацию о текущей игре
                /roll_d20 - бросок d20
                /roll_d12 - бросок d12
                /roll_d10 - бросок d10
                /roll_d8 - бросок d8
                /roll_d6 - бросок d6
                /roll_d4 - бросок d4
                """,
                    buttons=Button.inline("Назад", data="tostart")
                )
                ids.append(msg.id)
                await status_manager(client, event, ids, "outgame")

            elif data == "stephome":
                comm = await event.get_message()
                await comm.delete()

            elif data == "newgame":
                if get_dnd_status(event.sender.id) in ["outgame","ingame"] and isgame(user_id) == True:
                    buttons = []
                    dd = await event.get_message()
                    try:
                        await dd.delete()
                    except:
                        info.put("Сработало антизалипание")
                    buttons.append(Button.inline("✔️", data="newgameproceed"))
                    buttons.append(Button.inline("✖️", data="tostart"))
                    msg = await event.client.send_message(
                        event.chat_id,
                        "Уже есть начатая игра.\nПерезаписать ее?",
                        buttons=buttons
                    )
                else:
                    await delete_all_with_progress(client, event)
                    await status_manager(client, event, [], "ingame")
                    dd = await event.get_message()
                    try:
                        await dd.delete()
                    except:
                        info.put("Сработало антизалипание")
                    buttons = []
                    buttons.append(Button.inline("Взять готовый пресет", data="presetlore"))
                    buttons.append(Button.inline("Сгенерировать ИИ", data="inputlore"))
                    msg = await event.client.send_message(
                        event.chat_id,
                        "Твое приключение уже ждет.\nХочешь взять готовый сюжет, сгенерировать лор игры полностью случайным образом или указать свои пожелания?",
                        buttons=buttons
                    )

            elif data == "newgameproceed":
                await status_manager(client, event, [], "nogame")
                buttons = [Button.inline("✔️", data="newgame")]
                delete_files_with_substring(event.chat_id)
                set_moves_value(event.chat_id, 'move', 0)
                await event.client.send_message(
                    event.chat_id,
                    "Данные предыдущей игры удалены.",
                    buttons=buttons
                )

                msg = await event.get_message()
                try:
                    await msg.delete()
                except:
                    pass

            elif data == "rules":
                buttons = [Button.inline("Назад", data="tostart")]

                comm = await event.get_message()
                try:
                    await comm.delete()
                except:
                    pass
                msg = await client.send_message(user_id, "Этот раздел находится в разработке и будет обязательно добавлен в одном из следующих обновлений", buttons=buttons)
                ids = [event.message_id, msg.id]
                await status_manager(client, event, ids, "outgame")

            elif data == "agreement":
                w8 = await client.send_message(event.chat_id, "⏳")
                file = r"C:\Bots\commonData\DnD\docs\agreement.txt"
                with open(file, 'r', encoding='utf-8') as f:
                    agreement = f.read()
                buttons = Button.inline("Назад", data="tostart")
                msg = await client.send_message(user_id, agreement, parse_mode="HTML", buttons=buttons)
                ids = [event.message_id, msg.id]
                await status_manager(client, event, ids, "outgame")
                comm = await event.get_message()
                try:
                    await comm.delete()
                except: pass
                try:
                    await w8.delete()
                except:
                    pass

            elif data == "robokassa":
                w8 = await client.send_message(event.chat_id, "⏳")

                await robokassa_page(client, event, user_id)
                await w8.delete()

            elif data.startswith("robobill:"):
                w8 = await client.send_message(event.chat_id, "⏳")
                await robo_bill_page(client, event, user_id, data)
                await w8.delete()


            elif data == "presetlore":
                w8 = await client.send_message(event.chat_id, "⏳")

                msg = await event.get_message()
                if msg.text:  # если обычное текстовое сообщение
                    text = msg.text
                elif msg.media and getattr(msg, 'caption', None):  # если есть медиа и подпись (caption)
                    text = msg.caption
                else:
                    text = '1234567890'
                lore, loreimg = get_lore_preset(text[0:9])
                try:
                    await msg.delete()
                except: pass
                lorepath = r"C:\Bots\commonData\DnD\gamedata"
                filename = f"{event.chat_id}_templore.lore"
                with open(file=os.path.join(lorepath, filename), mode="w", encoding="utf-8") as file:
                    file.write(lore)

                buttons = [
                    [Button.inline("Играем!", data="charcreation")],
                    [Button.inline("Следующий пресет", data="presetlore")],
                    [Button.inline("Создать новый ИИ сеттинг", data="inputlore")]
                ]
                await event.client.send_file(
                    event.chat_id,
                    file=loreimg,
                    caption=lore,
                    buttons=buttons
                )
                await w8.delete()

            elif data == "inputlore":
                msg = await event.get_message()
                try:
                    await msg.delete()
                except: pass
                temp_msg = await event.client.send_message(
                    event.chat_id,
                    """Введи указания для нейросети. Если хочешь случайную генерацию, так и пиши, либо укажи свои пожелания. Например, 'хочу стимпанк сеттинг и чтоб там были культисты' или 'хочу грабить корованы'."""
                )
                save_temp_msg(event.chat_id, code = "loreinput", item = temp_msg.id)
                set_input_mode(event.chat_id,1)

            elif data.startswith("rocketbill:"):
                w8 = await client.send_message(event.chat_id, "⏳")
                await xrocket_bill_page(client, event, user_id, data)
                await w8.delete()

            elif data == "gamecontinue":
                msg = await event.get_message()
                await status_manager(client, event, [msg.id], "ingame")
                if isgame(user_id):
                    set_input_mode(event.chat_id,3)
                try:
                    await msg.delete()
                except:
                    pass

            elif data == "charcreation":
                w8 = await client.send_message(event.chat_id, "⏳")
                msg = await event.get_message()
                try:
                    await msg.delete()
                except:
                    pass
                with open(r"C:\Bots\commonData\DnD\chargen_text.madata", "r", encoding="utf-8") as file:
                    text = file.read()
                buttons = [
                    [Button.inline("Случайная генерация персонажа", data="randomchar")],
                    [Button.inline("Генерация с комментариями", data="yourchar")]
                ]
                pic = r"C:\Bots\commonData\DnD\pics\chargen.jpg"

                await event.client.send_file(
                    event.chat_id,
                    file=pic,
                    caption=text,
                    buttons=buttons
                )

                await w8.delete()

            elif data == "randomchar":
                w8 = await client.send_message(event.chat_id, "⏳")
                msg = await event.get_message()
                try:
                    await msg.delete()
                except:
                    pass
                text = await newchar(event.chat_id)
                buttons = [
                    [Button.inline("Подходит!", data="attrmenu")],
                    [Button.inline("Переделать!", data="randomchar")],
                    [Button.inline("Генерация с комментариями", data="yourchar")]
                ]

                await event.client.send_message(
                    event.chat_id,
                    text,
                    buttons=buttons
                )

                await w8.delete()
            elif data.startswith("react:"):

                user_id = event.chat_id
                filename = f"{user_id}_tempreactions.json"
                folderpath = r"C:\Bots\commonData\DnD\gamedata"
                if not os.path.exists(os.path.join(folderpath, filename)):
                    return
                with open(os.path.join(folderpath, filename), mode="r", encoding="utf-8") as file:
                    reactions = json.load(file)

                code = data.replace("react:", "")

                if code not in reactions:
                    return

                w8 = await client.send_message(event.chat_id, "⏳")
                set_input_mode(event.chat_id, 0)

                await client.send_message(user_id, f"😶 <b>Игрок:</b> {reactions[code]}", parse_mode="html")
                last_move(user_id, reactions[code])
                await gogame(client, event, user_msg=reactions[code])


                set_input_mode(event.chat_id, 3)
                await w8.delete()

            elif data == "yourchar":
                msg = await event.get_message()
                try:
                    await msg.delete()
                except:
                    pass

                temp_msg = await event.client.send_message(
                    event.chat_id,
                    """Введи указания для нейросети. Если хочешь случайную генерацию, так и пиши, либо укажи свои пожелания. Например, 'хочу персонажа-человека, взломщика' или 'хочу грабить корованы'."""
                )
                save_temp_msg(event.chat_id, code="charinput", item=temp_msg.id)
                set_input_mode(event.chat_id, 2)

            elif data == "xrocket":
                w8 = await client.send_message(event.chat_id, "⏳")

                await xrocket_page(client, event, user_id)
                await w8.delete()

            elif data.startswith("attrmenu"):
                w8 = await client.send_message(event.chat_id, "⏳")
                msg = await event.get_message()
                try:
                    await msg.delete()
                except:
                    pass
                parts = data.split(":")

                if len(parts) == 2:
                    attr, value = parts[1], None
                elif len(parts) == 3:
                    attr, value = parts[1], parts[2]
                else:
                    attr, value = None, None

                await attrlist(client=client, user_id=event.chat_id, attr=attr, value=value)
                await w8.delete()

            elif data == "tosummary":
                w8 = await client.send_message(event.chat_id, "⏳")
                msg = await event.get_message()
                try:
                    await msg.delete()
                except:
                    pass
                await summary_on_start(client=client, user_id=event.chat_id, mode=2)

                await w8.delete()

            elif data == "inthegame":
                w8 = await client.send_message(event.chat_id, "⏳")

                msg = await event.get_message()
                try:
                    await msg.delete()
                except:
                    pass
                await send_portal_intro(client,event)
                await gogame(client=client, event=event)
                set_input_mode(event.chat_id, 3)
                await w8.delete()

            elif data == "tostart":
                await startmenu(client=client, event=event, type=0)

            elif data == "store":
                w8 = await client.send_message(event.chat_id, "⏳")
                await store(client=client, event=event, user_id=user_id)

                await w8.delete()

            elif data == "promo":
                await ask_promo(client=client, event=event, user_id=user_id)

            elif data == "referal":
                await referal_info(client=client, event=event, user_id=user_id)

        finally:
            await release_lock(request_id)

    @client.on(events.NewMessage(pattern='/roll_d20'))
    async def roll20_handler(event):
        sender = event.sender
        username = sender.username
        user_id = sender.id

        w8 = await client.send_message(user_id, "⏳")
        try:
            await event.message.delete()
        except:
            pass

        roll_result = random.randint(1, 20)

        info.put(f"{username} ({user_id}) только что зароллил d20: {roll_result}")

        msg = await roll(client, event, roll_result, 20)
        await w8.delete()
        await status_manager(client, event, [msg.id], "outgame")
        raise StopPropagation

    @client.on(events.NewMessage(pattern='/roll_d10'))
    async def roll10_handler(event):
        sender = event.sender
        username = sender.username
        user_id = sender.id
        w8 = await client.send_message(user_id, "⏳")
        try:
            await event.message.delete()
        except: pass

        roll_result = random.randint(0, 9)

        info.put(f"{username} ({user_id}) только что зароллил d10: {roll_result}")

        msg = await roll(client, event, roll_result, 10)
        await w8.delete()
        await status_manager(client, event, [msg.id], "outgame")
        raise StopPropagation

    @client.on(events.NewMessage(pattern='/roll_d12'))
    async def roll12_handler(event):
        sender = event.sender
        username = sender.username
        user_id = sender.id
        w8 = await client.send_message(user_id, "⏳")

        await event.message.delete()

        roll_result = random.randint(1, 12)

        info.put(f"{username} ({user_id}) только что зароллил d12: {roll_result}")

        msg = await roll(client, event, roll_result, 12)
        await w8.delete()
        await status_manager(client, event, [msg.id], "outgame")
        raise StopPropagation

    @client.on(events.NewMessage(pattern='/roll_d8'))
    async def roll8_handler(event):
        sender = event.sender
        username = sender.username
        user_id = sender.id
        w8 = await client.send_message(user_id, "⏳")

        await event.message.delete()

        roll_result = random.randint(1, 8)

        info.put(f"{username} ({user_id}) только что зароллил d8: {roll_result}")

        msg = await roll(client, event, roll_result, 8)
        await w8.delete()
        await status_manager(client, event, [msg.id], "outgame")
        raise StopPropagation

    @client.on(events.NewMessage(pattern='/roll_d4'))
    async def roll4_handler(event):
        sender = event.sender
        username = sender.username
        user_id = sender.id
        w8 = await client.send_message(user_id, "⏳")

        await event.message.delete()

        roll_result = random.randint(1, 4)

        info.put(f"{username} ({user_id}) только что зароллил d4: {roll_result}")

        msg = await roll(client, event, roll_result, 4)
        await w8.delete()
        await status_manager(client, event, [msg.id], "outgame")
        raise StopPropagation

    @client.on(events.NewMessage(pattern='/roll_d6'))
    async def roll6_handler(event):
        sender = event.sender
        username = sender.username
        user_id = sender.id
        w8 = await client.send_message(user_id, "⏳")

        await event.message.delete()

        roll_result = random.randint(1, 6)

        info.put(f"{username} ({user_id}) только что зароллил d8: {roll_result}")

        msg = await roll(client, event, roll_result, 6)
        await w8.delete()
        await status_manager(client, event, [msg.id], "outgame")
        raise StopPropagation

    @client.on(events.NewMessage(pattern='/summary'))
    async def summary(event):
        sender = event.sender
        username = sender.username
        user_id = sender.id
        w8 = await client.send_message(user_id, "⏳")

        await event.message.delete()
        await ingame_summary(client, user_id)
        await w8.delete()
        raise StopPropagation

    @client.on(events.NewMessage(pattern='/campaign_restore'))
    async def campaign_restore(event):
        sender = event.sender
        username = sender.username
        await event.message.delete()
        user_id = sender.id
        w8 = await client.send_message(user_id, "⏳")
        folderpath = r"C:\Bots\commonData\DnD\gamedata"
        filename = f"{user_id}_common_context.json"
        if os.path.isfile(os.path.join(folderpath, filename)):
            with open(os.path.join(folderpath, filename), "r", encoding="utf-8") as file:
                context = json.load(file)
            if len(context) >= 3:
                await restore_game(client, user_id)
                set_input_mode(event.chat_id, 3)

        else:
            message = (f"<b>Начатой игры не найдено, либо вызов функции восстановления произошел на 1 ходу.</b>\n\n"
                    r"На данном этапе возможно только начать новую игру через меню /start !")
            buttons = Button.inline("Закрыть", data="stephome")
            await client.send_message(user_id, message, buttons=buttons, parse_mode="HTML" )
        await w8.delete()
        raise StopPropagation

    @client.on(events.NewMessage(pattern=r'^/start(?:\s+(\d+))?$'))
    async def start_handler(event):
        if not isgame(event.sender.id):
            await delete_all_with_progress(client, event)

        await startmenu(client, event, type =1)


        raise StopPropagation

    @client.on(events.NewMessage(func=lambda e: not e.message.media))
    async def text_handler(event):
        ids = []
        orig = event
        if get_input_mode(orig.sender.id) != 3:
            await event.delete()
        ids.append(event.message.id)
        sender = orig.sender
        user_id = sender.id

        w8 = await client.send_message(user_id, "⏳")

        if get_input_mode(user_id) == 1:
            set_input_mode(user_id, 0)
            temp_msg = load_temp_msg(user_id, "loreinput")
            try:
                await client.delete_messages(user_id, temp_msg)
            except:
                info.put("Неудачная попытка удаления сообщения")
                pass
            buttons = [
                [Button.inline("Играем!", data="charcreation")],
                [Button.inline("Использовать пресет", data="presetlore")],
                [Button.inline("Хочу переделать!", data="inputlore")]
            ]
            lore = await newlore(orig.text, event.chat_id)
            await event.client.send_message(
                event.chat_id,
                lore,
                buttons=buttons
            )

        elif get_input_mode(user_id) == 2:
            set_input_mode(user_id, 0)
            temp_msg = load_temp_msg(user_id, "charinput")
            try:
                await client.delete_messages(user_id, temp_msg)
            except Exception as e:
                info.put(f"Неудачная попытка удаления сообщения: {e}")
                pass
            buttons = [
                [Button.inline("Подходит!", data="attrmenu")],
                [Button.inline("Нужно переделать", data="yourchar")],
                [Button.inline("Случайная генерация", data="randomchar")]
            ]
            character = await newchar(text = orig.text, user_id = event.chat_id)
            await event.client.send_message(
                event.chat_id,
                character,
                buttons=buttons
            )

        elif get_input_mode(user_id) == 3:
            set_input_mode(user_id, 0)
            last_move(user_id, orig.text)
            await gogame(client, event, user_msg=orig.text)
            set_input_mode(user_id, 3)

        elif get_input_mode(user_id) == 666:
            await promocode_job(client, event, user_id, code=orig.text)
            set_input_mode(user_id, 0)
            folderpath = r"C:\Bots\commonData\DnD\gamedata"
            filename = f"{user_id}_askpromotemp.temp"
            with open(os.path.join(folderpath, filename), "r", encoding="utf-8") as file:
                id = int(file.read())
            try:
                await client.delete_messages(user_id, id)
            except Exception as e:
                info.put(f"Неудачная попытка удаления сообщения: {e}")
                pass

        await w8.delete()
        raise StopPropagation

    await client.run_until_disconnected()

def run_main_sync(l_queue):
    set_log_queue(l_queue)


    info.put("Процесс бота успешно запущен и настроил логирование.")
    asyncio.run(main(l_queue))