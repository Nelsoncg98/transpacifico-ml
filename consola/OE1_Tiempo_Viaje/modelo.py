"""OE1: cargar el CSV, entrenar XGBoost (80/20) y consultar un viaje."""

from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from xgboost import XGBRegressor

CARPETA = Path(__file__).parent
ARCHIVO = CARPETA / "dataset.csv"

VARIABLES = [
    "origen", "destino", "distancia_km", "peso_carga_tn",
    "dia_salida", "hora_salida", "velocidad_media_estimada_kmh",
]
OBJETIVO = "duracion_viaje_min"
CATEGORIAS = ["origen", "destino"]


def principal():
    # 1. CARGAR EL DATASET
    datos = pd.read_csv(ARCHIVO, encoding="utf-8-sig")            # -> lee los 1,000 viajes del archivo CSV

    # 2. PREPARAR ENTRADAS (X) Y RESPUESTA (y)
    X = pd.get_dummies(datos[VARIABLES], columns=CATEGORIAS, dtype=int) # -> convierte texto (Callao, etc.) a números 0 y 1
    y = datos[OBJETIVO]                                                 # -> separa la columna de duración en minutos

    # 3. DIVIDIR EN 80% ENTRENAMIENTO Y 20% PRUEBA (Como pide el profesor)
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, random_state=42                     # -> 800 viajes para entrenar y 200 para probar
    )

    # 4. CREAR Y ENTRENAR EL MODELO XGBOOST
    modelo = XGBRegressor(n_estimators=100, max_depth=3, learning_rate=0.1, random_state=42)
    modelo.fit(X_train, y_train)                                  # -> el modelo estudia solo con el 80% de entrenamiento

    # 5. EVALUAR RESULTADOS (Entrenamiento vs Prueba)
    pred_train = modelo.predict(X_train)                          # -> predicciones sobre el 80% de entrenamiento
    pred_test = modelo.predict(X_test)                            # -> examen sobre el 20% de prueba que nunca vio

    r2_train = r2_score(y_train, pred_train)                      # -> precisión R2 en entrenamiento
    r2_test = r2_score(y_test, pred_test)                         # -> precisión R2 en prueba
    mae_test = mean_absolute_error(y_test, pred_test)             # -> error promedio en minutos
    rmse_test = np.sqrt(mean_squared_error(y_test, pred_test))    # -> raíz del error cuadrático medio

    print("\n--- RESULTADOS DEL MODELO XGBOOST (80% Train / 20% Test) ---")
    print(f"Entrenamiento R2: {r2_train:.4f}")
    print(f"Prueba R2:        {r2_test:.4f}")
    print(f"Error MAE:        {mae_test:.2f} minutos")
    print(f"Error RMSE:       {rmse_test:.2f} minutos")

    # 6. GENERAR Y GUARDAR GRÁFICOS (20% Prueba)
    plt.figure(figsize=(8, 6))
    plt.scatter(y_test, pred_test, alpha=0.7)                     # -> un punto por cada viaje del 20% de prueba
    plt.plot([y_test.min(), y_test.max()], [y_test.min(), y_test.max()], "r--") # -> línea de coincidencia perfecta
    plt.title("OE1: Duración del dataset vs. predicha en prueba (datos simulados)")
    plt.xlabel("Duración del dataset (minutos)")
    plt.ylabel("Duración predicha (minutos)")
    plt.tight_layout()
    plt.savefig(CARPETA / "oe1_real_vs_predicho.png", dpi=150)

    plt.figure(figsize=(9, 5))
    plt.barh(X.columns, modelo.feature_importances_)              # -> barras con la importancia de cada variable
    plt.title("OE1: Importancia de las variables en XGBoost (datos simulados)")
    plt.xlabel("Importancia relativa")
    plt.tight_layout()
    plt.savefig(CARPETA / "oe1_importancia_variables.png", dpi=150)

    # 7. PROBAR 1 VIAJE INGRESANDO DATOS
    print("\n--- PROBAR PREDICCIÓN DE 1 VIAJE ---")
    origen = input("Origen (Callao / Huancayo / Trujillo): ")
    destino = input("Destino (Huancayo / Trujillo / Callao): ")
    distancia = float(input("Distancia en km (395 o 575): "))
    peso = float(input("Peso de carga en toneladas (0 a 29): "))
    dia = int(input("Día de salida (1=Lunes a 7=Domingo): "))
    hora = float(input("Hora de salida (5 a 20): "))
    velocidad = float(input("Velocidad media estimada km/h: "))

    # Armar la tabla de 1 sola línea con los datos ingresados
    fila_nueva = pd.DataFrame([{
        "origen": origen,
        "destino": destino,
        "distancia_km": distancia,
        "peso_carga_tn": peso,
        "dia_salida": dia,
        "hora_salida": hora,
        "velocidad_media_estimada_kmh": velocidad,
    }])

    # Preparar las columnas igual que en el entrenamiento y predecir
    consulta = pd.get_dummies(fila_nueva, columns=CATEGORIAS, dtype=int)
    consulta = consulta.reindex(columns=X.columns, fill_value=0)  # -> asegura que tenga las mismas columnas que X
    minutos_predichos = float(modelo.predict(consulta)[0])        # -> el modelo calcula la duración en minutos

    print(f"\n-> Resultado predicho: {minutos_predichos:.2f} minutos ({minutos_predichos / 60:.2f} horas)")
    plt.show()


if __name__ == "__main__":
    principal()
