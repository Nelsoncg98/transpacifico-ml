"""
Ventana Principal de Pruebas de Machine Learning - TRANSPACÍFICO S.A.C.
Permite entrenar, evaluar y predecir los tres Objetivos Específicos (OE1, OE2, OE3)
de manera interactiva con gráficos integrados dentro de la misma interfaz.
Ejecución: python consola/interfaz.py
"""

import tkinter as tk                                  # -> biblioteca nativa de interfaz gráfica
from tkinter import messagebox                       # -> cuadros de diálogo y alertas para el usuario
from queue import Empty, Queue                        # -> comunicación segura entre hilos sin congelar la ventana
from threading import Thread                          # -> ejecución de tareas pesadas (entrenamiento) en segundo plano
import matplotlib                                     # -> generación de gráficos analíticos

matplotlib.use("Agg")  # -> Las figuras se renderizan en memoria y se incorporan con FigureCanvasTkAgg.

# -> Importación de módulos internos de la capa de presentación
from presentacion.entrenamiento import ejecutar_en_hilo, liberar  # -> puente para entrenar modelos sin bloquear GUI
from presentacion.formulario import TITULOS                      # -> títulos canónicos de cada objetivo específico
from presentacion.predicciones import predecir                   # -> función unificada de inferencia por modelo
from presentacion.visor import mostrar_graficos                  # -> ventana modal para ampliar gráficos
from presentacion.tabla_datos import mostrar_datos, mostrar_detalle  # -> visualizadores de tablas y métricas completas
from presentacion.metricas import resumir                        # -> cálculo compacto de indicadores estadísticos (80/20)
from presentacion.diseno import construir                        # -> ensamblador del diseño gráfico de la ventana


