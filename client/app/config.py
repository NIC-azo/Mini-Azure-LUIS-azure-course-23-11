import os
from dotenv import load_dotenv

load_dotenv()

TARGET_SERVER_IP = os.getenv("TARGET_SERVER_IP", "127.0.0.1")
SERVER_PORT = os.getenv("SERVER_PORT", "8001")

def get_api_base_url(custom_ip: str = None) -> str:
    ip = custom_ip if custom_ip else TARGET_SERVER_IP
    return f"http://{ip}:{SERVER_PORT}"
