import pytest
from unittest.mock import AsyncMock
from Bot.commands.commands import start

@pytest.mark.asyncio
async def test_start_answer_text_contains_greeting():
    message = AsyncMock()
    await start(message)
    text = message.answer.call_args[0][0]
    assert any(word in text.lower() for word in ["привет", "здравствуйте"]), "Нет приветствия в тексте"
