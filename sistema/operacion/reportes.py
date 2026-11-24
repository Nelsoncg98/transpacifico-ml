"""Indicadores operativos en tiempo real, exportación CSV, métricas y reentrenamiento ML."""

from collections import Counter
import csv
import io
import json
from datetime import datetime

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse, Response

from ..config import MODELOS
from ..db import consultar, obtener
from ..ml import entrenar
from ..ml.almacen import cargar as cargar_modelo
from . import catalogos_bd
from .formularios import exigir, mostrar, volver
from ..seguridad import autorizado, permiso

router = APIRouter(dependencies=[Depends(autorizado)])
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
    "oe3_importancia.png",
)
ORDEN_ESTADOS = ("Programado", "En patio", "En tránsito", "En destino", "Cerrado", "Cancelado")


def indicadores():
    """Calcula indicadores globales, operativos activos y por corredor directamente desde SQL."""
    # 1. Leer cada tramo con su corredor, entrega, retorno y último pesaje registrado.
    filas = consultar("""SELECT d.id_despacho, c.nombre AS corredor, s.origen, s.destino,
        d.estado_viaje, d.fof_porcentaje, d.retorno_con_carga, pod.cumplio_otif,
        COALESCE(d.odometro_final_km-d.odometro_inicial_km,0) AS kilometros,
        COALESCE(p.peso_neto_kg,0) AS peso_kg
        FROM despacho d JOIN solicitud_carga s USING(id_solicitud)
        JOIN corredor c USING(id_corredor)
        LEFT JOIN pod_entrega pod USING(id_despacho)
        LEFT JOIN LATERAL (SELECT peso_neto_kg FROM pesaje_bascula
            WHERE id_despacho=d.id_despacho ORDER BY fecha_hora DESC,id_pesaje DESC LIMIT 1
        ) p ON TRUE ORDER BY d.id_despacho""")
    # 2. Separar viajes cerrados, despachos activos reales y entregas con validación OTIF.
    cerrados = [f for f in filas if f["estado_viaje"] == "Cerrado"]
    activos = [f for f in filas if f["estado_viaje"] not in ("Cerrado", "Cancelado")]
    entregados = [f for f in cerrados if f["cumplio_otif"] is not None]

    conteo_estados = {e: 0 for e in ORDEN_ESTADOS}
    for f in filas:
        est = f["estado_viaje"]
        conteo_estados[est] = conteo_estados.get(est, 0) + 1

    # 3. Calcular indicadores comparativos iterando los corredores dinámicos de SQL.
    corredores_sql = [c["nombre"] for c in catalogos_bd.obtener_corredores()]
    origen_principal = (
        Counter(f["origen"] for f in filas).most_common(1)[0][0] if filas else None
    )
    por_corredor = []
    for corr in corredores_sql:
        c_cerr = [f for f in cerrados if f["corredor"] == corr]
        c_ent = [f for f in c_cerr if f["cumplio_otif"] is not None]
        c_idas = [
            f
            for f in c_cerr
            if f["origen"] == origen_principal and f["retorno_con_carga"] is not None
        ]
        por_corredor.append(
            {
                "corredor": corr,
                "viajes": len(c_cerr),
                "otif": round(100 * sum(f["cumplio_otif"] for f in c_ent) / len(c_ent), 2)
                if c_ent
                else 0.0,
                "fof": round(
                    sum(float(f["fof_porcentaje"]) for f in c_cerr) / len(c_cerr), 2
                )
                if c_cerr
                else 0.0,
                "retorno_carga": round(
                    100 * sum(bool(f["retorno_con_carga"]) for f in c_idas) / len(c_idas), 2
                )
                if c_idas
                else 0.0,
            }
        )

    # 4. Consultar operación inmediata para evitar que el histórico cerrado opaque las barras activas.
    tractos_disp = obtener("SELECT count(*) AS cantidad FROM tracto WHERE estado='Disponible'")
    sol_pend = obtener("SELECT count(*) AS cantidad FROM solicitud_carga WHERE estado='Registrada'")
    operacion_activa = [
        {
            "estado": "Tractos disponibles",
            "cantidad": int(tractos_disp["cantidad"]) if tractos_disp else 0,
        },
        {
            "estado": "Solicitudes pendientes",
            "cantidad": int(sol_pend["cantidad"]) if sol_pend else 0,
        },
        {"estado": "Programado", "cantidad": conteo_estados["Programado"]},
        {"estado": "En patio", "cantidad": conteo_estados["En patio"]},
        {"estado": "En tránsito", "cantidad": conteo_estados["En tránsito"]},
        {"estado": "En destino", "cantidad": conteo_estados["En destino"]},
    ]

    resumen = {
        "viajes": len(filas),
        "cerrados": len(cerrados),
        "activos": len(activos),
        "otif": 100 * sum(f["cumplio_otif"] for f in entregados) / len(entregados)
        if entregados
        else None,
        "fof": sum(float(f["fof_porcentaje"]) for f in cerrados) / len(cerrados)
        if cerrados
        else None,
        "km_vacios": sum(f["kilometros"] for f in cerrados if f["peso_kg"] == 0),
        "km_cargados": sum(f["kilometros"] for f in cerrados if f["peso_kg"] > 0),
        "operacion_activa": operacion_activa,
        "por_estado": [{"estado": e, "cantidad": conteo_estados[e]} for e in ORDEN_ESTADOS],
        "por_corredor": por_corredor,
    }
    return filas, resumen


