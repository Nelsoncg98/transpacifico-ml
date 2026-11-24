"""Consultas dinámicas de catálogos, sedes y mapa de rutas desde PostgreSQL.

Centraliza la lectura de corredores, ciudades operativas, rutas históricas
válidas y texto resumen del pie de página para evitar listas fijas en código
Python o plantillas HTML.
"""

from .. import config, db


def obtener_corredores():
    """Retorna la lista ordenada de corredores logísticos registrados en SQL."""
    return db.consultar(
        "SELECT id_corredor, nombre, distancia_km FROM corredor ORDER BY nombre"
    )


def obtener_sedes():
    """Obtiene dinámicamente todas las sedes operativas registradas en la base de datos.

    Combina sedes asignadas a usuarios con orígenes y destinos registrados en
    solicitudes de carga. Si la base aún no tiene datos, utiliza el respaldo base.
    """
    try:
        filas = db.consultar(
            """SELECT DISTINCT sede FROM (
                SELECT sede_operativa AS sede FROM usuario
                UNION SELECT origen AS sede FROM solicitud_carga
                UNION SELECT destino AS sede FROM solicitud_carga
            ) AS t
            WHERE sede IS NOT NULL AND trim(sede) <> ''
            ORDER BY sede"""
        )
        sedes = [str(f["sede"]).strip() for f in filas if str(f.get("sede") or "").strip()]
        return sedes or list(config.SEDES_RESPALDO)
    except Exception:
        return list(config.SEDES_RESPALDO)


def obtener_mapa_rutas():
    """Construye el catálogo dinámico de corredores, ciudades y rutas válidas por corredor.

    Retorna un diccionario con:
    - corredores: filas de la tabla corredor (id_corredor, nombre, distancia_km).
    - ciudades: lista ordenada de todas las ciudades/sedes presentes en SQL.
    - rutas_por_corredor: mapa {id_corredor: [{'origen': o, 'destino': d}, ...]} observado.
    - pares_por_corredor: mapa {id_corredor: [(o, d), ...]} para validación en servidor.
    - resumen_corredores: cadena descriptiva dinámica para el pie de página del portal.
    """
    corredores = obtener_corredores()
    pares_sql = db.consultar(
        """SELECT DISTINCT id_corredor, origen, destino
        FROM solicitud_carga
        WHERE origen IS NOT NULL AND destino IS NOT NULL
        ORDER BY id_corredor, origen, destino"""
    )

    ciudades_set = set()
    for sede in obtener_sedes():
        ciudades_set.add(sede)

    rutas_por_corredor = {int(c["id_corredor"]): [] for c in corredores}
    pares_por_corredor = {int(c["id_corredor"]): [] for c in corredores}

    for fila in pares_sql:
        cid = int(fila["id_corredor"])
        origen = str(fila["origen"]).strip()
        destino = str(fila["destino"]).strip()
        if not origen or not destino:
            continue
        ciudades_set.add(origen)
        ciudades_set.add(destino)
        if cid in rutas_por_corredor:
            par = (origen, destino)
            if par not in pares_por_corredor[cid]:
                pares_por_corredor[cid].append(par)
                rutas_por_corredor[cid].append({"origen": origen, "destino": destino})

    # Si un corredor registrado aún no tiene histórico de solicitudes, queda abierto a ciudades !=.
    partes_resumen = []
    for corr in corredores:
        cid = int(corr["id_corredor"])
        dist = round(float(corr["distancia_km"]))
        pares = rutas_por_corredor.get(cid, [])
        if pares:
            pares_txt = ", ".join(f"{p['origen']}–{p['destino']}" for p in pares[:2])
            partes_resumen.append(f"{corr['nombre']} ({pares_txt} · {dist} km)")
        else:
            partes_resumen.append(f"{corr['nombre']} ({dist} km)")

    resumen = (
        "Corredores activos: " + " · ".join(partes_resumen)
        if partes_resumen
        else "Sin corredores registrados en base de datos"
    )
    return {
        "corredores": corredores,
        "ciudades": sorted(ciudades_set),
        "rutas_por_corredor": rutas_por_corredor,
        "pares_por_corredor": pares_por_corredor,
        "resumen_corredores": resumen,
    }
