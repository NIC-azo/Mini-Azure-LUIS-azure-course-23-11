# Mini-Azure LUIS 🌾

Motor de Procesamiento de Lenguaje Natural (NLP) On-Premise y Desacoplado para la Industria Agroexportadora en Red de Área Local (LAN).

---

## 🚀 Arquitectura y Servicios

El proyecto está compuesto por dos servicios orquestados mediante **Docker Compose**:

1. **`nlp-server`** (Puerto `8001`): Backend de Inferencia NLP con FastAPI y Scikit-Learn.
2. **`nlp-client`** (Puerto `8501`): Dashboard analítico e interfaz de simulación con Streamlit.

---

## 🛠️ Comandos de Ejecución

### Modo Desarrollo con Sincronización en Caliente (Docker Compose Watch)

Para iniciar ambos servicios con recarga automática (*live reload* de código y dataset):

```bash
docker compose up --watch
```

O si utilizas la sintaxis con guion:

```bash
docker-compose watch
```

### Ejecución Independiente para Demostración LAN (Día de Evaluación)

- **Integrante A (PC Servidor - Inferencia NLP):**
  ```bash
  docker compose up nlp-server --watch
  ```

- **Integrante B (PC Cliente - Dashboard & Simulador):**
  1. Configurar `TARGET_SERVER_IP` en `.env` con la IP LAN del Integrante A (ej. `192.168.1.XX`).
  2. Iniciar el cliente:
  ```bash
  docker compose up nlp-client --watch
  ```
