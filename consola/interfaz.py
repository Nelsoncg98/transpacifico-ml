"""Abrir con py consola/interfaz.py: prueba local con gráficos dentro de la ventana."""

import tkinter as tk
from tkinter import messagebox
from queue import Empty, Queue
from threading import Thread
import matplotlib

matplotlib.use("Agg")  # Las figuras se incorporan a los paneles con FigureCanvasTkAgg.
from presentacion.entrenamiento import ejecutar_en_hilo, liberar
from presentacion.formulario import TITULOS
from presentacion.predicciones import predecir
from presentacion.visor import mostrar_graficos
from presentacion.tabla_datos import mostrar_datos, mostrar_detalle
from presentacion.metricas import resumir
from presentacion.diseno import construir


class Aplicacion(tk.Tk):
    def __init__(self):
        super().__init__()
        self.paquetes, self.formularios, self.metricas, self.resultados, self.paneles = {}, {}, {}, {}, {}
        self.cola, self.ocupado, self.visor = Queue(), False, None
        construir(self)

    def oe(self):
        return list(TITULOS)[self.pestanas.index(self.pestanas.select())]

    def disponible(self):
        if self.ocupado or self.oe() not in self.paquetes:
            messagebox.showinfo("Modelo", "Espera el entrenamiento o pulsa «Leer SQL y entrenar».")
            return False
        return True

    def cerrar_ampliacion(self):
        if self.visor and self.visor.winfo_exists():
            self.visor.destroy()

    def entrenar(self):
        if self.ocupado:
            return
        oe = self.oe()
        self.cerrar_ampliacion()
        self.paneles[oe].cargar([])
        liberar(self.paquetes.pop(oe, None))
        self.resultados[oe].config(text="Entrenando desde PostgreSQL…")
        self.metricas[oe].set("Leyendo SQL y entrenando…")
        self.ocupado = True
        self.estado.set(f"{oe}: leyendo SQL y entrenando… La ventana sigue disponible.")
        Thread(target=ejecutar_en_hilo, args=(oe, self.cola), daemon=True).start()
        self.after(150, self.recibir)

    def recibir(self):
        try:
            oe, paquete, error = self.cola.get_nowait()
        except Empty:
            self.after(150, self.recibir)
            return
        self.ocupado = False
        if error:
            self.metricas[oe].set("Entrenamiento pendiente; revisa la conexión.")
            self.resultados[oe].config(text="No se completó el entrenamiento.")
            self.estado.set("No se modificó SQL ni se reutilizó un modelo anterior.")
            messagebox.showerror("Revisar entrenamiento", error)
            return
        self.paquetes[oe] = paquete
        self.metricas[oe].set(resumir(oe, paquete))
        self.paneles[oe].cargar(paquete["graficos"])
        self.resultados[oe].config(text="Modelo listo. Ingresa los datos y pulsa «Predecir».")
        self.estado.set(f"{oe} listo · PostgreSQL: {len(paquete['datos']):,} filas · División 80/20")

    def predecir(self):
        if not self.disponible():
            return
        oe, paquete = self.oe(), self.paquetes[self.oe()]
        self.cerrar_ampliacion()
        try:
            texto, figuras = predecir(oe, paquete, self.formularios[oe].leer())
            anteriores = paquete.get("consultas", [])
            paquete["consultas"] = figuras
            indice = len(paquete["graficos"]) + len(figuras) - 1
            self.paneles[oe].cargar(paquete["graficos"] + figuras, indice)
            liberar({"graficos": anteriores})
            self.resultados[oe].config(text=texto)
        except ValueError as error:
            self.resultados[oe].config(text="Consulta no ejecutada. Revisa las entradas.")
            self.paneles[oe].cargar(paquete["graficos"])
            liberar({"graficos": paquete.pop("consultas", [])})
            messagebox.showwarning("Revisar consulta", str(error))

    def graficos(self):
        if self.disponible():
            self.cerrar_ampliacion()
            panel = self.paneles[self.oe()]
            self.visor = mostrar_graficos(self, panel.figuras, panel.indice)

    def datos(self):
        if self.disponible():
            mostrar_datos(self, self.paquetes[self.oe()]["datos"])

    def detalle(self):
        if self.disponible():
            mostrar_detalle(self, self.paquetes[self.oe()]["resumen"])


if __name__ == "__main__":
    Aplicacion().mainloop()
