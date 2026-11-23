import sys
from pathlib import Path
import json
import time
from datetime import datetime
import pandas as pd
import requests
import streamlit as st

# Inyectar directorios en sys.path para resolver 'app' tanto en contenedor como en local
CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
for p in [str(PROJECT_ROOT), str(CURRENT_DIR)]:
    if p not in sys.path:
        sys.path.insert(0, p)

try:
    from app.config import TARGET_SERVER_IP, SERVER_PORT, get_api_base_url
except ModuleNotFoundError:
    from config import TARGET_SERVER_IP, SERVER_PORT, get_api_base_url

# ====================================================================
# Configuración de Página y Estilos Visuales
# ====================================================================
st.set_page_config(
    page_title="Mini-Azure LUIS",
    page_icon="🌾",
    layout="wide",
    initial_sidebar_state="auto",
)

st.markdown(
    """
    <style>
    .main-title {
        font-size: 2.1rem;
        font-weight: 700;
        color: #38BDF8;
        margin-bottom: 0.2rem;
    }
    .sub-title {
        font-size: 0.98rem;
        color: #94A3B8;
        margin-bottom: 1.2rem;
    }
    div[data-testid="stMetric"] {
        background: linear-gradient(135deg, rgba(30, 41, 59, 0.85), rgba(15, 23, 42, 0.95)) !important;
        border: 1px solid rgba(56, 189, 248, 0.25) !important;
        border-radius: 12px !important;
        padding: 16px 20px !important;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.25) !important;
    }
    div[data-testid="stMetric"] label, div[data-testid="stMetric"] div[data-testid="stMetricLabel"] p {
        color: #94A3B8 !important;
        font-size: 0.85rem !important;
        font-weight: 600 !important;
        text-transform: uppercase !important;
        letter-spacing: 0.05em !important;
    }
    div[data-testid="stMetric"] div[data-testid="stMetricValue"] {
        color: #38BDF8 !important;
        font-size: 1.85rem !important;
        font-weight: 700 !important;
    }
    .badge-critico {
        background-color: rgba(239, 68, 68, 0.2);
        color: #FCA5A5;
        border: 1px solid #EF4444;
        padding: 4px 10px;
        border-radius: 6px;
        font-weight: 600;
    }
    .badge-alerta {
        background-color: rgba(245, 158, 11, 0.2);
        color: #FCD34D;
        border: 1px solid #F59E0B;
        padding: 4px 10px;
        border-radius: 6px;
        font-weight: 600;
    }
    .badge-ok {
        background-color: rgba(16, 185, 129, 0.2);
        color: #6EE7B7;
        border: 1px solid #10B981;
        padding: 4px 10px;
        border-radius: 6px;
        font-weight: 600;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ====================================================================
# Detección de Dispositivo Móvil (User-Agent)
# ====================================================================
def detectar_dispositivo_movil() -> bool:
    """Detecta si la petición HTTP proviene de un smartphone o tablet (Android / iOS)."""
    try:
        if hasattr(st, "context") and hasattr(st.context, "headers"):
            ua = st.context.headers.get("user-agent", "").lower()
            palabras_movil = ["android", "mobile", "iphone", "ipod", "blackberry", "windows phone"]
            return any(w in ua for w in palabras_movil)
    except Exception:
        pass
    return False

es_movil = detectar_dispositivo_movil()
param_rol_solicitado = st.query_params.get("rol", "").lower()

# REGLA ESTRICTA DE SEGURIDAD Y SEPARACIÓN DE ROLES:
# 1. En el Celular (Terminal Operativa de Campo):
#    - NUNCA ve KPIs, métricas globales, gráficos ni bitácora administrativa.
#    - La barra lateral se oculta completamente vía CSS.
#    - Envía el reporte u orden operativa y recibe DIRECTAMENTE la respuesta JSON del modelo de inferencia LUIS Local según el enunciado.
# 2. En la PC (Estación Central de Monitoreo):
#    - Visualiza exclusivamente el Dashboard analítico en tiempo real consumiendo GET /nlp/estadisticas y sus KPIs con auto-refresco.
if es_movil:
    modo_activo = "operario"
    st.query_params["rol"] = "operario"
    # Ocultar completamente la barra lateral y su botón de despliegue en celulares
    st.markdown(
        """
        <style>
        section[data-testid="stSidebar"], [data-testid="collapsedControl"] {
            display: none !important;
        }
        .block-container {
            padding-top: 1.5rem !important;
            padding-bottom: 2rem !important;
            max-width: 100% !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
else:
    # En PC por defecto abre el Dashboard (Manager)
    # Permite alternar a simulación móvil si se pasa ?rol=operario o desde el menú
    if param_rol_solicitado == "operario":
        modo_activo = "operario"
    else:
        modo_activo = "dashboard"
        st.query_params["rol"] = "dashboard"

# ====================================================================
# Barra Lateral (Solo disponible y visible en PC)
# ====================================================================
server_ip = TARGET_SERVER_IP
server_port = SERVER_PORT
auto_refresh = False

if not es_movil:
    st.sidebar.markdown("# 🍇 Mini-Azure LUIS")
    st.sidebar.caption("Estación Central: Monitoreo & Control")

    modo_pc = st.sidebar.radio(
        "Modo de Vista PC",
        ["Dashboard de Monitoreo", "Simular Chat Móvil"],
        index=0 if modo_activo == "dashboard" else 1,
    )
    if modo_pc == "Simular Chat Móvil":
        modo_activo = "operario"
    else:
        modo_activo = "dashboard"

    st.sidebar.divider()

    # Configuración de Conexión LAN
    server_ip = st.sidebar.text_input(
        "IP del Servidor (PC A)",
        value=TARGET_SERVER_IP,
        help="En laboratorio o zona Wi-Fi ingrese la IPv4 del Servidor (ej. 192.168.1.XX o 192.168.137.1)",
    )
    server_port = st.sidebar.text_input("Puerto API", value=SERVER_PORT)

API_BASE = get_api_base_url(server_ip, server_port)

# Verificación de Conectividad con /health
server_online = False
server_info = {}
try:
    resp = requests.get(f"{API_BASE}/health", timeout=2)
    if resp.status_code == 200:
        server_online = True
        server_info = resp.json()
        if not es_movil:
            st.sidebar.success("🟢 Servidor Conectado")
    else:
        if not es_movil:
            st.sidebar.error(f"🔴 Error Servidor (HTTP {resp.status_code})")
except Exception:
    if not es_movil:
        st.sidebar.error("🔴 Servidor Inaccesible")

# Controles de la barra lateral en PC para el Dashboard
if not es_movil and modo_activo == "dashboard":
    auto_refresh = st.sidebar.toggle(
        "🔄 Auto-actualizar cada 3s",
        value=True,
        help="Monitorea en tiempo real las llegadas de mensajes desde los celulares",
    )

    st.sidebar.divider()
    if st.sidebar.button("🗑️ Reiniciar Estadísticas", use_container_width=True, type="secondary"):
        try:
            r = requests.post(f"{API_BASE}/nlp/estadisticas/reiniciar", timeout=3)
            if r.status_code == 200:
                st.sidebar.success("Estadísticas restablecidas a cero.")
                time.sleep(0.3)
                st.rerun()
        except Exception as e:
            st.sidebar.error(f"Error al reiniciar: {e}")

    with st.sidebar.expander("⚡ Simular Lote (8 Mensajes)", expanded=False):
        st.caption("Puebla métricas de prueba sin usar el celular:")
        if st.button("🚀 Ejecutar Lote en Servidor", use_container_width=True):
            bateria = [
                "La camara de frio 2 subio a 9 grados con 120 cajas de uva red globe",
                "se malogro la faja trasportadora de la linea 3 en packing urjente",
                "cuantos pallets de esparrago verde tenemos listos en almacen",
                "programar camion reefer para despacho de 20 pallets lote L-409 hacia pisco",
                "el lote L-512 de uva sweet globe paso control de calidad sin observaciones",
                "compresor del tunel 1 presentando ruido fuerte y perdida de frio",
                "necesito saber cuantas jabas cosecheras y bolsas SO2 quedan en bodega",
                "revisar lo que quedo pendiente ayer en la tarde con el encargado",
            ]
            for msg in bateria:
                try:
                    requests.post(f"{API_BASE}/nlp/entender-comando", json={"texto": msg}, timeout=4)
                except Exception:
                    pass
            st.success("8 mensajes enviados exitosamente.")
            time.sleep(0.3)
            st.rerun()


# ====================================================================
# VISTA 1: CELULAR / OPERARIO (SOLO ENVÍO + RESPUESTA MODELO SEGÚN ENUNCIADO)
# ====================================================================
if modo_activo == "operario":
    st.markdown('<div class="main-title">📱 Reporte Operativo de Campo</div>', unsafe_allow_html=True)
    st.caption("Envío de incidencias operativas a Mini-Azure LUIS (Ica: Uva de Mesa y Espárragos)")

    if not server_online:
        st.error("🔴 Servidor NLP fuera de línea. Verifique la conectividad de red con el host central.")

    # Inicializar historial del chat
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = [
            {
                "role": "assistant",
                "content": "👋 **Terminal Operativa Móvil:** Escriba su reporte de campo o seleccione una sugerencia rápida:",
            }
        ]

    # Sugerencias rápidas para el operario en campo
    st.markdown("**⚡ Sugerencias rápidas:**")
    sugerencias = [
        "La camara de frio 2 subio a 9 grados con 120 cajas de uva red globe",
        "se malogro la faja trasportadora de la linea 3 en packing urjente",
        "cuantos pallets de esparrago verde tenemos listos en almacen",
        "programar camion reefer para despacho de 20 pallets lote L-409 hacia pisco",
    ]

    cols_sug = st.columns(2)
    sug_seleccionada = None
    for idx, s in enumerate(sugerencias):
        col_t = cols_sug[idx % 2]
        label = s if len(s) < 32 else s[:30] + "..."
        if col_t.button(f"📌 {label}", key=f"sug_{idx}", use_container_width=True):
            sug_seleccionada = s

    # Mostrar mensajes del chat
    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            if isinstance(msg["content"], dict):
                # Respuesta directa del modelo según especificación del enunciado
                st.json(msg["content"])
            else:
                st.markdown(msg["content"])

    user_input = st.chat_input("Escribe el reporte operativo aquí...")
    prompt_final = sug_seleccionada or user_input

    if prompt_final:
        # Registrar mensaje enviado por el usuario
        st.session_state.chat_history.append({"role": "user", "content": prompt_final})
        with st.chat_message("user"):
            st.markdown(prompt_final)

        with st.chat_message("assistant"):
            if not server_online:
                st.error("No se pudo enviar. El servidor está desconectado.")
            else:
                with st.spinner("Consultando modelo LUIS Local..."):
                    try:
                        r = requests.post(f"{API_BASE}/nlp/entender-comando", json={"texto": prompt_final}, timeout=5)
                        if r.status_code == 200:
                            data = r.json()
                            # El celular muestra EXCLUSIVAMENTE la respuesta JSON del modelo de inferencia
                            st.json(data)
                            st.session_state.chat_history.append({
                                "role": "assistant",
                                "content": data,
                            })
                        else:
                            st.error(f"Error {r.status_code}: {r.text}")
                    except Exception as ex:
                        st.error(f"Falla de conexión: {ex}")


# ====================================================================
# VISTA 2: PC CENTRAL (SOLO DASHBOARD ANALÍTICO Y KPIS EN TIEMPO REAL)
# ====================================================================
else:
    st.markdown('<div class="main-title">🌾 Mini-Azure LUIS — Dashboard de Monitoreo</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="sub-title">Tablero de Control Operativo Agroexportador en Tiempo Real (Ica: Uva de Mesa y Espárragos)</div>',
        unsafe_allow_html=True,
    )

    # Consulta a GET /nlp/estadisticas
    stats = {
        "total_mensajes": 0,
        "por_intencion": {},
        "por_sentimiento": {},
        "confianza_promedio": 0.0,
        "tasa_derivacion": 0.0,
        "entidades_frecuentes": {},
        "ultimos_mensajes": [],
    }
    if server_online:
        try:
            r_stats = requests.get(f"{API_BASE}/nlp/estadisticas", timeout=3)
            if r_stats.status_code == 200:
                stats = r_stats.json()
        except Exception:
            st.warning("No se pudieron cargar las estadísticas del servidor.")

    total_mensajes = stats.get("total_mensajes", 0)
    por_intencion = stats.get("por_intencion", {})
    por_sentimiento = stats.get("por_sentimiento", {})
    confianza_promedio = stats.get("confianza_promedio", 0.0)
    tasa_derivacion = stats.get("tasa_derivacion", 0.0)
    entidades_frecuentes = stats.get("entidades_frecuentes", {})
    ultimos_mensajes = stats.get("ultimos_mensajes", [])

    # Alertas críticas
    alertas_criticas = 0
    for m in ultimos_mensajes:
        if m.get("accion_sugerida") in ["ALERTA_CRITICA_CALIDAD", "ORDEN_MANTENIMIENTO_URGENTE"]:
            alertas_criticas += 1
    if total_mensajes > len(ultimos_mensajes) and alertas_criticas == 0:
        alertas_criticas = por_intencion.get("FALLA_EQUIPO", 0) + por_intencion.get("REPORTE_CALIDAD", 0)

    # 1. KPIs Rápidos (según Sección 4 - Fase 3 del enunciado)
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Total Mensajes Procesados", total_mensajes)
    k2.metric("Confianza Promedio", f"{confianza_promedio * 100:.1f}%")
    k3.metric("Tasa de Derivación", f"{tasa_derivacion * 100:.1f}%", help="Proporción con INTENCION_NO_CLARA")
    k4.metric("Alertas Críticas Registradas", alertas_criticas, help="ALERTA_CRITICA_CALIDAD y ORDEN_MANTENIMIENTO_URGENTE")

    st.markdown("<br>", unsafe_allow_html=True)

    # 2. Distribución Visual (según enunciado: conteo o gráfico por intención y por sentimiento)
    cg1, cg2 = st.columns(2)
    with cg1:
        st.markdown("**Distribución por Intención Operativa**")
        if por_intencion and any(v > 0 for v in por_intencion.values()):
            df_intent = pd.DataFrame(
                list(por_intencion.items()),
                columns=["Intención", "Conteo"],
            ).set_index("Intención")
            st.bar_chart(df_intent, color="#2563EB", use_container_width=True)
        else:
            st.info("Sin registros de intenciones aún.")

    with cg2:
        st.markdown("**Distribución por Sentimiento**")
        if por_sentimiento and any(v > 0 for v in por_sentimiento.values()):
            df_sent = pd.DataFrame(
                list(por_sentimiento.items()),
                columns=["Sentimiento", "Conteo"],
            ).set_index("Sentimiento")
            st.bar_chart(df_sent, color="#10B981", use_container_width=True)
        else:
            st.info("Sin registros de sentimientos aún.")

    # 3. Ranking de Entidades y Bitácora Reciente (según enunciado)
    st.markdown("<br>", unsafe_allow_html=True)
    cb1, cb2 = st.columns([1, 2])
    with cb1:
        st.markdown("**🏷️ Entidades y Áreas Más Reportadas**")
        if entidades_frecuentes:
            df_ent = pd.DataFrame(
                list(entidades_frecuentes.items()),
                columns=["Entidad / Recurso", "Frecuencia"],
            ).head(8)
            st.dataframe(df_ent, hide_index=True, use_container_width=True)
        else:
            st.info("Aún no se han acumulado entidades.")

    with cb2:
        st.markdown("**📋 Bitácora Reciente de Mensajes (Últimos 15)**")
        if ultimos_mensajes:
            tabla = []
            for reg in ultimos_mensajes:
                ts = reg.get("timestamp", "")
                hora = ts[11:19] if len(ts) >= 19 else ts
                ents = reg.get("entidades", {})
                ents_resumen = ", ".join([f"{k}: {', '.join(v) if isinstance(v, list) else v}" for k, v in ents.items() if v]) or "—"
                tabla.append({
                    "Hora (UTC)": hora,
                    "Texto": reg.get("texto_original", ""),
                    "Intención": reg.get("intencion", ""),
                    "Conf. (%)": f"{float(reg.get('confianza_intencion', 0.0)) * 100:.1f}",
                    "Sent.": reg.get("sentimiento", ""),
                    "Entidades": ents_resumen,
                    "Acción Sugerida": reg.get("accion_sugerida", ""),
                })
            st.dataframe(pd.DataFrame(tabla), hide_index=True, use_container_width=True)
        else:
            st.info("Bitácora vacía. Los reportes enviados desde los celulares aparecerán aquí en vivo.")

    # Auto-actualización periódica de la pantalla de la PC
    if auto_refresh:
        time.sleep(3)
        st.rerun()
