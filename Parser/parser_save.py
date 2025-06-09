import sys
import asyncio
import os
from dotenv import load_dotenv
import datetime
import logging
import inspect
from db.db import db

load_dotenv()

HOST = os.getenv("HOST")
DATABASE = os.getenv("DATABASE")
USER = os.getenv("USERNAME_DB")
PASSWORD = os.getenv("PASSWORD_DB")

logging.basicConfig(
    level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)
file_handler = logging.FileHandler("chat_parser.log", encoding="utf-8")
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(
    logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s")
)
logger.addHandler(file_handler)


async def retry(func_name, *args, **kwargs):
    async def _wrapper():
        while True:
            try:
                await func_name(*args, **kwargs)
                break
            except Exception as e:
                print(f"Произошла ошибка: {e}. Повторная попытка...")
                await asyncio.sleep(1)

    await _wrapper()


async def insert_many(db, table_name, updates):
    try:
        if not updates:
            return
        logger.info(f"Инициализирую запрос на вставку в БД {updates}")
        conn = db[table_name]
        result = conn.insert_many(updates)
        if inspect.isawaitable(result):
            await result
    except Exception as e:
        raise


async def Users(data, pool):
    try:
        # Получаем существующих пользователей
        distinct_res = pool["users"].distinct(
            "user_id", {"user_id": {"$in": list(data["accounts"].keys())}}
        )
        if inspect.isawaitable(distinct_res):
            distinct_res = await distinct_res
        all_users = set(distinct_res) if isinstance(distinct_res, (list, tuple, set)) else set()

        # Получаем существующие связи user-chat
        cursor_res = pool["links"].find(
            {"chat_id": {"$in": list(data["chats"])}},
            {"_id": 0, "user_id": 1, "chat_id": 1},
        )
        if inspect.isawaitable(cursor_res):
            cursor_res = await cursor_res
        exists_links = set((doc["user_id"], doc["chat_id"]) for doc in cursor_res)

        updates = []
        updates_links = []

        for user_id, user_data in data["accounts"].items():
            # Добавляем новые связи
            for chat_id in user_data["chats"]:
                if (user_id, chat_id) in exists_links:
                    continue
                updates_links.append({"user_id": user_id, "chat_id": chat_id})

            if user_id in all_users:
                continue

            info = user_data["info"]
            if info.get("username") is not None and info.get("first_name") is not None:
                username = info.get("username").lower()
                last_online = (
                    datetime.datetime.strptime(
                        info.get("last_online"), "%Y-%m-%d %H:%M:%S"
                    ) if info.get("last_online") is not None else None
                )

                updates.append({
                    "user_id": user_id,
                    "username": username,
                    "bio": info.get("bio"),
                    "first_name": info.get("first_name"),
                    "last_name": info.get("last_name"),
                    "last_online": last_online,
                    "premium": info.get("premium"),
                    "phone": info.get("phone"),
                    "image": info.get("image"),
                })

        await retry(insert_many, pool, "users", updates)
        await retry(insert_many, pool, "links", updates_links)

    except Exception as e:
        logger.error(f"Error in Users: {e}", exc_info=True)


async def Chats(data, pool):
    try:
        # Получаем существующие чаты
        distinct_res = pool["chats"].distinct(
            "chat_id", {"chat_id": {"$in": list(data["chats"].keys())}}
        )
        if inspect.isawaitable(distinct_res):
            distinct_res = await distinct_res
        exists_chats = set(distinct_res) if isinstance(distinct_res, (list, tuple, set)) else set()

        updates = []
        for chat_id, chat_data in data["chats"].items():
            if chat_id in exists_chats:
                continue
            last_online = (
                datetime.datetime.strptime(
                    chat_data.get("last_online"), "%Y-%m-%d %H:%M:%S"
                ) if chat_data.get("last_online") is not None else None
            )
            updates.append({
                "chat_id": chat_id,
                "parent_link": chat_data.get("parent_link"),
                "children_link": chat_data.get("children_link"),
                "title": chat_data.get("title"),
                "last_online": last_online,
            })

        await retry(insert_many, pool, "chats", updates)

    except Exception as e:
        logger.error(f"Error in Chats: {e}", exc_info=True)


async def background_save(data):
    try:
        pool = db()
        await Chats(data, pool)
        await Users(data, pool)
    except Exception as e:
        logger.error(f"Error in background_save: {e}", exc_info=True)

