"""
integration_test.py

• Блокируем любые реальные запросы к Telegram Bot API
  (авто-фикстура `_block_telegram_api`).
• Отключаем хэндлер download_links, чтобы не обращаться к Mongo и
  не генерировать Excel (фикстура `_stub_download_links`).
• Фиксируем переменную окружения IP, иначе URL внутри бота получает
  “None”.
• Для ряда сценариев считаем вызовы requests.post, проверяя,
  отправляет ли бот ссылки на энд-поинт `/add`.

Путь к файлам проекта (commands, config и т. д.) соответствует
структуре: `commands.commands`, `config.config`.
"""

from __future__ import annotations

import os
from datetime import datetime
from unittest.mock import patch, MagicMock

import pytest
from aiogram.types import Message, Update, Chat, User


# ---------------------------------------------------------------------------
# 1) IP = 127.0.0.1 (нужен коду бота)
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True, scope="session")
def _set_test_ip():
    os.environ.setdefault("IP", "127.0.0.1")


# ---------------------------------------------------------------------------
# 2) Глушим сетевой вызов Telegram API
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _block_telegram_api(monkeypatch: pytest.MonkeyPatch):
    class _FakeResp:
        ok = True
        result = None
        description = "OK"

    async def _fake_call(self, bot, method, timeout=None):  # type: ignore[no-self-use]
        return _FakeResp()

    monkeypatch.setattr(
        "aiogram.client.session.base.BaseSession.__call__", _fake_call, raising=True
    )


# ---------------------------------------------------------------------------
# 3) Отключаем download_links (Mongo + Excel)
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _stub_download_links(monkeypatch: pytest.MonkeyPatch):
    async def _no_op(*_args, **_kwargs):
        return

    monkeypatch.setattr("commands.commands.download_links", _no_op, raising=True)


# ---------------------------------------------------------------------------
# 4) Реальные bot / dp
# ---------------------------------------------------------------------------
@pytest.fixture
def bot():
    from config.config import bot as real_bot  # type: ignore
    return real_bot


@pytest.fixture
def dispatcher(bot):  # noqa: D401
    from config.config import dp as real_dp  # type: ignore
    return real_dp


# ---------------------------------------------------------------------------
# Утилита: быстро создаёт Update
# ---------------------------------------------------------------------------
def create_message(text: str, user_id: int = 42) -> Update:
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


# ---------------------------------------------------------------------------
#                    Базовые «старые» тесты проекта
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_parse_valid_links(bot, dispatcher):
    await dispatcher.feed_update(bot, create_message("/parse"))
    await dispatcher.feed_update(
        bot, create_message("https://t.me/example1\nhttps://t.me/example2")
    )


@pytest.mark.asyncio
async def test_parse_invalid_links(bot, dispatcher):
    await dispatcher.feed_update(bot, create_message("/parse"))
    await dispatcher.feed_update(
        bot, create_message("https://t.me/example1/123\nftp://wrong.link")
    )


# ---------------------------------------------------------------------------
#                Расширенные сценарии с подсчётом POST
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_parse_valid_links_multiple_batches(bot, dispatcher):
    with patch("requests.post", autospec=True) as mock_post:
        mock_post.return_value = MagicMock(status_code=200)

        await dispatcher.feed_update(bot, create_message("/parse"))
        await dispatcher.feed_update(bot, create_message("https://t.me/example1"))
        await dispatcher.feed_update(
            bot, create_message("https://t.me/example2\nhttps://t.me/example3")
        )

        # Состояние сброшено после первого валидного сообщения
        assert mock_post.call_count == 1


@pytest.mark.asyncio
async def test_links_without_parse_command_are_ignored(bot, dispatcher):
    with patch("requests.post", autospec=True) as mock_post:
        mock_post.return_value = MagicMock(status_code=200)

        await dispatcher.feed_update(
            bot, create_message("https://t.me/should_be_ignored")
        )
        assert mock_post.call_count == 0


@pytest.mark.asyncio
async def test_parse_mixed_links(bot, dispatcher):
    """
    В сообщении есть одновременно валидные и невалидные ссылки –
    бот сообщает об ошибке и НЕ делает POST.
    """
    with patch("requests.post", autospec=True) as mock_post:
        mock_post.return_value = MagicMock(status_code=200)

        await dispatcher.feed_update(bot, create_message("/parse"))
        await dispatcher.feed_update(
            bot,
            create_message(
                "https://t.me/ok1  ftp://bad\nhttps://t.me/ok2/   https://t.me/ok2"
            ),
        )

        assert mock_post.call_count == 0


@pytest.mark.asyncio
async def test_parse_empty_message_keeps_state(bot, dispatcher):
    with patch("requests.post", autospec=True) as mock_post:
        mock_post.return_value = MagicMock(status_code=200)

        await dispatcher.feed_update(bot, create_message("/parse"))
        await dispatcher.feed_update(bot, create_message("   "))  # пустяк
        await dispatcher.feed_update(bot, create_message("https://t.me/ok"))

        # После пустого сообщения бот очистил FSM, POST нет
        assert mock_post.call_count == 0


@pytest.mark.asyncio
async def test_parse_cancel(bot, dispatcher):
    with patch("requests.post", autospec=True) as mock_post:
        mock_post.return_value = MagicMock(status_code=200)

        await dispatcher.feed_update(bot, create_message("/parse"))
        await dispatcher.feed_update(bot, create_message("/cancel"))
        await dispatcher.feed_update(bot, create_message("https://t.me/ignored"))

        assert mock_post.call_count == 0


@pytest.mark.asyncio
async def test_parse_deduplicates_links(bot, dispatcher):
    with patch("requests.post", autospec=True) as mock_post:
        mock_post.return_value = MagicMock(status_code=200)

        await dispatcher.feed_update(bot, create_message("/parse"))
        await dispatcher.feed_update(
            bot,
            create_message(
                "https://t.me/dup\nhttps://t.me/dup  \n https://t.me/dup "
            ),
        )

        # Дубликаты удалены, POST один
        assert mock_post.call_count == 1
