from pathlib import Path
import pandas as pd
import streamlit as st

BASE_DIR = Path(__file__).resolve().parent
PARQUET_FILE = BASE_DIR / "data" / "events.parquet"

st.set_page_config(page_title="Entradas vs Saídas", layout="wide")

st.title("Dashboard - Entradas vs Saídas")

if not PARQUET_FILE.exists():
    st.warning("Ainda não existe data/events.parquet. Rode export_to_parquet.py primeiro.")
    st.stop()

df_raw = pd.read_parquet(PARQUET_FILE)
st.caption("Total de linhas no Parquet: " + str(len(df_raw)))

# Normaliza nomes esperados (por segurança)
rename_map = {}
if "Data" in df_raw.columns and "Data/Hora de Envio" not in df_raw.columns:
    rename_map["Data"] = "Data/Hora de Envio"
if rename_map:
    df_raw = df_raw.rename(columns=rename_map)

# Garante colunas principais existam
for col in ["Entrada", "Saída"]:
    if col not in df_raw.columns:
        df_raw[col] = ""

# Cria eventos (uma linha no Sheets pode virar 0, 1 ou 2 eventos)
rows = []
for idx_val, r in df_raw.iterrows():
    sheet_row_val = idx_val + 2
    envio_val = r.get("Data/Hora de Envio", "")
    export_val = r.get("Data/Hora da Exportação", "")

    entrada_val = str(r.get("Entrada", "") if r.get("Entrada", "") is not None else "").strip()
    saida_val = str(r.get("Saída", "") if r.get("Saída", "") is not None else "").strip()

    if entrada_val != "" and entrada_val.lower() != "nan":
        rows.append({
            "tipo": "entrada",
            "conteudo": entrada_val,
            "Data/Hora de Envio": envio_val,
            "Data/Hora da Exportação": export_val,
            "sheet_row": sheet_row_val,
        })

    if saida_val != "" and saida_val.lower() != "nan":
        rows.append({
            "tipo": "saida",
            "conteudo": saida_val,
            "Data/Hora de Envio": envio_val,
            "Data/Hora da Exportação": export_val,
            "sheet_row": sheet_row_val,
        })

df_events = pd.DataFrame(rows)
if len(df_events) == 0:
    st.warning("Não há eventos para mostrar. Verifique se as colunas Entrada/Saída têm valores.")
    st.stop()

# Datas
if "Data/Hora de Envio" in df_events.columns:
    df_events["Data/Hora de Envio"] = pd.to_datetime(df_events["Data/Hora de Envio"], errors="coerce")
if "Data/Hora da Exportação" in df_events.columns:
    df_events["Data/Hora da Exportação"] = pd.to_datetime(df_events["Data/Hora da Exportação"], errors="coerce")

# Métricas
col_a, col_b, col_c = st.columns(3)
col_a.metric("Entradas", str((df_events["tipo"] == "entrada").sum()))
col_b.metric("Saídas", str((df_events["tipo"] == "saida").sum()))
col_c.metric("Linhas únicas no Sheets", str(df_events["sheet_row"].nunique()))

# Série temporal: usa Data/Hora de Envio se existir; senão cai para exportação
if df_events["Data/Hora de Envio"].notna().any():
    df_events["dia"] = df_events["Data/Hora de Envio"].dt.date
    st.caption("Agrupando por dia usando Data/Hora de Envio")
else:
    df_events["dia"] = df_events["Data/Hora da Exportação"].dt.date
    st.caption("Agrupando por dia usando Data/Hora da Exportação")

df_daily = df_events.groupby(["dia", "tipo"]).size().reset_index(name="qtd")
df_pivot = df_daily.pivot(index="dia", columns="tipo", values="qtd").fillna(0).sort_index()

st.subheader("Eventos por dia (contagem)")
st.line_chart(df_pivot)

st.subheader("Amostra dos eventos")
st.dataframe(df_events.sort_values(["sheet_row", "tipo"]).tail(100), width="stretch")