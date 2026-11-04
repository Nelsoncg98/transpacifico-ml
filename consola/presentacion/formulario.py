"""Campos visibles: nombres, unidades, ejemplos y límites de la práctica."""

from datetime import date, timedelta
import tkinter as tk
from tkinter import ttk

TITULOS = {"OE1": "Duración del viaje · XGBoost", "OE2": "Demanda semanal · Prophet",
           "OE3": "Retorno con carga · Árbol de decisión"}
LUNES = date.today() - timedelta(days=date.today().weekday())
# Cada fila contiene: columna, etiqueta, ejemplo y opciones o límites numéricos.
CAMPOS = {
    "OE1": [
        ("corredor", "Corredor logístico", "Centro", ("Centro", "Norte")),
        ("destino", "Ciudad de destino", "Huancayo", ("Huancayo", "Trujillo", "Callao")),
        ("peso_carga_tn", "Peso neto de carga (t)", 25.0, (0, 29)),
        ("dia_salida", "Día de salida (1=lunes, 7=domingo)", 1, (1, 7)),
        ("hora_salida", "Hora de salida (0 a 23 h)", 8, (0, 23)),
    ],
    "OE2": [
        ("corredor", "Corredor", "Centro", ("Centro", "Norte")),
        ("semana_inicio", "Lunes de la semana (AAAA-MM-DD)", str(LUNES), None),
        ("feriados_semana", "Feriados de esa semana", 0, (0, 2)),
    ],
    "OE3": [
        ("origen_retorno", "Ciudad de retorno hacia Callao", "Huancayo", ("Huancayo", "Trujillo")),
        ("dia_entrega_pactada", "Día de entrega (1=lunes, 7=domingo)", 1, (1, 7)),
        ("quincena_entrega_pactada", "Quincena de entrega (1 o 2)", 1, (1, 2)),
        ("solicitudes_compatibles", "Solicitudes compatibles disponibles", 3, (0, 5)),
        ("proporcion_retornos_previos", "Proporción previa con carga (0 a 1)", 0.5, (0, 1)),
    ],
}
AYUDA = {
    "OE1": "Predice minutos del viaje según corredor y destino (Centro=Sierra, Norte=Costa).\n"
           "Destino Callao representa retorno; Huancayo/Trujillo representa viaje de ida.",
    "OE2": "Predice toneladas de una semana. Los días de segunda quincena se cuentan\n"
           "automáticamente desde el lunes elegido; también se muestran en el resultado.",
    "OE3": "Predice 0=vacío o 1=con carga. La proporción previa es una entrada,\n"
           "mientras que la probabilidad y el nivel son resultados del modelo.",
}


class Formulario(ttk.LabelFrame):
    def __init__(self, padre, oe):
        super().__init__(padre, text="Variables de la consulta", padding=10)
        self.oe, self.valores = oe, {}
        for fila, (nombre, etiqueta, ejemplo, opciones) in enumerate(CAMPOS[oe]):
            ttk.Label(self, text=etiqueta, wraplength=155).grid(
                row=fila, column=0, sticky="w", padx=(0, 8))
            valor = tk.StringVar(value=str(ejemplo))
            self.valores[nombre] = valor
            if isinstance(ejemplo, str) and opciones:
                campo = ttk.Combobox(self, textvariable=valor, values=opciones, state="readonly")
            elif opciones:
                campo = ttk.Spinbox(self, textvariable=valor, from_=opciones[0], to=opciones[1])
            else:
                campo = ttk.Entry(self, textvariable=valor)
            campo.configure(width=13)
            campo.grid(row=fila, column=1, sticky="ew", pady=6)
        self.columnconfigure(1, weight=1)

    def leer(self):
        # Convertir una sola vez el texto del formulario a los tipos que usa el modelo.
        entrada = {}
        for nombre, etiqueta, ejemplo, limites in CAMPOS[self.oe]:
            texto = self.valores[nombre].get().strip()
            try:
                valor = type(ejemplo)(texto)  # int, float o str, según el campo declarado.
            except ValueError:
                raise ValueError(f"Revisa el número de: {etiqueta}.") from None
            if not isinstance(ejemplo, str) and not limites[0] <= valor <= limites[1]:
                raise ValueError(f"{etiqueta}: usa un valor entre {limites[0]} y {limites[1]}.")
            entrada[nombre] = valor
        return entrada
