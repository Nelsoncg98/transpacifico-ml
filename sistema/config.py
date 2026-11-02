"""Configuración del servidor. Las claves se leen del entorno, nunca del repositorio."""

import os
from pathlib import Path
from secrets import token_urlsafe
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

CARPETA = Path(__file__).resolve().parent
load_dotenv(CARPETA / ".env")
ZONA = ZoneInfo("America/Lima")
CLAVE_SESION = os.getenv("SESSION_SECRET") or token_urlsafe(48)
USUARIO_DEMO = os.getenv("APP_USER", "operador@transpacifico.pe")
CLAVE_DEMO = os.getenv("APP_PASSWORD", "")
ES_RENDER = bool(os.getenv("RENDER"))
MODELOS = CARPETA / "modelos"
