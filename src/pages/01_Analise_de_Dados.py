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
forma_pagamento_col = cols["forma_pagamento"]
data_col = cols["data"]

st.caption("Página analítica: tendência, ranking e resumo gerencial")

# ==========================================================
# Helpers
# ==========================================================
def aplicar_filtros(
    df: pd.DataFrame,
    inicio=None,
    fim=None,
    tipos=None,
    clientes=None,
    formas=None,
):
    out = df.copy()

    if data_col and inicio and fim and out[data_col].notna().any():
        out = out[
            (out[data_col].dt.date >= inicio) &
            (out[data_col].dt.date <= fim)
        ].copy()

    if tipos:
        out = out[out[tipo_col].astype(str).isin(tipos)].copy()

    if cliente_col and clientes:
        out = out[out[cliente_col].astype(str).isin(clientes)].copy()

    if forma_pagamento_col and formas:
        out = out[out[forma_pagamento_col].astype(str).isin(formas)].copy()

    return out


def limpar_selecao_invalida(selecionados, disponiveis):
    if not selecionados:
        return []
    return [x for x in selecionados if x in disponiveis]


# ==========================================================
# Estado inicial
# ==========================================================
if "filtro_tipo" not in st.session_state:
    st.session_state["filtro_tipo"] = []

if "filtro_cliente" not in st.session_state:
    st.session_state["filtro_cliente"] = []

if "filtro_forma" not in st.session_state:
    st.session_state["filtro_forma"] = []


# ==========================================================
# Sidebar - Período
# ==========================================================
st.sidebar.header("Filtros")

df_base = df.copy()
inicio = None
fim = None

if data_col and df_base[data_col].notna().any():

    data_min = df_base[data_col].dropna().min().date()
    data_max = df_base[data_col].dropna().max().date()

    periodo = st.sidebar.date_input(
        "Período",
        value=(data_min, data_max),
        format="DD/MM/YYYY",
    )

    # usuário selecionou apenas uma data
    if isinstance(periodo, tuple) and len(periodo) == 1:
        st.warning("Selecione a data final para completar o intervalo.")
        st.stop()

    # intervalo correto
    elif isinstance(periodo, tuple) and len(periodo) == 2:
        inicio, fim = periodo

        if inicio > fim:
            inicio, fim = fim, inicio

    else:
        st.warning("Selecione um intervalo de datas válido.")
        st.stop()


# ==========================================================
# Leitura das seleções atuais
# ==========================================================
tipos_sel_atual = st.session_state["filtro_tipo"]
clientes_sel_atual = st.session_state["filtro_cliente"]
formas_sel_atual = st.session_state["filtro_forma"]


# ==========================================================
# OPÇÕES DE TIPO
# Data + Cliente + Forma
# ==========================================================
df_tipo = aplicar_filtros(
    df_base,
    inicio=inicio,
    fim=fim,
    clientes=clientes_sel_atual,
    formas=formas_sel_atual,
)

tipos_disponiveis = sorted(
    df_tipo[tipo_col].dropna().astype(str).unique().tolist()
)

st.session_state["filtro_tipo"] = limpar_selecao_invalida(
    st.session_state["filtro_tipo"],
    tipos_disponiveis,
)

st.sidebar.multiselect(
    "Tipo",
    options=tipos_disponiveis,
    key="filtro_tipo",
)


# ==========================================================
# OPÇÕES DE CLIENTE
# Data + Tipo + Forma
# ==========================================================
tipos_sel_atual = st.session_state["filtro_tipo"]

if cliente_col:
    df_cliente = aplicar_filtros(
        df_base,
        inicio=inicio,
        fim=fim,
        tipos=tipos_sel_atual,
        formas=formas_sel_atual,
    )

    clientes_disponiveis = sorted(
        df_cliente[cliente_col].dropna().astype(str).unique().tolist()
    )

    st.session_state["filtro_cliente"] = limpar_selecao_invalida(
        st.session_state["filtro_cliente"],
        clientes_disponiveis,
    )

    st.sidebar.multiselect(
        "Cliente",
        options=clientes_disponiveis,
        key="filtro_cliente",
    )
else:
    clientes_disponiveis = []


# ==========================================================
# OPÇÕES DE FORMA
# Data + Tipo + Cliente
# ==========================================================
tipos_sel_atual = st.session_state["filtro_tipo"]
clientes_sel_atual = st.session_state["filtro_cliente"]

if forma_pagamento_col:
    df_forma = aplicar_filtros(
        df_base,
        inicio=inicio,
        fim=fim,
        tipos=tipos_sel_atual,
        clientes=clientes_sel_atual,
    )

    formas_disponiveis = sorted(
        df_forma[forma_pagamento_col].dropna().astype(str).unique().tolist()
    )

    st.session_state["filtro_forma"] = limpar_selecao_invalida(
        st.session_state["filtro_forma"],
        formas_disponiveis,
    )

    st.sidebar.multiselect(
        "Forma de pagamento",
        options=formas_disponiveis,
        key="filtro_forma",
    )
else:
    formas_disponiveis = []


# ==========================================================
# DataFrame final
# ==========================================================
work_df = aplicar_filtros(
    df_base,
    inicio=inicio,
    fim=fim,
    tipos=st.session_state["filtro_tipo"],
    clientes=st.session_state["filtro_cliente"],
    formas=st.session_state["filtro_forma"],
)

if work_df.empty:
    st.info("Nenhum registro encontrado com os filtros aplicados.")
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