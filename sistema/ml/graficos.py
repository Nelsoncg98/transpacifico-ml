"""Nueve gráficos: resultados de prueba y árboles de los modelos entrenados."""

import matplotlib
import numpy as np
from pathlib import Path
from graphviz.backend import dot_command

# Guardar imágenes en Render sin necesitar una ventana ni una pantalla gráfica.
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.metrics import ConfusionMatrixDisplay, RocCurveDisplay
from sklearn.tree import plot_tree
from xgboost import plot_tree as plot_tree_xgboost

from ..config import MODELOS

# Render prepara Graphviz aparte; indicar su ruta evita depender del PATH de Python.
dot_render = Path(__file__).resolve().parents[2] / ".graphviz/programa/usr/bin/dot"
if dot_render.is_file():
    dot_command.DOT_BINARY = dot_render


def guardar(nombre):
    # Ajustar los márgenes, guardar el PNG y liberar la figura utilizada.
    plt.tight_layout()
    plt.savefig(MODELOS / nombre, dpi=130)
    plt.close()


def generar(nombre, paquete):
    if nombre == "oe1":
        # OE1: comparar duraciones del conjunto de prueba con las predichas.
        e = paquete["evaluacion"]
        plt.figure(figsize=(7, 5))
        plt.scatter(e["real"], e["predicha"], alpha=0.6)
        limite = [min(e["real"]), max(e["real"])]
        plt.plot(limite, limite, "r--")
        plt.title("OE1: duración del dataset y predicción · 20% de prueba")
        plt.xlabel("Duración del dataset (min)")
        plt.ylabel("Duración predicha (min)")
        guardar("oe1_real.png")
        # Mostrar cuánto utiliza XGBoost cada variable en sus árboles.
        plt.figure(figsize=(8, 5))
        plt.barh(paquete["columnas"], paquete["modelo"].feature_importances_)
        plt.title("OE1: importancia de las variables")
        guardar("oe1_importancia.png")
        # Dibujar completos los árboles 0 y 1 del mismo XGBoost que se guarda para predecir.
        for indice in (0, 1):
            figura, eje = plt.subplots(figsize=(16, 11))
            plot_tree_xgboost(
                paquete["modelo"], tree_idx=indice, rankdir="LR", with_stats=True, ax=eje
            )
            eje.set_title(f"OE1: XGBoost · árbol {indice + 1} completo")
            figura.savefig(MODELOS / f"oe1_arbol_{indice + 1}.png", dpi=200, bbox_inches="tight")
            plt.close(figura)
    elif nombre == "oe2":
        # OE2: comparar las toneladas observadas y predichas, semana a semana.
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
        # OE3: contar aciertos y errores al clasificar vacío / con carga.
        ConfusionMatrixDisplay(
            np.asarray(paquete["metricas"]["matriz"]), display_labels=["Vacío", "Con carga"]
        ).plot(cmap="Blues")
        plt.title("OE3: matriz de confusión · 20% de prueba")
        guardar("oe3_matriz.png")
        # Sin max_depth: mostrar todas las decisiones y hojas, como en el informe.
        plt.figure(figsize=(24, 12))
        plot_tree(
            paquete["modelo"],
            feature_names=paquete["columnas"],
            class_names=["Vacío", "Con carga"],
            filled=True,
        )
        plt.title("OE3: árbol de decisión entrenado")
        guardar("oe3_arbol.png")
        e = paquete["evaluacion"]
        if len(set(e["real"])) > 1:
            # La curva ROC evalúa las probabilidades con distintos umbrales.
            RocCurveDisplay.from_predictions(e["real"], e["probabilidades"])
            plt.title("OE3: curva ROC · 20% de prueba")
            guardar("oe3_roc.png")
