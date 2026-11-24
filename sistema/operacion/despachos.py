"""Programación, reasignación, cancelación y consulta del expediente de cada viaje."""

from datetime import datetime

from fastapi import APIRouter, Depends, Form, Request

from .. import config
from ..db import conexion, consultar, obtener, viaje
from .formularios import exigir, mostrar, volver
from .solicitudes import a_fecha_zona
from ..seguridad import autorizado, permiso

router = APIRouter(dependencies=[Depends(autorizado)])
ESTADOS_VIAJE = ("Programado", "En patio", "En tránsito", "En destino", "Cerrado", "Cancelado")


def _validar_recursos_asignables(
    con, id_tracto, id_semirremolque, id_conductor, fecha_servicio, peso_tn, excluir_despacho=None
):
    """Verifica disponibilidad física, ausencia de viaje paralelo, brevete vigente y capacidad útil."""
    # 1. Bloquear y comprobar que tracto, semirremolque y conductor no participen en otro despacho activo.
    recursos = {}
    for tabla, identificador in (
        ("tracto", id_tracto),
        ("semirremolque", id_semirremolque),
        ("conductor", id_conductor),
    ):
        recurso = con.execute(
            f"SELECT * FROM {tabla} WHERE id_{tabla}=%s FOR UPDATE", (identificador,)
        ).fetchone()
        exigir(recurso is not None, f"El recurso {tabla} indicado no existe.")
        ocupado = con.execute(
            f"""SELECT id_despacho FROM despacho WHERE id_{tabla}=%s
            AND estado_viaje NOT IN ('Cerrado','Cancelado')
            AND (%s IS NULL OR id_despacho <> %s)""",
            (identificador, excluir_despacho, excluir_despacho),
        ).fetchone()
        exigir(not ocupado, f"El recurso {tabla} ya tiene un viaje activo.")
        mismo_viaje = (
            excluir_despacho is not None
            and con.execute(
                f"SELECT 1 FROM despacho WHERE id_despacho=%s AND id_{tabla}=%s",
                (excluir_despacho, identificador),
            ).fetchone()
        )
        exigir(
            mismo_viaje or recurso["estado"] in ("Disponible", "Habilitado"),
            f"El recurso {tabla} no está disponible.",
        )
        recursos[tabla] = recurso

    # 2. Exigir categoría MTC habilitada para vehículo pesado y licencia vigente al día de entrega.
    conductor = recursos["conductor"]
    exigir(
        conductor["categoria_brevete"] == config.CATEGORIA_BREVETE_PESADA
        and conductor["fecha_vencimiento"] >= max(fecha_servicio, datetime.now(config.ZONA).date()),
        f"El conductor requiere brevete {config.CATEGORIA_BREVETE_PESADA} vigente para el servicio.",
    )
    # 3. Validar capacidad del semirremolque y calcular Factor de Ocupación de Flota (FOF %).
    capacidad = float(recursos["semirremolque"]["capacidad_tn"])
    exigir(
        capacidad > 0 and float(peso_tn) <= capacidad,
        "La carga supera la capacidad útil del semirremolque seleccionado.",
    )
    return recursos, round(float(peso_tn) / capacidad * 100, 2)


@router.get("/viajes")
def listar(
    request: Request,
    pagina: int = 1,
    estado: str = "",
    solicitud: int | None = None,
):
    """Lista despachos con su trazabilidad completa y el último odómetro real por tractocamión."""
    pagina = max(1, pagina)
    limite = config.FILAS_POR_PAGINA
    filas = consultar(
        """SELECT d.*, s.origen, s.destino, s.peso_tn, s.ventana_entrega,
               c.nombre AS corredor, cl.razon_social AS cliente_nombre,
               t.placa, sr.placa AS placa_semi, sr.capacidad_tn,
               co.nombre AS conductor_nombre
        FROM despacho d
        JOIN solicitud_carga s USING(id_solicitud)
        JOIN corredor c USING(id_corredor)
        JOIN cliente cl ON cl.id_cliente = s.id_cliente
        JOIN tracto t USING(id_tracto)
        JOIN semirremolque sr USING(id_semirremolque)
        JOIN conductor co USING(id_conductor)
        WHERE (%s='' OR d.estado_viaje=%s)
        ORDER BY d.id_despacho DESC
        LIMIT %s OFFSET %s""",
        (estado, estado, limite, (pagina - 1) * limite),
    )
    pendientes = consultar(
        """SELECT s.*, cl.razon_social, c.nombre AS corredor
        FROM solicitud_carga s
        JOIN cliente cl USING(id_cliente)
        JOIN corredor c USING(id_corredor)
        WHERE s.estado='Aceptada'
        AND NOT EXISTS(
            SELECT 1 FROM despacho d
            WHERE d.id_solicitud=s.id_solicitud AND d.estado_viaje <> 'Cancelado'
        )
        ORDER BY s.id_solicitud DESC LIMIT 100"""
    )
    ahora_zona = datetime.now(config.ZONA)
    pendientes = [p for p in pendientes if a_fecha_zona(p["ventana_entrega"]) > ahora_zona]
    resumen_estados = {
        r["estado_viaje"]: int(r["cantidad"])
        for r in consultar("SELECT estado_viaje, count(*) AS cantidad FROM despacho GROUP BY estado_viaje")
    }
    # Recuperar para cada tractocamión el mayor odómetro histórico para sugerirlo automáticamente.
    tractos = consultar(
        """SELECT t.*, COALESCE((
            SELECT MAX(COALESCE(d.odometro_final_km, d.odometro_inicial_km))
            FROM despacho d
            WHERE d.id_tracto = t.id_tracto AND d.estado_viaje <> 'Cancelado'
        ), 0) AS ultimo_odometro
        FROM tracto t ORDER BY (t.estado='Disponible') DESC, t.placa"""
    )
    odometro_sugerido = next(
        (int(t["ultimo_odometro"]) for t in tractos if t["estado"] == "Disponible"), 0
    )
    catalogos = {
        "tracto": tractos,
        "semirremolque": consultar(
            "SELECT * FROM semirremolque ORDER BY (estado='Disponible') DESC, capacidad_tn, placa"
        ),
        "conductor": consultar(
            "SELECT * FROM conductor ORDER BY (estado='Habilitado') DESC, nombre"
        ),
    }
    return mostrar(
        request,
        "viajes.html",
        filas=filas,
        pendientes=pendientes,
        solicitud_seleccionada=solicitud,
        odometro_sugerido=odometro_sugerido,
        estados=ESTADOS_VIAJE,
        conteos=resumen_estados,
        total_viajes=sum(resumen_estados.values()),
        pagina=pagina,
        estado=estado,
        **catalogos,
    )


