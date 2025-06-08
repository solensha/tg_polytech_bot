import pytest
import respx
from httpx import Response
from aiogram import Bot, Dispatcher, Router
from aiogram.types import Message, Update, Chat, User
from aiogram.fsm.storage.memory import MemoryStorage
from datetime import datetime


@pytest.fixture
def bot():
    return Bot(token="123456:FAKE-TOKEN-FOR-TESTS")

@pytest.fixture
def dispatcher(bot):
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

@pytest.mark.asyncio
@respx.mock
async def test_parse_valid_links(bot: Bot, dispatcher: Dispatcher):
    # Мокаем HTTP POST-запрос
    respx.post("http://127.0.0.1/add").mock(
        return_value=Response(200, json={"status": "ok"})
    )

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
