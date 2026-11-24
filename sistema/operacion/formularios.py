"""Utilidades de presentación HTML, filtros Jinja2, fechas locales y validaciones."""

from datetime import date, datetime

from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from .. import config, db
from . import catalogos_bd

# Mapeo semántico entre el estado persistido en SQL y su clase visual de etiqueta.
CLASES_ESTADO = {
    "Registrada": "b-ambar",
    "Aceptada": "b-exito",
    "Rechazada": "b-error",
    "Anulada": "b-neutro",
    "Programado": "b-info",
    "En patio": "b-ambar",
    "En tránsito": "b-ruta",
    "En destino": "b-info",
    "Cerrado": "b-exito",
    "Cancelado": "b-error",
    "Disponible": "b-exito",
    "Habilitado": "b-exito",
    "Activo": "b-exito",
    "Conforme": "b-exito",
    "Emitida": "b-exito",
    "Asignado": "b-ruta",
    "Pendiente": "b-ambar",
    "Reestiba": "b-error",
    "Observado": "b-error",
    "Mantenimiento": "b-ambar",
    "Inhabilitado": "b-neutro",
    "Inactivo": "b-neutro",
}

plantillas = Jinja2Templates(directory=config.CARPETA / "plantillas")
plantillas.env.globals["FILAS_POR_PAGINA"] = config.FILAS_POR_PAGINA
plantillas.env.filters["numero"] = lambda n: f"{float(n or 0):,.2f}"
plantillas.env.filters["entero"] = lambda n: f"{int(n or 0):,}"
plantillas.env.filters["fecha"] = lambda f: (
    f.astimezone(config.ZONA).strftime("%d/%m/%Y %H:%M")
    if isinstance(f, datetime)
    else (f.strftime("%d/%m/%Y") if isinstance(f, date) else f or "—")
)
plantillas.env.filters["fecha_input"] = lambda f: (
    f.astimezone(config.ZONA).strftime("%Y-%m-%dT%H:%M") if isinstance(f, datetime) else ""
)
plantillas.env.filters["estado_clase"] = lambda e: CLASES_ESTADO.get(str(e or ""), "b-neutro")


def _contar_alertas_activas():
    """Cuenta alertas ETA vinculadas a despachos vigentes (excluye cerrados y cancelados)."""
    try:
        fila = db.obtener(
            """SELECT count(*) AS cantidad FROM alerta a
            JOIN despacho d USING(id_despacho)
            WHERE d.estado_viaje NOT IN ('Cerrado','Cancelado')"""
        )
        return int(fila["cantidad"]) if fila else 0
    except Exception:
        return 0


def _resumen_corredores_seguro():
    """Obtiene la descripción dinámica de corredores en SQL para el pie de página."""
    try:
        return catalogos_bd.obtener_mapa_rutas()["resumen_corredores"]
    except Exception:
        return "Sistema Integrado de Despacho y Flota"


def mostrar(request, archivo, **datos):
    """Renderiza una plantilla Jinja2 inyectando sesión, CSRF, alertas y parámetros base."""
    usuario = request.session.get("usuario")
    alertas_activas = (
        datos.pop("alertas_activas", None)
        if "alertas_activas" in datos
        else (_contar_alertas_activas() if usuario else 0)
    )
    resumen_corredores = (
        datos.pop("resumen_corredores")
        if "resumen_corredores" in datos
        else (_resumen_corredores_seguro() if usuario else "Transportes & Logística del Pacífico S.A.C.")
    )
    return plantillas.TemplateResponse(
        request=request,
        name=archivo,
        context={
            "usuario": usuario,
            "csrf": request.session.get("csrf"),
            "ruta_actual": request.url.path,
            "alertas_activas": alertas_activas,
            "resumen_corredores": resumen_corredores,
            "umbral_fof": config.UMBRAL_FOF_PCT,
            "peso_bruto_max_kg": config.PESO_BRUTO_MAX_KG,
            **datos,
        },
    )


def volver(url, mensaje):
    """Redirige tras POST exitoso (PRG) preservando el mensaje de confirmación en URL."""
    from urllib.parse import urlencode

    return RedirectResponse(url + "?" + urlencode({"mensaje": mensaje}), status_code=303)


def fecha_local(texto):
    """Interpreta marcas datetime-local del navegador como hora oficial de Perú (UTC-5)."""
    fecha = datetime.fromisoformat(texto)
    return fecha.replace(tzinfo=config.ZONA) if fecha.tzinfo is None else fecha


def exigir(condicion, mensaje):
    """Valida precondiciones de negocio lanzando ValueError manejado por FastAPI (HTTP 400)."""
    if not condicion:
        raise ValueError(mensaje)
