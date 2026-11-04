"""Diez gráficos: resultados de prueba, importancia y árboles entrenados."""

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


def importancia(nombre, paquete):
    """Sumar las categorías para mostrar una barra por variable del modelo."""
    etiquetas = {
        "corredor": "Corredor logístico",
        "destino": "Ciudad de destino",
        "peso_carga_tn": "Peso de carga (t)",
        "dia_salida": "Día de salida",
        "hora_salida": "Hora de salida",
        "origen_retorno": "Ciudad de retorno",
        "dia_entrega_pactada": "Día de entrega pactada",
        "quincena_entrega_pactada": "Quincena de entrega",
        "solicitudes_compatibles": "Solicitudes compatibles",
        "proporcion_retornos_previos": "Proporción previa con carga",
    }
    pesos = {}
    for columna, peso in zip(paquete["columnas"], paquete["modelo"].feature_importances_):
        variable = columna
        # Las columnas 0/1 de una categoría pertenecen a la misma variable original.
        for categoria in ("corredor", "destino", "origen_retorno"):
            if columna.startswith(categoria + "_"):
                variable = categoria
        pesos[variable] = pesos.get(variable, 0.0) + float(peso)
    variables = sorted(pesos, key=pesos.get)
    # Convertir a porcentaje solo para el gráfico; no cambiar ni forzar los pesos.
    valores = [pesos[variable] * 100 for variable in variables]
    plt.figure(figsize=(9, 5))
    barras = plt.barh([etiquetas[variable] for variable in variables], valores)
    plt.bar_label(barras, fmt="%.1f %%", padding=4)
    plt.xlim(0, max(1, max(valores) * 1.18))
    plt.xlabel("Importancia relativa (%)")
    plt.title(f"{nombre.upper()}: importancia de las variables")
    guardar(f"{nombre}_importancia.png")


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
        # Agrupar las columnas binarias, igual que en la demostración local.
        importancia(nombre, paquete)
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
        # Usar el mismo árbol de la matriz y las predicciones, sin volver a entrenar.
        importancia(nombre, paquete)

