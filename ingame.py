import asyncio
import concurrent.futures
import json
import os
import random
import re

from telethon import Button
from yandex_cloud_ml_sdk import YCloudML
from alarm import info, alarm
from anticensor import checkcensor

from sql_utils import set_moves_value, get_moves_value, set_input_mode, add_moves_value, get_ref_link, status_manager, \
    get_dnd_status


async def roll(client, event, num, dim):
    sender = event.sender
    user_id = sender.id
    base_path = r"C:\Bots\commonData\DnD\videorolls"

    # Формируем имя файла по паттерну
    video_filename = f"d{dim}-{num}.mp4"
    video_path = os.path.join(base_path, video_filename)

    # Отправляем video note с нужным видео
    for i in range (5):
        try:
            msg = await client.send_file(
                event.chat_id,
                video_path,
                video_note=True
            )
            return msg
        except:
            info.put("Ошибка отправки ролла!")
            buttons = [Button.inline("Назад", data="stephome")]
            await client.send_message(event.chat_id, "Вы заблокировали отправку голосовых сообщений и не можете увидеть ролл", buttons=buttons)
    return None

# создает либо дополняет файл текстовой истории, не возвращает
def savetextstory(user_id, person:str, text:str):
    folderpath = r"C:\Bots\commonData\DnD\gamedata"
    text_story = f"{user_id}_textstory.dnd"
    if os.path.isfile(os.path.join(folderpath, text_story)):
        with open(os.path.join(folderpath, text_story), "a", encoding="utf-8") as f:
            f.write(f">@{person}: {text}\n")
        info.put(f"{user_id}: файл текстовой истории игры дополнен.")
    else:
        with open(os.path.join(folderpath, text_story), "w", encoding="utf-8") as f:
            f.write(f">@{person}: {text}\n")
        info.put(f"{user_id}: файл текстовой истории игры создан.")

# создает стартовый контекст общего диалога игры, записывает в файл, не возвращает
def first_common_gen(user_id):
    info.put(f"{user_id}: запущена компиляция начального контекста")
    generator = r"C:\Bots\commonData\DnD\commongenerator.json"
    filename = f"{user_id}_common_context.json"
    folderpath = r"C:\Bots\commonData\DnD\gamedata"
    lore = f"{user_id}_templore.lore"
    character = f"{user_id}_tempcharacter.lore"
    with open(generator, "r", encoding="utf-8") as file:
        context = json.load(file)
    with open(os.path.join(folderpath, lore), mode="r", encoding="utf-8") as file:
        lore = file.read()
    with open(os.path.join(folderpath, character), mode="r", encoding="utf-8") as file:
        character = file.read()
    text = f"СЕТТИНГ:{lore};ДАННЫЕ ПЕРСОНАЖА:{character}"
    msg = {
        "role":"user",
        "text":text
    }
    savetextstory(user_id, "Игрок", text)
    context.append(msg)
    with open(os.path.join(folderpath, filename), mode="w", encoding="utf-8") as file:
        json.dump(context, file, ensure_ascii=False, indent=4)
    info.put(f"{user_id}: завершена компиляция начального контекста, записан файл")

# отправка контекста нейронке, возвращает ответ
# КОНТЕКСТ ПОДАЕТСЯ КОРРЕКТНО!!!
async def generate(user_id, context, tempt = 0.3):
    try:
        with open(r"C:\Bots\commonData\DnD\folderid.madata", 'r', encoding='utf-8') as file:
            folder_id = file.read()
        with open(r"C:\Bots\commonData\DnD\yapiid.madata", 'r', encoding='utf-8') as file:
            yapiid = file.read()
    except Exception as e:
        alarm.put(f"{user_id}: ошибка в блоке чтения промт и Яндекс данных: {e}")
        return None

    try:
        info.put(f"{user_id}: запуск генерации ИИ, контекст {context}")
        sdk = YCloudML(folder_id=folder_id, auth=yapiid)
        model = sdk.models.completions("yandexgpt", model_version="rc")
        model = model.configure(temperature=tempt)
    except Exception as e:
        alarm.put(f"Ошибка Яндекс авторизации: {e}")
        return None

    max_attempts = 5
    timeout_sec = 20

    loop = asyncio.get_event_loop()

    def run_model():
        return model.run(context)

    for attempt in range(1, max_attempts + 1):
        try:
            future = loop.run_in_executor(None, run_model)
            result = await asyncio.wait_for(future, timeout=timeout_sec)

            try:

                for alternative in result:
                    text = alternative.text

                    if "```" in text:
                        text.replace("```", "")
                    if "html" in text:
                        text.replace("html", "")

                    await checkcensor(user_id,text)
                    return text
                return None
            except Exception as e:
                alarm.put(f"{user_id}: ошибка обработки результата генерации: {e}")
                return None

        except asyncio.TimeoutError:
            alarm.put(f"{user_id}: таймаут ответа превышен (попытка {attempt})")
            if attempt == max_attempts:
                alarm.put(f"{user_id}: превышено максимальное число попыток из-за таймаута")
                return None
            # Продолжить попытки
            continue
        except Exception as e:
            alarm.put(f"{user_id}: ошибка получения генерации: {e}")
            alarm.put(context)
            return None

    return None

