import pandas as pd
import streamlit as st
import plotly.graph_objects as go

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

if not data_col:
    st.warning("A base não possui coluna de data.")
    st.stop()

df = df.dropna(subset=[data_col, valor_col]).copy()    

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
# Gráfico: "Evolução de Entradas e Saídas"
# ==========================================================
st.subheader("Evolução de Entradas e Saídas")

granularidade_evolucao = st.radio(
    "Exibir por:",
    options=["Semana", "Mês", "Trimestre", "Ano"],
    horizontal=True,
    key="radio_evolucao_entradas_saidas",
)

# Padroniza tipo
df[tipo_col] = df[tipo_col].astype(str).str.strip().str.lower()

# Cria coluna de agrupamento conforme granularidade
if granularidade_evolucao == "Semana":
    # início da semana
    df["periodo"] = df[data_col].dt.to_period("W").apply(lambda r: r.start_time)
    titulo_x = "Semana"

elif granularidade_evolucao == "Mês":
    df["periodo"] = df[data_col].dt.to_period("M").dt.to_timestamp()
    titulo_x = "Mês"

elif granularidade_evolucao == "Trimestre":
    df["periodo"] = df[data_col].dt.to_period("Q").dt.to_timestamp()
    titulo_x = "Trimestre"

else:  # Ano
    df["periodo"] = df[data_col].dt.to_period("Y").dt.to_timestamp()
    titulo_x = "Ano"

# Separa entradas e saídas
df_entrada = df[df[tipo_col] == "entrada"].copy()
df_saida = df[df[tipo_col].isin(["saída", "saida"])].copy()

entrada_agg = (
    df_entrada.groupby("periodo", as_index=False)[valor_col]
    .sum()
    .rename(columns={valor_col: "entrada"})
)

saida_agg = (
    df_saida.groupby("periodo", as_index=False)[valor_col]
    .sum()
    .rename(columns={valor_col: "saida"})
)

# Junta tudo em uma base única
grafico_df = pd.merge(
    entrada_agg,
    saida_agg,
    on="periodo",
    how="outer",
).fillna(0)

grafico_df = grafico_df.sort_values("periodo").reset_index(drop=True)

if grafico_df.empty:
    st.info("Não há dados para o período selecionado.")
    st.stop()

# Rótulo mais amigável para eixo X
if granularidade_evolucao == "Semana":
    grafico_df["label"] = grafico_df["periodo"].dt.strftime("%d/%m/%Y")

elif granularidade_evolucao == "Mês":
    grafico_df["label"] = grafico_df["periodo"].dt.strftime("%m/%Y")

elif granularidade_evolucao == "Trimestre":
    grafico_df["label"] = (
        "T"
        + grafico_df["periodo"].dt.quarter.astype(str)
        + "/"
        + grafico_df["periodo"].dt.year.astype(str)
    )

else:
    grafico_df["label"] = grafico_df["periodo"].dt.strftime("%Y")

# Gráfico estilo Power BI
fig = go.Figure()

fig.add_trace(
    go.Scatter(
        x=grafico_df["label"],
        y=grafico_df["entrada"],
        mode="lines+markers",
        name="Entrada",
        line=dict(color="green", width=3),
        marker=dict(size=7),
        hovertemplate="<b>Entrada</b><br>Período: %{x}<br>Valor: R$ %{y:,.2f}<extra></extra>",
    )
)

fig.add_trace(
    go.Scatter(
        x=grafico_df["label"],
        y=grafico_df["saida"],
        mode="lines+markers",
        name="Saída",
        line=dict(color="red", width=3),
        marker=dict(size=7),
        hovertemplate="<b>Saída</b><br>Período: %{x}<br>Valor: R$ %{y:,.2f}<extra></extra>",
    )
)

fig.update_layout(
    title="Evolução de Entradas e Saídas",
    xaxis_title=titulo_x,
    yaxis_title="Valor",
    hovermode="x unified",
    legend_title="Tipo",
    template="plotly_white",
    height=500,
    margin=dict(l=20, r=20, t=60, b=20),
)

fig.update_yaxes(tickprefix="R$ ")

st.plotly_chart(fig, use_container_width=True)

# Opcional: tabela de apoio abaixo
with st.expander("Ver dados do gráfico"):
    tabela = grafico_df[["label", "entrada", "saida"]].copy()
    tabela.columns = ["Período", "Entrada", "Saída"]
    st.dataframe(tabela, use_container_width=True, hide_index=True)

