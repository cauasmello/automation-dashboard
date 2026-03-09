import datetime as dt
import pandas as pd
import streamlit as st

from utils import load_events, format_brl


st.set_page_config(page_title="Dashboard Financeiro", layout="wide")
st.title("Dashboard - Entradas vs Saídas")

try:
    df_raw, cols = load_events()
except FileNotFoundError as e:
    st.warning(str(e))
    st.stop()
except ValueError as e:
    st.error(str(e))
    st.stop()

work_df = df_raw.copy()

tipo_col = cols["tipo"]
valor_col = cols["valor"]
descricao_col = cols["descricao"]
cliente_col = cols["cliente"]
forma_pagamento_col = cols["forma_pagamento"]
data_col = cols["data"]

st.caption("Página principal: visão operacional e consulta dos registros")

# ==========================================================
# Filtros laterais
# ==========================================================
st.sidebar.header("Filtros")

if data_col and work_df[data_col].notna().any():
    data_min = work_df[data_col].dropna().min().date()
    data_max = work_df[data_col].dropna().max().date()

    periodo = st.sidebar.date_input(
        "Período",
        value=(data_min, data_max),
        format="DD/MM/YYYY",
    )

    if isinstance(periodo, tuple) and len(periodo) == 2:
        inicio, fim = periodo
    else:
        inicio = fim = periodo

    if inicio > fim:
        inicio, fim = fim, inicio

    mask_data = (
        (work_df[data_col].dt.date >= inicio) &
        (work_df[data_col].dt.date <= fim)
    )
    work_df = work_df.loc[mask_data].copy()

tipos = sorted(work_df[tipo_col].dropna().astype(str).unique().tolist())
tipos_sel = st.sidebar.multiselect("Tipo", tipos, default=tipos)
if tipos_sel:
    work_df = work_df[work_df[tipo_col].isin(tipos_sel)].copy()

if cliente_col:
    clientes = sorted(work_df[cliente_col].dropna().astype(str).unique().tolist())
    clientes_sel = st.sidebar.multiselect("Cliente", clientes, default=clientes)
    if clientes_sel:
        work_df = work_df[work_df[cliente_col].astype(str).isin(clientes_sel)].copy()

if forma_pagamento_col:
    formas = sorted(work_df[forma_pagamento_col].dropna().astype(str).unique().tolist())
    formas_sel = st.sidebar.multiselect("Forma de pagamento", formas, default=formas)
    if formas_sel:
        work_df = work_df[
            work_df[forma_pagamento_col].astype(str).isin(formas_sel)
        ].copy()

if work_df.empty:
    st.info("Nenhum registro encontrado com os filtros aplicados.")
    st.stop()

# ==========================================================
# Métricas
# ==========================================================
df_entrada = work_df[work_df[tipo_col] == "entrada"]
df_saida = work_df[work_df[tipo_col].isin(["saída", "saida"])]

total_entrada = df_entrada[valor_col].sum()
total_saida = df_saida[valor_col].sum()
saldo = total_entrada - total_saida

c1, c2, c3, c4 = st.columns(4)
c1.metric("Entradas", format_brl(total_entrada))
c2.metric("Saídas", format_brl(total_saida))
c3.metric("Saldo", format_brl(saldo))
c4.metric("Registros", f"{len(work_df)}")

st.divider()

# ==========================================================
# Tabela
# ==========================================================
st.subheader("Registros filtrados")

preview_df = work_df.copy()

if data_col:
    preview_df = preview_df.sort_values(by=data_col, ascending=False)

evento = st.dataframe(
    preview_df,
    use_container_width=True,
    hide_index=True,
    selection_mode="single-row",
    on_select="rerun",
)

selected_rows = []
try:
    selected_rows = evento.selection.get("rows", [])
except Exception:
    selected_rows = []

def val_or_blank(row_obj, col_name):
    if not col_name or col_name not in row_obj.index:
        return ""
    value = row_obj[col_name]
    return "" if pd.isna(value) else str(value)

if len(selected_rows) == 1:
    st.subheader("Detalhes do registro")
    row = preview_df.iloc[int(selected_rows[0])]

    d1, d2 = st.columns(2)
    with d1:
        st.write(f"**Tipo:** {val_or_blank(row, tipo_col)}")
        st.write(f"**Valor:** {val_or_blank(row, valor_col)}")
        st.write(f"**Cliente:** {val_or_blank(row, cliente_col)}")
    with d2:
        st.write(f"**Descrição:** {val_or_blank(row, descricao_col)}")
        st.write(f"**Forma de pagamento:** {val_or_blank(row, forma_pagamento_col)}")
        st.write(f"**Data:** {val_or_blank(row, data_col)}")
else:
    st.caption("Selecione uma linha para ver os detalhes.")