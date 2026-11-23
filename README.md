# Mini-Azure LUIS 🌾

Motor On-Premise de Comprensión de Lenguaje Natural (NLP) y Analítica Operativa para la Industria Agroexportadora en Red de Área Local (LAN).

Desarrollado para emular la funcionalidad de **Azure AI Language / LUIS** de forma 100% local, privada y desacoplada, especializado en la gestión de **uva de mesa** (Red Globe, Sweet Globe, Autumn Crisp, uva sin pepa) y **espárragos** (verde y blanco) en la región de Ica, Perú.

---

## 🏛️ Arquitectura del Sistema

El proyecto está diseñado bajo una arquitectura de microservicios contenedorizados desacoplados mediante **Docker Compose**:

```text
mini-azure-luis/
├── .env                        # Variables de entorno locales reales (ignorado en Git)
├── .env.example                # Plantilla documentada de variables de entorno
├── .gitignore                  # Exclusiones de Git (entorno, modelos temporales, caches)
├── docker-compose.yml          # Orquestación de servicios + reglas develop.watch
├── README.md                   # Documentación de funcionamiento y contenido del proyecto
├── docs/
│   └── ficha_tecnica.md        # Entregable: Topología LAN, evidencias y cuadro comparativo
├── server/                     # [Servicio Backend] Motor NLP + API REST FastAPI (Puerto 8001)
│   ├── Dockerfile              # Imagen Python 3.11-slim optimizada
│   ├── requirements.txt        # Dependencias: FastAPI, Uvicorn, Scikit-Learn, Pandas, etc.
│   ├── data/
│   │   ├── dataset_agro.csv    # Corpus de 180 registros balanceados en español
│   │   └── historial.json      # Almacén persistente con control de concurrencia
│   ├── models/                 # Artefactos entrenados (.joblib)
│   └── app/
│       ├── __init__.py
│       ├── config.py           # Resolución híbrida de variables de entorno y rutas
│       ├── train.py            # Pipeline TF-IDF + LogisticRegression
│       ├── nlp_engine.py       # Motor AgroNLPEngine: inferencia, entidades y fallback
│       ├── analytics.py        # Gestor de analítica concurrente y cálculo de KPIs
│       └── main.py             # Endpoints FastAPI con ciclo de vida lifespan y CORS
└── client/                     # [Servicio Frontend] Cliente LAN + Dashboard Streamlit (Puerto 8501)
    ├── Dockerfile              # Imagen Python 3.11-slim con PYTHONPATH configurado
    ├── requirements.txt        # Dependencias: Streamlit, Requests, Pandas, Dotenv
    └── app/
        ├── __init__.py
        ├── config.py           # Construcción dinámica de BASE_URL con resolución interna
        └── dashboard.py        # Interfaz web (envío individual, lote y KPIs en vivo)
```

---

## 🧠 Motor de Inteligencia Artificial (NLP Local)

El backend de inferencia combina procesamiento de lenguaje natural estadístico con extracción híbrida de entidades de dominio:

### 1. Clasificación de Intenciones y Sentimientos
- **Vectorización:** `TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True, strip_accents='unicode', stop_words=SPANISH_STOPWORDS)`.
- **Clasificadores:** `LogisticRegression(C=2.0, class_weight='balanced', max_iter=1000)` con probabilidades calibradas mediante `predict_proba()`.
- **Intenciones Obligatorias:**
  - `REPORTE_CALIDAD`: Problemas de temperatura en cámaras, humedad relativa, *Botrytis* / pudrición gris, deshidratación de raquis o calibre fuera de norma.
  - `FALLA_EQUIPO`: Averías en túneles de prefrío, fajas transportadoras, balanzas electrónicas, etiquetadoras térmicas y lectores láser.
  - `CONSULTA_INVENTARIO`: Disponibilidad de pallets armados, jabas cosecheras, cajas de cartón, bolsas generadoras de $SO_2$ o stock en cámara.
  - `SOLICITUD_DESPACHO`: Programación de reefers, guías de remisión, certificados fitosanitarios SENASA y salidas a puerto (Callao/Pisco).
- **Sentimientos:** `POSITIVO`, `NEUTRAL`, `NEGATIVO`.

### 2. Extracción de Entidades Normalizadas
El motor extrae y estandariza 4 familias de entidades agroexportadoras:
- **`AREA`:** `camara de frio N`, `tunel de prefrio N`, `linea N`, `muelle N`, `packing`, `almacen`, `recepcion`, `bodega`.
- **`PRODUCTO`:** Normalización automática de variantes ortográficas (`uva red globe`, `uva sweet globe`, `uva autumn crisp`, `uva sin pepa`, `esparrago verde`, `esparrago blanco`).
- **`CANTIDAD`:** Magnitudes y unidades operativas (`120 cajas`, `20 pallets`, `50 jabas`, `9 grados`, `8 °c`, `15 parihuelas`).
- **`CODIGO_LOTE`:** Códigos de trazabilidad interna (`L-512`, `LT-409`, `LOTE-123`).

