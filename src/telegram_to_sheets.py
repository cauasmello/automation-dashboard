from pathlib import Path
import json
import re
from telethon.tl.types import PeerChannel


from telethon import TelegramClient
import gspread
from google.oauth2.service_account import Credentials

from config import API_ID, API_HASH, CHANNEL, SHEET_ID, WORKSHEET_NAME


BASE_DIR = Path(__file__).resolve().parents[1]

CREDENTIALS_FILE = BASE_DIR / "credentials" / "service_account.json"
STATE_FILE = BASE_DIR / "data" / "state.json"

scopes = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def parse_tipo_e_texto(raw_text):
    # Aceita "Saída:" / "Saida:" / "Entrada:" e ignora maiúsculas/minúsculas
    m = re.match(r"^\s*(sa[ií]da|saida|entrada)\s*:\s*(.*)\s*$", raw_text, flags=re.IGNORECASE)
    if not m:
        return None, None

    tipo_raw = m.group(1).lower()
    tipo = "saida" if tipo_raw.startswith("sa") else "entrada"

    conteudo = m.group(2).strip()

    # Remove aspas envolvendo a mensagem inteira
    if len(conteudo) >= 2:
        if (conteudo[0] == '"' and conteudo[-1] == '"') or (conteudo[0] == "'" and conteudo[-1] == "'"):
            conteudo = conteudo[1:-1].strip()

    return tipo, conteudo

# Data/hora de envio da mensagem no Telegram


def load_state():
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            state_data = json.load(f)
            if "last_id" not in state_data:
                state_data["last_id"] = 0
            return state_data
    except FileNotFoundError:
        return {"last_id": 0}


def save_state(state_data):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state_data, f)


def connect_worksheet():
    creds = Credentials.from_service_account_file(str(CREDENTIALS_FILE), scopes=scopes)
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(SHEET_ID)
    ws = sh.worksheet(WORKSHEET_NAME)
    return ws


def proxima_linha_vazia(ws, col):
    # col = 1 para coluna A (Entrada), 2 para coluna B (Saída)
    col_values = ws.col_values(col)  # só aquela coluna
    return len(col_values) + 1       # próxima linha depois da última não vazia


client = TelegramClient("session", API_ID, API_HASH)


async def main():
    print("Iniciando...")
    print("STATE_FILE:", str(STATE_FILE))
    print("CREDENTIALS_FILE:", str(CREDENTIALS_FILE))

    ws = connect_worksheet()
    print("Conectado na planilha:", SHEET_ID)
    print("Aba:", WORKSHEET_NAME)

    state_data = load_state()
    last_id = int(state_data.get("last_id", 0))
    print("last_id carregado:", last_id)

    channel_val = CHANNEL
    if isinstance(channel_val, int) and channel_val > 0:
        channel_val = int("-100" + str(channel_val))
    entity = await client.get_entity(channel_val)
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
        print("\nLENDO MSG")
        print("id:", msg.id)
        print("texto:", repr(texto_bruto))

        tipo, conteudo = parse_tipo_e_texto(texto_bruto)
        print("PARSE tipo:", tipo)
        print("PARSE conteudo:", repr(conteudo))

        if tipo is None:
            print("PULOU: fora do padrão Entrada:/Saída:")
            max_seen_id = max(max_seen_id, msg.id)
            continue

        # Escreve sempre uma nova linha com 3 colunas:
        # Coluna A = Entrada, Coluna B = Saída, Coluna C = Data/Hora de Envio
        data_envio = msg.date.astimezone().strftime("%Y-%m-%d %H:%M:%S")

        if tipo == "entrada":
            linha = proxima_linha_vazia(ws, 1)
            ws.update_cell(linha, 1, conteudo)
            ws.update_cell(linha, 3, data_envio)
        elif tipo == "saida":
            linha = proxima_linha_vazia(ws, 2)
            ws.update_cell(linha, 2, conteudo)
            ws.update_cell(linha, 3, data_envio)
        print("GRAVOU NA PLANILHA:", tipo)
        max_seen_id = max(max_seen_id, msg.id)

    state_data["last_id"] = max_seen_id
    save_state(state_data)
    print("\nFinalizado.")
    print("last_id atualizado:", max_seen_id)


with client:
    client.loop.run_until_complete(main())