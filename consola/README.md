# Modelos por consola: SQL y CSV local

Esta carpeta conserva los archivos Python de la versión de Drive, conservando su lógica de
entrenamiento y gráficos. Se ejecutan manualmente en tu computadora. El sistema web y Render no los usan.

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

Los tres `modelo.py` usan **PostgreSQL como fuente principal** (`USAR_SQL = True`).
Las consultas preparan los mismos datasets que el sistema web: viajes cerrados en OE1,
semanas históricas en OE2 y una evaluación por viaje de ida cerrado en OE3.
La consola imprime la fuente, las filas y las columnas antes del entrenamiento.

Si no hay Internet o SQL no está disponible, cambiar únicamente `USAR_SQL = False`
en el modelo que se desea ejecutar. Así se utiliza su `dataset.csv` incluido.
La elección es explícita: una falla de conexión no cambia la fuente automáticamente.
Los CSV son material auxiliar y sus resultados pueden diferir del histórico de SQL.
No hace falta ejecutar los generadores para presentar.

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
