"""OE2: Prophet por corredor, con las dos variables explicadas en la práctica."""

import pandas as pd
from prophet import Prophet
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

REGRESORES = ["feriados_semana", "dias_segunda_quincena"]


def entrenar(datos):
    paquetes = {}
    for corredor, tabla in datos.groupby("corredor"):
        tabla = tabla.rename(columns={"semana_inicio": "ds", "toneladas_semana": "y"})
        tabla["ds"] = pd.to_datetime(tabla["ds"])
        tabla = tabla.sort_values("ds")
        if len(tabla) < 10 or tabla["ds"].duplicated().any():
            raise ValueError(f"OE2: {corredor} necesita semanas únicas y al menos 10 filas.")
        # 1. Entrenar con el pasado y evaluar con las últimas semanas (80/20).
        corte = int(len(tabla) * 0.80)
        train, test = tabla.iloc[:corte], tabla.iloc[corte:]
        modelo = Prophet(
            yearly_seasonality=False, weekly_seasonality=False, daily_seasonality=False
        )
        for nombre in REGRESORES:
            modelo.add_regressor(nombre)
        modelo.fit(train)
        pred = modelo.predict(test)["yhat"]
        metricas = {
            "r2": r2_score(test["y"], pred),
            "mae_tn": mean_absolute_error(test["y"], pred),
            "rmse_tn": mean_squared_error(test["y"], pred) ** 0.5,
            "entrenamiento": len(train),
            "prueba": len(test),
        }
        paquetes[corredor] = {
            "modelo": modelo,
            "metricas": metricas,
            "ultima_semana": str(tabla["ds"].max().date()),
            "evaluacion": {
                "fechas": list(test["ds"]),
                "real": list(test["y"]),
                "predicha": list(pred),
            },
        }
    return paquetes


def predecir(paquete, semana, feriados):
    fecha = pd.Timestamp(semana)
    if fecha.dayofweek != 0 or not 0 <= feriados <= 7:
        raise ValueError("Selecciona un lunes y entre 0 y 7 feriados.")
    # 2. Contar los días del calendario; el usuario no necesita calcularlos.
    dias = sum((fecha + pd.Timedelta(days=i)).day >= 16 for i in range(7))
    fila = pd.DataFrame([{"ds": fecha, "feriados_semana": feriados, "dias_segunda_quincena": dias}])
    pred = paquete["modelo"].predict(fila).iloc[0]
    return {
        "semana": str(fecha.date()),
        "toneladas": max(0.0, float(pred.yhat)),
        "minimo": max(0.0, float(pred.yhat_lower)),
        "maximo": max(0.0, float(pred.yhat_upper)),
        "dias_quincena": dias,
    }
