"""Ejecutar: python -m sistema.ml.entrenar. Lee SQL; no modifica registros ni tablas."""

import json
import os
from datetime import datetime, timezone

import joblib

from ..config import MODELOS
from . import oe1, oe2, oe3
from .datos import cargar
from .graficos import generar


def principal():
    # 1. Preparar la carpeta donde se guardarán modelos y evidencias.
    MODELOS.mkdir(parents=True, exist_ok=True)
    resumen = {
        "fuente": "PostgreSQL",
        "fecha": datetime.now(timezone.utc).isoformat(),
        "division": "80/20",
        "resultados": {},
    }
    for nombre, modulo in (("oe1", oe1), ("oe2", oe2), ("oe3", oe3)):
        # 2. Leer el histórico de SQL y entrenar con la configuración 80/20.
        datos = cargar(nombre)
        try:
            if datos.empty:
                raise ValueError("No hay registros históricos para entrenar.")
            paquete = modulo.entrenar(datos)
        except ValueError as error:
            resumen["resultados"][nombre] = {"pendiente": str(error), "filas": len(datos)}
            # Un modelo anterior no debe aparentar un entrenamiento nuevo que no ocurrió.
            (MODELOS / f"{nombre}.joblib").unlink(missing_ok=True)
            for imagen in MODELOS.glob(f"{nombre}_*.png"):
                imagen.unlink()
            continue
        # 3. Guardar el modelo; cada consulta web reutilizará este archivo.
        temporal = MODELOS / f"{nombre}.temporal"
        if nombre == "oe2":
            from prophet.serialize import model_to_json

            for datos_corredor in paquete.values():
                datos_corredor["modelo"] = model_to_json(datos_corredor["modelo"])
        joblib.dump(paquete, temporal, compress=3)
        os.replace(temporal, MODELOS / f"{nombre}.joblib")
        # 4. Dibujar las evidencias usando los resultados del conjunto de prueba.
        generar(nombre, paquete)
        metricas = (
            {k: v["metricas"] for k, v in paquete.items()}
            if nombre == "oe2"
            else paquete["metricas"]
        )
        resumen["resultados"][nombre] = {"filas": len(datos), "metricas": metricas}
    (MODELOS / "metricas.json").write_text(json.dumps(resumen, indent=2), encoding="utf-8")
    print(json.dumps(resumen, indent=2))


if __name__ == "__main__":
    principal()
