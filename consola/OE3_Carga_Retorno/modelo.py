"""OE3: leer SQL (o CSV auxiliar), entrenar Árbol de Decisión (80/20) y consultar un retorno."""

from pathlib import Path
import sys
import matplotlib.pyplot as plt
import pandas as pd
from sklearn.metrics import (
    ConfusionMatrixDisplay,
    RocCurveDisplay,
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.tree import DecisionTreeClassifier, plot_tree

CARPETA = Path(__file__).parent
sys.path.append(str(CARPETA.parent))
ARCHIVO = CARPETA / "dataset.csv"
USAR_SQL = True  # -> False permite usar el CSV auxiliar sin conexión.

VARIABLES = [
    "origen_retorno",
    "dia_entrega_pactada",
    "quincena_entrega_pactada",
    "solicitudes_compatibles",
    "proporcion_retornos_previos",
]
OBJETIVO = "retorno_con_carga"
CATEGORIAS = ["origen_retorno"]


def principal():
    # 1. LEER EL DATASET: PostgreSQL es la fuente principal.
    if USAR_SQL:
        from base_datos import cargar_datos_oe3
        datos = cargar_datos_oe3()  # -> solo consulta; no genera ni cambia registros.
    else:
        datos = pd.read_csv(ARCHIVO, encoding="utf-8-sig")  # -> respaldo local.
    print("Fuente: PostgreSQL" if USAR_SQL else "Fuente: CSV auxiliar")
    print(f"Dataset: {len(datos)} filas y {len(datos.columns)} columnas")
    datos = datos.sort_values(["fecha_hora_evaluacion", "id_despacho"]).reset_index(drop=True)

    # 2. PREPARAR ENTRADAS (X) Y RESPUESTA (y)
    X = pd.get_dummies(datos[VARIABLES], columns=CATEGORIAS, dtype=int) # -> convierte Huancayo/Trujillo a números 0 y 1
    y = datos[OBJETIVO]                                                 # -> separa la columna objetivo (0=vacío, 1=con carga)

    # 3. DIVIDIR EN 80% ENTRENAMIENTO Y 20% PRUEBA POR FECHA (Mantiene el pasado antes de la prueba)
    corte_80 = int(len(datos) * 0.80)                             # -> calcula el 80% (primeros 800 casos por fecha)
    X_train, X_test = X.iloc[:corte_80], X.iloc[corte_80:]        # -> 800 casos antiguos para entrenar y 200 recientes para probar
    y_train, y_test = y.iloc[:corte_80], y.iloc[corte_80:]        # -> respuestas de entrenamiento (800) y de prueba (200)

    # 4. CREAR Y ENTRENAR EL ÁRBOL DE DECISIÓN
    modelo = DecisionTreeClassifier(max_depth=4, random_state=42) # -> árbol de clasificación de 4 niveles
    modelo.fit(X_train, y_train)                                  # -> el árbol estudia solo con el 80% de entrenamiento

    # 5. EVALUAR RESULTADOS (Accuracy, Precision, Recall, F1 y Matriz de Confusión)
    pred_train = modelo.predict(X_train)                          # -> predicciones sobre el 80% de entrenamiento
    pred_test = modelo.predict(X_test)                            # -> examen sobre el 20% de prueba que nunca vio

    acc_train = accuracy_score(y_train, pred_train)               # -> exactitud (Accuracy) en entrenamiento
    acc_test = accuracy_score(y_test, pred_test)                  # -> exactitud (Accuracy) en prueba
    prec_test = precision_score(y_test, pred_test)                # -> precisión cuando predice retorno con carga
    rec_test = recall_score(y_test, pred_test)                    # -> sensibilidad (Recall) detectando carga real
    f1_test = f1_score(y_test, pred_test)                         # -> promedio armónico (F1-Score)
    matriz = confusion_matrix(y_test, pred_test)                  # -> matriz de confusión (aciertos y errores)

    print("\n--- RESULTADOS DEL ÁRBOL DE DECISIÓN (80% Train / 20% Test) ---")
    print(f"Entrenamiento Accuracy: {acc_train:.4f}")
    print(f"Prueba Accuracy:        {acc_test:.4f}")
    print(f"Precision (con carga):  {prec_test:.4f}")
    print(f"Recall (con carga):     {rec_test:.4f}")
    print(f"F1-Score (con carga):   {f1_test:.4f}")
    print("\nMatriz de Confusión (200 casos de prueba):")
    print(pd.DataFrame(matriz, index=["Real Vacío (0)", "Real Con Carga (1)"], columns=["Pred Vacío (0)", "Pred Con Carga (1)"]))

    # 6. GENERAR Y GUARDAR GRÁFICOS (Matriz de Confusión, Árbol y Curva ROC)
    ConfusionMatrixDisplay.from_predictions(
        y_test, pred_test, display_labels=["Vacío (0)", "Con carga (1)"], cmap="Blues"
    )
    plt.title("OE3: Matriz de confusión en prueba (datos simulados)")
    plt.tight_layout()
    plt.savefig(CARPETA / "oe3_matriz_confusion.png", dpi=150)

    plt.figure(figsize=(20, 10))
    plot_tree(
        modelo,
        feature_names=X.columns,
        class_names=["Vacío (0)", "Con carga (1)"],
        filled=True,
        rounded=True,
        fontsize=9,
        precision=2,
    )
    plt.title("OE3: Árbol de decisión entrenado (datos simulados)")
    plt.tight_layout()
    plt.savefig(CARPETA / "oe3_arbol_decision.png", dpi=150)

    RocCurveDisplay.from_estimator(modelo, X_test, y_test)
    plt.title("OE3: Curva ROC en prueba (datos simulados)")
    plt.tight_layout()
    plt.savefig(CARPETA / "oe3_curva_roc.png", dpi=150)

    # 7. PROBAR 1 RETORNO INGRESANDO DATOS
    print("\n--- PROBAR PREDICCIÓN DE 1 RETORNO ---")
    origen = input("Ciudad de retorno hacia Callao (Huancayo / Trujillo): ")
    dia = int(input("Día de entrega pactada (1=Lunes a 7=Domingo): "))
    quincena = int(input("Quincena del mes (1=Primera / 2=Segunda): "))
    solicitudes = int(input("Solicitudes compatibles disponibles (0 a 5): "))
    proporcion = float(input("Proporción histórica previa (ej. 0.65): "))

    # Armar la tabla de 1 sola línea con los datos ingresados
    fila_nueva = pd.DataFrame([{
        "origen_retorno": origen,
        "dia_entrega_pactada": dia,
        "quincena_entrega_pactada": quincena,
        "solicitudes_compatibles": solicitudes,
        "proporcion_retornos_previos": proporcion,
    }])

    # Preparar las columnas igual que en el entrenamiento y predecir
    consulta = pd.get_dummies(fila_nueva, columns=CATEGORIAS, dtype=int)
    consulta = consulta.reindex(columns=X.columns, fill_value=0)  # -> asegura que tenga las mismas columnas que X
    resultado = int(modelo.predict(consulta)[0])                  # -> predice 1 (con carga) o 0 (vacío)
    probabilidad = float(modelo.predict_proba(consulta)[0, 1])    # -> calcula la probabilidad de volver con carga

    texto_estado = "CON CARGA (1)" if resultado == 1 else "VACÍO (0)"
    print(f"\n-> Resultado predicho: {texto_estado} | Probabilidad de carga: {probabilidad:.1%}")
    plt.show()


if __name__ == "__main__":
    principal()
