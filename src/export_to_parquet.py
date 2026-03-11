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


def normalize_text_series(series: pd.Series, lower: bool = False) -> pd.Series:
    out = series.astype(str).str.strip()
    out = out.replace({"": pd.NA, "nan": pd.NA, "None": pd.NA})
    if lower:
        out = out.str.lower()
    return out


def normalize_decimal_series(series: pd.Series) -> pd.Series:
    """
    Trata valores como:
    1234,56
    1.234,56
    1234.56
    """
    s = series.astype(str).str.strip()
    s = s.replace({"": pd.NA, "nan": pd.NA, "None": pd.NA})

    # se tiver vírgula, assume padrão BR e remove pontos de milhar
    has_comma = s.str.contains(",", na=False)

    s_br = (
        s.where(has_comma)
        .astype("string")
        .str.replace(".", "", regex=False)
        .str.replace(",", ".", regex=False)
    )

    s_en = s.where(~has_comma).astype("string")

    s_final = s_en.fillna(s_br)
    return pd.to_numeric(s_final, errors="coerce")


def normalize_integer_series(series: pd.Series) -> pd.Series:
    s = pd.to_numeric(series, errors="coerce")
    return s.astype("Int64")


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

    # mapa de colunas tolerante a maiúsculas/minúsculas e acentos básicos
    col_map = {str(c).lower().strip(): c for c in df.columns}

    tipo_col = col_map.get("tipo")
    cliente_col = col_map.get("cliente")
    forma_pagamento_col = col_map.get("forma de pagamento") or col_map.get("forma_pagamento")
    categoria_col = col_map.get("categoria")
    produto_col = col_map.get("produto")
    quantidade_col = col_map.get("quantidade")
    descricao_col = col_map.get("descrição") or col_map.get("descricao")
    valor_col = col_map.get("valor")
    data_col = col_map.get("data")

    # ==========================================================
    # Normalizações
    # ==========================================================
    if tipo_col:
        df[tipo_col] = normalize_text_series(df[tipo_col], lower=True)

    if cliente_col:
        df[cliente_col] = normalize_text_series(df[cliente_col], lower=False)

    if forma_pagamento_col:
        df[forma_pagamento_col] = normalize_text_series(df[forma_pagamento_col], lower=True)

    if categoria_col:
        df[categoria_col] = normalize_text_series(df[categoria_col], lower=True)

    if produto_col:
        df[produto_col] = normalize_text_series(df[produto_col], lower=True)

    if descricao_col:
        df[descricao_col] = normalize_text_series(df[descricao_col], lower=False)

    if quantidade_col:
        df[quantidade_col] = normalize_integer_series(df[quantidade_col])

    if valor_col:
        df[valor_col] = normalize_decimal_series(df[valor_col])

    if data_col:
        df[data_col] = pd.to_datetime(df[data_col], errors="coerce")

    # remove linhas totalmente vazias nas colunas principais
    colunas_principais = [
        c for c in [
            tipo_col,
            cliente_col,
            forma_pagamento_col,
            categoria_col,
            produto_col,
            quantidade_col,
            descricao_col,
            valor_col,
            data_col,
        ] if c is not None
    ]

    if colunas_principais:
        df = df.dropna(how="all", subset=colunas_principais).copy()

    exported_at = pd.Timestamp.now(tz="America/Sao_Paulo")
    df["Data/Hora da Exportação"] = exported_at

    parquet_file.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(parquet_file, index=False)

    print("Exportação concluída. Arquivo salvo em: " + str(parquet_file))
    print("Quantidade de registros exportados:", len(df))
    print("Colunas exportadas:", list(df.columns))


if __name__ == "__main__":
    main()