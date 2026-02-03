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
# Tenta padronizar nomes (tolerante a ordem/acentos)
col_map = {c.lower().strip(): c for c in df_raw.columns}

tipo_col = col_map.get("tipo")
valor_col = col_map.get("valor")
data_col = col_map.get("data") or col_map.get("data/hora") or col_map.get("data hora")
descricao_col = col_map.get("descrição") or col_map.get("descricao")
cliente_col = col_map.get("cliente")
forma_col = col_map.get("forma de pagamento") or col_map.get("forma pagamento")

missing = []
if not tipo_col:
    missing.append("Tipo")
if not valor_col:
    missing.append("Valor")
if not data_col:
    missing.append("Data")
if missing:
    st.info("Não encontrei colunas obrigatórias: " + ", ".join(missing) + ". Colunas disponíveis: " + ", ".join(df_raw.columns))
    st.stop()


# --- Julius: new model (Tipo has values Entrada/Saída) ---
df = df_raw.copy()
df[valor_col] = pd.to_numeric(df[valor_col], errors="coerce")
if data_col:
    df[data_col] = pd.to_datetime(df[data_col], errors="coerce").dt.date
df[tipo_col] = df[tipo_col].astype(str).str.strip()

df_entrada = df[df[tipo_col].str.lower() == "entrada"]
df_saida = df[df[tipo_col].str.lower().isin(["saída", "saida"]) ]

st.subheader("Resumo")
c1, c2, c3 = st.columns(3)
c1.metric("Registros", int(df.shape[0]))
c2.metric("Total Entrada", float(df_entrada[valor_col].sum(skipna=True)))
c3.metric("Total Saída", float(df_saida[valor_col].sum(skipna=True)))

st.subheader("Total por Tipo")
totais = df.groupby(tipo_col, dropna=False)[valor_col].sum().sort_values(ascending=False)
st.bar_chart(totais)

if data_col:
    st.subheader("Evolução (dia)")
    by_day = df.dropna(subset=[data_col]).groupby(data_col)[valor_col].sum()
    st.line_chart(by_day)


# Normaliza tipos
_df = df_raw.copy()
_df[valor_col] = pd.to_numeric(_df[valor_col], errors="coerce")
_df[data_col] = pd.to_datetime(_df[data_col], errors="coerce")

# Sidebar filters
st.sidebar.header("Filtros")
min_date = _df[data_col].min()
max_date = _df[data_col].max()
date_range = st.sidebar.date_input("Período", value=(min_date.date() if pd.notna(min_date) else None, max_date.date() if pd.notna(max_date) else None))
sel_tipos = st.sidebar.multiselect("Tipo", sorted([x for x in _df[tipo_col].dropna().unique().tolist()]))
sel_clientes = st.sidebar.multiselect("Cliente", sorted([x for x in _df[cliente_col].dropna().unique().tolist()]) if cliente_col else [])

_df2 = _df.copy()
if isinstance(date_range, tuple) and len(date_range) == 2 and date_range[0] is not None and date_range[1] is not None:
    _df2 = _df2[_df2[data_col].dt.date.between(date_range[0], date_range[1])]
if sel_tipos:
    _df2 = _df2[_df2[tipo_col].isin(sel_tipos)]
if cliente_col and sel_clientes:
    _df2 = _df2[_df2[cliente_col].isin(sel_clientes)]

st.subheader("Resumo")
col1, col2, col3 = st.columns(3)
col1.metric("Registros", int(_df2.shape[0]))
col2.metric("Total Valor", float(_df2[valor_col].sum(skipna=True)))
col3.metric("Média Valor", float(_df2[valor_col].mean(skipna=True)) if _df2.shape[0] else 0.0)

st.subheader("Total por Tipo")
by_tipo = (_df2.groupby(tipo_col, dropna=False)[valor_col].sum().sort_values(ascending=False))
st.bar_chart(by_tipo)

st.subheader("Evolução no tempo")
_df2_time = _df2.dropna(subset=[data_col]).sort_values(data_col)
_df2_time["data_dia"] = _df2_time[data_col].dt.date
by_day = _df2_time.groupby("data_dia")[valor_col].sum()
st.line_chart(by_day)

st.subheader("Tabela")
show_cols = [c for c in [data_col, tipo_col, valor_col, descricao_col, cliente_col, forma_col] if c]
st.dataframe(_df2[show_cols].sort_values(data_col, ascending=False), use_container_width=True)
st.stop()

st.subheader("Selecione uma linha")
preview_df = df_raw.head(200).copy()
preview_event = st.dataframe(
    preview_df,
    use_container_width=True,
    hide_index=True,
    selection_mode="single-row",
    on_select="rerun",
)

# Quando o usuário seleciona uma linha, mostramos um card estilo 'carta' (mock)
selected_rows = []
try:
    selected_rows = preview_event.selection.get("rows", [])
except Exception:
    selected_rows = []

def _val_or_blank(row_obj, col_name):
    if col_name is None:
        return ""
    if col_name not in row_obj.index:
        return ""
    vv = row_obj[col_name]
    if pd.isna(vv):
        return ""
    return str(vv)

