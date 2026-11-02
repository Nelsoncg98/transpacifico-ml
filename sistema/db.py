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
