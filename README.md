# Transpacífico S.A.C. · Sistema Integrado de Gestión Logística y Analítica Predictiva

Portal web unificado en **Python / FastAPI**, plantillas **Jinja2**, visualización interactiva con **Chart.js 4** y base de datos relacional **PostgreSQL (Neon)**. Integra el ciclo operativo completo del transporte terrestre de carga pesada y tres modelos de Machine Learning (**XGBoost**, **Prophet** y **Árbol de Decisión**).

- **Despliegue web:** https://transpacifico.onrender.com
- **Control de acceso (RBAC):** Autenticación multiusuario contra la tabla `usuario` con derivación criptográfica `scrypt`, verificación CSRF por sesión, selección de sede operativa desde BD y expiración configurable (`1,800 s` por defecto).

---

## Arquitectura del repositorio

| Componente | Carpeta | Función |
|---|---|---|
| Sistema web integrado | `sistema/` | Aplicación única FastAPI + Jinja2 + Chart.js conectada a PostgreSQL (Neon) con diseño responsivo para PC, tablet y móvil. |
| Entorno de apoyo y semilla | `consola/` | Scripts individuales por modelo con respaldo CSV (`USAR_SQL = False`), interfaz Tkinter de apoyo y generador transaccional `generarSQL.py`. |
| Esquema SQL base | `sql/` | Script DDL base de las 19 tablas del proyecto. La aplicación web consulta esas tablas sin crear esquemas ni ejecutar migraciones al arrancar. |

### Organización modular de `sistema/`

| Módulo | Responsabilidad |
|---|---|
| `app.py`, `config.py`, `db.py`, `seguridad.py` | Arranque FastAPI, parámetros normativos (`48,000 kg`, `85 %` FOF, paginación y sesión), pool PostgreSQL (`psycopg_pool`) y autenticación RBAC. |
| `operacion/catalogos_bd.py` | Lectura dinámica de corredores, sedes operativas y rutas válidas directamente desde SQL. |
| `operacion/solicitudes.py` | Alta, edición, anulación, evaluación (`Aceptada` / `Rechazada`) y control de vigencia de ventanas de entrega. |
| `operacion/despachos.py` | Programación simultánea multiunidad, reasignación o cancelación con liberación de recursos, brevete `A-IIIc`, `FOF` y expediente `/viajes/{id}`. |
| `operacion/pesaje_salida.py` | Báscula en patio (`PBV <= 48,000 kg` y límite de semirremolque), estados `Conforme` / `Reestiba`, precintos, número GRE y autorización de salida. |
| `operacion/entregas.py` | Incidencias en ruta, llegada a destino, cierre con `POD` + `OTIF` y verificación documental administrativa (`verificacion_entrega`). |
| `operacion/flota.py` | Mantenimiento CRUD de tractocamiones, semirremolques, conductores, clientes y cuentas RBAC, más centro de alertas ETA (`/alertas`). |
| `operacion/reportes.py` | KPIs SQL en vivo (`OTIF`, `FOF`, kilómetros productivos vs. en vacío), exportación `/reportes.csv`, métricas `80/20` y reentrenamiento en caliente. |
| `operacion/formularios.py` | Contexto compartido Jinja2, alertas activas en navegación, resumen de corredores y conversiones de zona horaria (`America/Lima`). |
| `ml/oe1.py`, `oe2.py`, `oe3.py` | Entrenamiento `80/20`, evaluación e inferencia de XGBoost (`OE1`), Prophet (`OE2`) y Árbol de Decisión (`OE3`). |
| `ml/datos.py`, `predicciones.py`, `entrenar.py`, `almacen.py`, `graficos.py` | Lectura SQL (`ml/sql/`), cálculo automático de sugerencias desde histórico real, endpoints predictivos y generación opcional de árboles estáticos. |
| `estaticos/estilos.css`, `graficos.js` | Sistema visual corporativo responsivo y lógica cliente para Chart.js, sincronización corredor-ruta, ajuste al lunes `OE2` y simulación reversible `OE3`. |
| `pruebas/verificar.py` | Suite automatizada de integración contra PostgreSQL local (`TEST_DATABASE_URL`; rechaza conexiones remotas como Neon). |

---

## Flujo operativo integrado

