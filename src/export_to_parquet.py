from pathlib import Path
import os
import json

import gspread
from google.oauth2.service_account import Credentials
import pandas as pd

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]


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


def connect_worksheet(sheet_id, worksheet_name, service_account_json):
    service_account_info = json.loads(service_account_json)
    creds = Credentials.from_service_account_info(service_account_info, scopes=SCOPES)
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(sheet_id)
    ws = sh.worksheet(worksheet_name)
    return ws


def main():
    base_dir = _find_base_dir()
    parquet_file = base_dir / "data" / "events.parquet"

    sheet_id = _get_required("SHEET_ID")
    worksheet_name = os.getenv("WORKSHEET_NAME", "Página1")
    service_account_json = _get_required("GOOGLE_SERVICE_ACCOUNT_JSON")

    print("Conectando à planilha...")
    ws = connect_worksheet(sheet_id, worksheet_name, service_account_json)

    values = ws.get_all_values()

    if not values or len(values) <= 1:
        print("Planilha vazia ou só com cabeçalho. Nada para exportar.")
        return

    header = values[0]
    rows = values[1:]

    df = pd.DataFrame(rows, columns=header)

    # Julius: normalize columns for analytics
    # Valor: accept comma decimals; Data: parse ISO/date strings
    col_map = {c.lower().strip(): c for c in df.columns}
    valor_col = col_map.get("valor")
    data_col = col_map.get("data")
    if valor_col:
        df[valor_col] = (df[valor_col].astype(str)
                        .str.replace(".", "", regex=False)
                        .str.replace(",", ".", regex=False))
        df[valor_col] = pd.to_numeric(df[valor_col], errors="coerce")
    if data_col:
        df[data_col] = pd.to_datetime(df[data_col], errors="coerce").dt.date

    exported_at = pd.Timestamp.now(tz="America/Sao_Paulo")
    df["Data/Hora da Exportação"] = exported_at

    parquet_file.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(parquet_file, index=False)
    print("Exportação concluída. Arquivo salvo em: " + str(parquet_file))


if __name__ == "__main__":
    main()