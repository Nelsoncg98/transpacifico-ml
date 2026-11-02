"""Lecturas de SQL para entrenar los modelos y mostrar sus consultas en la web."""

import pandas as pd

from ..db import consultar


def cargar(nombre):
    from pathlib import Path

    sql = (Path(__file__).parent / "sql" / f"{nombre}.sql").read_text()
    return pd.DataFrame(consultar(sql))


def corredores():
    return consultar("SELECT id_corredor,nombre FROM corredor ORDER BY nombre")


def historial_demanda(corredor):
    # El histórico excluye los pronósticos guardados por la página.
    return consultar(
        """SELECT p.* FROM pronostico_demanda p
        JOIN corredor c USING(id_corredor) WHERE c.nombre=%s AND es_historico=TRUE
        ORDER BY semana_inicio""",
        (corredor,),
    )


def pronosticos_recientes():
    return consultar("""SELECT p.*,c.nombre FROM pronostico_demanda p
        JOIN corredor c USING(id_corredor) WHERE es_historico=FALSE
        ORDER BY id_pronostico DESC LIMIT 10""")


def idas_para_evaluar():
    # OE3 corresponde al regreso de una ida desde Callao, no a un viaje que ya vuelve.
    return consultar("""SELECT d.id_despacho,s.destino,s.ventana_entrega,
        d.estado_viaje,d.solicitudes_compatibles,d.proporcion_retornos_previos
        FROM despacho d JOIN solicitud_carga s USING(id_solicitud)
        WHERE s.origen='Callao' AND s.destino IN ('Huancayo','Trujillo')
        ORDER BY (d.estado_viaje<>'Cerrado') DESC,d.id_despacho DESC LIMIT 100""")


def evaluaciones_recientes():
    return consultar("""SELECT p.*,s.destino FROM prediccion_retorno p
        JOIN despacho d USING(id_despacho) JOIN solicitud_carga s USING(id_solicitud)
        ORDER BY id_prediccion_retorno DESC LIMIT 15""")
