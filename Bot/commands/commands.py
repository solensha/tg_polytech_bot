import os
import re
from config.config import dp, bot
import aiohttp
import requests
from aiogram import Bot, Dispatcher, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.filters import Command
from aiogram.types import Message
from openpyxl import Workbook
from db.db import db
from dotenv import load_dotenv
from aiogram import Router
from aiogram.types import FSInputFile

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
IP = os.getenv("IP")

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
router = Router()
dp.include_router(router)

class DownloadState(StatesGroup):
    waiting_for_download_links = State()


class ParseState(StatesGroup):
    waiting_for_tasks_links = State()


@router.message(Command(commands=["start"]))
async def start(message: Message):
    await message.answer(
        'Привет! Мы рады представить Вам нашего бота и ознакомить с его функционалом.\n\n'
        'Команда "/parse"\nОтправьте список ссылок, которые Вы хотите добавить в базу данных. Бот проверит их на корректность и добавит допустимые ссылки.\n\n'
        'Команда "/download"\nОтправьте список ссылок на чаты, после чего бот отправит информацию о пользователях этих чатов в формате Excel.\n\n'
        'Вы можете отправлять как одну ссылку, так и несколько ссылок одновременно. Просто разделите их переносом строки.'
    )


@router.message(Command(commands=["parse"]))
async def tasks_command(message: Message, state: FSMContext):
    await message.answer(
        "Пожалуйста, отправьте ссылки, которые нужно добавить в базу данных.\nПример:\nhttps://t.me/example1 \nhttps://t.me/example2"
    )
    await state.set_state(ParseState.waiting_for_tasks_links)


@router.message(Command(commands=["download"]))
async def download_command(message: Message, state: FSMContext):
    await message.answer(
        "Пожалуйста, отправьте ссылки на чаты, чтобы скачать информацию о пользователях этих чатов.\nПример:\nhttps://t.me/example1 \nhttps://t.me/example2"
    )
    await state.set_state(DownloadState.waiting_for_download_links)


@router.message(ParseState.waiting_for_tasks_links)
async def tasks_links(message: types.Message, state: FSMContext):
    try:
        links = re.findall(r"(?:https?://\S+)", message.text)
        if links:
            valid_links = []
            invalid_links = []

            for link in links:
                remainder = link.split("://")[1].split("/", 1)[-1]
                if re.match(r"^https?://", link) and not "/" in remainder:
                    valid_links.append(link)
                else:
                    invalid_links.append(link)

            if invalid_links:
                await message.answer(
                    'Ссылки должны начинаться с "https://" и не содержать "/" в конце. '  \
                    'Например, ссылка "https://t.me/example1/4544" неправильна, так как содержит "/4544" в конце.\n'  \
                    + "\n".join(invalid_links)
                )
            else:
                if valid_links:
                    answer = requests.post(f"http://{IP}/add", json={"urls": valid_links})
                    if answer.status_code == 200:
                        await message.answer(
                            "Чаты успешно добавлены в очередь для парсинга. Рекомендуется подождать час, перед тем как получить информацию о пользователях из чатов."
                        )
                    else:
                        await message.answer(f"Ошибка: {answer.status_code}")
        else:
            await message.answer(
                'Ссылки должны начинаться с "https://" и не содержать "/" в конце. '  \
                'Например, ссылка "https://t.me/example1/4544" неправильна, так как содержит "/4544" в конце.'
            )
        await state.clear()

    except Exception as e:
        print(f"{e}")
        await message.answer(f"Ошибка: {e}")
        await state.clear()


@router.message()
async def download_links(message: types.Message):
    try:
        async with aiohttp.ClientSession():
            urls = re.findall(r"(?:https?://\S+)", message.text)
            wb = Workbook()
            ws = wb.active
            ws.append(
                [
                    "user_id", "username", "bio", "first_name", "last_name",
                    "last_online", "premium", "phone", "image", "ban"
                ]
            )
            if urls:
                file_path = "chats_users.xlsx"
                invalid_chat_ids_server = []
                invalid_chat_ids = []
                valid_urls = []
                for url in urls:
                    remainder = url.split("://")[1].split("/", 1)[-1]
                    if re.match(r"^https?://", url) and not "/" in remainder:
                        valid_urls.append(url.lower())
                    else:
                        invalid_chat_ids.append(url)
                data_base = db()
                cursor_chat = data_base["chats"]
                cursor_links = data_base["links"]
                cursor_users = data_base["users"]

                chats_ids = cursor_chat.distinct(
                    "chat_id",
                    {
                        "$or": [
                            {"parent_link": {"$in": valid_urls}},
                            {"children_link": {"$in": valid_urls}},
                        ]
                    },
                )
                users_ids = cursor_links.distinct(
                    "user_id", {"chat_id": {"$in": chats_ids}}
                )
                info_users = list(
                    cursor_users.find(
                        {"user_id": {"$in": users_ids}, "ban": {"$ne": True}},
                        {"_id": 0},
                    )
                )
                is_not_finished = False
                print(info_users)
                for user in info_users:
                    if "ban" not in user:
                        user["ban"] = False
                    if user["bio"] == "Default-value-for-parser":
                        bio = None
                        is_not_finished = True
                    else:
                        bio = str(user["bio"])
                    if user["last_online"] is not None:
                        last_online = (
                            user["last_online"].strftime("%Y-%m-%d %H:%M:%S")
                            if user["last_online"].strftime("%Y-%m-%d %H:%M:%S")
                            != "1970-01-01 00:00:00"
                            else ""
                        )
                    else:
                        last_online = ""
                    user_data = [
                        user["user_id"],
                        user["username"],
                        bio,
                        str(user["first_name"]),
                        str(user["last_name"]),
                        last_online,
                        "false" if user["premium"] == False else "true",
                        "" if user["phone"] is None else user["phone"],
                        "true" if user["image"] == True else "false",
                        "true" if user["ban"] == True else "false",
                    ]
                    print(user_data)
                    ws.append(user_data)
                wb.save(file_path)
                if is_not_finished:
                    await message.answer(
                        f"На данный момент не вся информация о пользователях доступна. Пожалуйста, подождите некоторое время и повторите попытку."
                    )
                if invalid_chat_ids:
                    await message.answer(
                        f'Ссылки должны начинаться с "https://" и не содержать "/" в конце. Например, ссылка "https://t.me/example1/4544" неправильна, так как содержит "/4544" в конце.\n'  \
                        + "\n".join(invalid_chat_ids_server)
                    )
                else:
                    document = FSInputFile(file_path)
                    await message.answer_document(document)
                    os.remove(file_path)
            else:
                await message.answer(
                    'Ссылки должны начинаться с "https://" и не содержать "/" в конце. Например, ссылка "https://t.me/example1/4544" неправильна, так как содержит "/4544" в конце.'
                )
    except Exception as e:
        await message.answer(f"Произошла ошибка при обработке запроса: {e}")

