"""Registro, consulta y evaluación de las solicitudes de transporte."""

from fastapi import APIRouter, Depends, Form, Request

from ..db import conexion, consultar
from .formularios import exigir, fecha_local, mostrar, volver
from ..seguridad import autorizado, permiso

router = APIRouter(dependencies=[Depends(autorizado)])


@router.get("/solicitudes")
def listar(request: Request, estado: str = "", pagina: int = 1):
    # Consultar una página de resultados, aplicando el filtro de estado.
    pagina = max(1, pagina)
    filas = consultar(
        """SELECT s.*, c.razon_social, r.nombre AS corredor,
        EXISTS(SELECT 1 FROM despacho d WHERE d.id_solicitud=s.id_solicitud) AS asignada
        FROM solicitud_carga s JOIN cliente c USING(id_cliente)
        JOIN corredor r USING(id_corredor) WHERE (%s='' OR s.estado=%s)
        ORDER BY s.id_solicitud DESC LIMIT 25 OFFSET %s""",
        (estado, estado, (pagina - 1) * 25),
    )
    return mostrar(
        request,
        "solicitudes.html",
        filas=filas,
        estado=estado,
        pagina=pagina,
        clientes=consultar("SELECT * FROM cliente ORDER BY razon_social"),
        corredores=consultar("SELECT * FROM corredor ORDER BY nombre"),
    )


@router.post("/solicitudes")
def registrar(
    request: Request,
    id_cliente: int = Form(gt=0),
    id_corredor: int = Form(gt=0),
    origen: str = Form(),
    destino: str = Form(),
    guia: str = Form(min_length=1, max_length=30),
    tipo_carga: str = Form(min_length=1, max_length=50),
    peso_tn: float = Form(ge=0, le=30),
    ventana: str = Form(),
):
    # 1. Revisar permisos y datos obligatorios antes de guardar.
    permiso(request, "solicitudes")
    exigir(
        guia.strip() and tipo_carga.strip(), "La guía y el tipo de carga no pueden estar vacíos."
    )
    fecha = fecha_local(ventana)
    with conexion() as con:
        corredor = con.execute(
            "SELECT nombre FROM corredor WHERE id_corredor=%s", (id_corredor,)
        ).fetchone()
        exigir(corredor is not None, "Selecciona un corredor existente.")
        # 2. Verificar que origen y destino correspondan al corredor.
        provincia = {"Centro": "Huancayo", "Norte": "Trujillo"}.get(corredor["nombre"])
        exigir(
            (origen, destino) in (("Callao", provincia), (provincia, "Callao")),
            "La ruta debe corresponder al corredor seleccionado.",
        )
        exigir(
            not con.execute(
                "SELECT 1 FROM solicitud_carga WHERE nro_guia_remitente=%s", (guia.strip(),)
            ).fetchone(),
            "La guía ya está registrada.",
        )
        # 3. Guardar la solicitud pendiente de evaluación.
        con.execute(
            """INSERT INTO solicitud_carga(id_cliente,id_corredor,nro_guia_remitente,
            origen,destino,tipo_carga,peso_tn,fecha,ventana_entrega)
            VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (
                id_cliente,
                id_corredor,
                guia.strip(),
                origen,
                destino,
                tipo_carga.strip(),
                peso_tn,
                fecha.date(),
                fecha,
            ),
        )
    return volver("/solicitudes", "Solicitud registrada. Está pendiente de evaluación.")


@router.post("/solicitudes/{id_solicitud}/evaluar")
def evaluar(
    request: Request,
    id_solicitud: int,
    decision: str = Form(),
    motivo: str = Form(default="", max_length=200),
):
    # 1. Validar la decisión; rechazar exige un motivo.
    permiso(request, "solicitudes")
    exigir(decision in ("Aceptada", "Rechazada"), "Selecciona una decisión válida.")
    exigir(decision != "Rechazada" or motivo.strip(), "Indica el motivo del rechazo.")
    # 2. Comprobar el estado actual y guardar la evaluación en una transacción.
    with conexion() as con:
        s = con.execute(
            "SELECT estado FROM solicitud_carga WHERE id_solicitud=%s FOR UPDATE", (id_solicitud,)
        ).fetchone()
        exigir(s and s["estado"] == "Registrada", "La solicitud ya fue evaluada o no existe.")
        con.execute(
            """UPDATE solicitud_carga SET estado=%s,motivo_rechazo=%s,
            fecha_hora_decision=CURRENT_TIMESTAMP WHERE id_solicitud=%s""",
            (decision, motivo.strip() if decision == "Rechazada" else None, id_solicitud),
        )
    return volver("/solicitudes", "Evaluación guardada.")
