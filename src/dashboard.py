import streamlit as st
import pandas as pd

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
# Inicialização de estado
# ==========================================================
if "filtro_tipos" not in st.session_state:
    st.session_state.filtro_tipos = []

if "filtro_clientes" not in st.session_state:
    st.session_state.filtro_clientes = []

if "filtro_formas" not in st.session_state:
    st.session_state.filtro_formas = []

# ==========================================================
# Função para aplicar filtros
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
        out = out[out[tipo_col].isin(tipos)].copy()

    if cliente_col and clientes:
        out = out[out[cliente_col].astype(str).isin(clientes)].copy()

    if forma_pagamento_col and formas:
        out = out[out[forma_pagamento_col].astype(str).isin(formas)].copy()

    return out

# ==========================================================
# Filtro de período
# ==========================================================
st.sidebar.header("Filtros")

df_base = df_raw.copy()

if data_col and df_base[data_col].notna().any():
    data_min = df_base[data_col].dropna().min().date()
    data_max = df_base[data_col].dropna().max().date()

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
else:
    inicio = None
    fim = None

# ==========================================================
# Opções dinâmicas dos filtros
# Cada filtro é calculado considerando os outros já selecionados
# ==========================================================

# valores atuais salvos
tipos_sel = st.session_state.filtro_tipos
clientes_sel = st.session_state.filtro_clientes
formas_sel = st.session_state.filtro_formas

# ---- opções de tipo ----
df_tipo_opcoes = aplicar_filtros(
    df_base,
    inicio=inicio,
    fim=fim,
    clientes=clientes_sel,
    formas=formas_sel,
)
tipos_disponiveis = sorted(
    df_tipo_opcoes[tipo_col].dropna().astype(str).unique().tolist()
)

# limpa seleções inválidas
tipos_sel = [x for x in tipos_sel if x in tipos_disponiveis]
st.session_state.filtro_tipos = tipos_sel

novos_tipos = st.sidebar.multiselect(
    "Tipo",
    options=tipos_disponiveis,
    default=tipos_sel,
    key="multiselect_tipo",
)

# ---- opções de cliente ----
if cliente_col:
    df_cliente_opcoes = aplicar_filtros(
        df_base,
        inicio=inicio,
        fim=fim,
        tipos=novos_tipos,
        formas=formas_sel,
    )
    clientes_disponiveis = sorted(
        df_cliente_opcoes[cliente_col].dropna().astype(str).unique().tolist()
    )

    clientes_sel = [x for x in clientes_sel if x in clientes_disponiveis]
    st.session_state.filtro_clientes = clientes_sel

    novos_clientes = st.sidebar.multiselect(
        "Cliente",
        options=clientes_disponiveis,
        default=clientes_sel,
        key="multiselect_cliente",
    )
else:
    novos_clientes = []

# ---- opções de forma de pagamento ----
if forma_pagamento_col:
    df_forma_opcoes = aplicar_filtros(
        df_base,
        inicio=inicio,
        fim=fim,
        tipos=novos_tipos,
        clientes=novos_clientes,
    )
    formas_disponiveis = sorted(
        df_forma_opcoes[forma_pagamento_col].dropna().astype(str).unique().tolist()
    )

    formas_sel = [x for x in formas_sel if x in formas_disponiveis]
    st.session_state.filtro_formas = formas_sel

    novas_formas = st.sidebar.multiselect(
        "Forma de pagamento",
        options=formas_disponiveis,
        default=formas_sel,
        key="multiselect_forma",
    )
else:
    novas_formas = []

# atualiza estado final
st.session_state.filtro_tipos = novos_tipos
st.session_state.filtro_clientes = novos_clientes
st.session_state.filtro_formas = novas_formas

# ==========================================================
# Dataframe final filtrado
# ==========================================================
work_df = aplicar_filtros(
    df_base,
    inicio=inicio,
    fim=fim,
    tipos=novos_tipos,
    clientes=novos_clientes,
    formas=novas_formas,
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