from pathlib import Path
import pandas as pd
import streamlit as st


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

st.subheader("Prévia")
st.dataframe(df_raw.head(20), use_container_width=True)

# Tenta padronizar nomes (tolerante a ordem/acentos)
col_map = {c.lower().strip(): c for c in df_raw.columns}

entrada_col = col_map.get("entrada")
saida_col = col_map.get("saída") or col_map.get("saida")
data_col = col_map.get("data")

if not entrada_col or not saida_col:
    st.info("Não encontrei colunas Entrada/Saída. Colunas disponíveis: " + ", ".join(df_raw.columns))
    st.stop()

# Normaliza valores para numérico
work_df = df_raw.copy()
for c in [entrada_col, saida_col]:
    work_df[c] = (
        work_df[c]
        .astype(str)
        .str.replace(".", "", regex=False)
        .str.replace(",", ".", regex=False)
    )
    work_df[c] = pd.to_numeric(work_df[c], errors="coerce")

if data_col:
    work_df[data_col] = pd.to_datetime(work_df[data_col], errors="coerce")

st.subheader("Totais")
col1, col2 = st.columns(2)
col1.metric("Total Entrada", float(work_df[entrada_col].fillna(0).sum()))
col2.metric("Total Saída", float(work_df[saida_col].fillna(0).sum()))
