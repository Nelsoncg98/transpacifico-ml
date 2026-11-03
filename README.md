# Transpacífico · Sistema web del avance 3

Prototipo con HTML, Python/FastAPI, PostgreSQL y los tres modelos de ML.
Está desplegado en Render y conectado a la base existente de Neon.

**Abrir el sistema:** https://transpacifico.onrender.com

Usuario de demostración: `operador@transpacifico.pe`. La contraseña está en la variable
privada `APP_PASSWORD` del servicio en Render. Las credenciales no se publican en este archivo.

## Dos partes del proyecto

| Parte | Carpeta | Funcionamiento |
|---|---|---|
| Sistema web | `sistema/` | HTML y Python/FastAPI conectados a PostgreSQL en Neon. Integra la operación de transporte y los tres modelos ML. Es la aplicación preparada para Render. |
| Pruebas de los modelos por consola | `consola/` | Copia de los Python de Drive, con sus comentarios originales. Incluye los tres OE, CSV de respaldo, `base_datos.py` y `generarSQL.py`. Se ejecuta manualmente en la computadora. |

El sistema web entrena con los datos de PostgreSQL. La consola viene configurada para CSV;
para leer SQL se activan las líneas comentadas del paso 1 de cada `modelo.py`, como explica
[la guía de consola](consola/README.md). El sistema web no importa esos scripts ni lee sus CSV.
Los códigos de consola conservan el contenido de Drive sin modificar sus algoritmos.
`generarSQL.py` se incluye como respaldo y no se ejecuta automáticamente.

| Archivo de apoyo | Función |
|---|---|
| `render.yaml` | Configuración de construcción y arranque del sistema web en Render. |
| `sistema/requirements.txt` | Dependencias del sistema web; es el archivo usado por Render. |
| `requirements.txt` de la raíz | Dependencias originales de los modelos y gráficos de consola. |
| `consola/requirements.txt` | Incluye las dependencias originales y añade la conexión a SQL. |
| `consola/.env.example` | Plantilla sin credenciales; el `.env` real se coloca aparte en `consola/`. |
| `sql/` | Script original conservado. La aplicación no lo ejecuta. |

La raíz de `sistema/` tiene solo cinco archivos Python: `__init__.py`, `app.py`,
`config.py`, `db.py` y `seguridad.py`. El resto está organizado por su responsabilidad:

| Carpeta / archivo | Qué contiene |
|---|---|
| `operacion/solicitudes.py` | Registro y evaluación de solicitudes. |
| `operacion/despachos.py` | Asignación de recursos y detalle del viaje. |
| `operacion/pesaje_salida.py` | Pesaje, precintos, GRE y autorización de salida. |
| `operacion/entregas.py` | Incidencias, llegada, entrega y cierre. |
| `operacion/reportes.py` | Indicadores, exportación y evidencias de los modelos. |
| `operacion/formularios.py` | Ayudas compartidas para mostrar HTML y leer formularios. |
| `ml/oe1.py`, `oe2.py`, `oe3.py` | Entrenamiento y predicción de cada objetivo. |
| `ml/predicciones.py` | Conecta los formularios con los tres modelos. |
| `ml/entrenar.py` | Ejecuta el entrenamiento antes de arrancar el servidor. |
| `pruebas/verificar.py` | Pruebas funcionales contra una base local aislada. |

La búsqueda de un viaje está en `db.py`. Las conversiones de duración a hora de llegada
están junto a OE1; el gráfico de demanda, junto a OE2. No hay un archivo `calculos.py`
que mezcle esas tareas. Los pasos de acceso, asignación, pesaje y entrega están comentados.

## Flujo implementado

1. Ingresar con el operador de demostración y seleccionar una sede.
2. Registrar una solicitud y aceptarla o rechazarla con un motivo.
3. Programar el viaje con tractocamión, semirremolque y conductor disponibles.
4. Registrar el pesaje. Se calcula el neto y se comprueba la capacidad y el PBV de 48 t.
5. Registrar los precintos y el número de una GRE ya emitida; autorizar la salida.
6. Consultar ETA, registrar incidencias, llegada y entrega con enlace a su POD.
7. Cerrar el viaje, liberar sus recursos y consultar indicadores o exportarlos a CSV.
8. Pronosticar una semana por corredor y evaluar una oportunidad de retorno hacia Callao.

Las operaciones usan las tablas y columnas ya existentes. El arranque y el entrenamiento
no crean tablas, no generan datos de prueba y no ejecutan borrados ni migraciones.
Los formularios guardan únicamente los registros y cambios solicitados por el usuario.
El HTML controla los formatos y límites de entrada, incluido el DNI de ocho dígitos.
Python convierte los tipos de datos y comprueba las reglas de operación, como disponibilidad,
peso permitido y orden de fechas, sin repetir las restricciones de formato del HTML.

## Modelos

| Objetivo | Algoritmo | División de datos |
|---|---|---|
| OE1: duración del viaje | XGBoost: 100 árboles, profundidad 3, tasa 0,1 | 80/20 aleatorio, semilla 42. |
| OE2: toneladas semanales | Prophet por corredor, feriados y días de segunda quincena | Primeras 80 % de semanas / últimas 20 %. |
| OE3: retorno con carga | Árbol de decisión: profundidad 4, semilla 42 | Primeros 80 % de casos / últimos 20 %. |

El entrenamiento lee SQL mediante `sistema/ml/sql/`. Usa el último pesaje conforme de cada
viaje y filtra los históricos de demanda. OE3 toma una observación por despacho de ida,
por lo que guardar varias predicciones no duplica sus respuestas de entrenamiento.
Las predicciones nunca reemplazan `retorno_con_carga`, que representa un resultado observado.

