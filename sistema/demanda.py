"""Pronóstico de una semana y consulta del histórico de demanda."""

from fastapi import APIRouter, Depends, Form, Request

from .calculos import curva
from .db import consultar, guardar, obtener
from .ml import oe2
from .ml.almacen import cargar
from .pantallas import exigir, mostrar
from .seguridad import autorizado, permiso

router = APIRouter(dependencies=[Depends(autorizado)])


def pantalla(request, corredor, resultado=None, semana=""):
    corredores = consultar("SELECT id_corredor,nombre FROM corredor ORDER BY nombre")
    historial = consultar(
        """SELECT p.* FROM pronostico_demanda p
        JOIN corredor c USING(id_corredor) WHERE c.nombre=%s AND es_historico=TRUE
        ORDER BY semana_inicio""",
        (corredor,),
    )
    recientes = consultar("""SELECT p.*,c.nombre FROM pronostico_demanda p
        JOIN corredor c USING(id_corredor) WHERE es_historico=FALSE
        ORDER BY id_pronostico DESC LIMIT 10""")
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
    return pantalla(request, corredor)


@router.post("/demanda")
def pronosticar(
    request: Request, corredor: str = Form(), semana: str = Form(), feriados: int = Form(ge=0, le=7)
):
    permiso(request, "ml")
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
    return pantalla(request, corredor, resultado, semana)
