"""generarSQL.py: Limpia Neon (TRUNCATE), genera los viajes unificados e inserta en SQL."""

import numpy as np
import pandas as pd
from psycopg2.extras import execute_values
from sklearn.tree import DecisionTreeClassifier
from base_datos import obtener_conexion

SEMILLA = 42                                    # -> semilla fija para repetir los sorteos


# =====================================================================
# PASO 2: FUNCIONES PARA GENERAR LOS DATOS UNIFICADOS DESDE CERO
# =====================================================================

def _calcular_duracion_oe1(distancia, velocidades, horas, dia_semana, destino, pesos):
    """Aplica la fórmula paso a paso de OE1 para calcular la duración del viaje en minutos."""
    minutos_base = (distancia / velocidades) * 60                       # -> tiempo base en ruta
    hay_trafico = ((horas >= 6) & (horas <= 9)) | ((horas >= 17) & (horas <= 19))
    demora_trafico = np.where(hay_trafico, 35, 0)                       # -> +35 min en hora punta
    demora_subida = np.where((destino == "Huancayo") & (pesos > 20), 45, 0) # -> +45 min Ticlio
    demora_dia = np.where((dia_semana == 5) | (dia_semana == 6), 20, 0) # -> +20 min vie/sáb
    return (minutos_base + demora_trafico + demora_subida + demora_dia).round(2)


