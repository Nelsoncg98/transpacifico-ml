"""Recibir las consultas de la web y llamar a OE1, OE2 u OE3.

Los algoritmos y sus cálculos están en oe1.py, oe2.py y oe3.py.
Este archivo solamente conecta formularios, modelos y resultados guardados.
"""

from datetime import datetime, timezone
import json
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
    restantes: float | None = Form(default=None),
    consulta: str = Form(default=""),
):
    permiso(request, "ml")
    # 1. Obtener el peso disponible: pesaje conforme o carga solicitada.
    datos_viaje = viaje(id_viaje)
    # Solo se estima mientras el viaje sigue pendiente o en tránsito.
    exigir(datos_viaje["estado_viaje"] in ("Programado", "En patio", "En tránsito"),
           "La ETA no está disponible para el estado actual del viaje.")
    # Antes de salir, el plazo de entrega todavía debe estar vigente.
    exigir(datos_viaje["estado_viaje"] == "En tránsito"
           or datos_viaje["ventana_entrega"] > datetime.now(ZONA),
           "La entrega pactada ya venció. Revisa las fechas antes de estimar la llegada.")
    restantes = restantes if datos_viaje["estado_viaje"] == "En tránsito" else None  # Solo en ruta.
    pesaje = obtener(
        """SELECT peso_neto_kg/1000 AS peso FROM pesaje_bascula
        WHERE id_despacho=%s AND resultado='Conforme'
        ORDER BY fecha_hora DESC,id_pesaje DESC LIMIT 1""",
        (id_viaje,),
    )
    peso = float(pesaje["peso"] if pesaje else datos_viaje["peso_tn"])
    exigir(peso <= float(datos_viaje["capacidad_tn"]), "El peso supera la capacidad de la unidad.")
    sal = datos_viaje["fecha_hora_salida"] or fecha_local(salida)  # Priorizar la salida real.
    momento = fecha_local(consulta) if consulta else datetime.now(ZONA)
    # 2. Pedir la duración a XGBoost y convertirla en hora de llegada.
    total = oe1.predecir(cargar("oe1"), entrada_eta(datos_viaje, peso, sal))
    resultado = calcular_eta(total, float(datos_viaje["distancia_km"]), sal, momento, restantes)
    retraso = max(
        0, int((resultado["llegada"] - datos_viaje["ventana_entrega"]).total_seconds() / 60)
    )
    # Se actualizan la estimación y su alerta; no la llegada real ni la respuesta del dataset.
    with conexion() as con:
        con.execute(
            "UPDATE despacho SET eta_estimado=%s,eta_fecha_hora_calculo=%s WHERE id_despacho=%s",
            (resultado["llegada"], momento, id_viaje),
        )
        if retraso and datos_viaje["estado_viaje"] != "Cerrado":
            con.execute(
                """INSERT INTO alerta(id_despacho,tipo,mensaje,retraso_min)
                VALUES(%s,'ETA',%s,%s)""",
                (id_viaje, "ETA posterior a la entrega pactada", retraso),
            )
    return mostrar(
        request,
        "resultado_eta.html",
        viaje=datos_viaje,
        peso=peso,
        retraso=retraso,
        resultado=resultado,
    )


# OE2: mostrar el histórico y pronosticar una semana.
def pantalla_demanda(request, corredor, resultado=None, semana=""):
    corredores = datos.corredores()
    historial = datos.historial_demanda(corredor) if corredor else []
    recientes = datos.pronosticos_recientes()
    semana_sugerida = semana or (datos.siguiente_semana_demanda(corredor) if corredor else "")
    serie_demanda = {
        "corredor": corredor,
        "historial": [
            {
                "semana": str(h["semana_inicio"]),
                "toneladas": round(float(h["toneladas_estimadas"]), 2),
                "feriados": int(h["feriados_semana"] or 0),
                "dias_quincena": int(h["dias_segunda_quincena"] or 0),
            }
            for h in historial
        ],
        "recientes": [
            {
                "semana": str(r["semana_inicio"]),
                "corredor": str(r["nombre"]),
                "toneladas": round(float(r["toneladas_estimadas"]), 2),
                "minimo": round(float(r["toneladas_min"]), 2),
                "maximo": round(float(r["toneladas_max"]), 2),
            }
            for r in recientes
            if r["nombre"] == corredor
        ],
        "actual": resultado,
    }
    return mostrar(
        request,
        "demanda.html",
        corredores=corredores,
        corredor=corredor,
        historial=historial,
        recientes=recientes,
        resultado=resultado,
        semana=semana,
        semana_sugerida=semana_sugerida,
        grafico=curva(historial, resultado),
        serie_demanda_json=json.dumps(serie_demanda, ensure_ascii=False),
    )


