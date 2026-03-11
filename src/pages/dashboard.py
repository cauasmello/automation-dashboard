import pandas as pd
import streamlit as st

from components.filters import aplicar_filtros
from services.data_loader import load_events, format_brl


st.title("Dashboard Operacional")
st.caption("Visão operacional e consulta dos registros")

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
categoria_col = cols.get("categoria")
produto_col = cols.get("produto")

work_df = aplicar_filtros(
    df=df,
    data_col=data_col,
    tipo_col=tipo_col,
    cliente_col=cliente_col,
    forma_pagamento_col=forma_pagamento_col,
    categoria_col=categoria_col,
    produto_col=produto_col,
    state_prefix="dashboard",
)

if work_df.empty:
    st.info("Nenhum registro encontrado com os filtros aplicados.")
    st.stop()

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
        st.write(f"**Categoria:** {val_or_blank(row, categoria_col)}")
        st.write(f"**Produto:** {val_or_blank(row, produto_col)}")
    with d2:
        st.write(f"**Descrição:** {val_or_blank(row, descricao_col)}")
        st.write(f"**Forma de pagamento:** {val_or_blank(row, forma_pagamento_col)}")
        st.write(f"**Data:** {val_or_blank(row, data_col)}")
else:
    st.caption("Selecione uma linha para ver os detalhes.")