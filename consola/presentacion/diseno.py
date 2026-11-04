"""Distribución visual. Las acciones de los botones están en interfaz.py."""

import tkinter as tk
from tkinter import ttk
from .formulario import AYUDA, TITULOS, Formulario


def construir(app):
    app.title("Transpacífico · Prueba local de Machine Learning")
    app.geometry("1100x720")
    app.minsize(950, 680)
    estilo = ttk.Style(app)
    estilo.theme_use("clam")
    estilo.configure("TLabel", font=("Segoe UI", 10))
    estilo.configure("TButton", padding=8, font=("Segoe UI", 10))
    ttk.Label(app, text="TRANSPACÍFICO · Pruebas de los tres modelos", padding=14,
              font=("Segoe UI", 17, "bold")).pack(anchor="w")
    app.pestanas = ttk.Notebook(app)
    app.pestanas.pack(fill="both", expand=True, padx=14)
    for oe, titulo in TITULOS.items():
        pagina = ttk.Frame(app.pestanas, padding=12)
        app.pestanas.add(pagina, text=f"{oe} · {titulo}")
        ttk.Label(pagina, text=AYUDA[oe], padding=(0, 0, 0, 10)).pack(anchor="w")
        columnas = ttk.Frame(pagina)
        columnas.pack(fill="both", expand=True)
        app.formularios[oe] = Formulario(columnas, oe)
        app.formularios[oe].pack(side="left", fill="y", padx=(0, 12))
        resumen = tk.Text(columnas, width=61, wrap="word", font=("Consolas", 10),
                          padx=12, pady=12, state="disabled", relief="flat")
        resumen.pack(side="left", fill="both", expand=True)
        app.textos[oe] = resumen
        app.resultados[oe] = ttk.Label(pagina, text="Primero entrena el modelo desde SQL.",
                                        padding=(0, 12), font=("Segoe UI", 12, "bold"))
        app.resultados[oe].pack(anchor="w")
    barra = ttk.Frame(app, padding=14)
    barra.pack(fill="x")
    for texto, accion in (("1. Leer SQL y entrenar", app.entrenar), ("2. Predecir", app.predecir),
                          ("Ver dataset SQL", app.datos), ("Ver gráficos", app.graficos)):
        ttk.Button(barra, text=texto, command=accion).pack(side="left", padx=(0, 8))
    app.estado = tk.StringVar(value="Fuente: PostgreSQL · División 80/20 · Datos simulados")
    ttk.Label(app, textvariable=app.estado, padding=(14, 0, 14, 12)).pack(anchor="w")
