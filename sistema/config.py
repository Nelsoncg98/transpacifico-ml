"""Configuración del servidor, reglas reglamentarias y rutas base del sistema."""

import os
from pathlib import Path
from secrets import token_urlsafe
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

# 1. Ubicar la raíz del paquete y cargar variables locales (.env) si existen.
CARPETA = Path(__file__).resolve().parent
load_dotenv(CARPETA / ".env")

# 2. Zona horaria oficial de operación para formateo visual en Perú.
ZONA = ZoneInfo("America/Lima")

# 3. Credenciales y secretos administrados exclusivamente mediante variables de entorno.
CLAVE_SESION = os.getenv("SESSION_SECRET") or token_urlsafe(48)
USUARIO_DEMO = os.getenv("APP_USER", "operador@transpacifico.pe")
CLAVE_DEMO = os.getenv("APP_PASSWORD", "")
ES_RENDER = bool(os.getenv("RENDER"))

# 4. Directorio de artefactos de Machine Learning (modelos serializados y métricas).
MODELOS = CARPETA / "modelos"

# 5. Constantes normativas y operativas centralizadas (evitan literales sueltos en el código).
PESO_BRUTO_MAX_KG = 48000.0          # Límite máximo PBV en carretera (DS 058-2003-MTC)
UMBRAL_FOF_PCT = 85.0                # Meta operativa mínima de ocupación de flota (%)
CAPACIDAD_MIN_TN = 10.0              # Capacidad útil mínima permitida en catálogos de semirremolques
CAPACIDAD_MAX_TN = 35.0              # Capacidad útil máxima admitida para transporte articulado
FILAS_POR_PAGINA = 25                # Registros mostrados por página en tablas operativas
EXPIRACION_SESION_SEG = 1800         # Expiración de sesión por inactividad (30 minutos)
CATEGORIA_BREVETE_PESADA = "A-IIIc"  # Categoría MTC requerida para tractocamiones de carga pesada
CATEGORIAS_BREVETE = ("A-IIIc", "A-IIIb", "A-IIIa")
SEDES_RESPALDO = ("Callao", "Huancayo", "Trujillo")  # Respaldo solo si PostgreSQL inicia vacío
