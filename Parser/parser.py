import string
import random
import logging
import asyncio
import json
import os
import requests
import sys

from aiohttp import web
from telethon.sessions import StringSession
from telethon import TelegramClient
from telethon.tl.types import Channel, ChannelForbidden
from telethon import functions, errors
from datetime import datetime
from dotenv import load_dotenv
from parser_save import background_save

load_dotenv()
IP = os.getenv("IP")

base_dir = os.path.dirname(os.path.abspath(__file__))
query_keys_path = os.path.join(base_dir, "query_keys.json")

with open(query_keys_path, "r") as f:
    queryKey = json.load(f) or []


logging.basicConfig(
    level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)
file_handler = logging.FileHandler("chat_parser.log")
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(
    logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s")
)
logger.addHandler(file_handler)


async def handle_links(request):
    data = await request.json()
    link = data.get("link")
    return web.Response(text="Received link: {}".format(link))


app = web.Application()
app.add_routes([web.post("/handle_links", handle_links)])


def generate_random_string(length):
    letters = string.ascii_letters
    return "".join(random.choice(letters) for _ in range(length))


def get_username(entity):
    if hasattr(entity, "username") and entity.username is not None:
        return entity.username
    else:
        return None


def serialize_participant(participant):
    return {
        "user_id": participant.id,
        "first_name": (
            participant.first_name if hasattr(participant, "first_name") else None
        ),
        "last_name": (
            participant.last_name if hasattr(participant, "last_name") else None
        ),
        "username": participant.username if hasattr(participant, "username") else None,
        "last_online": (
            participant.status.was_online.strftime("%Y-%m-%d %H:%M:%S")
            if participant.status and hasattr(participant.status, "was_online")
            else None
        ),
        "premium": (
            participant.premium
            if hasattr(participant, "premium") and participant.premium is not None
            else False
        ),
        "phone": participant.phone if hasattr(participant, "phone") else None,
        "image": hasattr(participant, "photo") and participant.photo is not None,
    }


async def send_request_to_server(user_data, retry_delay=5):
    if not any(user_data.values()):
        logger.error("Попытка сохранить пустые данные. Отмена сохранения.")
        return
    while True:
        try:
            logger.info(f"Инициирую запрос на сохранение данных.")
            await background_save(user_data)
            return
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка при сохранении данных на сервер: {e}")
            await asyncio.sleep(retry_delay)


async def parse_chat(client, chat, user_data, link):
    try:
        logger.info(f"Обработка чата: {chat.title}")
        if chat.username is not None:
            chat_username = "https://t.me/" + chat.username.lower()
        else:
            chat_username = None
        chat_data = {
            "parent_link": link.lower(),
            "children_link": chat_username,
            "title": chat.title if hasattr(chat, "title") else None,
            "last_online": (
                chat.date.strftime("%Y-%m-%d %H:%M:%S")
                if chat.date and hasattr(chat, "date")
                else None
            ),
        }
        user_data["chats"][chat.id] = chat_data

        try:
            total_messages = (await client.get_messages(chat, 1)).total
        except Exception as e:
            logger.error(
                f"Произошла ошибка при получении сообщений в чате: {chat.title}, {e}"
            )
            return

        processed_participants = 0
        total_participants = 0

        for letter in queryKey:
            try:
                logger.info(
                    f"Начинаю получать участников по букве {letter} в чате {chat.title}"
                )
                participants = await client.get_participants(chat, search=letter)
                total_participants += len(participants)

                for participant in participants:
                    processed_participants += 1
                    logger.info(
                        f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Обработка участника {processed_participants}/{total_participants}"
                    )
                    if participant is None or not getattr(
                        participant, "username", None
                    ):
                        continue

                    if (
                        not isinstance(participant, Channel)
                        and not isinstance(participant, ChannelForbidden)
                        and not getattr(participant, "bot", False)
                    ):
                        if participant.id not in user_data["accounts"]:
                            user_data["accounts"][participant.id] = {
                                "chats": set([chat.id]),
                                "info": serialize_participant(participant),
                            }
                            user_data["accounts"][participant.id]["info"][
                                "bio"
                            ] = "Default-value-for-parser"
                        else:
                            chats = user_data["accounts"][participant.id]["chats"]
                            if chat.id not in chats:
                                chats.add(chat.id)
            except Exception as e:
                logger.error(
                    f"Произошла ошибка при получении участников по букве {letter} в чате {chat.title}: {e}"
                )
        processed_messages = 0

        async for message in client.iter_messages(chat, limit=25000):
            sender = message.sender
            if sender is None or not getattr(sender, "username", None):
                continue
            if (
                not isinstance(sender, Channel)
                and not isinstance(sender, ChannelForbidden)
                and not getattr(sender, "bot", False)
            ):
                if sender.id not in user_data["accounts"]:
                    user_data["accounts"][sender.id] = {
                        "chats": set([chat.id]),
                        "info": serialize_participant(sender),
                    }
                    user_data["accounts"][sender.id]["info"][
                        "bio"
                    ] = "Default-value-for-parser"
                else:
                    if chat.id not in user_data["accounts"][sender.id]["chats"]:
                        user_data["accounts"][sender.id]["chats"].add(chat.id)

                processed_messages += 1
                progress = processed_messages / total_messages * 100
                logger.info(
                    f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Обработка сообщений: {processed_messages}/{total_messages} ({progress:.2f}%)"
                )
    except Exception as e:
        logger.error(f"Произошла ошибка при обработке чата. {e}")
        logger.exception(e)


async def parse_chat_by_link(client, link, user_data):
    chat = await client.get_entity(link)
    if chat.megagroup:
        logger.info(f"Чат {link} в работе.")
        await parse_chat(client, chat, user_data, link)
    else:
        full = await client(functions.channels.GetFullChannelRequest(chat))
        if full and full.chats:
            for chat in full.chats:
                if chat is not None and chat.megagroup:
                    logger.info(f"Чат {link} в работе.")
                    await parse_chat(client, chat, user_data, link)


async def main(api_id, api_hash, session_value):
    user_data = {"chats": {}, "accounts": {}}
    try:
        res = requests.get(f"http://{IP}/link")
        link = res.json()
        if link:
            logger.info(f"Ссылка, полученная для парсинга: {link}")
            async with TelegramClient(
                StringSession(session_value),
                api_id,
                api_hash,
                system_version="4.16.30-vxCUSTOM",
                device_model="Samsung Galaxy S21 Ultra 5G",
            ) as client:
                try:
                    await parse_chat_by_link(client, link, user_data)
                    await send_request_to_server(user_data)
                except errors.FloodWaitError as e:
                    try:
                        wait_time = e.seconds
                        logger.warning(
                            f"Получена ошибка FloodWaitError. Ожидание {wait_time} секунд перед повторной попыткой..."
                        )
                        await asyncio.sleep(wait_time + 5)
                        await parse_chat_by_link(client, link, user_data)
                        await send_request_to_server(user_data)
                    except Exception as e:
                        logger.error(f"Произошла ошибка при повторном парсен: {e}")
                except Exception as e:
                    logger.error(f"Ссылка {link} не распаршена, произошла ошибка. {e}")
                print("Выполнение скрипта успешно завершено")
        else:
            print("База данных для парсинга пуста. Завершение работы через 60s.")
        await asyncio.sleep(60)
    except Exception as e:
        logger.error(f"Произошла глобальная ошибка. {e}")




if __name__ == "__main__":
    api_id = sys.argv[1]
    api_hash = sys.argv[2]
    session_value = sys.argv[3]
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main(api_id, api_hash, session_value))
