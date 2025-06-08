from telethon.sync import TelegramClient
from telethon.sessions import StringSession

with TelegramClient(
    StringSession(),
    25626122,
    "c76965d766df96290ee0575527656292",
    system_version="4.16.30-vxCUSTOM",
    device_model="Samsung Galaxy S21 Ultra 5G",
) as client:
    string = client.session.save()
    print(string)
    me = client.get_me()
    print("Вы вошли как:", me)
