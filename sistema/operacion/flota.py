"""Gestión integral de catálogos operativos (flota, conductores, clientes, accesos) y centro de alertas."""

from datetime import date, datetime, timedelta
import re

from fastapi import APIRouter, Depends, Form, Request

from .. import config
from ..db import conexion, consultar, obtener
from ..seguridad import ROLES_SISTEMA, autorizado, cifrar_clave, permiso
from . import catalogos_bd
from .formularios import exigir, mostrar, volver

router = APIRouter(dependencies=[Depends(autorizado)])
SECCIONES = ("tractos", "semirremolques", "conductores", "clientes", "usuarios")
PATRON_PLACA = re.compile(r"^[A-Z0-9]{3}-[A-Z0-9]{3}$")
PATRON_RUC = re.compile(r"^(10|20)[0-9]{9}$")


def _asegurar_roles(con):
    """Garantiza que todos los roles definidos en RBAC existan en PostgreSQL."""
    for nombre in ROLES_SISTEMA:
        con.execute(
            "INSERT INTO rol(nombre) VALUES(%s) ON CONFLICT (nombre) DO NOTHING",
            (nombre,),
        )


@router.get("/flota")
def panel_flota(request: Request, seccion: str = "tractos", editar: int | None = None):
    """Panel maestro CRUD para tractocamiones, semirremolques, conductores, clientes y cuentas RBAC."""
    permiso(request, "flota")
    if seccion not in SECCIONES:
        seccion = "tractos"
    with conexion() as con:
        _asegurar_roles(con)

    # 1. Consultar catálogos completos junto con su historial de viajes/sesiones desde SQL.
    tractos = consultar(
        """SELECT t.*,
           (SELECT count(*) FROM despacho d WHERE d.id_tracto=t.id_tracto) AS total_viajes
           FROM tracto t ORDER BY t.id_tracto"""
    )
    semis = consultar(
        """SELECT s.*,
           (SELECT count(*) FROM despacho d WHERE d.id_semirremolque=s.id_semirremolque) AS total_viajes
           FROM semirremolque s ORDER BY s.id_semirremolque"""
    )
    conductores = consultar(
        """SELECT c.*, u.correo AS usuario_correo,
           (SELECT count(*) FROM despacho d WHERE d.id_conductor=c.id_conductor) AS total_viajes
           FROM conductor c JOIN usuario u USING(id_usuario) ORDER BY c.id_conductor"""
    )
    clientes = consultar(
        """SELECT cl.*,
           (SELECT count(*) FROM solicitud_carga s WHERE s.id_cliente=cl.id_cliente) AS total_solicitudes
           FROM cliente cl ORDER BY cl.razon_social"""
    )
    usuarios = consultar(
        """SELECT u.id_usuario, u.correo, u.sede_operativa, u.estado, r.nombre AS rol,
           (SELECT count(*) FROM registro_sesion rs WHERE rs.id_usuario=u.id_usuario) AS sesiones
           FROM usuario u JOIN rol r USING(id_rol) ORDER BY u.id_usuario"""
    )
    roles = consultar("SELECT * FROM rol ORDER BY id_rol")

    item_editar = None
    if editar:
        mapa = {
            "tractos": ("tracto", "id_tracto"),
            "semirremolques": ("semirremolque", "id_semirremolque"),
            "conductores": ("conductor", "id_conductor"),
            "clientes": ("cliente", "id_cliente"),
        }
        if seccion in mapa:
            tabla, pk = mapa[seccion]
            item_editar = obtener(f"SELECT * FROM {tabla} WHERE {pk}=%s", (editar,))

    # 2. Calcular indicadores y valores sugeridos dinámicamente sin literales fijos en HTML.
    kpis_flota = {
        "tractos_disp": sum(1 for t in tractos if t["estado"] == "Disponible"),
        "tractos_total": len(tractos),
        "semis_disp": sum(1 for s in semis if s["estado"] == "Disponible"),
        "semis_total": len(semis),
        "cond_hab": sum(1 for c in conductores if c["estado"] == "Habilitado"),
        "cond_total": len(conductores),
        "clientes_total": len(clientes),
    }
    capacidad_defecto = (
        round(sum(float(s["capacidad_tn"]) for s in semis) / len(semis), 2)
        if semis
        else config.CAPACIDAD_MAX_TN
    )
    hoy = datetime.now(config.ZONA).date()
    return mostrar(
        request,
        "flota.html",
        seccion=seccion,
        secciones=SECCIONES,
        item_editar=item_editar,
        kpis_flota=kpis_flota,
        tractos=tractos,
        semirremolques=semis,
        conductores=conductores,
        clientes=clientes,
        usuarios=usuarios,
        roles=roles,
        sedes=catalogos_bd.obtener_sedes(),
        capacidad_min=config.CAPACIDAD_MIN_TN,
        capacidad_max=config.CAPACIDAD_MAX_TN,
        capacidad_defecto=capacidad_defecto,
        categorias_brevete=config.CATEGORIAS_BREVETE,
        hoy_iso=hoy.isoformat(),
        vencimiento_defecto=(hoy + timedelta(days=730)).isoformat(),
        usuario_principal=config.USUARIO_DEMO,
    )


