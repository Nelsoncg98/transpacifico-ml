"""OE2: leer SQL (o CSV auxiliar), entrenar Prophet (80/20) por corredor y pronosticar 1 semana."""

from pathlib import Path
import sys
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from prophet import Prophet
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

CARPETA = Path(__file__).parent
sys.path.append(str(CARPETA.parent))
ARCHIVO = CARPETA / "dataset.csv"
USAR_SQL = True  # -> False permite usar el CSV auxiliar sin conexión.


def principal(interfaz=False):
    # 1. LEER EL DATASET: PostgreSQL es la fuente principal.
    if USAR_SQL:
        from base_datos import cargar_datos_oe2
        datos = cargar_datos_oe2()  # -> solo consulta; no genera ni cambia registros.
    else:
        datos = pd.read_csv(ARCHIVO, encoding="utf-8-sig")  # -> respaldo local.
    print("Fuente: PostgreSQL" if USAR_SQL else "Fuente: CSV auxiliar")
    print(f"Dataset: {len(datos)} filas y {len(datos.columns)} columnas")

    corredores = ["Centro", "Norte"]                              # -> los dos corredores a evaluar
    modelos_entrenados = {}                                       # -> diccionario para guardar el modelo de cada corredor

    print("\n--- RESULTADOS DEL MODELO PROPHET (80% Train / 20% Test) ---")

    evaluaciones = {}  # -> conservar las semanas de prueba para el visor local.

    for corredor in corredores:

        # 2. FILTRAR EL CORREDOR Y PREPARAR NOMBRES QUE PIDE PROPHET (ds y y)
        tabla_corredor = datos[datos["corredor"] == corredor].copy() # -> filtra las 104 semanas de este corredor
        tabla_corredor = tabla_corredor.rename(columns={
            "semana_inicio": "ds",                                # -> Prophet exige llamar 'ds' a la columna de fecha
            "toneladas_semana": "y",                              # -> Prophet exige llamar 'y' a la columna objetivo
        })
        tabla_corredor["ds"] = pd.to_datetime(tabla_corredor["ds"]) # -> convierte el texto de fecha a formato calendario

        # 3. DIVIDIR EN 80% ENTRENAMIENTO Y 20% PRUEBA (Ordenado por semanas)
        total_semanas = len(tabla_corredor)                       # -> total de semanas del corredor (104 semanas)
        corte_80 = int(total_semanas * 0.80)                      # -> calcula el 80% (83 semanas para entrenar)

        train = tabla_corredor.iloc[:corte_80]                    # -> primeras 83 semanas para entrenar el modelo
        test = tabla_corredor.iloc[corte_80:]                     # -> últimas 21 semanas para poner a prueba el modelo

        # 4. CREAR Y ENTRENAR EL MODELO PROPHET
        modelo = Prophet(yearly_seasonality=False, weekly_seasonality=False, daily_seasonality=False)
        modelo.add_regressor("feriados_semana")                   # -> agrega la variable de feriados al modelo
        modelo.add_regressor("dias_segunda_quincena")             # -> agrega la variable de segunda quincena al modelo
        modelo.fit(train)                                         # -> el modelo estudia solo con el 80% de entrenamiento

        modelos_entrenados[corredor] = modelo                     # -> guarda el modelo entrenado de este corredor

        # 5. EVALUAR RESULTADOS (Entrenamiento vs Prueba)
        pred_train = modelo.predict(train)["yhat"]                # -> predicciones sobre el 80% de entrenamiento
        pred_test = modelo.predict(test)["yhat"]                  # -> examen sobre el 20% de prueba que nunca vio

        r2_train = r2_score(train["y"], pred_train)               # -> precisión R2 en entrenamiento
        r2_test = r2_score(test["y"], pred_test)                  # -> precisión R2 en prueba
        mae_test = mean_absolute_error(test["y"], pred_test)      # -> error promedio en toneladas
        rmse_test = np.sqrt(mean_squared_error(test["y"], pred_test)) # -> raíz del error cuadrático medio

        print(f"\nCorredor {corredor}:")
        print(f"  Entrenamiento R2: {r2_train:.4f}")
        print(f"  Prueba R2:        {r2_test:.4f}")
        print(f"  Error MAE:        {mae_test:.2f} toneladas")
        print(f"  Error RMSE:       {rmse_test:.2f} toneladas")

        if interfaz:
            evaluaciones[corredor] = {"prueba": test.copy(), "predicha": pred_test.to_numpy()}

        # 6. GENERAR Y GUARDAR GRÁFICO DEL CORREDOR (20% Prueba)
        plt.figure(figsize=(9, 5))
        plt.plot(test["ds"], test["y"], marker="o", label="Toneladas del dataset")
        plt.plot(test["ds"], pred_test, marker="s", linestyle="--", label="Toneladas predichas")
        plt.title(f"OE2: Toneladas observadas vs. predichas en prueba - {corredor} (datos simulados)")
        plt.xlabel("Semana de inicio")
        plt.ylabel("Toneladas por semana")
        plt.legend()
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig(CARPETA / f"oe2_pronostico_{corredor.lower()}.png", dpi=150)

    # La ventana utiliza los mismos modelos; no entrena otra versión.
    if interfaz:
        return {"datos": datos, "modelos": modelos_entrenados, "evaluaciones": evaluaciones}

    # 7. PROBAR 1 SEMANA INGRESANDO DATOS
    print("\n--- PROBAR PRONÓSTICO DE 1 SEMANA ---")
    corredor_elegido = input("Corredor (Centro / Norte): ")
    fecha_lunes = input("Fecha del lunes de esa semana (ej. 2026-01-05): ")
    feriados = int(input("Feriados en esa semana (0, 1 o 2): "))
    quincena = int(input("Días de segunda quincena (0 a 7): "))

    # Armar la tabla de 1 sola línea con los datos ingresados
    fila_nueva = pd.DataFrame([{
        "ds": pd.to_datetime(fecha_lunes),
        "feriados_semana": feriados,
        "dias_segunda_quincena": quincena,
    }])

    # Predecir las toneladas usando el modelo del corredor elegido
    modelo_usar = modelos_entrenados[corredor_elegido]            # -> selecciona el modelo del corredor ingresado
    resultado = modelo_usar.predict(fila_nueva)                   # -> calcula el pronóstico para esa semana
    toneladas_predichas = float(resultado["yhat"].iloc[0])        # -> extrae el valor numérico predicho

    print(f"\n-> Demanda semanal predicha ({corredor_elegido}): {toneladas_predichas:.2f} toneladas")
    plt.show()


if __name__ == "__main__":
    principal()
