import streamlit as st
from app.config import get_api_base_url, TARGET_SERVER_IP, SERVER_PORT

st.set_page_config(
    page_title="Mini-Azure LUIS | Agro Dashboard",
    page_icon="🌾",
    layout="wide"
)

st.title("🌾 Mini-Azure LUIS - Cliente LAN y Dashboard")

st.sidebar.header("Configuración de Red LAN")
server_ip = st.sidebar.text_input("IP del Servidor (PC A)", value=TARGET_SERVER_IP)
api_url = get_api_base_url(server_ip)
st.sidebar.info(f"Target API: `{api_url}`")

st.info("Paso 0.2 completado: Entorno y orquestación Docker Compose Watch configurados.")
