import pandas as pd
import streamlit as st

from utils import load_events, format_brl


st.set_page_config(page_title="Análise de Dados", layout="wide")
st.title("Análise de Dados")

try:
    df, cols = load_events()
except FileNotFoundError as e:
    st.warning(str(e))
    st.stop()
except ValueError as e:
    st.error(str(e))
    st.stop()

tipo_col = cols["tipo"]
valor_col = cols["valor"]
descricao_col = cols["descricao"]
cliente_col = cols["cliente"]
data_col = cols["data"]

st.caption("Página analítica: tendência, ranking e resumo gerencial")

# ==========================================================
# Filtros
# ==========================================================
st.sidebar.header("Filtros da análise")

tipos = sorted(df[tipo_col].dropna().astype(str).unique().tolist())
tipos_sel = st.sidebar.multiselect("Tipo", tipos, default=tipos)

if data_col and df[data_col].notna().any():
    data_min = df[data_col].dropna().min().date()
    data_max = df[data_col].dropna().max().date()

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

    df = df[
        (df[data_col].dt.date >= inicio) &
        (df[data_col].dt.date <= fim)
    ].copy()

if tipos_sel:
    df = df[df[tipo_col].isin(tipos_sel)].copy()

if cliente_col:
    clientes = sorted(df[cliente_col].dropna().astype(str).unique().tolist())
    clientes_sel = st.sidebar.multiselect("Cliente", clientes, default=clientes)
    if clientes_sel:
        df = df[df[cliente_col].astype(str).isin(clientes_sel)].copy()

if df.empty:
    st.info("Nenhum dado encontrado para os filtros aplicados.")
    st.stop()

# ==========================================================
# Colunas auxiliares
# ==========================================================
if data_col:
    df["ano_mes"] = df[data_col].dt.to_period("M").astype(str)
else:
    df["ano_mes"] = "Sem data"

# ==========================================================
# Métricas principais
# ==========================================================
entradas = df.loc[df[tipo_col] == "entrada", valor_col].sum()
saidas = df.loc[df[tipo_col].isin(["saída", "saida"]), valor_col].sum()
saldo = entradas - saidas
ticket_medio = df[valor_col].mean()

m1, m2, m3, m4 = st.columns(4)
m1.metric("Entradas", format_brl(entradas))
m2.metric("Saídas", format_brl(saidas))
m3.metric("Saldo", format_brl(saldo))
m4.metric("Ticket médio", format_brl(ticket_medio))

st.divider()

# ==========================================================
# Evolução mensal
# ==========================================================
st.subheader("Evolução mensal")

resumo_mensal = (
    df.groupby(["ano_mes", tipo_col], as_index=False)[valor_col]
    .sum()
    .pivot(index="ano_mes", columns=tipo_col, values=valor_col)
    .fillna(0)
    .reset_index()
)

if "entrada" not in resumo_mensal.columns:
    resumo_mensal["entrada"] = 0

saida_calc = 0
if "saida" in resumo_mensal.columns:
    saida_calc = saida_calc + resumo_mensal["saida"]
if "saída" in resumo_mensal.columns:
    saida_calc = saida_calc + resumo_mensal["saída"]

resumo_mensal["saida_total"] = saida_calc
resumo_mensal["saldo"] = resumo_mensal["entrada"] - resumo_mensal["saida_total"]

st.line_chart(
    resumo_mensal.set_index("ano_mes")[["entrada", "saida_total", "saldo"]]
)

# ==========================================================
# Ranking por cliente
# ==========================================================
if cliente_col:
    st.subheader("Top 10 clientes por valor movimentado")
    ranking_cliente = (
        df.groupby(cliente_col, as_index=False)[valor_col]
        .sum()
        .sort_values(valor_col, ascending=False)
        .head(10)
    )

    if not ranking_cliente.empty:
        st.bar_chart(ranking_cliente.set_index(cliente_col)[valor_col])

# ==========================================================
# Ranking por descrição
# ==========================================================
if descricao_col:
    st.subheader("Top 10 descrições")
    ranking_desc = (
        df.groupby(descricao_col, as_index=False)[valor_col]
        .sum()
        .sort_values(valor_col, ascending=False)
        .head(10)
    )

    st.dataframe(ranking_desc, use_container_width=True, hide_index=True)

# ==========================================================
# Resumo por tipo
# ==========================================================
st.subheader("Resumo por tipo")

resumo_tipo = (
    df.groupby(tipo_col, as_index=False)
    .agg(
        quantidade=(valor_col, "count"),
        valor_total=(valor_col, "sum"),
        valor_medio=(valor_col, "mean"),
    )
    .sort_values("valor_total", ascending=False)
)

st.dataframe(resumo_tipo, use_container_width=True, hide_index=True)

# ==========================================================
# Resumo mensal detalhado
# ==========================================================
st.subheader("Resumo mensal detalhado")
st.dataframe(resumo_mensal, use_container_width=True, hide_index=True)