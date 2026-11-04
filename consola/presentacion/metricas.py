"""Resumen compacto calculado con las mismas respuestas del 20 % de prueba."""

import numpy as np
from sklearn.metrics import accuracy_score, f1_score, mean_absolute_error
from sklearn.metrics import mean_squared_error, precision_score, r2_score, recall_score


def regresion(real, predicha, unidad):
    return (f"R²: {r2_score(real, predicha):.4f}  |  "
            f"MAE: {mean_absolute_error(real, predicha):.2f} {unidad}  |  "
            f"RMSE: {np.sqrt(mean_squared_error(real, predicha)):.2f} {unidad}")


def resumir(oe, paquete):
    total = len(paquete["datos"])
    cabecera = f"PostgreSQL · {total:,} filas · Entrenamiento 80 % / Prueba 20 %"
    if oe == "OE2":
        lineas = [cabecera + " por corredor"]
        for corredor, evaluacion in paquete["evaluaciones"].items():
            prueba, predicha = evaluacion["prueba"], evaluacion["predicha"]
            lineas.append(f"{corredor}: " + regresion(prueba.y, predicha, "t"))
        return "\n".join(lineas)
    real, predicha = paquete["real"], paquete["predicha"]
    cabecera += f" ({total - len(real):,} / {len(real):,})"
    if oe == "OE1":
        return cabecera + "\n" + regresion(real, predicha, "min")
    return (cabecera + f"\nExactitud: {accuracy_score(real, predicha):.2%}  |  "
            f"Precisión: {precision_score(real, predicha, zero_division=0):.2%}\n"
            f"Recall: {recall_score(real, predicha, zero_division=0):.2%}  |  "
            f"F1: {f1_score(real, predicha, zero_division=0):.2%}")
