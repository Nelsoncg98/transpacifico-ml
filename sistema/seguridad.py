"""Acceso de demostración con usuario de SQL y contraseña configurada en Render."""

import secrets
import time

from fastapi import APIRouter, HTTPException, Request

from . import config
from .db import conexion
from .pantallas import mostrar, volver

router = APIRouter()
SEDES = ("Callao", "Huancayo", "Trujillo")
PERMISOS = {
    "solicitudes": {"Operador", "Jefe de Operaciones", "Operador de despacho"},
    "viajes": {"Operador", "Programador de Flota", "Jefe de Operaciones"},
    "patio": {"Operador", "Operador de Patio"},
    "entregas": {"Operador", "Conductor", "Operador de Tráfico"},
    "ml": {
        "Operador",
        "Planificador de flota",
        "Operador de Tráfico",
        "Programador de Flota",
        "Jefe de Operaciones",
    },
}


def coincide(valor, esperado):
    return secrets.compare_digest(str(valor).encode("utf-8"), str(esperado).encode("utf-8"))


async def autorizado(request: Request):
    usuario = request.session.get("usuario")
    if not usuario or time.time() - request.session.get("actividad", 0) > 1800:
        request.session.clear()
        raise HTTPException(303, headers={"Location": "/ingresar"})
    request.session["actividad"] = time.time()
    if request.method == "POST":
        formulario = await request.form()
        if not coincide(str(formulario.get("csrf", "")), request.session.get("csrf", "")):
            raise HTTPException(403, "La sesión del formulario venció. Recarga la página.")
    return usuario


def permiso(request, modulo):
    rol = request.session["usuario"]["rol"]
    if rol not in PERMISOS[modulo]:
        raise HTTPException(403, "Tu rol no tiene permiso para realizar esta operación.")


@router.get("/ingresar")
def ingresar(request: Request):
    request.session.setdefault("csrf", secrets.token_urlsafe(24))
    return mostrar(request, "ingresar.html", sedes=SEDES)


@router.post("/ingresar")
async def entrar(request: Request):
    f = await request.form()
    correcto = config.CLAVE_DEMO and coincide(str(f.get("clave", "")), config.CLAVE_DEMO)
    correcto = correcto and f.get("correo") == config.USUARIO_DEMO
    correcto = correcto and f.get("sede") in SEDES
    correcto = (
        correcto
        and bool(request.session.get("csrf"))
        and coincide(str(f.get("csrf", "")), request.session.get("csrf", ""))
    )
    if not correcto:
        return mostrar(
            request,
            "ingresar.html",
            sedes=SEDES,
            error="Revisa las credenciales y la sede seleccionada.",
        )
    with conexion() as con:
        u = con.execute(
            """SELECT u.id_usuario, u.correo, r.nombre AS rol
            FROM usuario u JOIN rol r USING(id_rol)
            WHERE correo=%s AND u.estado='Activo'""",
            (config.USUARIO_DEMO,),
        ).fetchone()
        if not u:
            raise ValueError("El usuario de demostración debe existir y estar activo en SQL.")
        con.execute(
            "INSERT INTO registro_sesion(id_usuario,sede) VALUES(%s,%s)",
            (u["id_usuario"], f["sede"]),
        )
    request.session.clear()
    request.session.update(
        usuario={**u, "sede": f["sede"]}, actividad=time.time(), csrf=secrets.token_urlsafe(24)
    )
    return volver("/", "Sesión iniciada.")


@router.post("/salir", dependencies=[])
async def salir(request: Request):
    await autorizado(request)
    request.session.clear()
    return volver("/ingresar", "Sesión cerrada.")
