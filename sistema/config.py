"""Configuración del servidor. Las claves se leen del entorno, nunca del repositorio."""

import os
from pathlib import Path
from secrets import token_urlsafe
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

# 1. Ubicar el sistema; cargar .env solo si se ejecuta localmente.
CARPETA = Path(__file__).resolve().parent
load_dotenv(CARPETA / ".env")
# 2. Mostrar las fechas al usuario en hora de Perú.
ZONA = ZoneInfo("America/Lima")
# 3. Leer las claves desde el entorno de Render, sin escribirlas en el código.
CLAVE_SESION = os.getenv("SESSION_SECRET") or token_urlsafe(48)
USUARIO_DEMO = os.getenv("APP_USER", "operador@transpacifico.pe")
CLAVE_DEMO = os.getenv("APP_PASSWORD", "")
ES_RENDER = bool(os.getenv("RENDER"))
# 4. Guardar los modelos entrenados aparte del código fuente.
MODELOS = CARPETA / "modelos"
