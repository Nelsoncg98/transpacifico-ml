"""OE1: XGBoost para la duración total. Mantiene la configuración de la práctica."""

from datetime import timedelta, timezone

import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from xgboost import XGBRegressor

from ..operacion.formularios import exigir

VARIABLES = [
    "corredor",
    "destino",
    "peso_carga_tn",
    "dia_salida",
    "hora_salida",
]
CATEGORIAS = ["corredor", "destino"]
ETIQUETAS_OE1 = {
    "corredor": "Corredor logístico",
    "destino": "Ciudad de destino",
    "peso_carga_tn": "Peso de carga (t)",
    "dia_salida": "Día de salida",
    "hora_salida": "Hora de salida",
}


def _agrupar_importancia(columnas, importancias):
    pesos = {}
    for col, valor in zip(columnas, importancias):
        base = next((cat for cat in CATEGORIAS if col.startswith(cat + "_")), col)
        pesos[base] = pesos.get(base, 0.0) + float(valor)
    orden = sorted(pesos, key=pesos.get, reverse=True)
    return [
        {"variable": ETIQUETAS_OE1.get(k, k), "porcentaje": round(pesos[k] * 100, 2)}
        for k in orden
    ]


def entrenar(datos):
    if len(datos) < 20:
        raise ValueError("OE1 necesita al menos 20 viajes completos para entrenar.")
    # Corredor y destino se convierten en columnas 0/1, igual que en consola.
    X = pd.get_dummies(datos[VARIABLES], columns=CATEGORIAS, dtype=int)
    y = datos["duracion_viaje_min"]
    # 1. Reservar el 20 % antes de ajustar el modelo, conservando metadatos para trazabilidad visual.
    xt, xp, yt, yp, _, meta_p = train_test_split(
        X, y, datos, test_size=0.20, random_state=42
    )
    modelo = XGBRegressor(
        n_estimators=100, max_depth=3, learning_rate=0.1, random_state=42, n_jobs=1
    )
    modelo.fit(xt, yt)
    # 2. Informar las métricas de prueba, sin reentrenar con esas respuestas.
    pred = modelo.predict(xp)
    metricas = {
        "r2_entrenamiento": r2_score(yt, modelo.predict(xt)),
        "r2": r2_score(yp, pred),
        "mae_min": mean_absolute_error(yp, pred),
        "rmse_min": mean_squared_error(yp, pred) ** 0.5,
        "entrenamiento": len(xt),
        "prueba": len(xp),
    }
    puntos = []
    for fila_m, real_v, pred_v in zip(meta_p.to_dict("records"), yp, pred):
        origen_txt = fila_m.get("origen", "Callao")
        puntos.append(
            {
                "id_despacho": int(fila_m.get("id_despacho", 0)),
                "corredor": str(fila_m.get("corredor", "")),
                "ruta": f"{origen_txt} → {fila_m.get('destino', '')}",
                "peso_tn": round(float(fila_m.get("peso_carga_tn", 0.0)), 2),
                "hora_salida": int(fila_m.get("hora_salida", 0)),
                "real": round(float(real_v), 2),
                "predicha": round(float(pred_v), 2),
            }
        )
    rutas = datos[CATEGORIAS].drop_duplicates().to_dict("records")
    return {
        "modelo": modelo,
        "columnas": list(X.columns),
        "rutas": rutas,
        "metricas": metricas,
        "evaluacion": {
            "real": [float(v) for v in yp],
            "predicha": [float(v) for v in pred],
            "puntos": puntos,
            "importancia": _agrupar_importancia(X.columns, modelo.feature_importances_),
        },
    }


def predecir(paquete, entrada):
    ruta = (entrada["corredor"], entrada["destino"])
    if ruta not in {(r["corredor"], r["destino"]) for r in paquete["rutas"]}:
        raise ValueError("El modelo no tiene viajes de entrenamiento para esa ruta.")
    fila = pd.get_dummies(
        pd.DataFrame([entrada])[VARIABLES], columns=CATEGORIAS, dtype=int
    )
    # Usar las mismas columnas y el mismo orden que durante el entrenamiento.
    # Las categorías ausentes en esta entrada conservan su columna con valor 0.
    fila = fila.reindex(columns=paquete["columnas"], fill_value=0)
    return max(0.0, float(paquete["modelo"].predict(fila)[0]))


def entrada_eta(datos, peso, salida):
    # Preparar las variables de entrada de XGBoost; aquí todavía no se predice.
    # Las columnas históricas del SQL actual extraen día y hora en UTC.
    fecha_modelo = salida.astimezone(timezone.utc)
    return {
        "corredor": datos["corredor"],
        "destino": datos["destino"],
        "peso_carga_tn": peso,
        "dia_salida": fecha_modelo.isoweekday(),
        "hora_salida": fecha_modelo.hour,
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
