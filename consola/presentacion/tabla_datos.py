"""Mostrar las filas realmente leídas de SQL y el detalle de las métricas."""

import tkinter as tk
from tkinter import ttk


def mostrar_datos(padre, datos):
    ventana = tk.Toplevel(padre)
    ventana.title("Dataset leído de PostgreSQL")
    ventana.geometry("1050x580")
    resumen = (f"Filas: {len(datos):,}  |  Columnas: {len(datos.columns)}  |  "
               f"Nulos: {datos.isna().sum().sum()}  |  Duplicados: {datos.duplicated().sum()}")
    ttk.Label(ventana, text=resumen, padding=12).pack(fill="x")
    marco = ttk.Frame(ventana)
    marco.pack(fill="both", expand=True, padx=12, pady=6)
    tabla = ttk.Treeview(marco, columns=list(datos.columns), show="headings")
    vertical = ttk.Scrollbar(marco, orient="vertical", command=tabla.yview)
    horizontal = ttk.Scrollbar(marco, orient="horizontal", command=tabla.xview)
    tabla.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
    tabla.grid(row=0, column=0, sticky="nsew")
    vertical.grid(row=0, column=1, sticky="ns")
    horizontal.grid(row=1, column=0, sticky="ew")
    marco.rowconfigure(0, weight=1)
    marco.columnconfigure(0, weight=1)
    for nombre in datos.columns:
        tabla.heading(nombre, text=nombre)
        tabla.column(nombre, width=max(130, len(nombre) * 8), stretch=False)
    for fila in datos.itertuples(index=False, name=None):
        tabla.insert("", "end", values=[str(valor) for valor in fila])
    ttk.Label(ventana, text="Los identificadores y fechas de control no se usan como predictores.",
              padding=12).pack(fill="x")


def mostrar_detalle(padre, texto):
    ventana = tk.Toplevel(padre)
    ventana.title("Detalle del entrenamiento y prueba")
    caja = tk.Text(ventana, width=85, height=28, font=("Consolas", 10), padx=12, pady=12)
    caja.pack(fill="both", expand=True)
    caja.insert("1.0", texto)
    caja.config(state="disabled")
