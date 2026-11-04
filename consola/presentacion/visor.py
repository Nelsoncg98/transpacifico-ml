"""Un mismo visor para el panel principal y la ampliación opcional."""

from copy import deepcopy
import tkinter as tk
from tkinter import ttk
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk


class Visor(ttk.Frame):
    def __init__(self, padre, copiar=False):
        super().__init__(padre)
        self.figuras, self.indice, self.copiar = [], 0, copiar
        self.actual = None
        barra = ttk.Frame(self, padding=(0, 6))
        barra.pack(fill="x")
        ttk.Button(barra, text="◀", width=3, command=lambda: self.pasar(-1)).pack(side="left")
        ttk.Button(barra, text="▶", width=3, command=lambda: self.pasar(1)).pack(side="left")
        self.lista = ttk.Combobox(barra, state="disabled", width=38)
        self.lista.pack(side="left", fill="x", expand=True, padx=6)
        self.numero = ttk.Label(barra, text="0 / 0")
        self.numero.pack(side="right")
        self.lista.bind("<<ComboboxSelected>>", lambda _: self.dibujar(self.lista.current()))
        self.contenido = ttk.Frame(self)
        self.contenido.pack(fill="both", expand=True)
        self.cargar([])

    def cargar(self, figuras, indice=0):
        self.figuras = list(figuras)
        self.lista.configure(values=[nombre for nombre, _ in figuras])
        self.lista.configure(state="readonly" if figuras else "disabled")
        self.dibujar(min(max(0, indice), max(0, len(figuras) - 1)))

    def dibujar(self, indice):
        # Retirar el lienzo anterior evita superponer gráficos al cambiar de página.
        for hijo in self.contenido.winfo_children():
            hijo.destroy()
        if self.copiar and self.actual is not None:
            plt.close(self.actual)
        self.actual = None
        self.indice = indice
        if not self.figuras:
            self.lista.set("")
            self.numero.config(text="0 / 0")
            ttk.Label(self.contenido, text="Pulsa «Leer SQL y entrenar» para mostrar los gráficos.",
                      anchor="center").pack(fill="both", expand=True)
            return
        self.lista.current(indice)
        self.numero.config(text=f"{indice + 1} / {len(self.figuras)}")
        figura = self.figuras[indice][1]
        # El popup recibe una copia: su zoom no modifica el gráfico del panel principal.
        if self.copiar:
            figura = deepcopy(figura)
        self.actual = figura
        lienzo = FigureCanvasTkAgg(figura, master=self.contenido)
        herramientas = NavigationToolbar2Tk(lienzo, self.contenido, pack_toolbar=False)
        herramientas.update()
        herramientas.pack(side="bottom", fill="x")
        lienzo.get_tk_widget().pack(fill="both", expand=True)
        lienzo.draw()

    def pasar(self, paso):
        if self.figuras:
            self.dibujar((self.indice + paso) % len(self.figuras))

    def destroy(self):
        if self.copiar and self.actual is not None:
            plt.close(self.actual)
        super().destroy()


def mostrar_graficos(padre, figuras, indice=0):
    ventana = tk.Toplevel(padre)
    ventana.title("Ampliar gráficos del modelo")
    ventana.geometry("1150x740")
    visor = Visor(ventana, copiar=True)
    visor.pack(fill="both", expand=True, padx=10, pady=6)
    visor.cargar(figuras, indice)
    return ventana
