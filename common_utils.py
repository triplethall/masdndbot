import asyncio
import json
import os
import sqlite3

from telethon import Button, events
from telethon.errors import MessageDeleteForbiddenError

from alarm import info, alarm
from sql_utils import is_user_registered, register_user, get_dnd_status, set_dnd_status, add_moves_value, \
    increment_total_refs, status_manager, get_moves_value


#подавать сюда часть текста прошлого сообщения!
def get_lore_preset(begin:str):
    folder_path = r"C:\Bots\commonData\DnD\lore_presets"
    files = [f for f in os.listdir(folder_path) if f.endswith('.lor')]
    files.sort(key=lambda x: int(x.split('_')[0]))

    texts = []
    for filename in files:
        with open(os.path.join(folder_path, filename), 'r', encoding='utf-8') as file:
            text = file.read()
            texts.append(text)
    indexlore = 0
    for i, text in enumerate(texts):
        if text.startswith(begin):
            # Вернуть текст следующего файла, если он есть
            if i + 1 < len(texts):
                indexlore = i+1
            else:
                indexlore = 0

    imgfile = f"{indexlore+1}_img.jpg"
    imgpath = os.path.join(folder_path, imgfile)



    return texts[indexlore], imgpath


def delete_files_with_substring(substr: str):
    folder = r"C:\Bots\commonData\DnD\gamedata"

    # Получаем список файлов в папке
    for filename in os.listdir(folder):
        # Проверяем, содержится ли подстрока в имени файла
        if str(substr) in filename:
            file_path = os.path.join(folder, filename)
            try:
                os.remove(file_path)
                print(f"Удалён файл: {file_path}")
            except Exception as e:
                print(f"Ошибка при удалении файла {file_path}: {e}")

async def startmenu(client, event, type):
    ids = []
    if type == 0:
        user_id = event.chat_id
        comm = await event.get_message()
        await comm.delete()
    elif type == 1:
        await event.message.delete()
        ids.append(event.message.id)
        sender = event.sender
        username = sender.username
        user_id = sender.id
        ref_code = event.pattern_match.group(1)  # Получит None, если параметра нет
        if ref_code:
            if is_user_registered(int(ref_code)):
                buttons = Button.inline("Закрыть", data="stephome")
                if is_user_registered(user_id) == False:
                    with open(r"C:\Bots\commonData\DnD\ref_granting.json", "r", encoding="utf-8") as file:
                        grants = json.load(file)

                    register_user(user_id, username)


                    info.put(f"Новый пользователь: {username} ({user_id}) по реферальной ссылке!")
                    if get_dnd_status(user_id) is None:
                        set_dnd_status(user_id, status="nostarted")
                    await client.send_message(int(ref_code),
                                              f"Пользователь {user_id} перешел по вашей ссылке. Вам начислено {grants["sender"]} шагов.",
                                              buttons=buttons)
                    await client.send_message(user_id,
                                              f"Вы перешли по реферальной ссылке. Вам начислено {grants["newbie"]} шагов.",
                                              buttons=buttons)
                    add_moves_value(user_id, "movecoin", grants["newbie"])
                    add_moves_value(int(ref_code), "movecoin", grants["sender"])
                    increment_total_refs(int(ref_code))


    w8 = await client.send_message(user_id, "⏳")

    if get_dnd_status(user_id) == "nostarted":
        await status_manager(client, event, [], "nogame")
        await status_manager(client, event, [], "nostarted")
    else:
        await status_manager(client, event, [], "ingame")

    buttons = []
    folderpath = r"C:\Bots\commonData\DnD\gamedata"
    filename = f"{user_id}_common_context.json"
    isgame = os.path.isfile(os.path.join(folderpath, filename))
    cm = get_moves_value(user_id, "movecoin")
    if get_dnd_status(user_id) in ["outgame", "ingame"] and isgame == True and cm>0:
        buttons.append([Button.inline(f"🔘 Продолжить игру", data="gamecontinue")])
    if cm>0:
        buttons.append([Button.inline(f"⚔️ Новая игра", data="newgame")])
    else:
        buttons.append([Button.inline(f"Нет ходов", data="store")])
    buttons.append([Button.inline(f"🎲 Правила игры", data="rules"), Button.inline(f"⌨️ Команды бота", data="comslist")])
    buttons.append(
        [Button.url("⭐️ Канал", "t.me/masterdiceofficial"), Button.inline(f"🗝 Получить ходы", data="store")])
    buttons.append([Button.inline(f"📝 Пользовательское соглашение", data="agreement")])
    START_IMG = r"C:\Bots\commonData\DnD\pics\start.png"
    msg = await event.client.send_file(
        event.chat_id,
        START_IMG,
        caption=("<b>Добро пожаловать в TRIPLETHALL's MASTER OF DICE - RPG с ИИ-мастером! "
                 "Уникальные истории, борьба за выживание и твоя судьба в твоих руках. "
                 "Начни своё приключение!</b>\n"
                 "\n"
                 "В случае технических проблем пиши в личные сообщения канала разработчика (кнопка ниже) "
                 "версия 0.5.1"),
        buttons=buttons,
        parse_mode="html"
    )
    await w8.delete()
    ids.append(msg.id)
    await status_manager(client, event, ids, "outgame")

