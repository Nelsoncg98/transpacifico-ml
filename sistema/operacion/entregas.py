"""Incidencias y cierre del viaje con evidencia de entrega."""

from fastapi import APIRouter, Depends, Form, Request

from ..db import viaje, conexion, guardar
from .formularios import exigir, fecha_local, volver
from ..seguridad import autorizado, permiso

router = APIRouter(dependencies=[Depends(autorizado)])


@router.post("/viajes/{id_viaje}/incidencia")
def incidencia(
    request: Request,
    id_viaje: int,
    tipo: str = Form(),
    descripcion: str = Form(),
    accion: str = Form(default=""),
):
    permiso(request, "entregas")
    # Comprobar que el viaje exista antes de asociarle la incidencia.
    viaje(id_viaje)
    guardar(
        """INSERT INTO incidencia(id_despacho,tipo,descripcion,accion_tomada)
        VALUES(%s,%s,%s,%s)""",
        (id_viaje, tipo.strip(), descripcion.strip(), accion.strip()),
    )
    return volver(f"/viajes/{id_viaje}", "Incidencia registrada.")


@router.post("/viajes/{id_viaje}/llegar")
def llegar(request: Request, id_viaje: int):
    permiso(request, "entregas")
    # Solo un viaje en tránsito puede pasar a En destino.
    with conexion() as con:
        datos_viaje = viaje(id_viaje, con, True)
        exigir(datos_viaje["estado_viaje"] == "En tránsito", "El viaje debe estar en tránsito.")
        con.execute(
            "UPDATE despacho SET estado_viaje='En destino' WHERE id_despacho=%s", (id_viaje,)
        )
    return volver(f"/viajes/{id_viaje}", "Llegada al destino registrada.")


@router.post("/viajes/{id_viaje}/entregar")
def entregar(
    request: Request,
    id_viaje: int,
    fecha: str = Form(),
    receptor: str = Form(),
    dni: str = Form(),
    foto: str = Form(),
    odometro: int = Form(),
    precintos_conformes: bool = Form(default=False),
    carga_completa: bool = Form(default=False),
):
    # 1. Revisar permisos; el formato de los campos se controla en el HTML.
    permiso(request, "entregas")

    with conexion() as con:
        datos_viaje = viaje(id_viaje, con, True)
        exigir(
            datos_viaje["estado_viaje"] == "En destino", "Primero registra la llegada al destino."
        )
        # 2. Comprobar la secuencia de fechas y que el odómetro no disminuya.
        real = fecha_local(fecha)
        exigir(
            real >= datos_viaje["fecha_hora_salida"],
            "La entrega no puede ser anterior a la salida.",
        )
        exigir(
            odometro >= datos_viaje["odometro_inicial_km"], "El odómetro final no puede disminuir."
        )
        # 3. Calcular OTIF con la fecha real, los precintos y la carga completa.
        otif = real <= datos_viaje["ventana_entrega"] and precintos_conformes and carga_completa
        # 4. Guardar la entrega y su evidencia antes de cerrar el viaje.
        con.execute(
            """INSERT INTO pod_entrega(id_despacho,fecha_hora_real,receptor_nombre,
            receptor_dni,precintos_conformes,cumplio_otif,archivo_foto_url)
            VALUES(%s,%s,%s,%s,%s,%s,%s)""",
            (id_viaje, real, receptor.strip(), dni, precintos_conformes, otif, foto),
        )
        con.execute(
            """UPDATE despacho SET estado_viaje='Cerrado',odometro_final_km=%s
            WHERE id_despacho=%s""",
            (odometro, id_viaje),
        )
        # 5. Liberar los recursos después de registrar el cierre.
        for tabla, estado in (
            ("tracto", "Disponible"),
            ("semirremolque", "Disponible"),
            ("conductor", "Habilitado"),
        ):
            con.execute(
                f"UPDATE {tabla} SET estado=%s WHERE id_{tabla}=%s",
                (estado, datos_viaje[f"id_{tabla}"]),
            )
    return volver(f"/viajes/{id_viaje}", "Entrega registrada y viaje cerrado con su POD.")