def generar_recorridos_completos(semilla=SEMILLA, cantidad_por_corredor=500):
    """
    Genera 1,000 recorridos completos (ida + evaluación OE3 + regreso del mismo recorrido).
    - Ida: Callao -> Huancayo o Callao -> Trujillo (con carga entre 10 y 29 t).
    - OE3: Evalúa en ese viaje la oportunidad de retorno desde Huancayo/Trujillo hacia Callao.
    - Regreso: Huancayo/Trujillo -> Callao del mismo camión, saliendo después de entregar la ida
      y llevando peso (10-29 t) solo si OE3 determinó retorno_con_carga = 1 (si no, 0 t).
    """
    azar = np.random.default_rng(semilla)
    fecha_ini = pd.Timestamp("2024-01-01")
    cantidad_dias = (pd.Timestamp("2025-12-25") - fecha_ini).days + 1

    corredores = [
        ("Callao", "Huancayo", 395, 25, 55),    # -> corredor Centro (395 km)
        ("Callao", "Trujillo", 575, 45, 78),    # -> corredor Norte (575 km)
    ]

    # --- PARTE A: Generar los 1,000 viajes de IDA desde Callao ---
    grupos_ida = []
    for origen, destino, distancia, vel_min, vel_max in corredores:
        pesos_ida = azar.uniform(10, 29, cantidad_por_corredor).round(2) # -> peso ida (10-29 t)
        vel_ida = azar.uniform(vel_min, vel_max, cantidad_por_corredor).round(2)
        dias_azar = azar.integers(0, cantidad_dias, cantidad_por_corredor)
        horas_ida = azar.integers(5, 21, cantidad_por_corredor)          # -> salida entre 5am y 8pm

        salidas_ida = (
            fecha_ini
            + pd.to_timedelta(dias_azar, unit="D")
            + pd.to_timedelta(horas_ida, unit="h")
        )
        dia_sem_ida = salidas_ida.dayofweek + 1
        dur_ida = _calcular_duracion_oe1(
            distancia, vel_ida, horas_ida, dia_sem_ida, destino, pesos_ida
        )

        grupos_ida.append(pd.DataFrame({
            "fecha_hora_salida": salidas_ida,
            "origen": origen,
            "destino": destino,
            "distancia_km": distancia,
            "vel_min": vel_min,
            "vel_max": vel_max,
            "peso_carga_tn": pesos_ida,
            "dia_salida": dia_sem_ida,
            "hora_salida": horas_ida,
            "velocidad_media_estimada_kmh": vel_ida,
            "duracion_viaje_min": dur_ida,
        }))

    # Ordenar las 1,000 idas cronológicamente
    idas = pd.concat(grupos_ida, ignore_index=True).sort_values("fecha_hora_salida")
    idas = idas.reset_index(drop=True)

    # --- PARTE B: Evaluar OE3 en cada ida y construir su trayecto de REGRESO ---
    cant_total = len(idas)
    solicitudes_azar = azar.integers(0, 6, cant_total)                  # -> ofertas (0 a 5)
    variaciones_azar = azar.integers(-8, 9, cant_total)                 # -> variación diaria
    pesos_retorno_azar = azar.uniform(10, 29, cant_total).round(2)      # -> peso si vuelve cargado
    horas_salida_reg = azar.integers(5, 21, cant_total)                 # -> hora salida del regreso

    historial = {"Huancayo": [], "Trujillo": []}                        # -> cierres previos por sede
    filas_recorrido = []

    for i, ida in idas.iterrows():
        ciudad_prov = str(ida["destino"])                               # -> Huancayo o Trujillo
        dist = int(ida["distancia_km"])
        salida_ida = ida["fecha_hora_salida"]
        llegada_ida = salida_ida + pd.Timedelta(minutes=float(ida["duracion_viaje_min"]))
        plazo_h = 13 if ciudad_prov == "Huancayo" else 14
        ventana_ida = salida_ida + pd.Timedelta(hours=plazo_h)          # -> entrega pactada ida

        # 1) Evaluar OE3 desde Huancayo/Trujillo hacia Callao
        dia_ent = int(ventana_ida.dayofweek) + 1                        # -> día entrega (1-7)
        quincena_ent = 1 if ventana_ida.day <= 15 else 2                # -> quincena (1 o 2)
        sol_comp = int(solicitudes_azar[i])

        finalizados = [res for f_fin, res in historial[ciudad_prov] if f_fin < salida_ida]
        ultimos_10 = finalizados[-10:]
        prop_prev = round(sum(ultimos_10) / len(ultimos_10), 2) if ultimos_10 else 0.50

        pts_sol = sol_comp * 20
        pts_quin = 15 if quincena_ent == 2 else 0
        pts_dia = 15 if dia_ent <= 5 else 0
        pts_ciu = 10 if ciudad_prov == "Trujillo" else 0
        pts_hist = prop_prev * 30
        puntaje = pts_sol + pts_quin + pts_dia + pts_ciu + pts_hist + int(variaciones_azar[i])
        vuelve_cargado = 1 if (sol_comp > 0 and puntaje >= 70) else 0   # -> 1=cargado, 0=vacío

        # 2) Construir el trayecto de REGRESO (Huancayo/Trujillo -> Callao) de este mismo viaje
        # Sale al día siguiente de llegar/entregar en destino, entre las 5 am y 8 pm
        base_dia_reg = max(llegada_ida, ventana_ida).floor("D") + pd.Timedelta(days=1)
        hora_reg = int(horas_salida_reg[i])
        salida_reg = base_dia_reg + pd.Timedelta(hours=hora_reg)        # -> siempre > llegada_ida
        dia_sem_reg = int(salida_reg.dayofweek) + 1

        # El peso del regreso depende directamente de si OE3 consiguió carga o no
        peso_reg = float(pesos_retorno_azar[i]) if vuelve_cargado == 1 else 0.0
        vel_reg = round(float(azar.uniform(ida["vel_min"], ida["vel_max"])), 2)
        dur_reg = float(_calcular_duracion_oe1(
            dist, vel_reg, np.array([hora_reg]), np.array([dia_sem_reg]),
            "Callao", np.array([peso_reg])
        )[0])
        llegada_reg = salida_reg + pd.Timedelta(minutes=dur_reg)
        ventana_reg = salida_reg + pd.Timedelta(hours=plazo_h)

        # El retorno se registra en el historial cuando finaliza el viaje de regreso
        historial[ciudad_prov].append((llegada_reg, vuelve_cargado))

        filas_recorrido.append({
            "num_recorrido": int(i) + 1,
            "ciudad_provincia": ciudad_prov,
            "distancia_km": dist,
            # Datos del tramo de IDA (Callao -> Provincia)
            "salida_ida": salida_ida,
            "llegada_ida": llegada_ida,
            "ventana_ida": ventana_ida,
            "peso_ida": float(ida["peso_carga_tn"]),
            "vel_ida": float(ida["velocidad_media_estimada_kmh"]),
            "dur_ida": float(ida["duracion_viaje_min"]),
            # Datos de evaluación OE3 (Retorno desde Provincia -> Callao)
            "origen_retorno": ciudad_prov,
            "dia_entrega_pactada": dia_ent,
            "quincena_entrega_pactada": quincena_ent,
            "solicitudes_compatibles": sol_comp,
            "proporcion_retornos_previos": prop_prev,
            "retorno_con_carga": vuelve_cargado,
            # Datos del tramo de REGRESO (Provincia -> Callao)
            "salida_reg": salida_reg,
            "llegada_reg": llegada_reg,
            "ventana_reg": ventana_reg,
            "peso_reg": peso_reg,
            "vel_reg": vel_reg,
            "dur_reg": dur_reg,
        })

    return pd.DataFrame(filas_recorrido)


