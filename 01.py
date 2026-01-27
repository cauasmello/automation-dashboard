from telethon.sync import TelegramClient
from telethon.sessions import StringSession
import os

api_id = int(input("API_ID: ").strip())
api_hash = input("API_HASH: ").strip()
session = input("TELETHON_SESSION: ").strip()

with TelegramClient(StringSession(session), api_id, api_hash) as client:
    for d in client.iter_dialogs():
        title = (d.name or "").replace("\n", " ")
        print(d.id, " | ", title)