"""OE1: crear un CSV didáctico con 1.000 viajes completos (ejecuta: python generar.py)."""

from pathlib import Path

import numpy as np
import pandas as pd

# 1. CONFIGURACIÓN. Los rangos son supuestos explícitos de esta práctica.
ARCHIVO = Path(__file__).with_name("dataset.csv")
SEMILLA = 42  # Permite reproducir los mismos sorteos.
CANTIDAD_POR_RUTA = 250  # Cuatro rutas x 250 registros = 1.000 viajes.
FECHA_INICIO = pd.Timestamp("2024-01-01")
FECHA_FIN = pd.Timestamp("2025-12-31")
PESO_MINIMO_TN = 10
PESO_MAXIMO_TN = 29  # Perfil supuesto de hasta 30 t; no es un límite legal universal.

# Cada fila contiene: origen, destino, distancia total, velocidad mínima y máxima.
# Los km son fijos por ruta. Las velocidades son MEDIAS ESTIMADAS, no máximos legales.
# PROMPERÚ publica 395 km Huancayo-Callao; usarlo en ambos sentidos es una simplificación.
# Los 575 km del Norte siguen siendo una referencia provisional del proyecto.
# Rangos de velocidad supuestos, bajo los 80 km/h generales para carga en carretera.
RUTAS = [
    ("Callao", "Huancayo", 395, 25, 55),
    ("Huancayo", "Callao", 395, 25, 55),
    ("Callao", "Trujillo", 575, 45, 78),
    ("Trujillo", "Callao", 575, 45, 78),
]


def principal():
    # 2. GENERAR LAS ENTRADAS. uniform(mínimo, máximo, cantidad) sortea decimales.
    azar = np.random.default_rng(SEMILLA)
    cantidad_dias = (FECHA_FIN - FECHA_INICIO).days + 1
    grupos = []
    for origen, destino, distancia, velocidad_minima, velocidad_maxima in RUTAS:

        # --- A. Generar peso de la carga ---
        # Sortea pesos con decimales entre 10 y 29 toneladas
        pesos = azar.uniform(PESO_MINIMO_TN, PESO_MAXIMO_TN, CANTIDAD_POR_RUTA).round(2)

        # Si el camión viene de regreso (origen no es Callao), algunos regresan vacíos (peso = 0)
        es_viaje_de_retorno = (origen != "Callao")
        if es_viaje_de_retorno:
            filtro_con_carga = azar.integers(0, 2, CANTIDAD_POR_RUTA) # -> sortea 0 (vacío) o 1 (con carga)
            pesos = pesos * filtro_con_carga                          # -> deja en 0 toneladas los camiones que van vacíos

        # --- B. Generar velocidad media del viaje ---
        # Sortea velocidades promedio según la ruta (ej. 25 a 55 km/h en sierra)
        velocidades = azar.uniform(velocidad_minima, velocidad_maxima, CANTIDAD_POR_RUTA).round(2)

        # --- C. Generar fecha, día y hora exacta de salida ---
        dias_azar = azar.integers(0, cantidad_dias, CANTIDAD_POR_RUTA) # -> elige un día al azar del calendario
        horas = azar.integers(5, 21, CANTIDAD_POR_RUTA)                # -> elige la hora de salida (entre 5 am y 8 pm)

        sumar_dias = pd.to_timedelta(dias_azar, unit="D")              # -> convierte los días sorteados a formato de tiempo
        sumar_horas = pd.to_timedelta(horas, unit="h")                 # -> convierte las horas sorteadas a formato de tiempo
        salidas = FECHA_INICIO + sumar_dias + sumar_horas              # -> calcula la fecha y hora final de partida
        dia_semana = salidas.dayofweek + 1                             # -> obtiene el día de la semana (1=Lunes a 7=Domingo)

        # 3. CONSTRUIR LA RESPUESTA (PASO A PASO)
        
        # Paso A: Tiempo base en carretera
        horas_viaje = distancia / velocidades          # -> calcula las horas dividiendo distancia entre velocidad
        minutos_base = horas_viaje * 60                # -> convierte las horas a minutos

        # Paso B: Evaluar tráfico de salida/llegada según la hora punta
        es_punta_manana = (horas >= 6) & (horas <= 9)   # -> verifica si sale en hora punta de la mañana (6 a 9 am)
        es_punta_tarde = (horas >= 17) & (horas <= 19)  # -> verifica si sale en hora punta de la tarde (5 a 7 pm)
        hay_trafico = es_punta_manana | es_punta_tarde  # -> junta ambas: es verdadero si cae en mañana o en tarde
        demora_trafico = np.where(hay_trafico, 35, 0)   # -> si hay tráfico suma 35 minutos de retraso, si no suma 0

        # Paso C: Evaluar subida pesada a Ticlio / Huancayo
        va_a_huancayo = (destino == "Huancayo")        # -> verifica si la ruta va subiendo hacia Huancayo
        es_camion_pesado = (pesos > 20)                # -> verifica si la carga supera las 20 toneladas
        subida_pesada = va_a_huancayo & es_camion_pesado # -> es verdadero solo si van a Huancayo Y con más de 20t
        demora_subida = np.where(subida_pesada, 45, 0) # -> si es subida pesada suma 45 minutos extra, si no suma 0

        # Paso D: Evaluar día de salida (mayor flujo los viernes y sábados)
        es_viernes_o_sabado = (dia_semana == 5) | (dia_semana == 6) # -> verifica si sale viernes (5) o sábado (6)
        demora_dia = np.where(es_viernes_o_sabado, 20, 0)           # -> si es viernes o sábado suma 20 minutos, si no suma 0

        # Paso E: Sumar los tiempos
        duracion_total = minutos_base + demora_trafico + demora_subida + demora_dia # -> suma base + tráfico + subida + día
        duraciones = duracion_total.round(2)           # -> redondea la duración final a 2 decimales
        grupos.append(pd.DataFrame({
            "fecha_hora_salida": salidas,
            "origen": origen,
            "destino": destino,
            "distancia_km": distancia,
            "peso_carga_tn": pesos,  # Peso neto simulado en t; no se simulan bruto ni tara.
            "dia_salida": dia_semana,  # Lunes=1, domingo=7.
            "hora_salida": horas,
            "velocidad_media_estimada_kmh": velocidades,
            "duracion_viaje_min": duraciones,
        }))

    # 4. GUARDAR EL DATASET. Cada fila representa un viaje, no una posición GPS.
    datos = pd.concat(grupos, ignore_index=True).sort_values("fecha_hora_salida")
    datos.insert(0, "id_despacho", range(1, len(datos) + 1))  # Identificador; no predictor.
    datos.to_csv(ARCHIVO, index=False, encoding="utf-8-sig")
    print(f"Creado {ARCHIVO.name}: {len(datos)} viajes simulados.")
    print(datos.head(3).to_string(index=False))
    print("Duración simulada = (distancia / velocidad x 60) + tráfico + subida + día.")


if __name__ == "__main__":
    principal()
