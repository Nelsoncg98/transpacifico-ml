"""Pruebas funcionales: solo contra una base LOCAL indicada en TEST_DATABASE_URL."""

import os
import re
from datetime import datetime, timedelta
from urllib.parse import urlparse
from uuid import uuid4


def principal():
    url = os.getenv("TEST_DATABASE_URL", "")
    if urlparse(url).hostname not in ("localhost", "127.0.0.1", "::1"):
        raise SystemExit("Indica TEST_DATABASE_URL de una base local de pruebas; nunca Neon.")
    os.environ["DATABASE_URL"] = url
    os.environ["APP_PASSWORD"] = "clave-solo-para-pruebas"
    os.environ["APP_USER"] = "operador@transpacifico.pe"
    from fastapi.testclient import TestClient
    from ..app import app
    from ..config import ZONA
    from ..db import obtener
    from ..ml.datos import cargar

    cliente = TestClient(app)
    casos = []

    def comprobar(nombre, condicion):
        casos.append((nombre, bool(condicion)))
        if not condicion:
            raise AssertionError(nombre)

    def enviar(ruta, **datos):
        return cliente.post(ruta, data={"csrf": token, **datos}, follow_redirects=False)

    r = cliente.get("/", follow_redirects=False)
    comprobar("Acceso privado sin sesión", r.status_code == 303)
    r = cliente.get("/ingresar")
    token = re.search(r'name="csrf" value="([^"]+)"', r.text)[1]
    r = enviar("/ingresar", correo=os.environ["APP_USER"], clave="incorrecta", sede="Callao")
    comprobar("Contraseña incorrecta rechazada", "Revisa las credenciales" in r.text)
    r = enviar(
        "/ingresar", correo=os.environ["APP_USER"], clave="contraseña-incorrecta", sede="Callao"
    )
    comprobar("Contraseña con caracteres españoles no causa error", r.status_code == 200)
    r = enviar(
        "/ingresar", correo=os.environ["APP_USER"], clave=os.environ["APP_PASSWORD"], sede="Callao"
    )
    comprobar("Ingreso válido", r.status_code == 303)
    r = cliente.get("/")
    token = re.search(r'name="csrf" value="([^"]+)"', r.text)[1]
    pestaña_a = cliente.get("/solicitudes").text
    pestaña_b = cliente.get("/viajes").text
    token_a = re.search(r'name="csrf" value="([^"]+)"', pestaña_a)[1]
    token_b = re.search(r'name="csrf" value="([^"]+)"', pestaña_b)[1]
    comprobar("Dos pantallas de la misma sesión conservan CSRF", token_a == token_b == token)
    for ruta in ("/", "/solicitudes", "/viajes", "/demanda", "/retornos", "/modelos"):
        respuesta = cliente.get(ruta)
        if respuesta.status_code != 200:
            print("Pantalla con error:", ruta, respuesta.status_code, respuesta.text[-1300:])
        comprobar("Pantalla " + ruta, respuesta.status_code == 200)
    r = cliente.post("/solicitudes", data={}, follow_redirects=False)
    comprobar("Formulario sin token bloqueado", r.status_code == 403)

    # Cada ejecución crea una solicitud nueva en la base LOCAL de pruebas.
    codigo = uuid4().hex[:12]
    base = datetime.now(ZONA).replace(second=0, microsecond=0)
    texto = lambda fecha: fecha.isoformat(timespec="minutes")
    cliente_id = obtener("SELECT id_cliente FROM cliente ORDER BY 1 LIMIT 1")["id_cliente"]
    corredor = obtener("SELECT id_corredor FROM corredor WHERE nombre='Centro'")["id_corredor"]
    datos = dict(
        id_cliente=cliente_id,
        id_corredor=corredor,
        origen="Callao",
        destino="Trujillo",
        guia=codigo,
        tipo_carga="Carga de prueba",
        peso_tn=20,
        ventana=texto(base + timedelta(hours=14)),
    )
    comprobar("Ruta incompatible rechazada", enviar("/solicitudes", **datos).status_code == 400)
    datos["destino"] = "Huancayo"
    comprobar("Registro de solicitud", enviar("/solicitudes", **datos).status_code == 303)
    sid = obtener(
        "SELECT id_solicitud FROM solicitud_carga WHERE nro_guia_remitente=%s", (codigo,)
    )["id_solicitud"]
    comprobar("Guía duplicada rechazada", enviar("/solicitudes", **datos).status_code == 400)
    comprobar(
        "Rechazo exige motivo",
        enviar(f"/solicitudes/{sid}/evaluar", decision="Rechazada", motivo="").status_code == 400,
    )
    comprobar(
        "Aceptación de solicitud",
        enviar(f"/solicitudes/{sid}/evaluar", decision="Aceptada").status_code == 303,
    )
    recursos = {}
    for tabla in ("tracto", "semirremolque", "conductor"):
        fila = obtener(f"SELECT * FROM {tabla} WHERE estado IN ('Disponible','Habilitado') LIMIT 1")
        recursos[f"id_{tabla}"] = fila[f"id_{tabla}"]
    r = enviar("/viajes", id_solicitud=sid, odometro=100000, **recursos)
    comprobar("Asignación de recursos", r.status_code == 303)
    r = enviar("/viajes", id_solicitud=sid, odometro=100000, **recursos)
    comprobar("Recurso ya asignado bloqueado", r.status_code == 400)
    did = obtener("SELECT id_despacho FROM despacho WHERE id_solicitud=%s", (sid,))["id_despacho"]
    ruta = f"/viajes/{did}"
    comprobar("Detalle de viaje", cliente.get(ruta).status_code == 200)
    comprobar(
        "Salida sin controles bloqueada",
        enviar(ruta + "/salir", salida=texto(base), velocidad=40).status_code == 400,
    )
    comprobar(
        "Pesaje con exceso registrado",
        enviar(ruta + "/pesar", tara=15000, bruto=50000, ingreso=texto(base)).status_code == 303,
    )
    ultimo = obtener(
        "SELECT resultado FROM pesaje_bascula WHERE id_despacho=%s ORDER BY id_pesaje DESC LIMIT 1",
        (did,),
    )
    comprobar("Exceso exige reestiba", ultimo["resultado"] == "Reestiba")
    comprobar(
        "Nuevo pesaje conforme",
        enviar(ruta + "/pesar", tara=15000, bruto=35000, ingreso=texto(base)).status_code == 303,
    )
    comprobar(
        "Registro de GRE y precintos",
        enviar(
            ruta + "/documentar", numero_gre="GRE-" + codigo, precintos="P-" + codigo
        ).status_code
        == 303,
    )
    comprobar(
        "Salida autorizada",
        enviar(ruta + "/salir", salida=texto(base + timedelta(hours=1)), velocidad=40).status_code
        == 303,
    )
    comprobar(
        "Incidencia registrada",
        enviar(
            ruta + "/incidencia",
            tipo="Tráfico",
            descripcion="Incidencia de prueba",
            accion="Aviso al operador",
        ).status_code
        == 303,
    )
    antes = len(cargar("oe3"))
    comprobar(
        "Predicción OE3",
        enviar("/retornos", id_viaje=did, solicitudes=4, proporcion=0.7).status_code == 200,
    )
    comprobar("Predicción no se vuelve respuesta histórica", len(cargar("oe3")) == antes)
    comprobar(
        "Predicción ETA",
        enviar(ruta + "/eta", salida=texto(base + timedelta(hours=1)), velocidad=40).status_code
        == 200,
    )
    comprobar("Llegada a destino", enviar(ruta + "/llegar").status_code == 303)
    comprobar(
        "Entrega anterior a salida rechazada",
        enviar(
            ruta + "/entregar",
            fecha=texto(base - timedelta(hours=1)),
            receptor="Receptor de prueba",
            dni="12345678",
            foto="https://example.com/pod.jpg",
            odometro=100395,
        ).status_code
        == 400,
    )
    comprobar(
        "Entrega y cierre con POD",
        enviar(
            ruta + "/entregar",
            fecha=texto(base + timedelta(hours=13)),
            receptor="Receptor de prueba",
            dni="12345678",
            foto="https://example.com/pod.jpg",
            odometro=100395,
            carga_completa="true",
            precintos_conformes="true",
        ).status_code
        == 303,
    )
    comprobar(
        "Viaje quedó cerrado",
        obtener("SELECT estado_viaje FROM despacho WHERE id_despacho=%s", (did,))["estado_viaje"]
        == "Cerrado",
    )
    recurso = obtener("SELECT estado FROM tracto WHERE id_tracto=%s", (recursos["id_tracto"],))
    comprobar("Unidad vuelve a estar disponible", recurso["estado"] == "Disponible")
    antes = len(cargar("oe2"))
    comprobar(
        "Pronóstico semanal",
        enviar("/demanda", corredor="Centro", semana="2026-01-05", feriados=0).status_code == 200,
    )
    comprobar("Pronóstico no entra al histórico", len(cargar("oe2")) == antes)
    comprobar(
        "Fecha semanal inválida rechazada",
        enviar("/demanda", corredor="Centro", semana="2026-01-06", feriados=0).status_code == 400,
    )
    comprobar("Exportación CSV", cliente.get("/reportes.csv").status_code == 200)
    comprobar("Cerrar sesión", enviar("/salir").status_code == 303)
    comprobar(
        "Sesión cerrada no conserva acceso",
        cliente.get("/", follow_redirects=False).status_code == 303,
    )
    for nombre, correcto in casos:
        print(("OK " if correcto else "ERROR ") + nombre)
    print(f"{len(casos)} comprobaciones aprobadas. Solo se usó la base local de pruebas.")
    return casos


if __name__ == "__main__":
    principal()
