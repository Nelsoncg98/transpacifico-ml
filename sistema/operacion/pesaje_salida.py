"""Control de patio: pesaje en báscula, precintos, GRE y autorización de salida."""

from fastapi import APIRouter, Depends, Form, Request

from .. import config
from ..db import conexion, viaje
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
    """Registra pesaje en báscula validando PBV máximo legal y capacidad útil del semirremolque."""
    # 1. Verificar rol autorizado y consistencia física entre peso bruto y tara.
    permiso(request, "patio")
    exigir(bruto >= tara, "El peso bruto debe ser mayor o igual a la tara vehicular.")

    with conexion() as con:
        datos_viaje = viaje(id_viaje, con, True)
        exigir(
            datos_viaje["estado_viaje"] in ("Programado", "En patio"),
            "Solo se permiten pesajes en viajes programados o en patio.",
        )
        # 2. Calcular peso neto (kg), comprobar PBV reglamentario (48 t) y capacidad de carga útil.
        neto = round(bruto - tara, 2)
        conforme = (
            bruto <= config.PESO_BRUTO_MAX_KG
            and neto <= float(datos_viaje["capacidad_tn"]) * 1000
        )
        # 3. Persistir trazabilidad de cada pesaje (si excede, queda en Reestiba y bloquea salida).
        resultado = "Conforme" if conforme else "Reestiba"
        con.execute(
            """INSERT INTO pesaje_bascula(id_despacho,fecha_hora,tara_kg,
            peso_bruto_kg,peso_neto_kg,resultado) VALUES(%s,%s,%s,%s,%s,%s)""",
            (id_viaje, fecha_local(ingreso), tara, bruto, neto, resultado),
        )
        # 4. Actualizar estado a En patio y recalcular FOF real a partir del peso neto medido.
        con.execute(
            """UPDATE despacho SET estado_viaje='En patio',
            fecha_hora_ingreso_patio=COALESCE(fecha_hora_ingreso_patio,%s),
            fof_porcentaje=%s WHERE id_despacho=%s""",
            (
                fecha_local(ingreso),
                round(neto / 1000 / float(datos_viaje["capacidad_tn"]) * 100, 2),
                id_viaje,
            ),
        )
    return volver(f"/viajes/{id_viaje}", "Pesaje registrado: " + resultado)


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
        datos_viaje = viaje(id_viaje, con, True)
        exigir(datos_viaje["estado_viaje"] == "En patio", "El viaje debe estar en patio.")
        pesaje = con.execute(
            """SELECT * FROM pesaje_bascula WHERE id_despacho=%s
            ORDER BY fecha_hora DESC,id_pesaje DESC LIMIT 1""",
            (id_viaje,),
        ).fetchone()
        exigir(pesaje and pesaje["resultado"] == "Conforme", "Primero realiza un pesaje conforme.")
        for numero in numeros:
            con.execute(
                "INSERT INTO precinto(id_pesaje,numero) VALUES(%s,%s)",
                (pesaje["id_pesaje"], numero),
            )
        # Se registra una GRE ya emitida. Este prototipo no timbra documentos ante SUNAT.
        con.execute(
            "UPDATE despacho SET nro_gre=%s,estado_gre='Emitida' WHERE id_despacho=%s",
            (numero_gre.strip(), id_viaje),
        )
    return volver(f"/viajes/{id_viaje}", "GRE y precintos registrados.")


@router.post("/viajes/{id_viaje}/salir")
def salir(request: Request, id_viaje: int, salida: str = Form()):
    permiso(request, "patio")
    # 1. Exigir estado en patio, GRE, pesaje conforme y precintos del pesaje actual.
    with conexion() as con:
        datos_viaje = viaje(id_viaje, con, True)
        exigir(
            datos_viaje["estado_viaje"] == "En patio" and datos_viaje["estado_gre"] == "Emitida",
            "Se requiere viaje en patio y GRE emitida.",
        )
        pesaje = con.execute(
            """SELECT * FROM pesaje_bascula WHERE id_despacho=%s
            ORDER BY fecha_hora DESC,id_pesaje DESC LIMIT 1""",
            (id_viaje,),
        ).fetchone()
        exigir(pesaje and pesaje["resultado"] == "Conforme", "El último pesaje debe ser conforme.")
        exigir(
            con.execute(
                "SELECT 1 FROM precinto WHERE id_pesaje=%s", (pesaje["id_pesaje"],)
            ).fetchone(),
            "Faltan los precintos del pesaje actual.",
        )
        # 2. Revisar la fecha; guardar la salida real y pasar a En tránsito.
        fecha = fecha_local(salida)
        exigir(fecha >= pesaje["fecha_hora"], "La salida no puede ser anterior al pesaje.")
        con.execute(
            """UPDATE despacho SET estado_viaje='En tránsito',fecha_hora_salida=%s
            WHERE id_despacho=%s""",
            (fecha, id_viaje),
        )
    return volver(f"/viajes/{id_viaje}", "Salida autorizada.")
