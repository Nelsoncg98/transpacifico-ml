"""OE2: crear un CSV didáctico con la demanda semanal en toneladas por corredor (ejecuta: python generar.py)."""

from pathlib import Path
import numpy as np
import pandas as pd

# 1. CONFIGURACIÓN
ARCHIVO = Path(__file__).with_name("dataset.csv")
SEMILLA = 42                                    # -> semilla fija para que siempre salgan los mismos sorteos
FECHA_INICIO = "2024-01-01"                     # -> primer lunes del año 2024
FECHA_FIN = "2025-12-28"                        # -> último lunes del año 2025 (104 semanas = 2 años)

CORREDORES = ["Centro", "Norte"]                # -> los dos corredores logísticos de TRANSPACÍFICO


def principal():
    # 2. GENERAR EL CALENDARIO NACIONAL (Igual para ambos corredores)
    azar = np.random.default_rng(SEMILLA)
    semanas = pd.date_range(FECHA_INICIO, FECHA_FIN, freq="7D") # -> crea la lista de los 104 lunes (2 años)
    cantidad_semanas = len(semanas)                             # -> cuenta cuántas semanas son en total (104)

    # Sorteamos los feriados nacionales de cada semana (compartidos por Centro y Norte)
    feriados = azar.choice([0, 1, 2], size=cantidad_semanas, p=[0.80, 0.15, 0.05])

    # Contamos cuántos días reales de cada semana (de lunes a domingo) caen del día 16 a fin de mes
    dias_quincena = np.zeros(cantidad_semanas, dtype=int)       # -> inicia el contador de días en 0
    for d in range(7):                                          # -> revisa los 7 días de la semana (lunes a domingo)
        fecha_dia = semanas + pd.Timedelta(days=d)              # -> obtiene la fecha exacta de ese día
        dias_quincena = dias_quincena + np.where(fecha_dia.day >= 16, 1, 0) # -> suma 1 si cae del día 16 en adelante

    # 3. CALCULAR LOS VIAJES Y TONELADAS DE CADA CORREDOR
    grupos = []
    for corredor in CORREDORES:

        # --- A. Calcular cuántos viajes salen en la semana (PASO A PASO) ---
        viajes_base = 6 if corredor == "Centro" else 7          # -> base semanal: 6 viajes en Centro y 7 en Norte
        extra_por_quincena = dias_quincena * 1                  # -> cada día en 2da quincena suma 1 viaje extra
        resta_por_feriados = feriados * 1                       # -> cada feriado nacional reduce 1 viaje en la semana
        viajes_totales = viajes_base + extra_por_quincena - resta_por_feriados # -> total de viajes de la semana

        # --- B. Calcular las toneladas totales de la semana (PASO A PASO) ---
        peso_por_camion = azar.uniform(20.5, 21.5, cantidad_semanas) # -> cada camión lleva entre 20.5 y 21.5 toneladas
        toneladas_calculadas = viajes_totales * peso_por_camion      # -> multiplica los viajes por el peso del camión
        toneladas_finales = toneladas_calculadas.round(2)            # -> redondea las toneladas finales a 2 decimales

        # --- C. Guardar la tabla de este corredor ---
        grupos.append(pd.DataFrame({
            "semana_inicio": semanas.strftime("%Y-%m-%d"),
            "corredor": corredor,
            "feriados_semana": feriados,
            "dias_segunda_quincena": dias_quincena,
            "toneladas_semana": toneladas_finales,
        }))

    # 4. JUNTAR AMBOS CORREDORES Y GUARDAR EL CSV
    datos = pd.concat(grupos, ignore_index=True).sort_values(["semana_inicio", "corredor"])
    datos.to_csv(ARCHIVO, index=False, encoding="utf-8-sig")
    print(f"Creado {ARCHIVO.name}: {len(datos)} filas semanales simuladas.")
    print(datos.head(6).to_string(index=False))


if __name__ == "__main__":
    principal()
