"""Consultar el XGBoost a distintas velocidades, conservando las demás entradas."""

import numpy as np
import pandas as pd
from matplotlib.figure import Figure


def dibujar(paquete, entrada, minutos):
    minimo, maximo = (25, 55) if entrada["distancia_km"] == 395 else (45, 78)
    # Incluir la velocidad elegida permite señalar exactamente su predicción.
    velocidades = np.unique(np.append(np.linspace(minimo, maximo, 61),
                                      entrada["velocidad_media_estimada_kmh"]))
    filas = pd.DataFrame([entrada] * len(velocidades))
    filas["velocidad_media_estimada_kmh"] = velocidades
    columnas = pd.get_dummies(filas, columns=["origen", "destino"], dtype=int)
    columnas = columnas.reindex(columns=paquete["columnas"], fill_value=0)
    # Son predicciones del modelo actual, no la fórmula del generador de datos.
    duraciones = paquete["modelo"].predict(columnas)
    figura = Figure(figsize=(9, 5))
    eje = figura.add_subplot()
    eje.plot(velocidades, duraciones, color="#2563eb", label="Predicción de XGBoost")
    velocidad = entrada["velocidad_media_estimada_kmh"]
    eje.scatter([velocidad], [minutos], color="#dc2626", s=90, zorder=5,
                label=f"Consulta: {velocidad:g} km/h → {minutos:.2f} min")
    eje.set(xlabel="Velocidad media estimada (km/h)", ylabel="Duración predicha (minutos)",
            title=f"OE1: velocidad y duración · {entrada['origen']} → {entrada['destino']}")
    eje.grid(alpha=0.2)
    eje.legend()
    detalle = (f"Fijos: {entrada['distancia_km']:g} km · {entrada['peso_carga_tn']:g} t · "
               f"día {entrada['dia_salida']} · hora {entrada['hora_salida']} (UTC del dataset).")
    figura.text(0.5, 0.02, detalle, ha="center", fontsize=9)
    figura.tight_layout(rect=(0, 0.06, 1, 1))
    return figura
