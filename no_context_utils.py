import json
import os
import pickle

from telethon import Button
from yandex_cloud_ml_sdk import YCloudML
from alarm import alarm, info
from sql_utils import get_moves_value


def file_exists(filename, folder_path=r"C:\Bots\commonData\DnD\gamedata"):
    return os.path.isfile(os.path.join(folder_path, filename))

def getMessages(text:str):

    with open(r"C:\Bots\commonData\DnD\loregenerator.json", "r", encoding='utf-8') as read_file:
        messages = json.load(read_file)
        if messages[1]["text"] == "{{generate_random_promt()}}":

            messages[1]["text"] = text
            info.put(f"Запущена генерация лора новой вселенной!")
    return messages

def getlorepath(user_id):
    folderpath = r"C:\Bots\commonData\DnD\gamedata"
    filename = f"{user_id}_templore.lore"
    return os.path.join(folderpath, filename)



def save_lore(lore,user_id):
    folderpath = r"C:\Bots\commonData\DnD\gamedata"
    filename = f"{user_id}_templore.lore"
    with open(file = os.path.join(folderpath, filename), mode = "w", encoding = "utf-8") as file:
        file.write(lore)



async def newlore(text,user_id):
    try:
        with open(r"C:\Bots\commonData\DnD\folderid.madata", 'r', encoding='utf-8') as file:
            folder_id = file.read()
        with open(r"C:\Bots\commonData\DnD\yapiid.madata", 'r', encoding='utf-8') as file:
            yapiid = file.read()
    except:
        alarm.put("Ошибка в блоке чтения промт и Яндекс данных")

    try:
        info.put("Запуск генерации ИИ")
        sdk = YCloudML(folder_id=folder_id, auth=yapiid)
        model = sdk.models.completions("yandexgpt", model_version="rc")
        model = model.configure(temperature=0.3)
    except:
        alarm.put("Ошибка Яндекс авторизации")
    try:
        messages = getMessages(text)
        info.put(messages)
    except:
        alarm.put("Ошибка подгрузки промта")
    try:
        result = model.run(messages)
        info.put("Успешно получен результат генерации")
        print(result)
    except:
        alarm.put("Ошибка получения генерации")

    try:
        for alternative in result:
            lore = alternative.text
            save_lore(lore,user_id)
            return lore
        return None
    except:
        alarm.put("Ошибка обработки результата генерации")
        return None

def save_temp_msg(user_id, code, item):
    folderpath = r"C:\Bots\commonData\DnD\gamedata"
    filename = f"{user_id}_{code}.json"
    with open(os.path.join(folderpath, filename), 'wb') as file:
        pickle.dump(item, file)

def load_temp_msg(user_id, code):
    folderpath = r"C:\Bots\commonData\DnD\gamedata"
    filename = f"{user_id}_{code}.json"
    fullpath = os.path.join(folderpath, filename)
    with open(fullpath, 'rb') as file:
        msg = pickle.load(file)
    os.remove(fullpath)
    return msg

def saveattrs(user_id, attribute=None, value=None):

    folderpath = r"C:\Bots\commonData\DnD\gamedata"
    filename = f"{user_id}_attrs.json"
    if file_exists(filename) == False:
        with open(os.path.join(folderpath, filename), 'w') as file:
            nole = {
                "strength": 0,
                "dexterity": 0,
                "constitution": 0,
                "intelligence": 0,
                "wisdom": 0,
                "charisma": 0
            }
            json.dump(nole, file)

    with open(os.path.join(folderpath, filename), 'r+') as file:
        book = json.load(file)
        if attribute is not None and value is not None:
            info.put(f"Файл записан {attribute} = {value}")
            book[attribute] = int(value)
            file.seek(0)  # Переместить указатель в начало файла
            file.truncate(0)
            json.dump(book, file)
            return book
        elif attribute is None or value is None:
            info.put("SAVEATTR отработал без аргументов для записи")
            return book
        return book


def get_attrs(user_id):
    folderpath = r"C:\Bots\commonData\DnD\gamedata"
    filename = f"{user_id}_attrs.json"
    with open(os.path.join(folderpath, filename), 'r') as file:
        return json.load(file)

def attrsrenew(user_id):
    folderpath = r"C:\Bots\commonData\DnD\gamedata"
    filename = f"{user_id}_attrs.json"
    if file_exists(filename):
        os.remove(os.path.join(folderpath, filename))
        info.put("Файл аттрибутов сброшен!")
    else:
        info.put("Файл, который нужно удалить, отсутствует!")

rustats = {
        "strength": "💪 Cила",
        "dexterity": "🎯 Ловкость",
        "constitution": "🫀 Телосложение",
        "intelligence": "🎓 Интеллект",
        "wisdom": "🦉 Мудрость",
        "charisma": "🎩 Харизма"
    }