1. **Acceso por rol y sede (`/ingresar`):** Autentica usuarios activos en PostgreSQL con control RBAC por rol (`Operador`, `Jefe de Operaciones`, `Programador de Flota`, `Operador de Patio`, `Operador de Tráfico`, `Operador de despacho`, `Planificador de flota` y `Conductor`), incluida la cuenta operativa principal configurada por variables de entorno (`APP_USER` / `APP_PASSWORD`).
2. **Solicitudes de transporte (`/solicitudes`):** Valida cliente, corredor y par origen-destino según histórico SQL, límite útil de semirremolque y entrega pactada futura. Solo las solicitudes vigentes pueden aceptarse o programarse.
3. **Programación de viajes (`/viajes`):** Asigna tractocamión, semirremolque y conductor disponibles con licencia `A-IIIc` vigente, calcula el **Factor de Ocupación de Flota (`FOF`)** y sugiere el último odómetro real de la unidad.
4. **Control de patio, báscula y salida (`/viajes/{id}`):** Registra tara y peso bruto comprobando `PBV <= 48,000 kg` y capacidad del semirremolque, habilita precintos y número de `GRE` emitida antes de autorizar salida.
5. **Seguimiento, alertas y cierre `POD` (`/viajes/{id}`, `/alertas`):** Registra incidencias, estima **ETA (`OE1`)**, genera alerta automática si la ETA supera la ventana pactada y cierra el despacho al cargar el `POD` final evaluando `OTIF` y auditoría de facturación.
6. **Flota, alertas e indicadores (`/`, `/flota`, `/reportes.csv`):** Administra recursos y usuarios RBAC, presenta KPIs SQL en vivo con gráficos comparativos por corredor y estado, y exporta reportes CSV.

---

## Modelos de Machine Learning (`OE1`, `OE2`, `OE3`)

| Objetivo | Algoritmo | Variables de entrada | Estrategia de evaluación | Integración en el portal |
|---|---|---|---|---|
| **OE1 · Duración y ETA** | `XGBRegressor` (`100` árboles, `max_depth=3`, `lr=0.1`) | Corredor, destino, peso neto (`t`), día y hora de salida | `80/20` aleatorio (`seed=42`): `R²`, `MAE` y `RMSE` (min) | Integrado en `/viajes` y `/viajes/{id}#oe1-eta`. Calcula arribo previsto o tiempo restante en ruta según km faltantes y genera alertas ETA. |
| **OE2 · Demanda semanal** | `Prophet` por corredor | Fecha lunes de semana, feriados previstos y días en 2da quincena | `80/20` cronológico por corredor: `R²`, `MAE` y `RMSE` (`t`) | Pantalla `/demanda`. Sugiere el próximo lunes posterior al histórico, restringe/ajusta la fecha al lunes y guarda proyecciones con `es_historico=FALSE`. |
| **OE3 · Retorno con carga** | `DecisionTreeClassifier` (`max_depth=4`, `seed=42`) | Ciudad de retorno, día y quincena pactada, ofertas abiertas (`0–5`) y tasa previa con carga | `80/20` cronológico: `Accuracy`, `Precision`, `Recall`, `F1`, `AUC` y matriz de confusión | Pantalla `/retornos`. Selector de despacho de ida con carga automática de ofertas abiertas y tasa real de los últimos `10` retornos cerrados en destino (%), editable para simular escenarios con botón de restauración SQL. |

Desde `/modelos` se visualizan las curvas interactivas de validación `80/20` (dispersión por despacho, importancia de variables, serie temporal Prophet, curva ROC y matrices) junto con el botón **Actualizar entrenamiento desde SQL** (`POST /modelos/reentrenar`), que reentrena sobre PostgreSQL sin alterar datos históricos reales.

---

## Despliegue en Render (`render.yaml`)

1. Crear un **Blueprint** en Render apuntando al repositorio (Root Directory vacío para respetar `render.yaml`).
2. Configurar la variable privada `DATABASE_URL` con la cadena completa de Neon (`sslmode=require`). Render genera `SESSION_SECRET` y `APP_PASSWORD`.
3. Verificar que `APP_USER` (`operador@transpacifico.pe`) exista activo en la tabla `usuario` con rol `Operador` (acceso completo a los módulos).
4. Parámetros definidos en `render.yaml`:
   - **Runtime:** Python `3.12.14`
   - **Build:** `pip install -r sistema/requirements.txt && bash sistema/preparar_graphviz.sh python -m sistema.ml.entrenar`
   - **Start:** `uvicorn sistema.app:app --host 0.0.0.0 --port $PORT --workers 1`
   - **Health check:** `/salud` (`{"estado": "activo"}`)
   - **Publicación:** `autoDeployTrigger: "off"` (después de cada `git push` a `main`, la publicación se ejecuta mediante **Manual Deploy** en Render).

---

## Ejecución local y pruebas

Con Python `3.12`:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r sistema/requirements.txt
```

Copiar `sistema/.env.example` hacia `sistema/.env`, completar las credenciales privadas (`DATABASE_URL`, `SESSION_SECRET`, `APP_USER`, `APP_PASSWORD`) y ejecutar:

```powershell
python -m sistema.ml.entrenar
python -m uvicorn sistema.app:app --reload
```

Abrir `http://127.0.0.1:8000` en PC, tablet o móvil. Para ejecutar la suite de pruebas contra una base local aislada (nunca Neon):

```powershell
$env:TEST_DATABASE_URL = "postgresql://usuario:clave@localhost:5432/transpacifico_test"
python -m sistema.pruebas.verificar
```
