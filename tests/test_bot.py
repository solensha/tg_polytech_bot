# tests/test_commands.py
import os
import sys
import pytest

# Добавляем путь к модулю Bot/commands
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "Bot")))

from unittest.mock import MagicMock, AsyncMock

# Импортируем тестируемые сущности
from commands.commands import (
    start,
    tasks_command,
    download_command,
    tasks_links,
    download_links,
    ParseState,
    DownloadState,
)

# ============================================================
# Хелперы
# ============================================================

def assert_any_response_sent(message):
    """
    Проверяет, что бот что-то отправил пользователю:
    текст (answer/reply) или файл (answer_document/reply_document).
    """
    total = 0
    for name in ("answer", "reply", "answer_document", "reply_document"):
        meth = getattr(message, name, None)
        if hasattr(meth, "await_count"):
            total += meth.await_count
    assert total >= 1, "Ожидался хотя бы один ответ (text/document), но вызовов не было"


def make_message(text: str = "") -> AsyncMock:
    m = AsyncMock()
    m.text = text
    # страхуемся: некоторые тесты прямо вызывают эти методы
    m.answer = AsyncMock()
    m.reply = AsyncMock()
    m.answer_document = AsyncMock()
    m.reply_document = AsyncMock()
    return m


# ============================================================
# 0) Smoke-тесты (быстрые проверки на жизнь)
# ============================================================

@pytest.mark.asyncio
async def test_start_contains_commands__01():
    message = make_message()
    await start(message)
    message.answer.assert_awaited()
    txt = message.answer.call_args[0][0]
    assert "Привет" in txt
    assert "/parse" in txt
    assert "/download" in txt


@pytest.mark.asyncio
async def test_tasks_command_sets_state__02():
    message = make_message()
    state = AsyncMock()
    await tasks_command(message, state)
    message.answer.assert_awaited()
    state.set_state.assert_awaited_once_with(ParseState.waiting_for_tasks_links)


@pytest.mark.asyncio
async def test_download_command_sets_state__03():
    message = make_message()
    state = AsyncMock()
    await download_command(message, state)
    message.answer.assert_awaited()
    state.set_state.assert_awaited_once_with(DownloadState.waiting_for_download_links)


@pytest.mark.asyncio
async def test_tasks_command_idempotent__04():
    message = make_message()
    state = AsyncMock()
    await tasks_command(message, state)
    await tasks_command(message, state)
    assert state.set_state.await_count == 2


@pytest.mark.asyncio
async def test_download_command_idempotent__05():
    message = make_message()
    state = AsyncMock()
    await download_command(message, state)
    await download_command(message, state)
    assert state.set_state.await_count == 2


# ============================================================
# 1) Классы эквивалентности для /parse (валидные и невалидные)
#    — позитивные кейсы отправки в backend и ошибки
# ============================================================

VALID_PARSE_INPUTS = [
    "https://t.me/a",
    "https://t.me/a/1",
    "https://t.me/chan_name",
    "https://t.me/chan_name/123",
    "https://t.me/a\nhttps://t.me/b",
    "https://t.me/a\r\nhttps://t.me/b",
    " https://t.me/a \n  https://t.me/b/42 ",
]

INVALID_PARSE_INPUTS = [
    "",
    " \n\t ",
    "hello world",
    "www.example.com",
    "t.me/without_schema",
    "https:/t.me/broken",
    "mailto:user@example.com",
]

@pytest.mark.asyncio
@pytest.mark.parametrize("payload", VALID_PARSE_INPUTS, ids=[f"valid_{i+1:02d}" for i in range(len(VALID_PARSE_INPUTS))])
async def test_tasks_links_valid_equivalence__06_to_12(payload, mocker):
    state = AsyncMock()
    message = make_message(payload)
    post_mock = mocker.patch("requests.post")
    post_mock.return_value.status_code = 200

    await tasks_links(message, state)

    assert message.answer.await_count >= 1
    state.clear.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("payload", INVALID_PARSE_INPUTS, ids=[f"invalid_{i+1:02d}" for i in range(len(INVALID_PARSE_INPUTS))])
