"""Recibir las consultas de la web y llamar a OE1, OE2 u OE3.

Los algoritmos y sus cálculos están en oe1.py, oe2.py y oe3.py.
Este archivo solamente conecta formularios, modelos y resultados guardados.
"""

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Form, Request
from ..config import ZONA
from ..db import conexion, guardar, obtener, viaje
from ..operacion.formularios import exigir, fecha_local, mostrar
from ..seguridad import autorizado, permiso
from . import oe1, oe2, oe3, datos
from .oe1 import entrada_eta, calcular_eta
from .oe2 import curva
from .almacen import cargar

router = APIRouter(dependencies=[Depends(autorizado)])


# OE1: estimar la llegada del viaje seleccionado.
@router.post("/viajes/{id_viaje}/eta")
def estimar_llegada(
    request: Request,
    id_viaje: int,
    salida: str = Form(),
    velocidad: float = Form(),
    restantes: float | None = Form(default=None),
    consulta: str = Form(default=""),
):
    permiso(request, "ml")
    # 1. Obtener el peso disponible: pesaje conforme o carga solicitada.
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
    # 2. Pedir la duración a XGBoost y convertirla en hora de llegada.
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


# OE2: mostrar el histórico y pronosticar una semana.
def pantalla_demanda(request, corredor, resultado=None, semana=""):
    corredores = datos.corredores()
    historial = datos.historial_demanda(corredor)
    recientes = datos.pronosticos_recientes()
    return mostrar(
        request,
        "demanda.html",
        corredores=corredores,
        corredor=corredor,
        historial=historial,
        recientes=recientes,
        resultado=resultado,
        semana=semana,
        grafico=curva(historial, resultado),
    )


@router.get("/demanda")
def consultar_demanda(request: Request, corredor: str = "Centro"):
    permiso(request, "ml")
    return pantalla_demanda(request, corredor)


@router.post("/demanda")
def pronosticar(
    request: Request, corredor: str = Form(), semana: str = Form(), feriados: int = Form()
):
    permiso(request, "ml")
    # 1. Usar el modelo ya entrenado del corredor elegido.
    modelos = cargar("oe2")
    exigir(corredor in modelos, "Falta historial suficiente para ese corredor.")
    resultado = oe2.predecir(modelos[corredor], semana, feriados)
    c = obtener("SELECT id_corredor FROM corredor WHERE nombre=%s", (corredor,))
    exigir(c is not None, "No existe el corredor seleccionado.")
    # FALSE es esencial: este resultado no se utilizará como una observación histórica.
    guardar(
        """INSERT INTO pronostico_demanda(id_corredor,semana_inicio,toneladas_estimadas,
        toneladas_min,toneladas_max,feriados_semana,dias_segunda_quincena,es_historico)
        VALUES(%s,%s,%s,%s,%s,%s,%s,FALSE)""",
        (
            c["id_corredor"],
            semana,
            resultado["toneladas"],
            resultado["minimo"],
            resultado["maximo"],
            feriados,
            resultado["dias_quincena"],
        ),
    )
    return pantalla_demanda(request, corredor, resultado, semana)


# OE3: evaluar la oportunidad de volver con carga hacia Callao.
def pantalla_retornos(request, resultado=None, seleccionado=None):
    viajes = datos.idas_para_evaluar()
    recientes = datos.evaluaciones_recientes()
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
    return pantalla_retornos(request)


@router.post("/retornos")
def estimar_retorno(
    request: Request,
    id_viaje: int = Form(),
    solicitudes: int = Form(),
    proporcion: float = Form(),
):
    permiso(request, "ml")
    # 1. Verificar la ruta y tomar el calendario de la entrega pactada.
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
    # 2. Consultar el árbol y guardar su probabilidad, sin cambiar la respuesta real.
    resultado = oe3.predecir(cargar("oe3"), entrada)
    guardar(
        """INSERT INTO prediccion_retorno(id_despacho,nivel_probabilidad,probabilidad)
        VALUES(%s,%s,%s)""",
        (id_viaje, resultado["nivel"], round(resultado["probabilidad"], 3)),
    )
    # La predicción NO cambia retorno_con_carga, que es el resultado observado del viaje.
    return pantalla_retornos(request, resultado, d)
