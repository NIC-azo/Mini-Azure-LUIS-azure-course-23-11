import os
import re
import sys
import unicodedata
from pathlib import Path
from typing import Dict, List, Any, Optional
import joblib
import numpy as np

# Asegurar importación de app.config
current_dir = Path(__file__).resolve().parent
server_dir = current_dir.parent
if str(server_dir) not in sys.path:
    sys.path.insert(0, str(server_dir))

from app.config import MODEL_DIR, CONFIDENCE_THRESHOLD


def strip_accents(text: str) -> str:
    """Normaliza texto eliminando tildes y diacríticos conservando caracteres alfanuméricos."""
    text = unicodedata.normalize("NFD", text)
    return "".join(c for c in text if unicodedata.category(c) != "Mn")


class AgroNLPEngine:
    """
    Motor NLP Local para el dominio agroexportador.
    Combina pipelines TF-IDF + LogisticRegression con extracción híbrida de entidades (RegEx + Normalización).
    """

    def __init__(self, model_dir: Optional[str] = None):
        self.model_dir = model_dir or MODEL_DIR
        self.intent_path = os.path.join(self.model_dir, "intent_pipeline.joblib")
        self.sentiment_path = os.path.join(self.model_dir, "sentiment_pipeline.joblib")

        self.intent_pipeline = None
        self.sentiment_pipeline = None
        self._load_models()

    def _load_models(self):
        """Carga los modelos .joblib entrenados."""
        if not os.path.exists(self.intent_path) or not os.path.exists(self.sentiment_path):
            raise FileNotFoundError(
                f"Modelos no encontrados en '{self.model_dir}'. "
                f"Por favor ejecute primero 'python app/train.py'."
            )
        self.intent_pipeline = joblib.load(self.intent_path)
        self.sentiment_pipeline = joblib.load(self.sentiment_path)

    # -------------------------------------------------------------
    # Extracción de Entidades
    # -------------------------------------------------------------
    def extraer_entidades(self, texto: str) -> Dict[str, List[str]]:
        """
        Extrae entidades nombradas de dominio (AREA, PRODUCTO, CANTIDAD, CODIGO_LOTE).
        """
        texto_norm = strip_accents(texto.lower())
        entidades: Dict[str, List[str]] = {
            "AREA": [],
            "PRODUCTO": [],
            "CANTIDAD": [],
            "CODIGO_LOTE": [],
        }

        # 1. CODIGO_LOTE (ej. L-512, LT-409, LOTE-123, LT 89)
        lote_pattern = re.compile(r"\b(?:lote|lt|l)[-\s]?\d{2,6}\b", re.IGNORECASE)
        for m in lote_pattern.finditer(texto):
            clean_lote = re.sub(r"\s+", "-", m.group().upper())
            if clean_lote not in entidades["CODIGO_LOTE"]:
                entidades["CODIGO_LOTE"].append(clean_lote)

        # 2. CANTIDAD (ej. 120 cajas, 20 pallets, 9 grados, 8 °c, 50 jabas, 15 parihuelas)
        cant_pattern = re.compile(
            r"\b\d+(?:[.,]\d+)?\s*(?:cajas|jabas|pallets|palets|parihuelas|kg|kilos|toneladas|grados|°\s*c|%|por ciento)\b",
            re.IGNORECASE,
        )
        for m in cant_pattern.finditer(texto):
            clean_cant = re.sub(r"\s+", " ", m.group().lower().strip())
            if clean_cant not in entidades["CANTIDAD"]:
                entidades["CANTIDAD"].append(clean_cant)

        # 3. AREA (ej. camara de frio 2, tunel 1, linea 3, muelle 1, packing, almacen, recepcion)
        area_patterns = [
            r"\bcamara(?:\s+de\s+frio)?\s+\d+\b",
            r"\btunel(?:\s+de\s+prefrio)?\s+\d+\b",
            r"\blinea\s+\d+\b",
            r"\bmuelle\s+\d+\b",
            r"\b(?:packing|empaque|almacen(?:\s+general|\s+\d+)?|recepcion|sala\s+de\s+maquinas|bodega(?:\s+central)?)\b",
        ]
        for pat in area_patterns:
            for m in re.finditer(pat, texto_norm):
                area_val = m.group().strip()
                if area_val not in entidades["AREA"]:
                    entidades["AREA"].append(area_val)

        # 4. PRODUCTO (variedades de uva de mesa y espárrago)
        producto_map = [
            (r"\buva\s+red\s+globe\b", "uva red globe"),
            (r"\buva\s+sweet\s+globe\b", "uva sweet globe"),
            (r"\buva\s+autumn\s+crisp\b", "uva autumn crisp"),
            (r"\buva\s+(?:sin\s+pepa|seedless)\b", "uva sin pepa"),
            (r"\besparrago\s+verde\b", "esparrago verde"),
            (r"\besparrago\s+blanco\b", "esparrago blanco"),
            (r"\buva(?:\s+de\s+mesa)?\b", "uva"),
            (r"\besparrago\b", "esparrago"),
        ]
        for pat, canonical in producto_map:
            if re.search(pat, texto_norm):
                # Evitar agregar el genérico si ya se identificó la variedad específica
                if canonical == "uva" and any("uva " in p for p in entidades["PRODUCTO"]):
                    continue
                if canonical == "esparrago" and any("esparrago " in p for p in entidades["PRODUCTO"]):
                    continue
                if canonical not in entidades["PRODUCTO"]:
                    entidades["PRODUCTO"].append(canonical)

        return entidades

    # -------------------------------------------------------------
    # Extracción de Palabras Clave (TF-IDF Top-K)
    # -------------------------------------------------------------
    def extraer_palabras_clave(self, texto: str, top_k: int = 4) -> List[str]:
        """
        Extrae los términos con mayor ponderación TF-IDF presentes en el texto.
        """
        if not self.intent_pipeline:
            return []

        tfidf: Any = self.intent_pipeline.named_steps.get("tfidf")
        if not tfidf:
            return []

        tfidf_vec = tfidf.transform([texto])
        feature_names = np.array(tfidf.get_feature_names_out())
        scores = tfidf_vec.toarray()[0]

        # Índices con score mayor a 0
        nonzero_indices = np.where(scores > 0)[0]
        if len(nonzero_indices) == 0:
            # Fallback simple a palabras significativas (>= 4 letras)
            tokens = [w for w in re.findall(r"\b[a-zA-ZáéíóúñÁÉÍÓÚÑ]{4,}\b", texto.lower())]
            return list(dict.fromkeys(tokens))[:top_k]

        sorted_indices = nonzero_indices[np.argsort(-scores[nonzero_indices])]
        top_terms = [str(feature_names[idx]) for idx in sorted_indices[:top_k]]
        return top_terms

    # -------------------------------------------------------------
    # Análisis de Sentimiento y Text Analytics
    # -------------------------------------------------------------
    def analizar_texto(self, texto: str) -> Dict[str, Any]:
        """
        Clasifica el sentimiento y extrae palabras clave para analítica de texto.
        """
        if not texto or not texto.strip():
            return {
                "texto": texto,
                "sentimiento": "NEUTRAL",
                "confianza_sentimiento": 0.0,
                "palabras_clave": [],
            }

        probas = self.sentiment_pipeline.predict_proba([texto])[0]
        classes = self.sentiment_pipeline.classes_
        best_idx = int(np.argmax(probas))
        sentimiento = str(classes[best_idx])
        confianza = float(probas[best_idx])
        palabras_clave = self.extraer_palabras_clave(texto, top_k=4)

        return {
            "texto": texto,
            "sentimiento": sentimiento,
            "confianza_sentimiento": round(confianza, 4),
            "palabras_clave": palabras_clave,
        }

    # -------------------------------------------------------------
    # Inferencia de Intención y Decisión Operativa
    # -------------------------------------------------------------
    def entender_comando(
        self, texto: str, umbral_confianza: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Evalúa el texto completo devolviendo intención, confianza, sentimiento,
        entidades extraídas y la acción operativa sugerida aplicando fallback.
        """
        threshold = umbral_confianza if umbral_confianza is not None else CONFIDENCE_THRESHOLD

        if not texto or not texto.strip():
            return {
                "texto": texto,
                "intencion": "INTENCION_NO_CLARA",
                "confianza_intencion": 0.0,
                "sentimiento": "NEUTRAL",
                "confianza_sentimiento": 0.0,
                "entidades": {"AREA": [], "PRODUCTO": [], "CANTIDAD": [], "CODIGO_LOTE": []},
                "palabras_clave": [],
                "accion_sugerida": "DERIVAR_A_SUPERVISOR",
            }

        # 1. Análisis de Sentimiento y Palabras Clave
        sent_info = self.analizar_texto(texto)
        sentimiento = sent_info["sentimiento"]
        confianza_sentimiento = sent_info["confianza_sentimiento"]
        palabras_clave = sent_info["palabras_clave"]

        # 2. Inferencia de Intención con Scikit-Learn
        intent_probas = self.intent_pipeline.predict_proba([texto])[0]
        intent_classes = self.intent_pipeline.classes_
        best_intent_idx = int(np.argmax(intent_probas))
        raw_intent = str(intent_classes[best_intent_idx])
        confianza_intencion = float(intent_probas[best_intent_idx])

        # 3. Extracción de Entidades de Dominio
        entidades = self.extraer_entidades(texto)

        # 4. Validación de Umbral y Fallback (INTENCION_NO_CLARA)
        palabras_validas = re.findall(r"\b[a-zA-ZáéíóúñÁÉÍÓÚÑ]{2,}\b", texto)
        es_ambiguo = (confianza_intencion < threshold) or (len(palabras_validas) < 2)

        if es_ambiguo:
            intencion_final = "INTENCION_NO_CLARA"
            accion_sugerida = "DERIVAR_A_SUPERVISOR"
        else:
            intencion_final = raw_intent
            # Mapeo a Acción Sugerida según Intención y Sentimiento
            if intencion_final == "REPORTE_CALIDAD":
                if sentimiento == "NEGATIVO":
                    accion_sugerida = "ALERTA_CRITICA_CALIDAD"
                else:
                    accion_sugerida = "REGISTRAR_CONTROL_CALIDAD"
            elif intencion_final == "FALLA_EQUIPO":
                accion_sugerida = "ORDEN_MANTENIMIENTO_URGENTE"
            elif intencion_final == "CONSULTA_INVENTARIO":
                accion_sugerida = "CONSULTAR_ERP_ALMACEN"
            elif intencion_final == "SOLICITUD_DESPACHO":
                accion_sugerida = "PROGRAMAR_LOGISTICA_SALIDA"
            else:
                accion_sugerida = "DERIVAR_A_SUPERVISOR"

        return {
            "texto": texto,
            "intencion": intencion_final,
            "confianza_intencion": round(confianza_intencion, 4),
            "sentimiento": sentimiento,
            "confianza_sentimiento": round(confianza_sentimiento, 4),
            "entidades": entidades,
            "palabras_clave": palabras_clave,
            "accion_sugerida": accion_sugerida,
        }
