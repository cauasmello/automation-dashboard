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

entrada_col = col_map.get("entrada")
saida_col = col_map.get("saída") or col_map.get("saida")
data_col = col_map.get("data")

if not entrada_col or not saida_col:
    st.info("Não encontrei colunas Entrada/Saída. Colunas disponíveis: " + ", ".join(df_raw.columns))
    st.stop()



st.subheader("Prévia (clique em uma linha)")
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

    # Mapeia também TipoDespesa e TipoProduto (se existirem no parquet)
    tipo_despesa_col = col_map.get("tipodespesa") or col_map.get("tipo despesa")
    tipo_produto_col = col_map.get("tipoproduto") or col_map.get("tipo produto")

    saida_txt = _escape_html(_val_or_blank(sel_row, saida_col))
    entrada_txt = _escape_html(_val_or_blank(sel_row, entrada_col))
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
    st.caption("Selecione uma linha acima para ver os detalhes em formato de carta.")


# Normaliza valores para numérico
work_df = df_raw.copy()
for c in [entrada_col, saida_col]:
    work_df[c] = (
        work_df[c]
        .astype(str)
        .str.replace(".", "", regex=False)
        .str.replace(",", ".", regex=False)
    )
    work_df[c] = pd.to_numeric(work_df[c], errors="coerce")

if data_col:
    work_df[data_col] = pd.to_datetime(work_df[data_col], errors="coerce")

