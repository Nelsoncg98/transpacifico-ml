"""Siete evidencias de prueba, dibujadas con Matplotlib como en los ejemplos de clase."""

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.metrics import ConfusionMatrixDisplay, RocCurveDisplay
from sklearn.tree import plot_tree

from ..config import MODELOS


def guardar(nombre):
    plt.tight_layout()
    plt.savefig(MODELOS / nombre, dpi=130)
    plt.close()


def generar(nombre, paquete):
    if nombre == "oe1":
        e = paquete["evaluacion"]
        plt.figure(figsize=(7, 5))
        plt.scatter(e["real"], e["predicha"], alpha=0.6)
        limite = [min(e["real"]), max(e["real"])]
        plt.plot(limite, limite, "r--")
        plt.title("OE1: duración del dataset y predicción · 20% de prueba")
        plt.xlabel("Duración del dataset (min)")
        plt.ylabel("Duración predicha (min)")
        guardar("oe1_real.png")
        plt.figure(figsize=(8, 5))
        plt.barh(paquete["columnas"], paquete["modelo"].feature_importances_)
        plt.title("OE1: importancia de las variables")
        guardar("oe1_importancia.png")
    elif nombre == "oe2":
        for corredor, p in paquete.items():
            e = p["evaluacion"]
            plt.figure(figsize=(8, 5))
            plt.plot(e["fechas"], e["real"], label="Dataset")
            plt.plot(e["fechas"], e["predicha"], label="Predicción")
            plt.title(f"OE2: corredor {corredor} · 20% de prueba")
            plt.ylabel("Toneladas por semana")
            plt.xticks(rotation=30)
            plt.legend()
            guardar(f"oe2_{corredor.lower()}.png")
    else:
        ConfusionMatrixDisplay(
            np.asarray(paquete["metricas"]["matriz"]), display_labels=["Vacío", "Con carga"]
        ).plot(cmap="Blues")
        plt.title("OE3: matriz de confusión · 20% de prueba")
        guardar("oe3_matriz.png")
        plt.figure(figsize=(18, 8))
        plot_tree(
            paquete["modelo"],
            feature_names=paquete["columnas"],
            class_names=["Vacío", "Con carga"],
            filled=True,
            fontsize=8,
        )
        plt.title("OE3: árbol de decisión entrenado")
        guardar("oe3_arbol.png")
        e = paquete["evaluacion"]
        if len(set(e["real"])) > 1:
            RocCurveDisplay.from_predictions(e["real"], e["probabilidades"])
            plt.title("OE3: curva ROC · 20% de prueba")
            guardar("oe3_roc.png")
