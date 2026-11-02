# TRANSPACÍFICO S.A.C.

Proyecto académico de gestión de flota para los corredores Callao–Huancayo y Callao–Trujillo.

## Contenido

- `consola/OE1_Tiempo_Viaje`: XGBoost para la duración total del viaje.
- `consola/OE2_Demanda`: Prophet para toneladas semanales por corredor.
- `consola/OE3_Carga_Retorno`: árbol de decisión para el retorno con carga.
- `sql/01_base_original.sql`: estructura original de 19 tablas con PostGIS.
- `requirements.txt`: dependencias de los generadores y modelos de consola.

Cada OE conserva su `generar.py`, `modelo.py` y `dataset.csv`. Los datos son simulados. Los modelos mantienen su división 80/20 y guardan sus gráficos PNG en la carpeta correspondiente.

## Ejecutar los modelos de consola

Utilizar Python 3.12. Desde la carpeta del repositorio:

```bash
python -m venv .venv
```

Activar el entorno en Windows:

```powershell
.venv\Scripts\Activate.ps1
```

O en Linux/macOS:

```bash
source .venv/bin/activate
```

Instalar las dependencias y ejecutar un modelo:

```bash
python -m pip install -r requirements.txt
python consola/OE1_Tiempo_Viaje/modelo.py
python consola/OE2_Demanda/modelo.py
python consola/OE3_Carga_Retorno/modelo.py
```

Cada programa muestra sus métricas, solicita los valores de una consulta y muestra la predicción. Los gráficos se guardan como PNG y se muestran al finalizar la consulta.

Los CSV ya están incluidos. Para reproducirlos, ejecutar el `generar.py` del OE correspondiente; no editar sus registros manualmente.

## Integración del sistema

La conexión con PostgreSQL, el backend FastAPI y la interfaz HTML se desarrollarán en este mismo repositorio. Esta primera versión conserva los modelos de consola como punto de partida y respaldo. Todavía no contiene un backend desplegado.

El SQL original declara PostgreSQL 16 y PostGIS. El proyecto inicial de Neon mostró PostgreSQL 18: la versión del entorno debe comprobarse antes de la carga.

Las contraseñas y cadenas de conexión se configuran mediante variables de entorno; no se incorporan al repositorio.
