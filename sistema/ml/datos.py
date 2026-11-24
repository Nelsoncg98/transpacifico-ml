"""Lecturas dinámicas desde PostgreSQL para entrenamiento y consultas web de ML."""

from collections import defaultdict
from datetime import date, datetime, timedelta
import pandas as pd

from .. import config, db


def cargar(nombre):
    """Carga el dataset de entrenamiento ejecutando el archivo SQL correspondiente."""
    from pathlib import Path

    sql = (Path(__file__).parent / "sql" / f"{nombre}.sql").read_text(encoding="utf-8")
    return pd.DataFrame(db.consultar(sql))


def corredores():
    """Devuelve los corredores logísticos activos registrados en PostgreSQL."""
    return db.consultar("SELECT id_corredor, nombre FROM corredor ORDER BY nombre")


def historial_demanda(corredor):
    """Consulta la serie histórica de toneladas semanales (excluye predicciones futuras)."""
    return db.consultar(
        """SELECT p.* FROM pronostico_demanda p
        JOIN corredor c USING(id_corredor) WHERE c.nombre=%s AND es_historico=TRUE
        ORDER BY semana_inicio""",
        (corredor,),
    )


def pronosticos_recientes():
    """Obtiene los últimos pronósticos operativos generados por Prophet desde la web."""
    return db.consultar("""SELECT p.*, c.nombre FROM pronostico_demanda p
        JOIN corredor c USING(id_corredor) WHERE es_historico=FALSE
        ORDER BY id_pronostico DESC LIMIT 10""")


def siguiente_semana_demanda(corredor):
    """Sugiere el lunes inmediato posterior al último registro histórico del corredor."""
    fila = db.obtener(
        """SELECT MAX(semana_inicio) AS ultima
        FROM pronostico_demanda p
        JOIN corredor c USING(id_corredor)
        WHERE c.nombre=%s AND p.es_historico=TRUE""",
        (corredor,),
    )
    if fila and fila["ultima"]:
        base = date.fromisoformat(str(fila["ultima"])[:10]) + timedelta(days=7)
    else:
        hoy = datetime.now(config.ZONA).date()
        base = hoy + timedelta(days=(7 - hoy.weekday()) % 7 or 7)
    # Ajustar siempre al lunes de esa semana operativa.
    ajuste_lunes = (7 - base.weekday()) % 7
    return (base + timedelta(days=ajuste_lunes)).isoformat()


def idas_para_evaluar():
    """Lista despachos de ida y calcula métricas sugeridas de retorno directamente desde SQL."""
    # 1. Identificar dinámicamente la sede principal de origen con mayor volumen en SQL.
    hub = db.obtener(
        "SELECT origen, count(*) AS total FROM solicitud_carga GROUP BY origen ORDER BY total DESC LIMIT 1"
    )
    if not hub:
        return []
    origen_base = str(hub["origen"])

    # 2. Recuperar despachos de ida vigentes y cerrados desde la sede principal.
    viajes = db.consultar(
        """SELECT d.id_despacho, s.origen, s.destino, s.ventana_entrega,
        d.estado_viaje, d.solicitudes_compatibles, d.proporcion_retornos_previos
        FROM despacho d JOIN solicitud_carga s USING(id_solicitud)
        WHERE s.origen=%s AND s.destino <> %s AND d.estado_viaje <> 'Cancelado'
        ORDER BY (d.estado_viaje<>'Cerrado') DESC, d.id_despacho DESC LIMIT 100""",
        (origen_base, origen_base),
    )

    # 3. Contar solicitudes abiertas compatibles por par (provincia -> sede principal).
    abiertas_sql = db.consultar(
        """SELECT s.origen, s.destino, count(*) AS abiertas
        FROM solicitud_carga s
        WHERE s.estado IN ('Registrada', 'Aceptada')
          AND NOT EXISTS (
              SELECT 1 FROM despacho d
              WHERE d.id_solicitud = s.id_solicitud AND d.estado_viaje <> 'Cancelado'
          )
        GROUP BY s.origen, s.destino"""
    )
    mapa_abiertas = {
        (str(a["origen"]), str(a["destino"])): int(a["abiertas"]) for a in abiertas_sql
    }

    # 4. Calcular tasa reciente de retorno con carga (últimos 10 viajes cerrados por destino).
    cerrados_sql = db.consultar(
        """SELECT s.destino, d.retorno_con_carga
        FROM despacho d JOIN solicitud_carga s USING(id_solicitud)
        WHERE s.origen=%s AND d.estado_viaje='Cerrado' AND d.retorno_con_carga IS NOT NULL
        ORDER BY d.id_despacho DESC LIMIT 200""",
        (origen_base,),
    )
    por_ciudad = defaultdict(list)
    for c in cerrados_sql:
        if len(por_ciudad[c["destino"]]) < 10:
            por_ciudad[c["destino"]].append(1 if c["retorno_con_carga"] else 0)
    tasa_ciudad = {
        ciudad: round(sum(vals) / len(vals), 2)
        for ciudad, vals in por_ciudad.items()
        if vals
    }

    # 5. Enriquecer cada despacho con sus valores sugeridos reales para el formulario web.
    for v in viajes:
        destino_v = str(v["destino"])
        if v["solicitudes_compatibles"] is not None:
            v["solicitudes_sugeridas"] = int(v["solicitudes_compatibles"])
        else:
            v["solicitudes_sugeridas"] = min(
                5, mapa_abiertas.get((destino_v, str(v["origen"])), 0)
            )
        if v["proporcion_retornos_previos"] is not None:
            prop_num = float(v["proporcion_retornos_previos"])
            v["proporcion_sugerida"] = f"{prop_num:.2f}"
            v["tasa_sugerida_pct"] = int(round(prop_num * 100))
            v["fuente_tasa"] = "registrada en el despacho"
        else:
            prop_num = float(tasa_ciudad.get(destino_v, 0.50))
            cant_cierres = len(por_ciudad[destino_v])
            v["proporcion_sugerida"] = f"{prop_num:.2f}"
            v["tasa_sugerida_pct"] = int(round(prop_num * 100))
            v["fuente_tasa"] = (
                f"calculada sobre últimos {cant_cierres} retornos cerrados de {destino_v}"
                if cant_cierres
                else "base inicial 50 % sin cierres previos"
            )
    return viajes


def evaluaciones_recientes():
    """Devuelve las últimas predicciones de retorno con carga guardadas en SQL."""
    return db.consultar("""SELECT p.*, s.destino FROM prediccion_retorno p
        JOIN despacho d USING(id_despacho) JOIN solicitud_carga s USING(id_solicitud)
        ORDER BY id_prediccion_retorno DESC LIMIT 15""")
