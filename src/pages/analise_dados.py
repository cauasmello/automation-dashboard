import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from components.filters import aplicar_filtros
from services.data_loader import load_events, format_brl


st.title("Análise de Dados")
st.caption("Visão analítica dos dados financeiros")

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
cliente_col = cols["cliente"]
forma_pagamento_col = cols["forma_pagamento"]
data_col = cols["data"]
categoria_col = cols.get("categoria")
produto_col = cols.get("produto")

if not data_col:
    st.warning("A base não possui coluna de data.")
    st.stop()

df = df.dropna(subset=[data_col, valor_col]).copy()

work_df = aplicar_filtros(
    df=df,
    data_col=data_col,
    tipo_col=tipo_col,
    cliente_col=cliente_col,
    forma_pagamento_col=forma_pagamento_col,
    categoria_col=categoria_col,
    produto_col=produto_col,
    state_prefix="analise",
)

if work_df.empty:
    st.info("Nenhum registro encontrado com os filtros aplicados.")
    st.stop()


def preparar_periodo(base_df: pd.DataFrame, granularidade: str) -> tuple[pd.DataFrame, str]:
    out = base_df.copy()

    if granularidade == "Semana":
        out["periodo"] = out[data_col].dt.to_period("W").apply(lambda r: r.start_time)
        titulo_x = "Semana"
    elif granularidade == "Mês":
        out["periodo"] = out[data_col].dt.to_period("M").dt.to_timestamp()
        titulo_x = "Mês"
    elif granularidade == "Trimestre":
        out["periodo"] = out[data_col].dt.to_period("Q").dt.to_timestamp()
        titulo_x = "Trimestre"
    else:
        out["periodo"] = out[data_col].dt.to_period("Y").dt.to_timestamp()
        titulo_x = "Ano"

    return out, titulo_x


def criar_labels(base_df: pd.DataFrame, granularidade: str) -> pd.DataFrame:
    out = base_df.copy()

    if granularidade == "Semana":
        out["label"] = out["periodo"].dt.strftime("%d/%m/%Y")
    elif granularidade == "Mês":
        out["label"] = out["periodo"].dt.strftime("%m/%Y")
    elif granularidade == "Trimestre":
        out["label"] = (
            "T"
            + out["periodo"].dt.quarter.astype(str)
            + "/"
            + out["periodo"].dt.year.astype(str)
        )
    else:
        out["label"] = out["periodo"].dt.strftime("%Y")

    return out


# KPI
entradas = work_df.loc[work_df[tipo_col] == "entrada", valor_col].sum()
saidas = work_df.loc[work_df[tipo_col].isin(["saída", "saida"]), valor_col].sum()
saldo = entradas - saidas

k1, k2, k3, k4 = st.columns(4)
k1.metric("Entradas", format_brl(entradas))
k2.metric("Saídas", format_brl(saidas))
k3.metric("Saldo", format_brl(saldo))
k4.metric("Registros", f"{len(work_df)}")

st.divider()

# Gráfico 1
st.subheader("Evolução de Entradas e Saídas")

granularidade_evolucao = st.radio(
    "Exibir por:",
    options=["Semana", "Mês", "Trimestre", "Ano"],
    horizontal=True,
    key="radio_evolucao",
)

grafico_df_base, titulo_x = preparar_periodo(work_df, granularidade_evolucao)

df_entrada = grafico_df_base[grafico_df_base[tipo_col] == "entrada"].copy()
df_saida = grafico_df_base[grafico_df_base[tipo_col].isin(["saída", "saida"])].copy()

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

grafico_df = pd.merge(
    entrada_agg,
    saida_agg,
    on="periodo",
    how="outer",
).fillna(0)

grafico_df = grafico_df.sort_values("periodo").reset_index(drop=True)
grafico_df = criar_labels(grafico_df, granularidade_evolucao)

fig1 = go.Figure()

