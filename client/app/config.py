import os
from dotenv import load_dotenv

load_dotenv()

TARGET_SERVER_IP = os.getenv("TARGET_SERVER_IP", "127.0.0.1")
SERVER_PORT = os.getenv("SERVER_PORT", "8001")


def get_api_base_url(custom_ip: str = None, custom_port: str = None) -> str:
    """
    Construye la URL base del servidor NLP.
    Si corre dentro de un contenedor Docker y se indica 127.0.0.1 o localhost,
    resuelve automáticamente al servicio 'nlp-server' de la red interna Docker.
    En laboratorio LAN, usará la IP ingresada (ej. 192.168.1.XX).
    """
    ip = custom_ip.strip() if custom_ip and custom_ip.strip() else TARGET_SERVER_IP
    port = custom_port.strip() if custom_port and custom_port.strip() else SERVER_PORT

    # Si estamos dentro del contenedor Docker y se pasa localhost/127.0.0.1
    if os.path.exists("/.dockerenv") and ip in ["127.0.0.1", "localhost"]:
        ip = "nlp-server"

    return f"http://{ip}:{port}"
