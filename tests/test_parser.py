import os
import sys
import pytest
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'Parser')))

from unittest.mock import AsyncMock, MagicMock, patch

from parser import (
    generate_random_string,
    get_username,
    serialize_participant,
    handle_links,
    send_request_to_server,
    parse_chat_by_link,
)


def test_generate_random_string():
    s = generate_random_string(10)
    assert isinstance(s, str)
    assert len(s) == 10
    assert all(c.isalpha() for c in s)

def test_get_username():
    class Entity:
        username = "user123"
    assert get_username(Entity()) == "user123"

    class EntityNoUsername:
        pass
    assert get_username(EntityNoUsername()) is None

def test_serialize_participant():
    class WasOnline:
        def strftime(self, fmt):
            return "2025-01-01 00:00:00"

    class Status:
        was_online = WasOnline()

    class Participant:
        id = 123
        first_name = "First"
        last_name = "Last"
        username = "username"
        status = Status()
        premium = True
        phone = "+123456789"
        photo = True

    p = Participant()
    data = serialize_participant(p)
    assert data["user_id"] == 123
    assert data["first_name"] == "First"
    assert data["last_name"] == "Last"
    assert data["username"] == "username"
    assert data["last_online"] == "2025-01-01 00:00:00"
    assert data["premium"] is True
    assert data["phone"] == "+123456789"
    assert data["image"] is True


@pytest.mark.asyncio
@patch("parser.background_save", new_callable=AsyncMock)
async def test_send_request_to_server_success(mock_save):
    user_data = {"key": "value"}
    await send_request_to_server(user_data)
    mock_save.assert_awaited_once_with(user_data)

@pytest.mark.asyncio
@patch("parser.background_save", new_callable=AsyncMock)
async def test_send_request_to_server_empty_data(mock_save):
    user_data = {"key": None, "another": False}
    result = await send_request_to_server(user_data)
    mock_save.assert_not_awaited()
    assert result is None

@pytest.mark.asyncio
@patch("parser.parse_chat")
@patch("parser.TelegramClient")
@patch("parser.requests.get")
@patch("parser.send_request_to_server", new_callable=AsyncMock)
async def test_parse_chat_by_link(mock_send_request, mock_requests_get, mock_telegram_client, mock_parse_chat):
    # Мокаем ответ requests.get
    mock_requests_get.return_value.json = lambda: "some_link"
    mock_chat = MagicMock()
    mock_chat.megagroup = True
    client = AsyncMock()
    client.get_entity = AsyncMock(return_value=mock_chat)
    mock_telegram_client.return_value.__aenter__.return_value = client

    user_data = {"chats": {}, "accounts": {}}

    await parse_chat_by_link(client, "some_link", user_data)
    mock_parse_chat.assert_awaited_once_with(client, mock_chat, user_data, "some_link")