@router.post("/flota/tractos")
def crear_tracto(request: Request, placa: str = Form(), modelo: str = Form()):
    permiso(request, "flota")
    placa_norm = placa.strip().upper()
    exigir(bool(PATRON_PLACA.match(placa_norm)), "La placa debe tener el formato ABC-123.")
    exigir(bool(modelo.strip()), "Indica la marca y modelo del tractocamión.")
    with conexion() as con:
        con.execute(
            "INSERT INTO tracto(placa, modelo, estado) VALUES(%s, %s, 'Disponible')",
            (placa_norm, modelo.strip()),
        )
    return volver("/flota?seccion=tractos", f"Tractocamión {placa_norm} registrado.")


@router.post("/flota/tractos/{id_tracto}/editar")
def editar_tracto(
    request: Request,
    id_tracto: int,
    placa: str = Form(),
    modelo: str = Form(),
    estado: str = Form(),
):
    permiso(request, "flota")
    placa_norm = placa.strip().upper()
    exigir(bool(PATRON_PLACA.match(placa_norm)), "La placa debe tener el formato ABC-123.")
    exigir(estado in ("Disponible", "Mantenimiento"), "Estado operativo no válido.")
    with conexion() as con:
        actual = con.execute(
            "SELECT * FROM tracto WHERE id_tracto=%s FOR UPDATE", (id_tracto,)
        ).fetchone()
        exigir(actual is not None, "Tractocamión no encontrado.")
        exigir(
            actual["estado"] != "Asignado",
            "No se puede cambiar el estado de un tractocamión con viaje en curso.",
        )
        con.execute(
            "UPDATE tracto SET placa=%s, modelo=%s, estado=%s WHERE id_tracto=%s",
            (placa_norm, modelo.strip(), estado, id_tracto),
        )
    return volver("/flota?seccion=tractos", f"Tractocamión {placa_norm} actualizado.")


@router.post("/flota/tractos/{id_tracto}/eliminar")
def eliminar_tracto(request: Request, id_tracto: int):
    permiso(request, "flota")
    with conexion() as con:
        usado = con.execute(
            "SELECT 1 FROM despacho WHERE id_tracto=%s LIMIT 1", (id_tracto,)
        ).fetchone()
        exigir(
            not usado,
            "El tractocamión tiene viajes registrados; cámbialo a Mantenimiento para conservar la trazabilidad.",
        )
        borrado = con.execute(
            "DELETE FROM tracto WHERE id_tracto=%s RETURNING placa", (id_tracto,)
        ).fetchone()
        exigir(borrado is not None, "Tractocamión no encontrado.")
    return volver("/flota?seccion=tractos", f"Tractocamión {borrado['placa']} eliminado.")


@router.post("/flota/semirremolques")
def crear_semirremolque(request: Request, placa: str = Form(), capacidad_tn: float = Form()):
    permiso(request, "flota")
    placa_norm = placa.strip().upper()
    exigir(bool(PATRON_PLACA.match(placa_norm)), "La placa debe tener el formato F9T-901.")
    exigir(
        config.CAPACIDAD_MIN_TN <= capacidad_tn <= config.CAPACIDAD_MAX_TN,
        f"La capacidad útil debe estar entre {config.CAPACIDAD_MIN_TN:g} y {config.CAPACIDAD_MAX_TN:g} toneladas.",
    )
    with conexion() as con:
        con.execute(
            "INSERT INTO semirremolque(placa, capacidad_tn, estado) VALUES(%s, %s, 'Disponible')",
            (placa_norm, round(capacidad_tn, 2)),
        )
    return volver("/flota?seccion=semirremolques", f"Semirremolque {placa_norm} registrado.")


