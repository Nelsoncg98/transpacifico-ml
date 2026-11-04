"""Dibujar árboles completos a partir de los nodos reales de XGBoost."""

import json
from textwrap import fill
from matplotlib.figure import Figure


def dibujar_xgboost(modelo, indice):
    # get_dump exporta las divisiones y hojas del modelo, sin inventar reglas.
    raiz = json.loads(modelo.get_booster().get_dump(dump_format="json", with_stats=True)[indice])
    posiciones, nodos, ramas = {}, {}, []
    hojas = []

    def ubicar(nodo, profundidad=0):
        identificador = nodo["nodeid"]
        nodos[identificador] = nodo
        if "leaf" in nodo:
            x = len(hojas)
            hojas.append(identificador)
        else:
            hijos = [ubicar(hijo, profundidad + 1) for hijo in nodo["children"]]
            x = sum(hijos) / len(hijos)
            ramas.extend((identificador, hijo["nodeid"]) for hijo in nodo["children"])
        posiciones[identificador] = (x, -profundidad)
        return x

    ubicar(raiz)
    figura = Figure(figsize=(20, 10), layout="constrained")
    eje = figura.add_subplot()
    # La ubicación cambia el dibujo, pero conserva todos los nodos y conexiones.
    for padre, hijo in ramas:
        x1, y1 = posiciones[padre]
        x2, y2 = posiciones[hijo]
        eje.plot([x1, x2], [y1, y2], color="#64748b", zorder=0)
        nodo = nodos[padre]
        texto = "Sí" if hijo == nodo["yes"] else "No"
        if hijo == nodo["missing"]:
            texto += " / faltante"
        eje.text((x1 + x2) / 2, (y1 + y2) / 2, texto, fontsize=8,
                 ha="center", bbox={"facecolor": "white", "edgecolor": "none"})
    for identificador, nodo in nodos.items():
        if "leaf" in nodo:
            texto = f"Hoja {identificador}\nAporte: {nodo['leaf']:.3f}"
            color = "#dcfce7"
        else:
            nombre = fill(nodo["split"].replace("_", " "), 22)
            texto = f"Nodo {identificador}\n{nombre} < {nodo['split_condition']:.3f}"
            color = "#dbeafe"
        texto += f"\nCobertura: {nodo['cover']:.2f}"
        eje.text(*posiciones[identificador], texto, ha="center", va="center", fontsize=8,
                 bbox={"boxstyle": "round,pad=0.5", "facecolor": color, "edgecolor": "#64748b"})
    profundidad = max(-y for _, y in posiciones.values())
    eje.set(xlim=(-0.8, len(hojas) - 0.2), ylim=(-profundidad - 0.5, 0.6))
    eje.axis("off")
    eje.set_title(f"OE1: XGBoost · árbol {indice + 1} completo ({len(nodos)} nodos)")
    figura.text(0.5, 0.01, "Cada árbol aporta al resultado conjunto; una hoja no es la duración total.",
                ha="center", fontsize=10)
    return figura
