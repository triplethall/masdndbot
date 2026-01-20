import asyncio
import json
import sqlite3
import uuid
from datetime import datetime, timedelta

from alarm import info, alarm


conn = sqlite3.connect(r"C:\Bots\commonData\DnD\base.db")
cursor = conn.cursor()


cursor.execute('''
CREATE TABLE IF NOT EXISTS registered_users (
    user_id INTEGER PRIMARY KEY,
    username TEXT NOT NULL,
    reg_time TEXT NOT NULL
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS busy_locks (
    request_id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    created_at TEXT NOT NULL
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS statuses (
    user_id INTEGER PRIMARY KEY,
    status TEXT NOT NULL,
    msg_ids TEXT,
    input_mode INTEGER DEFAULT 0
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS moves (
    user_id INTEGER PRIMARY KEY,
    movecoin INTEGER DEFAULT 25,
    move INTEGER DEFAULT 0,
    bought_times INTEGER DEFAULT 0,
    bought_moves INTEGER DEFAULT 0
    )
''')


cursor.execute('''
CREATE TABLE IF NOT EXISTS refs (
    user_id INTEGER PRIMARY KEY,
    ref_link TEXT UNIQUE,
    total_refs INTEGER DEFAULT 0
)
''')

cursor.execute('''
INSERT OR IGNORE INTO refs (user_id)
SELECT user_id FROM registered_users
''')

cursor.execute('''
UPDATE refs
SET ref_link = 'https://t.me/ttmasterdicebot?start=' || user_id
WHERE ref_link IS NULL
''')

conn.commit()

# добавляет нового пользователя (если такой есть, не добавляет - можно не проверять)
def register_user(user_id: int, username: str):
    if not username:
        #чтобы не было ошибки если ник пустой
        username = 'unknown'
    """Добавляет пользователя в registered_users с текущей датой и временем"""
    reg_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    # Вставляем запись или обновляем (если user_id уже есть)
    cursor.execute('''
        INSERT INTO registered_users (user_id, username, reg_time)
        VALUES (?, ?, ?)
        ON CONFLICT(user_id) DO NOTHING;
    ''', (user_id, username, reg_time))

    cursor.execute("""INSERT OR IGNORE INTO moves (user_id) VALUES (?)""", (user_id,))
    cursor.execute("""INSERT OR IGNORE INTO refs (user_id) VALUES (?)""", (user_id,))

    conn.commit()


async def acquire_lock(user_id: int) -> str | None:
    """Возвращает request_id если lock взят, None если занят"""
    request_id = str(uuid.uuid4())
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    cursor.execute('INSERT INTO busy_locks VALUES (?, ?, ?)', (request_id, user_id, now))

    cursor.execute('SELECT COUNT(*) FROM busy_locks WHERE user_id=? AND request_id != ?',
                   (user_id, request_id))

    if cursor.fetchone()[0] > 0:
        cursor.execute('DELETE FROM busy_locks WHERE request_id=?', (request_id,))
        conn.commit()
        return None

    conn.commit()
    return request_id


async def release_lock(request_id: str):
    """Удаляет ТОЧНО этот request_id"""
    cursor.execute('DELETE FROM busy_locks WHERE request_id=?', (request_id,))
    conn.commit()


async def cleanup_old_locks(user_id: int):
    """Удаляет locks старше 15 секунд"""
    cutoff = datetime.now() - timedelta(seconds=30)
    cursor.execute('DELETE FROM busy_locks WHERE user_id=? AND created_at < ?',
                   (user_id, cutoff.strftime('%Y-%m-%d %H:%M:%S')))
    conn.commit()

