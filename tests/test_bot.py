import pytest
import os
import  sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'Bot')))
from unittest.mock import MagicMock, AsyncMock
from commands.commands import start, tasks_command, download_command, tasks_links, download_links, ParseState, DownloadState

@pytest.mark.asyncio
async def test_start_handler():
    message = AsyncMock()
    await start(message)
    message.answer.assert_called_once()
    text = message.answer.call_args[0][0]
    assert "Привет" in text

@pytest.mark.asyncio
async def test_parse_command_sets_state():
    message = AsyncMock()
    state = AsyncMock()
    await tasks_command(message, state)
    message.answer.assert_called_once()
    state.set_state.assert_called_once_with(ParseState.waiting_for_tasks_links)


@pytest.mark.asyncio
async def test_tasks_links_valid_and_invalid_links(mocker):
    # Мок состояния и message
    state = AsyncMock()
    message = AsyncMock()
    message.text = "https://t.me/example1\nhttps://t.me/example1/1234\ninvalidlink"

    # Мок requests.post
    post_mock = mocker.patch("requests.post")
    post_mock.return_value.status_code = 200

    await tasks_links(message, state)

    # Проверяем, что сообщение содержит предупреждение о невалидных ссылках
    message.answer.assert_any_call(mocker.ANY)
    # Проверяем, что состояние очищается
    state.clear.assert_called_once()


@pytest.mark.asyncio
async def test_download_command_sets_state():
    message = AsyncMock()
    state = AsyncMock()

    await download_command(message, state)

    message.answer.assert_called_once()
    state.set_state.assert_called_once_with(DownloadState.waiting_for_download_links)

@pytest.mark.asyncio
async def test_tasks_links_with_valid_and_invalid_links(mocker):
    state = AsyncMock()
    message = AsyncMock()
    message.text = "https://t.me/example1\nhttps://t.me/example1/invalid\ninvalidlink"

    post_mock = mocker.patch("requests.post")
    post_mock.return_value.status_code = 200

    await tasks_links(message, state)

    message.answer.assert_any_call(mocker.ANY)
    state.clear.assert_called_once()

@pytest.mark.asyncio
async def test_download_links_with_no_links():
    message = AsyncMock()
    message.text = "some random text without links"

    await download_links(message)

    message.answer.assert_called_once()
    assert "Ссылки должны начинаться" in message.answer.call_args[0][0]

@pytest.mark.asyncio
async def test_download_links_with_exception(mocker):
    message = AsyncMock()
    message.text = "https://t.me/example1"

    # Имитируем ошибку в openpyxl или в любом другом месте
    mocker.patch("openpyxl.Workbook.save", side_effect=Exception("Test exception"))

    await download_links(message)

    message.answer.assert_called_once()
    assert "Произошла ошибка" in message.answer.call_args[0][0]

@pytest.mark.asyncio
async def test_tasks_links_raises_exception(mocker):
    message = AsyncMock()
    message.text = "https://t.me/example1"

    # Создаем state как MagicMock, но его clear — это AsyncMock
    state = MagicMock()
    state.clear = AsyncMock()

    mocker.patch("requests.post", side_effect=Exception("Test error"))

    await tasks_links(message, state)

    message.answer.assert_called_once()
    assert "Ошибка" in message.answer.call_args[0][0]
    state.clear.assert_awaited_once()


@pytest.mark.asyncio
async def test_start_command():
    message = AsyncMock()
    await start(message)
    message.answer.assert_called_once()
    text = message.answer.call_args[0][0]
    assert "Привет" in text
    assert "/parse" in text
    assert "/download" in text


@pytest.mark.asyncio
async def test_download_command_sets_state():
    message = AsyncMock()
    state = AsyncMock()
    await download_command(message, state)
    message.answer.assert_called_once()
    state.set_state.assert_called_once_with(DownloadState.waiting_for_download_links)



@pytest.mark.asyncio
async def test_tasks_links_with_invalid_links(mocker):
    state = AsyncMock()
    message = AsyncMock()
    message.text = "https://t.me/validlink\nhttps://t.me/invalidlink/123"

    post_mock = mocker.patch("requests.post")
    post_mock.return_value.status_code = 200

    await tasks_links(message, state)

    message.answer.assert_any_call(mocker.ANY)
    assert any("неправильна" in call[0][0] for call in message.answer.call_args_list)
    state.clear.assert_called_once()
