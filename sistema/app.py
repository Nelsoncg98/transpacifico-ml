"""Servidor web principal de Transpacífico S.A.C. (FastAPI + Jinja2 + PostgreSQL)."""

import json
import psycopg
from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from starlette.exceptions import HTTPException
from starlette.responses import RedirectResponse

from . import seguridad
from .operacion import solicitudes, despachos, pesaje_salida, entregas, flota, reportes
from .ml import predicciones
from .config import CARPETA, CLAVE_SESION, ES_RENDER, EXPIRACION_SESION_SEG
from .db import consultar, obtener, ViajeNoEncontrado
from .ml.almacen import disponibles
from .operacion.formularios import mostrar, plantillas
from .seguridad import PERMISOS, autorizado

# 1. Inicializar la aplicación FastAPI con sesión cifrada y expiración parametrizada.
app = FastAPI(title="Transpacífico S.A.C.", docs_url=None, redoc_url=None, openapi_url=None)
app.add_middleware(
    SessionMiddleware,
    secret_key=CLAVE_SESION,
    max_age=EXPIRACION_SESION_SEG,
    same_site="lax",
    https_only=ES_RENDER,
)
# 2. Montar archivos estáticos (CSS/JS) y exponer verificación RBAC hacia Jinja2.
app.mount("/estaticos", StaticFiles(directory=CARPETA / "estaticos"), name="estaticos")
plantillas.env.globals["puede"] = lambda usuario, modulo: (
    bool(usuario) and usuario["rol"] in PERMISOS.get(modulo, set())
)
# 3. Registrar routers modulares de operación logística y analítica predictiva.
for modulo in (
    seguridad,
    solicitudes,
    despachos,
    pesaje_salida,
    entregas,
    flota,
    predicciones,
    reportes,
):
    app.include_router(modulo.router)


@app.get("/salud")
def salud():
    """Endpoint ligero de verificación de estado para monitoreo de Render."""
    return {"estado": "activo"}


@app.get("/", dependencies=[Depends(autorizado)])
def inicio(request: Request):
    """Panel operativo principal alimentado íntegramente desde PostgreSQL."""
    # 1. Consultar indicadores agregados de flota, OTIF, FOF, corredores y estados.
    _, resumen = reportes.indicadores()
    pendientes = obtener(
        "SELECT count(*) AS cantidad FROM solicitud_carga WHERE estado='Registrada'"
    )
    # 2. Recuperar despachos vigentes (excluye cerrados y cancelados) con su asignación.
    viajes_curso = consultar(
        """SELECT d.id_despacho, d.estado_viaje, d.fof_porcentaje, d.eta_estimado,
                  s.origen, s.destino, s.ventana_entrega, t.placa, co.nombre AS conductor_nombre
           FROM despacho d
           JOIN solicitud_carga s USING(id_solicitud)
           JOIN tracto t USING(id_tracto)
           JOIN conductor co USING(id_conductor)
           WHERE d.estado_viaje NOT IN ('Cerrado','Cancelado')
           ORDER BY d.id_despacho DESC LIMIT 8"""
    )
    # 3. Obtener alertas ETA activas priorizadas por mayor desviación estimada.
    alertas_top = consultar(
        """SELECT a.id_alerta, a.id_despacho, a.retraso_min, a.mensaje,
                  s.origen, s.destino, t.placa
           FROM alerta a
           JOIN despacho d USING(id_despacho)
           JOIN solicitud_carga s USING(id_solicitud)
           JOIN tracto t USING(id_tracto)
           WHERE d.estado_viaje NOT IN ('Cerrado','Cancelado')
           ORDER BY a.retraso_min DESC, a.id_alerta DESC LIMIT 5"""
    )
    # 4. Serializar series operativas e históricas para los gráficos interactivos en Chart.js.
    graficos_inicio = json.dumps(
        {
            "operacion_activa": resumen["operacion_activa"],
            "por_estado": resumen["por_estado"],
            "por_corredor": resumen["por_corredor"],
        },
        ensure_ascii=False,
    )
    return mostrar(
        request,
        "index.html",
        resumen=resumen,
        modelos=disponibles(),
        pendientes=pendientes["cantidad"],
        viajes_curso=viajes_curso,
        alertas_top=alertas_top,
        graficos_inicio_json=graficos_inicio,
    )


@app.exception_handler(ValueError)
async def dato_invalido(request, error):
    respuesta = mostrar(request, "error.html", error=str(error))
    respuesta.status_code = 400
    return respuesta


@app.exception_handler(ViajeNoEncontrado)
async def viaje_inexistente(request, error):
    respuesta = mostrar(request, "error.html", error=str(error))
    respuesta.status_code = 404
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