def _escape_html(txt_val):
    if txt_val is None:
        return ""
    return str(txt_val).replace('&','&amp;').replace('<','&lt;').replace('>','&gt;')

if len(selected_rows) == 1:
    sel_row = preview_df.iloc[int(selected_rows[0])]

# --- Detalhes da linha selecionada (novo modelo) ---
try:
    tipo_txt = _escape_html(_val_or_blank(sel_row, tipo_col)) if "tipo_col" in globals() and tipo_col else ""
    valor_txt = _escape_html(_val_or_blank(sel_row, valor_col)) if "valor_col" in globals() and valor_col else ""
    data_txt = ""
    if "data_col" in globals() and data_col:
        data_txt = _escape_html(_val_or_blank(sel_row, data_col))
    desc_txt = _escape_html(_val_or_blank(sel_row, col_map.get("descrição"))) if col_map.get("descrição") else ""
    cli_txt = _escape_html(_val_or_blank(sel_row, col_map.get("cliente"))) if col_map.get("cliente") else ""
    forma_txt = _escape_html(_val_or_blank(sel_row, col_map.get("forma de pagamento"))) if col_map.get("forma de pagamento") else ""

    st.markdown("""
    <div style="padding:12px;border:1px solid #E5E7EB;border-radius:10px;background:#FFFFFF">
      <div style="font-size:16px;font-weight:600;color:#171717;margin-bottom:8px">Detalhes</div>
      <div style="color:#171717"><b>Data</b> {data_txt}</div>
      <div style="color:#171717"><b>Tipo</b> {tipo_txt}</div>
      <div style="color:#171717"><b>Valor</b> {valor_txt}</div>
      <div style="color:#171717"><b>Cliente</b> {cli_txt}</div>
      <div style="color:#171717"><b>Forma</b> {forma_txt}</div>
      <div style="color:#171717"><b>Descrição</b> {desc_txt}</div>
    </div>
    """.format(data_txt=data_txt, tipo_txt=tipo_txt, valor_txt=valor_txt, cli_txt=cli_txt, forma_txt=forma_txt, desc_txt=desc_txt), unsafe_allow_html=True)
except Exception:
    pass

    # Mapeia também TipoDespesa e TipoProduto (se existirem no parquet)
    tipo_despesa_col = col_map.get("tipodespesa") or col_map.get("tipo despesa")
    tipo_produto_col = col_map.get("tipoproduto") or col_map.get("tipo produto")

    saida_txt = _escape_html(_val_or_blank(sel_row, tipo_col))
    entrada_txt = _escape_html(_val_or_blank(sel_row, tipo_col))
    tipo_despesa_txt = _escape_html(_val_or_blank(sel_row, tipo_despesa_col))
    tipo_produto_txt = _escape_html(_val_or_blank(sel_row, tipo_produto_col))
    data_txt = _escape_html(_val_or_blank(sel_row, data_col))

    card_html = (
        '<div style="display:flex; justify-content:center; margin-top: 18px;">'
        '<div style="position:relative; width: 360px; height: 520px; border: 6px solid #111827; border-radius: 18px; background: #ffffff;">'
        '<div style="position:absolute; top: 18px; left: 18px; text-align:left; line-height: 1;">'
        '<div style="font-size: 44px; color:#111827; font-weight:700;">♠</div>'
        '<div style="font-size: 26px; color:#111827; margin-top:-8px;">♠</div>'
        '</div>'
        '<div style="position:absolute; bottom: 18px; right: 18px; text-align:right; line-height: 1; transform: rotate(180deg);">'
        '<div style="font-size: 44px; color:#111827; font-weight:700;">♠</div>'
        '<div style="font-size: 26px; color:#111827; margin-top:-8px;">♠</div>'
        '</div>'
        '<div style="position:absolute; inset: 0; display:flex; align-items:center; justify-content:center;">'
        '<div style="text-align:center; font-size: 20px; color:#111827; font-weight:600; line-height: 1.9; padding: 0 26px;">'
        + 'Saída:&quot;' + saida_txt + '&quot;<br>'
        + 'Entrada:&quot;' + entrada_txt + '&quot;<br>'
        + 'TipoDespesa:&quot;' + tipo_despesa_txt + '&quot;<br>'
        + 'TipoProduto:&quot;' + tipo_produto_txt + '&quot;<br>'
        + 'Data:&quot;' + data_txt + '&quot;'
        + '</div>'
        '</div>'
        '</div>'
        '</div>'
    )
    st.markdown(card_html, unsafe_allow_html=True)
else:
    st.caption("Selecione uma linha acima para ver os detalhes.")


# Normaliza valores para numérico
work_df = df_raw.copy()
for c in [tipo_col, tipo_col]:
    work_df[c] = (
        work_df[c]
        .astype(str)
        .str.replace(".", "", regex=False)
        .str.replace(",", ".", regex=False)
    )
    work_df[c] = pd.to_numeric(work_df[c], errors="coerce")

if data_col:
    work_df[data_col] = pd.to_datetime(work_df[data_col], errors="coerce")