"""Cálculos de presentación. El tiempo total lo predice el modelo, no esta fórmula."""

from datetime import timedelta, timezone
from datetime import date

from .pantallas import exigir


def limites_velocidad(distancia):
    # Rangos de velocidad media de los datos de práctica aprobados.
    return (25, 55) if float(distancia) == 395 else (45, 78)


def validar_velocidad(distancia, velocidad):
    minimo, maximo = limites_velocidad(distancia)
    exigir(
        minimo <= velocidad <= maximo,
        f"Para esta ruta, la práctica utiliza velocidades medias de {minimo} a {maximo} km/h.",
    )


def entrada_eta(datos, peso, salida, velocidad):
    validar_velocidad(datos["distancia_km"], velocidad)
    # Las columnas históricas del SQL actual extraen día y hora en UTC.
    fecha_modelo = salida.astimezone(timezone.utc)
    return {
        "origen": datos["origen"],
        "destino": datos["destino"],
        "distancia_km": float(datos["distancia_km"]),
        "peso_carga_tn": peso,
        "dia_salida": fecha_modelo.isoweekday(),
        "hora_salida": fecha_modelo.hour,
        "velocidad_media_estimada_kmh": velocidad,
    }


def calcular_eta(total, distancia, salida, consulta, restantes=None):
    exigir(distancia > 0, "La distancia de la ruta debe ser mayor que cero.")
    if restantes is None:
        return {
            "total_min": total,
            "restante_min": None,
            "llegada": salida + timedelta(minutes=total),
        }
    exigir(0 <= restantes <= distancia, "Los kilómetros restantes deben estar dentro de la ruta.")
    exigir(consulta >= salida, "La consulta en ruta no puede ser anterior a la salida.")
    # Aproximación acordada: mantener proporcionalmente el ritmo del recorrido completo.
    restante = total * restantes / distancia
    return {
        "total_min": total,
        "restante_min": restante,
        "llegada": consulta + timedelta(minutes=restante),
    }


def curva(historial, resultado=None):
    """Coordenadas de un gráfico SVG sencillo, sin librerías de JavaScript."""
    valores = [float(r["toneladas_estimadas"]) for r in historial]
    fechas = [date.fromisoformat(str(r["semana_inicio"])) for r in historial]
    if resultado:
        fechas += [date.fromisoformat(resultado["semana"])]
    if not valores:
        return {"puntos": "", "maximo": 0}
    maximo = max(valores + ([resultado["maximo"]] if resultado else [])) * 1.1 or 1
    inicio, fin = min(fechas), max(fechas)

    def x(fecha):
        return 20 + (fecha - inicio).days * 660 / max(1, (fin - inicio).days)

    def y(valor):
        return 180 - valor / maximo * 160

    puntos = " ".join(f"{x(f):.1f},{y(v):.1f}" for f, v in zip(fechas, valores))
    return {
        "puntos": puntos,
        "maximo": maximo,
        "inicio": inicio,
        "fin": fin,
        "x": x(fechas[-1]) if resultado else None,
        "y": y(resultado["toneladas"]) if resultado else None,
        "y_min": y(resultado["minimo"]) if resultado else None,
        "y_max": y(resultado["maximo"]) if resultado else None,
    }
