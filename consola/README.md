# Pruebas locales: ventana y consola

Esta carpeta conserva los archivos Python de la versión de Drive, conservando su lógica de
entrenamiento y gráficos. Se ejecutan localmente en tu computadora. El sistema web y Render no los usan.

---

## 1. Guía rápida para la presentación (USB / Otra máquina)

Si llevas el proyecto en un `.zip` dentro de un USB a una máquina del aula o laboratorio:

### Requisitos previos en el USB
1. **Verificar el archivo `.env`:** Asegúrate de que el archivo `consola/.env` esté incluido dentro del `.zip` (en Windows los archivos que inician con punto a veces se ocultan). Sin este archivo, la aplicación no podrá conectarse a Neon.
2. **Conexión a Internet:** Para conectarse a Neon PostgreSQL se requiere acceso a internet (o compartir datos móviles a la PC).

### Pasos de ejecución en Thonny o Terminal

#### Opción A: Desde Thonny (Directo en el shell interactivo)
1. Abre Thonny en la máquina.
2. En la consola inferior interactiva de Thonny (`>>>`), copia y pega esta línea completa para instalar las dependencias directamente (sin importar en qué carpeta estés):
   ```python
   !pip install numpy pandas scikit-learn xgboost prophet matplotlib psycopg2-binary python-dotenv
   ```
3. En Thonny, abre el archivo `interfaz.py` y pulsa el botón verde **Ejecutar** (o la tecla `F5`).

*(Alternativa con archivo de requisitos: en **Herramientas** → **Abrir consola del sistema**, navegar a la carpeta y ejecutar `pip install -r requirements.txt`).*

#### Opción B: Desde PowerShell / CMD
Desde la carpeta `consola/`:
```powershell
pip install -r requirements.txt
python interfaz.py
```
*(Si estás en la raíz del repositorio: `python consola/interfaz.py`).*

---

## 2. Plan de contingencia sin Internet (Uso de Datasets locales)

Si en el aula no hay internet, falla la red de la universidad o bloquean el puerto 5432 de PostgreSQL:

Los tres modelos (`modelo.py`) cuentan con un selector rápido de fuente:
1. Abre los archivos de los modelos en Thonny o un editor de texto:
   - `consola/OE1_Tiempo_Viaje/modelo.py`
   - `consola/OE2_Demanda/modelo.py`
   - `consola/OE3_Carga_Retorno/modelo.py`
2. Cambia la variable en la cabecera (línea 15 o 21):
   ```python
   USAR_SQL = False  # Cambiado a False para usar el CSV auxiliar sin conexión
   ```
3. Guarda el archivo y ejecuta nuevamente `interfaz.py`.
4. La ventana y los modelos entrenarán inmediatamente usando los archivos `dataset.csv` de respaldo incluidos localmente, sin solicitar conexión a Internet ni `.env`.

---

## 3. Uso de la ventana gráfica

1. Elegir la pestaña **OE1**, **OE2** u **OE3**.
2. Pulsar **1. Leer SQL y entrenar**. Lee los registros (o el CSV si `USAR_SQL = False`) y muestra sus métricas 80/20.
3. Revisar las variables del formulario e ingresar una consulta.
4. Pulsar **2. Predecir**. El resultado aparece a la izquierda y el gráfico de la consulta se actualiza en el panel derecho.
5. Recorrer los gráficos con el selector o las flechas del panel.
6. **Ampliar gráfico** abre el gráfico seleccionado en una ventana independiente.
7. **Ver dataset SQL** muestra las filas del dataset en una tabla interactiva.
8. **Detalle de métricas** permite revisar la salida analítica completa del modelo.

---

## 4. Gráficos disponibles

| Objetivo | Gráficos del entrenamiento y prueba | Consulta actual |
|---|---|---|
| **OE1** | Duración del dataset vs. predicha, importancia de variables y dos árboles completos de XGBoost. | Duración y comparación respecto a la ruta con el punto de la consulta. |
| **OE2** | Semanas de prueba observadas vs. predichas para Centro y Norte. | Histórico, pronóstico e intervalo de la semana elegida. |
| **OE3** | Matriz de confusión, árbol completo, curva ROC e importancia de variables. | Probabilidades y camino de la consulta resaltado en el árbol completo. |

---

## 5. Estructura del código

| Archivo o carpeta | Responsabilidad |
|---|---|
| `interfaz.py` | Ventana principal Tkinter y coordinación de eventos. |
| `presentacion/diseno.py` | Maquetación visual: formulario a la izquierda, métricas y gráficos a la derecha. |
| `presentacion/formulario.py` | Variables visibles, ejemplos, unidades y lectura de entradas. |
| `presentacion/entrenamiento.py` | Ejecución de los modelos en segundo plano sin congelar la ventana. |
| `presentacion/predicciones.py` | Preparación de consultas y cálculo de inferencias. |
| `presentacion/visor.py` | Visor paginado integrado para visualización de gráficos. |
| `OE1_Tiempo_Viaje/` | XGBoost: duración del viaje (`modelo.py`, `generar.py`, `dataset.csv`). |
| `OE2_Demanda/` | Prophet: toneladas semanales (`modelo.py`, `generar.py`, `dataset.csv`). |
| `OE3_Carga_Retorno/` | Árbol de decisión: retorno con carga (`modelo.py`, `generar.py`, `dataset.csv`). |
| `base_datos.py` | Conexión y consultas de lectura a PostgreSQL en Neon. |
| `generarSQL.py` | Generador de datos y carga masiva a Neon (vacía y recarga). |
| `requirements.txt` | Lista completa de dependencias de Python para la consola y modelos. |
| `.env.example` | Plantilla de variables de entorno para la cadena de conexión. |

---

## 6. Ejecución individual por consola

Si deseas ejecutar un modelo directamente sin la ventana gráfica:

```powershell
python consola/OE1_Tiempo_Viaje/modelo.py
python consola/OE2_Demanda/modelo.py
python consola/OE3_Carga_Retorno/modelo.py
```

Cada script entrena su modelo, imprime métricas detalladas en la terminal, solicita datos para una predicción y guarda sus gráficos correspondientes.
Para probar únicamente la conexión a la base de datos Neon:
```powershell
python consola/base_datos.py
```
