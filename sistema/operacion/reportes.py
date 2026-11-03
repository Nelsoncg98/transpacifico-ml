"""Indicadores por tramo, exportación CSV y métricas de los modelos."""

import csv
import io
import json
from datetime import datetime

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse, Response

from ..config import MODELOS
from ..db import consultar
from .formularios import exigir, mostrar
from ..seguridad import autorizado

router = APIRouter(dependencies=[Depends(autorizado)])
# Conservar el orden de exposición: OE1, OE2 y OE3.
GRAFICOS = (
    "oe1_real.png",
    "oe1_importancia.png",
    "oe1_arbol_1.png",
    "oe1_arbol_2.png",
    "oe2_centro.png",
    "oe2_norte.png",
    "oe3_matriz.png",
    "oe3_arbol.png",
    "oe3_roc.png",
)


def indicadores():
    # 1. Leer cada tramo con su entrega y su último peso registrado.
    filas = consultar("""SELECT d.id_despacho,s.origen,s.destino,d.estado_viaje,
        d.fof_porcentaje,pod.cumplio_otif,
        COALESCE(d.odometro_final_km-d.odometro_inicial_km,0) AS kilometros,
        COALESCE(p.peso_neto_kg,0) AS peso_kg
        FROM despacho d JOIN solicitud_carga s USING(id_solicitud)
        LEFT JOIN pod_entrega pod USING(id_despacho)
        LEFT JOIN LATERAL (SELECT peso_neto_kg FROM pesaje_bascula
            WHERE id_despacho=d.id_despacho ORDER BY fecha_hora DESC,id_pesaje DESC LIMIT 1
        ) p ON TRUE ORDER BY d.id_despacho""")
    # 2. Calcular los indicadores solo con viajes cerrados.
    cerrados = [f for f in filas if f["estado_viaje"] == "Cerrado"]
    entregados = [f for f in cerrados if f["cumplio_otif"] is not None]
    # 3. Separar kilómetros con carga y en vacío; no sumar dos veces el retorno.
    resumen = {
        "viajes": len(filas),
        "activos": len(filas) - len(cerrados),
        "otif": 100 * sum(f["cumplio_otif"] for f in entregados) / len(entregados)
        if entregados
        else None,
        "fof": sum(float(f["fof_porcentaje"]) for f in cerrados) / len(cerrados)
        if cerrados
        else None,
        "km_vacios": sum(f["kilometros"] for f in cerrados if f["peso_kg"] == 0),
        "km_cargados": sum(f["kilometros"] for f in cerrados if f["peso_kg"] > 0),
    }
    return filas, resumen


@router.get("/reportes.csv")
def exportar():
    # Generar un archivo de consulta; esta descarga no modifica la base.
    filas, _ = indicadores()
    salida = io.StringIO()
    columnas = [
        "id_despacho",
        "origen",
        "destino",
        "estado_viaje",
        "fof_porcentaje",
        "cumplio_otif",
        "kilometros",
        "peso_kg",
    ]
    escritor = csv.DictWriter(salida, fieldnames=columnas)
    escritor.writeheader()
    escritor.writerows(filas)
    return Response(
        "\ufeff" + salida.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=viajes.csv"},
    )


@router.get("/modelos")
def metricas(request: Request, pagina: int = 1):
    # Mostrar los resultados guardados durante el entrenamiento, sin repetirlo.
    ruta = MODELOS / "metricas.json"
    datos = json.loads(ruta.read_text()) if ruta.exists() else None
    if datos:
        datos["fecha"] = datetime.fromisoformat(datos["fecha"])
    # Mostrar una imagen disponible por página, sin volver a entrenar los modelos.
    graficos = [g for g in GRAFICOS if (MODELOS / g).exists()]
    pagina = min(max(pagina, 1), len(graficos) or 1)
    return mostrar(
        request,
        "modelos.html",
        datos=datos,
        graficos=graficos,
        pagina=pagina,
    )


@router.get("/graficos/{archivo}")
def grafico(archivo: str):
    exigir(archivo in GRAFICOS and (MODELOS / archivo).exists(), "El gráfico no está disponible.")
    return FileResponse(MODELOS / archivo, media_type="image/png")