def generar_oe2(semilla=SEMILLA):
    """OE2: Genera 208 filas semanales de demanda en toneladas por corredor."""
    azar = np.random.default_rng(semilla)
    semanas = pd.date_range("2024-01-01", "2025-12-28", freq="7D")     # -> 104 lunes (2 años)
    cant_sem = len(semanas)
    feriados = azar.choice([0, 1, 2], size=cant_sem, p=[0.80, 0.15, 0.05]) # -> feriados por semana

    dias_quincena = np.zeros(cant_sem, dtype=int)
    for d in range(7):
        fecha_dia = semanas + pd.Timedelta(days=d)
        dias_quincena = dias_quincena + np.where(fecha_dia.day >= 16, 1, 0) # -> días en 2da quincena

    grupos = []
    for corredor in ["Centro", "Norte"]:
        viajes_base = 6 if corredor == "Centro" else 7                  # -> base: 6 Centro, 7 Norte
        viajes_totales = viajes_base + dias_quincena - feriados         # -> viajes de la semana
        peso_camion = azar.uniform(20.5, 21.5, cant_sem)                # -> toneladas por viaje
        toneladas_finales = (viajes_totales * peso_camion).round(2)     # -> toneladas totales

        grupos.append(pd.DataFrame({
            "semana_inicio": semanas.strftime("%Y-%m-%d"),
            "corredor": corredor,
            "feriados_semana": feriados,
            "dias_segunda_quincena": dias_quincena,
            "toneladas_semana": toneladas_finales,
        }))

    datos = pd.concat(grupos, ignore_index=True).sort_values(["semana_inicio", "corredor"])
    return datos.reset_index(drop=True)


def calcular_probabilidades_oe3(df_viajes):
    """Entrena el árbol de decisión (80/20) y devuelve la probabilidad de cada retorno."""
    vars_oe3 = [
        "origen_retorno",
        "dia_entrega_pactada",
        "quincena_entrega_pactada",
        "solicitudes_compatibles",
        "proporcion_retornos_previos",
    ]
    X = pd.get_dummies(df_viajes[vars_oe3], columns=["origen_retorno"], dtype=int)
    y = df_viajes["retorno_con_carga"]
    corte = max(1, int(len(df_viajes) * 0.80))
    if y.iloc[:corte].nunique() < 2:
        return [float(y.iloc[0])] * len(df_viajes)
    arbol = DecisionTreeClassifier(max_depth=4, random_state=42)
    arbol.fit(X.iloc[:corte], y.iloc[:corte])
    return arbol.predict_proba(X)[:, 1]


# =====================================================================
# FLUJO PRINCIPAL: 1. TRUNCATE -> 2. GENERAR -> 3. INSERT
# =====================================================================

