"""Gráfico de la consulta actual, separado de los resultados del 20 % de prueba."""

from matplotlib.figure import Figure


def dibujar(oe, paquete, entrada, resultado):
    figura = Figure(figsize=(9, 5))
    eje = figura.add_subplot()
    if oe == "OE1":
        minutos = resultado["minutos"]
        eje.barh(["Consulta actual"], [minutos], color="#2563eb", height=0.35)
        eje.set_xlim(0, minutos * 1.3)
        eje.set_ylim(-0.7, 0.7)
        eje.text(minutos, 0, f"  {minutos:.2f} min", va="center", fontsize=12)
        eje.set_xlabel("Duración predicha (minutos)")
        eje.set_title(f"OE1: nueva consulta · {entrada['origen']} → {entrada['destino']}")
    elif oe == "OE2":
        corredor = entrada["corredor"]
        historico = paquete["datos"].query("corredor == @corredor").sort_values("semana_inicio")
        import pandas as pd
        eje.plot(pd.to_datetime(historico.semana_inicio), historico.toneladas_semana,
                 color="#94a3b8", label="Dataset SQL (simulado)")
        prueba = paquete["evaluaciones"][corredor]
        eje.plot(prueba["prueba"].ds, prueba["predicha"], color="#2563eb", label="Predicción 20 %")
        eje.vlines(resultado["fecha"], resultado["minimo"], resultado["maximo"], color="#dc2626")
        eje.scatter([resultado["fecha"]], [resultado["toneladas"]], s=140, marker="*",
                    color="#dc2626", label=f"Consulta: {resultado['toneladas']:.2f} t", zorder=5)
        eje.set_title(f"OE2: nueva consulta · corredor {corredor}")
        eje.set_ylabel("Toneladas por semana")
        eje.tick_params(axis="x", rotation=30)
        eje.legend()
    else:
        probabilidad = resultado["probabilidad"]
        valores = [100 * (1 - probabilidad), 100 * probabilidad]
        barras = eje.bar(["Vacío (0)", "Con carga (1)"], valores, color=["#94a3b8", "#2563eb"])
        eje.bar_label(barras, labels=[f"{v:.1f} %" for v in valores], padding=4)
        eje.set(ylim=(0, 110), ylabel="Probabilidad estimada (%)")
        eje.set_title(f"OE3: nueva consulta · {entrada['origen_retorno']} → Callao")
    figura.text(0.5, 0.01, "Consulta nueva: todavía no tiene un resultado observado para calcular su error.",
                ha="center", fontsize=9)
    figura.tight_layout(rect=(0, 0.06, 1, 1))
    return figura
