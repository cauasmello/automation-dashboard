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
# Carrega base e padroniza nomes
# ===================================================================
df_raw = pd.read_parquet(PARQUET_FILE)
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

# ===================================================================
# Normalizações de trabalho (ANTES de qualquer UI que dependa dos dados)
# ===================================================================
work_df = df_raw.copy()
# Valor numérico
work_df[valor_col] = (
    work_df[valor_col]
    .astype(str)
    .str.replace(".", "", regex=False)
    .str.replace(",", ".", regex=False)
)
work_df[valor_col] = pd.to_numeric(work_df[valor_col], errors="coerce")
work_df = work_df.dropna(subset=[valor_col])

# Data para datetime (mantendo NaT onde inválido)
if data_col:
    work_df[data_col] = work_df[data_col].astype(str).str.strip()
    work_df.loc[work_df[data_col].isin(["", "None", "nan", "NaT"]), data_col] = None
    work_df[data_col] = pd.to_datetime(work_df[data_col], errors="coerce")

# Tipo como string normalizada
work_df[tipo_col] = work_df[tipo_col].astype(str).str.strip()

# ===================================================================
# Filtros por coluna (múltipla escolha) — acima da tabela
# ===================================================================
st.subheader("Filtros por coluna")

# Não repetimos o filtro por data aqui (já existe o filtro de período)
exclude_cols = set([data_col]) if data_col else set()

PLACEHOLDER_NA = "(vazio)"  # como vamos exibir e filtrar valores vazios

def _chunks(lst, n):
    """Divide a lista em blocos de tamanho n (para layout responsivo)."""
    for i in range(0, len(lst), n):
        yield lst[i : i + n]

def _prepare_options(series: pd.Series):
    """Gera opções tipadas e amigáveis para o multiselect daquela coluna."""
    if pd.api.types.is_datetime64_any_dtype(series):
        # se quiser permitir filtro por 'data' aqui, troque exclude_cols acima
        opts = series.dt.date.astype("object")
    else:
        opts = series.astype("object")
    # substitui NaN/NaT/None por marcador
    opts = opts.where(~pd.isna(opts), other=PLACEHOLDER_NA)

    # únicos ordenados (limitamos a 2000 para não poluir a UI)
    uniques = pd.unique(opts)
    try:
        uniques = sorted(uniques, key=lambda x: (str(x).casefold()))
    except Exception:
        uniques = list(uniques)
    return [str(x) for x in uniques[:2000]]

col_selections = {}
cols_to_filter = [c for c in work_df.columns if c not in exclude_cols]

# Renderiza em linhas de 3 colunas (ajuste se preferir 2 ou 4)
for group in _chunks(cols_to_filter, 3):
    st_cols = st.columns(len(group))
    for c, container in zip(group, st_cols):
        with container:
            options = _prepare_options(work_df[c])
            # default vazio = não filtra; o usuário escolhe o que quer ver
            sel = st.multiselect(f"{c}", options=options, default=[])
            col_selections[c] = sel

# Aplica os filtros cumulativamente
for c, sel in col_selections.items():
    if not sel:
        continue
    ser = work_df[c]
    if pd.api.types.is_datetime64_any_dtype(ser):
        left = ser.dt.date.astype("object")
    else:
        left = ser.astype("object")
    left = left.where(~pd.isna(left), other=PLACEHOLDER_NA).astype(str)
    mask = left.isin(set(sel))
    work_df = work_df.loc[mask].copy()

st.caption(
    f"Filtros aplicados: {sum(1 for v in col_selections.values() if v)} coluna(s) · {len(work_df)} registros após filtros"
)

# ===================================================================
# Filtro de Período (ACIMA da tabela). BLOQUEIA seleção de único dia.
# Janela SEMIABERTA: [início, fim)
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

    default_start = max(data_min, data_max - dt.timedelta(days=7))
    default_end = data_max

    date_sel = st.date_input(
        "Intervalo de datas",
        value=(default_start, default_end),
        format="DD/MM/YYYY",
        help=(
            "Selecione data inicial e final (arrastando no calendário). "
            "O dashboard requer **duas datas diferentes** para formar um intervalo válido."
        ),
    )

    # >>> BLOQUEIO explícito de seleção inválida <<<
    if not isinstance(date_sel, tuple) or len(date_sel) != 2:
        st.warning("Selecione **um intervalo** com data inicial e final.")
        st.stop()

    start_date, end_date = date_sel
    if start_date == end_date:
        st.warning("Selecione **datas diferentes** para formar um intervalo válido.")
        st.stop()

    # Corrige inversão, se necessário
    if start_date > end_date:
        start_date, end_date = end_date, start_date
        st.warning("As datas foram invertidas para manter início <= fim.")

    # Limites em datetime (meia-noite) + semiaberto
    start_dt = dt.datetime.combine(start_date, dt.time.min)
    end_exclusive = dt.datetime.combine(end_date, dt.time.min) + dt.timedelta(days=1)

    mask = (work_df[data_col] >= start_dt) & (work_df[data_col] < end_exclusive)
    work_df = work_df.loc[mask].copy()
    st.caption(
        f"Período aplicado, Início: {start_date:%d/%m/%Y} - Fim: {end_date:%d/%m/%Y} · {len(work_df)} Registros"
    )

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
