from pathlib import Path
import pandas as pd
import streamlit as st
from datetime import date

def _find_base_dir():
    here_dir = Path(__file__).resolve().parent
    if (here_dir / "data").exists() or (here_dir / ".github").exists():
        return here_dir
    if (here_dir.parent / "data").exists() or (here_dir.parent / ".github").exists():
        return here_dir.parent
    return here_dir

BASE_DIR = _find_base_dir()
PARQUET_FILE = BASE_DIR / "data" / "events.parquet"

st.set_page_config(page_title="Entradas vs Saídas", layout="wide")
st.title("Dashboard - Entradas vs Saídas")

if not PARQUET_FILE.exists():
    st.warning("Ainda não existe data/events.parquet. Aguarde a automação ou rode export_to_parquet.py.")
    st.stop()

df_raw = pd.read_parquet(PARQUET_FILE)

# Tenta padronizar nomes (tolerante a ordem/acentos)
col_map = {c.lower().strip(): c for c in df_raw.columns}
tipo_col = col_map.get("tipo")
valor_col = col_map.get("valor")
descricao_col = col_map.get("descrição")
cliente_col = col_map.get("cliente")
forma_pagamento_col = col_map.get("forma de pagamento")
data_col = col_map.get("data")

if not tipo_col or not valor_col:
    st.info("Não encontrei colunas Tipo/Valor. Colunas disponíveis: " + ", ".join(df_raw.columns))
    st.stop()

# ==========================================
# Preparação dos dados (mantendo 'Data' como date)
# ==========================================
df = df_raw.copy()

# Remove colunas de exportação (se existirem) para não poluir a tabela
_drop_export_cols = [c for c in df.columns if c.lower().strip() in [
    "data/hora da exportação", "data/hora da exportacao",
    "data/hora exportação", "data/hora exportacao",
]]
if _drop_export_cols:
    df = df.drop(columns=_drop_export_cols)

# Normaliza Valor como numérico
df[valor_col] = pd.to_numeric(df[valor_col], errors="coerce")
df = df.dropna(subset=[valor_col])

# -------------------------
# Filtro por intervalo de data (usando somente 'date')
# -------------------------
if data_col:
    # Converte qualquer representação para 'date' (descarta datetime)
    tmp = pd.to_datetime(df[data_col].astype(str).str.strip(), errors="coerce")
    df[data_col] = tmp.dt.date  # <- tipo 'date'

    valid_dates = df[data_col].dropna()
    if not valid_dates.empty:
        min_date = valid_dates.min()
        max_date = valid_dates.max()

        st.subheader("Filtro")
        start_date, end_date = st.date_input(
            "Intervalo de datas)",
            value=(min_date, max_date),
            min_value=min_date,
            max_value=max_date,
            format="DD/MM/YYYY",   # <-- PT-BR no seletor
        )

        if end_date < start_date:
            st.warning("A data final é menor que a data inicial. Ajuste o intervalo.")
            st.stop()

        # Aplica filtro (somente 'date')
        df = df[(df[data_col] >= start_date) & (df[data_col] <= end_date)]

        # ---------- NOVO: Coluna de exibição em PT-BR ----------
        df["Data (BR)"] = df[data_col].apply(
            lambda d: d.strftime("%d/%m/%Y") if pd.notna(d) else ""
        )
    else:
        st.info("Não há valores de data válidos para aplicar filtro.")
        # Mesmo sem filtro, se existir coluna Data, cria exibição PT-BR (vazia)
        df["Data (BR)"] = df.get(data_col, pd.Series([None]*len(df))).apply(
            lambda d: d.strftime("%d/%m/%Y") if pd.notna(d) else ""
        )
else:
    # Caso não exista a coluna "Data", cria "Data (BR)" vazia para evitar KeyError na exibição
    df["Data (BR)"] = ""

# ==========================================
# Métricas e tabela (já usando o DF filtrado)
# ==========================================
df_entrada = df[df[tipo_col].astype(str).str.lower() == "entrada"]
df_saida = df[df[tipo_col].astype(str).str.lower().isin(["saída", "saida"])]

total_entrada = df_entrada[valor_col].sum()
total_saida = df_saida[valor_col].sum()

c1, c2, c3 = st.columns(3)
c1.metric("Total de Entradas (filtrado)", f"R$ {total_entrada:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
c2.metric("Total de Saídas (filtrado)", f"R$ {total_saida:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
c3.metric("Saldo (filtrado)", f"R$ {(total_entrada - total_saida):,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))

st.subheader("Selecione uma linha")

# -------- Exibição: inclui 'Data (BR)' na tabela --------
# Mantemos a coluna original 'Data' (tipo date) para cálculos e filtro,
# mas priorizamos 'Data (BR)' na tabela para visual.
cols_for_view = list(df.columns)
# Garante que 'Data (BR)' aparece imediatamente após 'Data' (se houver)
if data_col and "Data (BR)" in cols_for_view:
    # Move 'Data (BR)' para logo após 'Data'
    cols_for_view.remove("Data (BR)")
    if data_col in cols_for_view:
