from telethon import TelegramClient
from config import API_ID, API_HASH

client = TelegramClient("session", API_ID, API_HASH)

async def main():
    dialogs = await client.get_dialogs(limit=200)
    for d in dialogs:
        ent = d.entity
        title = getattr(ent, "title", "")
        username = getattr(ent, "username", "")
        ent_type = type(ent).__name__
        print(str(ent_type) + " | " + str(title) + " | @" + str(username) + " | id=" + str(ent.id))

with client:
    client.loop.run_until_complete(main())