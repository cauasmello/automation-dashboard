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

tipo_col  = col_map.get("tipo")
valor_col = col_map.get("valor")
descricao_col  = col_map.get("descrição")
cliente_col = col_map.get("cliente")
forma_pagamento_col = col_map.get("forma de pagamento")
data_col  = col_map.get("data") or col_map.get("data/hora da exportação")

if not tipo_col or not valor_col:
    st.info("Não encontrei colunas Tipo/Valor. Colunas disponíveis: " + ", ".join(df_raw.columns))
    st.stop()

df = df_raw.copy()
df[valor_col] = pd.to_numeric(df[valor_col], errors="coerce")
df = df.dropna(subset=[valor_col])

# Se tiver Data, normaliza como date-only (mantém datetime64[ns])
if data_col:
    df[data_col] = pd.to_datetime(df[data_col], errors="coerce").dt.floor("D")

# Separa entradas e saídas
df_entrada = df[df[tipo_col].str.lower() == "entrada"]
df_saida   = df[df[tipo_col].str.lower() == "saída"]

total_entrada = df_entrada[valor_col].sum()
total_saida   = df_saida[valor_col].sum()



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

    tipo_txt = _escape_html(_val_or_blank(sel_row, tipo_col))
    valor_txt = _escape_html(_val_or_blank(sel_row, valor_col))
    descricao_txt = _escape_html(_val_or_blank(sel_row, descricao_col))
    cliente_txt = _escape_html(_val_or_blank(sel_row, cliente_col))
    forma_pagamento_txt = _escape_html(_val_or_blank(sel_row, forma_pagamento_col))
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
        + 'Tipo: ' + tipo_txt + '<br>'
        + 'Valor: ' + valor_txt + '<br>'
        + 'Descrição: ' + descricao_txt + '<br>'
        + 'Cliente: ' + cliente_txt + '<br>'
        + 'Forma de Pagamento: ' + forma_pagamento_txt + '<br>'
        + 'Data: ' + data_txt + '<br>'
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
work_df[valor_col] = (
    work_df[valor_col]
    .astype(str)
    .str.replace(".", "", regex=False)
    .str.replace(",", ".", regex=False)
)
work_df[valor_col] = pd.to_numeric(work_df[valor_col], errors="coerce")

if data_col:
    work_df[data_col] = pd.to_datetime(work_df[data_col], errors="coerce")


work_df[tipo_col] = work_df[tipo_col].astype(str).str.strip()

entrada_df = work_df[work_df[tipo_col].str.lower() == "entrada"]
saida_df = work_df[work_df[tipo_col].str.lower().isin(["saída", "saida"])]

total_entrada = entrada_df[valor_col].sum(skipna=True)
total_saida = saida_df[valor_col].sum(skipna=True)

