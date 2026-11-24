"""Registro, consulta, edición, evaluación y anulación de solicitudes de transporte."""

from datetime import datetime, timedelta, timezone
import json
from fastapi import APIRouter, Depends, Form, Request

from .. import config
from ..db import conexion, consultar, obtener
from . import catalogos_bd
from .formularios import exigir, fecha_local, mostrar, volver
from ..seguridad import autorizado, permiso

router = APIRouter(dependencies=[Depends(autorizado)])
ESTADOS_SOLICITUD = ("Registrada", "Aceptada", "Rechazada", "Anulada")


def a_fecha_zona(valor):
    """Normaliza una fecha SQL (datetime o cadena ISO) hacia la zona horaria oficial de Perú."""
    dt = valor if isinstance(valor, datetime) else datetime.fromisoformat(str(valor))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(config.ZONA)


def _validar_ruta_y_peso(con, id_corredor: int, origen: str, destino: str, peso_tn: float):
    """Comprueba peso reglamentario y coherencia entre corredor y par origen-destino según SQL."""
    # 1. Validar que el peso solicitado no supere la capacidad útil máxima admitida.
    exigir(
        0 < peso_tn <= config.CAPACIDAD_MAX_TN,
        f"El peso estimado debe estar entre 0.01 y {config.CAPACIDAD_MAX_TN:.2f} toneladas.",
    )
    # 2. Comprobar existencia del corredor seleccionado en la base de datos.
    corredor = con.execute(
        "SELECT nombre FROM corredor WHERE id_corredor=%s", (id_corredor,)
    ).fetchone()
    exigir(corredor is not None, "Selecciona un corredor existente.")

    # 3. Contrastar la ruta contra los pares históricos registrados para ese corredor en SQL.
    mapa = catalogos_bd.obtener_mapa_rutas()
    pares_corredor = mapa["pares_por_corredor"].get(int(id_corredor), [])
    if pares_corredor:
        exigir(
            (origen.strip(), destino.strip()) in pares_corredor,
            "La ruta debe corresponder al corredor seleccionado.",
        )
    else:
        exigir(
            bool(origen.strip()) and bool(destino.strip()) and origen.strip() != destino.strip(),
            "El origen y el destino deben ser ciudades válidas y distintas.",
        )


@router.get("/solicitudes")
def listar(
    request: Request,
    estado: str = "",
    pagina: int = 1,
    editar: int | None = None,
):
    """Lista paginada de solicitudes con filtros por estado, capacidad dinámica y rutas SQL."""
    pagina = max(1, pagina)
    limite = config.FILAS_POR_PAGINA
    # 1. Consultar página actual junto con el despacho asociado (si existe y no fue cancelado).
    filas = consultar(
        """SELECT s.*, c.razon_social, r.nombre AS corredor,
        d.id_despacho,
        d.estado_viaje,
        (d.id_despacho IS NOT NULL AND d.estado_viaje <> 'Cancelado') AS asignada
        FROM solicitud_carga s
        JOIN cliente c USING(id_cliente)
        JOIN corredor r USING(id_corredor)
        LEFT JOIN despacho d USING(id_solicitud)
        WHERE (%s='' OR s.estado=%s)
        ORDER BY s.id_solicitud DESC LIMIT %s OFFSET %s""",
        (estado, estado, limite, (pagina - 1) * limite),
    )
    # 2. Calcular totales reales por estado para las pestañas de filtro rápido.
    resumen_estados = {
        r["estado"]: int(r["cantidad"])
        for r in consultar("SELECT estado, count(*) AS cantidad FROM solicitud_carga GROUP BY estado")
    }
    # 3. Determinar tope dinámico del formulario según la mayor capacidad útil de semirremolques.
    max_flota = obtener(
        "SELECT COALESCE(MAX(capacidad_tn), 0) AS max_tn FROM semirremolque WHERE estado <> 'Mantenimiento'"
    )
    max_sql = float(max_flota["max_tn"]) if max_flota else 0.0
    capacidad_max = (
        min(config.CAPACIDAD_MAX_TN, max(config.CAPACIDAD_MIN_TN, max_sql))
        if max_sql > 0
        else config.CAPACIDAD_MAX_TN
    )
    # 4. Cargar mapa dinámico de ciudades y rutas válidas por corredor desde PostgreSQL.
    mapa = catalogos_bd.obtener_mapa_rutas()
    rutas_json = json.dumps(
        {
            str(cid): [[p["origen"], p["destino"]] for p in lista]
            for cid, lista in mapa["rutas_por_corredor"].items()
        },
        ensure_ascii=False,
    )
    ahora = datetime.now(config.ZONA).replace(second=0, microsecond=0)
    for fila in filas:
        ventana_dt = a_fecha_zona(fila["ventana_entrega"])
        fila["vencida"] = (
            fila["estado"] in ("Registrada", "Aceptada")
            and not fila["asignada"]
            and ventana_dt <= ahora
        )
    solicitud_editar = (
        obtener(
            "SELECT * FROM solicitud_carga WHERE id_solicitud=%s AND estado='Registrada'",
            (editar,),
        )
        if editar
        else None
    )
    return mostrar(
        request,
        "solicitudes.html",
        filas=filas,
        estado=estado,
        estados=ESTADOS_SOLICITUD,
        conteos=resumen_estados,
        total_solicitudes=sum(resumen_estados.values()),
        capacidad_max=capacidad_max,
        solicitud_editar=solicitud_editar,
        pagina=pagina,
        ciudades=mapa["ciudades"],
        mapa_rutas_json=rutas_json,
        ahora_min=ahora.strftime("%Y-%m-%dT%H:%M"),
        ventana_sugerida=(ahora + timedelta(hours=12)).strftime("%Y-%m-%dT%H:%M"),
        clientes=consultar("SELECT * FROM cliente ORDER BY razon_social"),
        corredores=mapa["corredores"],
    )


