"""Pesaje, precintos y salida: las condiciones se verifican también en el servidor."""

from fastapi import APIRouter, Depends, Form, Request

from ..db import viaje, conexion
from .formularios import exigir, fecha_local, volver
from ..seguridad import autorizado, permiso

router = APIRouter(dependencies=[Depends(autorizado)])


@router.post("/viajes/{id_viaje}/pesar")
def pesar(
    request: Request,
    id_viaje: int,
    tara: float = Form(),
    bruto: float = Form(),
    ingreso: str = Form(),
):
    # 1. Revisar que el viaje pueda pesarse y que bruto no sea menor que tara.
    permiso(request, "patio")
    exigir(bruto >= tara, "El peso bruto debe ser mayor o igual a la tara.")
    with conexion() as con:
        d = viaje(id_viaje, con, True)
        exigir(
            d["estado_viaje"] in ("Programado", "En patio"),
            "Solo se pesan viajes programados o en patio.",
        )
        # 2. Calcular el neto y comprobar los límites de peso.
        neto = round(bruto - tara, 2)
        conforme = bruto <= 48000 and neto <= float(d["capacidad_tn"]) * 1000
        # 3. Conservar cada pesaje; un exceso exige reestiba antes de salir.
        resultado = "Conforme" if conforme else "Reestiba"
        con.execute(
            """INSERT INTO pesaje_bascula(id_despacho,fecha_hora,tara_kg,
            peso_bruto_kg,peso_neto_kg,resultado) VALUES(%s,%s,%s,%s,%s,%s)""",
            (id_viaje, fecha_local(ingreso), tara, bruto, neto, resultado),
        )
        con.execute(
            """UPDATE despacho SET estado_viaje='En patio',
            fecha_hora_ingreso_patio=COALESCE(fecha_hora_ingreso_patio,%s),
            fof_porcentaje=%s WHERE id_despacho=%s""",
            (
                fecha_local(ingreso),
                round(neto / 1000 / float(d["capacidad_tn"]) * 100, 2),
                id_viaje,
            ),
        )
    return volver(f"/viajes/{id_viaje}", "Pesaje: " + resultado)


@router.post("/viajes/{id_viaje}/documentar")
def documentar(
    request: Request,
    id_viaje: int,
    numero_gre: str = Form(),
    precintos: str = Form(),
):
    permiso(request, "patio")
    # 1. Separar y revisar los precintos ingresados.
    numeros = list(dict.fromkeys(n.strip() for n in precintos.split(",") if n.strip()))
    # 2. Exigir el último pesaje conforme y registrar la GRE ya emitida.
    with conexion() as con:
        d = viaje(id_viaje, con, True)
        exigir(d["estado_viaje"] == "En patio", "El viaje debe estar en patio.")
        p = con.execute(
            """SELECT * FROM pesaje_bascula WHERE id_despacho=%s
            ORDER BY fecha_hora DESC,id_pesaje DESC LIMIT 1""",
            (id_viaje,),
        ).fetchone()
        exigir(p and p["resultado"] == "Conforme", "Primero realiza un pesaje conforme.")
        for numero in numeros:
            con.execute(
                "INSERT INTO precinto(id_pesaje,numero) VALUES(%s,%s)", (p["id_pesaje"], numero)
            )
        # Se registra una GRE ya emitida. Este prototipo no timbra documentos ante SUNAT.
        con.execute(
            "UPDATE despacho SET nro_gre=%s,estado_gre='Emitida' WHERE id_despacho=%s",
            (numero_gre.strip(), id_viaje),
        )
    return volver(f"/viajes/{id_viaje}", "GRE y precintos registrados.")


@router.post("/viajes/{id_viaje}/salir")
def salir(request: Request, id_viaje: int, salida: str = Form(), velocidad: float = Form()):
    permiso(request, "patio")
    # 1. Exigir estado en patio, GRE, pesaje conforme y precintos del pesaje actual.
    with conexion() as con:
        d = viaje(id_viaje, con, True)
        exigir(
            d["estado_viaje"] == "En patio" and d["estado_gre"] == "Emitida",
            "Se requiere viaje en patio y GRE emitida.",
        )
        p = con.execute(
            """SELECT * FROM pesaje_bascula WHERE id_despacho=%s
            ORDER BY fecha_hora DESC,id_pesaje DESC LIMIT 1""",
            (id_viaje,),
        ).fetchone()
        exigir(p and p["resultado"] == "Conforme", "El último pesaje debe ser conforme.")
        exigir(
            con.execute("SELECT 1 FROM precinto WHERE id_pesaje=%s", (p["id_pesaje"],)).fetchone(),
            "Faltan los precintos del pesaje actual.",
        )
        # 2. Revisar la fecha; guardar la salida real y pasar a En tránsito.
        fecha = fecha_local(salida)
        exigir(fecha >= p["fecha_hora"], "La salida no puede ser anterior al pesaje.")
        con.execute(
            """UPDATE despacho SET estado_viaje='En tránsito',fecha_hora_salida=%s,
            velocidad_media_estimada_kmh=%s WHERE id_despacho=%s""",
            (fecha, velocidad, id_viaje),
        )
    return volver(f"/viajes/{id_viaje}", "Salida autorizada.")
