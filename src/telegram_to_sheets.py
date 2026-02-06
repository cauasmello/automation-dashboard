from pathlib import Path
import json
import re
import os
import time

from telethon import TelegramClient
from telethon.sessions import StringSession

import gspread
from gspread.exceptions import APIError
from gspread.utils import rowcol_to_a1
from google.oauth2.service_account import Credentials


def julius_start_telegram_client(client_obj):
    """Start Telethon client without prompting for input() (safe for CI/pipelines)."""
    bot_token_val = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if bot_token_val:
        return client_obj.start(bot_token=bot_token_val)
    raise RuntimeError("Missing TELEGRAM_BOT_TOKEN. Configure it in GitHub Actions Secrets.")

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
    # Parses messages like:
    # Tipo: String
    # Valor: Decimal
    # Descrição: String
    # Cliente: String
    # Forma de Pagamento: String
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

    # Split por linhas; também aceita uma única linha com ';'
    parts = []
    for chunk in re.split(r"[\n\r]+", text_val):
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
    # Garante a linha de cabeçalho e retorna o mapa de colunas
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
    # Procura a primeira linha vazia lendo uma única coluna
    col_vals = ws.col_values(key_col_idx)
    return len(col_vals) + 1

def normalize_date_str(date_in):
    # Normaliza datas para YYYY-MM-DD
    if date_in is None:
        return ""
    s = str(date_in).strip()
    if not s:
        return ""
    s = s.replace(".", "-").replace("/", "-")
    parts = [p for p in s.split("-") if p]
    if len(parts) != 3:
        return s
    if len(parts[0]) == 4:  # YYYY-MM-DD
        yyyy = parts[0]
        mm = parts[1].zfill(2)
        dd = parts[2].zfill(2)
        return yyyy + "-" + mm + "-" + dd
    # DD-MM-YYYY
    dd = parts[0].zfill(2)
    mm = parts[1].zfill(2)
    yyyy = parts[2]
    if len(yyyy) == 2:
        yyyy = "20" + yyyy
    return yyyy + "-" + mm + "-" + dd

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

# -------------------- NOVOS HELPERS (backoff e batch) --------------------

def _is_quota_429(e: APIError) -> bool:
    s = str(e).lower()
    return "429" in s or "quota" in s or "too many requests" in s or "rate" in s

def with_backoff(max_retries=6, base=1.0, cap=32.0):
    """
    Exponential backoff simples para 429: 1s, 2s, 4s, 8s, 16s, 32s.
    """
    def deco(fn):
        def wrapper(*args, **kwargs):
            delay = base
            for _ in range(max_retries):
                try:
                    return fn(*args, **kwargs)
                except APIError as e:
                    if _is_quota_429(e):
                        time.sleep(min(delay, cap))
                        delay *= 2
                    else:
                        raise
            # última tentativa
            return fn(*args, **kwargs)
        return wrapper
    return deco

def _col_letter(col_idx: int) -> str:
    # Converte índice numérico de coluna (1-based) para letra A1
    a1 = rowcol_to_a1(1, col_idx)  # ex.: "C1"
    m = re.match(r"([A-Z]+)", a1)
    return m.group(1) if m else "A"

@with_backoff(max_retries=6, base=1.0)
def batch_write_rows(ws, col_idx_map, rows_matrix, start_row):
    """
    Escreve um conjunto de N linhas usando UMA chamada 'values.batchUpdate',
    escrevendo coluna a coluna (permite colunas não contíguas sem sobrescrever outras).
    rows_matrix: lista de linhas, onde cada linha segue a ordem:
      ["Tipo", "Valor", "Descrição", "Cliente", "Forma de Pagamento", "Data"]
    start_row: número da primeira linha (1-based) onde começar a escrever.
    """
    headers = ["Tipo", "Valor", "Descrição", "Cliente", "Forma de Pagamento", "Data"]

    data_entries = []
    for col_pos, header in enumerate(headers):
        if header not in col_idx_map:
            continue
        cidx = col_idx_map[header]
        letter = _col_letter(cidx)
        rng = f"{letter}{start_row}:{letter}{start_row + len(rows_matrix) - 1}"

        # coluna vertical (N x 1): [[v1],[v2],...]
        col_values = [[row[col_pos] if col_pos < len(row) else ""] for row in rows_matrix]
        data_entries.append({"range": rng, "values": col_values})

    body = {"valueInputOption": "USER_ENTERED", "data": data_entries}
    # 'values_batch_update' chama spreadsheets.values.batchUpdate (uma única escrita)
    return ws.spreadsheet.values_batch_update(body)

# ------------------------------------------------------------------------


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

    # Garante autenticação do bot
    try:
        bot_token_val = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
        if bot_token_val:
            client = client.start(bot_token=bot_token_val)
    except Exception:
        pass

    async with client:
        ch = channel
        if ch.lstrip("-").isdigit():
            ch = int(ch)
        entity = await client.get_entity(ch)
        print("Canal carregado com sucesso.")

        msgs = []
        async for msg in client.iter_messages(entity, min_id=last_id):
            if msg.message:
                msgs.append(msg)
        msgs.sort(key=lambda m: m.id)
        print("Mensagens novas encontradas:", len(msgs))

        max_seen_id = last_id

        # 1) Cabeçalhos uma vez só
        required_headers = ["Tipo", "Valor", "Descrição", "Cliente", "Forma de Pagamento", "Data"]
        col_idx_map = ensure_headers(ws, required_headers)  # pode fazer 1 leitura + 1 escrita se cabeçalho faltar

        # 2) Primeira linha vazia uma única vez
        key_col = col_idx_map.get("Data", 1)  # usamos "Data" como coluna de referência
        start_row = first_empty_row(ws, key_col)

        # 3) Montar o lote de linhas
        rows_to_write = []
        for msg in msgs:
            texto_bruto = (msg.message or "").strip()
            payload = parse_telegram_payload(texto_bruto)
            if payload is None:
                max_seen_id = max(max_seen_id, msg.id)
                continue

            # Data: usa data do payload (normalizada) ou a data do envio (apenas YYYY-MM-DD)
            data_envio = msg.date.astimezone().strftime("%Y-%m-%d %H:%M:%S") if msg.date else ""
            data_norm = normalize_date_str(payload.get("Data"))
            if str(data_norm).strip() == "":
                data_norm = str(data_envio).split(" ")[0] if data_envio else ""

            linha = [
                payload.get("Tipo") or "",
                payload.get("Valor") or "",
                payload.get("Descrição") or "",
                payload.get("Cliente") or "",
                payload.get("Forma de Pagamento") or "",
                data_norm or "",
            ]
            rows_to_write.append(linha)
            max_seen_id = max(max_seen_id, msg.id)

        # 4) Escrita única em lote (reduz drasticamente "write requests/min")
        if rows_to_write:
            batch_write_rows(ws, col_idx_map, rows_to_write, start_row)

        # 5) Atualiza estado uma única vez
        state_data["last_id"] = max_seen_id
        save_state(state_file, state_data)
        print("Finalizado. last_id atualizado:", max_seen_id)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
