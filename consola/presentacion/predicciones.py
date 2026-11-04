"""Una consulta nueva usa el modelo entrenado; no modifica SQL ni las métricas."""

from datetime import date, timedelta
import pandas as pd
from .grafico_consulta import dibujar
from .arbol_decision import camino


def predecir(oe, paquete, entrada):
    if oe == "OE1":
        if entrada["corredor"] == "Centro" and entrada["destino"] not in ("Huancayo", "Callao"):
            raise ValueError("Para el Corredor Centro, el destino debe ser Huancayo (ida) o Callao (retorno).")
        if entrada["corredor"] == "Norte" and entrada["destino"] not in ("Trujillo", "Callao"):
            raise ValueError("Para el Corredor Norte, el destino debe ser Trujillo (ida) o Callao (retorno).")
        categorias = ["corredor", "destino"]
    elif oe == "OE2":
        try:
            lunes = date.fromisoformat(entrada["semana_inicio"])
        except ValueError:
            raise ValueError("Escribe el lunes como AAAA-MM-DD.") from None
        if lunes.weekday() != 0:
            raise ValueError("El inicio de semana debe ser un lunes.")
        dias = sum((lunes + timedelta(days=i)).day >= 16 for i in range(7))
        fila = pd.DataFrame([{"ds": pd.Timestamp(lunes), "feriados_semana": entrada["feriados_semana"],
                              "dias_segunda_quincena": dias}])
        modelo = paquete["modelos"][entrada["corredor"]]
        pronostico = modelo.predict(fila).iloc[0]
        resultado = {"toneladas": max(0.0, float(pronostico.yhat)), "fecha": pd.Timestamp(lunes),
                     "minimo": max(0.0, float(pronostico.yhat_lower)),
                     "maximo": max(0.0, float(pronostico.yhat_upper)), "dias_quincena": dias}
        texto = (f"{entrada['corredor']}: {resultado['toneladas']:.2f} toneladas\n"
                 f"Intervalo: {resultado['minimo']:.2f}–{resultado['maximo']:.2f} t. "
                 f"Días de segunda quincena: {dias}.")
        return texto, [("Consulta actual · pronóstico semanal", dibujar(oe, paquete, entrada, resultado))]
    else:
        if entrada["origen_retorno"] not in paquete["datos"].origen_retorno.unique():
            raise ValueError("No hay casos de entrenamiento para esa ciudad de retorno.")
        categorias = ["origen_retorno"]
    # La misma codificación 0/1 y el mismo orden de columnas de los modelo.py.
    fila = pd.get_dummies(pd.DataFrame([entrada]), columns=categorias, dtype=int)
    fila = fila.reindex(columns=paquete["columnas"], fill_value=0)
    modelo = paquete["modelo"]
    valor = modelo.predict(fila)[0]
    if oe == "OE1":
        resultado = {"minutos": float(valor)}
        minutos = round(float(valor))
        texto = f"Duración predicha: {float(valor):.2f} minutos ({minutos // 60} h {minutos % 60} min)."
    else:
        columna = list(modelo.classes_).index(1)
        probabilidad = float(modelo.predict_proba(fila)[0, columna])
        nivel = "Alta" if probabilidad >= 0.70 else "Media" if probabilidad >= 0.40 else "Baja"
        resultado = {"probabilidad": probabilidad}
        clase = "CON CARGA (1)" if int(valor) == 1 else "VACÍO (0)"
        texto = f"Retorno: {clase}\nProbabilidad con carga: {probabilidad:.1%}. Oportunidad: {nivel}."
    figuras = [("Consulta actual · resultado", dibujar(oe, paquete, entrada, resultado))]
    if oe != "OE1":
        figuras.append(("Consulta actual · camino dentro del árbol", camino(paquete, fila)))
    return texto, figuras
