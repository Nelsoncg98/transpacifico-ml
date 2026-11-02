"""Programación de recursos y consulta del detalle de cada viaje."""

from datetime import datetime

from fastapi import APIRouter, Depends, Form, Request

from .config import ZONA
from .calculos import limites_velocidad
from .db import conexion, consultar
from .pantallas import exigir, mostrar, viaje, volver
from .seguridad import autorizado, permiso

router = APIRouter(dependencies=[Depends(autorizado)])


@router.get("/viajes")
def listar(request: Request, pagina: int = 1, estado: str = ""):
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
    id_solicitud: int = Form(gt=0),
    id_tracto: int = Form(gt=0),
    id_semirremolque: int = Form(gt=0),
    id_conductor: int = Form(gt=0),
    odometro: int = Form(ge=0),
):
    permiso(request, "viajes")
    with conexion() as con:
        s = con.execute(
            "SELECT * FROM solicitud_carga WHERE id_solicitud=%s FOR UPDATE", (id_solicitud,)
        ).fetchone()
        exigir(s and s["estado"] == "Aceptada", "La solicitud debe estar aceptada.")
        recursos = {}
        for tabla, identificador in (
            ("tracto", id_tracto),
            ("semirremolque", id_semirremolque),
            ("conductor", id_conductor),
        ):
            r = con.execute(
                f"SELECT * FROM {tabla} WHERE id_{tabla}=%s FOR UPDATE", (identificador,)
            ).fetchone()
            exigir(
                r and r["estado"] in ("Disponible", "Habilitado"),
                f"El recurso {tabla} no está disponible.",
            )
            ocupado = con.execute(
                f"""SELECT 1 FROM despacho WHERE id_{tabla}=%s
                AND estado_viaje NOT IN ('Cerrado','Cancelado')""",
                (identificador,),
            ).fetchone()
            exigir(not ocupado, f"El recurso {tabla} ya tiene un viaje activo.")
            recursos[tabla] = r
        c = recursos["conductor"]
        exigir(
            c["categoria_brevete"] == "A-IIIc"
            and c["fecha_vencimiento"] >= max(s["fecha"], datetime.now(ZONA).date()),
            "El brevete no está habilitado.",
        )
        capacidad = float(recursos["semirremolque"]["capacidad_tn"])
        exigir(
            capacidad > 0 and float(s["peso_tn"]) <= capacidad,
            "La carga supera la capacidad del semirremolque.",
        )
        fof = round(float(s["peso_tn"]) / capacidad * 100, 2)
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


@router.get("/viajes/{id_viaje}")
def detalle(request: Request, id_viaje: int):
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
        limites=limites_velocidad(datos["distancia_km"]),
        **tablas,
    )
