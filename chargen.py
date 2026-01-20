import json
import os
from yandex_cloud_ml_sdk import YCloudML
from alarm import alarm, info
from no_context_utils import getlorepath, file_exists

#сохраняет текст персонажа
def save_character(character, user_id):
    folderpath = r"C:\Bots\commonData\DnD\gamedata"
    filename = f"{user_id}_tempcharacter.lore"
    with open(file=os.path.join(folderpath, filename), mode="w", encoding="utf-8") as file:
        file.write(character)

#сохраняет контекст
def save_char_context(user_id, text=None, message=None, character=None):
    params = [text, message, character]
    # Проверяем сколько параметров не None
    if sum(p is not None for p in params) != 1:
        return  # Выход, если больше одного параметра передано
    filename = f"{user_id}_charcontext.json"
    folderpath = r"C:\Bots\commonData\DnD\gamedata"

    if file_exists(os.path.join(folderpath, filename))==False:
        if message is None:
            a= getCharacter(user_id)
            return
        else:
            a= getCharacter(user_id, text=message)
            return

    if text is not None:
        alarm.put("вспышка справа")
        with open(os.path.join(folderpath, filename), mode="w", encoding="utf-8") as file:
            json.dump(text, file, ensure_ascii=False, indent=4)
    elif message is not None and file_exists(filename):
        with open(os.path.join(folderpath, filename), mode="r+", encoding="utf-8") as file:
            prev_context = json.load(file)
            prev_context.append({"role": "user", "text": f"{message}"})
            file.seek(0)  # Переместить указатель в начало файла
            file.truncate(0)
            json.dump(prev_context, file, ensure_ascii=False, indent=4)
    elif character is not None and file_exists(filename):
        with open(os.path.join(folderpath, filename), mode="r+", encoding="utf-8") as file:
            prev_context = json.load(file)
            prev_context.append({"role": "assistant", "text": f"{character}"})
            file.seek(0)  # Переместить указатель в начало файла
            file.truncate(0)
            json.dump(prev_context, file, ensure_ascii=False, indent=4)

    with open(os.path.join(folderpath, filename), mode="r", encoding="utf-8") as file:
        print("файл после сейва")
        print(json.load(file))
    return

#выдает сохраненный контекст
def get_char_context(user_id):
    folderpath = r"C:\Bots\commonData\DnD\gamedata"
    filename = f"{user_id}_charcontext.json"
    with open(os.path.join(folderpath, filename), mode="r", encoding="utf-8") as file:
        return json.load(file)

#выдает автора последнего сообщения в контексте
def get_char_context_status(user_id):
    folderpath = r"C:\Bots\commonData\DnD\gamedata"
    filename = f"{user_id}_charcontext.json"
    with open(os.path.join(folderpath, filename), mode="r", encoding="utf-8") as file:
        context = json.load(file)
    if context[-1]["role"] == "assistant":
        return "assistant"
    elif context[-1]["role"] == "user":
        return "user"
    else:
        return None

#контекст нулевой генерации
def getCharacter(user_id, text="Сгенерируй случайным образом"):
    with open(r"C:\Bots\commonData\DnD\chargenerator.json", "r", encoding='utf-8') as read_file:
        messages = json.load(read_file)
    with open(getlorepath(user_id), "r", encoding='utf-8') as read_file:
        a = read_file.read()
        text = f"""Сеттинг: {a}
            Комментарий: {text}"""
        info.put(text)
        if messages[1]["text"] == "{{generate_random_promt()}}":
            messages[1]["text"] = text
            info.put(f"Запущена генерация персонажа!")

    filename = f"{user_id}_charcontext.json"
    folderpath = r"C:\Bots\commonData\DnD\gamedata"

    with open(os.path.join(folderpath, filename), mode="w", encoding="utf-8") as file:
        json.dump(messages, file, ensure_ascii=False, indent=4)

    return messages

#полная генерация нужного контекста
def chargen_create_context(user_id, text=None):
    default_text = "Сгенерируй случайным образом"
    folderpath = r"C:\Bots\commonData\DnD\gamedata"
    filename = f"{user_id}_charcontext.json"
    if file_exists(filename):
        with open(os.path.join(folderpath, filename), mode="r", encoding="utf-8") as file:
            context = json.load(file)
        if context[-1]["role"] == "assistant":
            info.put("При генерации контекста обнаружен неправильный последний отправитель. Файл сброшен")
            if text is None:
                return getCharacter(user_id)
            else:
                return getCharacter(user_id, text=text)
        elif context[-1]["role"] == "user":
            if len(context) == 2:
                return context
            elif default_text in context[-3]["text"] and text is None:
                return context
            elif default_text in context[-3]["text"] and text is not None:
                alarm.put("вспышка слева")
                return getCharacter(user_id, text=text)
            elif default_text not in context[-3]["text"] and text is not None:
                return context
            else:
                alarm.put("третья вспышка")
                alarm.put(context[-3]["text"])
                alarm.put(default_text)
                return getCharacter(user_id)
        else:
            info.put("Файл контекста генератора персонажа побился. Сброс")
            return getCharacter(user_id)
    else:
        if text is None:
            return getCharacter(user_id)
        else:
            return getCharacter(user_id, text=text)

def delete_chargen(user_id):
    folderpath = r"C:\Bots\commonData\DnD\gamedata"
    filename = f"{user_id}_charcontext.json"
    fullpath = os.path.join(folderpath, filename)
    if file_exists(fullpath):
        os.remove(fullpath)

#запуск генерации
async def newchar(user_id, text = None):
    default_text = "Сгенерируй случайным образом"
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
        if text is not None:
            save_char_context(user_id, message=text)
            messages = chargen_create_context(user_id, text=text)
            info.put(messages)
        else:
            print (1)
            save_char_context(user_id, message=default_text)
            print(2)
            messages = chargen_create_context(user_id)
            print(3)
            alarm.put(messages)
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
            character = alternative.text
            save_character(character, user_id)
            save_char_context(user_id, character=character)
            return character
        info.put("Ошибка генерации персонажа")
        return "Ошибка генерации персонажа"
    except:
        alarm.put("Ошибка обработки результата генерации")
        return None