async def test_tasks_links_invalid_equivalence__13_to_19(payload):
    state = AsyncMock()
    message = make_message(payload)
    # В невалидных кейсах хендлер сам должен сообщить об ошибке формата
    await tasks_links(message, state)
    message.answer.assert_awaited()
    # Должно быть упоминание о неправильном формате или требуемом префиксе
    sent = message.answer.call_args[0][0]
    assert "http" in sent or "https" in sent or "ссылк" in sent.lower()
    state.clear.assert_awaited()


# ============================================================
# 2) Граничные значения — количество ссылок и длины
#    - 0, 1, 2, 5 (микро-стресс), а также длинная ссылка
# ============================================================

BOUNDARY_PAYLOADS = [
    "",  # 0 ссылок
    "https://t.me/a",  # 1
    "https://t.me/a\nhttps://t.me/b",  # 2
    "\n".join([f"https://t.me/c{i}" for i in range(5)]),  # 5 ссылок
    "https://t.me/" + "a"*200,  # длинное имя канала
]

@pytest.mark.asyncio
@pytest.mark.parametrize("payload", BOUNDARY_PAYLOADS, ids=["n0","n1","n2","n5","long"])
async def test_tasks_links_boundary_values__20_to_24(payload, mocker):
    state = AsyncMock()
    message = make_message(payload)

    post_mock = mocker.patch("requests.post")
    post_mock.return_value.status_code = 200

    await tasks_links(message, state)
    # В любом случае пользователь получает ответ
    assert message.answer.await_count >= 1
    # Стейт должен очищаться
    state.clear.assert_awaited()


# ============================================================
# 3) Попарное тестирование (/parse):
#    измеряем влияние комбинаций:
#    - schema: http/https
#    - тип ссылки: канал/пост
#    - разделитель: пробел/перенос
#    - наличие лишних пробелов: да/нет
# ============================================================

SCHEMAS = ["http", "https"]
LINK_TYPES = ["chan", "post"]  # chan => /name, post => /name/123
SEPARATORS = ["space", "nl"]
TRIM = [False, True]

def build_pair(schema, ltype, sep, trim):
    base1 = f"{schema}://t.me/x"
    base2 = f"{schema}://t.me/y"
    if ltype == "post":
        base1 += "/111"
        base2 += "/222"
    link1 = base1 if not trim else f"  {base1}  "
    link2 = base2 if not trim else f"  {base2}  "
    return (f"{link1} {link2}" if sep == "space" else f"{link1}\n{link2}")

PAIRWISE_CASES = [
    build_pair(schema, ltype, sep, trim)
    for schema in SCHEMAS
    for ltype in LINK_TYPES
    for sep in SEPARATORS
    for trim in TRIM
]

@pytest.mark.asyncio
@pytest.mark.parametrize("payload", PAIRWISE_CASES, ids=[f"pw_{i+1:02d}" for i in range(len(PAIRWISE_CASES))])
async def test_tasks_links_pairwise__25_to_40(payload, mocker):
    state = AsyncMock()
    message = make_message(payload)
    post_mock = mocker.patch("requests.post")
    post_mock.return_value.status_code = 200

    await tasks_links(message, state)

    assert message.answer.await_count >= 1
    state.clear.assert_awaited()


# ============================================================
# 4) Разные HTTP-статусы от backend (негативные сценарии)
# ============================================================

STATUSES = [400, 401, 403, 404, 408, 409, 413, 429, 500, 503]

@pytest.mark.asyncio
@pytest.mark.parametrize("status", STATUSES, ids=[f"http_{s}" for s in STATUSES])
async def test_tasks_links_http_statuses__41_to_50(status, mocker):
    state = AsyncMock()
    message = make_message("https://t.me/example")
    post_mock = mocker.patch("requests.post")
    post_mock.return_value.status_code = status

    await tasks_links(message, state)

    # Должно быть сообщение пользователю об ошибке/результате
    assert message.answer.await_count >= 1
    # Состояние очищается даже при ошибках
    state.clear.assert_awaited_once()


# ============================================================
# 5) Исключения: сетевые/сохранение файла
# ============================================================

@pytest.mark.asyncio
async def test_tasks_links_requests_exception__51(mocker):
    message = make_message("https://t.me/example1")
    state = AsyncMock()
    mocker.patch("requests.post", side_effect=Exception("boom"))
    await tasks_links(message, state)
    message.answer.assert_awaited()
    # Сообщение должно подсветить ошибку
    assert "ошиб" in message.answer.call_args[0][0].lower() or "error" in message.answer.call_args[0][0].lower()
    state.clear.assert_awaited_once()


