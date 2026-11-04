"""Ejecutar desde la raíz: py consola/interfaz.py. Usa PostgreSQL; no cambia datos."""

import tkinter as tk
from tkinter import messagebox
from queue import Empty, Queue
from threading import Thread
import matplotlib

# Los modelos generan figuras sin abrir ventanas; el visor las incorpora a Tkinter.
matplotlib.use("Agg")
from presentacion.entrenamiento import ejecutar_en_hilo
from presentacion.formulario import TITULOS
from presentacion.predicciones import predecir
from presentacion.visor import mostrar_datos, mostrar_graficos
from presentacion.diseno import construir


class Aplicacion(tk.Tk):
    def __init__(self):
        super().__init__()
        self.paquetes, self.formularios, self.textos, self.resultados = {}, {}, {}, {}
        self.cola, self.ocupado, self.visor = Queue(), False, None
        construir(self)

    def oe(self):
        return list(TITULOS)[self.pestanas.index(self.pestanas.select())]

    def disponible(self):
        if self.ocupado or self.oe() not in self.paquetes:
            messagebox.showinfo("Modelo", "Espera el entrenamiento o pulsa «Leer SQL y entrenar».")
            return False
        return True

    def entrenar(self):
        if self.ocupado:
            return
        # Un intento nuevo descarta el resultado anterior, incluso si luego falla SQL.
        anterior = self.paquetes.pop(self.oe(), None)
        if self.visor and self.visor.winfo_exists():
            self.visor.destroy()
        if anterior:
            import matplotlib.pyplot as plt
            for _, figura in anterior["graficos"]:
                plt.close(figura)
        self.resultados[self.oe()].config(text="Entrenando desde PostgreSQL…")
        self.ocupado = True
        self.estado.set(f"{self.oe()}: leyendo SQL y entrenando… La ventana sigue disponible.")
        Thread(target=ejecutar_en_hilo, args=(self.oe(), self.cola), daemon=True).start()
        self.after(150, self.recibir)

    def recibir(self):
        try:
            oe, paquete, error = self.cola.get_nowait()
        except Empty:
            self.after(150, self.recibir)
            return
        self.ocupado = False
        if error:
            self.textos[oe].config(state="normal")
            self.textos[oe].delete("1.0", "end")
            self.textos[oe].config(state="disabled")
            self.resultados[oe].config(text="Entrenamiento pendiente. Revisa la conexión y vuelve a intentar.")
            self.estado.set("No se completó el entrenamiento; no se modificó SQL.")
            messagebox.showerror("Revisar entrenamiento", error)
            return
        self.paquetes[oe] = paquete
        texto = self.textos[oe]
        texto.config(state="normal")
        texto.delete("1.0", "end")
        texto.insert("1.0", paquete["resumen"])
        texto.config(state="disabled")
        self.resultados[oe].config(text="Modelo listo. Ingresa los datos y pulsa «Predecir».")
        self.estado.set(f"{oe} listo · PostgreSQL: {len(paquete['datos']):,} filas · Prueba 80/20")

    def predecir(self):
        if not self.disponible():
            return
        try:
            oe, paquete = self.oe(), self.paquetes[self.oe()]
            texto, figura = predecir(oe, paquete, self.formularios[oe].leer())
            paquete["consulta"] = ("Consulta actual · predicción nueva", figura)
            self.resultados[oe].config(text=texto)
            self.graficos(consulta=True)
        except ValueError as error:
            messagebox.showwarning("Revisar consulta", str(error))

    def graficos(self, consulta=False):
        if self.disponible():
            if self.visor and self.visor.winfo_exists():
                self.visor.destroy()
            paquete = self.paquetes[self.oe()]
            figuras = paquete["graficos"] + ([paquete["consulta"]] if "consulta" in paquete else [])
            self.visor = mostrar_graficos(self, figuras, consulta)

    def datos(self):
        if self.disponible():
            mostrar_datos(self, self.paquetes[self.oe()]["datos"])

if __name__ == "__main__":
    Aplicacion().mainloop()
