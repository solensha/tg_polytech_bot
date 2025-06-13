import pytest
from unittest.mock import AsyncMock
from commands.commands import start

@pytest.mark.asyncio
async def test_start_answer_returns_string():
    message = AsyncMock()
    await start(message)
    args, kwargs = message.answer.call_args
    assert isinstance(args[0], str), "Ответ должен быть строкой"