@router.post("/flota/semirremolques/{id_semirremolque}/editar")
def editar_semirremolque(
    request: Request,
    id_semirremolque: int,
    placa: str = Form(),
    capacidad_tn: float = Form(),
    estado: str = Form(),
):
    permiso(request, "flota")
    placa_norm = placa.strip().upper()
    exigir(bool(PATRON_PLACA.match(placa_norm)), "La placa debe tener el formato F9T-901.")
    exigir(
        config.CAPACIDAD_MIN_TN <= capacidad_tn <= config.CAPACIDAD_MAX_TN,
        f"La capacidad útil debe estar entre {config.CAPACIDAD_MIN_TN:g} y {config.CAPACIDAD_MAX_TN:g} toneladas.",
    )
    exigir(estado in ("Disponible", "Mantenimiento"), "Estado operativo no válido.")
    with conexion() as con:
        actual = con.execute(
            "SELECT * FROM semirremolque WHERE id_semirremolque=%s FOR UPDATE",
            (id_semirremolque,),
        ).fetchone()
        exigir(actual is not None, "Semirremolque no encontrado.")
        exigir(
            actual["estado"] != "Asignado",
            "No se puede modificar un semirremolque asignado a un viaje activo.",
        )
        con.execute(
            """UPDATE semirremolque SET placa=%s, capacidad_tn=%s, estado=%s
            WHERE id_semirremolque=%s""",
            (placa_norm, round(capacidad_tn, 2), estado, id_semirremolque),
        )
    return volver("/flota?seccion=semirremolques", f"Semirremolque {placa_norm} actualizado.")


@router.post("/flota/semirremolques/{id_semirremolque}/eliminar")
def eliminar_semirremolque(request: Request, id_semirremolque: int):
    permiso(request, "flota")
    with conexion() as con:
        usado = con.execute(
            "SELECT 1 FROM despacho WHERE id_semirremolque=%s LIMIT 1", (id_semirremolque,)
        ).fetchone()
        exigir(
            not usado,
            "El semirremolque posee historial de viajes; cámbialo a Mantenimiento para conservar la auditoría.",
        )
        borrado = con.execute(
            "DELETE FROM semirremolque WHERE id_semirremolque=%s RETURNING placa",
            (id_semirremolque,),
        ).fetchone()
        exigir(borrado is not None, "Semirremolque no encontrado.")
    return volver("/flota?seccion=semirremolques", f"Semirremolque {borrado['placa']} eliminado.")


@router.post("/flota/conductores")
def crear_conductor(
    request: Request,
    nombre: str = Form(),
    brevete: str = Form(),
    categoria_brevete: str = Form(default=config.CATEGORIA_BREVETE_PESADA),
    fecha_vencimiento: str = Form(),
    id_usuario: int = Form(),
):
    permiso(request, "flota")
    vencimiento = date.fromisoformat(fecha_vencimiento)
    exigir(bool(nombre.strip()) and bool(brevete.strip()), "Completa el nombre y número de brevete.")
    exigir(categoria_brevete in config.CATEGORIAS_BREVETE, "Categoría de brevete no válida.")
    with conexion() as con:
        con.execute(
            """INSERT INTO conductor(id_usuario, nombre, brevete, categoria_brevete, fecha_vencimiento, estado)
            VALUES(%s, %s, %s, %s, %s, 'Habilitado')""",
            (id_usuario, nombre.strip(), brevete.strip().upper(), categoria_brevete, vencimiento),
        )
    return volver("/flota?seccion=conductores", f"Conductor {nombre.strip()} registrado.")


