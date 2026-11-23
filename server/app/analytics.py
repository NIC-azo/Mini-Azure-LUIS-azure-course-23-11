import json
import os
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List

# Asegurar importación de app.config
current_dir = Path(__file__).resolve().parent
server_dir = current_dir.parent
if str(server_dir) not in sys.path:
    sys.path.insert(0, str(server_dir))

from app.config import STATS_FILE

_lock = threading.Lock()


def _ensure_file():
    """Asegura que el archivo de persistencia exista y tenga la estructura base."""
    os.makedirs(os.path.dirname(os.path.abspath(STATS_FILE)), exist_ok=True)
    if not os.path.exists(STATS_FILE) or os.path.getsize(STATS_FILE) == 0:
        with open(STATS_FILE, "w", encoding="utf-8") as f:
            json.dump({"registros": []}, f, indent=2, ensure_ascii=False)


def _read_data() -> Dict[str, Any]:
    """Lee el archivo JSON de forma segura."""
    _ensure_file()
    try:
        with open(STATS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if not isinstance(data, dict) or "registros" not in data:
                return {"registros": []}
            return data
    except Exception:
        return {"registros": []}


def _write_data(data: Dict[str, Any]):
    """Escribe los datos al archivo JSON de forma atómica."""
    _ensure_file()
    temp_path = f"{STATS_FILE}.tmp"
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    # Reemplazo atómico en disco
    if os.name == "nt" and os.path.exists(STATS_FILE):
        os.replace(temp_path, STATS_FILE)
    else:
        os.replace(temp_path, STATS_FILE)


def registrar_evento(evento: Dict[str, Any]) -> Dict[str, Any]:
    """
    Guarda un mensaje procesado en el historial acumulado de forma segura y concurrente.
    """
    with _lock:
        data = _read_data()
        registros = data.get("registros", [])

        # Filtrar entidades vacías para un almacenamiento limpio
        entidades_raw = evento.get("entidades", {})
        entidades_limpias = {k: v for k, v in entidades_raw.items() if v}

        record = {
            "id": len(registros) + 1,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "texto_original": evento.get("texto_original") or evento.get("texto", ""),
            "intencion": evento.get("intencion", "INTENCION_NO_CLARA"),
            "confianza_intencion": float(evento.get("confianza_intencion", 0.0)),
            "sentimiento": evento.get("sentimiento", "NEUTRAL"),
            "confianza_sentimiento": float(evento.get("confianza_sentimiento", 0.0)),
            "entidades": entidades_limpias,
            "palabras_clave": evento.get("palabras_clave", []),
            "accion_sugerida": evento.get("accion_sugerida", "DERIVAR_A_SUPERVISOR"),
        }

        registros.append(record)
        data["registros"] = registros
        _write_data(data)
        return record


def obtener_estadisticas() -> Dict[str, Any]:
    """
    Calcula y devuelve las métricas y KPIs acumulados en tiempo real.
    """
    with _lock:
        data = _read_data()
        registros: List[Dict[str, Any]] = data.get("registros", [])

        total = len(registros)

        # 1. Distribución por Intención
        por_intencion = {
            "REPORTE_CALIDAD": 0,
            "FALLA_EQUIPO": 0,
            "CONSULTA_INVENTARIO": 0,
            "SOLICITUD_DESPACHO": 0,
            "INTENCION_NO_CLARA": 0,
        }
        for r in registros:
            intent = r.get("intencion", "INTENCION_NO_CLARA")
            por_intencion[intent] = por_intencion.get(intent, 0) + 1

        # 2. Distribución por Sentimiento
        por_sentimiento = {
            "POSITIVO": 0,
            "NEUTRAL": 0,
            "NEGATIVO": 0,
        }
        for r in registros:
            sent = r.get("sentimiento", "NEUTRAL")
            por_sentimiento[sent] = por_sentimiento.get(sent, 0) + 1

        # 3. Confianza Promedio y Tasa de Derivación
        if total > 0:
            suma_confianza = sum(float(r.get("confianza_intencion", 0.0)) for r in registros)
            confianza_promedio = round(suma_confianza / total, 4)
            derivados = por_intencion.get("INTENCION_NO_CLARA", 0)
            tasa_derivacion = round(derivados / total, 4)
        else:
            confianza_promedio = 0.0
            tasa_derivacion = 0.0

        # 4. Entidades Frecuentes (conteo consolidado y ordenado)
        freq_entidades: Dict[str, int] = {}
        for r in registros:
            ents = r.get("entidades", {})
            for categoria, valores in ents.items():
                if isinstance(valores, list):
                    for v in valores:
                        v_str = str(v).strip()
                        if v_str:
                            freq_entidades[v_str] = freq_entidades.get(v_str, 0) + 1
                elif isinstance(valores, str) and valores.strip():
                    freq_entidades[valores] = freq_entidades.get(valores, 0) + 1

        # Ordenar de mayor a menor frecuencia
        entidades_frecuentes = dict(
            sorted(freq_entidades.items(), key=lambda item: item[1], reverse=True)
        )

        # 5. Últimos 15 mensajes (del más reciente al más antiguo)
        ultimos = registros[-15:][::-1]

        return {
            "total_mensajes": total,
            "por_intencion": por_intencion,
            "por_sentimiento": por_sentimiento,
            "confianza_promedio": confianza_promedio,
            "tasa_derivacion": tasa_derivacion,
            "entidades_frecuentes": entidades_frecuentes,
            "ultimos_mensajes": ultimos,
        }


def reiniciar_estadisticas() -> Dict[str, Any]:
    """
    Restaura el archivo historial.json a cero registros y devuelve la confirmación.
    """
    with _lock:
        data = {"registros": []}
        _write_data(data)
        return {
            "mensaje": "Estadísticas reiniciadas correctamente",
            "total_mensajes": 0,
        }
