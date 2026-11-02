"""Oportunidad de retorno hacia Callao, separada de su resultado real 0/1."""

from datetime import timezone

from fastapi import APIRouter, Depends, Form, Request

from .db import consultar, guardar
from .ml import oe3
from .ml.almacen import cargar
from .pantallas import exigir, mostrar, viaje
from .seguridad import autorizado, permiso

router = APIRouter(dependencies=[Depends(autorizado)])


def pantalla(request, resultado=None, seleccionado=None):
    viajes = consultar("""SELECT d.id_despacho,s.destino,s.ventana_entrega,
        d.estado_viaje,d.solicitudes_compatibles,d.proporcion_retornos_previos
        FROM despacho d JOIN solicitud_carga s USING(id_solicitud)
        WHERE s.origen='Callao' AND s.destino IN ('Huancayo','Trujillo')
        ORDER BY (d.estado_viaje<>'Cerrado') DESC,d.id_despacho DESC LIMIT 100""")
    recientes = consultar("""SELECT p.*,s.destino FROM prediccion_retorno p
        JOIN despacho d USING(id_despacho) JOIN solicitud_carga s USING(id_solicitud)
        ORDER BY id_prediccion_retorno DESC LIMIT 15""")
    return mostrar(
        request,
        "retornos.html",
        viajes=viajes,
        recientes=recientes,
        resultado=resultado,
        seleccionado=seleccionado,
    )


@router.get("/retornos")
def consultar_retornos(request: Request):
    permiso(request, "ml")
    return pantalla(request)


@router.post("/retornos")
def estimar(
    request: Request,
    id_viaje: int = Form(gt=0),
    solicitudes: int = Form(ge=0, le=5),
    proporcion: float = Form(ge=0, le=1),
):
    permiso(request, "ml")
    d = viaje(id_viaje)
    exigir(
        d["origen"] == "Callao" and d["destino"] in ("Huancayo", "Trujillo"),
        "OE3 evalúa el retorno desde Huancayo o Trujillo hacia Callao.",
    )
    entrega = d["ventana_entrega"].astimezone(timezone.utc)
    entrada = {
        "origen_retorno": d["destino"],
        "dia_entrega_pactada": entrega.isoweekday(),
        "quincena_entrega_pactada": 1 if entrega.day <= 15 else 2,
        "solicitudes_compatibles": solicitudes,
        "proporcion_retornos_previos": proporcion,
    }
    resultado = oe3.predecir(cargar("oe3"), entrada)
    guardar(
        """INSERT INTO prediccion_retorno(id_despacho,nivel_probabilidad,probabilidad)
        VALUES(%s,%s,%s)""",
        (id_viaje, resultado["nivel"], round(resultado["probabilidad"], 3)),
    )
    # La predicción NO cambia retorno_con_carga, que es el resultado observado del viaje.
    return pantalla(request, resultado, d)
