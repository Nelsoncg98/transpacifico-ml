"""Puente pequeño: ejecutar los modelo.py existentes sin sus preguntas input()."""

from contextlib import redirect_stdout
from importlib import import_module
from io import StringIO
import matplotlib.pyplot as plt
from .arboles import dibujar_xgboost
from .arbol_decision import importancia

MODULOS = {"OE1": "OE1_Tiempo_Viaje.modelo", "OE2": "OE2_Demanda.modelo",
           "OE3": "OE3_Carga_Retorno.modelo"}


def entrenar(oe):
    # Se vuelve a leer SQL en cada entrenamiento; nunca se ejecuta generarSQL.py.
    anteriores = set(plt.get_fignums())
    salida = StringIO()
    try:
        with redirect_stdout(salida):
            paquete = import_module(MODULOS[oe]).principal(interfaz=True)
        figuras = [plt.figure(n) for n in plt.get_fignums() if n not in anteriores]
        if oe == "OE1":
            # Ambos árboles pertenecen al XGBoost recién entrenado para esta ventana.
            figuras += [dibujar_xgboost(paquete["modelo"], i) for i in (0, 1)]
        elif oe == "OE3":
            figuras.append(importancia(paquete))
        paquete["graficos"] = [(f.axes[0].get_title(), f) for f in figuras]
        paquete["resumen"] = salida.getvalue()
        paquete["resumen"] += "\nDatos simulados. Métricas calculadas sobre el 20 % de prueba.\n"
        return paquete
    except Exception:
        # Liberar únicamente las figuras de este intento si falló el entrenamiento.
        for numero in set(plt.get_fignums()) - anteriores:
            plt.close(numero)
        raise


def ejecutar_en_hilo(oe, cola):
    # El hilo trabaja con Python y SQL. Solo la ventana principal modifica Tkinter.
    try:
        cola.put((oe, entrenar(oe), None))
    except Exception as error:
        if type(error).__module__.startswith("psycopg2"):
            mensaje = "No se pudo leer PostgreSQL. Revisa Internet y consola/.env."
        else:
            mensaje = str(error)
        cola.put((oe, None, mensaje))


def liberar(paquete):
    # Soltar figuras anteriores después de retirarlas del visor.
    if paquete:
        for _, figura in paquete.get("graficos", []) + paquete.get("consultas", []):
            plt.close(figura)