@router.post("/solicitudes")
def registrar(
    request: Request,
    id_cliente: int = Form(),
    id_corredor: int = Form(),
    origen: str = Form(),
    destino: str = Form(),
    guia: str = Form(),
    tipo_carga: str = Form(),
    peso_tn: float = Form(),
    ventana: str = Form(),
):
    permiso(request, "solicitudes")
    fecha = fecha_local(ventana)
    exigir(
        fecha > datetime.now(config.ZONA),
        "La entrega pactada debe ser posterior a la fecha y hora actual.",
    )
    guia_limpia = guia.strip()
    exigir(bool(guia_limpia) and bool(tipo_carga.strip()), "Completa la guía y el tipo de carga.")
    with conexion() as con:
        _validar_ruta_y_peso(con, id_corredor, origen, destino, peso_tn)
        exigir(
            not con.execute(
                "SELECT 1 FROM solicitud_carga WHERE nro_guia_remitente=%s", (guia_limpia,)
            ).fetchone(),
            "La guía ya está registrada.",
        )
        con.execute(
            """INSERT INTO solicitud_carga(id_cliente,id_corredor,nro_guia_remitente,
            origen,destino,tipo_carga,peso_tn,fecha,ventana_entrega)
            VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (
                id_cliente,
                id_corredor,
                guia_limpia,
                origen,
                destino,
                tipo_carga.strip(),
                peso_tn,
                fecha.date(),
                fecha,
            ),
        )
    return volver("/solicitudes", "Solicitud registrada. Está pendiente de evaluación.")


@router.post("/solicitudes/{id_solicitud}/editar")
def editar(
    request: Request,
    id_solicitud: int,
    id_cliente: int = Form(),
    id_corredor: int = Form(),
    origen: str = Form(),
    destino: str = Form(),
    guia: str = Form(),
    tipo_carga: str = Form(),
    peso_tn: float = Form(),
    ventana: str = Form(),
):
    permiso(request, "solicitudes")
    fecha = fecha_local(ventana)
    exigir(
        fecha > datetime.now(config.ZONA),
        "La entrega pactada debe ser posterior a la fecha y hora actual.",
    )
    guia_limpia = guia.strip()
    exigir(bool(guia_limpia) and bool(tipo_carga.strip()), "Completa la guía y el tipo de carga.")
    with conexion() as con:
        actual = con.execute(
            "SELECT estado FROM solicitud_carga WHERE id_solicitud=%s FOR UPDATE", (id_solicitud,)
        ).fetchone()
        exigir(
            actual and actual["estado"] == "Registrada",
            "Solo se pueden modificar solicitudes en estado Registrada.",
        )
        _validar_ruta_y_peso(con, id_corredor, origen, destino, peso_tn)
        duplicada = con.execute(
            "SELECT 1 FROM solicitud_carga WHERE nro_guia_remitente=%s AND id_solicitud<>%s",
            (guia_limpia, id_solicitud),
        ).fetchone()
        exigir(not duplicada, "La guía indicada ya pertenece a otra solicitud.")
        con.execute(
            """UPDATE solicitud_carga
            SET id_cliente=%s, id_corredor=%s, nro_guia_remitente=%s,
                origen=%s, destino=%s, tipo_carga=%s, peso_tn=%s,
                fecha=%s, ventana_entrega=%s
            WHERE id_solicitud=%s""",
            (
                id_cliente,
                id_corredor,
                guia_limpia,
                origen,
                destino,
                tipo_carga.strip(),
                peso_tn,
                fecha.date(),
                fecha,
                id_solicitud,
            ),
        )
    return volver("/solicitudes", f"Solicitud #{id_solicitud} actualizada.")


@router.post("/solicitudes/{id_solicitud}/anular")
def anular(
    request: Request,
    id_solicitud: int,
    motivo: str = Form(default=""),
):
    permiso(request, "solicitudes")
    razon = motivo.strip() or "Anulada por el operador antes de despacho."
    with conexion() as con:
        actual = con.execute(
            "SELECT estado FROM solicitud_carga WHERE id_solicitud=%s FOR UPDATE", (id_solicitud,)
        ).fetchone()
        exigir(
            actual and actual["estado"] == "Registrada",
            "Solo se pueden anular solicitudes en estado Registrada.",
        )
        tiene_despacho = con.execute(
            "SELECT 1 FROM despacho WHERE id_solicitud=%s AND estado_viaje <> 'Cancelado'",
            (id_solicitud,),
        ).fetchone()
        exigir(not tiene_despacho, "La solicitud ya cuenta con un viaje activo.")
        con.execute(
            """UPDATE solicitud_carga
            SET estado='Anulada', motivo_rechazo=%s, fecha_hora_decision=CURRENT_TIMESTAMP
            WHERE id_solicitud=%s""",
            (razon, id_solicitud),
        )
    return volver("/solicitudes", f"Solicitud #{id_solicitud} anulada.")


@router.post("/solicitudes/{id_solicitud}/evaluar")
def evaluar(
    request: Request,
    id_solicitud: int,
    decision: str = Form(),
    motivo: str = Form(default=""),
):
    permiso(request, "solicitudes")
    exigir(decision in ("Aceptada", "Rechazada"), "Selecciona una decisión válida.")
    exigir(decision != "Rechazada" or motivo.strip(), "Indica el motivo del rechazo.")
    with conexion() as con:
        solicitud = con.execute(
            "SELECT estado, ventana_entrega FROM solicitud_carga WHERE id_solicitud=%s FOR UPDATE",
            (id_solicitud,),
        ).fetchone()
        exigir(
            solicitud and solicitud["estado"] == "Registrada",
            "La solicitud ya fue evaluada o no existe.",
        )
        if decision == "Aceptada":
            exigir(
                a_fecha_zona(solicitud["ventana_entrega"]) > datetime.now(config.ZONA),
                "La ventana de entrega pactada ya venció. Edita la fecha de entrega o rechaza/anula la solicitud.",
            )
        con.execute(
            """UPDATE solicitud_carga SET estado=%s,motivo_rechazo=%s,
            fecha_hora_decision=CURRENT_TIMESTAMP WHERE id_solicitud=%s""",
            (decision, motivo.strip() if decision == "Rechazada" else None, id_solicitud),
        )
    return volver("/solicitudes", "Evaluación guardada.")