@router.post("/flota/conductores/{id_conductor}/editar")
def editar_conductor(
    request: Request,
    id_conductor: int,
    nombre: str = Form(),
    brevete: str = Form(),
    categoria_brevete: str = Form(),
    fecha_vencimiento: str = Form(),
    estado: str = Form(),
):
    permiso(request, "flota")
    vencimiento = date.fromisoformat(fecha_vencimiento)
    exigir(categoria_brevete in config.CATEGORIAS_BREVETE, "Categoría de brevete no válida.")
    exigir(estado in ("Habilitado", "Inhabilitado"), "Estado de conductor no válido.")
    with conexion() as con:
        actual = con.execute(
            "SELECT * FROM conductor WHERE id_conductor=%s FOR UPDATE", (id_conductor,)
        ).fetchone()
        exigir(actual is not None, "Conductor no encontrado.")
        exigir(
            actual["estado"] != "Asignado",
            "El conductor tiene un viaje en curso y no puede modificarse ahora.",
        )
        con.execute(
            """UPDATE conductor
            SET nombre=%s, brevete=%s, categoria_brevete=%s, fecha_vencimiento=%s, estado=%s
            WHERE id_conductor=%s""",
            (
                nombre.strip(),
                brevete.strip().upper(),
                categoria_brevete,
                vencimiento,
                estado,
                id_conductor,
            ),
        )
    return volver("/flota?seccion=conductores", f"Conductor {nombre.strip()} actualizado.")


@router.post("/flota/conductores/{id_conductor}/eliminar")
def eliminar_conductor(request: Request, id_conductor: int):
    permiso(request, "flota")
    with conexion() as con:
        usado = con.execute(
            "SELECT 1 FROM despacho WHERE id_conductor=%s LIMIT 1", (id_conductor,)
        ).fetchone()
        exigir(
            not usado,
            "El conductor figura en viajes históricos; márcalo como Inhabilitado.",
        )
        borrado = con.execute(
            "DELETE FROM conductor WHERE id_conductor=%s RETURNING nombre", (id_conductor,)
        ).fetchone()
        exigir(borrado is not None, "Conductor no encontrado.")
    return volver("/flota?seccion=conductores", f"Conductor {borrado['nombre']} eliminado.")


@router.post("/flota/clientes")
def crear_cliente(request: Request, razon_social: str = Form(), ruc: str = Form()):
    permiso(request, "flota")
    ruc_limpio = ruc.strip()
    exigir(bool(PATRON_RUC.match(ruc_limpio)), "El RUC debe tener 11 dígitos válidos (10 o 20...).")
    exigir(bool(razon_social.strip()), "Ingresa la razón social del cliente.")
    with conexion() as con:
        con.execute(
            "INSERT INTO cliente(razon_social, ruc) VALUES(%s, %s)",
            (razon_social.strip(), ruc_limpio),
        )
    return volver("/flota?seccion=clientes", f"Cliente {razon_social.strip()} registrado.")


@router.post("/flota/clientes/{id_cliente}/editar")
def editar_cliente(
    request: Request, id_cliente: int, razon_social: str = Form(), ruc: str = Form()
):
    permiso(request, "flota")
    ruc_limpio = ruc.strip()
    exigir(bool(PATRON_RUC.match(ruc_limpio)), "El RUC debe tener 11 dígitos válidos (10 o 20...).")
    with conexion() as con:
        actualizado = con.execute(
            "UPDATE cliente SET razon_social=%s, ruc=%s WHERE id_cliente=%s RETURNING id_cliente",
            (razon_social.strip(), ruc_limpio, id_cliente),
        ).fetchone()
        exigir(actualizado is not None, "Cliente no encontrado.")
    return volver("/flota?seccion=clientes", f"Cliente {razon_social.strip()} actualizado.")


@router.post("/flota/clientes/{id_cliente}/eliminar")
def eliminar_cliente(request: Request, id_cliente: int):
    permiso(request, "flota")
    with conexion() as con:
        usado = con.execute(
            "SELECT 1 FROM solicitud_carga WHERE id_cliente=%s LIMIT 1", (id_cliente,)
        ).fetchone()
        exigir(
            not usado,
            "El cliente tiene solicitudes asociadas y se conserva por integridad referencial.",
        )
        borrado = con.execute(
            "DELETE FROM cliente WHERE id_cliente=%s RETURNING razon_social", (id_cliente,)
        ).fetchone()
        exigir(borrado is not None, "Cliente no encontrado.")
    return volver("/flota?seccion=clientes", f"Cliente {borrado['razon_social']} eliminado.")


