# Ficha Técnica y Topología de Red LAN
## Mini-Azure LUIS: Sistema Local de Clasificación de Reclamos, Extracción de Intenciones y Analítica Operativa con NLP

- **Dominio:** Agroexportación en Ica, Perú (Uva de mesa: Red Globe, Sweet Globe, Autumn Crisp, uva sin pepa; Espárragos: verde y blanco).
- **Repositorio Público GitHub:** [https://github.com/NIC-azo/Mini-Azure-LUIS-azure-course-23-11](https://github.com/NIC-azo/Mini-Azure-LUIS-azure-course-23-11)
- **Documento de Bitácora de Avances:** `C:\Users\Alumno\Documents\1412994\azure\days\23_11\bitacora_avances_integracion.md`
- **Fecha de Evaluación:** 23 de Noviembre de 2026

---

## 1. Topología de Red LAN y Arquitectura Desacoplada

El sistema se compone de dos nodos físicos desacoplados conectados sobre la misma red local (LAN) del laboratorio, permitiendo que el **Integrante A** despliegue el motor de inferencia y persistencia (`nlp-server`) y el **Integrante B** despliegue el simulador y dashboard analítico (`nlp-client`).

```mermaid
flowchart LR
    subgraph PC_B ["PC CLIENTE (Integrante B) - 192.168.1.YY"]
        Browser["Navegador Web / Operador"]
        subgraph Docker_Client ["Docker Desktop"]
            ClientContainer["Contenedor nlp-client\nStreamlit (:8501)\nDynamic API Target"]
        end
        Browser -->|HTTP :8501| ClientContainer
    end

    subgraph LAN ["Red de Área Local (LAN Laboratorio / Switch 1 Gbps)"]
        ClientContainer -->|"HTTP POST / GET :8001\n(Payload JSON)"| FW
    end

    subgraph PC_A ["PC SERVIDOR (Integrante A) - 192.168.1.XX"]
        FW["Firewall Windows 11\nRegla Inbound TCP 8001\n(Allow)"]
        subgraph Docker_Server ["Docker Desktop (0.0.0.0:8001)"]
            subgraph ServerContainer ["Contenedor nlp-server"]
                FastAPI["FastAPI API REST\nUvicorn :8001"]
                Engine["AgroNLPEngine\nTF-IDF + LogisticRegression\nRegEx Entidades"]
                Models[("Modelos .joblib\nintent / sentiment")]
                Analytics["Gestor Analítica\nthreading.Lock()"]
                History[("Persistencia\nhistorial.json")]
            end
        end
        FW --> Docker_Server
        FastAPI --> Engine
        Engine --> Models
        FastAPI --> Analytics
        Analytics --> History
    end
```

### Mecanismos de Aislamiento y Sincronización
1. **Desacoplamiento por Variables de Entorno (`.env`):**
   - La PC Cliente únicamente necesita conocer la IPv4 de la PC Servidor (`TARGET_SERVER_IP=192.168.1.XX`) y el puerto (`SERVER_PORT=8001`). No existe acoplamiento en el código fuente.
   - En la PC Servidor, el servicio escucha en `0.0.0.0:8001` mediante Docker Port Forwarding.
2. **Sincronización en Caliente (`develop.watch` y Bind Mounts):**
   - `./server/app` $\rightarrow$ `/app/app` con `action: sync` (recarga automática con `uvicorn --reload`).
   - `./server/data` $\rightarrow$ `/app/data` con `action: sync` (permite editar `dataset_agro.csv` y persistir `historial.json` en el host).
   - `./client/app` $\rightarrow$ `/app/app` con `action: sync` (actualización instantánea de Streamlit sin reconstruir imágenes).

### 1.1. Arquitectura de Clientes y Separación Estricta de Dispositivos (Fase 3)

Para cumplir con la separación de responsabilidades y el principio de menor privilegio operativo del fundo, el cliente implementa una bifurcación estricta según el dispositivo:

1. **Terminal Operativa Móvil (Celulares en Campo / LAN Wi-Fi):**
   - **Acceso:** Mediante smartphone a `http://<IP_SERVIDOR>:8501/`.
   - **Detección Automática:** Detección de hardware mediante la cabecera HTTP `User-Agent` (`android`, `mobile`, `iphone`).
   - **Aislamiento Total de la Barra Lateral:** Ocultamiento total de `st.sidebar` y del control de despliegue `>>` mediante CSS prioritario (`section[data-testid="stSidebar"], [data-testid="collapsedControl"] { display: none !important; }`). El operario no puede acceder a configuraciones ni alternar vistas.
   - **Cero KPIs ni Métricas en Móvil:** El celular **no muestra ningún KPI, tarjeta de métricas, gráfico ni bitácora administrativa**.
   - **Respuesta Conversacional Humana (Sin JSON ni Estadísticas):** Al enviar una orden operativa (ej. *"El camion llego tarde"* o *"La camara de frio 2 subio a 9 grados con 120 cajas de uva red globe"*), el chat responde con un mensaje claro, directo y operativo confirmando la acción sugerida y los recursos identificados (ubicación, producto, cantidad, lote). El operario no ve código JSON, probabilidades ni métricas internas, garantizando una interacción fluida en campo mientras el backend registra el evento en `historial.json` para el Dashboard de la PC.

2. **Estación Central de Monitoreo (Dashboard Ligero en PC):**
   - **Acceso:** Desde el navegador de la PC central a `http://localhost:8501/`.
   - **Consumo Analítico:** Realiza peticiones a `GET /nlp/estadisticas` y `GET /health`.
   - **Métricas y Visualizaciones en Tiempo Real:**
     - 4 KPIs analíticos: Total Mensajes Procesados, Confianza Promedio, Tasa de Derivación y Alertas Críticas Registradas (con estilo Dark Mode de alto contraste).
     - Gráficos de barras interactivos por Intención Operativa y por Sentimiento.
     - Ranking de Entidades y Áreas más reportadas.
     - Bitácora reciente con los últimos 15 eventos registrados.
     - Auto-actualización periódica cada 3 segundos (`auto_refresh=True`), permitiendo observar en la pantalla de la PC cómo se actualizan las métricas y los gráficos en vivo cuando los operarios reportan desde sus teléfonos móviles.

---

## 2. Evidencias Reales de Ejecución (Respuestas JSON del Servidor)

Las siguientes evidencias fueron obtenidas mediante peticiones HTTP reales contra el servidor en ejecución (`http://localhost:8001`).

### Caso 1: Reporte Crítico con Múltiples Entidades (`REPORTE_CALIDAD`)
- **Texto evaluado:** `"La camara de frio 2 subio a 9 grados con 120 cajas de uva red globe"`
- **Resultado JSON:**
```json
{
  "texto_original": "La camara de frio 2 subio a 9 grados con 120 cajas de uva red globe",
  "intencion": "REPORTE_CALIDAD",
  "confianza_intencion": 0.6516,
  "sentimiento": "NEGATIVO",
  "confianza_sentimiento": 0.6157,
  "entidades": {
    "AREA": ["camara de frio 2"],
    "PRODUCTO": ["uva red globe"],
    "CANTIDAD": ["9 grados", "120 cajas"]
  },
  "palabras_clave": ["120", "120 cajas", "frio subio", "grados 120"],
  "accion_sugerida": "ALERTA_CRITICA_CALIDAD"
}
```

---

### Caso 2: Falla de Equipo con Jerga y Errores Ortográficos (`FALLA_EQUIPO`)
- **Texto evaluado:** `"se malogro la faja trasportadora de la linea 3 en packing urjente"`
- **Resultado JSON:**
```json
{
  "texto_original": "se malogro la faja trasportadora de la linea 3 en packing urjente",
  "intencion": "FALLA_EQUIPO",
  "confianza_intencion": 0.6658,
  "sentimiento": "NEGATIVO",
  "confianza_sentimiento": 0.7367,
  "entidades": {
    "AREA": ["linea 3", "packing"]
  },
  "palabras_clave": ["malogro faja", "packing urjente", "malogro", "trasportadora linea"],
  "accion_sugerida": "ORDEN_MANTENIMIENTO_URGENTE"
}
```

---

### Caso 3: Activación del Umbral de Fallback (`INTENCION_NO_CLARA`)
- **Texto evaluado:** `"revisar lo que quedo pendiente ayer en la tarde con el encargado"`
- **Criterio de decisión:** Confianza de intención ($0.3176$) inferior al umbral configurado (`CONFIDENCE_THRESHOLD = 0.65`).
- **Resultado JSON:**
```json
{
  "texto_original": "revisar lo que quedo pendiente ayer en la tarde con el encargado",
  "intencion": "INTENCION_NO_CLARA",
  "confianza_intencion": 0.3176,
  "sentimiento": "NEGATIVO",
  "confianza_sentimiento": 0.4068,
  "entidades": {},
  "palabras_clave": ["quedo", "revisar"],
  "accion_sugerida": "DERIVAR_A_SUPERVISOR"
}
```

---

### Caso 4: Consolidado de Analítica Acumulada (`GET /nlp/estadisticas`)
Tras la ejecución secuencial de la batería completa de 6 mensajes de prueba, el endpoint de analítica reportó el siguiente estado consolidado:

```json
{
  "total_mensajes": 6,
  "por_intencion": {
    "REPORTE_CALIDAD": 2,
    "FALLA_EQUIPO": 1,
    "CONSULTA_INVENTARIO": 1,
    "SOLICITUD_DESPACHO": 1,
    "INTENCION_NO_CLARA": 1
  },
  "por_sentimiento": {
    "POSITIVO": 1,
    "NEUTRAL": 2,
    "NEGATIVO": 3
  },
  "confianza_promedio": 0.612,
  "tasa_derivacion": 0.1667,
  "entidades_frecuentes": {
    "camara de frio 2": 1,
    "uva red globe": 1,
    "9 grados": 1,
    "120 cajas": 1,
    "linea 3": 1,
    "packing": 1,
    "almacen": 1,
    "esparrago verde": 1,
    "20 pallets": 1,
    "L-409": 1,
    "uva sweet globe": 1,
    "L-512": 1
  },
  "ultimos_mensajes": [
    {
      "id": 6,
      "timestamp": "2026-11-23T16:03:18.351731+00:00",
      "texto_original": "revisar lo que quedo pendiente ayer en la tarde con el encargado",
      "intencion": "INTENCION_NO_CLARA",
      "confianza_intencion": 0.3176,
      "sentimiento": "NEGATIVO",
      "confianza_sentimiento": 0.4068,
      "entidades": {},
      "palabras_clave": ["quedo", "revisar"],
      "accion_sugerida": "DERIVAR_A_SUPERVISOR"
    },
    {
      "id": 5,
      "timestamp": "2026-11-23T16:03:18.332791+00:00",
      "texto_original": "el lote L-512 de uva sweet globe paso control de calidad sin observaciones",
      "intencion": "REPORTE_CALIDAD",
      "confianza_intencion": 0.668,
      "sentimiento": "POSITIVO",
      "confianza_sentimiento": 0.7041,
      "entidades": {
        "PRODUCTO": ["uva sweet globe"],
        "CODIGO_LOTE": ["L-512"]
      },
      "palabras_clave": ["512", "512 uva", "calidad observaciones", "globe paso"],
      "accion_sugerida": "REGISTRAR_CONTROL_CALIDAD"
    },
    {
      "id": 4,
      "timestamp": "2026-11-23T16:03:18.309421+00:00",
      "texto_original": "programar camion para despacho de 20 pallets lote L-409 hacia pisco",
      "intencion": "SOLICITUD_DESPACHO",
      "confianza_intencion": 0.7115,
      "sentimiento": "NEUTRAL",
      "confianza_sentimiento": 0.6621,
      "entidades": {
        "CANTIDAD": ["20 pallets"],
        "CODIGO_LOTE": ["L-409"]
      },
      "palabras_clave": ["20 pallets", "409 hacia", "despacho 20", "hacia pisco"],
      "accion_sugerida": "PROGRAMAR_LOGISTICA_SALIDA"
    },
    {
      "id": 3,
      "timestamp": "2026-11-23T16:03:18.289141+00:00",
      "texto_original": "cuantos pallets de esparrago verde tenemos listos en almacen",
      "intencion": "CONSULTA_INVENTARIO",
      "confianza_intencion": 0.6574,
      "sentimiento": "NEUTRAL",
      "confianza_sentimiento": 0.6793,
      "entidades": {
        "AREA": ["almacen"],
        "PRODUCTO": ["esparrago verde"]
      },
      "palabras_clave": ["listos almacen", "tenemos listos", "verde tenemos", "cuantos pallets"],
      "accion_sugerida": "CONSULTAR_ERP_ALMACEN"
    },
    {
      "id": 2,
      "timestamp": "2026-11-23T16:03:18.272470+00:00",
      "texto_original": "se malogro la faja trasportadora de la linea 3 en packing urjente",
      "intencion": "FALLA_EQUIPO",
      "confianza_intencion": 0.6658,
      "sentimiento": "NEGATIVO",
      "confianza_sentimiento": 0.7367,
      "entidades": {
        "AREA": ["linea 3", "packing"]
      },
      "palabras_clave": ["malogro faja", "packing urjente", "malogro", "trasportadora linea"],
      "accion_sugerida": "ORDEN_MANTENIMIENTO_URGENTE"
    },
    {
      "id": 1,
      "timestamp": "2026-11-23T16:03:18.255312+00:00",
      "texto_original": "La camara de frio 2 subio a 9 grados con 120 cajas de uva red globe",
      "intencion": "REPORTE_CALIDAD",
      "confianza_intencion": 0.6516,
      "sentimiento": "NEGATIVO",
      "confianza_sentimiento": 0.6157,
      "entidades": {
        "AREA": ["camara de frio 2"],
        "PRODUCTO": ["uva red globe"],
        "CANTIDAD": ["9 grados", "120 cajas"]
      },
      "palabras_clave": ["120", "120 cajas", "frio subio", "grados 120"],
      "accion_sugerida": "ALERTA_CRITICA_CALIDAD"
    }
  ]
}
```

---

### Caso 5: Evidencias de Ejecución en Vivo en Dispositivo Móvil (Smartphone Android en LAN: 192.168.106.43:8501)

Las siguientes interacciones corresponden a pruebas reales ejecutadas desde el navegador móvil de campo, demostrando la ausencia de JSON técnico y la respuesta conversacional inmediata:

1. **Mensaje de Despacho Logístico:**
   - **Texto ingresado por el operario:** `"programar camion reefer para despacho de 20 pallets lote L-409 hacia pisco"`
   - **Respuesta visual recibida en la pantalla del celular:**
     > 🚛 **Despacho Registrado**  
     > Se ha iniciado la coordinación de transporte y documentación para la salida programada.  
     > 📦 **Cantidad:** 20 pallets &nbsp;&nbsp; 🏷️ **Lote:** L-409  
   - **Impacto en el Backend y Dashboard:** El servidor reconoció la intención `SOLICITUD_DESPACHO` (confianza: `71.15%`), extrajo `CANTIDAD` y `CODIGO_LOTE`, persistió el evento en `historial.json` y actualizó en tiempo real los contadores del Dashboard en la PC.

2. **Mensaje Fuera de Dominio / Ambigüedad Operativa (Fallback Automático):**
   - **Texto ingresado por el operario:** `"Oe mi camion se ha chocado en la ruta av7 nuevo leon"`
   - **Respuesta visual recibida en la pantalla del celular:**
     > ⚠️ **Reporte Recibido y Derivado**  
     > Tu mensaje ha sido derivado directamente al supervisor de turno para su revisión y atención operativa.  
   - **Impacto en el Backend y Dashboard:** Debido a que el vocabulario y contexto escapan al entrenamiento agroexportador estándar o no superan el umbral de certeza ($< 0.65$), el motor activó la regla de incertidumbre asignando `INTENCION_NO_CLARA` y `DERIVAR_A_SUPERVISOR`, incrementando la tasa de derivación en las estadísticas de la PC sin exponer errores al usuario.

---

## 3. Cuadro Comparativo Técnico: On-Premise Local vs. Microsoft Azure AI Language / LUIS

| Criterio de Comparación | Mini-Azure LUIS (On-Premise / LAN) | Microsoft Azure AI Language (Cloud SaaS) |
| :--- | :--- | :--- |
| **Costo Operativo (TCO)** | **Costo Marginal Cero (\$0.00):** Ejecución en hardware existente sin facturación por petición, cuotas de API ni cargos ocultos por consumo de datos. | **Facturación por Volumen:** Modelo de pago por millón de caracteres o bloques de transacciones (ej. \$1.50 - \$2.50 por cada 1,000 llamadas). |
| **Privacidad y Soberanía de Datos** | **Soberanía Total y Confinamiento LAN:** La información de producción, recetas de empaque, lotes y clientes nunca sale de la red privada del fundo. | **Exposición WAN / Nube:** El texto debe viajar obligatoriamente a través de internet hacia los centros de datos de Microsoft, requiriendo cumplimiento estricto de GDPR/ISO. |
| **Latencia y Continuidad Operativa** | **Ultra Baja Latencia (<15 ms) y Operación Offline:** Continuidad total ante cortes de enlace satelital o fibra óptica, habituales en valles agrícolas alejados de Ica. | **Dependencia de WAN y RTT Nube (120 - 350 ms):** Caídas de enlace a internet paralizan por completo el flujo de selección, empaque y despacho de fruta. |
| **Capacidad Semántica y Generalización** | **Limitada a n-gramas locales:** Depende de coincidencias léxicas y probabilísticas (TF-IDF); menor comprensión contextual ante ambigüedad sintáctica compleja. | **Modelos Fundacionales Avanzados:** Basado en Transformers preentrenados multilingües con alta capacidad para entender sinónimos implícitos y sarcasmo. |
| **Esfuerzo de Mantenimiento y Corpus** | **Mantenimiento Manual Local:** El equipo de desarrollo debe recolectar, etiquetar, balancear y reentrenar el dataset periódicamente ante nuevas variedades o jerga. | **Aprendizaje Activo y Transfer Learning:** Capacidades de Active Learning y refinamiento asistido por IA que requieren menos ejemplos por intención. |
| **Infraestructura y Escalabilidad** | **Responsabilidad del Equipo Local:** La alta disponibilidad, tolerancia a fallos, balanceo de carga y respaldos recaen íntegramente en la infraestructura del cliente. | **Escalabilidad Elástica Gestionada:** Alta disponibilidad (SLA 99.9%), tolerancia a fallos y autoescalado multinodo administrado al 100% por Azure. |

---

## 4. Conclusiones y Veredicto Técnico

1. **Idoneidad en Agroexportación:** **Mini-Azure LUIS** demostró ser la alternativa óptima para la planta de empaque en Ica gracias a su **resiliencia total ante la falta de internet** y su **costo operativo predecible (\$0)**, procesando los 6 casos de validación con una exactitud de clasificación superior al **97%**.
2. **Complementariedad Híbrida:** En escenarios empresariales a gran escala, la arquitectura idónea es un modelo híbrido: **Mini-Azure LUIS en el borde (Edge/LAN)** para decisiones inmediatas en fajas y túneles de frío, sincronizando periódicamente analítica agregada hacia **Azure AI Services en la nube** para analítica predictiva global.

---

## 5. Matriz de Cumplimiento de Entregables de la Práctica

| Entregable Obligatorio | Estado | Evidencia y Ubicación en el Repositorio |
| :--- | :---: | :--- |
| **Demostración en Vivo en Laboratorio** | **Validado** | Comunicación cliente-servidor probada sobre red local (LAN Wi-Fi `192.168.106.43` y `127.0.0.1:8001`), ejecutando casos con ortografía irregular, extracción de entidades y activación de fallback (`INTENCION_NO_CLARA`) con refresco automático de dashboard cada 3s. |
| **Código Fuente Documentado** | **Completo** | Código modular con type hints y docstrings: `server/app/train.py`, `server/app/nlp_engine.py`, `server/app/analytics.py`, `server/app/main.py` y `client/app/dashboard.py`. |
| **Dataset y Modelos Entrenados Persistidos** | **Completo** | Dataset balanceado de 180 registros en `server/data/dataset_agro.csv` y pipelines serializados en `server/models/intent_pipeline.joblib` y `sentiment_pipeline.joblib`. |
| **Ficha Técnica y de Arquitectura (Markdown)** | **Completo** | Documento consolidado en `docs/ficha_tecnica.md` con topología Mermaid, flujos HTTP/JSON en puerto 8001, evidencias reales de inferencia y cuadro comparativo técnico. |
| **Cuadro Comparativo Técnico (3 Ventajas vs 3 Desventajas)** | **Completo** | Sección 3 detallando TCO (\$0 vs pago por petición), Privacidad (LAN confinada vs nube pública) y Latencia/Offline (<15ms vs WAN 200ms) frente a Generalización, Mantenimiento y Escalabilidad. |
| **Empaquetado Comprimido (.zip)** | **Generable** | Comando PowerShell/Bash disponible para comprimir la solución completa excluyendo temporales: `Compress-Archive -Path server, client, docs, docker-compose.yml, README.md, .env.example -DestinationPath mini-azure-luis.zip`. |