batch_size = 50

async def delete_all_with_progress(client, event):
    async def _delete_task():
        if hasattr(event, 'message') and event.message:
            msg = event.message
        else:
            msg = await event.get_message()
        chat = await event.get_chat()
        current_id = msg.id

        progress_msg = await client.send_message(chat, "⌛")

        for start in range(current_id, 0, -batch_size):
            end = max(start - batch_size + 1, 1)
            message_ids = list(range(end, start + 1))
            message_ids.reverse()

            try:
                await client.delete_messages(chat, message_ids)

            except Exception as e:
                for msg_id in message_ids:
                    try:
                        await client.delete_messages(chat, msg_id)
                    except Exception as e_individual:
                        break
                break

        await progress_msg.delete()



def save_move(user_id, usertext, code):
    folder = r"C:\Bots\commonData\DnD\gamedata"
    filename = f"{user_id}_movetext.text"

    if code == 1:
        with open(os.path.join(folder, filename), "w", encoding="utf-8") as f:
            f.write(usertext)
    if code == 0:
        if os.path.exists(os.path.join(folder, filename)):
            os.remove(os.path.join(folder, filename))


async def is_busy(user_id: int) -> bool:
    """Проверяет os.environ по ключу user_id. Если True — возвращает True.
    Иначе ставит True и возвращает False."""
    key = f"busy_{user_id}"

    # Проверяем environ
    busy_flag = os.environ.get(key, "false").lower() == "true"

    if busy_flag:
        return True  # Уже занят

    # Ставим флаг True
    os.environ[key] = "true"
    return False  # Был свободен

def clear_busy(user_id: int):
    key = f"busy_{user_id}"
    if key in os.environ:
        del os.environ[key]  # Удаляем ключ



def last_move(user_id: int, text: str | None = None) -> str | None:
    BASE_DIR = r"C:\Bots\commonData\DnD\gamedata"

    path = os.path.join(BASE_DIR, f"lastmove_{user_id}.data")

    if text is not None:
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        return None

    if not os.path.exists(path):
        return None

    with open(path, "r", encoding="utf-8") as f:
        return f.read()



def add_blocked(text: str) -> None:
    BLOCKED_PATH = r"C:\Bots\commonData\DnD\blocked.data"
    os.makedirs(os.path.dirname(BLOCKED_PATH), exist_ok=True)

    if os.path.exists(BLOCKED_PATH):
        with open(BLOCKED_PATH, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                data = []
    else:
        data = []

    if text not in data:
        data.append(text)

    with open(BLOCKED_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def last_move_for_check(user_id: int, text: str | None = None) -> str | None:
    BASE_DIR = r"C:\Bots\commonData\DnD\gamedata"

    path = os.path.join(BASE_DIR, f"lastmoveOLD_{user_id}.data")

    if text is not None:
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        return None

    if not os.path.exists(path):
        return None

    with open(path, "r", encoding="utf-8") as f:
        return f.read()