@router.get("/reportes.csv")
def exportar():
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
    escritor = csv.DictWriter(salida, fieldnames=columnas, extrasaction="ignore")
    escritor.writeheader()
    escritor.writerows(filas)
    return Response(
        "\ufeff" + salida.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=viajes.csv"},
    )


def _cargar_evaluaciones_respaldo():
    """Construye series mínimas desde los modelos en disco si evaluaciones.json aún no existe."""
    ruta_eval = MODELOS / "evaluaciones.json"
    if ruta_eval.exists():
        return json.loads(ruta_eval.read_text(encoding="utf-8"))
    series = {}
    try:
        p1 = cargar_modelo("oe1")
        ev1 = p1.get("evaluacion", {})
        puntos = ev1.get("puntos") or [
            {
                "id_despacho": idx + 1,
                "corredor": "Histórico",
                "ruta": "Muestra de prueba",
                "peso_tn": 0,
                "hora_salida": 0,
                "real": round(float(r), 2),
                "predicha": round(float(pr), 2),
            }
            for idx, (r, pr) in enumerate(zip(ev1.get("real", []), ev1.get("predicha", [])))
        ]
        series["oe1"] = {"puntos": puntos, "importancia": ev1.get("importancia", [])}
    except Exception:
        pass
    try:
        p2 = cargar_modelo("oe2")
        series["oe2"] = {}
        for corr, datos_c in p2.items():
            ev2 = datos_c.get("evaluacion", {})
            series["oe2"][corr] = ev2.get("semanas") or [
                {
                    "semana": str(getattr(f, "date", lambda: f)())[:10],
                    "real": round(float(r), 2),
                    "predicha": round(float(pr), 2),
                    "minimo": round(float(pr) * 0.92, 2),
                    "maximo": round(float(pr) * 1.08, 2),
                    "feriados": 0,
                    "dias_quincena": 0,
                }
                for f, r, pr in zip(
                    ev2.get("fechas", []), ev2.get("real", []), ev2.get("predicha", [])
                )
            ]
    except Exception:
        pass
    try:
        p3 = cargar_modelo("oe3")
        ev3 = p3.get("evaluacion", {})
        series["oe3"] = {
            "roc": ev3.get("roc", []),
            "importancia": ev3.get("importancia", []),
            "casos": ev3.get("casos", []),
            "matriz": p3.get("metricas", {}).get("matriz", []),
        }
    except Exception:
        pass
    return series


@router.get("/modelos")
def metricas(request: Request, pagina: int = 1):
    ruta = MODELOS / "metricas.json"
    datos = json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else None
    if datos:
        datos["fecha"] = datetime.fromisoformat(datos["fecha"])
    evaluaciones = _cargar_evaluaciones_respaldo()
    graficos = [g for g in GRAFICOS if (MODELOS / g).exists()]
    pagina = min(max(pagina, 1), len(graficos) or 1)
    return mostrar(
        request,
        "modelos.html",
        datos=datos,
        corredores=catalogos_bd.obtener_corredores(),
        evaluaciones_json=json.dumps(evaluaciones, ensure_ascii=False),
        tiene_series=bool(evaluaciones),
        graficos=graficos,
        pagina=pagina,
    )


@router.post("/modelos/reentrenar")
def reentrenar_modelos(request: Request):
    permiso(request, "ml")
    entrenar.principal()
    return volver(
        "/modelos", "Modelos reentrenados y gráficos actualizados con los datos actuales de SQL."
    )


@router.get("/graficos/{archivo}")
def grafico(archivo: str):
    exigir(archivo in GRAFICOS and (MODELOS / archivo).exists(), "El gráfico no está disponible.")
    return FileResponse(MODELOS / archivo, media_type="image/png")

