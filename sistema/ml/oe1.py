"""OE1: XGBoost para la duración total. Mantiene la configuración de la práctica."""

from datetime import timedelta, timezone

import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from xgboost import XGBRegressor

from ..operacion.formularios import exigir

VARIABLES = [
    "origen",
    "destino",
    "distancia_km",
    "peso_carga_tn",
    "dia_salida",
    "hora_salida",
    "velocidad_media_estimada_kmh",
]


def entrenar(datos):
    if len(datos) < 20:
        raise ValueError("OE1 necesita al menos 20 viajes completos para esta práctica.")
    X = pd.get_dummies(datos[VARIABLES], columns=["origen", "destino"], dtype=int)
    y = datos["duracion_viaje_min"]
    # 1. Reservar el 20 % antes de ajustar el modelo.
    xt, xp, yt, yp = train_test_split(X, y, test_size=0.20, random_state=42)
    modelo = XGBRegressor(
        n_estimators=100, max_depth=3, learning_rate=0.1, random_state=42, n_jobs=1
    )
    modelo.fit(xt, yt)
    # 2. Informar las métricas de prueba, sin reentrenar con esas respuestas.
    pred = modelo.predict(xp)
    metricas = {
        "r2": r2_score(yp, pred),
        "mae_min": mean_absolute_error(yp, pred),
        "rmse_min": mean_squared_error(yp, pred) ** 0.5,
        "entrenamiento": len(xt),
        "prueba": len(xp),
    }
    rutas = datos[["origen", "destino", "distancia_km"]].drop_duplicates().to_dict("records")
    return {
        "modelo": modelo,
        "columnas": list(X.columns),
        "rutas": rutas,
        "metricas": metricas,
        "evaluacion": {"real": list(yp), "predicha": list(pred)},
    }


def predecir(paquete, entrada):
    ruta = (entrada["origen"], entrada["destino"])
    if ruta not in {(r["origen"], r["destino"]) for r in paquete["rutas"]}:
        raise ValueError("El modelo no tiene viajes de entrenamiento para esa ruta.")
    fila = pd.get_dummies(
        pd.DataFrame([entrada])[VARIABLES], columns=["origen", "destino"], dtype=int
    )
    fila = fila.reindex(columns=paquete["columnas"], fill_value=0)
    return max(0.0, float(paquete["modelo"].predict(fila)[0]))


def limites_velocidad(distancia):
    # Rangos de velocidad media de los datos de práctica aprobados.
    return (25, 55) if float(distancia) == 395 else (45, 78)


def entrada_eta(datos, peso, salida, velocidad):
    # Preparar las variables de entrada de XGBoost; aquí todavía no se predice.
    # Las columnas históricas del SQL actual extraen día y hora en UTC.
    fecha_modelo = salida.astimezone(timezone.utc)
    return {
        "origen": datos["origen"],
        "destino": datos["destino"],
        "distancia_km": float(datos["distancia_km"]),
        "peso_carga_tn": peso,
        "dia_salida": fecha_modelo.isoweekday(),
        "hora_salida": fecha_modelo.hour,
        "velocidad_media_estimada_kmh": velocidad,
    }


def calcular_eta(total, distancia, salida, consulta, restantes=None):
    # El modelo ya entregó la duración total. Aquí solo se calcula la hora de llegada.
    exigir(distancia > 0, "La distancia de la ruta debe ser mayor que cero.")
    if restantes is None:
        return {
            "total_min": total,
            "restante_min": None,
            "llegada": salida + timedelta(minutes=total),
        }
    exigir(consulta >= salida, "La consulta en ruta no puede ser anterior a la salida.")
    # Aproximación acordada: mantener proporcionalmente el ritmo del recorrido completo.
    restante = total * restantes / distancia
    return {
        "total_min": total,
        "restante_min": restante,
        "llegada": consulta + timedelta(minutes=restante),
    }
