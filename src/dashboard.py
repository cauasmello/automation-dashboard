from pathlib import Path
import pandas as pd
import streamlit as st
from datetime import date

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
descricao_col = col_map.get("descrição")
cliente_col = col_map.get("cliente")
forma_pagamento_col = col_map.get("forma de pagamento")
data_col = col_map.get("data")

if not tipo_col or not valor_col:
    st.info("Não encontrei colunas Tipo/Valor. Colunas disponíveis: " + ", ".join(df_raw.columns))
    st.stop()

# ==========================================
# Preparação dos dados (mantendo 'Data' como date)
# ==========================================
df = df_raw.copy()

# Remove colunas de exportação (se existirem) para não poluir a tabela
_drop_export_cols = [c for c in df.columns if c.lower().strip() in [
    "data/hora da exportação", "data/hora da exportacao",
    "data/hora exportação", "data/hora exportacao",
]]
if _drop_export_cols:
    df = df.drop(columns=_drop_export_cols)

# Normaliza Valor como numérico
df[valor_col] = pd.to_numeric(df[valor_col], errors="coerce")
df = df.dropna(subset=[valor_col])

# -------------------------
# Filtro por intervalo de data (usando somente 'date') + Data (BR)
# -------------------------
if data_col:
    # Converte qualquer representação para 'date' (descarta datetime)
    tmp = pd.to_datetime(df[data_col].astype(str).str.strip(), errors="coerce")
    df[data_col] = tmp.dt.date  # <- tipo 'date'

    valid_dates = df[data_col].dropna()
    if not valid_dates.empty:
        min_date = valid_dates.min()
        max_date = valid_dates.max()

        st.subheader("Período")

        # --- CSS para reduzir a largura do DateInput (sem mudar o alinhamento) ---
        st.markdown(
            """
            <style>
            /* Limita a largura do componente de intervalo de data */
            div[data-testid="stDateInput"] {
                max-width: 260px;   /* ajuste: 200px, 220px, 280px... */
                width: 100%;
            }
            /* Garante que o input interno não estique */
            div[data-baseweb="input"] {
                max-width: 260px;
            }
            </style>
            """,
            unsafe_allow_html=True
        )

        # --- Seletor de intervalo de datas logo abaixo do título ---
        start_date, end_date = st.date_input(
            "Intervalo de datas (coluna 'Data')",
            value=(min_date, max_date),
            min_value=min_date,
            max_value=max_date,
            format="DD/MM/YYYY",   # PT-BR no seletor
        )

        if end_date < start_date:
            st.warning("A data final é menor que a data inicial. Ajuste o intervalo.")
            st.stop()

        # Aplica filtro (somente 'date')
        df = df[(df[data_col] >= start_date) & (df[data_col] <= end_date)]

        # Coluna de exibição em PT-BR para a tabela/cartão
        df["Data (BR)"] = df[data_col].apply(
            lambda d: d.strftime("%d/%m/%Y") if pd.notna(d) else ""
        )
    else:
        st.info("Não há valores de data válidos para aplicar filtro.")
        # Mesmo sem filtro, se existir coluna Data, cria exibição PT-BR (vazia)
        df["Data (BR)"] = df.get(data_col, pd.Series([None]*len(df))).apply(
            lambda d: d.strftime("%d/%m/%Y") if pd.notna(d) else ""
        )
else:
    # Caso não exista a coluna "Data", cria "Data (BR)" vazia para evitar KeyError na exibição
    df["Data (BR)"] = ""

# ==========================================
# Métricas e tabela (já usando o DF filtrado)
# ==========================================
df_entrada = df[df[tipo_col].astype(str).str.lower() == "entrada"]
df_saida = df[df[tipo_col].astype(str).str.lower().isin(["saída", "saida"])]

total_entrada = df_entrada[valor_col].sum()
total_saida = df_saida[valor_col].sum()

c1, c2, c3 = st.columns(3)
c1.metric("Total de Entradas (filtrado)", f"R$ {total_entrada:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
c2.metric("Total de Saídas (filtrado)", f"R$ {total_saida:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
c3.metric("Saldo (filtrado)", f"R$ {(total_entrada - total_saida):,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))

st.subheader("Selecione uma linha")

# -------- Exibição: inclui 'Data (BR)' na tabela --------
# Mantemos a coluna original 'Data' (tipo date) para cálculos/filtro,
# mas priorizamos 'Data (BR)' na tabela para visual.
# -------- Exibição: SOMENTE 'Data (BR)' na tabela --------
# Garante que 'Data (BR)' exista (foi criada no bloco do filtro)
cols_for_view = list(df.columns)

# Remove a coluna 'Data' da visualização, se existir
if data_col in cols_for_view:
    cols_for_view.remove(data_col)

# Garante que 'Data (BR)' esteja presente; se não estiver, cria a partir de 'Data'
if "Data (BR)" not in cols_for_view:
    if data_col in df.columns:
        df["Data (BR)"] = df[data_col].apply(
            lambda d: d.strftime("%d/%m/%Y") if pd.notna(d) else ""
        )
    else:
        df["Data (BR)"] = ""

# Opcional: coloca 'Data (BR)' mais à direita de 'Forma de Pagamento' (ou no fim, se preferir)
# Primeiro remove e depois insere na posição desejada
cols_for_view.remove("Data (BR)")
insert_pos = len(cols_for_view)  # no fim; mude se quiser outra posição
cols_for_view.insert(insert_pos, "Data (BR)")

preview_df = df[cols_for_view].head(200).copy()

# Leitura da seleção
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
    return str(txt_val).replace('&','&').replace('<','<').replace('>','>')

if len(selected_rows) == 1:
    sel_row = preview_df.iloc[int(selected_rows[0])]
    tipo_txt = _escape_html(_val_or_blank(sel_row, tipo_col))
    valor_txt = _escape_html(_val_or_blank(sel_row, valor_col))
    descricao_txt = _escape_html(_val_or_blank(sel_row, descricao_col))
    cliente_txt = _escape_html(_val_or_blank(sel_row, cliente_col))
    forma_pagamento_txt = _escape_html(_val_or_blank(sel_row, forma_pagamento_col))
    # Mostra a exibição PT-BR
    data_txt = _escape_html(_val_or_blank(sel_row, "Data (BR)"))

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

# ==========================================
# Seção final (cálculo) — já com DF filtrado
# ==========================================
work_df = df.copy()

# Garantia de numérico
work_df[valor_col] = (
    work_df[valor_col]
    .astype(str)
    .str.replace(".", "", regex=False)
    .str.replace(",", ".", regex=False)
)
work_df[valor_col] = pd.to_numeric(work_df[valor_col], errors="coerce")

# Mantém 'Data' como 'date' (nenhuma conversão para datetime aqui)
# work_df[data_col] já está como date (se existir)

work_df[tipo_col] = work_df[tipo_col].astype(str).str.strip()
entrada_df = work_df[work_df[tipo_col].str.lower() == "entrada"]
saida_df = work_df[work_df[tipo_col].str.lower().isin(["saída", "saida"])]

total_entrada = entrada_df[valor_col].sum(skipna=True)
total_saida = saida_df[valor_col].sum(skipna=True)
