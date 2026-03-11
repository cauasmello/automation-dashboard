import streamlit as st

st.set_page_config(
    page_title="Automation Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

pg = st.navigation(
    [
        st.Page("pages/dashboard.py", title="Dashboard Operacional", icon="📊"),
        st.Page("pages/analise_dados.py", title="Análise de Dados", icon="📈"),
        st.Page("pages/cadastro_lancamentos.py", title="Lançamento de Dados", icon="📈")
    ]
)

pg.run()