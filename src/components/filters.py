import pandas as pd
import streamlit as st


def aplicar_filtros(
    df: pd.DataFrame,
    data_col: str | None,
    tipo_col: str | None,
    cliente_col: str | None,
    forma_pagamento_col: str | None,
    categoria_col: str | None = None,
    produto_col: str | None = None,
    state_prefix: str = "default",
) -> pd.DataFrame:
    def _state_key(nome: str) -> str:
        return f"{state_prefix}_{nome}"

    def _limpar_selecao_invalida(selecionados, disponiveis):
        if not selecionados:
            return []
        return [x for x in selecionados if x in disponiveis]

    def _aplicar(
        base_df: pd.DataFrame,
        inicio=None,
        fim=None,
        tipos=None,
        clientes=None,
        formas=None,
        categorias=None,
        produtos=None,
    ) -> pd.DataFrame:
        out = base_df.copy()

        if data_col and inicio and fim and out[data_col].notna().any():
            out = out[
                (out[data_col].dt.date >= inicio) &
                (out[data_col].dt.date <= fim)
            ].copy()

        if tipo_col and tipos:
            out = out[out[tipo_col].astype(str).isin(tipos)].copy()

        if cliente_col and clientes:
            out = out[out[cliente_col].astype(str).isin(clientes)].copy()

        if forma_pagamento_col and formas:
            out = out[out[forma_pagamento_col].astype(str).isin(formas)].copy()

        if categoria_col and categorias:
            out = out[out[categoria_col].astype(str).isin(categorias)].copy()

        if produto_col and produtos:
            out = out[out[produto_col].astype(str).isin(produtos)].copy()

        return out

    tipo_key = _state_key("filtro_tipo")
    cliente_key = _state_key("filtro_cliente")
    forma_key = _state_key("filtro_forma")
    categoria_key = _state_key("filtro_categoria")
    produto_key = _state_key("filtro_produto")

    if tipo_key not in st.session_state:
        st.session_state[tipo_key] = []
    if cliente_key not in st.session_state:
        st.session_state[cliente_key] = []
    if forma_key not in st.session_state:
        st.session_state[forma_key] = []
    if categoria_key not in st.session_state:
        st.session_state[categoria_key] = []
    if produto_key not in st.session_state:
        st.session_state[produto_key] = []

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
            key=_state_key("periodo"),
        )

        if isinstance(periodo, tuple) and len(periodo) == 1:
            st.info("Selecione a data final para completar o intervalo.")
            st.stop()

        if isinstance(periodo, tuple) and len(periodo) == 2:
            inicio, fim = periodo
            if inicio > fim:
                inicio, fim = fim, inicio
        else:
            st.info("Selecione um intervalo de datas válido.")
            st.stop()

    tipos_sel_atual = st.session_state[tipo_key]
    clientes_sel_atual = st.session_state[cliente_key]
    formas_sel_atual = st.session_state[forma_key]
    categorias_sel_atual = st.session_state[categoria_key]
    produtos_sel_atual = st.session_state[produto_key]

    if tipo_col:
        df_tipo = _aplicar(
            df_base,
            inicio=inicio,
            fim=fim,
            clientes=clientes_sel_atual,
            formas=formas_sel_atual,
            categorias=categorias_sel_atual,
            produtos=produtos_sel_atual,
        )

        tipos_disponiveis = sorted(
            df_tipo[tipo_col].dropna().astype(str).unique().tolist()
        )

        st.session_state[tipo_key] = _limpar_selecao_invalida(
            st.session_state[tipo_key],
            tipos_disponiveis,
        )

        st.sidebar.multiselect(
            "Tipo",
            options=tipos_disponiveis,
            key=tipo_key,
            placeholder="Selecione",
        )

    tipos_sel_atual = st.session_state[tipo_key]

    if cliente_col:
        df_cliente = _aplicar(
            df_base,
            inicio=inicio,
            fim=fim,
            tipos=tipos_sel_atual,
            formas=formas_sel_atual,
            categorias=categorias_sel_atual,
            produtos=produtos_sel_atual,
        )

        clientes_disponiveis = sorted(
            df_cliente[cliente_col].dropna().astype(str).unique().tolist()
        )

        st.session_state[cliente_key] = _limpar_selecao_invalida(
            st.session_state[cliente_key],
            clientes_disponiveis,
        )

        st.sidebar.multiselect(
            "Cliente",
            options=clientes_disponiveis,
            key=cliente_key,
            placeholder="Selecione",
        )

    tipos_sel_atual = st.session_state[tipo_key]
    clientes_sel_atual = st.session_state[cliente_key]

    if forma_pagamento_col:
        df_forma = _aplicar(
            df_base,
            inicio=inicio,
            fim=fim,
            tipos=tipos_sel_atual,
            clientes=clientes_sel_atual,
            categorias=categorias_sel_atual,
            produtos=produtos_sel_atual,
        )

        formas_disponiveis = sorted(
            df_forma[forma_pagamento_col].dropna().astype(str).unique().tolist()
        )

        st.session_state[forma_key] = _limpar_selecao_invalida(
            st.session_state[forma_key],
            formas_disponiveis,
        )

        st.sidebar.multiselect(
            "Forma de pagamento",
            options=formas_disponiveis,
            key=forma_key,
            placeholder="Selecione",
        )

    tipos_sel_atual = st.session_state[tipo_key]
    clientes_sel_atual = st.session_state[cliente_key]
    formas_sel_atual = st.session_state[forma_key]

    if categoria_col:
        df_categoria = _aplicar(
            df_base,
            inicio=inicio,
            fim=fim,
            tipos=tipos_sel_atual,
            clientes=clientes_sel_atual,
            formas=formas_sel_atual,
            produtos=produtos_sel_atual,
        )

        categorias_disponiveis = sorted(
            df_categoria[categoria_col].dropna().astype(str).unique().tolist()
        )

        st.session_state[categoria_key] = _limpar_selecao_invalida(
            st.session_state[categoria_key],
            categorias_disponiveis,
        )

        st.sidebar.multiselect(
            "Categoria",
            options=categorias_disponiveis,
            key=categoria_key,
            placeholder="Selecione",
        )

    tipos_sel_atual = st.session_state[tipo_key]
    clientes_sel_atual = st.session_state[cliente_key]
    formas_sel_atual = st.session_state[forma_key]
    categorias_sel_atual = st.session_state[categoria_key]

    if produto_col:
        df_produto = _aplicar(
            df_base,
            inicio=inicio,
            fim=fim,
            tipos=tipos_sel_atual,
            clientes=clientes_sel_atual,
            formas=formas_sel_atual,
            categorias=categorias_sel_atual,
        )

        produtos_disponiveis = sorted(
            df_produto[produto_col].dropna().astype(str).unique().tolist()
        )

        st.session_state[produto_key] = _limpar_selecao_invalida(
            st.session_state[produto_key],
            produtos_disponiveis,
        )

        st.sidebar.multiselect(
            "Produto",
            options=produtos_disponiveis,
            key=produto_key,
            placeholder="Selecione",
        )

    work_df = _aplicar(
        df_base,
        inicio=inicio,
        fim=fim,
        tipos=st.session_state[tipo_key],
        clientes=st.session_state[cliente_key],
        formas=st.session_state[forma_key],
        categorias=st.session_state[categoria_key],
        produtos=st.session_state[produto_key],
    )

    return work_df