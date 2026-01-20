import json
import os

from alarm import info
from common_utils import last_move, add_blocked, last_move_for_check
from sql_utils import add_moves_value

BASE_DIR = r"C:\Bots\commonData\DnD\gamedata"

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

async def checkcensor(user_id,result):
    if len(result) > 180:
        return
    redflag = 0
    with open(r"C:\Bots\commonData\DnD\censor_policy\patterns1.text", "r", encoding="utf-8") as file:
        patterns = file.read().splitlines()
    with open(r"C:\Bots\commonData\DnD\censor_policy\patterns2.text", "r", encoding="utf-8") as file:
        patterns2 = file.read().splitlines()

    for pattern in patterns:
        if pattern in result:
            redflag += 1
            break
    for pattern in patterns2:
        if pattern in result:
            redflag += 1
            break

    if redflag == 2:
        msg = last_move(user_id)
        if msg is not None:
            add_blocked(msg)
    else:
        msg = None

    last = last_move_for_check(user_id)
    if last != msg and msg is not None:
        add_moves_value(user_id, "movecoin", 1)
        info.put(f"Ход {user_id} возвращен из-за отказа нейросети")
        last_move_for_check(user_id, msg)
        delete_last_usercontext(user_id)