# вспомогательная
def extract_roll_texts(text):
    # Ищем текст между 'ROLL_TEXT:' и 'ROLL:', не включая сами эти подстроки
    pattern = r'ROLL_TEXT:(.*?)ROLL:'
    matches = re.findall(pattern, text, re.DOTALL)
    # Обрезаем пробелы вокруг и возвращаем список
    return [match.strip() for match in matches]

# вспомогательная
def parse_reaction_substrings(text):

    idx = text.find("REACTION:")
    if idx == -1:
        return []  # Если подстрока не найдена, возвращаем пустой список
    start_idx = idx + len("REACTION:")
    # Берём оставшуюся часть строки после "REACTION:"
    substring = text[start_idx:].strip()
    # Разделяем по двоеточию и возвращаем список
    return [part.strip() for part in substring.split(':') if part.strip()]

# READY - вспомогательная
def parse_roll_substrings(text):
    # Ищем позицию "ROLL:"
    idx = text.find("ROLL:")
    if idx == -1:
        return []  # Если подстрока не найдена, возвращаем пустой список
    start_idx = idx + len("ROLL:")
    # Берём оставшуюся часть строки после "ROLL:"
    substring = text[start_idx:].strip()
    # Разделяем по двоеточию и возвращаем список
    return [part.strip() for part in substring.split(':') if part.strip()]

