"""Consultas parametrizadas a PostgreSQL. No crea tablas ni genera registros."""

import os
from contextlib import contextmanager
from functools import lru_cache

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool


@lru_cache(maxsize=1)
def conexiones():
    url = os.getenv("DATABASE_URL")
    if not url:
        raise ValueError("Falta configurar DATABASE_URL en el servidor.")
    return ConnectionPool(
        url,
        min_size=0,
        max_size=int(os.getenv("DB_POOL_MAX", "4")),
        timeout=10,
        # Evita depender de sentencias preparadas persistentes con un pooler externo.
        kwargs={"connect_timeout": 10, "row_factory": dict_row, "prepare_threshold": None},
    )


@contextmanager
def conexion():
    # El contexto confirma todas las operaciones juntas o revierte si algo falla.
    with conexiones().connection() as con:
        con.execute("SET TIME ZONE 'UTC'")
        yield con


def consultar(sql, parametros=()):
    with conexion() as con:
        return con.execute(sql, parametros).fetchall()


def obtener(sql, parametros=()):
    with conexion() as con:
        return con.execute(sql, parametros).fetchone()


def guardar(sql, parametros=()):
    with conexion() as con:
        resultado = con.execute(sql, parametros)
        return resultado.fetchone() if resultado.description else None


class ViajeNoEncontrado(LookupError):
    """Permite responder 404 sin mezclar la consulta SQL con la pantalla."""


def viaje(id_viaje, con=None, bloquear=False):
    # Reunir los datos que comparten pesaje, entrega y estimación de llegada.
    sql = """
        SELECT d.*, s.origen, s.destino, s.peso_tn, s.ventana_entrega,
               s.tipo_carga, s.nro_guia_remitente, c.distancia_km,
               sr.capacidad_tn, t.placa
        FROM despacho d JOIN solicitud_carga s USING(id_solicitud)
        JOIN corredor c USING(id_corredor)
        JOIN semirremolque sr USING(id_semirremolque)
        JOIN tracto t USING(id_tracto) WHERE d.id_despacho=%s
    """
    # Al guardar cambios, bloquear el despacho hasta terminar la transacción.
    if bloquear:
        sql += " FOR UPDATE OF d"
    fila = con.execute(sql, (id_viaje,)).fetchone() if con else obtener(sql, (id_viaje,))
    # La pantalla responderá 404 si el identificador no existe.
    if not fila:
        raise ViajeNoEncontrado("No se encontró el viaje.")
    return fila