class Aplicacion(tk.Tk):
    """Ventana principal que gestiona las pestañas de los tres modelos predictivos."""

    def __init__(self):
        super().__init__()
        # -> Estructuras de almacenamiento en memoria para cada objetivo (OE1, OE2, OE3)
        self.paquetes = {}       # -> almacena modelos entrenados, métricas y datasets resultantes
        self.formularios = {}    # -> instancias de los formularios de entrada por cada pestaña
        self.metricas = {}       # -> variables de texto para la cabecera estadística superior
        self.resultados = {}     # -> etiquetas para presentar el valor de la predicción calculada
        self.paneles = {}        # -> visores interactivos de gráficos de Matplotlib dentro de la GUI
        
        # -> Control de concurrencia y ventanas auxiliares
        self.cola = Queue()      # -> cola FIFO para recibir el modelo entrenado desde el hilo secundario
        self.ocupado = False     # -> bandera booleana para impedir entrenamientos simultáneos
        self.visor = None        # -> referencia a la ventana emergente de ampliación de figuras
        
        construir(self)          # -> inicializa widgets, pestañas, botones y disposición visual

    def oe(self):
        """Retorna el código del Objetivo Específico actualmente seleccionado en las pestañas ('OE1', 'OE2' o 'OE3')."""
        return list(TITULOS)[self.pestanas.index(self.pestanas.select())]

    def disponible(self):
        """Valida que no haya un entrenamiento en curso y que el modelo de la pestaña activa esté listo para predecir."""
        if self.ocupado or self.oe() not in self.paquetes:
            messagebox.showinfo("Modelo no entrenado", "Primero pulsa «1. Leer SQL y entrenar» para inicializar el modelo.")
            return False
        return True

    def cerrar_ampliacion(self):
        """Cierra la ventana emergente de zoom de gráficos si se encuentra abierta para liberar recursos."""
        if self.visor and self.visor.winfo_exists():
            self.visor.destroy()

    def entrenar(self):
        """Inicia el entrenamiento del modelo correspondiente a la pestaña activa en segundo plano."""
        if self.ocupado:
            return  # -> evita doble pulsación mientras el hilo está trabajando
            
        oe = self.oe()                                       # -> objetivo seleccionado (OE1, OE2 o OE3)
        self.cerrar_ampliacion()                             # -> cerrar ampliaciones previas
        self.paneles[oe].cargar([])                          # -> limpiar panel de gráficos anterior
        liberar(self.paquetes.pop(oe, None))                 # -> liberar figuras y memoria del modelo previo
        
        # -> Actualizar retroalimentación visual en la pestaña activa
        self.resultados[oe].config(text="Entrenando desde PostgreSQL…")
        self.metricas[oe].set("Leyendo SQL y entrenando…")
        self.ocupado = True                                  # -> bloquear acciones hasta finalizar
        
        # -> Lanzar hilo de entrenamiento para que la ventana permanezca fluida y responsiva
        Thread(target=ejecutar_en_hilo, args=(oe, self.cola), daemon=True).start()
        self.after(150, self.recibir)                        # -> programar sondeo periódico de la cola

    def recibir(self):
        """Comprueba periódicamente si el hilo de entrenamiento ha terminado y procesa el resultado."""
        try:
            oe, paquete, error = self.cola.get_nowait()      # -> extraer resultado sin bloquear el flujo principal
        except Empty:
            self.after(150, self.recibir)                    # -> si aún no termina, volver a consultar en 150 ms
            return
            
        self.ocupado = False                                 # -> desbloquear la interfaz para nuevas acciones
        
        if error:
            # -> Manejo y reporte visual de errores de conexión o ejecución
            self.metricas[oe].set("Entrenamiento pendiente; revisa la conexión.")
            self.resultados[oe].config(text="No se completó el entrenamiento.")
            messagebox.showerror("Revisar entrenamiento", error)
            return
            
        # -> Almacenar paquete entrenado y refrescar la vista
        self.paquetes[oe] = paquete                          # -> persistir paquete (modelo, datos, scaler, etc.)
        self.metricas[oe].set(resumir(oe, paquete))          # -> formatear y mostrar indicadores de prueba (80/20)
        self.paneles[oe].cargar(paquete["graficos"])         # -> renderizar gráficos analíticos en el visor
        self.resultados[oe].config(text="Modelo listo. Ingresa los datos y pulsa «Predecir».")

    def predecir(self):
        """Lee los datos del formulario de la pestaña activa, ejecuta la predicción y dibuja el gráfico."""
        if not self.disponible():
            return
            
        oe, paquete = self.oe(), self.paquetes[self.oe()]    # -> contexto del modelo actual
        self.cerrar_ampliacion()                             # -> cerrar ventanas de ampliación anteriores
        
        try:
            entradas = self.formularios[oe].leer()           # -> extraer y validar valores ingresados por el usuario
            texto, figuras = predecir(oe, paquete, entradas) # -> inferencia matemática y generación de gráficos
            
            # -> Actualizar la lista de gráficos para incluir la visualización de la consulta
            anteriores = paquete.get("consultas", [])
            paquete["consultas"] = figuras
            indice = len(paquete["graficos"]) + len(figuras) - 1
            self.paneles[oe].cargar(paquete["graficos"] + figuras, indice)
            liberar({"graficos": anteriores})                # -> liberar memoria de figuras de consultas previas
            self.resultados[oe].config(text=texto)           # -> mostrar el valor resultante (minutos, tons o %)
        except ValueError as error:
            # -> Captura de errores de formato o valores fuera de rango
            self.resultados[oe].config(text="Consulta no ejecutada. Revisa las entradas.")
            self.paneles[oe].cargar(paquete["graficos"])
            liberar({"graficos": paquete.pop("consultas", [])})
            messagebox.showwarning("Revisar consulta", str(error))

    def graficos(self):
        """Abre el gráfico actual en una ventana independiente con herramientas avanzadas de zoom y guardado."""
        if self.disponible():
            self.cerrar_ampliacion()
            panel = self.paneles[self.oe()]
            self.visor = mostrar_graficos(self, panel.figuras, panel.indice)

    def datos(self):
        """Muestra una tabla con todas las filas leídas de PostgreSQL o del CSV para auditoría visual."""
        if self.disponible():
            mostrar_datos(self, self.paquetes[self.oe()]["datos"])

    def detalle(self):
        """Abre un diálogo con el reporte estadístico y matriz de confusión completa generada en consola."""
        if self.disponible():
            mostrar_detalle(self, self.paquetes[self.oe()]["resumen"])


if __name__ == "__main__":
    # -> Punto de entrada principal para la ejecución de la aplicación de escritorio
    Aplicacion().mainloop()
