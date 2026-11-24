"""Autenticación por sesión firmada, protección CSRF y control de acceso por rol (RBAC)."""

import hashlib
import secrets
import time

from fastapi import APIRouter, HTTPException, Request

from . import config
from .db import conexion
from .operacion import catalogos_bd
from .operacion.formularios import mostrar, volver

router = APIRouter()
ROLES_SISTEMA = (
    "Operador",
    "Jefe de Operaciones",
    "Programador de Flota",
    "Operador de Patio",
    "Operador de Tráfico",
    "Operador de despacho",
    "Planificador de flota",
    "Conductor",
)
# Matriz de permisos por módulo operativo y perfil institucional.
PERMISOS = {
    "solicitudes": {"Operador", "Jefe de Operaciones", "Operador de despacho"},
    "viajes": {"Operador", "Programador de Flota", "Jefe de Operaciones"},
    "patio": {"Operador", "Operador de Patio", "Jefe de Operaciones"},
    "entregas": {"Operador", "Conductor", "Operador de Tráfico", "Jefe de Operaciones"},
    "flota": {"Operador", "Programador de Flota", "Jefe de Operaciones"},
    "alertas": {
        "Operador",
        "Operador de Tráfico",
        "Programador de Flota",
        "Jefe de Operaciones",
    },
    "ml": {
        "Operador",
        "Planificador de flota",
        "Operador de Tráfico",
        "Programador de Flota",
        "Jefe de Operaciones",
    },
}


def coincide(valor, esperado):
    """Compara cadenas en tiempo constante para mitigar ataques de temporización."""
    return secrets.compare_digest(str(valor).encode("utf-8"), str(esperado).encode("utf-8"))


def cifrar_clave(clave: str) -> str:
    """Deriva un hash seguro con scrypt (sal aleatoria de 16 bytes)."""
    sal = secrets.token_hex(16)
    derivada = hashlib.scrypt(
        clave.encode("utf-8"), salt=bytes.fromhex(sal), n=16384, r=8, p=1, dklen=32
    )
    return f"scrypt${sal}${derivada.hex()}"


def verificar_clave(clave: str, almacenada: str) -> bool:
    """Comprueba la contraseña ingresada frente al hash scrypt o clave de entorno autorizada."""
    if not clave or not almacenada or almacenada == "hash":
        return False
    if almacenada == "env_demo":
        return bool(config.CLAVE_DEMO) and coincide(clave, config.CLAVE_DEMO)
    if not almacenada.startswith("scrypt$"):
        return False
    partes = almacenada.split("$")
    if len(partes) != 3:
        return False
    _, sal, esperado = partes
    try:
        derivada = hashlib.scrypt(
            clave.encode("utf-8"), salt=bytes.fromhex(sal), n=16384, r=8, p=1, dklen=32
        )
    except ValueError:
        return False
    return coincide(derivada.hex(), esperado)


async def autorizado(request: Request):
    """Dependencia FastAPI que valida sesión activa, timeout y token CSRF en cada POST."""
    # 1. Recuperar la sesión actual y invalidarla si expiró el tiempo máximo de inactividad.
    usuario = request.session.get("usuario")
    if not usuario or time.time() - request.session.get("actividad", 0) > config.EXPIRACION_SESION_SEG:
        request.session.clear()
        raise HTTPException(303, headers={"Location": "/ingresar"})
    # 2. Renovar la marca de última actividad al procesar una petición válida.
    request.session["actividad"] = time.time()
    # 3. Exigir token CSRF coincidente en toda petición de escritura (POST).
    if request.method == "POST":
        formulario = await request.form()
        if not coincide(str(formulario.get("csrf", "")), request.session.get("csrf", "")):
            raise HTTPException(403, "La sesión del formulario venció. Recarga la página.")
    return usuario


def permiso(request, modulo):
    """Verifica en servidor que el rol del usuario autenticado posea acceso al módulo."""
    rol = request.session["usuario"]["rol"]
    if rol not in PERMISOS.get(modulo, set()):
        raise HTTPException(403, "Tu rol no tiene permiso para realizar esta operación.")


@router.get("/ingresar")
def ingresar(request: Request):
    """Muestra la pantalla de inicio de sesión cargando sedes reales desde PostgreSQL."""
    request.session.setdefault("csrf", secrets.token_urlsafe(24))
    return mostrar(request, "ingresar.html", sedes=catalogos_bd.obtener_sedes())


@router.post("/ingresar")
async def entrar(request: Request):
    """Autentica al usuario por correo, contraseña y sede operativa validada contra SQL."""
    sedes_validas = catalogos_bd.obtener_sedes()
    # 1. Comprobar formato de entrada, sede operativa existente en SQL y token CSRF.
    f = await request.form()
    correo = str(f.get("correo", "")).strip()
    clave = str(f.get("clave", ""))
    sede = str(f.get("sede", ""))
    csrf_valido = bool(request.session.get("csrf")) and coincide(
        str(f.get("csrf", "")), request.session.get("csrf", "")
    )
    if not (csrf_valido and correo and clave and sede in sedes_validas):
        return mostrar(
            request,
            "ingresar.html",
            sedes=sedes_validas,
            error="Revisa las credenciales y la sede seleccionada.",
        )

    es_principal = correo.lower() == config.USUARIO_DEMO.lower()
    valida_env = es_principal and bool(config.CLAVE_DEMO) and coincide(clave, config.CLAVE_DEMO)

    # 2. Consultar cuenta activa y rol asignado en PostgreSQL, registrando auditoría de acceso.
    with conexion() as con:
        u = con.execute(
            """SELECT u.id_usuario, u.correo, u.contrasena, r.nombre AS rol
            FROM usuario u JOIN rol r USING(id_rol)
            WHERE lower(u.correo)=lower(%s) AND u.estado='Activo'""",
            (correo,),
        ).fetchone()
        if not u:
            if valida_env:
                raise ValueError("El usuario principal configurado debe existir y estar activo en SQL.")
            return mostrar(
                request,
                "ingresar.html",
                sedes=sedes_validas,
                error="Revisa las credenciales y la sede seleccionada.",
            )
        if not (valida_env or verificar_clave(clave, u["contrasena"])):
            return mostrar(
                request,
                "ingresar.html",
                sedes=sedes_validas,
                error="Revisa las credenciales y la sede seleccionada.",
            )
        con.execute(
            "INSERT INTO registro_sesion(id_usuario,sede) VALUES(%s,%s)",
            (u["id_usuario"], sede),
        )

    # 3. Emitir cookie limpia (jamás guarda contraseña ni hash) y rotar token CSRF.
    perfil = {"id_usuario": u["id_usuario"], "correo": u["correo"], "rol": u["rol"], "sede": sede}
    request.session.clear()
    request.session.update(
        usuario=perfil, actividad=time.time(), csrf=secrets.token_urlsafe(24)
    )
    return volver("/", "Sesión iniciada.")


@router.post("/salir", dependencies=[])
async def salir(request: Request):
    """Cierra la sesión validando el token CSRF antes de limpiar las cookies."""
    await autorizado(request)
    request.session.clear()
    return volver("/ingresar", "Sesión cerrada.")
