"""OE3: crear un CSV didáctico con 1.000 evaluaciones de retorno con carga o vacío (ejecuta: python generar.py)."""

from pathlib import Path
import numpy as np
import pandas as pd

# 1. CONFIGURACIÓN
ARCHIVO = Path(__file__).with_name("dataset.csv")
SEMILLA = 42                                    # -> semilla fija para repetir siempre los mismos sorteos
CANTIDAD = 1000                                 # -> 1,000 viajes de retorno a evaluar
FECHA_INICIO = "2024-01-01"                     # -> inicio del historial (año 2024)
FECHA_FIN = "2025-12-28"                        # -> fin del historial (año 2025)


def principal():
    # 2. SORTEAR LAS FECHAS Y VARIABLES DE CADA RETORNO
    azar = np.random.default_rng(SEMILLA)
    calendario = pd.date_range(FECHA_INICIO, FECHA_FIN, freq="D")

    # Sorteamos fecha y hora de salida/evaluación y las ordenamos de más antiguo a más reciente
    indice_dias = azar.integers(0, len(calendario), CANTIDAD)
    horas = azar.integers(5, 21, CANTIDAD)
    fechas_salida = pd.Series(calendario[indice_dias] + pd.to_timedelta(horas, unit="h")).sort_values().reset_index(drop=True)

    # Sorteamos ciudad y ofertas disponibles; calculamos la fecha de entrega pactada (+13h o +14h)
    ciudades = azar.choice(["Huancayo", "Trujillo"], size=CANTIDAD) # -> ciudad donde entrega la ida y empieza el retorno
    horas_ida = np.where(ciudades == "Huancayo", 13, 14)            # -> plazo pactado de ida: 13h Huancayo, 14h Trujillo
    fechas_entrega = fechas_salida + pd.to_timedelta(horas_ida, unit="h") # -> fecha y hora pactada de entrega en destino

    dias = fechas_entrega.dt.isocalendar().day.to_numpy(dtype=int)  # -> día de la entrega pactada (1=Lunes a 7=Domingo)
    quincenas = np.where(fechas_entrega.dt.day <= 15, 1, 2)         # -> quincena de la entrega pactada (1 o 2)
    solicitudes = azar.integers(0, 6, CANTIDAD)                     # -> ofertas compatibles disponibles (0 a 5)
    variaciones = azar.integers(-8, 9, CANTIDAD)                    # -> pequeña variación operativa de cada día

    # 3. CALCULAR HISTORIAL REAL (ÚLTIMOS 10 RETORNOS FINALIZADOS) Y RESULTADO PASO A PASO
    historial = {"Huancayo": [], "Trujillo": []}                    # -> guarda (fecha_cierre, resultado) por ciudad
    proporciones = []
    retornos_con_carga = []

    for i in range(CANTIDAD):
        ciudad = ciudades[i]
        momento_eval = fechas_salida[i]

        # Filtramos solo los retornos de esa ciudad que ya finalizaron antes de esta evaluación
        finalizados = [res for fecha_fin, res in historial[ciudad] if fecha_fin < momento_eval]
        ultimos_10 = finalizados[-10:]                              # -> toma hasta los últimos 10 retornos disponibles

        if len(ultimos_10) > 0:
            proporcion = round(sum(ultimos_10) / len(ultimos_10), 2) # -> promedio real de los retornos previos conocidos
        else:
            proporcion = 0.50                                       # -> supuesto inicial de arranque cuando aún no hay cerrados

        # Calculamos los puntos del viaje paso a paso
        puntos_solicitudes = solicitudes[i] * 20                    # -> cada solicitud compatible suma 20 puntos
        puntos_quincena = 15 if quincenas[i] == 2 else 0            # -> en 2da quincena hay más carga (+15 puntos)
        puntos_dia = 15 if dias[i] <= 5 else 0                      # -> de lunes a viernes hay más despachos (+15 puntos)
        puntos_ciudad = 10 if ciudad == "Trujillo" else 0           # -> Trujillo tiene más flujo agroindustrial (+10 puntos)
        puntos_historial = proporcion * 30                          # -> el historial previo suma hasta 30 puntos

        puntaje_total = (
            puntos_solicitudes + puntos_quincena + puntos_dia + puntos_ciudad + puntos_historial + variaciones[i]
        )                                                           # -> suma todos los puntos del retorno

        # Si hay al menos 1 solicitud y el puntaje llega a 70 o más, vuelve con carga (1); si no, vacío (0)
        resultado = 1 if (solicitudes[i] > 0 and puntaje_total >= 70) else 0

        proporciones.append(proporcion)
        retornos_con_carga.append(resultado)

        # El retorno finaliza 24 horas después de la entrega pactada; recién ahí entra al historial
        fecha_cierre = fechas_entrega[i] + pd.Timedelta(hours=24)
        historial[ciudad].append((fecha_cierre, resultado))

    # 4. GUARDAR EL ARCHIVO CSV
    datos = pd.DataFrame({
        "id_despacho": np.arange(1, CANTIDAD + 1),
        "fecha_hora_evaluacion": fechas_salida.dt.strftime("%Y-%m-%d %H:%M:%S"),
        "origen_retorno": ciudades,
        "dia_entrega_pactada": dias,
        "quincena_entrega_pactada": quincenas,
        "solicitudes_compatibles": solicitudes,
        "proporcion_retornos_previos": proporciones,
        "retorno_con_carga": retornos_con_carga,
    })

    datos.to_csv(ARCHIVO, index=False, encoding="utf-8-sig")
    print(f"Creado {ARCHIVO.name}: {len(datos)} retornos simulados.")
    print(datos.head(4).to_string(index=False))


if __name__ == "__main__":
    principal()