async def attrlist(client, user_id, attr=None, value=None):
    total_points = 72
    base_stats = {15, 14, 13, 12, 10, 8}

    with open(r"C:\Bots\commonData\DnD\attr_text.madata", "r", encoding="utf-8") as file:
        text = file.read()

    if attr == "null":
        attrsrenew(user_id)
        book = saveattrs(user_id)
    else:
        book = saveattrs(user_id, attr, value)

    buttons = []

    for key, item in book.items():
        if int(item) in base_stats:
            base_stats.remove(int(item))

    if len(base_stats) > 1:
        for key, item in book.items():
            buttons.append([Button.inline(f"{rustats[key]} = {book[key]}", data=f"attrmenu:{key}")])
            if item == 0 and attr == key:
                keys = []
                for n in sorted(base_stats):
                    keys.append(Button.inline(f"+{n}", data=f"attrmenu:{key}:{n}"))
                buttons.append(keys)
    if len(base_stats) < 6:
        buttons.append([Button.inline(f"Сброс", data=f"attrmenu:null")])
    if len(base_stats) <= 1:
        appendix = "\n**Выбранные характеристики:**"
        for key, item in book.items():
            if item == 0:
                book[key] = next(iter(base_stats))
                book = saveattrs(user_id, attribute = key, value = book[key])
            appendix = appendix + f"\n**{rustats[key]}: {book[key]}**"
        text += appendix
        buttons.append([Button.inline(f"Готово", data=f"tosummary")])



    await client.send_message(user_id, text, buttons=buttons)

def remove_stars(text: str) -> str:
    return text.replace("*", "")

async def summary_on_start(client, user_id, mode=3):
    folderpath = r"C:\Bots\commonData\DnD\gamedata"
    attrsfile = f"{user_id}_attrs.json"
    lore = f"{user_id}_templore.lore"
    character = f"{user_id}_tempcharacter.lore"
    with open(file=os.path.join(folderpath, lore), mode="r", encoding="utf-8") as file:
        lore_text = remove_stars(file.read())
    with open(file=os.path.join(folderpath, character), mode="r", encoding="utf-8") as file:
        character_text = remove_stars(file.read())
    appendix = ""
    with open(file=os.path.join(folderpath, attrsfile), mode="r", encoding="utf-8") as file:
        book = json.load(file)
    for key, item in book.items():
        appendix = appendix + f"<b>{rustats[key]}: {book[key]}</b>\n"
    if mode == 1:
        buttons = [Button.inline(f"Закрыть", data=f"gamecontinue")]
        await client.send_message(user_id, lore, buttons=buttons)
        character += appendix
        await client.send_message(user_id, character, buttons=buttons)
    if mode == 2:
        message = (f"<b>Выбранные настройки игры:</b>"
                   f"\n<b>1. Сеттинг:</b>"
                   f"<blockquote expandable>{lore_text}</blockquote>"
                   f"\n\n<b>2. Персонаж:</b>"
                   f"<blockquote expandable>{character_text}</blockquote>"
                   f"\n\n<b>3. Выбранные характеристики:</b>"
                   f"<blockquote>{appendix}</blockquote>"
                   )
        buttons = [
            [Button.inline(f"Начать игру!", data=f"inthegame")],
            [Button.inline(f"Нет, хочу другой сеттинг!", data=f"newgame")],
            [Button.inline(f"Нет, хочу другого персонажа!", data=f"charcreation")],
            [Button.inline(f"Нет, хочу поменять характеристики!", data=f"attrmenu")]
        ]
        await client.send_message(user_id, message, buttons=buttons, parse_mode="html")

        if mode ==3:
            return

async def ingame_summary(client, user_id):
    folderpath = r"C:\Bots\commonData\DnD\gamedata"
    context = f"{user_id}_common_context.json"
    attrsfile = f"{user_id}_attrs.json"
    lore = f"{user_id}_templore.lore"
    character = f"{user_id}_tempcharacter.lore"
    if os.path.isfile(os.path.join(folderpath, context)):
        with open(file=os.path.join(folderpath, lore), mode="r", encoding="utf-8") as file:
            lore_text = remove_stars(file.read())
        with open(file=os.path.join(folderpath, character), mode="r", encoding="utf-8") as file:
            character_text = remove_stars(file.read())
        appendix = ""
        with open(file=os.path.join(folderpath, attrsfile), mode="r", encoding="utf-8") as file:
            book = json.load(file)
        for key, item in book.items():
            appendix = appendix + f"<b>{rustats[key]}: {book[key]}</b>\n"

        buttons = [Button.inline(f"Закрыть", data=f"stephome")]
        move = get_moves_value(user_id=user_id, field_name="move")
        coins = get_moves_value(user_id=user_id, field_name="movecoin")

        message = (f"<b>Текущий ход #{move}</b>"
                   f"\n<b>Доступно ходов: {coins}</b>"
                   f"\n<b>Данные игры:</b>"
                   f"\n<b>1. Сеттинг:</b>"
                   f"<blockquote expandable>{lore_text}</blockquote>"
                   f"\n\n<b>2. Персонаж:</b>"
                   f"<blockquote expandable>{character_text}</blockquote>"
                   f"\n\n<b>3. Выбранные характеристики:</b>"
                   f"<blockquote>{appendix}</blockquote>"
                   )

        await client.send_message(user_id, message, buttons=buttons, parse_mode="html")
    else:
        buttons = [Button.inline(f"Закрыть", data=f"stephome")]
        await client.send_message(user_id, "<b>Это меню работает только при наличии начатой кампании</b>", buttons=buttons, parse_mode="html")