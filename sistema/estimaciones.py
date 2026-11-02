"""Consulta de ETA y guardado de su resultado en el viaje seleccionado."""

from datetime import datetime

from fastapi import APIRouter, Depends, Form, Request

from .calculos import calcular_eta, entrada_eta
from .config import ZONA
from .db import conexion, obtener
from .ml import oe1
from .ml.almacen import cargar
from .pantallas import exigir, fecha_local, mostrar, viaje
from .seguridad import autorizado, permiso

router = APIRouter(dependencies=[Depends(autorizado)])


@router.post("/viajes/{id_viaje}/eta")
def estimar(
    request: Request,
    id_viaje: int,
    salida: str = Form(),
    velocidad: float = Form(gt=0, le=90),
    restantes: float | None = Form(default=None),
    consulta: str = Form(default=""),
):
    permiso(request, "ml")
    d = viaje(id_viaje)
    p = obtener(
        """SELECT peso_neto_kg/1000 AS peso FROM pesaje_bascula
        WHERE id_despacho=%s AND resultado='Conforme'
        ORDER BY fecha_hora DESC,id_pesaje DESC LIMIT 1""",
        (id_viaje,),
    )
    peso = float(p["peso"] if p else d["peso_tn"])
    exigir(peso <= float(d["capacidad_tn"]), "El peso supera la capacidad de la unidad.")
    sal = fecha_local(salida)
    momento = fecha_local(consulta) if consulta else datetime.now(ZONA)
    total = oe1.predecir(cargar("oe1"), entrada_eta(d, peso, sal, velocidad))
    resultado = calcular_eta(total, float(d["distancia_km"]), sal, momento, restantes)
    retraso = max(0, int((resultado["llegada"] - d["ventana_entrega"]).total_seconds() / 60))
    # Se actualizan la estimación y su alerta; no la llegada real ni la respuesta del dataset.
    with conexion() as con:
        con.execute(
            "UPDATE despacho SET eta_estimado=%s,eta_fecha_hora_calculo=%s WHERE id_despacho=%s",
            (resultado["llegada"], momento, id_viaje),
        )
        if retraso and d["estado_viaje"] != "Cerrado":
            con.execute(
                """INSERT INTO alerta(id_despacho,tipo,mensaje,retraso_min)
                VALUES(%s,'ETA',%s,%s)""",
                (id_viaje, "ETA posterior a la entrega pactada", retraso),
            )
    return mostrar(
        request, "resultado_eta.html", viaje=d, peso=peso, retraso=retraso, resultado=resultado
    )
