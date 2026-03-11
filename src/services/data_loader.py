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


def _normalize_text_series(series: pd.Series, lower: bool = False) -> pd.Series:
    out = series.astype(str).str.strip()
    out = out.replace({
        "": pd.NA,
        "nan": pd.NA,
        "None": pd.NA,
        "NaT": pd.NA,
    })
    if lower:
        out = out.str.lower()
    return out


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
    cliente_col = col_map.get("cliente")
    forma_pagamento_col = (
        col_map.get("forma de pagamento")
        or col_map.get("forma_pagamento")
    )
    categoria_col = col_map.get("categoria")
    produto_col = col_map.get("produto")
    quantidade_col = col_map.get("quantidade")
    descricao_col = col_map.get("descrição") or col_map.get("descricao")
    valor_col = col_map.get("valor")
    data_col = col_map.get("data")

    if not tipo_col or not valor_col:
        raise ValueError(
            f"Não encontrei as colunas mínimas esperadas. Colunas disponíveis: {list(df.columns)}"
        )

    # ==========================================================
    # Tratamentos numéricos
    # ==========================================================
    df[valor_col] = pd.to_numeric(df[valor_col], errors="coerce")

    if quantidade_col:
        df[quantidade_col] = pd.to_numeric(df[quantidade_col], errors="coerce").astype("Int64")

    # Remove linhas sem valor
    df = df.dropna(subset=[valor_col]).copy()

    # ==========================================================
    # Tratamentos de data
    # ==========================================================
    if data_col:
        df[data_col] = df[data_col].astype(str).str.strip()
        df.loc[df[data_col].isin(["", "None", "nan", "NaT"]), data_col] = None
        df[data_col] = pd.to_datetime(df[data_col], errors="coerce")

    # ==========================================================
    # Tratamentos textuais
    # ==========================================================
    if tipo_col:
        df[tipo_col] = _normalize_text_series(df[tipo_col], lower=True)

    if cliente_col:
        df[cliente_col] = _normalize_text_series(df[cliente_col], lower=False)

    if forma_pagamento_col:
        df[forma_pagamento_col] = _normalize_text_series(df[forma_pagamento_col], lower=True)

    if categoria_col:
        df[categoria_col] = _normalize_text_series(df[categoria_col], lower=True)

    if produto_col:
        df[produto_col] = _normalize_text_series(df[produto_col], lower=True)

    if descricao_col:
        df[descricao_col] = _normalize_text_series(df[descricao_col], lower=False)

    columns = {
        "tipo": tipo_col,
        "cliente": cliente_col,
        "forma_pagamento": forma_pagamento_col,
        "categoria": categoria_col,
        "produto": produto_col,
        "quantidade": quantidade_col,
        "descricao": descricao_col,
        "valor": valor_col,
        "data": data_col,
    }

    return df, columns