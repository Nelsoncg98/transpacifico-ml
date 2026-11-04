"""OE1: generar el CSV auxiliar con las cinco entradas actuales del modelo."""

from pathlib import Path

import numpy as np
import pandas as pd

# 1. CONFIGURACIÓN. Son supuestos de práctica, iguales a los de generarSQL.py.
ARCHIVO = Path(__file__).with_name("dataset.csv")
SEMILLA = 42  # Cambiarla produce otros sorteos; repetirla reproduce el dataset.
CANTIDAD_POR_RUTA = 500  # Cuatro trayectos x 500 registros = 2 000 viajes.
FECHA_INICIO = pd.Timestamp("2024-01-01")
FECHA_FIN = pd.Timestamp("2025-12-25")

# Corredor, origen, destino, duración base (min) y minutos adicionales por tonelada.
# Cada dirección tiene su referencia; estas cifras no son mediciones de carretera.
RUTAS = [
    ("Centro", "Callao", "Huancayo", 590, 3.2),
    ("Centro", "Huancayo", "Callao", 490, 0.8),
    ("Norte", "Callao", "Trujillo", 520, 1.0),
    ("Norte", "Trujillo", "Callao", 510, 1.0),
]


def principal():
    azar = np.random.default_rng(SEMILLA)
    cantidad_dias = (FECHA_FIN - FECHA_INICIO).days + 1
    grupos = []

    for corredor, origen, destino, minutos_base, minutos_por_tonelada in RUTAS:
        # 2. SORTEAR LA CARGA. La ida lleva de 10 a 29 t; el regreso puede ir vacío.
        pesos = azar.uniform(10, 29, CANTIDAD_POR_RUTA).round(2)
        if destino == "Callao":
            con_carga = azar.integers(0, 2, CANTIDAD_POR_RUTA)
            pesos = pesos * con_carga  # Un 0 representa un retorno vacío.

        # 3. SORTEAR LA SALIDA. De la fecha se obtiene un día válido de la semana.
        dias = azar.integers(0, cantidad_dias, CANTIDAD_POR_RUTA)
        horas = azar.integers(5, 21, CANTIDAD_POR_RUTA)  # De 05:00 a 20:00.
        salidas = FECHA_INICIO + pd.to_timedelta(dias, unit="D")
        salidas = salidas + pd.to_timedelta(horas, unit="h")
        dia_semana = salidas.dayofweek + 1  # Lunes = 1; domingo = 7.

        # 4. SIMULAR LA DURACIÓN con las mismas reglas del generador SQL.
        demora_peso = pesos * minutos_por_tonelada
        hora_punta = ((horas >= 6) & (horas <= 9)) | ((horas >= 17) & (horas <= 19))
        demora_trafico = np.where(hora_punta, 45, 0)
        viernes_o_sabado = (dia_semana == 5) | (dia_semana == 6)
        demora_dia = np.where(viernes_o_sabado, 25, 0)
        variacion = azar.normal(0, 8, CANTIDAD_POR_RUTA)  # Variación de media 0 y desvío 8 min.
        duraciones = minutos_base + demora_peso + demora_trafico + demora_dia + variacion

        # 5. ORGANIZAR LOS DATOS. El modelo usa cinco entradas y aprende la duración.
        grupos.append(pd.DataFrame({
            "fecha_hora_salida": salidas,  # Solo sirve para ordenar; no se exporta.
            "corredor": corredor,
            "origen": origen,  # Dato de control; el modelo no lo usa como predictor.
            "destino": destino,
            "peso_carga_tn": pesos,
            "dia_salida": dia_semana,
            "hora_salida": horas,
            "duracion_viaje_min": duraciones.round(2),
        }))

    # 6. GUARDAR ocho columnas, con la misma estructura que la consulta SQL de OE1.
    datos = pd.concat(grupos, ignore_index=True).sort_values("fecha_hora_salida")
    datos = datos.drop(columns="fecha_hora_salida").reset_index(drop=True)
    datos.insert(0, "id_despacho", range(1, len(datos) + 1))  # Identificador de control.
    datos.to_csv(ARCHIVO, index=False, encoding="utf-8-sig")
    print(f"Creado {ARCHIVO.name}: {len(datos)} viajes y {len(datos.columns)} columnas.")
    print(datos.head(3).to_string(index=False))
    print("Entradas: corredor, destino, peso, día y hora. Objetivo: duración en minutos.")


if __name__ == "__main__":
    principal()
