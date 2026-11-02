"""OE3: árbol de decisión para volver con carga; evaluación cronológica 80/20."""

import pandas as pd
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score
from sklearn.metrics import precision_score, recall_score, roc_auc_score
from sklearn.tree import DecisionTreeClassifier

VARIABLES = [
    "origen_retorno",
    "dia_entrega_pactada",
    "quincena_entrega_pactada",
    "solicitudes_compatibles",
    "proporcion_retornos_previos",
]


def entrenar(datos):
    datos = datos.sort_values(["fecha_hora_evaluacion", "id_despacho"])
    corte = int(len(datos) * 0.80)
    y = datos["retorno_con_carga"]
    if len(datos) < 20 or y.iloc[:corte].nunique() < 2:
        raise ValueError("OE3 necesita al menos 20 casos y ambas clases en entrenamiento.")
    X = pd.get_dummies(datos[VARIABLES], columns=["origen_retorno"], dtype=int)
    modelo = DecisionTreeClassifier(max_depth=4, random_state=42)
    modelo.fit(X.iloc[:corte], y.iloc[:corte])
    pred = modelo.predict(X.iloc[corte:])
    real = y.iloc[corte:]
    probabilidades = modelo.predict_proba(X.iloc[corte:])[:, list(modelo.classes_).index(1)]
    metricas = {
        "accuracy": accuracy_score(real, pred),
        "precision": precision_score(real, pred, zero_division=0),
        "recall": recall_score(real, pred, zero_division=0),
        "f1": f1_score(real, pred, zero_division=0),
        "matriz": confusion_matrix(real, pred, labels=[0, 1]).tolist(),
        "auc": roc_auc_score(real, probabilidades) if real.nunique() == 2 else None,
        "entrenamiento": corte,
        "prueba": len(real),
    }
    return {
        "modelo": modelo,
        "columnas": list(X.columns),
        "metricas": metricas,
        "evaluacion": {"real": list(real), "probabilidades": list(probabilidades)},
    }


def predecir(paquete, entrada):
    fila = pd.get_dummies(pd.DataFrame([entrada])[VARIABLES], columns=["origen_retorno"], dtype=int)
    fila = fila.reindex(columns=paquete["columnas"], fill_value=0)
    modelo = paquete["modelo"]
    prob = float(modelo.predict_proba(fila)[0, list(modelo.classes_).index(1)])
    # Estos cortes presentan la probabilidad; no sustituyen la respuesta objetivo 0/1.
    nivel = "Alta" if prob >= 0.70 else "Media" if prob >= 0.40 else "Baja"
    return {"probabilidad": prob, "nivel": nivel, "con_carga": int(modelo.predict(fila)[0])}
