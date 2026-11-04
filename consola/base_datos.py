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
    """Lee viajes cerrados y usa solo el último pesaje conforme de cada viaje."""
    consulta = """
    SELECT d.id_despacho, s.origen, s.destino, c.distancia_km::float8,
           round(p.peso_neto_kg/1000,2)::float8 AS peso_carga_tn,
           extract(isodow FROM d.fecha_hora_salida AT TIME ZONE 'UTC')::int AS dia_salida,
           extract(hour FROM d.fecha_hora_salida AT TIME ZONE 'UTC')::int AS hora_salida,
           d.velocidad_media_estimada_kmh::float8,
           round((extract(epoch FROM (pod.fecha_hora_real-d.fecha_hora_salida))/60)::numeric,2)
           ::float8 AS duracion_viaje_min
    FROM despacho d JOIN solicitud_carga s USING(id_solicitud)
    JOIN corredor c USING(id_corredor)
    JOIN LATERAL (
        SELECT peso_neto_kg FROM pesaje_bascula
        WHERE id_despacho=d.id_despacho AND resultado='Conforme'
        ORDER BY fecha_hora DESC,id_pesaje DESC LIMIT 1
    ) p ON TRUE
    JOIN pod_entrega pod USING(id_despacho)
    WHERE d.estado_viaje='Cerrado' AND d.fecha_hora_salida IS NOT NULL
    AND d.velocidad_media_estimada_kmh>0 AND pod.fecha_hora_real>d.fecha_hora_salida
    ORDER BY d.id_despacho;
    """
    return _consultar_dataframe(consulta)


def cargar_datos_oe2():
    """Lee semanas históricas ordenadas; excluye los nuevos pronósticos de la web."""
    consulta = """
    SELECT semana_inicio::text, c.nombre AS corredor,
           feriados_semana, dias_segunda_quincena,
           toneladas_estimadas::float8 AS toneladas_semana
    FROM pronostico_demanda p JOIN corredor c USING(id_corredor)
    WHERE p.es_historico=TRUE AND p.feriados_semana IS NOT NULL
    AND p.dias_segunda_quincena IS NOT NULL
    ORDER BY p.semana_inicio,c.nombre;
    """
    return _consultar_dataframe(consulta)


def cargar_datos_oe3():
    """Lee una fila por ida cerrada; no une predicciones que puedan repetir el viaje."""
    consulta = """
    SELECT d.id_despacho,
           to_char(d.fecha_hora_salida AT TIME ZONE 'UTC','YYYY-MM-DD HH24:MI:SS')
           AS fecha_hora_evaluacion,
           s.destino AS origen_retorno,
           extract(isodow FROM s.ventana_entrega AT TIME ZONE 'UTC')::int AS dia_entrega_pactada,
           CASE WHEN extract(day FROM s.ventana_entrega AT TIME ZONE 'UTC')<=15
                THEN 1 ELSE 2 END AS quincena_entrega_pactada,
           d.solicitudes_compatibles, d.proporcion_retornos_previos::float8,
           d.retorno_con_carga::int
    FROM despacho d JOIN solicitud_carga s USING(id_solicitud)
    WHERE d.estado_viaje='Cerrado' AND s.origen='Callao'
    AND s.destino IN ('Huancayo','Trujillo')
    AND d.fecha_hora_salida IS NOT NULL AND d.retorno_con_carga IS NOT NULL
    AND d.solicitudes_compatibles IS NOT NULL AND d.proporcion_retornos_previos IS NOT NULL
    ORDER BY d.fecha_hora_salida,d.id_despacho;
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
