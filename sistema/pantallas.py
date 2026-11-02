"""Funciones compartidas por las pantallas y sus formularios."""

from datetime import datetime

from fastapi import HTTPException
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from .config import CARPETA, ZONA
from .db import obtener

plantillas = Jinja2Templates(directory=CARPETA / "plantillas")
plantillas.env.filters["numero"] = lambda n: f"{float(n or 0):,.2f}"
plantillas.env.filters["fecha"] = lambda f: (
    f.astimezone(ZONA).strftime("%d/%m/%Y %H:%M") if isinstance(f, datetime) else f or "—"
)
plantillas.env.filters["fecha_input"] = lambda f: (
    f.astimezone(ZONA).strftime("%Y-%m-%dT%H:%M") if f else ""
)


def mostrar(request, archivo, **datos):
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
    fecha = datetime.fromisoformat(texto)
    return fecha.replace(tzinfo=ZONA) if fecha.tzinfo is None else fecha


def viaje(id_viaje, con=None, bloquear=False):
    sql = """
        SELECT d.*, s.origen, s.destino, s.peso_tn, s.ventana_entrega,
               s.tipo_carga, s.nro_guia_remitente, c.distancia_km,
               sr.capacidad_tn, t.placa
        FROM despacho d JOIN solicitud_carga s USING(id_solicitud)
        JOIN corredor c USING(id_corredor)
        JOIN semirremolque sr USING(id_semirremolque)
        JOIN tracto t USING(id_tracto) WHERE d.id_despacho=%s
    """
    if bloquear:
        sql += " FOR UPDATE OF d"
    fila = con.execute(sql, (id_viaje,)).fetchone() if con else obtener(sql, (id_viaje,))
    if not fila:
        raise HTTPException(404, "No se encontró el viaje.")
    return fila


def exigir(condicion, mensaje):
    if not condicion:
        raise ValueError(mensaje)
