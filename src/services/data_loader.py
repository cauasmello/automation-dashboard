from pathlib import Path

import pandas as pd
import streamlit as st


def find_base_dir() -> Path:
    current = Path(__file__).resolve().parent

    for _ in range(6):
        if (current / "data").exists() or (current / ".github").exists():
            return current
        current = current.parent

    return Path(__file__).resolve().parent


def format_brl(valor: float) -> str:
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


@st.cache_data(show_spinner=False)
def load_events() -> tuple[pd.DataFrame, dict]:
    base_dir = find_base_dir()
    parquet_file = base_dir / "data" / "events.parquet"

    if not parquet_file.exists():
        raise FileNotFoundError(
            "Ainda não existe data/events.parquet. Rode export_to_parquet.py antes."
        )

    df = pd.read_parquet(parquet_file).copy()
    col_map = {c.lower().strip(): c for c in df.columns}

    tipo_col = col_map.get("tipo")
    valor_col = col_map.get("valor")
    descricao_col = col_map.get("descrição") or col_map.get("descricao")
    cliente_col = col_map.get("cliente")
    forma_pagamento_col = (
        col_map.get("forma de pagamento")
        or col_map.get("forma_pagamento")
    )
    data_col = col_map.get("data")

    if not tipo_col or not valor_col:
        raise ValueError(
            f"Não encontrei as colunas mínimas esperadas. Colunas disponíveis: {list(df.columns)}"
        )

    df[valor_col] = pd.to_numeric(df[valor_col], errors="coerce")
    df = df.dropna(subset=[valor_col]).copy()

    if data_col:
        df[data_col] = df[data_col].astype(str).str.strip()
        df.loc[df[data_col].isin(["", "None", "nan", "NaT"]), data_col] = None
        df[data_col] = pd.to_datetime(df[data_col], errors="coerce")

    if tipo_col:
        df[tipo_col] = df[tipo_col].astype(str).str.strip().str.lower()

    if cliente_col:
        df[cliente_col] = df[cliente_col].astype(str).str.strip()

    if forma_pagamento_col:
        df[forma_pagamento_col] = (
            df[forma_pagamento_col].astype(str).str.strip().str.lower()
        )

    columns = {
        "tipo": tipo_col,
        "valor": valor_col,
        "descricao": descricao_col,
        "cliente": cliente_col,
        "forma_pagamento": forma_pagamento_col,
        "data": data_col,
    }

    return df, columns