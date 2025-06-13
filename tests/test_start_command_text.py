import pytest
from unittest.mock import AsyncMock
from commands.commands import start

@pytest.mark.asyncio
async def test_start_text_exact_match():
    message = AsyncMock()
    await start(message)
    text = message.answer.call_args[0][0]
    assert "представить Вам нашего бота" in text  # часть приветственного текста