# Помощник - проверяет на адекватность ответ пользователя (из файла), используя ИИ.
# Дополняет файл контекста, файл истории. Возвращает 0 если ошибка, 1 если пропуск броска, список бросков если они есть
# использовать только после записи user!!!
async def check_move(user_id):
    info.put(f"{user_id}: запуск проверки хода")
    filename = f"{user_id}_common_context.json"
    roll_text_file = f"{user_id}_temp_roll_text.temp"
    attrs_file = f"{user_id}_attrs.json"
    folderpath = r"C:\Bots\commonData\DnD\gamedata"
    contextpath = r"C:\Bots\commonData\DnD\movecheckgenerator.json"
    with open(os.path.join(folderpath, filename), mode="r", encoding="utf-8") as file:
        context = json.load(file)
    with open(os.path.join(folderpath, attrs_file), mode="r", encoding="utf-8") as file:
        attrsjson = json.load(file)
    attrs = "Характеристики персонажа: "
    for key, value in attrsjson.items():
        attrs += f"{key}:{value}\n"
    if len(context) == 2:
        info.put(f"{user_id}: проверка хода отменена")
        return 1
    if "Характеристики персонажа: " not in context[1]["text"]:
        context[1]["text"] = context[1]["text"] + attrs
    workspace = [context[1],context[-2],context[-1]]
    message = ''
    for item in workspace:
        message = message + f"{item["role"]}:\n{item["text"]}\n"
    with open(contextpath, "r", encoding="utf-8") as file:
        context_move = json.load(file)
    context_move.append({
        "role":"user",
        "text":message
    })
    analysis = await generate(user_id, context_move)

    with open(os.path.join(folderpath, "analysis.txt"), "w", encoding="utf-8") as file:
        file.write(analysis)
    if "PASS" in analysis:
        info.put(f"{user_id}: ответ не подразумевает бросков дайса")
        return 1
    elif "ERROR" in analysis:
        info.put(f"{user_id}: ответ пользователя в оффтопе")
        return 0
    elif "ROLL_TEXT:" in analysis and "ROLL:" in analysis:
        info.put(f"{user_id}: разбор необходимых бросков...")
        roll_texts_list = extract_roll_texts(analysis)
        roll_text = "\n".join(roll_texts_list)
        savetextstory(user_id, "Помощник", roll_text)
        context[-1]["text"] += roll_text
        dices = parse_roll_substrings(analysis)
        dices_to_roll = []
        results = ["\n\n"]
        for dice in dices:
            if dice[1:] in ["4","6","8","10","12","20"]:
                if dice[1:] == "10":
                    n = random.randint(0,9)
                else:
                    n = random.randint(1,int(dice[1:]))
                    if n<int(int(dice[1:])//2):
                        n = random.randint(1, int(dice[1:]))
                results.append(f"Бросаю {dice}, результат {n}\n")
                dices_to_roll.append(f"{dice}_{n}")
        for result in results:
            context[-1]['text'] += result
            roll_text += result
        with open(r"C:\Bots\commonData\DnD\rollresultgenerator.json", "r", encoding="utf-8") as file:
            checkresult = json.load(file)
        message = message + roll_text
        print (message)
        checkresult.append({"role":"user","text":message})
        summary = await generate(user_id, checkresult)

        context[-1]['text'] += f"\n{summary}\n"
        roll_text += f"\n{summary}\n"

        with open(os.path.join(folderpath, roll_text_file), mode="w", encoding="utf-8") as file:
            file.write(f"<b>🎲 Помощник: </b> {roll_text}")
        with open(os.path.join(folderpath, filename), mode="w", encoding="utf-8") as file:
            json.dump(context, file, ensure_ascii=False, indent=4)
        info.put(f"{user_id}: файлы контекста и истории обновлены информацией о бросках")
        return dices_to_roll
    else:
        info.put(f"{user_id}: неизвестная ошибка помощника (ответ: '{analysis}')")
        return 0

# Компрессор - создает сжатый пересказ сюжета в одном из ответов для оптимизации контекста, используя ИИ.
# не меняет файл общего контекста, создает файл компрессора и обновляет его на основании самого файла компрессора
# (сжимает себя же), нужна отдельная запись нового контекста в созданный файл компрессора после его создания.
async def common_context_compressor(user_id):
    info.put(f"{user_id}: запуск компрессора контекста...")
    filename = f"{user_id}_common_context.json"
    filename_comp = f"{user_id}_common_context_compressor.json"
    folderpath = r"C:\Bots\commonData\DnD\gamedata"
    compressor_path = r"C:\Bots\commonData\DnD\compressorgenerator.json"
    if not os.path.isfile(os.path.join(folderpath, filename_comp)):
        with open(os.path.join(folderpath, filename), mode="r", encoding="utf-8") as file:
            context = json.load(file)
        if len(context) < 8:
            info.put(f"{user_id}: компрессия не требуется!")
            return
        workspace = context[3:6]
        to_compress = ""
        for item in workspace:
            to_compress = to_compress + "\n" + item["role"] + ": " + item["text"]
        with open(compressor_path, mode="r", encoding="utf-8") as file:
            compressor_context = json.load(file)
        compressor_context.append({
            "role":"user",
            "text": to_compress
        })
        compressed_text = await generate(user_id, compressor_context)

        workspace = context[:4]+context[6:]
        workspace[3]["text"] = "@optimized:" + compressed_text
        with open(os.path.join(folderpath,filename_comp), mode="w", encoding="utf-8") as file:
            json.dump(workspace, file, ensure_ascii=False, indent=4)
        info.put(f"{user_id}: создан компрессор-контекст!")
    else:
        with open(os.path.join(folderpath,filename_comp), mode="r", encoding="utf-8") as file:
            context = json.load(file)
        if len(context) < 8:
            info.put(f"{user_id}: компрессия не требуется (есть файл компрессора)!")
            return
        workspace = context[4:6]
        to_compress = ""
        for item in workspace:
            to_compress = to_compress + "\n" + item["role"] + ": " + item["text"]
        with open(compressor_path, mode="r", encoding="utf-8") as file:
            compressor_context = json.load(file)
        compressor_context.append({
            "role":"user",
            "text": to_compress
        })
        compressed_text = await generate(user_id, compressor_context)

        workspace = context[:4]+context[6:]
        workspace[3]["text"] = workspace[3]["text"] + " " + compressed_text
        with open(os.path.join(folderpath,filename_comp), mode="w", encoding="utf-8") as file:
            json.dump(workspace, file, ensure_ascii=False, indent=4)
        info.put(f"{user_id}: обновлен компрессор-контекст!")

# проверяет ответ ИИ, если от игрока нужна реакция, возвращает словарь, где ключ-число, а значение - реакция.
# и записывает во временный файл. Если реакция не подразумевается, возвращает None.
def reaction_checker(user_id, text):
    info.put(f"{user_id}: проверка наличия реакции...")
    if "REACTION:" in text:
        info.put(f"{user_id}: обнаружена возможность реакции!")
        reacts = parse_reaction_substrings(text)
        reacts_dict = {}
        key_gen = [random.randint(1000, 9999) for _ in range(len(reacts))]
        for i, key in enumerate(key_gen):
            reacts_dict[key] = reacts[i]
        filename = f"{user_id}_tempreactions.json"
        folderpath = r"C:\Bots\commonData\DnD\gamedata"
        with open(os.path.join(folderpath, filename), mode="w", encoding="utf-8") as file:
            json.dump(reacts_dict, file, ensure_ascii=False, indent=4)
        info.put(f"{user_id}: реакции загружены во временный файл!")
        return reacts_dict
    else:
        info.put(f"{user_id}: реакций не обнаружено!")
        return None

# дополняет новой записью (подавать готовый словарь) файл компрессора.
def compressor_append(user_id, msg):
    info.put(f"{user_id}: дополняю файл компрессора новой записью")
    folderpath = r"C:\Bots\commonData\DnD\gamedata"
    filename_comp = f"{user_id}_common_context_compressor.json"
    if not os.path.isfile(os.path.join(folderpath, filename_comp)):
        info.put(f"{user_id}: файл компрессора пока не создан!")
        return
    else:
        with open(os.path.join(folderpath, filename_comp), mode="r", encoding="utf-8") as file:
            compressor_context = json.load(file)
        compressor_context.append(msg)
        with open(os.path.join(folderpath, filename_comp), mode="w", encoding="utf-8") as file:
            json.dump(compressor_context, file, ensure_ascii=False, indent=4)
        info.put(f"{user_id}: файл компрессора обновлен!")

# создает либо дополняет файл общего контекста и компрессор, возвращает контекст (если есть компрессор, то его)
# создает и обновляет файл текстовой игры
def save_common_context(user_id, user_msg=None, ai_msg=None):
    info.put(f"{user_id}: сохранение общего контекста...")
    filename = f"{user_id}_common_context.json"
    folderpath = r"C:\Bots\commonData\DnD\gamedata"
    filename_comp = f"{user_id}_common_context_compressor.json"
    gg= True
    if not os.path.isfile(os.path.join(folderpath, filename)):
        info.put(f"{user_id}: файл общего контекста игры не найден, запуск сборщика...")
        first_common_gen(user_id)
        gg = False

    params = [user_msg, ai_msg]
    # Проверяем сколько параметров не None
    if sum(p is not None for p in params) > 1:
        alarm.put("Неправильная подача данных в функцию сохранения контекста!")
        return  # Выход, если больше одного параметра передано

    with open(os.path.join(folderpath, filename), mode="r", encoding="utf-8") as file:
        context = json.load(file)
    if gg == False:
        return context

    if user_msg is not None:
        if context[-1]["role"] != "user":
            msg = {
                "role":"user",
                "text":user_msg
            }
            context.append(msg)
            compressor_append(user_id, msg)
        else:
            alarm.put("Ошибка сохранения контекста, неправильно подан параметр USER")
    elif ai_msg is not None:
        if context[-1]["role"] != "assistant":
            msg = {
                "role":"assistant",
                "text":ai_msg
            }
            context.append(msg)
            compressor_append(user_id, msg)
        else:
            alarm.put("Ошибка сохранения контекста, неправильно подан параметр ASSISTANT")

    with open(os.path.join(folderpath, filename), mode="w", encoding="utf-8") as file:
        json.dump(context, file, ensure_ascii=False, indent=4)
    with open(os.path.join(folderpath, filename), mode="r", encoding="utf-8") as file:
        context = json.load(file)
    if context[-1]["role"] == "assistant":
        savetextstory(user_id, "Мастер", context[-1]["text"])
    else:
        savetextstory(user_id, "Игрок", context[-1]["text"])
    info.put(f"{user_id}: обновление общего контекста записано в файл")
    if os.path.isfile(os.path.join(folderpath, filename_comp)):
        with open(os.path.join(folderpath, filename_comp), mode="r", encoding="utf-8") as file:
            context = json.load(file)
    return context

def delete_last_usercontext(user_id):
    folderpath = r"C:\Bots\commonData\DnD\gamedata"
    gen = r"C:\Bots\commonData\DnD\restoregenerator.json"
    filename = f"{user_id}_common_context.json"
    filename_comp = f"{user_id}_common_context_compressor.json"

    if os.path.isfile(os.path.join(folderpath, filename_comp)):
        with open(os.path.join(folderpath, filename_comp), mode="r", encoding="utf-8") as file:
            compressor_context = json.load(file)
        with open(os.path.join(folderpath, filename), mode="r", encoding="utf-8") as file:
            common_context = json.load(file)
        if compressor_context[-1]["role"] == "user":
            compressor_context = compressor_context[:-1]
            common_context = common_context[:-1]
            with open(os.path.join(folderpath, filename_comp), mode="w", encoding="utf-8") as file:
                json.dump(compressor_context, file, ensure_ascii=False, indent=4)
            with open(os.path.join(folderpath, filename), mode="w", encoding="utf-8") as file:
                json.dump(common_context, file, ensure_ascii=False, indent=4)
    else:
        with open(os.path.join(folderpath, filename), mode="r", encoding="utf-8") as file:
            common_context = json.load(file)
        if common_context[-1]["role"] == "user":
            common_context = common_context[:-1]

            with open(os.path.join(folderpath, filename), mode="w", encoding="utf-8") as file:
                json.dump(common_context, file, ensure_ascii=False, indent=4)

async def gogame (client, event, user_msg= None):
    def extract_before_reaction(s):
        index = s.find("REACTION")
        if index == -1:
            return s
        else:
            return s[:index]
    user_id = event.sender.id
    tokens = get_moves_value(user_id, "movecoin")
    if tokens < 1:
        outmoves = r"C:\Bots\commonData\DnD\pics\outmoves.png"
        freeze_msg = f"{user_id}_frozen_msg.temp"
        folderpath = r"C:\Bots\commonData\DnD\gamedata"
        buttons = [Button.inline("Получить еще ходы", data=f"store")]
        with open(os.path.join(folderpath,freeze_msg), mode="w", encoding="utf-8") as file:
            file.write(user_msg)
        await client.send_file(user_id, file=outmoves, caption="<b>У тебя закончились ходы. Можно раздобыть еще, цена чашки кофе = одно приключение. \nЖми кнопку ниже, чтобы получить:</b>", buttons=buttons, parse_mode="html")
        return
    move = get_moves_value(event.chat_id, 'move')
    context = save_common_context(user_id, user_msg=user_msg)
    print(f")))))))))))){context}")
    await common_context_compressor(user_id)
    check = await check_move(user_id)
    if check == 0:
        delete_last_usercontext(user_id)
        message = "<b>Мастер с помощником недоуменно переглянулись - о чём это он??</b>\nПопробуй описать свое действие иначе."
        await client.send_message(user_id, message, parse_mode="HTML")
        return
    elif check == 1:
        pass
    elif isinstance(check, list):
        for item in check:
            a,b = item.split("_")
            a = int(a[1:])
            await roll(client, event, b, a)
        roll_text_file = f"{user_id}_temp_roll_text.temp"
        folderpath = r"C:\Bots\commonData\DnD\gamedata"
        with open(os.path.join(folderpath, roll_text_file), mode="r", encoding="utf-8") as file:
            text = file.read()
        await client.send_message(user_id, text, parse_mode="HTML")
        if text[:30] not in context[-1]['text']:
            context[-1]['text'] = context[-1]['text'] + text
    print(f">>>> {context}")
    answer = await generate(user_id,context)

    save_common_context(user_id, ai_msg=answer)
    move = move + 1
    set_moves_value(event.chat_id, 'move', move)
    set_moves_value(event.chat_id, 'movecoin', tokens-1)
    react = reaction_checker(user_id, answer)
    buttons = []
    if isinstance(react, dict):
        for key, value in react.items():
            buttons.append([Button.inline(react[key], data=f"react:{key}")])
        answer = extract_before_reaction(answer)
        await client.send_message(user_id, f"<b>🗣 Мастер: </b>\n{answer}", parse_mode="HTML", buttons=buttons)
    else:
        await client.send_message(user_id, f"<b>🗣 Мастер: </b>\n{answer}", parse_mode="HTML")

#для восстановления игры - обновляет файлы контекста, оставляя последним сообщение ассистента, и отправляет два
#сообщения - с пересказом и последнее от мастера (без форматирования)
async def restore_game(client, user_id):
    folderpath = r"C:\Bots\commonData\DnD\gamedata"
    gen = r"C:\Bots\commonData\DnD\restoregenerator.json"
    filename = f"{user_id}_common_context.json"
    filename_comp = f"{user_id}_common_context_compressor.json"

    if os.path.isfile(os.path.join(folderpath, filename_comp)):
        with open(os.path.join(folderpath, filename_comp), mode="r", encoding="utf-8") as file:
            compressor_context = json.load(file)
        with open(os.path.join(folderpath, filename), mode="r", encoding="utf-8") as file:
            common_context = json.load(file)
        if compressor_context[-1]["role"] == "user":
            compressor_context = compressor_context[:-1]
            common_context = common_context[:-1]
            with open(os.path.join(folderpath, filename_comp), mode="w", encoding="utf-8") as file:
                json.dump(compressor_context, file, ensure_ascii=False, indent=4)
            with open(os.path.join(folderpath, filename), mode="w", encoding="utf-8") as file:
                json.dump(common_context, file, ensure_ascii=False, indent=4)
        gametext = ""
        for item in compressor_context[1:-1]:
            gametext += item["role"] + "\n" + item["text"] + "\n"

        print(gametext)
        with open(gen, mode="r", encoding="utf-8") as file:
            context = json.load(file)
        context.append({"role": "user", "text": gametext})
        print(context)
        brief = await generate(user_id, context)
        ll = r"<b>Пересказ сюжета игры: </b>"
        await client.send_message(user_id, f"{ll}{brief}", parse_mode="HTML")
        await client.send_message(user_id, common_context[-1]["text"], parse_mode="HTML")
    else:
        with open(os.path.join(folderpath, filename), mode="r", encoding="utf-8") as file:
            common_context = json.load(file)
        if common_context[-1]["role"] == "user":
            common_context = common_context[:-1]

            with open(os.path.join(folderpath, filename), mode="w", encoding="utf-8") as file:
                json.dump(common_context, file, ensure_ascii=False, indent=4)
        gametext = ""
        for item in common_context[1:-1]:
            gametext += item["role"] + "\n" + item["text"] + "\n"
        with open(gen, mode="r", encoding="utf-8") as file:
            context = json.load(file)
        context.append({"role": "user", "text": gametext})
        brief = await generate(user_id, context)

        ll = r"<b>Пересказ сюжета игры:<\b> \n"
        await client.send_message(user_id, f"{ll}{brief}", parse_mode="HTML")
        await client.send_message(user_id, common_context[-1]["text"], parse_mode="HTML")

async def store(client, event, user_id):
    buttons = [[Button.inline("XRocket - от 4 USDT", data=f"xrocket"), Button.inline("Robokassa - от 299 RUB", data=f"robokassa")],
               [Button.inline("⭐️ Реферальная программа ⭐️", data=f"referal")],
               [Button.inline("🎁 Ввести промокод 🎁", data=f"promo")],
               [Button.inline("В главное меню", data="tostart")]]
    img = r"C:\Bots\commonData\DnD\pics\store.png"

    move = get_moves_value(user_id, "movecoin")

    text = ("<b>В этом боте внутриигровая валюта - ходы, которые совершают твои персонажи по мере игры.</b>"
            "\nКаждое твое решение отнимает один ход. При первом запуске бота выдается 25 ходов."
            "\n\nПополнить ходы можно:"
            "\n✔️ просто купить, использовав опции ниже - от 299 рублей за 50 ходов."
            "\n✔️ приведя в игру друзей"
            "\n✔️ использовав промокод (которые всегда есть в <a href='https://t.me/masterdiceofficial'>канале разработчика бота</a>)"
            
            f"\n\nСейчас ходов у тебя на балансе: <b>{move}</b>")

    msg = await client.send_file(user_id, file=img, caption=text, parse_mode="HTML", buttons=buttons)

    ids = [event.message_id]
    ids.append(msg.id)

    comm = await event.get_message()
    if get_dnd_status(user_id) != "ingame":
        try:
            await comm.delete()
        except:
            pass

    await status_manager(client, event, ids, "outgame")


def check_promo_code(user_id: int, code: str) -> int | str:
    folder_path = r"C:\Bots\commonData\DnD\proms"
    file_path = os.path.join(folder_path, f'{code}.json')
    if not os.path.isfile(file_path):
        return 0
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    used_set = set(data.get('used', []))
    if user_id in used_set:
        return 1
    used_set.add(user_id)
    data['used'] = list(used_set)
    # Сохраняем обратно в файл
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

    return data.get('to_add')

async def ask_promo(client, event, user_id):
    text = "Введи промокод:"
    msg = await client.send_message(user_id, text)
    folderpath = r"C:\Bots\commonData\DnD\gamedata"
    filename = f"{user_id}_askpromotemp.temp"
    with open(os.path.join(folderpath, filename), "w", encoding="utf-8") as file:
        file.write(str(msg.id))
    ids = [event.message_id]
    ids.append(msg.id)
    await status_manager(client, event, ids, "outgame")

    set_input_mode(user_id, 666)


async def promocode_job(client, event, user_id, code):
    result = check_promo_code(user_id, code)
    buttons = [Button.inline(f"Закрыть", data=f"stephome")]

    if result == 0:
        msg=await client.send_message(user_id, "Такого промокода нет!", buttons=buttons)
    elif result == 1:
        msg=await client.send_message(user_id, "Ты уже вводил этот промокод!", buttons=buttons)
    else:
        msg=await client.send_message(user_id, f"Поздравляю! Тебе начислено {result} ходов!", buttons=buttons)
        add_moves_value(user_id, "movecoin", int(result))
    ids = [msg.id]
    await status_manager(client, event, ids, "outgame")


async def referal_info(client, event, user_id):
    buttons = []
    buttons.append([Button.inline("Назад", data="store")])
    buttons.append([Button.inline(f"В главное меню", data=f"tostart")])
    reflink = get_ref_link(user_id)
    grant_file = r"C:\Bots\commonData\DnD\ref_granting.json"
    with open(grant_file, mode="r", encoding="utf-8") as file:
        grants = json.load(file)

    text = ("В боте действует реферальная программа."
            "\nТвоя ссылка:"
            f"\n\n`{reflink}`"
            f"\n\nВ случае, если новый пользователь придет по твоей ссылке,"
            f"ему будет дополнительно начислено {grants["newbie"]}, а тебе {grants["sender"]} ходов. "
            f"Как только он это сделает, вам обоим придет соответствующее оповещение."
            f"\n\nУдачи!")

    img = r"C:\Bots\commonData\DnD\pics\referal.png"

    msg = await client.send_file(user_id, img, caption=text, parse_mode="Markdown", buttons=buttons)
    ids = [event.message_id]
    ids.append(msg.id)
    await status_manager(client, event, ids, "outgame")
    comm = await event.get_message()
    await comm.delete()


async def send_portal_intro(client, event):
    """Отправляет портал как отдельное сообщение"""
    portal_phrases = [
        "<i>Ты входишь в портал... Мир вокруг меняется...</i>",
        "<i>Ты шагаешь в сияющий портал... Реальность искажается перед глазами...</i>",
        "<i>Вихрь магии поглощает тебя... Новый мир ждёт за гранью...</i>",
        "<i>Портал раскрывается... Знакомые очертания тают в эфире...</i>",
        "<i>Энергия арканы уносит тебя... Тени прошлого сменяются неизвестностью...</i>",
        "<i>Ты переступаешь грань миров... Воздух дрожит от магии...</i>",
        "<i>Свет портала ослепляет... Новый путь открывается перед тобой...</i>"
    ]
    video_path = r"C:\Bots\commonData\DnD\pics\portal.mp4"
    try:
        await client.send_file(event.chat_id, video_path, video_note=True)
    except:
        buttons = [Button.inline("Назад", data="stephome")]
        await client.send_message(event.chat_id,
                                        "Вы заблокировали отправку голосовых сообщений и не можете увидеть портал, а он красивый.",
                                        buttons=buttons)
    await asyncio.sleep(1.5)

    phrase = random.choice(portal_phrases)
    await client.send_message(event.chat_id, phrase, parse_mode='html')