Los modelos, las métricas y siete gráficos se crean en `sistema/modelos/`, excluida de Git.
El modelo de Prophet se conserva con su serialización JSON. Los modelos se cargan una vez
y se reutilizan; una consulta web no vuelve a entrenarlos.
Si falta histórico suficiente, la pantalla informa que el modelo está pendiente.

La ETA inicial suma la duración predicha a la salida indicada. En ruta se aplica la
aproximación acordada: duración predicha × kilómetros restantes / distancia total.
Los kilómetros restantes se ingresan; no se presentan como datos de un GPS automático.

Las fechas de la interfaz están en hora de Perú. Para mantener la lógica del SQL revisado,
las variables de calendario de los modelos se extraen en UTC, como en el generador actual.
Los históricos actuales son simulados; las métricas de prueba describen esos datos.

## Preparar Render

1. En Render, crear un **Blueprint** y seleccionar este repositorio privado.
   El directorio raíz (Root Directory) debe quedar vacío: los comandos parten de la raíz
   del repositorio.
2. Render leerá `render.yaml`. Introducir `DATABASE_URL` con la URL completa de Neon,
   conservando sus parámetros de conexión, incluido `sslmode=require`. Guardarla únicamente
   como variable de entorno privada.
3. Se generan `SESSION_SECRET` y `APP_PASSWORD`. Consultar esta última en Environment
   para ingresar. El correo configurado es `operador@transpacifico.pe` y debe existir
   como usuario activo en PostgreSQL, con su rol `Operador`.

El acceso de este avance usa la contraseña del entorno porque los usuarios de prueba
del generador tienen contraseñas de relleno (`hash`). No se interpreta ese texto como
una contraseña válida. La aplicación consulta el usuario y su rol en SQL, registra
el inicio de sesión y limita las acciones por módulo. La sesión vence tras 30 minutos
sin actividad.

Comando de construcción:

```sh
pip install -r sistema/requirements.txt && python -m sistema.ml.entrenar
```

Comando de inicio:

```sh
uvicorn sistema.app:app --host 0.0.0.0 --port $PORT --workers 1
```

El Blueprint selecciona el plan `free`, Python 3.12.14, la variante CPU de XGBoost y un
solo proceso. La comprobación del servidor está en `/salud`. El despliegue automático
queda desactivado: los cambios de GitHub se publican desde Render cuando se decida.
La configuración sigue la [referencia oficial de Blueprints](https://render.com/docs/blueprint-spec).

Despliegue verificado: los tres modelos se entrenaron leyendo Neon. Se comprobó el ingreso,
las seis pantallas principales y una predicción de ETA, demanda semanal y retorno. Las
consultas de prueba guardaron sus estimaciones mediante el sistema; no se borraron históricos
ni se modificó el esquema SQL. También se verificó la apertura de los siete gráficos.

La instancia gratuita puede suspenderse por inactividad. Antes de la presentación, abrir
la web con anticipación para dar tiempo al arranque.

## Ejecutar el sistema web localmente

Desde la raíz del repositorio, con Python 3.12:

```sh
python -m venv .venv
```

Activar con `.venv\Scripts\Activate.ps1` en PowerShell, o con `source .venv/bin/activate`
en Linux/macOS. Instalar después con `python -m pip install -r sistema/requirements.txt`.
Copiar `sistema/.env.example` a
`sistema/.env` y completar las cuatro variables con valores privados. Después:

```sh
python -m sistema.ml.entrenar
python -m uvicorn sistema.app:app --reload
```

Abrir `http://127.0.0.1:8000`. Nunca subir `.env`, contraseñas ni cadenas de conexión a GitHub.

## Pruebas funcionales del sistema web

Estas comprobaciones verifican el funcionamiento de la aplicación. Son distintas de los
scripts de modelos con CSV locales que están en `consola/`.

`python -m sistema.pruebas.verificar` ejecuta las comprobaciones de acceso, solicitudes, pesaje,
salida, entrega, ETA, demanda y retorno. Exige `TEST_DATABASE_URL` de una base local de
pruebas con el esquema y catálogos del proyecto; rechaza conexiones remotas como Neon.
Los modelos deben haberse entrenado antes contra esa base de prueba.
Las comprobaciones registran nuevos viajes de prueba en esa base local; no limpian tablas.

Validación ejecutada en una copia aislada de PostgreSQL con PostGIS: 41 comprobaciones
funcionales aprobadas, las seis pantallas principales con históricos vacíos, 30 consultas
adicionales de navegación y acceso autenticado a los siete gráficos. También se verificó
el arranque real con Uvicorn y las consultas por HTTP. Estas pruebas locales no realizaron
escrituras en Neon.
Se comprobó que navegar entre dos pantallas de la misma sesión conserva el token CSRF.

El código de las pantallas está en `sistema/plantillas/`; cada HTML tiene menos de 100 líneas.
No se necesita JavaScript para los formularios, los filtros ni la navegación.
La conexión está en `db.py`, el flujo de transporte en `operacion/` y los modelos en `ml/`.
Las pruebas quedan en `pruebas/`, separadas del código que atiende las pantallas.

## Alcance del prototipo

Este avance permite demostrar la operación y los tres modelos integrados a PostgreSQL.
Se registran manualmente el pesaje, la GRE emitida, las incidencias y el enlace de la
constancia. La emisión real ante SUNAT, la lectura automática de GPS/balanza, la aplicación
móvil sin conexión y el almacenamiento de fotografías requieren sus integraciones externas.
Este prototipo no las presenta como implementadas.
