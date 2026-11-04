"""Programación de recursos y consulta del detalle de cada viaje."""

from datetime import datetime

from fastapi import APIRouter, Depends, Form, Request

from ..config import ZONA
from ..db import viaje, conexion, consultar
from .formularios import exigir, mostrar, volver
from ..seguridad import autorizado, permiso

router = APIRouter(dependencies=[Depends(autorizado)])


@router.get("/viajes")
def listar(request: Request, pagina: int = 1, estado: str = ""):
    # Mostrar los viajes y las solicitudes aceptadas aún sin asignación.
    filas = consultar(
        """SELECT d.*,s.origen,s.destino,t.placa FROM despacho d
        JOIN solicitud_carga s USING(id_solicitud) JOIN tracto t USING(id_tracto)
        WHERE (%s='' OR d.estado_viaje=%s) ORDER BY d.id_despacho DESC
        LIMIT 25 OFFSET %s""",
        (estado, estado, (max(1, pagina) - 1) * 25),
    )
    pendientes = consultar("""SELECT s.* FROM solicitud_carga s WHERE estado='Aceptada'
        AND NOT EXISTS(SELECT 1 FROM despacho d WHERE d.id_solicitud=s.id_solicitud)
        ORDER BY id_solicitud DESC LIMIT 100""")
    catalogos = {
        nombre: consultar(f"SELECT * FROM {nombre} ORDER BY 1")
        for nombre in ("tracto", "semirremolque", "conductor")
    }
    return mostrar(
        request,
        "viajes.html",
        filas=filas,
        pendientes=pendientes,
        pagina=max(1, pagina),
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
    # 1. Bloquear la solicitud mientras se confirma la asignación.
    with conexion() as con:
        solicitud = con.execute(
            "SELECT * FROM solicitud_carga WHERE id_solicitud=%s FOR UPDATE", (id_solicitud,)
        ).fetchone()
        exigir(solicitud and solicitud["estado"] == "Aceptada", "La solicitud debe estar aceptada.")
        # 2. Comprobar disponibilidad del tracto, semirremolque y conductor.
        recursos = {}
        for tabla, identificador in (
            ("tracto", id_tracto),
            ("semirremolque", id_semirremolque),
            ("conductor", id_conductor),
        ):
            recurso = con.execute(
                f"SELECT * FROM {tabla} WHERE id_{tabla}=%s FOR UPDATE", (identificador,)
            ).fetchone()
            exigir(
                recurso and recurso["estado"] in ("Disponible", "Habilitado"),
                f"El recurso {tabla} no está disponible.",
            )
            ocupado = con.execute(
                f"""SELECT 1 FROM despacho WHERE id_{tabla}=%s
                AND estado_viaje NOT IN ('Cerrado','Cancelado')""",
                (identificador,),
            ).fetchone()
            exigir(not ocupado, f"El recurso {tabla} ya tiene un viaje activo.")
            recursos[tabla] = recurso
        # 3. Verificar categoría y vigencia del brevete para la fecha del servicio.
        conductor = recursos["conductor"]
        exigir(
            conductor["categoria_brevete"] == "A-IIIc"
            and conductor["fecha_vencimiento"]
            >= max(solicitud["fecha"], datetime.now(ZONA).date()),
            "El brevete no está habilitado.",
        )
        # 4. Comprobar la capacidad y calcular el porcentaje de ocupación.
        capacidad = float(recursos["semirremolque"]["capacidad_tn"])
        exigir(
            capacidad > 0 and float(solicitud["peso_tn"]) <= capacidad,
            "La carga supera la capacidad del semirremolque.",
        )
        fof = round(float(solicitud["peso_tn"]) / capacidad * 100, 2)
        # 5. Crear el despacho y recuperar su identificador generado por SQL.
        nuevo = con.execute(
            """INSERT INTO despacho(id_solicitud,id_tracto,id_semirremolque,
            id_conductor,fof_porcentaje,odometro_inicial_km) VALUES(%s,%s,%s,%s,%s,%s)
            RETURNING id_despacho""",
            (id_solicitud, id_tracto, id_semirremolque, id_conductor, fof, odometro),
        ).fetchone()
        # 6. Marcar los recursos como asignados al confirmar el viaje.
        for tabla, identificador in (
            ("tracto", id_tracto),
            ("semirremolque", id_semirremolque),
            ("conductor", id_conductor),
        ):
            con.execute(
                f"UPDATE {tabla} SET estado='Asignado' WHERE id_{tabla}=%s", (identificador,)
            )
    return volver(f"/viajes/{nuevo['id_despacho']}", "Viaje programado.")


@router.get("/viajes/{id_viaje}")
def detalle(request: Request, id_viaje: int):
    # Cargar el despacho y sus pesajes, entrega, incidencias y precintos.
    datos = viaje(id_viaje)
    tablas = {
        tabla: consultar(f"SELECT * FROM {tabla} WHERE id_despacho=%s ORDER BY 1 DESC", (id_viaje,))
        for tabla in ("pesaje_bascula", "pod_entrega", "incidencia", "precinto")
        if tabla != "precinto"
    }
    precintos = consultar(
        """SELECT pr.* FROM precinto pr JOIN pesaje_bascula p USING(id_pesaje)
        WHERE p.id_despacho=%s ORDER BY pr.id_precinto DESC""",
        (id_viaje,),
    )
    return mostrar(
        request,
        "detalle.html",
        viaje=datos,
        precintos=precintos,
        ahora=datetime.now(ZONA).strftime("%Y-%m-%dT%H:%M"),
        **tablas,
    )
