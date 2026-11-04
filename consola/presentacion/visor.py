"""Visor paginado: elegir un gráfico, ampliar con la lupa o guardar una imagen."""

import tkinter as tk
from tkinter import ttk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk


def mostrar_graficos(padre, graficos, consulta=False):
    ventana = tk.Toplevel(padre)
    ventana.title("Gráficos del modelo · datos simulados")
    ventana.geometry("1100x720")
    ventana.minsize(800, 520)
    barra = ttk.Frame(ventana, padding=8)
    barra.pack(fill="x")
    seleccion = tk.StringVar()
    lista = ttk.Combobox(barra, textvariable=seleccion, state="readonly", width=82,
                         values=[nombre for nombre, _ in graficos])
    lista.pack(side="left", fill="x", expand=True, padx=8)
    numero = ttk.Label(barra)
    numero.pack(side="right", padx=8)
    contenido = ttk.Frame(ventana)
    contenido.pack(fill="both", expand=True)

    def dibujar(indice):
        # Destruir el lienzo anterior impide acumular gráficos al pasar de página.
        for hijo in contenido.winfo_children():
            hijo.destroy()
        lista.current(indice)
        numero.config(text=f"{indice + 1} / {len(graficos)}")
        lienzo = FigureCanvasTkAgg(graficos[indice][1], master=contenido)
        herramientas = NavigationToolbar2Tk(lienzo, contenido, pack_toolbar=False)
        herramientas.update()
        herramientas.pack(side="bottom", fill="x")
        lienzo.get_tk_widget().pack(fill="both", expand=True)
        lienzo.draw()

    ttk.Button(barra, text="◀", command=lambda: dibujar((lista.current() - 1) % len(graficos))).pack(side="left")
    ttk.Button(barra, text="▶", command=lambda: dibujar((lista.current() + 1) % len(graficos))).pack(side="left")
    lista.bind("<<ComboboxSelected>>", lambda _: dibujar(lista.current()))
    dibujar(len(graficos) - 1 if consulta else 0)
    return ventana


def mostrar_datos(padre, datos):
    # Son las filas realmente consultadas a SQL; no una tabla armada para la captura.
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