fig1.add_trace(
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

fig1.add_trace(
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

fig1.update_layout(
    title="Evolução de Entradas e Saídas",
    xaxis_title=titulo_x,
    yaxis_title="Valor",
    hovermode="x unified",
    legend_title="Tipo",
    template="plotly_white",
    height=500,
    margin=dict(l=20, r=20, t=60, b=20),
)

fig1.update_yaxes(tickprefix="R$ ")
st.plotly_chart(fig1, use_container_width=True)

with st.expander("Ver dados do gráfico de evolução"):
    tabela1 = grafico_df[["label", "entrada", "saida"]].copy()
    tabela1.columns = ["Período", "Entrada", "Saída"]

    st.dataframe(
        tabela1,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Entrada": st.column_config.NumberColumn("Entrada", format="R$ %.2f"),
            "Saída": st.column_config.NumberColumn("Saída", format="R$ %.2f"),
        },
    )

st.divider()

# Gráfico 2
st.subheader("Percentual de Lucro")

granularidade_lucro = st.radio(
    "Exibir por:",
    options=["Semana", "Mês", "Trimestre", "Ano"],
    horizontal=True,
    key="radio_lucro",
)

base_lucro_df, titulo_x_lucro = preparar_periodo(work_df, granularidade_lucro)

df_entrada_lucro = base_lucro_df[base_lucro_df[tipo_col] == "entrada"].copy()
df_saida_lucro = base_lucro_df[base_lucro_df[tipo_col].isin(["saída", "saida"])].copy()

entrada_agg_lucro = (
    df_entrada_lucro.groupby("periodo", as_index=False)[valor_col]
    .sum()
    .rename(columns={valor_col: "entrada"})
)

saida_agg_lucro = (
    df_saida_lucro.groupby("periodo", as_index=False)[valor_col]
    .sum()
    .rename(columns={valor_col: "saida"})
)

base = pd.merge(entrada_agg_lucro, saida_agg_lucro, on="periodo", how="outer").fillna(0)
base["lucro"] = base["entrada"] - base["saida"]
base["perc_lucro"] = base.apply(
    lambda row: ((row["lucro"] / row["entrada"]) * 100) if row["entrada"] != 0 else 0,
    axis=1,
)

base = base.sort_values("periodo").reset_index(drop=True)
base = criar_labels(base, granularidade_lucro)
base["cor"] = base["perc_lucro"].apply(lambda x: "green" if x >= 0 else "red")

fig2 = go.Figure()

fig2.add_trace(
    go.Bar(
        x=base["label"],
        y=base["perc_lucro"],
        marker_color=base["cor"],
        text=base["perc_lucro"].round(1).astype(str) + "%",
        textposition="outside",
        hovertemplate=(
            "<b>Período:</b> %{x}<br>"
            "<b>% Lucro:</b> %{y:.1f}%<br>"
            "<extra></extra>"
        ),
        name="% Lucro",
    )
)

fig2.update_layout(
    title="Percentual de Lucro por Período",
    xaxis_title=titulo_x_lucro,
    yaxis_title="% Lucro",
    template="plotly_white",
    height=550,
    margin=dict(l=20, r=20, t=60, b=20),
    showlegend=False,
)

fig2.update_yaxes(
    ticksuffix="%",
    zeroline=True,
    zerolinewidth=2,
    zerolinecolor="gray",
)

st.plotly_chart(fig2, use_container_width=True)

with st.expander("Ver dados do gráfico de % lucro"):
    tabela2 = base[["label", "entrada", "saida", "lucro", "perc_lucro"]].copy()
    tabela2.columns = ["Período", "Entrada", "Saída", "Lucro", "% Lucro"]

    st.dataframe(
        tabela2,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Entrada": st.column_config.NumberColumn("Entrada", format="R$ %.2f"),
            "Saída": st.column_config.NumberColumn("Saída", format="R$ %.2f"),
            "Lucro": st.column_config.NumberColumn("Lucro", format="R$ %.2f"),
            "% Lucro": st.column_config.NumberColumn("% Lucro", format="%.1f%%"),
        },
    )