@pytest.mark.asyncio
async def test_download_links_openpyxl_exception__52(mocker):
    message = make_message("https://t.me/example1")
    mocker.patch("openpyxl.Workbook.save", side_effect=Exception("Test exception"))
    await download_links(message)
    message.answer.assert_awaited()
    assert "ошиб" in message.answer.call_args[0][0].lower() or "error" in message.answer.call_args[0][0].lower()


# ============================================================
# 6) /download — классы эквивалентности (нет ссылок / есть ссылки)
# ============================================================

NO_LINK_TEXTS = [
    "hello world",
    "без ссылок вообще",
    "https:/t.me/missed_slash",
    "t.me but missing schema",
    "www.example.com",
    "12345",
    "   \n\t  ",
    "mailto:abc@ex.com",
    "https://github.com/user/repo",
    "not a link at all",
]

@pytest.mark.asyncio
@pytest.mark.parametrize("payload", NO_LINK_TEXTS, ids=[f"nolink_{i+1:02d}" for i in range(len(NO_LINK_TEXTS))])
async def test_download_links_no_links__53_to_62(payload):
    message = make_message(payload)
    await download_links(message)
    message.answer.assert_awaited()
    assert "начинаться" in message.answer.call_args[0][0].lower() or "ссылк" in message.answer.call_args[0][0].lower()


VALID_DOWNLOAD_INPUTS = [
    "https://t.me/a",
    "https://t.me/a/123",
    "https://t.me/a\nhttps://t.me/b",
    "https://t.me/chan_1\nhttps://t.me/chan_2/777",
    "https://t.me/abc\n\nhttps://t.me/def/1",
    " https://t.me/some_chat ",
]

@pytest.mark.asyncio
@pytest.mark.parametrize("payload", VALID_DOWNLOAD_INPUTS, ids=[f"dl_ok_{i+1:02d}" for i in range(len(VALID_DOWNLOAD_INPUTS))])
async def test_download_links_success__63_to_68(payload, mocker):
    message = make_message(payload)
    # не пишем реальный файл на диск
    mocker.patch("openpyxl.Workbook.save", return_value=None)

    await download_links(message)

    # допускаем, что либо был текстовый ответ, либо отправка документа
    assert_any_response_sent(message)


# ============================================================
# 7) /download — граничные значения по количеству ссылок
# ============================================================

DL_BOUNDARY = [
    "",  # 0
    "https://t.me/a",  # 1
    "https://t.me/a\nhttps://t.me/b",  # 2
    "\n".join([f"https://t.me/c{i}" for i in range(5)]),  # 5
]

@pytest.mark.asyncio
@pytest.mark.parametrize("payload", DL_BOUNDARY, ids=["dl0","dl1","dl2","dl5"])
async def test_download_links_boundary_counts__69_to_72(payload, mocker):
    message = make_message(payload)
    mocker.patch("openpyxl.Workbook.save", return_value=None)
    await download_links(message)
    assert_any_response_sent(message)


# ============================================================
# 8) /download — разные разделители и пробелы (попарное с trim/sep)
# ============================================================

DL_SEPARATORS = ["space", "tab", "nl"]
DL_TRIM = [False, True]

def build_dl_payload(sep, trim):
    a = "https://t.me/a"
    b = "https://t.me/b/10"
    if trim:
        a = f"  {a}  "
        b = f"  {b}  "
    if sep == "space":
        return f"{a} {b}"
    if sep == "tab":
        return f"{a}\t{b}"
    return f"{a}\n{b}"

DL_PAIRWISE = [build_dl_payload(s, t) for s in DL_SEPARATORS for t in DL_TRIM]

@pytest.mark.asyncio
@pytest.mark.parametrize("payload", DL_PAIRWISE, ids=[f"dl_pw_{i+1:02d}" for i in range(len(DL_PAIRWISE))])
async def test_download_links_pairwise__73_to_78(payload, mocker):
    message = make_message(payload)
    mocker.patch("openpyxl.Workbook.save", return_value=None)
    await download_links(message)
    assert_any_response_sent(message)