@router.post("/flota/usuarios")
def crear_usuario(
    request: Request,
    correo: str = Form(),
    clave: str = Form(),
    id_rol: int = Form(),
    sede_operativa: str = Form(),
):
    permiso(request, "flota")
    correo_limpio = correo.strip().lower()
    sedes_validas = catalogos_bd.obtener_sedes()
    exigir("@" in correo_limpio and len(correo_limpio) >= 6, "Ingresa un correo institucional válido.")
    exigir(len(clave) >= 8, "La contraseña debe tener al menos 8 caracteres.")
    exigir(sede_operativa in sedes_validas, "Selecciona una sede operativa válida.")
    hash_clave = cifrar_clave(clave)
    with conexion() as con:
        con.execute(
            """INSERT INTO usuario(id_rol, correo, contrasena, sede_operativa, estado)
            VALUES(%s, %s, %s, %s, 'Activo')""",
            (id_rol, correo_limpio, hash_clave, sede_operativa),
        )
    return volver("/flota?seccion=usuarios", f"Usuario {correo_limpio} creado con rol asignado.")


@router.post("/flota/usuarios/{id_usuario}/estado")
def cambiar_estado_usuario(
    request: Request,
    id_usuario: int,
    estado: str = Form(),
    nueva_clave: str = Form(default=""),
):
    permiso(request, "flota")
    exigir(estado in ("Activo", "Inactivo"), "Estado de usuario no válido.")
    with conexion() as con:
        objetivo = con.execute(
            "SELECT * FROM usuario WHERE id_usuario=%s FOR UPDATE", (id_usuario,)
        ).fetchone()
        exigir(objetivo is not None, "Usuario no encontrado.")
        if estado == "Inactivo":
            exigir(
                objetivo["correo"].lower() != config.USUARIO_DEMO.lower()
                and objetivo["id_usuario"] != request.session["usuario"]["id_usuario"],
                "No puedes desactivar tu propia sesión ni la cuenta principal del sistema.",
            )
        if nueva_clave.strip():
            exigir(len(nueva_clave.strip()) >= 8, "La nueva contraseña requiere al menos 8 caracteres.")
            con.execute(
                "UPDATE usuario SET estado=%s, contrasena=%s WHERE id_usuario=%s",
                (estado, cifrar_clave(nueva_clave.strip()), id_usuario),
            )
        else:
            con.execute(
                "UPDATE usuario SET estado=%s WHERE id_usuario=%s", (estado, id_usuario)
            )
    return volver("/flota?seccion=usuarios", f"Cuenta {objetivo['correo']} actualizada.")


@router.get("/alertas")
def listar_alertas(request: Request):
    permiso(request, "alertas")
    activas = consultar(
        """SELECT a.*, d.estado_viaje, d.eta_estimado, s.origen, s.destino,
                  s.ventana_entrega, t.placa, c.nombre AS corredor
           FROM alerta a
           JOIN despacho d USING(id_despacho)
           JOIN solicitud_carga s USING(id_solicitud)
           JOIN corredor c USING(id_corredor)
           JOIN tracto t USING(id_tracto)
           WHERE d.estado_viaje NOT IN ('Cerrado','Cancelado')
           ORDER BY a.retraso_min DESC, a.fecha_hora DESC"""
    )
    historicas = consultar(
        """SELECT a.*, d.estado_viaje, s.origen, s.destino, t.placa
           FROM alerta a
           JOIN despacho d USING(id_despacho)
           JOIN solicitud_carga s USING(id_solicitud)
           JOIN tracto t USING(id_tracto)
           WHERE d.estado_viaje IN ('Cerrado','Cancelado')
           ORDER BY a.id_alerta DESC LIMIT 25"""
    )
    return mostrar(
        request,
        "alertas.html",
        activas=activas,
        historicas=historicas,
        alertas_activas=len(activas),
    )


@router.post("/alertas/{id_alerta}/atender")
def atender_alerta(
    request: Request,
    id_alerta: int,
    accion: str = Form(default="Seguimiento telefónico con unidad y cliente"),
):
    permiso(request, "alertas")
    with conexion() as con:
        alerta = con.execute(
            "SELECT * FROM alerta WHERE id_alerta=%s FOR UPDATE", (id_alerta,)
        ).fetchone()
        exigir(alerta is not None, "La alerta indicada ya no existe.")
        con.execute(
            """INSERT INTO incidencia(id_despacho, tipo, descripcion, accion_tomada)
            VALUES(%s, 'Alerta ETA atendida', %s, %s)""",
            (
                alerta["id_despacho"],
                f"{alerta['mensaje']} ({alerta['retraso_min']} min)",
                accion.strip() or "Alerta revisada en centro de control",
            ),
        )
        con.execute("DELETE FROM alerta WHERE id_alerta=%s", (id_alerta,))
    return volver("/alertas", "Alerta atendida y registrada en la bitácora del viaje.")