@router.get("/demanda")
def consultar_demanda(request: Request, corredor: str = ""):
    permiso(request, "ml")
    if not corredor:
        corredores = datos.corredores()
        corredor = corredores[0]["nombre"] if corredores else ""
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
    datos_corredor = obtener("SELECT id_corredor FROM corredor WHERE nombre=%s", (corredor,))
    exigir(datos_corredor is not None, "No existe el corredor seleccionado.")
    # FALSE es esencial: este resultado no se utilizará como una observación histórica.
    guardar(
        """INSERT INTO pronostico_demanda(id_corredor,semana_inicio,toneladas_estimadas,
        toneladas_min,toneladas_max,feriados_semana,dias_segunda_quincena,es_historico)
        VALUES(%s,%s,%s,%s,%s,%s,%s,FALSE)""",
        (
            datos_corredor["id_corredor"],
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
def pantalla_retornos(request, resultado=None, seleccionado=None, valores_form=None):
    viajes = datos.idas_para_evaluar()
    recientes = datos.evaluaciones_recientes()
    serie_retornos = {
        "actual": {
            "id_despacho": int(seleccionado["id_despacho"]),
            "destino": str(seleccionado["destino"]),
            "probabilidad": round(float(resultado["probabilidad"]) * 100, 1),
            "vacio": round((1.0 - float(resultado["probabilidad"])) * 100, 1),
            "nivel": resultado["nivel"],
        }
        if resultado and seleccionado
        else None,
        "recientes": [
            {
                "id_despacho": int(r["id_despacho"]),
                "destino": str(r["destino"]),
                "nivel": str(r["nivel_probabilidad"]),
                "probabilidad": round(float(r["probabilidad"]) * 100, 1),
            }
            for r in reversed(recientes)
        ],
    }
    return mostrar(
        request,
        "retornos.html",
        viajes=viajes,
        recientes=recientes,
        resultado=resultado,
        seleccionado=seleccionado,
        valores_form=valores_form,
        serie_retornos_json=json.dumps(serie_retornos, ensure_ascii=False),
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
    tasa_pct: float | None = Form(default=None),
    proporcion: float | None = Form(default=None),
):
    permiso(request, "ml")
    exigir(0 <= solicitudes <= 5, "Las solicitudes compatibles deben estar entre 0 y 5.")
    if tasa_pct is not None:
        exigir(
            0.0 <= tasa_pct <= 100.0,
            "La tasa reciente con carga debe estar entre 0 y 100 %.",
        )
        prop_real = round(float(tasa_pct) / 100.0, 4)
    elif proporcion is not None:
        exigir(0.0 <= proporcion <= 1.0, "La proporción debe estar entre 0 y 1.")
        prop_real = round(float(proporcion), 4)
    else:
        raise ValueError("Indica la tasa reciente de retorno con carga (0 a 100 %).")

    # 1. Cargar modelo entrenado y validar que el destino figure en sus categorías conocidas.
    paquete_oe3 = cargar("oe3")
    destinos_entrenados = {
        col.removeprefix("origen_retorno_")
        for col in paquete_oe3["columnas"]
        if col.startswith("origen_retorno_")
    }
    datos_viaje = viaje(id_viaje)
    exigir(
        datos_viaje["origen"] != datos_viaje["destino"]
        and datos_viaje["destino"] in destinos_entrenados,
        "OE3 evalúa retornos de despachos hacia ciudades con histórico entrenado.",
    )
    entrega = datos_viaje["ventana_entrega"].astimezone(timezone.utc)
    entrada = {
        "origen_retorno": datos_viaje["destino"],
        "dia_entrega_pactada": entrega.isoweekday(),
        "quincena_entrega_pactada": 1 if entrega.day <= 15 else 2,
        "solicitudes_compatibles": solicitudes,
        "proporcion_retornos_previos": prop_real,
    }
    # 2. Consultar el árbol y guardar su probabilidad, sin cambiar la respuesta real.
    resultado = oe3.predecir(paquete_oe3, entrada)
    guardar(
        """INSERT INTO prediccion_retorno(id_despacho,nivel_probabilidad,probabilidad)
        VALUES(%s,%s,%s)""",
        (id_viaje, resultado["nivel"], round(resultado["probabilidad"], 3)),
    )
    # La predicción NO cambia retorno_con_carga, que es el resultado observado del viaje.
    return pantalla_retornos(
        request,
        resultado,
        datos_viaje,
        valores_form={
            "id_viaje": id_viaje,
            "solicitudes": solicitudes,
            "tasa_pct": int(round(prop_real * 100)),
        },
    )
