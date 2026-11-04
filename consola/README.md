# Pruebas locales: ventana y consola

Esta carpeta conserva los archivos Python de la versión de Drive, conservando su lógica de
entrenamiento y gráficos. Se ejecutan manualmente en tu computadora. El sistema web y Render no los usan.

## Ventana para la presentación

Desde la raíz del repositorio, abrir con:

```powershell
py consola/interfaz.py
```

Si ya estás dentro de `consola`, ejecutar `py interfaz.py`. Primero instalar las dependencias
y preparar `consola/.env`, como se explica abajo. La ventana usa **PostgreSQL** y necesita
Internet para leer Neon. No ejecuta el generador ni cambia registros de la base de datos.
Tkinter viene con la instalación habitual de Python para Windows; no se instala con pip.

1. Elegir la pestaña **OE1**, **OE2** u **OE3**.
2. Pulsar **Leer SQL y entrenar**. Lee el histórico actual y muestra sus métricas 80/20.
3. Revisar las variables del formulario e ingresar una consulta.
4. Pulsar **Predecir**. Muestra el resultado y abre el gráfico de esa consulta.
5. Usar **Ver gráficos** para cambiar de imagen con la lista o las flechas. La barra
   inferior permite ampliar con la lupa, volver a la vista inicial y guardar una imagen.
6. **Ver dataset SQL** muestra las filas leídas, sus columnas, nulos y duplicados.

Los ejemplos iniciales del formulario son editables; no son respuestas guardadas.
Una predicción nueva no tiene todavía un resultado observado: su gráfico se muestra por
separado y no modifica la matriz de confusión, el conjunto de prueba ni las métricas.
Al volver a entrenar se descarta la consulta anterior. Si SQL falla, se muestra el error;
no se cambia a CSV ni se presenta el modelo anterior como recién entrenado.

### Gráficos disponibles

| Objetivo | Gráficos del entrenamiento y prueba | Consulta actual |
|---|---|---|
| OE1 | Duración del dataset vs. predicha, importancia de variables y dos árboles completos de XGBoost. | Duración predicha en minutos. |
| OE2 | Semanas de prueba observadas vs. predichas para Centro y Norte. | Histórico, pronóstico e intervalo de la semana elegida. |
| OE3 | Matriz de confusión, árbol completo y curva ROC. | Probabilidades de regresar vacío o con carga. |

Los dos árboles de XGBoost se dibujan con los nodos exportados por `get_dump`, sin omitir
ramas ni hojas. No requieren instalar Graphviz. Cada hoja aporta al conjunto de árboles;
su valor por sí solo no representa la duración total. OE3 utiliza `plot_tree` de Scikit-learn.

### Cómo está ordenado el código de la ventana

| Archivo | Responsabilidad |
|---|---|
| `interfaz.py` | Abrir la ventana y coordinar los cuatro botones. |
| `presentacion/diseno.py` | Distribución visual de pestañas, formularios y resultados. |
| `presentacion/formulario.py` | Variables visibles, ejemplos, unidades y lectura de entradas. |
| `presentacion/entrenamiento.py` | Llamar a los mismos `modelo.py` sin bloquear la ventana. |
| `presentacion/predicciones.py` | Preparar una consulta y llamar al modelo ya entrenado. |
| `presentacion/grafico_consulta.py` | Dibujar el resultado de la consulta actual. |
| `presentacion/arboles.py` | Mostrar completos los árboles reales de XGBoost. |
| `presentacion/visor.py` | Navegar por los gráficos y revisar la tabla del dataset. |

Los `modelo.py` conservan su ejecución por consola. El parámetro opcional `interfaz=True`
permite que la ventana reciba su modelo, datos y resultados antes de los `input()`. No se
duplican el entrenamiento, los algoritmos ni la división 80/20 en otra implementación.

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
