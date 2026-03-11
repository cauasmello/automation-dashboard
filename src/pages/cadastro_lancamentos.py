from datetime import date

import gspread
import pandas as pd
import streamlit as st
from google.oauth2.service_account import Credentials


st.title("Cadastro de Lançamentos")
st.caption("Registre um novo lançamento com campos padronizados.")

# ==========================================================
# CONFIGURAÇÕES
# ==========================================================
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

TIPOS = ["entrada", "saida"]

CLIENTES = [
    "cliente a",
    "cliente b",
    "cliente c",
]

FORMAS_PAGAMENTO = [
    "pix",
    "cartao",
    "dinheiro",
    "boleto",
]

CATEGORIAS = [
    "venda",
    "alimentacao",
    "transporte",
    "manutencao",
    "outros",
]

PRODUTOS = [
    "produto 1",
    "produto 2",
    "produto 3",
]

# ==========================================================
# CONEXÃO GOOGLE SHEETS
# ==========================================================
@st.cache_resource
def conectar_google_sheets():
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=SCOPES,
    )
    client = gspread.authorize(creds)
    return client


def obter_aba():
    client = conectar_google_sheets()
    planilha = client.open_by_key(st.secrets["google_sheets"]["spreadsheet_id"])
    aba = planilha.worksheet(st.secrets["google_sheets"]["worksheet_name"])
    return aba


def salvar_lancamento_google_sheets(registro: dict):
    aba = obter_aba()

    linha = [
        registro["tipo"],
        registro["cliente"],
        registro["forma de pagamento"],
        registro["categoria"],
        registro["produto"],
        registro["quantidade"],
        registro["descrição"],
        registro["valor"],
        registro["data"],
    ]

    aba.append_row(linha, value_input_option="USER_ENTERED")


# ==========================================================
# FORMULÁRIO
# ==========================================================
with st.form("form_cadastro_lancamento", clear_on_submit=True):
    c1, c2 = st.columns(2)

    with c1:
        tipo = st.selectbox("Tipo", TIPOS)
        cliente = st.selectbox("Cliente", CLIENTES)
        forma_pagamento = st.selectbox("Forma de pagamento", FORMAS_PAGAMENTO)
        categoria = st.selectbox("Categoria", CATEGORIAS)
        produto = st.selectbox("Produto", PRODUTOS)

    with c2:
        data_lancamento = st.date_input(
            "Data",
            value=date.today(),
            format="DD/MM/YYYY",
        )

        quantidade = st.number_input(
            "Quantidade",
            min_value=1,
            step=1,
            value=1,
            format="%d",
        )

        valor = st.number_input(
            "Valor",
            min_value=0.01,
            step=0.01,
            value=0.01,
            format="%.2f",
        )

    descricao = st.text_area(
        "Descrição",
        placeholder="Digite uma descrição livre...",
        height=100,
    )

    submitted = st.form_submit_button("Salvar lançamento")


# ==========================================================
# VALIDAÇÃO E SALVAMENTO
# ==========================================================
if submitted:
    erros = []

    if not tipo:
        erros.append("Selecione o tipo.")
    if not cliente:
        erros.append("Selecione o cliente.")
    if not forma_pagamento:
        erros.append("Selecione a forma de pagamento.")
    if not categoria:
        erros.append("Selecione a categoria.")
    if not produto:
        erros.append("Selecione o produto.")
    if quantidade < 1:
        erros.append("A quantidade deve ser maior que zero.")
    if valor <= 0:
        erros.append("O valor deve ser maior que zero.")

    if erros:
        for erro in erros:
            st.error(erro)
        st.stop()

    novo_registro = {
        "tipo": str(tipo).strip().lower(),
        "cliente": str(cliente).strip().lower(),
        "forma de pagamento": str(forma_pagamento).strip().lower(),
        "categoria": str(categoria).strip().lower(),
        "produto": str(produto).strip().lower(),
        "quantidade": int(quantidade),
        "descrição": str(descricao).strip(),
        "valor": float(valor),
        "data": pd.to_datetime(data_lancamento).strftime("%Y-%m-%d"),
    }

    try:
        salvar_lancamento_google_sheets(novo_registro)
        st.success("Lançamento salvo com sucesso na planilha.")
        st.dataframe(
            pd.DataFrame([novo_registro]),
            use_container_width=True,
            hide_index=True,
        )
    except Exception as e:
        st.error("Erro ao salvar no Google Sheets.")
        st.exception(e)