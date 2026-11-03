"""
Módulo de Conexión a Base de Datos PostgreSQL (Neon) - TRANSPACÍFICO S.A.C.
Permite conectar los modelos de Machine Learning (OE1, OE2, OE3) con la BD en la nube.
"""

from pathlib import Path
import os
import pandas as pd
import psycopg2
from dotenv import load_dotenv

# Cargar variables del archivo .env en esta misma carpeta
CARPETA_ACTUAL = Path(__file__).parent
load_dotenv(CARPETA_ACTUAL / ".env")

DATABASE_URL = os.getenv("DATABASE_URL")


def obtener_conexion():
    """Retorna una conexión activa a la base de datos PostgreSQL en Neon."""
    if not DATABASE_URL:
        raise ValueError(
            "No se encontró la variable DATABASE_URL en el archivo .env. "
            "Verifica que el archivo .env exista en la carpeta del proyecto."
        )
    return psycopg2.connect(DATABASE_URL)


def _consultar_dataframe(consulta):
    """Ejecuta una consulta SQL en Neon y devuelve un DataFrame de Pandas limpio."""
    with obtener_conexion() as conn:
        with conn.cursor() as cur:
            cur.execute(consulta)
            columnas = [col.name for col in cur.description]
            return pd.DataFrame(cur.fetchall(), columns=columnas)


def cargar_datos_oe1():
    """
    OE1: Consulta SQL para obtener los viajes con distancia, peso, velocidad y duración.
    Calcula día y hora directamente desde fecha_hora_salida y lee la velocidad real.
    """
    consulta = """
    SELECT
        d.id_despacho,
        TO_CHAR(
            d.fecha_hora_salida AT TIME ZONE 'UTC',
            'YYYY-MM-DD HH24:MI:SS'
        ) AS fecha_hora_salida,
        s.origen,
        s.destino,
        c.distancia_km::INT AS distancia_km,
        ROUND((p.peso_neto_kg / 1000.0)::numeric, 2)::FLOAT8 AS peso_carga_tn,
        EXTRACT(ISODOW FROM d.fecha_hora_salida AT TIME ZONE 'UTC')::INT AS dia_salida,
        EXTRACT(HOUR FROM d.fecha_hora_salida AT TIME ZONE 'UTC')::INT AS hora_salida,
        d.velocidad_media_estimada_kmh::FLOAT8 AS velocidad_media_estimada_kmh,
        ROUND(
            (EXTRACT(EPOCH FROM (pod.fecha_hora_real - d.fecha_hora_salida)) / 60.0)::numeric,
            2
        )::FLOAT8 AS duracion_viaje_min
    FROM despacho d
    JOIN solicitud_carga s ON d.id_solicitud = s.id_solicitud
    JOIN corredor c ON s.id_corredor = c.id_corredor
    JOIN pesaje_bascula p ON d.id_despacho = p.id_despacho
    JOIN pod_entrega pod ON d.id_despacho = pod.id_despacho
    ORDER BY d.id_despacho;
    """
    return _consultar_dataframe(consulta)


def cargar_datos_oe2():
    """
    OE2: Consulta SQL para obtener las semanas históricas por corredor para entrenamiento.
    Filtra es_historico = TRUE para separarlas de nuevos pronósticos guardados por la web.
    """
    consulta = """
    SELECT
        TO_CHAR(p.semana_inicio, 'YYYY-MM-DD') AS semana_inicio,
        c.nombre AS corredor,
        p.feriados_semana::INT AS feriados_semana,
        p.dias_segunda_quincena::INT AS dias_segunda_quincena,
        p.toneladas_estimadas::FLOAT8 AS toneladas_semana
    FROM pronostico_demanda p
    JOIN corredor c ON p.id_corredor = c.id_corredor
    WHERE p.es_historico = TRUE
    ORDER BY p.id_pronostico;
    """
    return _consultar_dataframe(consulta)


def cargar_datos_oe3():
    """
    OE3: Consulta SQL para obtener las evaluaciones de retorno con carga.
    Usa s.destino como origen_retorno porque el retorno nace del destino del mismo viaje.
    """
    consulta = """
    SELECT
        pr.id_prediccion_retorno,
        d.id_despacho,
        TO_CHAR(
            d.eta_fecha_hora_calculo AT TIME ZONE 'UTC',
            'YYYY-MM-DD HH24:MI:SS'
        ) AS fecha_hora_evaluacion,
        s.destino AS origen_retorno,
        EXTRACT(ISODOW FROM s.ventana_entrega AT TIME ZONE 'UTC')::INT AS dia_entrega_pactada,
        CASE
            WHEN EXTRACT(DAY FROM s.ventana_entrega AT TIME ZONE 'UTC') <= 15 THEN 1
            ELSE 2
        END AS quincena_entrega_pactada,
        d.solicitudes_compatibles::INT AS solicitudes_compatibles,
        d.proporcion_retornos_previos::FLOAT8 AS proporcion_retornos_previos,
        CASE WHEN d.retorno_con_carga THEN 1 ELSE 0 END AS retorno_con_carga
    FROM prediccion_retorno pr
    JOIN despacho d ON pr.id_despacho = d.id_despacho
    JOIN solicitud_carga s ON d.id_solicitud = s.id_solicitud
    ORDER BY pr.id_prediccion_retorno;
    """
    return _consultar_dataframe(consulta)


def probar_conexion():
    """Verifica el estado de la conexión a Neon y cuenta las tablas existentes."""
    print("Conectando a PostgreSQL (Neon)...")
    try:
        with obtener_conexion() as conn:
            with conn.cursor() as cur:
                # 1. Versión de PostgreSQL
                cur.execute("SELECT version();")
                version = cur.fetchone()[0]

                # 2. Conteo de tablas del proyecto
                cur.execute("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    ORDER BY table_name;
                """)
                tablas = [fila[0] for fila in cur.fetchall()]

                print("\n=======================================================")
                print("       ¡CONEXIÓN EXITOSA A NEON POSTGRESQL!")
                print("=======================================================")
                print(f"Versión: {version.split(',')[0]}")
                print(f"Total de tablas en esquema public: {len(tablas)}")
                print("Tablas encontradas:")
                for t in tablas:
                    print(f"  - {t}")
                print("=======================================================")
                print("\nPara usarlo en cualquier modelo.py, solo agregas:")
                print("  from base_datos import cargar_datos_oe1")
                print("  datos = cargar_datos_oe1()")
                print("=======================================================\n")
    except Exception as e:
        print(f"\n[ERROR] No se pudo conectar a Neon: {e}")


if __name__ == "__main__":
    probar_conexion()
