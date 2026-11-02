"""Datasets de entrenamiento obtenidos únicamente de PostgreSQL."""

import pandas as pd

from ..db import consultar


def cargar(nombre):
    from pathlib import Path

    sql = (Path(__file__).parent / "sql" / f"{nombre}.sql").read_text()
    return pd.DataFrame(consultar(sql))
