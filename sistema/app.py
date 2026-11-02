"""Servidor del prototipo. Ejecutar desde la raíz: uvicorn sistema.app:app."""

import psycopg
from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from starlette.exceptions import HTTPException
from starlette.responses import RedirectResponse

from . import demanda, entregas, estimaciones, patio, reportes, retornos, seguridad
from . import solicitudes, viajes
from .config import CARPETA, CLAVE_SESION, ES_RENDER
from .db import obtener
from .ml.almacen import disponibles
from .pantallas import mostrar, plantillas
from .seguridad import PERMISOS, autorizado

app = FastAPI(title="Transpacífico", docs_url=None, redoc_url=None, openapi_url=None)
app.add_middleware(
    SessionMiddleware, secret_key=CLAVE_SESION, max_age=1800, same_site="lax", https_only=ES_RENDER
)
app.mount("/estaticos", StaticFiles(directory=CARPETA / "estaticos"), name="estaticos")
plantillas.env.globals["puede"] = lambda usuario, modulo: (
    usuario and usuario["rol"] in PERMISOS[modulo]
)
for modulo in (
    seguridad,
    solicitudes,
    viajes,
    patio,
    entregas,
    estimaciones,
    demanda,
    retornos,
    reportes,
):
    app.include_router(modulo.router)


@app.get("/salud")
def salud():
    return {"estado": "activo"}


@app.get("/", dependencies=[Depends(autorizado)])
def inicio(request: Request):
    _, resumen = reportes.indicadores()
    pendientes = obtener(
        "SELECT count(*) AS cantidad FROM solicitud_carga WHERE estado='Registrada'"
    )
    return mostrar(
        request,
        "index.html",
        resumen=resumen,
        modelos=disponibles(),
        pendientes=pendientes["cantidad"],
    )


@app.exception_handler(ValueError)
async def dato_invalido(request, error):
    respuesta = mostrar(request, "error.html", error=str(error))
    respuesta.status_code = 400
    return respuesta


@app.exception_handler(HTTPException)
async def acceso_o_ruta(request, error):
    if error.status_code == 303:
        return RedirectResponse(error.headers["Location"], status_code=303)
    respuesta = mostrar(request, "error.html", error=error.detail)
    respuesta.status_code = error.status_code
    return respuesta


@app.exception_handler(RequestValidationError)
async def formulario_invalido(request, error):
    campos = ", ".join(str(e["loc"][-1]) for e in error.errors())
    return await dato_invalido(request, ValueError("Revisa estos campos: " + campos))


@app.exception_handler(psycopg.Error)
async def error_sql(request, error):
    # Nunca mostrar la cadena de conexión, credenciales ni detalles internos de PostgreSQL.
    mensaje = (
        "El registro ya existe o tiene datos relacionados. Revisa el formulario."
        if isinstance(error, psycopg.IntegrityError)
        else "No se pudo consultar PostgreSQL. Revisa la conexión del servidor."
    )
    respuesta = mostrar(request, "error.html", error=mensaje)
    respuesta.status_code = 409 if isinstance(error, psycopg.IntegrityError) else 503
    return respuesta
