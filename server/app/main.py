import os
import sys
from pathlib import Path
from typing import Optional, Dict, Any, List
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Asegurar importación de módulos locales
current_dir = Path(__file__).resolve().parent
server_dir = current_dir.parent
if str(server_dir) not in sys.path:
    sys.path.insert(0, str(server_dir))

from app.config import SERVER_HOST, SERVER_PORT, CONFIDENCE_THRESHOLD
from app.nlp_engine import AgroNLPEngine
from app.analytics import (
    registrar_evento,
    obtener_estadisticas,
    reiniciar_estadisticas,
)

# Variable global para el motor NLP cargado en memoria
nlp_engine: Optional[AgroNLPEngine] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Ciclo de vida de FastAPI: Carga los modelos entrenados al iniciar."""
    global nlp_engine
    print("🌾 Cargando modelos de inferencia NLP en memoria...")
    try:
        nlp_engine = AgroNLPEngine()
        print("✅ Motor AgroNLPEngine cargado y listo para recibir peticiones.")
    except Exception as e:
        print(f"⚠️ Advertencia al inicializar AgroNLPEngine: {e}")
        print("Asegúrese de haber ejecutado 'python app/train.py' previamente.")
    yield
    print("Cerrando servicio NLP...")


app = FastAPI(
    title="Mini-Azure LUIS API",
    description="Motor de Inferencia de Lenguaje Natural On-Premise para Agroexportación (Ica)",
    version="1.0.0",
    lifespan=lifespan,
)

# Habilitar CORS para permitir consumo desde el Dashboard Streamlit o cualquier cliente LAN
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -------------------------------------------------------------
# Esquemas Pydantic
# -------------------------------------------------------------
class TextoRequest(BaseModel):
    texto: str = Field(
        ...,
        description="Mensaje u orden operativa en lenguaje natural",
        examples=["La camara de frio 2 subio a 9 grados con 120 cajas de uva red globe"],
        min_length=1,
    )


class AnalisisTextoResponse(BaseModel):
    texto_original: str
    sentimiento: str
    confianza_sentimiento: float
    palabras_clave: List[str]


class EntenderComandoResponse(BaseModel):
    texto_original: str
    intencion: str
    confianza_intencion: float
    sentimiento: str
    confianza_sentimiento: float
    entidades: Dict[str, List[str]]
    palabras_clave: List[str]
    accion_sugerida: str


# -------------------------------------------------------------
# Endpoints de la API
# -------------------------------------------------------------
@app.get("/", tags=["Salud"])
@app.get("/health", tags=["Salud"])
def health_check():
    """Verifica la disponibilidad del servicio y los parámetros activos."""
    return {
        "status": "online",
        "servicio": "Mini-Azure LUIS NLP Engine",
        "version": "1.0.0",
        "puerto": SERVER_PORT,
        "host": SERVER_HOST,
        "umbral_confianza": CONFIDENCE_THRESHOLD,
        "motor_cargado": nlp_engine is not None,
    }


@app.post(
    "/nlp/analizar-texto",
    response_model=AnalisisTextoResponse,
    tags=["NLP"],
    summary="Análisis de Sentimiento y Text Analytics",
)
def analizar_texto_endpoint(req: TextoRequest):
    """
    Analiza un texto en español identificando su sentimiento predominante,
    nivel de confianza y las palabras clave con mayor relevancia TF-IDF.
    """
    if nlp_engine is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Motor NLP no disponible. Entrene los modelos con 'train.py'.",
        )

    res = nlp_engine.analizar_texto(req.texto)
    return {
        "texto_original": req.texto,
        "sentimiento": res["sentimiento"],
        "confianza_sentimiento": res["confianza_sentimiento"],
        "palabras_clave": res["palabras_clave"],
    }


@app.post(
    "/nlp/entender-comando",
    response_model=EntenderComandoResponse,
    tags=["NLP"],
    summary="Comprensión de Comandos e Inferencia Operativa",
)
def entender_comando_endpoint(req: TextoRequest):
    """
    Identifica la intención operativa del mensaje, sentimiento, extrae entidades
    del dominio agroexportador y sugiere una acción operativa.
    Registra el evento automáticamente en la persistencia analítica.
    """
    if nlp_engine is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Motor NLP no disponible. Entrene los modelos con 'train.py'.",
        )

    res = nlp_engine.entender_comando(req.texto, umbral_confianza=CONFIDENCE_THRESHOLD)

    # Filtrar categorías vacías de entidades para mantener un JSON limpio y legible
    entidades_limpias = {k: v for k, v in res.get("entidades", {}).items() if v}

    evento = {
        "texto_original": req.texto,
        "intencion": res["intencion"],
        "confianza_intencion": res["confianza_intencion"],
        "sentimiento": res["sentimiento"],
        "confianza_sentimiento": res["confianza_sentimiento"],
        "entidades": entidades_limpias,
        "palabras_clave": res.get("palabras_clave", []),
        "accion_sugerida": res["accion_sugerida"],
    }

    # Registrar el evento en el almacén persistente con control de concurrencia
    registrar_evento(evento)

    return evento


@app.get(
    "/nlp/estadisticas",
    tags=["Analítica"],
    summary="Resumen de Métricas y KPIs de la Operación",
)
def obtener_estadisticas_endpoint():
    """
    Devuelve los KPIs acumulados: total de mensajes, distribución por intención,
    sentimiento, confianza promedio, tasa de derivación, entidades frecuentes y bitácora.
    """
    return obtener_estadisticas()


@app.post(
    "/nlp/estadisticas/reiniciar",
    tags=["Analítica"],
    summary="Reinicia el Historial y Métricas Acumuladas",
)
def reiniciar_estadisticas_endpoint():
    """
    Restablece a cero todos los contadores y limpia el archivo historial.json.
    """
    return reiniciar_estadisticas()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host=SERVER_HOST, port=SERVER_PORT, reload=True)
