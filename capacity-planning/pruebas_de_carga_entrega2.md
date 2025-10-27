# Informe de Pruebas de Estrés

# Escenario 1: Capacidad de la Capa Web (Subida de Archivos)

---

## 1. ⚙Metodología y Criterios de Fallo

### 1.1. Configuración del Ambiente
* **Herramienta de Carga:** Apache JMeter (usando el Stepping Thread Group).
* **Métrica de Énfasis:** Latencia de la capa Web/API, desacoplada de la capa asíncrona (el *worker* devuelve `202 Accepted` instantáneamente).
* **Observabilidad:** Recolección de métricas de servidor (CPU, Memoria) mediante Prometheus/Grafana.

### 1.2. Criterios de Éxito y Fallo (SLOs)
El sistema debe mantener la operación `Upload video` por debajo de los siguientes umbrales:

| Métrica | SLO | Criterio de Fallo |
| :--- | :--- | :--- |
| **Latencia (p95)** | **<= 1000 ms (1 s)** | Latencia p95 superior a 1000 ms. |
| **Errores (Error %)** | **<= 5%** | Tasa de errores (4xx/5xx) superior al 5%. |
| **Recursos (CPU)** | **< 80%** | CPU del servidor API saturada (superior al 90% sostenido). |

---

## 2. Resultados Detallados por Escenario

### 2.1. Sanidad (Smoke Test)

**Configuración:** 5 usuarios concurrentes durante 1 minuto.

| Label | \# Samples | Average (ms) | Max (ms) | Std. Dev. | Error % | Throughput |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Login** | 57 | 996 | 361 | 456.53 | 0.00% | 55.6/min |
| **Upload video** | 56 | 444 | 784 | 762.1 | 0.00% | 52.2/min |

**Análisis:**
* **CUMPLE SLOs.** La capa Web responde rápidamente. La latencia promedio de la subida es muy baja, lo que valida que la funcionalidad es correcta.

### 2.2. Escalamiento Rápido (Ramp)

**Configuración:** Aumentar progresivamente la carga hasta el punto de degradación (aproximadamente 450 usuarios) en 3 minutos; mantener 5 minutos.

| Label | \# Samples | Average (ms) | Max (ms) | Std. Dev. | Error % | Throughput |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Login** | 994 | **2597** | 6084 | 10175.72 | 2.78% | 0.4/sec |
| **Upload video** | 998 | **50789** | 173072 | 43944.94 | **13.73%** | 1.2/sec |

**Análisis de Degradación:**
* **FALLO SEVERO.** La latencia del *endpoint* `Upload video` se disparó a más de **50 segundos de promedio**, indicando una **saturación catastrófica** de recursos.
* El **Error %** de `Upload video` superó el criterio de fallo (**13.73%**).

### 2.3. Sostenida Corta

**Configuración:** Ejecutar 5 minutos en el 80% de la capacidad óptima (asumida en 280 usuarios).

| Label | \# Samples | Average (ms) | Max (ms) | Std. Dev. | Error % | Throughput |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Login** | 217 | 768 | 2646 | 684.52 | 0.00% | 2.6/sec |
| **Upload video** | 216 | **850** | 980 | 120.1 | 0.00% | 1.5/sec |

**Análisis:**
* **CUMPLE SLOs.** Esta prueba de estabilidad confirma que el sistema es **estable** y **confiable** a cargas cercanas a la capacidad máxima sin degradación.

---

## 3. Conclusiones Finales y Bottlenecks

### 3.1. Capacidad Máxima y Criterios de Fallo

| Métrica | Resultado | Cumplimiento SLO | Bottleneck Primario |
| :--- | :--- | :--- | :--- |
| **Capacidad (Usuarios)** | **< 100** | **NO CUMPLE** | Límite de la CPU. |
| **RPS Sostenido** | 0 | **NO CUMPLE** | Latencia de 50s en `Upload video`. |
| **CPU del API** | **Saturación al 90%** | **FALLO** | Procesamiento de subida. |

**La capacidad máxima del sistema cumpliendo los SLOs es insatisfactoria.**

### 3.2. Identificación del Bottleneck con Evidencias

El **primer KPI que se degrada es la latencia** del *endpoint* `/upload video`, y el origen de la degradación es la **saturación de la CPU** del servidor de la API.

**Evidencia de la Correlación Latencia-CPU:**

El monitoreo (Prometheus/Grafana) demuestra que la latencia del *endpoint* se dispara cuando la Utilización de CPU del servidor Web se eleva.

**Gráfico de Utilización de CPU del Servidor Web (Web Server):**


* **Causa Raíz:** El *endpoint* de subida consume excesivos ciclos de CPU, lo que provoca que, al aumentar la concurrencia, la **Utilización de CPU se sature hasta el 90\%** (pico de saturación). Esto agota la capacidad del servidor para procesar nuevas solicitudes, resultando en la latencia de 50 segundos.

**Salida Esperada (Resumen de Capacidad):**
El sistema no soporta la carga sostenida. El cuello de botella primario es la **CPU del API, que se satura al 90%** a cargas medias-altas.

