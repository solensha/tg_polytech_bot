import os
import sys
import pytest
import respx
from httpx import Response
from aiogram import Bot, Dispatcher, Router
from aiogram.types import Message, Update, Chat, User
from aiogram.fsm.storage.memory import MemoryStorage
from datetime import datetime


@pytest.fixture
def bot():
    # Фейковый токен, реальных запросов к Telegram не будет
    return Bot(token="123456:FAKE-TOKEN-FOR-TESTS")

@pytest.fixture
def dispatcher(bot):
    # Роутер создаём “пустым”, как и в исходных тестах
    router = Router()
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)
    return dp

def create_message(text: str, user_id=42) -> Update:
    return Update(
        update_id=1,
        message=Message(
            message_id=1,
            date=datetime.now(),
            chat=Chat(id=user_id, type="private"),
            from_user=User(id=user_id, is_bot=False, first_name="TestUser"),
            text=text,
        ),
    )

# ─────────────────────────────────────────────────────────────
# Оригинальные тесты (2 шт)
# ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
@respx.mock
async def test_parse_valid_links(bot: Bot, dispatcher: Dispatcher):
    # Мокаем HTTP POST-запрос, который может делать бекенд при /parse
    respx.post("http://127.0.0.1/add").mock(return_value=Response(200, json={"status": "ok"}))

    update_parse = create_message("/parse")
    await dispatcher.feed_update(bot, update_parse)

    update_links = create_message("https://t.me/example1\nhttps://t.me/example2")
    await dispatcher.feed_update(bot, update_links)


@pytest.mark.asyncio
@respx.mock
async def test_parse_invalid_links(bot: Bot, dispatcher: Dispatcher):
    update_parse = create_message("/parse")
    await dispatcher.feed_update(bot, update_parse)

    update_invalid = create_message("https://t.me/example1/123\nftp://wrong.link")
    await dispatcher.feed_update(bot, update_invalid)

# ─────────────────────────────────────────────────────────────
# A) Матрица статусов ответа backend для /add (12 шт)
# ─────────────────────────────────────────────────────────────

STATUSES = [200, 202, 204, 400, 401, 403, 404, 409, 413, 429, 500, 503]

@pytest.mark.asyncio
@respx.mock
@pytest.mark.parametrize("status", STATUSES, ids=[f"status_{s}" for s in STATUSES])
async def test_parse_links_status_matrix(bot: Bot, dispatcher: Dispatcher, status: int):
    respx.post("http://127.0.0.1/add").mock(return_value=Response(status))
    await dispatcher.feed_update(bot, create_message("/parse"))
    await dispatcher.feed_update(bot, create_message("https://t.me/a\nhttps://t.me/b"))

# ─────────────────────────────────────────────────────────────
# B) Разные формы “битых” или смешанных входов (10 шт)
# ─────────────────────────────────────────────────────────────

MIXED_INPUTS = [
    "invalid",
    "https://t.me/a/123 notalink",
    "ftp://wrong\nhttps://t.me/right",
    "plain text only",
    "https://site.com/path",
    "https://t.me/a\n???\nhttps://t.me/b",
    "https://t.me/chan#frag\nbad://url",
    "mailto:test@example.com",
    "https://t.me/a\thttps://t.me/b\nwrong",
    " \n \t  ",
]

@pytest.mark.asyncio
@respx.mock
@pytest.mark.parametrize("payload", MIXED_INPUTS, ids=[f"mixed_{i+1:02d}" for i in range(len(MIXED_INPUTS))])
async def test_parse_mixed_inputs(bot: Bot, dispatcher: Dispatcher, payload: str):
    respx.post("http://127.0.0.1/add").mock(return_value=Response(200, json={"ok": True}))
    await dispatcher.feed_update(bot, create_message("/parse"))
    await dispatcher.feed_update(bot, create_message(payload))

# ─────────────────────────────────────────────────────────────
# C) Большие батчи ссылок (5 шт)
# ─────────────────────────────────────────────────────────────

def gen_links(n, with_ids=False):
    if with_ids:
        return "\n".join([f"https://t.me/chat{i}/{i}" for i in range(n)])
    return "\n".join([f"https://t.me/chat{i}" for i in range(n)])

BIG_BATCHES = [
    gen_links(5),
    gen_links(10),
    gen_links(20),
    gen_links(5, with_ids=True),
    gen_links(10, with_ids=True),
]

@pytest.mark.asyncio
@respx.mock
@pytest.mark.parametrize("payload", BIG_BATCHES, ids=[f"batch_{i+1:02d}" for i in range(len(BIG_BATCHES))])
async def test_parse_big_batches(bot: Bot, dispatcher: Dispatcher, payload: str):
    respx.post("http://127.0.0.1/add").mock(return_value=Response(200, json={"status": "queued"}))
    await dispatcher.feed_update(bot, create_message("/parse"))
    await dispatcher.feed_update(bot, create_message(payload))

# ─────────────────────────────────────────────────────────────
# D) Варианты разделителей/пробелов (5 шт)
# ─────────────────────────────────────────────────────────────

SEPARATORS = [
    "https://t.me/a https://t.me/b",
    "https://t.me/a\thttps://t.me/b",
    "https://t.me/a\nhttps://t.me/b",
    "  https://t.me/a   \n  https://t.me/b  ",
    "https://t.me/a\r\nhttps://t.me/b\r\n",
]

@pytest.mark.asyncio
@respx.mock
@pytest.mark.parametrize("payload", SEPARATORS, ids=[f"sep_{i+1:02d}" for i in range(len(SEPARATORS))])
async def test_parse_separators(bot: Bot, dispatcher: Dispatcher, payload: str):
    respx.post("http://127.0.0.1/add").mock(return_value=Response(200))
    await dispatcher.feed_update(bot, create_message("/parse"))
    await dispatcher.feed_update(bot, create_message(payload))

# ─────────────────────────────────────────────────────────────
# E) Поведение нескольких /parse подряд, потом ссылки (5 шт)
# ─────────────────────────────────────────────────────────────

MULTI_PARSE_SEQUENCES = [
    (1, "https://t.me/a"),
    (2, "https://t.me/a\nhttps://t.me/b"),
    (3, "https://t.me/a/1\nhttps://t.me/b/2"),
    (4, "invalid\nhttps://t.me/a"),
    (5, "https://t.me/a\tinvalid\nhttps://t.me/b"),
]

@pytest.mark.asyncio
@respx.mock
@pytest.mark.parametrize("repeats, payload", MULTI_PARSE_SEQUENCES, ids=[f"repeats_{r}" for r, _ in MULTI_PARSE_SEQUENCES])
async def test_multiple_parse_commands(bot: Bot, dispatcher: Dispatcher, repeats: int, payload: str):
    respx.post("http://127.0.0.1/add").mock(return_value=Response(200))
    for _ in range(repeats):
        await dispatcher.feed_update(bot, create_message("/parse"))
    await dispatcher.feed_update(bot, create_message(payload))
