from pathlib import Path
import pandas as pd
import streamlit as st
import datetime as dt


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

# ===================================================================
# Carrega e prepara base
# ===================================================================
df_raw = pd.read_parquet(PARQUET_FILE)
# Tenta padronizar nomes (tolerante a ordem/acentos)
col_map = {c.lower().strip(): c for c in df_raw.columns}

tipo_col  = col_map.get("tipo")
valor_col = col_map.get("valor")
descricao_col  = col_map.get("descrição")
cliente_col = col_map.get("cliente")
forma_pagamento_col = col_map.get("forma de pagamento")
data_col  = col_map.get("data")

if not tipo_col or not valor_col:
    st.info("Não encontrei colunas Tipo/Valor. Colunas disponíveis: " + ", ".join(df_raw.columns))
    st.stop()

# Copiamos e limpamos valores numéricos
work_df = df_raw.copy()
work_df[valor_col] = (
    work_df[valor_col]
    .astype(str)
    .str.replace(".", "", regex=False)
    .str.replace(",", ".", regex=False)
)
work_df[valor_col] = pd.to_numeric(work_df[valor_col], errors="coerce")
work_df = work_df.dropna(subset=[valor_col])

# Limpa/normaliza a coluna de data
if data_col:
    # Remove strings vazias e converte para datetime (mantém NaT se inválido)
    work_df[data_col] = work_df[data_col].astype(str).str.strip()
    work_df.loc[work_df[data_col].isin(["", "None", "nan", "NaT"]), data_col] = None
    work_df[data_col] = pd.to_datetime(work_df[data_col], errors="coerce")

# Normaliza tipo
work_df[tipo_col] = work_df[tipo_col].astype(str).str.strip()

# ===================================================================
# Filtro de Período (ACIMA da tabela) – aceita um único dia e usa [início, fim)
# ===================================================================
if data_col:
    st.subheader("Período")

    _valid_dates = work_df[data_col].dropna()
    if not _valid_dates.empty:
        data_min = _valid_dates.min().date()
        data_max = _valid_dates.max().date()
    else:
        today = dt.date.today()
        data_min = today - dt.timedelta(days=7)
        data_max = today

    # Default: últimos 7 dias até o máximo
    default_start = max(data_min, data_max - dt.timedelta(days=7))
    default_end = data_max

    date_sel = st.date_input(
        "Intervalo de datas",
        value=(default_start, default_end),
        format="DD/MM/YYYY",
        help=(
            "Selecione data inicial e final. Se escolher apenas um dia, vamos considerar somente aquele dia "
            "(intervalo semiaberto [início, fim))."
        ),
    )

    # Autocorreção: único dia vira [dia, dia]
    if isinstance(date_sel, tuple) and len(date_sel) == 2:
        start_date, end_date = date_sel
    else:
        start_date = end_date = date_sel
        st.info("Considerando somente o dia selecionado.")

    # Sanidade: garante ordem
    if start_date > end_date:
        start_date, end_date = end_date, start_date
        st.warning("As datas foram invertidas para manter início <= fim.")

    # Constrói limites em datetime (00:00) e semiaberto
    start_dt = pd.Timestamp(start_date)
    end_exclusive = pd.Timestamp(end_date) + pd.offsets.Day(1)

    # Importante: compara diretamente datetime64[ns] com Timestamp
    mask = (work_df[data_col] >= start_dt) & (work_df[data_col] < end_exclusive)
    work_df = work_df.loc[mask].copy()
    st.caption(f"Período aplicado (intervalo semiaberto [início, fim)): {start_date:%d/%m/%Y} a {end_date:%d/%m/%Y} · {len(work_df)} registros")

# ===================================================================
# Métricas após o filtro
# ===================================================================
entrada_df = work_df[work_df[tipo_col].str.lower() == "entrada"]
saida_df   = work_df[work_df[tipo_col].str.lower().isin(["saída", "saida"])]

total_entrada = entrada_df[valor_col].sum(skipna=True)
total_saida   = saida_df[valor_col].sum(skipna=True)

# ===================================================================
# Tabela filtrada + card de detalhes
# ===================================================================
st.subheader("Selecione uma linha")
preview_df = work_df.head(200).copy()
preview_event = st.dataframe(
    preview_df,
    width='stretch',
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
