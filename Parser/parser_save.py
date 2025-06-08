import sys
import asyncio
import os
from dotenv import load_dotenv
import datetime
import logging
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
        if len(updates) == 0:
            return
        logger.info(f"Инициализирую запрос на вставку в БД {updates}")
        conn = db[f"{table_name}"]
        await conn.insert_many(updates)
    except Exception as e:
        raise e


async def Users(data, pool):
    try:
        updates = []
        updates_links = []

        conn = pool["users"]
        conn_links = pool["links"]

        all_users = set(
            await conn.distinct(
                "user_id",
                {"user_id": {"$in": list(data["accounts"].keys())}},
            )
        )

        cursor = await conn_links.find(
            {"chat_id": {"$in": list(data["chats"])}},
            {"_id": 0, "user_id": 1, "chat_id": 1},
        )

        exists_links = set((doc["user_id"], doc["chat_id"]) for doc in cursor)

        for key in data["accounts"]:
            for key_chat in data["accounts"][key]["chats"]:
                if (key, key_chat) in exists_links:
                    continue
                links_update = {
                    "user_id": key,
                    "chat_id": key_chat,
                }
                updates_links.append(links_update)

            if key in all_users:
                continue

            accounts_info = data["accounts"][key]["info"]

            if (
                accounts_info.get("username") is not None
                and accounts_info.get("first_name") is not None
            ):
                username = accounts_info.get("username").lower()
                last_online = (
                    datetime.datetime.strptime(
                        accounts_info.get("last_online"),
                        "%Y-%m-%d %H:%M:%S",
                    )
                    if accounts_info.get("last_online") is not None
                    else None
                )

                user_update = {
                    "user_id": key,
                    "username": username,
                    "bio": accounts_info.get("bio"),
                    "first_name": accounts_info.get("first_name"),
                    "last_name": accounts_info.get("last_name"),
                    "last_online": last_online,
                    "premium": accounts_info.get("premium"),
                    "phone": accounts_info.get("phone"),
                    "image": accounts_info.get("image"),
                }

                updates.append(user_update)

        await retry(insert_many, pool, "users", updates)
        await retry(insert_many, pool, "links", updates_links)
    except Exception as e:
        logger.error(f"Error: {e}")
        logger.error(sys.exc_info())


async def Chats(data, pool):
    try:
        updates = []
        conn = pool["chats"]
        exists_chats = set(
            await conn.distinct("chat_id", {"chat_id": {"$in": list(data["chats"].keys())}})
        )

        for key in data["chats"]:
            if key in exists_chats:
                continue

            chats_key = data["chats"][key]
            last_online = (
                datetime.datetime.strptime(
                    chats_key.get("last_online"), "%Y-%m-%d %H:%M:%S"
                )
                if chats_key.get("last_online") is not None
                else None
            )

            updates.append(
                {
                    "chat_id": key,
                    "parent_link": chats_key.get("parent_link"),
                    "children_link": chats_key.get("children_link"),
                    "title": chats_key.get("title"),
                    "last_online": last_online,
                }
            )

        await retry(insert_many, pool, "chats", updates)
    except Exception as e:
        logger.error(f"Error: {e}")


async def background_save(data):
    try:
        pool = db()
        await Chats(data, pool)
        await Users(data, pool)
    except Exception as e:
        logger.error(f"Error: {e}")
        logger.error(sys.exc_info())