@router.post("/viajes")
def programar(
    request: Request,
    id_solicitud: int = Form(),
    id_tracto: int = Form(),
    id_semirremolque: int = Form(),
    id_conductor: int = Form(),
    odometro: int = Form(),
):
    permiso(request, "viajes")
    with conexion() as con:
        solicitud = con.execute(
            "SELECT * FROM solicitud_carga WHERE id_solicitud=%s FOR UPDATE", (id_solicitud,)
        ).fetchone()
        exigir(solicitud and solicitud["estado"] == "Aceptada", "La solicitud debe estar aceptada.")
        exigir(
            a_fecha_zona(solicitud["ventana_entrega"]) > datetime.now(config.ZONA),
            "La ventana de entrega de la solicitud ya venció.",
        )
        previo = con.execute(
            "SELECT id_despacho, estado_viaje FROM despacho WHERE id_solicitud=%s FOR UPDATE",
            (id_solicitud,),
        ).fetchone()
        exigir(
            not previo or previo["estado_viaje"] == "Cancelado",
            "Esta solicitud ya cuenta con un viaje programado o ejecutado.",
        )
        _, fof = _validar_recursos_asignables(
            con,
            id_tracto,
            id_semirremolque,
            id_conductor,
            solicitud["fecha"],
            solicitud["peso_tn"],
        )
        if previo:
            nuevo = con.execute(
                """UPDATE despacho
                SET id_tracto=%s, id_semirremolque=%s, id_conductor=%s,
                    estado_viaje='Programado', fof_porcentaje=%s, odometro_inicial_km=%s,
                    eta_estimado=NULL, eta_fecha_hora_calculo=NULL,
                    fecha_hora_ingreso_patio=NULL, fecha_hora_salida=NULL,
                    nro_gre=NULL, estado_gre='Pendiente'
                WHERE id_despacho=%s RETURNING id_despacho""",
                (
                    id_tracto,
                    id_semirremolque,
                    id_conductor,
                    fof,
                    odometro,
                    previo["id_despacho"],
                ),
            ).fetchone()
        else:
            nuevo = con.execute(
                """INSERT INTO despacho(id_solicitud,id_tracto,id_semirremolque,
                id_conductor,fof_porcentaje,odometro_inicial_km) VALUES(%s,%s,%s,%s,%s,%s)
                RETURNING id_despacho""",
                (id_solicitud, id_tracto, id_semirremolque, id_conductor, fof, odometro),
            ).fetchone()
        for tabla, identificador in (
            ("tracto", id_tracto),
            ("semirremolque", id_semirremolque),
            ("conductor", id_conductor),
        ):
            con.execute(
                f"UPDATE {tabla} SET estado='Asignado' WHERE id_{tabla}=%s", (identificador,)
            )
    return volver(f"/viajes/{nuevo['id_despacho']}", "Viaje programado.")


