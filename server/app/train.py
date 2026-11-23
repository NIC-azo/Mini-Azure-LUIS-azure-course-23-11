import os
import sys
from pathlib import Path
import joblib
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.metrics import accuracy_score, classification_report

# Asegurar importación de app.config independientemente del directorio de ejecución
current_dir = Path(__file__).resolve().parent
server_dir = current_dir.parent
if str(server_dir) not in sys.path:
    sys.path.insert(0, str(server_dir))

from app.config import DATASET_PATH, MODEL_DIR

# Lista de palabras vacías (stopwords) en español para filtrar ruido léxico común
SPANISH_STOPWORDS = [
    "de", "la", "que", "el", "en", "y", "a", "los", "del", "se", "las", "por", "un", "para", "con", "no", "una",
    "su", "al", "lo", "como", "mas", "pero", "sus", "le", "ya", "o", "este", "si", "porque", "esta", "son", "entre",
    "cuando", "muy", "sin", "sobre", "tambien", "me", "hasta", "hay", "donde", "quien", "desde", "todo", "nos",
    "durante", "todos", "uno", "les", "ni", "contra", "otros", "ese", "eso", "ante", "ellos", "e", "esto", "mi",
    "antes", "algunos", "unos", "otro", "otras", "otra", "tanto", "esa", "estos", "mucho", "quienes", "nada",
    "muchos", "cual", "sea", "poco", "ella", "estas", "estaba", "estamos", "algunas", "algo", "nosotros"
]


def build_pipeline(c_param: float = 2.0) -> Pipeline:
    """Construye un pipeline Scikit-Learn TF-IDF + LogisticRegression calibrado."""
    return Pipeline([
        (
            "tfidf",
            TfidfVectorizer(
                ngram_range=(1, 2),
                sublinear_tf=True,
                strip_accents="unicode",
                lowercase=True,
                stop_words=SPANISH_STOPWORDS,
            ),
        ),
        (
            "clf",
            LogisticRegression(
                C=c_param,
                class_weight="balanced",
                max_iter=1000,
                random_state=42,
            ),
        ),
    ])


def train_models():
    print("=" * 60)
    print("🌾 INICIANDO ENTRENAMIENTO - MINI-AZURE LUIS")
    print("=" * 60)
    print(f"Ruta del Dataset: {DATASET_PATH}")
    print(f"Directorio de Modelos: {MODEL_DIR}")

    if not os.path.exists(DATASET_PATH):
        raise FileNotFoundError(f"No se encontró el dataset en: {DATASET_PATH}")

    os.makedirs(MODEL_DIR, exist_ok=True)
    df = pd.read_csv(DATASET_PATH)

    print(f"\nTotal de registros cargados: {len(df)}")
    print("\nDistribución por Intención:")
    print(df["intencion"].value_counts())
    print("\nDistribución por Sentimiento:")
    print(df["sentimiento"].value_counts())

    X = df["texto"].astype(str)
    y_intent = df["intencion"]
    y_sentiment = df["sentimiento"]

    # -------------------------------------------------------------
    # 1. Entrenamiento y Validación del Modelo de Intenciones
    # -------------------------------------------------------------
    print("\n" + "-" * 50)
    print("🎯 [1/2] Entrenando Clasificador de Intenciones...")
    print("-" * 50)

    X_train_i, X_val_i, y_train_i, y_val_i = train_test_split(
        X, y_intent, test_size=0.2, random_state=42, stratify=y_intent
    )

    intent_pipeline = build_pipeline(c_param=2.0)
    intent_pipeline.fit(X_train_i, y_train_i)

    y_pred_i = intent_pipeline.predict(X_val_i)
    acc_i = accuracy_score(y_val_i, y_pred_i)
    print(f"Exactitud (Accuracy) de Intención en Validación: {acc_i * 100:.2f}%\n")
    print("Reporte de Clasificación (Intención):")
    print(classification_report(y_val_i, y_pred_i, digits=4))

    # Reentrenar sobre todo el dataset para máxima cobertura en producción
    intent_pipeline.fit(X, y_intent)
    intent_path = os.path.join(MODEL_DIR, "intent_pipeline.joblib")
    joblib.dump(intent_pipeline, intent_path)
    print(f"-> Modelo de Intenciones guardado en: {intent_path}")

    # -------------------------------------------------------------
    # 2. Entrenamiento y Validación del Modelo de Sentimientos
    # -------------------------------------------------------------
    print("\n" + "-" * 50)
    print("😊 [2/2] Entrenando Clasificador de Sentimientos...")
    print("-" * 50)

    X_train_s, X_val_s, y_train_s, y_val_s = train_test_split(
        X, y_sentiment, test_size=0.2, random_state=42, stratify=y_sentiment
    )

    sentiment_pipeline = build_pipeline(c_param=2.0)
    sentiment_pipeline.fit(X_train_s, y_train_s)

    y_pred_s = sentiment_pipeline.predict(X_val_s)
    acc_s = accuracy_score(y_val_s, y_pred_s)
    print(f"Exactitud (Accuracy) de Sentimiento en Validación: {acc_s * 100:.2f}%\n")
    print("Reporte de Clasificación (Sentimiento):")
    print(classification_report(y_val_s, y_pred_s, digits=4))

    # Reentrenar sobre todo el dataset para producción
    sentiment_pipeline.fit(X, y_sentiment)
    sentiment_path = os.path.join(MODEL_DIR, "sentiment_pipeline.joblib")
    joblib.dump(sentiment_pipeline, sentiment_path)
    print(f"-> Modelo de Sentimientos guardado en: {sentiment_path}")

    print("\n" + "=" * 60)
    print("✅ ENTRENAMIENTO COMPLETADO EXITOSAMENTE")
    print("=" * 60)


if __name__ == "__main__":
    train_models()
