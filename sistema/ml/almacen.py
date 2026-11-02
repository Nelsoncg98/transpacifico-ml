"""Carga una vez los modelos producidos por nuestro entrenamiento separado."""

from functools import lru_cache

import joblib

from ..config import MODELOS


@lru_cache(maxsize=3)
def cargar(nombre):
    ruta = MODELOS / f"{nombre}.joblib"
    if not ruta.exists():
        raise ValueError(f"{nombre.upper()}: faltan datos suficientes o ejecutar el entrenamiento.")
    # Solo se cargan archivos producidos por este proyecto, nunca archivos subidos por usuarios.
    paquete = joblib.load(ruta)
    if nombre == "oe2":
        from prophet.serialize import model_from_json

        for datos_corredor in paquete.values():
            datos_corredor["modelo"] = model_from_json(datos_corredor["modelo"])
    return paquete


def disponibles():
    return {nombre: (MODELOS / f"{nombre}.joblib").exists() for nombre in ("oe1", "oe2", "oe3")}