def get_moves_value(user_id, field_name):
    valid_fields = ['movecoin', 'move', 'bought_times', 'bought_moves']
    if field_name not in valid_fields:
        alarm.put("Неверное имя поля принято аргументом get_moves_value")
        return None
    cursor.execute(f"SELECT {field_name} FROM moves WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    return result[0] if result else None

def set_moves_value(user_id, field_name, value):
    valid_fields = ['movecoin', 'move', 'bought_times', 'bought_moves']
    if field_name not in valid_fields:
        alarm.put("Неверное имя поля принято аргументом get_moves_value")
        return
    cursor.execute(f"UPDATE moves SET {field_name} = ? WHERE user_id = ?", (value, user_id))
    conn.commit()

def add_moves_value(user_id, field_name, value):
    valid_fields = ['movecoin', 'move', 'bought_times', 'bought_moves']
    if field_name not in valid_fields:
        alarm.put("Неверное имя поля принято аргументом add_moves_value")
        return
    # Обновляем поле, добавляя value к уже существующему значению
    cursor.execute(f'''
        UPDATE moves
        SET {field_name} = COALESCE({field_name}, 0) + ?
        WHERE user_id = ?
    ''', (value, user_id))
    conn.commit()

# проверяет, есть ли пользователь в базе
def is_user_registered(user_id: int) -> bool:
    cursor.execute('SELECT 1 FROM registered_users WHERE user_id = ?', (user_id,))
    return cursor.fetchone() is not None

# меняет статус пользователю
def set_dnd_status(user_id: int, status: str):
    cursor.execute('''
        INSERT INTO statuses (user_id, status)
        VALUES (?, ?)
        ON CONFLICT(user_id) DO UPDATE SET status=excluded.status
    ''', (user_id, status))
    conn.commit()

# меняет статус пользователю
def set_input_mode(user_id: int, input_mode: int):
    cursor.execute('''
        INSERT INTO statuses (user_id, status, input_mode)
        VALUES (?, (SELECT status FROM statuses WHERE user_id = ?), ?)
        ON CONFLICT(user_id) DO UPDATE SET input_mode=excluded.input_mode
    ''', (user_id, user_id, input_mode))
    conn.commit()

def get_input_mode(user_id: int) -> int | None:
    cursor.execute('SELECT input_mode FROM statuses WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    return result[0] if result else None

def get_msg_ids(user_id):
    cursor.execute('SELECT msg_ids FROM statuses WHERE user_id = ?', (user_id,))
    row = cursor.fetchone()
    if not row or not row[0]:
        return []

    try:
        msg_ids = json.loads(row[0])
        if isinstance(msg_ids, list):
            return msg_ids
        else:
            return []
    except json.JSONDecodeError:
        return []

def update_msg_ids(user_id, new_msg_ids):
    # Проверяем статус пользователя
    cursor.execute('SELECT status, msg_ids FROM statuses WHERE user_id = ?', (user_id,))
    row = cursor.fetchone()
    if not row:
        print("Ошибка: пользователь не найден в таблице statuses")
        return
    status, msg_ids_json = row

    # Если поле msg_ids не пустое, загружаем JSON, иначе создаем пустой список
    if msg_ids_json:
        try:
            existing_msg_ids = json.loads(msg_ids_json)
            if not isinstance(existing_msg_ids, list):
                existing_msg_ids = []
        except json.JSONDecodeError:
            existing_msg_ids = []
    else:
        existing_msg_ids = []

    # Дополняем список новыми id, избегая дубликатов
    for msg_id in new_msg_ids:
        if msg_id not in existing_msg_ids:
            existing_msg_ids.append(msg_id)
    existing_msg_ids = list(set(existing_msg_ids))
    # Сохраняем обновленный список обратно в JSON
    updated_msg_ids_json = json.dumps(existing_msg_ids)
    cursor.execute('''
        UPDATE statuses
        SET msg_ids = ?
        WHERE user_id = ?
    ''', (updated_msg_ids_json, user_id))
    conn.commit()

async def delete_message(client, chat_id, message_id):
    await client.delete_messages(chat_id, message_id)


# проверяет статус пользователя

def get_dnd_status(user_id: int) -> str | None:
    cursor.execute('SELECT status FROM statuses WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    return result[0] if result else None

def clear_msg_ids(user_id: int):
    empty_json_list = "[]"
    cursor.execute('''
        UPDATE statuses
        SET msg_ids = ?
        WHERE user_id = ?
    ''', (empty_json_list, user_id))
    conn.commit()

# считает зарегистрированных пользователей
def count_registered_users() -> int:
    cursor.execute('SELECT COUNT(*) FROM registered_users')
    result = cursor.fetchone()
    return result[0] if result else 0

"""
ingame - есть текущая игра
nogame - нет текущей игры
nostarted - никогда не начинал игру
outgame - есть игра, но в другом меню
"""
async def status_manager(client, event, ids, status):
    user_id = event.sender.id
    username = event.sender.username
    previous_status = get_dnd_status(user_id)

    if is_user_registered(user_id) == False:
        register_user(user_id, username)
        info.put(f"Новый пользователь: {username} ({user_id})!")
        if get_dnd_status(user_id) is None:
            set_dnd_status(user_id, status="nostarted")
        return

    if previous_status == status:
        if status == 'outgame':
            update_msg_ids(user_id, ids)
            return
        else:
            return
    elif previous_status == "ingame":
        if status == "nogame":
            set_dnd_status(user_id, status)
        elif status == "outgame":
            set_dnd_status(user_id, status)
            update_msg_ids(user_id, ids)
        else:
            return
    elif previous_status == "nogame":
        if status == "ingame":
            set_dnd_status(user_id, status)
        elif status == "nostarted":
            set_dnd_status(user_id, status)
        else:
            return
    elif previous_status == "nostarted":
        if status == "ingame":
            set_dnd_status(user_id, status)
        else:
            return
    elif previous_status == "outgame":
        if status == "ingame":
            msg_ids = get_msg_ids(user_id)
            await delete_message(client, user_id, msg_ids)
            set_dnd_status(user_id, status)
            clear_msg_ids(user_id)
        if status == "nogame":
            msg_ids = get_msg_ids(user_id)
            await delete_message(client, user_id, msg_ids)
            set_dnd_status(user_id, status)
            clear_msg_ids(user_id)
        else:
            return


def get_ref_link(user_id):
    cursor.execute('SELECT ref_link FROM refs WHERE user_id = ?', (user_id,))
    row = cursor.fetchone()
    if row:
        return row[0]
    else:
        # Если пользователя нет, формируем и добавляем новую реф ссылку (примерно)
        ref_link = f"https://t.me/ttmasterdicebot?start={user_id}"
        cursor.execute('INSERT INTO refs (user_id, ref_link) VALUES (?, ?)', (user_id, ref_link))
        conn.commit()
        return ref_link


def increment_total_refs(user_id):
    cursor.execute('SELECT total_refs FROM refs WHERE user_id = ?', (user_id,))
    row = cursor.fetchone()
    if row:
        new_total = row[0] + 1
        cursor.execute('UPDATE refs SET total_refs = ? WHERE user_id = ?', (new_total, user_id))
        conn.commit()
    else:
        # пользователя нет, ничего не делаем
        return