# ==========================================================
# Gráfico: "Evolução do Percentual de Lucro"
# ==========================================================

if df.empty:
    st.info("Não há dados suficientes para gerar o gráfico.")
    st.stop()

df[tipo_col] = df[tipo_col].astype(str).str.strip().str.lower()

st.subheader("Percentual de Lucro")

granularidade_lucro = st.radio(
    "Exibir por:",
    options=["Semana", "Mês", "Trimestre", "Ano"],
    horizontal=True,
    key="radio_percentual_lucro",
)

# ==========================================================
# Define período
# ==========================================================
if granularidade_lucro == "Semana":
    df["periodo"] = df[data_col].dt.to_period("W").apply(lambda r: r.start_time)
    titulo_x = "Semana"

elif granularidade_lucro == "Mês":
    df["periodo"] = df[data_col].dt.to_period("M").dt.to_timestamp()
    titulo_x = "Mês"

elif granularidade_lucro == "Trimestre":
    df["periodo"] = df[data_col].dt.to_period("Q").dt.to_timestamp()
    titulo_x = "Trimestre"

else:
    df["periodo"] = df[data_col].dt.to_period("Y").dt.to_timestamp()
    titulo_x = "Ano"

# ==========================================================
# Agrega entradas e saídas por período
# ==========================================================
df_entrada = df[df[tipo_col] == "entrada"].copy()
df_saida = df[df[tipo_col].isin(["saída", "saida"])].copy()

entrada_agg = (
    df_entrada.groupby("periodo", as_index=False)[valor_col]
    .sum()
    .rename(columns={valor_col: "entrada"})
)

saida_agg = (
    df_saida.groupby("periodo", as_index=False)[valor_col]
    .sum()
    .rename(columns={valor_col: "saida"})
)

base = pd.merge(entrada_agg, saida_agg, on="periodo", how="outer").fillna(0)

base["lucro"] = base["entrada"] - base["saida"]

# Evita divisão por zero
base["perc_lucro"] = base.apply(
    lambda row: ((row["lucro"] / row["entrada"]) * 100) if row["entrada"] != 0 else 0,
    axis=1,
)

base = base.sort_values("periodo").reset_index(drop=True)

if base.empty:
    st.info("Não há dados para gerar o gráfico.")
    st.stop()

# ==========================================================
# Label do eixo X
# ==========================================================
if granularidade_lucro == "Semana":
    base["label"] = base["periodo"].dt.strftime("%d/%m/%Y")

elif granularidade_lucro == "Mês":
    base["label"] = base["periodo"].dt.strftime("%m/%Y")

elif granularidade_lucro == "Trimestre":
    base["label"] = (
        "T"
        + base["periodo"].dt.quarter.astype(str)
        + "/"
        + base["periodo"].dt.year.astype(str)
    )

else:
    base["label"] = base["periodo"].dt.strftime("%Y")

# ==========================================================
# Cor da barra
# ==========================================================
base["cor"] = base["perc_lucro"].apply(lambda x: "green" if x >= 0 else "red")

# ==========================================================
# Gráfico
# ==========================================================
fig = go.Figure()

fig.add_trace(
    go.Bar(
        x=base["label"],
        y=base["perc_lucro"],
        marker_color=base["cor"],
        text=base["perc_lucro"].round(1).astype(str) + "%",
        textposition="outside",
        hovertemplate=(
            "<b>Período:</b> %{x}<br>"
            "<b>% Lucro:</b> %{y:.2f}%<br>"
            "<extra></extra>"
        ),
        name="% Lucro",
    )
)

fig.update_layout(
    title="Percentual de Lucro por Período",
    xaxis_title=titulo_x,
    yaxis_title="% Lucro",
    template="plotly_white",
    height=550,
    margin=dict(l=20, r=20, t=60, b=20),
    showlegend=False,
)

fig.update_yaxes(
    ticksuffix="%",
    zeroline=True,
    zerolinewidth=2,
    zerolinecolor="gray",
)

st.plotly_chart(fig, use_container_width=True)

with st.expander("Ver dados do gráfico"):
    tabela = base[["label", "entrada", "saida", "lucro", "perc_lucro"]].copy()
    tabela.columns = ["Período", "Entrada", "Saída", "Lucro", "% Lucro"]
    st.dataframe(tabela, use_container_width=True, hide_index=True)