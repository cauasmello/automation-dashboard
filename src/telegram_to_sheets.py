from pathlib import Path
import json
import re
import os

from telethon import TelegramClient
from telethon.sessions import StringSession

import gspread
from google.oauth2.service_account import Credentials

# --- Julius: non-interactive Telegram auth helper ---
def julius_start_telegram_client(client_obj):
    """Start Telethon client without prompting for input() (safe for CI/pipelines)."""
    bot_token_val = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if bot_token_val:
        return client_obj.start(bot_token=bot_token_val)
    raise RuntimeError("Missing TELEGRAM_BOT_TOKEN. Configure it in GitHub Actions Secrets.")
# --- /Julius helper ---



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

def parse_telegram_payload(raw_text):
    # Parses messages like (multiline or single-line):
    # Tipo: String
    # Valor: Decimal
    # Descrição: String
    # Cliente: String
    # Forma de Pagamento: String
    #
    # Accepts separators ':' or '=' and ignores surrounding quotes.
    if raw_text is None:
        return None

    text_val = str(raw_text).strip()
    if text_val == "":
        return None

    field_aliases = {
        "tipo": "Tipo",
        "valor": "Valor",
        "descrição": "Descrição",
        "descricao": "Descrição",
        "cliente": "Cliente",
        "forma de pagamento": "Forma de Pagamento",
        "forma_pagamento": "Forma de Pagamento",
        "forma": "Forma de Pagamento",
        "pagamento": "Forma de Pagamento",
        "data": "Data",
    }

    out = {
        "Tipo": None,
        "Valor": None,
        "Descrição": None,
        "Cliente": None,
        "Forma de Pagamento": None,
        "Data": None,
    }

    parts = []
    for chunk in re.split(r"[]+", text_val):
        chunk2 = chunk.strip()
        if chunk2 != "":
            parts.append(chunk2)

    if len(parts) == 1 and ";" in parts[0]:
        parts = [p.strip() for p in parts[0].split(";") if p.strip()]

    for part in parts:
        m = re.match(r"^\s*([^:=]+?)\s*[:=]\s*(.*)\s*$", part)
        if not m:
            continue

        key_raw = m.group(1).strip().lower()
        val_raw = m.group(2).strip()
        val_raw = val_raw.strip('"').strip("'")

        key_norm = re.sub(r"\s+", " ", key_raw)
        if key_norm in field_aliases:
            out[field_aliases[key_norm]] = val_raw

    # Normalize Tipo values
    if out.get("Tipo"):
        tipo_norm = str(out.get("Tipo")).strip().lower()
        if tipo_norm in ["entrada", "in", "receita", "+"]:
            out["Tipo"] = "Entrada"
        elif tipo_norm in ["saída", "saida", "out", "despesa", "-"]:
            out["Tipo"] = "Saída"

    if not out.get("Tipo") and not out.get("Valor"):
        return None

    return out
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



def ensure_headers(ws, required_headers):
    # Ensures header row (row 1) contains required headers, appending any missing ones.
    existing = ws.row_values(1)
    existing_norm = [str(x).strip() for x in existing]
    changed = False
    for h in required_headers:
        if h not in existing_norm:
            existing_norm.append(h)
            changed = True
    if changed:
        ws.update("A1", [existing_norm])
    return {h: (existing_norm.index(h) + 1) for h in existing_norm}


def first_empty_row(ws, key_col_idx):
    # Finds first empty row by scanning a single column
    col_vals = ws.col_values(key_col_idx)
    return len(col_vals) + 1


def write_payload_row(ws, col_idx_map, payload, data_envio):
    # Writes a complete row using the column map.
    row_idx = first_empty_row(ws, col_idx_map.get("Data", 1))

    if payload.get("Entrada") is not None:
        ws.update_cell(row_idx, col_idx_map["Entrada"], payload.get("Entrada"))

    if payload.get("Saida") is not None:
        ws.update_cell(row_idx, col_idx_map["Saida"], payload.get("Saida"))

    ws.update_cell(row_idx, col_idx_map["Data"], data_envio)

    if "TipoDespesa" in col_idx_map and payload.get("TipoDespesa") is not None:
        ws.update_cell(row_idx, col_idx_map["TipoDespesa"], payload.get("TipoDespesa"))

    if "TipoProduto" in col_idx_map and payload.get("TipoProduto") is not None:
        ws.update_cell(row_idx, col_idx_map["TipoProduto"], payload.get("TipoProduto"))

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

    bot_token_val = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()

    if telethon_session:
        client = TelegramClient(StringSession(telethon_session), api_id, api_hash)
    else:
        if not bot_token_val:
            raise RuntimeError("Missing TELEGRAM_BOT_TOKEN. Configure it in GitHub Actions Secrets.")
        client = TelegramClient("bot_session", api_id, api_hash).start(bot_token=bot_token_val)

    print("Iniciando...")
    print("STATE_FILE:", str(state_file))

    ws = connect_worksheet(sheet_id, worksheet_name, service_account_json)
    print("Conectado na planilha:", sheet_id)
    print("Aba:", worksheet_name)

    state_data = load_state(state_file)
    last_id = int(state_data.get("last_id", 0))
    print("last_id carregado:", last_id)

    # Ensure bot auth is active before entering async context (avoids input() in CI)
    try:
        bot_token_val = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
        if bot_token_val:
            client = client.start(bot_token=bot_token_val)
    except Exception:
        pass

    async with client:
        channel = os.getenv("CHANNEL", "").strip()
        if channel.lstrip("-").isdigit():
            channel = int(channel)
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

            payload = parse_telegram_payload(texto_bruto)

            data_str = payload.get("Data")
            if not data_str:
                data_str = msg.date.date().isoformat() if msg.date else ""
            else:
                data_str = str(data_str).strip()
            row_data = [payload.get("Tipo"), payload.get("Valor"), payload.get("Descrição"), payload.get("Cliente"), payload.get("Forma de Pagamento"), data_str]

            if payload is None:

                max_seen_id = max(max_seen_id, msg.id)

                continue

            data_envio = msg.date.astimezone().strftime("%Y-%m-%d %H:%M:%S")

            required_headers = ["Tipo", "Valor", "Descrição", "Cliente", "Forma de Pagamento", "Data"]

            col_idx_map = ensure_headers(ws, required_headers)

            write_payload_row(ws, col_idx_map, payload, data_envio)

            max_seen_id = max(max_seen_id, msg.id)

        state_data["last_id"] = max_seen_id
        save_state(state_file, state_data)

        print("Finalizado. last_id atualizado:", max_seen_id)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())