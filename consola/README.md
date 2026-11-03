# Modelos por consola: SQL y CSV local

Esta carpeta conserva los archivos Python de la versión de Drive, sin modificar su
lógica. Se ejecutan manualmente en tu computadora. El sistema web y Render no los usan.

| Archivo o carpeta | Para qué sirve |
|---|---|
| `OE1_Tiempo_Viaje/` | XGBoost: duración del viaje. Incluye modelo, generador y CSV. |
| `OE2_Demanda/` | Prophet: toneladas semanales. Incluye modelo, generador y CSV. |
| `OE3_Carga_Retorno/` | Árbol de decisión: retorno con carga. Incluye modelo, generador y CSV. |
| `base_datos.py` | Conexión y consultas de lectura a PostgreSQL en Neon. |
| `generarSQL.py` | Genera datos simulados y los inserta en PostgreSQL. Vacía las tablas antes de cargarlas. |
| `.env.example` | Ejemplo sin credenciales para preparar tu archivo `.env` privado. |
| `requirements.txt` | Dependencias para consola, gráficos y conexión a SQL. |

## Preparar la computadora

Descargar el repositorio completo y usar Python 3.12. Desde la raíz del repositorio:

```sh
python -m venv .venv
```

Activar el entorno con `.venv\Scripts\Activate.ps1` en PowerShell, o con
`source .venv/bin/activate` en Linux/macOS. Instalar después:

```sh
python -m pip install -r consola/requirements.txt
```

Para SQL, copiar tu `.env` privado desde el USB a `consola/.env`, junto a `base_datos.py`.
También puedes copiar `.env.example` como `.env` y completar `DATABASE_URL` con la URL
completa de Neon, conservando `sslmode=require` y los demás parámetros de conexión.
El archivo debe llamarse `.env`, no `.env.txt`. El `.gitignore` de la raíz lo excluye de Git.
Para trabajar con CSV no se necesita `.env` ni conexión a Internet una vez instaladas las
dependencias. Para consultar Neon sí se necesita Internet.

## Elegir la fuente de datos

La copia de Drive viene configurada para **CSV local**. En cada `modelo.py`, el paso
`1. CARGAR EL DATASET` contiene también las dos líneas para leer SQL, comentadas.
No hay selección automática ni cambio automático a CSV si SQL falla.

Para presentar OE1 con SQL, dejar ese paso así:

```python
from base_datos import cargar_datos_oe1
datos = cargar_datos_oe1()
# datos = pd.read_csv(ARCHIVO, encoding="utf-8-sig")
```

Para OE2 y OE3, hacer el mismo cambio usando `cargar_datos_oe2` y `cargar_datos_oe3`.
Es importante comentar la lectura del CSV: si se deja activa, reemplaza los datos de SQL.
El entrenamiento, las métricas, los gráficos y las consultas manuales permanecen iguales.

Si SQL no está disponible, volver a comentar las dos líneas de SQL y activar únicamente:

```python
datos = pd.read_csv(ARCHIVO, encoding="utf-8-sig")
```

Los CSV ya están incluidos. No hace falta ejecutar los generadores para presentar.
Los resultados de SQL pueden diferir de los CSV porque la base contiene datos distintos.

## Ejecutar los modelos

Desde la raíz del repositorio, ejecutar uno de estos comandos:

```sh
python consola/OE1_Tiempo_Viaje/modelo.py
python consola/OE2_Demanda/modelo.py
python consola/OE3_Carga_Retorno/modelo.py
```

Ejecutar un modelo cada vez. Imprime métricas, pide los datos de una consulta, muestra la
predicción y abre sus gráficos al terminar. Los PNG se guardan dentro de la carpeta del OE.
Para comprobar solo la conexión SQL: `python consola/base_datos.py`.

## Sobre generarSQL.py

Se incluye como respaldo del trabajo de generación. No se ejecuta al descargar el
repositorio, al abrir la web, al entrenar los modelos ni al desplegar en Render.
**No hace falta ejecutarlo para la presentación: Neon ya contiene los datos.**
Si se ejecuta manualmente, realiza `TRUNCATE` y reemplaza los registros por nuevos datos
simulados; también contiene instrucciones de preparación del esquema. Para esta copia en
GitHub solo se revisó el código: no se ejecutó ni se modificó la base de datos.
