"""OE3: árbol de decisión para volver con carga; evaluación cronológica 80/20."""

import pandas as pd
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score
from sklearn.metrics import precision_score, recall_score, roc_auc_score, roc_curve
from sklearn.tree import DecisionTreeClassifier

VARIABLES = [
    "origen_retorno",
    "dia_entrega_pactada",
    "quincena_entrega_pactada",
    "solicitudes_compatibles",
    "proporcion_retornos_previos",
]
ETIQUETAS_OE3 = {
    "origen_retorno": "Ciudad de retorno",
    "dia_entrega_pactada": "Día de entrega pactada",
    "quincena_entrega_pactada": "Quincena de entrega",
    "solicitudes_compatibles": "Solicitudes compatibles",
    "proporcion_retornos_previos": "Proporción previa con carga",
}


def _agrupar_importancia_oe3(columnas, importancias):
    pesos = {}
    for col, valor in zip(columnas, importancias):
        base = "origen_retorno" if col.startswith("origen_retorno_") else col
        pesos[base] = pesos.get(base, 0.0) + float(valor)
    orden = sorted(pesos, key=pesos.get, reverse=True)
    return [
        {"variable": ETIQUETAS_OE3.get(k, k), "porcentaje": round(pesos[k] * 100, 2)}
        for k in orden
    ]


def entrenar(datos):
    # 1. Ordenar los casos por fecha y reservar el 20 % más reciente.
    datos = datos.sort_values(["fecha_hora_evaluacion", "id_despacho"])
    corte = int(len(datos) * 0.80)
    y = datos["retorno_con_carga"]
    if len(datos) < 20 or y.iloc[:corte].nunique() < 2:
        raise ValueError("OE3 necesita al menos 20 casos y ambas clases en entrenamiento.")
    # 2. Preparar las variables predictoras; los identificadores no se usan como entradas.
    X = pd.get_dummies(datos[VARIABLES], columns=["origen_retorno"], dtype=int)
    modelo = DecisionTreeClassifier(max_depth=4, random_state=42)
    # 3. Ajustar el árbol únicamente con el 80 % de entrenamiento.
    modelo.fit(X.iloc[:corte], y.iloc[:corte])
    # 4. Evaluar con el 20 % reservado y conservar las métricas y curvas para Chart.js.
    pred = modelo.predict(X.iloc[corte:])
    real = y.iloc[corte:]
    probabilidades = modelo.predict_proba(X.iloc[corte:])[:, list(modelo.classes_).index(1)]
    tiene_dos_clases = real.nunique() == 2
    metricas = {
        "accuracy": accuracy_score(real, pred),
        "precision": precision_score(real, pred, zero_division=0),
        "recall": recall_score(real, pred, zero_division=0),
        "f1": f1_score(real, pred, zero_division=0),
        "matriz": confusion_matrix(real, pred, labels=[0, 1]).tolist(),
        "auc": roc_auc_score(real, probabilidades) if tiene_dos_clases else None,
        "entrenamiento": corte,
        "prueba": len(real),
    }
    roc_pts = []
    if tiene_dos_clases:
        fpr, tpr, umbrales = roc_curve(real, probabilidades)
        roc_pts = [
            {
                "fpr": round(float(fp), 4),
                "tpr": round(float(tp), 4),
                "umbral": round(float(um), 3) if um <= 1 else 1.0,
            }
            for fp, tp, um in zip(fpr, tpr, umbrales)
        ]
    casos_prueba = [
        {
            "id_despacho": int(f.get("id_despacho", 0)),
            "ciudad": str(f.get("origen_retorno", "")),
            "solicitudes": int(f.get("solicitudes_compatibles", 0)),
            "proporcion": round(float(f.get("proporcion_retornos_previos", 0.0)), 2),
            "real": int(r_val),
            "probabilidad": round(float(p_val) * 100, 1),
        }
        for f, r_val, p_val in zip(
            datos.iloc[corte:].to_dict("records"), real, probabilidades
        )
    ]
    return {
        "modelo": modelo,
        "columnas": list(X.columns),
        "metricas": metricas,
        "evaluacion": {
            "real": [int(v) for v in real],
            "probabilidades": [float(v) for v in probabilidades],
            "roc": roc_pts,
            "importancia": _agrupar_importancia_oe3(X.columns, modelo.feature_importances_),
            "casos": casos_prueba,
        },
    }


def predecir(paquete, entrada):
    fila = pd.get_dummies(pd.DataFrame([entrada])[VARIABLES], columns=["origen_retorno"], dtype=int)
    # Repetir las columnas del entrenamiento, aunque aquí solo se consulte una ciudad.
    fila = fila.reindex(columns=paquete["columnas"], fill_value=0)
    modelo = paquete["modelo"]
    # predict_proba entrega una probabilidad por clase; aquí interesa volver con carga.
    prob = float(modelo.predict_proba(fila)[0, list(modelo.classes_).index(1)])
    # Estos cortes presentan la probabilidad; no sustituyen la respuesta objetivo 0/1.
    # Alta: desde 70 %; Media: desde 40 % hasta menos de 70 %; Baja: menos de 40 %.
    nivel = "Alta" if prob >= 0.70 else "Media" if prob >= 0.40 else "Baja"
    return {"probabilidad": prob, "nivel": nivel, "con_carga": int(modelo.predict(fila)[0])}
