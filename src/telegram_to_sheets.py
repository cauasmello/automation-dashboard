from pathlib import Path
import json
import re
import os

from telethon import TelegramClient
from telethon.sessions import StringSession

import gspread
from google.oauth2.service_account import Credentials


def _get_required(name):
    val = os.getenv(name)
    if not val:
        raise RuntimeError("Missing required env var: " + name)
    return val


def _find_base_dir():
    here_dir = Path(__file__).resolve().parent
    if (here_dir / "data").exists() or (here_dir / ".github").exists():
        return here_dir
    if (here_dir.parent / "data").exists() or (here_dir.parent / ".github").exists():
        return here_dir.parent
    return here_dir


def parse_tipo_e_texto(raw_text):
    m = re.match(r"^\s*(sa[ií]da|saida|entrada)\s*:\s*(.*)\s*$", raw_text, flags=re.IGNORECASE)
    if not m:
        return None, None

    tipo_raw = m.group(1).lower()
    tipo = "saida" if tipo_raw.startswith("sa") else "entrada"

    conteudo = m.group(2).strip()

    if len(conteudo) >= 2:
        if (conteudo[0] == '"' and conteudo[-1] == '"') or (conteudo[0] == "'" and conteudo[-1] == "'"):
            conteudo = conteudo[1:-1].strip()

    return tipo, conteudo


def load_state(state_file):
    try:
        with open(state_file, "r", encoding="utf-8") as state_f:
            state_data = json.load(state_f)
            if "last_id" not in state_data:
                state_data["last_id"] = 0
            return state_data
    except FileNotFoundError:
        return {"last_id": 0}


def save_state(state_file, state_data):
    state_file.parent.mkdir(parents=True, exist_ok=True)
    with open(state_file, "w", encoding="utf-8") as state_f:
        json.dump(state_data, state_f)


def connect_worksheet(sheet_id, worksheet_name, service_account_json):
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]

    service_account_info = json.loads(service_account_json)
    creds = Credentials.from_service_account_info(service_account_info, scopes=scopes)
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(sheet_id)
    ws = sh.worksheet(worksheet_name)
    return ws


def proxima_linha_vazia(ws, col):
    col_values = ws.col_values(col)
    return len(col_values) + 1


async def main():
    base_dir = _find_base_dir()
    state_file = base_dir / "data" / "state.json"

    api_id = int(_get_required("API_ID"))
    api_hash = _get_required("API_HASH")
    channel = _get_required("CHANNEL")

    sheet_id = _get_required("SHEET_ID")
    worksheet_name = os.getenv("WORKSHEET_NAME")
    service_account_json = _get_required("GOOGLE_SERVICE_ACCOUNT_JSON")

    telethon_session = os.getenv("TELETHON_SESSION", "").strip()

    if telethon_session:
        client = TelegramClient(StringSession(telethon_session), api_id, api_hash)
    else:
        # Fallback local only. In GitHub Actions this will usually fail because it needs interactive login.
        client = TelegramClient("session", api_id, api_hash)

    print("Iniciando...")
    print("STATE_FILE:", str(state_file))

    ws = connect_worksheet(sheet_id, worksheet_name, service_account_json)
    print("Conectado na planilha:", sheet_id)
    print("Aba:", worksheet_name)

    state_data = load_state(state_file)
    last_id = int(state_data.get("last_id", 0))
    print("last_id carregado:", last_id)

    async with client:
        entity = await client.get_entity(channel)
        print("Canal carregado com sucesso.")

        msgs = []
        async for msg in client.iter_messages(entity, min_id=last_id):
            if msg.message:
                msgs.append(msg)

        msgs.sort(key=lambda m: m.id)
        print("Mensagens novas encontradas:", len(msgs))

        max_seen_id = last_id

        for msg in msgs:
            texto_bruto = (msg.message or "").strip()

            tipo, conteudo = parse_tipo_e_texto(texto_bruto)

            if tipo is None:
                max_seen_id = max(max_seen_id, msg.id)
                continue

            data_envio = msg.date.astimezone().strftime("%Y-%m-%d %H:%M:%S")

            if tipo == "entrada":
                linha = proxima_linha_vazia(ws, 1)
                ws.update_cell(linha, 1, conteudo)
                ws.update_cell(linha, 3, data_envio)
            elif tipo == "saida":
                linha = proxima_linha_vazia(ws, 2)
                ws.update_cell(linha, 2, conteudo)
                ws.update_cell(linha, 3, data_envio)

            max_seen_id = max(max_seen_id, msg.id)

        state_data["last_id"] = max_seen_id
        save_state(state_file, state_data)

        print("Finalizado. last_id atualizado:", max_seen_id)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