def principal():
    with obtener_conexion() as conn, conn.cursor() as cur:

        # -----------------------------------------------------------------
        # 1. TRUNCATE: Limpiar tablas de Neon y asegurar columnas de ML
        # -----------------------------------------------------------------
        print("1. Limpiando base de datos en Neon (TRUNCATE)...")
        cur.execute("""
            ALTER TABLE despacho
                DROP COLUMN IF EXISTS origen_retorno,
                ADD COLUMN IF NOT EXISTS velocidad_media_estimada_kmh NUMERIC(5,2),
                ADD COLUMN IF NOT EXISTS solicitudes_compatibles INTEGER,
                ADD COLUMN IF NOT EXISTS proporcion_retornos_previos NUMERIC(4,3);

            ALTER TABLE pronostico_demanda
                ADD COLUMN IF NOT EXISTS feriados_semana INTEGER,
                ADD COLUMN IF NOT EXISTS dias_segunda_quincena INTEGER,
                ADD COLUMN IF NOT EXISTS es_historico BOOLEAN NOT NULL DEFAULT TRUE;

            TRUNCATE TABLE
                prediccion_retorno, pod_entrega, pesaje_bascula,
                despacho, pronostico_demanda, solicitud_carga,
                corredor, cliente, semirremolque, tracto,
                conductor, usuario, rol
            RESTART IDENTITY CASCADE;
        """)

        # -----------------------------------------------------------------
        # 2. GENERAR: Crear los 1,000 recorridos (Ida + OE3 + Regreso) y OE2
        # -----------------------------------------------------------------
        print("2. Generando 1,000 recorridos completos (Ida + OE3 + Regreso) y OE2...")
        df_recorridos = generar_recorridos_completos()
        df_oe2 = generar_oe2()
        probs_oe3 = calcular_probabilidades_oe3(df_recorridos)

        # -----------------------------------------------------------------
        # 3. INSERT: Guardar idas, regresos, evaluaciones OE3 y semanas OE2
        # -----------------------------------------------------------------
        print("3. Insertando las tablas relacionadas en Neon PostgreSQL...")

        # A. Insertar catálogos base (llaves foráneas obligatorias)
        cur.execute("""
            INSERT INTO rol (nombre) VALUES ('Operador');
            INSERT INTO usuario (id_rol, correo, contrasena, sede_operativa, estado)
                VALUES (1, 'operador@transpacifico.pe', 'hash', 'Callao', 'Activo');
            INSERT INTO conductor
                (id_usuario, nombre, brevete, categoria_brevete, fecha_vencimiento, estado)
                VALUES (1, 'Conductor Base', 'Q41526371', 'A-IIIc', '2028-12-31', 'Habilitado');
            INSERT INTO tracto (placa, modelo, estado)
                VALUES ('B7K-912', 'Volvo FH', 'Disponible');
            INSERT INTO semirremolque (placa, capacidad_tn, estado)
                VALUES ('F9T-901', 30.00, 'Disponible');
            INSERT INTO cliente (razon_social, ruc)
                VALUES ('Cliente General S.A.C.', '20512345671');
            INSERT INTO corredor (nombre, distancia_km)
                VALUES ('Centro', 395.00), ('Norte', 575.00);
        """)

        # B. Armar los registros de IDA y REGRESO de cada recorrido
        lista_solicitudes = []
        lista_despachos = []
        lista_pesajes = []
        lista_pods = []
        # Guardaremos (indice_en_lista_despachos, nivel, prob) solo para las IDAS
        info_predicciones_ida = []

        for i, rec in df_recorridos.iterrows():
            num = int(rec["num_recorrido"])
            ciudad_prov = str(rec["ciudad_provincia"])          # -> Huancayo o Trujillo
            distancia = int(rec["distancia_km"])                # -> 395 km o 575 km
            id_corredor = 1 if distancia == 395 else 2          # -> 1=Centro, 2=Norte
            vuelve_cargado = bool(int(rec["retorno_con_carga"]) == 1)
            sol_comp = int(rec["solicitudes_compatibles"])
            prop_prev = float(rec["proporcion_retornos_previos"])

            # Odómetros continuos del mismo recorrido: Callao -> Provincia -> Callao
            odo_callao = 100000 + (num * 2000)                  # -> km al salir de Callao
            odo_provincia = odo_callao + distancia              # -> km al llegar a provincia
            odo_vuelta = odo_provincia + distancia              # -> km al regresar a Callao

            # --- TRAMO 1: IDA (Callao -> Huancayo/Trujillo) ---
            sal_ida = pd.Timestamp(rec["salida_ida"], tz="UTC")
            ing_ida = sal_ida - pd.Timedelta(hours=1)           # -> ingresa a patio 1h antes
            lleg_ida = pd.Timestamp(rec["llegada_ida"], tz="UTC")
            vent_ida = pd.Timestamp(rec["ventana_ida"], tz="UTC")
            peso_ida = float(rec["peso_ida"])
            vel_ida = float(rec["vel_ida"])
            fof_ida = round((peso_ida / 30.0) * 100.0, 2)

            idx_despacho_ida = len(lista_despachos)             # -> posición de esta ida
            lista_solicitudes.append((
                1, id_corredor, f"GR-{num:04d}-IDA", "Callao", ciudad_prov,
                "Carga General", peso_ida, sal_ida.date(), vent_ida, "Aceptada",
            ))
            lista_despachos.append((
                1, 1, 1, "Cerrado", fof_ida, vent_ida, sal_ida,
                ing_ida, sal_ida, f"EG01-{num:04d}-I", "Emitida",
                odo_callao, odo_provincia, odo_vuelta, vuelve_cargado,
                vel_ida, sol_comp, prop_prev,
            ))
            neto_ida_kg = round(peso_ida * 1000.0, 2)
            lista_pesajes.append((
                ing_ida, 15000.0, round(15000.0 + neto_ida_kg, 2), neto_ida_kg, "Conforme",
            ))
            lista_pods.append((
                lleg_ida, "Receptor Provincia", "45678912",
                True, bool(lleg_ida <= vent_ida), "pod_ida.jpg",
            ))

            # OE3 solo evalúa el retorno desde Huancayo/Trujillo hacia Callao (en la ida)
            prob = round(float(probs_oe3[i]), 3)
            nivel = "Alta" if prob >= 0.70 else ("Media" if prob >= 0.40 else "Baja")
            info_predicciones_ida.append((idx_despacho_ida, nivel, prob))

            # --- TRAMO 2: REGRESO DEL MISMO RECORRIDO (Huancayo/Trujillo -> Callao) ---
            sal_reg = pd.Timestamp(rec["salida_reg"], tz="UTC")
            ing_reg = sal_reg - pd.Timedelta(hours=1)           # -> alistamiento 1h antes
            lleg_reg = pd.Timestamp(rec["llegada_reg"], tz="UTC")
            vent_reg = pd.Timestamp(rec["ventana_reg"], tz="UTC")
            peso_reg = float(rec["peso_reg"])                   # -> >0 si cargado, 0 si vacío
            vel_reg = float(rec["vel_reg"])
            fof_reg = round((peso_reg / 30.0) * 100.0, 2)       # -> 0.0% si vuelve vacío
            tipo_reg = "Carga Retorno" if vuelve_cargado else "Retorno Vacío"

            lista_solicitudes.append((
                1, id_corredor, f"GR-{num:04d}-RET", ciudad_prov, "Callao",
                tipo_reg, peso_reg, sal_reg.date(), vent_reg, "Aceptada",
            ))
            lista_despachos.append((
                1, 1, 1, "Cerrado", fof_reg, vent_reg, sal_reg,
                ing_reg, sal_reg, f"EG01-{num:04d}-R", "Emitida",
                odo_provincia, odo_vuelta, odo_vuelta, vuelve_cargado,
                vel_reg, sol_comp, prop_prev,
            ))
            neto_reg_kg = round(peso_reg * 1000.0, 2)
            lista_pesajes.append((
                ing_reg, 15000.0, round(15000.0 + neto_reg_kg, 2), neto_reg_kg, "Conforme",
            ))
            lista_pods.append((
                lleg_reg, "Base Callao", "45678912",
                True, bool(lleg_reg <= vent_reg), "pod_ret.jpg",
            ))

        # C. Un solo INSERT por cada tabla de viajes (enlazando los IDs reales con RETURNING)
        sql_sol = """
            INSERT INTO solicitud_carga
            (id_cliente, id_corredor, nro_guia_remitente, origen, destino,
             tipo_carga, peso_tn, fecha, ventana_entrega, estado)
            VALUES %s RETURNING id_solicitud;
        """
        ids_sol = [r[0] for r in execute_values(cur, sql_sol, lista_solicitudes, fetch=True)]

        filas_despacho = [
            (id_s, *datos_d) for id_s, datos_d in zip(ids_sol, lista_despachos)
        ]
        sql_desp = """
            INSERT INTO despacho
            (id_solicitud, id_tracto, id_semirremolque, id_conductor, estado_viaje,
             fof_porcentaje, eta_estimado, eta_fecha_hora_calculo,
             fecha_hora_ingreso_patio, fecha_hora_salida, nro_gre, estado_gre,
             odometro_inicial_km, odometro_final_km, odometro_retorno_km,
             retorno_con_carga, velocidad_media_estimada_kmh,
             solicitudes_compatibles, proporcion_retornos_previos)
            VALUES %s RETURNING id_despacho;
        """
        ids_desp = [r[0] for r in execute_values(cur, sql_desp, filas_despacho, fetch=True)]

        filas_pesaje = [(id_d, *p) for id_d, p in zip(ids_desp, lista_pesajes)]
        execute_values(
            cur,
            "INSERT INTO pesaje_bascula (id_despacho, fecha_hora, tara_kg, "
            "peso_bruto_kg, peso_neto_kg, resultado) VALUES %s;",
            filas_pesaje,
        )

        filas_pod = [(id_d, *pod) for id_d, pod in zip(ids_desp, lista_pods)]
        execute_values(
            cur,
            "INSERT INTO pod_entrega (id_despacho, fecha_hora_real, receptor_nombre, "
            "receptor_dni, precintos_conformes, cumplio_otif, archivo_foto_url) VALUES %s;",
            filas_pod,
        )

        # Insertar prediccion_retorno únicamente para los 1,000 recorridos desde Provincia
        filas_pred = [
            (ids_desp[idx_ida], nivel, prob)
            for idx_ida, nivel, prob in info_predicciones_ida
        ]
        execute_values(
            cur,
            "INSERT INTO prediccion_retorno (id_despacho, nivel_probabilidad, probabilidad) "
            "VALUES %s;",
            filas_pred,
        )

        # D. Un solo INSERT para pronostico_demanda (las 208 semanas históricas de OE2)
        lista_pronosticos = []
        for _, f2 in df_oe2.iterrows():
            id_corr = 1 if f2["corredor"] == "Centro" else 2
            ton = float(f2["toneladas_semana"])
            ton_min = round(ton * 0.90, 2)                      # -> margen referencial (-10%)
            ton_max = round(ton * 1.10, 2)                      # -> margen referencial (+10%)
            lista_pronosticos.append((
                id_corr, str(f2["semana_inicio"]), ton, ton_min, ton_max,
                int(f2["feriados_semana"]), int(f2["dias_segunda_quincena"]), True,
            ))

        execute_values(
            cur,
            "INSERT INTO pronostico_demanda (id_corredor, semana_inicio, toneladas_estimadas, "
            "toneladas_min, toneladas_max, feriados_semana, dias_segunda_quincena, "
            "es_historico) VALUES %s;",
            lista_pronosticos,
        )
        conn.commit()

    print("-> Listo: TRUNCATE -> GENERAR -> INSERT completado (0 NULLs y viajes 100% coherentes).")


if __name__ == "__main__":
    principal()