@router.post("/viajes/{id_viaje}/reasignar")
def reasignar(
    request: Request,
    id_viaje: int,
    id_tracto: int = Form(),
    id_semirremolque: int = Form(),
    id_conductor: int = Form(),
    odometro: int = Form(),
):
    permiso(request, "viajes")
    with conexion() as con:
        actual = viaje(id_viaje, con, True)
        exigir(
            actual["estado_viaje"] in ("Programado", "En patio"),
            "Solo se pueden reasignar recursos antes de autorizar la salida.",
        )
        pesaje_ok = con.execute(
            """SELECT peso_neto_kg/1000 AS peso_tn FROM pesaje_bascula
            WHERE id_despacho=%s AND resultado='Conforme'
            ORDER BY fecha_hora DESC, id_pesaje DESC LIMIT 1""",
            (id_viaje,),
        ).fetchone()
        peso_ref = float(pesaje_ok["peso_tn"]) if pesaje_ok else float(actual["peso_tn"])
        _, fof = _validar_recursos_asignables(
            con,
            id_tracto,
            id_semirremolque,
            id_conductor,
            actual["fecha_solicitud"],
            peso_ref,
            excluir_despacho=id_viaje,
        )
        anteriores = (
            ("tracto", actual["id_tracto"], "Disponible", id_tracto),
            ("semirremolque", actual["id_semirremolque"], "Disponible", id_semirremolque),
            ("conductor", actual["id_conductor"], "Habilitado", id_conductor),
        )
        con.execute(
            """UPDATE despacho
            SET id_tracto=%s, id_semirremolque=%s, id_conductor=%s,
                fof_porcentaje=%s, odometro_inicial_km=%s
            WHERE id_despacho=%s""",
            (id_tracto, id_semirremolque, id_conductor, fof, odometro, id_viaje),
        )
        for tabla, id_ant, estado_libre, id_nuevo in anteriores:
            if id_ant != id_nuevo:
                con.execute(
                    f"UPDATE {tabla} SET estado=%s WHERE id_{tabla}=%s", (estado_libre, id_ant)
                )
            con.execute(
                f"UPDATE {tabla} SET estado='Asignado' WHERE id_{tabla}=%s", (id_nuevo,)
            )
    return volver(f"/viajes/{id_viaje}", "Recursos del viaje actualizados.")


@router.post("/viajes/{id_viaje}/cancelar")
def cancelar(
    request: Request,
    id_viaje: int,
    motivo: str = Form(),
):
    permiso(request, "viajes")
    exigir(bool(motivo.strip()), "Indica el motivo de la cancelación del viaje.")
    with conexion() as con:
        actual = viaje(id_viaje, con, True)
        exigir(
            actual["estado_viaje"] in ("Programado", "En patio"),
            "Solo se pueden cancelar viajes programados o en patio antes de salir a ruta.",
        )
        con.execute(
            "UPDATE despacho SET estado_viaje='Cancelado' WHERE id_despacho=%s",
            (id_viaje,),
        )
        for tabla, estado_libre in (
            ("tracto", "Disponible"),
            ("semirremolque", "Disponible"),
            ("conductor", "Habilitado"),
        ):
            con.execute(
                f"UPDATE {tabla} SET estado=%s WHERE id_{tabla}=%s",
                (estado_libre, actual[f"id_{tabla}"]),
            )
        con.execute(
            """INSERT INTO incidencia(id_despacho,tipo,descripcion,accion_tomada)
            VALUES(%s,'Cancelación',%s,'Viaje cancelado y unidades liberadas')""",
            (id_viaje, motivo.strip()),
        )
    return volver(f"/viajes/{id_viaje}", "Viaje cancelado y recursos liberados.")


@router.get("/viajes/{id_viaje}")
def detalle(request: Request, id_viaje: int):
    datos = viaje(id_viaje)
    tablas = {
        tabla: consultar(f"SELECT * FROM {tabla} WHERE id_despacho=%s ORDER BY 1 DESC", (id_viaje,))
        for tabla in ("pesaje_bascula", "pod_entrega", "incidencia", "alerta")
    }
    precintos = consultar(
        """SELECT pr.* FROM precinto pr JOIN pesaje_bascula p USING(id_pesaje)
        WHERE p.id_despacho=%s ORDER BY pr.id_precinto DESC""",
        (id_viaje,),
    )
    verificacion = obtener(
        """SELECT v.* FROM verificacion_entrega v
        JOIN pod_entrega p USING(id_pod)
        WHERE p.id_despacho=%s""",
        (id_viaje,),
    )
    reasignables = (
        {
            "tractos_disp": consultar(
                "SELECT * FROM tracto WHERE estado='Disponible' OR id_tracto=%s ORDER BY placa",
                (datos["id_tracto"],),
            ),
            "semis_disp": consultar(
                "SELECT * FROM semirremolque WHERE estado='Disponible' OR id_semirremolque=%s ORDER BY capacidad_tn, placa",
                (datos["id_semirremolque"],),
            ),
            "conductores_disp": consultar(
                "SELECT * FROM conductor WHERE estado='Habilitado' OR id_conductor=%s ORDER BY nombre",
                (datos["id_conductor"],),
            ),
        }
        if datos["estado_viaje"] in ("Programado", "En patio")
        else {}
    )
    return mostrar(
        request,
        "detalle.html",
        viaje=datos,
        precintos=precintos,
        verificacion=verificacion,
        ahora=datetime.now(config.ZONA).strftime("%Y-%m-%dT%H:%M"),
        **reasignables,
        **tablas,
    )
