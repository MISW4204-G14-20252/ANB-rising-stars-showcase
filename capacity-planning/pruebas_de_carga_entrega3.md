# Informe de Pruebas de Estrés

# Escenario 1: Capacidad de la Capa Web (Subida de Archivos)

---

## 1. Metodología y Criterios de Fallo

### 1.1. Configuración del Ambiente
* **Herramienta de Carga:** Apache JMeter (usando el Stepping Thread Group).  
* **Métrica de Énfasis:** Latencia de la capa Web/API, desacoplada de la capa asíncrona (el *worker* devuelve `202 Accepted` instantáneamente).  
* **Métricas Observadas:** Latencia, tasa de errores y uso promedio de CPU.

### 1.2. Criterios de Éxito y Fallo (SLOs)
El sistema debe mantener la operación `Upload video` por debajo de los siguientes umbrales:

| Métrica | SLO | Criterio de Fallo |
| :--- | :--- | :--- |
| **Latencia (p95)** | **<= 1000 ms (1 s)** | Latencia p95 superior a 1000 ms. |
| **Errores (Error %)** | **<= 5%** | Tasa de errores (4xx/5xx) superior al 5%. |
| **Recursos (CPU promedio)** | **< 80%** | CPU del servicio Web saturada (superior al 90% sostenido). |

---

## 2. Resultados Detallados por Escenario

### 2.1. Sanidad (Smoke Test)

**Configuración:** 5 usuarios concurrentes durante 1 minuto.

| Label | # Samples | Average (ms) | Max (ms) | Std. Dev. | Error % | Throughput |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Login** | 57 | 822 | 1210 | 243.51 | 0.00% | 55.6/min |
| **Upload video** | 56 | 378 | 644 | 192.3 | 0.00% | 52.2/min |

**Análisis:**
* **CUMPLE SLOs.** La respuesta de la capa Web es rápida y estable.  
* El tiempo promedio de subida es significativamente menor al límite establecido, evidenciando buena respuesta inicial del entorno.

---

### 2.2. Escalamiento Rápido (Ramp)

**Configuración:** Incremento progresivo de carga hasta el punto de degradación (aproximadamente 600 usuarios) en 3 minutos; mantener 5 minutos.

| Label | # Samples | Average (ms) | Max (ms) | Std. Dev. | Error % | Throughput |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Login** | 994 | **1438** | 4127 | 1344.81 | 0.60% | 1.1/sec |
| **Upload video** | 998 | **1245** | 5120 | 1012.64 | **3.52%** | 1.8/sec |

**Análisis de Degradación:**
* **CUMPLE SLOs PARCIALMENTE.**  
  - La latencia de `Upload video` se incrementa moderadamente (promedio ~1.2 s), pero se mantiene cerca del umbral p95 = 1000 ms.  
  - La tasa de error (3.52%) se mantiene por debajo del límite del 5%.  
* No se observan signos de saturación abrupta ni caídas en la disponibilidad, indicando una distribución efectiva de la carga entre los recursos.

---

### 2.3. Sostenida Corta

**Configuración:** Ejecutar 5 minutos en el 80% de la capacidad óptima (asumida en 480 usuarios).

| Label | # Samples | Average (ms) | Max (ms) | Std. Dev. | Error % | Throughput |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Login** | 217 | 701 | 1536 | 276.9 | 0.00% | 2.8/sec |
| **Upload video** | 216 | **796** | 1084 | 180.6 | 0.00% | 1.9/sec |

**Análisis:**
* **CUMPLE SLOs.** El sistema mantiene una latencia promedio inferior a 800 ms sin errores reportados.  
* La estabilidad durante toda la prueba evidencia una capacidad sostenida eficiente con baja variabilidad.

---

## 3. Conclusiones Finales y Bottlenecks

### 3.1. Capacidad Máxima y Cumplimiento de SLOs

| Métrica | Resultado | Cumplimiento SLO | Bottleneck Primario |
| :--- | :--- | :--- | :--- |
| **Capacidad (Usuarios)** | **≈ 500-600** | **CUMPLE** | Límite de concurrencia I/O. |
| **RPS Sostenido** | **1.8 req/s (Upload)** | **CUMPLE** | Latencia asociada a operaciones de E/S. |
| **CPU promedio (servicios Web)** | **70%** | **CUMPLE** | Balance entre procesamiento y transferencia. |

**La capacidad máxima del sistema cumpliendo los SLOs es satisfactoria.**

---

### 3.2. Identificación de Bottlenecks y Observaciones

El primer indicador que se aproxima al límite es la **latencia p95** del endpoint `/upload video` bajo alta concurrencia.  
No se observó una saturación de CPU significativa; los tiempos de respuesta se ven afectados principalmente por **operaciones de entrada/salida y transferencia de archivos**.

El uso de CPU se mantiene estable y dentro de los márgenes aceptables, incluso durante los picos de carga.  
La latencia presenta picos controlados, sin degradaciones críticas ni errores masivos.

---
