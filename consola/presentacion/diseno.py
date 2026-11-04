"""Entradas y resultado a la izquierda; métricas y gráfico a la derecha."""

import tkinter as tk
from tkinter import ttk
from .formulario import AYUDA, TITULOS, Formulario
from .visor import Visor


def construir(app):
    app.title("Transpacífico · Prueba local de Machine Learning")
    ancho = min(1320, app.winfo_screenwidth() - 80)
    alto = min(800, app.winfo_screenheight() - 100)
    app.geometry(f"{ancho}x{alto}")
    app.minsize(1000, 660)
    estilo = ttk.Style(app)
    estilo.theme_use("clam")
    estilo.configure("TLabel", font=("Segoe UI", 10))
    estilo.configure("TButton", padding=6, font=("Segoe UI", 10))
    ttk.Label(app, text="TRANSPACÍFICO · Pruebas de los tres modelos", padding=10,
              font=("Segoe UI", 16, "bold")).pack(anchor="w")
    app.pestanas = ttk.Notebook(app)
    app.pestanas.pack(fill="both", expand=True, padx=10)
    for oe, titulo in TITULOS.items():
        pagina = ttk.Frame(app.pestanas, padding=10)
        app.pestanas.add(pagina, text=f"{oe} · {titulo.split(' · ')[0]}")
        ttk.Label(pagina, text=f"{titulo}\n{AYUDA[oe]}", padding=(0, 0, 0, 8)).pack(anchor="w")
        columnas = ttk.PanedWindow(pagina, orient="horizontal")
        columnas.pack(fill="both", expand=True)
        izquierda = ttk.Frame(columnas, padding=(0, 0, 12, 0))
        derecha = ttk.Frame(columnas)
        columnas.add(izquierda, weight=0)
        columnas.add(derecha, weight=1)
        app.formularios[oe] = Formulario(izquierda, oe)
        app.formularios[oe].pack(fill="x")
        resultado = ttk.LabelFrame(izquierda, text="Resultado de la predicción", padding=12)
        resultado.pack(fill="x", pady=(12, 0))
        app.resultados[oe] = ttk.Label(resultado, text="Primero entrena desde SQL.",
                                        wraplength=310, font=("Segoe UI", 12, "bold"))
        app.resultados[oe].pack(fill="x")
        app.metricas[oe] = tk.StringVar(value="PostgreSQL · Entrenamiento pendiente")
        cabecera = ttk.Label(derecha, textvariable=app.metricas[oe], padding=10,
                              relief="groove", anchor="w", wraplength=650)
        cabecera.pack(fill="x")
        cabecera.bind("<Configure>", lambda evento, w=cabecera:
                      w.configure(wraplength=max(1, evento.width - 20)))
        app.paneles[oe] = Visor(derecha)
        app.paneles[oe].pack(fill="both", expand=True)
    barra = ttk.Frame(app, padding=10)
    barra.pack(fill="x")
    botones = (("1. Leer SQL y entrenar", app.entrenar), ("2. Predecir", app.predecir),
               ("Ver dataset SQL", app.datos), ("Ampliar gráfico", app.graficos),
               ("Detalle de métricas", app.detalle))
    for texto, accion in botones:
        ttk.Button(barra, text=texto, command=accion).pack(side="left", padx=(0, 8))
    app.estado = tk.StringVar(value="PostgreSQL · Datos simulados · Predicción sin cambiar registros")
    ttk.Label(app, textvariable=app.estado, padding=(10, 0, 10, 8)).pack(anchor="w")