### 3. Regla de Fallback y Decisión Operativa
Si la confianza de la intención es inferior al umbral configurado (`CONFIDENCE_THRESHOLD = 0.65`) o el texto contiene menos de dos palabras válidas:
- **Intención:** `INTENCION_NO_CLARA`
- **Acción Sugerida:** `DERIVAR_A_SUPERVISOR`

En caso afirmativo, la intención y el sentimiento se mapean automáticamente a la acción operativa correspondiente (`ALERTA_CRITICA_CALIDAD`, `ORDEN_MANTENIMIENTO_URGENTE`, `CONSULTAR_ERP_ALMACEN` o `PROGRAMAR_LOGISTICA_SALIDA`).

---

## 🌐 Endpoints de la API REST (FastAPI - Puerto 8001)

| Método | Endpoint | Descripción |
| :--- | :--- | :--- |
| `GET` | `/health` o `/` | Healthcheck del servicio, versión del motor y umbral de confianza activo. |
| `POST` | `/nlp/analizar-texto` | Clasifica sentimiento, confianza y extrae las 4 palabras clave TF-IDF principales. |
| `POST` | `/nlp/entender-comando` | Clasifica intención, sentimiento, entidades, acción sugerida y persiste en bitácora. |
| `GET` | `/nlp/estadisticas` | Retorna los KPIs acumulados: total, por intención, por sentimiento, confianza promedio, tasa de derivación, ranking de entidades y últimos 15 mensajes. |
| `POST` | `/nlp/estadisticas/reiniciar` | Limpia el archivo de persistencia `historial.json` y restablece los KPIs a cero. |

---

## 🖥️ Cliente y Dashboard Streamlit (Puerto 8501)

La interfaz web ofrece:
1. **Control de Conexión LAN (Sidebar):** Campo para ingresar la IP del servidor en el laboratorio (con resolución interna automática a `http://nlp-server:8001` en pruebas locales con Docker).
2. **Indicador de Conectividad:** Semáforo en vivo conectado a `/health`.
3. **Pestaña de Envío Individual:** Caja de texto con ejemplos rápidos para evaluar mensajes libres y visualizar tarjetas con badges de criticidad, entidades y JSON de respuesta.
4. **Pestaña Simulador de Lote:** Batería de 8 mensajes predefinidos con barra de progreso para poblar métricas en segundos.
5. **Panel de Métricas en Tiempo Real:** 4 tarjetas KPI, 2 gráficos de barras (Intención y Sentimiento), ranking de entidades más reportadas y tabla dinámica con la bitácora reciente.

---

## 🚀 Guía de Despliegue y Ejecución

### Requisitos Previos
- Docker Desktop en Windows 11 (o Linux/macOS) con soporte para Docker Compose v2.
- Git.

### Opción 1: Desarrollo en una Sola PC (Localhost)
Para levantar ambos contenedores con sincronización en caliente:
```bash
docker compose up -d
```
O con recarga automática activa:
```bash
docker compose up --watch
```
- **API FastAPI:** `http://localhost:8001` (Documentación Swagger en `http://localhost:8001/docs`)
- **Dashboard Streamlit:** `http://localhost:8501`

---

### Opción 2: Demostración en Red Local LAN (Evaluación en Laboratorio)

#### 1. Configuración en la PC Servidor (Integrante A)
1. Abrir PowerShell como **Administrador** y habilitar el puerto 8001 en el Firewall de Windows:
   ```powershell
   New-NetFirewallRule -DisplayName "Mini-Azure-LUIS-API-8001" -Direction Inbound -LocalPort 8001 -Protocol TCP -Action Allow
   ```
2. Obtener la IPv4 privada ejecutando `ipconfig` (ejemplo: `192.168.1.45`).
3. Iniciar únicamente el backend:
   ```bash
   docker compose up nlp-server -d
   ```

#### 2. Configuración en la PC Cliente (Integrante B)
1. En el archivo `.env` de la PC Cliente (o directamente desde la barra lateral de Streamlit):
   ```env
   TARGET_SERVER_IP=192.168.1.45
   SERVER_PORT=8001
   ```
2. Iniciar el cliente:
   ```bash
   docker compose up nlp-client -d
   ```
3. Abrir en el navegador `http://localhost:8501` y validar que el semáforo muestre `🟢 Servidor Conectado`.

---

## 🔄 Reentrenamiento del Modelo

Si editas o amplías el corpus en `server/data/dataset_agro.csv`, puedes reentrenar los modelos `.joblib` al instante sin reconstruir la imagen:

- **Desde el host:**
  ```bash
  python server/app/train.py
  ```
- **Dentro del contenedor Docker:**
  ```bash
  docker compose exec nlp-server python app/train.py
  ```
