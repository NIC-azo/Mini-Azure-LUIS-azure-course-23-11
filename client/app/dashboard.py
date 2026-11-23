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
# Configuración de Página y Estilos
# ====================================================================
st.set_page_config(
    page_title="Mini-Azure LUIS | Agro Dashboard",
    page_icon="🌾",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .main-title {
        font-size: 2.2rem;
        font-weight: 700;
        color: #1E3A8A;
        margin-bottom: 0.2rem;
    }
    .sub-title {
        font-size: 1.05rem;
        color: #4B5563;
        margin-bottom: 1.5rem;
    }
    .stMetric {
        background-color: #F8FAFC;
        border: 1px solid #E2E8F0;
        border-radius: 8px;
        padding: 10px 14px;
    }
    .badge-critico {
        background-color: #FEE2E2;
        color: #991B1B;
        padding: 4px 10px;
        border-radius: 6px;
        font-weight: 600;
    }
    .badge-alerta {
        background-color: #FEF3C7;
        color: #92400E;
        padding: 4px 10px;
        border-radius: 6px;
        font-weight: 600;
    }
    .badge-ok {
        background-color: #D1FAE5;
        color: #065F46;
        padding: 4px 10px;
        border-radius: 6px;
        font-weight: 600;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ====================================================================
# Barra Lateral: Conectividad y Control LAN
# ====================================================================
st.sidebar.image("https://img.icons8.com/color/96/grape.png", width=64)
st.sidebar.title("Configuración de Red")
st.sidebar.caption("Mini-Azure LUIS (On-Premise LAN)")

server_ip = st.sidebar.text_input(
    "IP del Servidor (PC A)",
    value=TARGET_SERVER_IP,
    help="En laboratorio ingrese la IPv4 de la máquina servidor (ej. 192.168.1.XX)",
)
server_port = st.sidebar.text_input("Puerto API", value=SERVER_PORT)

API_BASE = get_api_base_url(server_ip, server_port)
st.sidebar.markdown(f"**URL Activa:** `{API_BASE}`")

# Verificación de Conectividad con /health
server_online = False
server_info = {}
try:
    resp = requests.get(f"{API_BASE}/health", timeout=2)
    if resp.status_code == 200:
        server_online = True
        server_info = resp.json()
        st.sidebar.success("🟢 Servidor Conectado (HTTP 200)")
        st.sidebar.caption(
            f"Versión: `{server_info.get('version', '1.0.0')}` | Umbral: `{server_info.get('umbral_confianza', 0.65)}`"
        )
    else:
        st.sidebar.error(f"🔴 Error del Servidor (HTTP {resp.status_code})")
except Exception:
    st.sidebar.error("🔴 Servidor Inaccesible")
    st.sidebar.caption("Compruebe la IP y que `nlp-server` esté encendido.")

st.sidebar.divider()

# Botón de Peligro: Reiniciar Estadísticas
if st.sidebar.button("🗑️ Reiniciar Estadísticas", use_container_width=True, type="secondary"):
    try:
        r = requests.post(f"{API_BASE}/nlp/estadisticas/reiniciar", timeout=3)
        if r.status_code == 200:
            st.sidebar.success("Estadísticas restablecidas a cero.")
            time.sleep(0.4)
            st.rerun()
        else:
            st.sidebar.error("No se pudo reiniciar.")
    except Exception as e:
        st.sidebar.error(f"Error de conexión: {e}")

st.sidebar.divider()
st.sidebar.markdown(
    """
    **Guía Rápida LAN:**
    1. Asegure que la PC Servidor tiene la regla de Firewall abierta en el puerto 8001.
    2. Ingrese la IP privada de la PC Servidor arriba.
    3. Monitoree las métricas en tiempo real.
    """
)

# ====================================================================
# Encabezado Principal
# ====================================================================
st.markdown('<div class="main-title">🌾 Mini-Azure LUIS — Agro Dashboard</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="sub-title">Motor de Comprensión de Lenguaje Natural On-Premise para Agroexportación (Ica: Uva de Mesa y Espárragos)</div>',
    unsafe_allow_html=True,
)

# ====================================================================
# Panel de Envío y Simulador Operativo
# ====================================================================
tab_individual, tab_lote = st.tabs(["📝 Envío Individual", "🚀 Simulador de Lote (8 Casos de Prueba)"])

# -------------------------------------------------------------
# Pestaña 1: Envío Individual
# -------------------------------------------------------------
with tab_individual:
    ejemplos_rapidos = [
        "-- Seleccionar un ejemplo rápido o escribir libremente abajo --",
        "La camara de frio 2 subio a 9 grados con 120 cajas de uva red globe",
        "se malogro la faja trasportadora de la linea 3 en packing urjente",
        "cuantos pallets de esparrago verde tenemos listos en almacen",
        "programar camion reefer para despacho de 20 pallets lote L-409 hacia pisco",
        "el lote L-512 de uva sweet globe paso control de calidad sin observaciones",
        "revisar lo que quedo pendiente ayer en la tarde con el encargado",
    ]

    seleccion_ejemplo = st.selectbox("Ejemplos representativos:", ejemplos_rapidos)
    texto_defecto = "" if seleccion_ejemplo.startswith("--") else seleccion_ejemplo

    texto_input = st.text_area(
        "Mensaje u orden operativa en lenguaje natural:",
        value=texto_defecto,
        placeholder="Ej: La camara 2 reporta 9 grados con 100 cajas de uva red globe...",
        height=80,
    )

    col_btn1, col_btn2 = st.columns([1, 4])
    with col_btn1:
        btn_analizar = st.button("⚡ Analizar Comando", type="primary", use_container_width=True)

    if btn_analizar:
        if not texto_input.strip():
            st.warning("Por favor ingrese un mensaje para analizar.")
        elif not server_online:
            st.error("No se puede conectar con el servidor NLP. Verifique la IP en la barra lateral.")
        else:
            with st.spinner("Procesando comando con Scikit-Learn..."):
                try:
                    t_inicio = time.time()
                    res_raw = requests.post(
                        f"{API_BASE}/nlp/entender-comando",
                        json={"texto": texto_input.strip()},
                        timeout=5,
                    )
                    latencia_ms = (time.time() - t_inicio) * 1000

                    if res_raw.status_code == 200:
                        resultado = res_raw.json()

                        intencion = resultado.get("intencion", "")
                        conf_int = resultado.get("confianza_intencion", 0.0)
                        sentimiento = resultado.get("sentimiento", "")
                        conf_sent = resultado.get("confianza_sentimiento", 0.0)
                        entidades = resultado.get("entidades", {})
                        accion = resultado.get("accion_sugerida", "")
                        palabras = resultado.get("palabras_clave", [])

                        st.success(f"Inferencia completada en {latencia_ms:.1f} ms")

                        # Tarjeta de Resultados
                        with st.container(border=True):
                            c1, c2, c3, c4 = st.columns(4)
                            c1.metric("Intención Detectada", intencion)
                            c2.metric("Confianza de Intención", f"{conf_int * 100:.1f}%")
                            c3.metric("Sentimiento", sentimiento, f"{conf_sent * 100:.1f}%")

                            # Formato de Acción Sugerida según criticidad
                            if accion in ["ALERTA_CRITICA_CALIDAD", "ORDEN_MANTENIMIENTO_URGENTE"]:
                                c4.markdown(f"**Acción:**<br><span class='badge-critico'>🚨 {accion}</span>", unsafe_allow_html=True)
                            elif accion == "DERIVAR_A_SUPERVISOR":
                                c4.markdown(f"**Acción:**<br><span class='badge-alerta'>⚠️ {accion}</span>", unsafe_allow_html=True)
                            else:
                                c4.markdown(f"**Acción:**<br><span class='badge-ok'>✅ {accion}</span>", unsafe_allow_html=True)

                            st.divider()

                            # Entidades Extraídas
                            st.markdown("**🏷️ Entidades Extraídas:**")
                            if entidades:
                                col_e1, col_e2, col_e3, col_e4 = st.columns(4)
                                with col_e1:
                                    st.markdown(f"**Área:** {', '.join(entidades.get('AREA', [])) or '—'}")
                                with col_e2:
                                    st.markdown(f"**Producto:** {', '.join(entidades.get('PRODUCTO', [])) or '—'}")
                                with col_e3:
                                    st.markdown(f"**Cantidad:** {', '.join(entidades.get('CANTIDAD', [])) or '—'}")
                                with col_e4:
                                    st.markdown(f"**Código Lote:** {', '.join(entidades.get('CODIGO_LOTE', [])) or '—'}")
                            else:
                                st.info("No se identificaron entidades nombradas específicas en el texto.")

                            if palabras:
                                st.caption(f"Palabras Clave (TF-IDF): {', '.join(palabras)}")

                            with st.expander("Ver JSON Crudo de Respuesta"):
                                st.json(resultado)
                    else:
                        st.error(f"Error {res_raw.status_code}: {res_raw.text}")
                except Exception as ex:
                    st.error(f"Falla de conexión: {ex}")

# -------------------------------------------------------------
# Pestaña 2: Simulador de Lote (8 Casos de Prueba)
# -------------------------------------------------------------
with tab_lote:
    st.markdown(
        "Ejecuta una batería de **8 mensajes representativos** de la operación de Ica (incluye casos con jerga, errores ortográficos, múltiples entidades y casos ambiguos) para poblar las métricas acumuladas."
    )

    bateria_mensajes = [
        "La camara de frio 2 subio a 9 grados con 120 cajas de uva red globe",
        "se malogro la faja trasportadora de la linea 3 en packing urjente",
        "cuantos pallets de esparrago verde tenemos listos en almacen",
        "programar camion reefer para despacho de 20 pallets lote L-409 hacia pisco",
        "el lote L-512 de uva sweet globe paso control de calidad sin observaciones",
        "compresor del tunel 1 presentando ruido fuerte y perdida de frio",
        "necesito saber cuantas jabas cosecheras y bolsas SO2 quedan en bodega",
        "revisar lo que quedo pendiente ayer en la tarde con el encargado",
    ]

    with st.expander("Ver mensajes del Lote de Prueba", expanded=False):
        for idx, m in enumerate(bateria_mensajes, 1):
            st.markdown(f"**{idx}.** {m}")

    if st.button("🚀 Ejecutar Lote Completo (8 mensajes)", type="primary"):
        if not server_online:
            st.error("Servidor no disponible para procesar el lote.")
        else:
            progreso = st.progress(0, text="Iniciando envío de lote...")
            exitos = 0
            for i, msg in enumerate(bateria_mensajes):
                try:
                    requests.post(
                        f"{API_BASE}/nlp/entender-comando",
                        json={"texto": msg},
                        timeout=5,
                    )
                    exitos += 1
                except Exception:
                    pass
                porcentaje = int(((i + 1) / len(bateria_mensajes)) * 100)
                progreso.progress(porcentaje, text=f"Enviando mensaje {i+1} de {len(bateria_mensajes)}...")
                time.sleep(0.08)

            st.success(f"Lote procesado con éxito: {exitos}/{len(bateria_mensajes)} mensajes registrados.")
            time.sleep(0.4)
            st.rerun()

st.divider()

# ====================================================================
# Dashboard Analítico en Tiempo Real
# ====================================================================
st.subheader("📊 Métricas y KPIs de la Operación en Tiempo Real")

# Obtener estadísticas de /nlp/estadisticas
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

# Cálculo de Alertas Críticas (Reporte Calidad o Falla Equipo con acciones críticas)
alertas_criticas = 0
for m in ultimos_mensajes:
    if m.get("accion_sugerida") in ["ALERTA_CRITICA_CALIDAD", "ORDEN_MANTENIMIENTO_URGENTE"]:
        alertas_criticas += 1
# Si no hay bitácora completa, estimar con suma de intenciones críticas
if total_mensajes > len(ultimos_mensajes) and alertas_criticas == 0:
    alertas_criticas = por_intencion.get("FALLA_EQUIPO", 0) + por_intencion.get("REPORTE_CALIDAD", 0)

# Fila de 4 KPIs
kpi1, kpi2, kpi3, kpi4 = st.columns(4)
kpi1.metric("Total Mensajes Procesados", total_mensajes)
kpi2.metric("Confianza Promedio", f"{confianza_promedio * 100:.1f}%")
kpi3.metric("Tasa de Derivación", f"{tasa_derivacion * 100:.1f}%", help="Proporción de mensajes con INTENCION_NO_CLARA")
kpi4.metric("Alertas Críticas Registradas", alertas_criticas, help="ALERTA_CRITICA_CALIDAD y ORDEN_MANTENIMIENTO_URGENTE")

st.markdown("<br>", unsafe_allow_html=True)

# Distribuciones Visuales (Gráficos)
col_g1, col_g2 = st.columns(2)

with col_g1:
    st.markdown("**Distribución por Intención Operativa**")
    if por_intencion and any(v > 0 for v in por_intencion.values()):
        df_intent = pd.DataFrame(
            list(por_intencion.items()),
            columns=["Intención", "Conteo"],
        ).set_index("Intención")
        st.bar_chart(df_intent, color="#2563EB", use_container_width=True)
    else:
        st.info("No hay datos de intenciones registrados aún.")

with col_g2:
    st.markdown("**Distribución por Sentimiento**")
    if por_sentimiento and any(v > 0 for v in por_sentimiento.values()):
        df_sent = pd.DataFrame(
            list(por_sentimiento.items()),
            columns=["Sentimiento", "Conteo"],
        ).set_index("Sentimiento")
        st.bar_chart(df_sent, color="#10B981", use_container_width=True)
    else:
        st.info("No hay datos de sentimientos registrados aún.")

# Entidades Frecuentes y Bitácora Reciente
st.markdown("<br>", unsafe_allow_html=True)
col_b1, col_b2 = st.columns([1, 2])

with col_b1:
    st.markdown("**🏷️ Ranking de Entidades Más Reportadas**")
    if entidades_frecuentes:
        df_ent = pd.DataFrame(
            list(entidades_frecuentes.items()),
            columns=["Entidad / Recurso", "Frecuencia"],
        ).head(8)
        st.dataframe(df_ent, hide_index=True, use_container_width=True)
    else:
        st.info("Aún no se han acumulado entidades.")

with col_b2:
    st.markdown("**📋 Bitácora Reciente de Mensajes (Últimos 15)**")
    if ultimos_mensajes:
        tabla_datos = []
        for reg in ultimos_mensajes:
            ts = reg.get("timestamp", "")
            hora_fmt = ts[11:19] if len(ts) >= 19 else ts
            ents = reg.get("entidades", {})
            ents_resumen = ", ".join([f"{k}: {', '.join(v)}" for k, v in ents.items() if v]) or "—"

            tabla_datos.append({
                "Hora (UTC)": hora_fmt,
                "Texto": reg.get("texto_original", ""),
                "Intención": reg.get("intencion", ""),
                "Conf. (%)": f"{float(reg.get('confianza_intencion', 0.0)) * 100:.1f}",
                "Sent.": reg.get("sentimiento", ""),
                "Entidades": ents_resumen,
                "Acción Sugerida": reg.get("accion_sugerida", ""),
            })

        df_bitacora = pd.DataFrame(tabla_datos)
        st.dataframe(df_bitacora, hide_index=True, use_container_width=True)
    else:
        st.info("La bitácora se encuentra vacía. Ejecute el lote o envíe un mensaje individual.")
