"""OE3: importancia de variables y camino real de una consulta por todo el árbol."""

import re
import numpy as np
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg
from sklearn.tree import plot_tree


def importancia(paquete):
    # Consolidar importancia por variable real (sumando las columnas binarias de ciudad)
    mapa_nombres = {
        "dia_entrega_pactada": "Día de entrega pactada",
        "quincena_entrega_pactada": "Quincena de entrega",
        "solicitudes_compatibles": "Solicitudes compatibles disponibles",
        "proporcion_retornos_previos": "Proporción previa con carga",
        "origen_retorno": "Origen del retorno (Ciudad)",
    }
    pesos_reales = {}
    for col, peso in zip(paquete["columnas"], paquete["modelo"].feature_importances_ * 100):
        var_base = "origen_retorno" if col.startswith("origen_retorno") else col
        nombre = mapa_nombres.get(var_base, var_base)
        pesos_reales[nombre] = pesos_reales.get(nombre, 0.0) + peso

    nombres_ord = sorted(pesos_reales.keys(), key=lambda k: pesos_reales[k])
    valores_ord = [pesos_reales[k] for k in nombres_ord]

    figura = Figure(figsize=(9, 4.5))
    eje = figura.add_subplot()
    barras = eje.barh(nombres_ord, valores_ord, color="#2563eb")
    eje.bar_label(barras, labels=[f"{p:.1f} %" for p in valores_ord], padding=4)
    eje.set(xlim=(0, max(1, max(valores_ord)) * 1.18), xlabel="Importancia relativa (%)",
            title="OE3: importancia de las variables del árbol")
    figura.tight_layout()
    return figura


def camino(paquete, fila):
    modelo = paquete["modelo"]
    # Estos métodos entregan los nodos recorridos y la hoja final de ESTA fila.
    recorrido = set(modelo.decision_path(fila).indices)
    hoja = int(modelo.apply(fila)[0])
    figura = Figure(figsize=(20, 10))
    FigureCanvasAgg(figura)  # plot_tree necesita un renderizador antes de entrar al visor Tk.
    eje = figura.add_subplot()
    clases = ["Vacío (0)" if clase == 0 else "Con carga (1)" for clase in modelo.classes_]
    notas = plot_tree(modelo, feature_names=paquete["columnas"], class_names=clases,
                      node_ids=True, filled=True, rounded=True, precision=2, fontsize=9, ax=eje)
    for nota in notas:
        # node_ids=True permite identificar cada nodo sin suponer un orden de dibujo.
        coincidencia = re.search(r"node #(\d+)", nota.get_text())
        if coincidencia is None:  # plot_tree también devuelve las etiquetas True / False.
            continue
        identificador = int(coincidencia.group(1))
        caja = nota.get_bbox_patch()
        if identificador in recorrido:
            caja.set(facecolor="#fef3c7", edgecolor="#dc2626", linewidth=3)
            if nota.arrow_patch:
                nota.arrow_patch.set(color="#dc2626", linewidth=2.5)
        else:
            caja.set_alpha(0.35)
    eje.set_title("OE3: camino de la consulta dentro del árbol completo")
    figura.text(0.5, 0.02, f"Ruta resaltada en rojo y amarillo · Hoja final: {hoja} · "
                "Las demás ramas permanecen visibles.", ha="center", fontsize=10)
    figura.tight_layout(rect=(0, 0.05, 1, 1))
    return figura
