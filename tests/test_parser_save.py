import os
import sys
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'Parser')))

@patch("parser_save.db")
@pytest.mark.asyncio
async def test_background_save_success(mock_db):
    from parser_save import background_save

    mock_users = MagicMock()
    mock_users.insert_many = MagicMock()

    mock_chats = MagicMock()
    mock_links = MagicMock()

    mock_db.return_value = {
        "users": mock_users,
        "chats": mock_chats,
        "links": mock_links,
    }

    fake_data = {
        "accounts": {
            1: {
                "chats": set([100]),
                "info": {
                    "username": "testuser",
                    "first_name": "Test",
                    "last_name": "User",
                    "last_online": "2024-01-01 10:00:00",
                    "bio": "test",
                    "premium": False,
                    "phone": "123456",
                    "image": True,
                },
            }
        },
        "chats": {
            100: {
                "parent_link": "https://t.me/source",
                "children_link": "https://t.me/testchat",
                "title": "Test Chat",
                "last_online": "2024-01-01 10:00:00",
            }
        },
    }

    await background_save(fake_data)

    assert mock_db.called
    assert mock_users.insert_many.called
