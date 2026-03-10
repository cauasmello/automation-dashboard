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

tipo_col = cols["tipo"]
valor_col = cols["valor"]
descricao_col = cols["descricao"]
cliente_col = cols["cliente"]
forma_pagamento_col = cols["forma_pagamento"]
data_col = cols["data"]

st.caption("Página principal: visão operacional e consulta dos registros")


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

df_base = df_raw.copy()
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