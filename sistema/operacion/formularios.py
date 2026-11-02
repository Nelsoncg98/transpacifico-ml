"""Mostrar HTML, leer fechas de formularios y comprobar datos obligatorios."""

from datetime import datetime

from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from ..config import CARPETA, ZONA

plantillas = Jinja2Templates(directory=CARPETA / "plantillas")
plantillas.env.filters["numero"] = lambda n: f"{float(n or 0):,.2f}"
plantillas.env.filters["fecha"] = lambda f: (
    f.astimezone(ZONA).strftime("%d/%m/%Y %H:%M") if isinstance(f, datetime) else f or "—"
)
plantillas.env.filters["fecha_input"] = lambda f: (
    f.astimezone(ZONA).strftime("%Y-%m-%dT%H:%M") if f else ""
)


def mostrar(request, archivo, **datos):
    # Renderizar el HTML con el usuario y el token de sus formularios.
    return plantillas.TemplateResponse(
        request=request,
        name=archivo,
        context={
            "usuario": request.session.get("usuario"),
            "csrf": request.session.get("csrf"),
            **datos,
        },
    )


def volver(url, mensaje):
    from urllib.parse import urlencode

    return RedirectResponse(url + "?" + urlencode({"mensaje": mensaje}), status_code=303)


def fecha_local(texto):
    # Interpretar una fecha sin zona horaria como hora de Perú.
    fecha = datetime.fromisoformat(texto)
    return fecha.replace(tzinfo=ZONA) if fecha.tzinfo is None else fecha


def exigir(condicion, mensaje):
    if not condicion:
        raise ValueError(mensaje)
