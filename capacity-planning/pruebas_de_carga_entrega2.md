# Informe de Pruebas de Estrés

# Escenario 1: Capacidad de la Capa Web (Subida de Archivos)

---

## 1. Metodología y Criterios de Fallo

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

![https://github.com/MISW4204-G14-20252/ANB-rising-stars-showcase/blob/main/capacity-planning/CPU%20Usage.png](https://github.com/MISW4204-G14-20252/ANB-rising-stars-showcase/blob/main/capacity-planning/CPU%20Usage.png)

* **Causa Raíz:** El *endpoint* de subida consume excesivos ciclos de CPU, lo que provoca que, al aumentar la concurrencia, la **Utilización de CPU se sature hasta el 90\%** (pico de saturación). Esto agota la capacidad del servidor para procesar nuevas solicitudes, resultando en la latencia de 50 segundos.

**Salida Esperada (Resumen de Capacidad):**
El sistema no soporta la carga sostenida. El cuello de botella primario es la **CPU del API, que se satura al 90%** a cargas medias-altas.

# Escenario 2: Capacidad del worker (Procesamiento de videos)

## Objetivo de la prueba
Evaluar el rendimiento del worker encargado del procesamiento de videos al variar la cantidad de **hilos de ejecución (threads)** en un entorno con **2 CPU virtuales (EC2)**.  
El propósito es determinar cómo escala el tiempo de procesamiento con cargas concurrentes y analizar posibles cuellos de botella o interferencias de E/S (lectura/escritura simultánea).

---

## Forma de ejecución

Se ejecutó el worker con el siguiente comando, variando el parámetro `--concurrency=n`:

```bash
sudo -E $(pwd)/venv/bin/celery -A worker.video_processor_task worker --loglevel=info -P threads --concurrency=n -E
```

Donde **n = 1, 2, 4** según la prueba.  
Cada ejecución consistió en **5 videos de 50 MB** procesados de forma concurrente.

---

## Resultados de las pruebas

| Hilos | Tiempos individuales (s) | Promedio (s) | Duración total (s) | Estimado 100MB (s) |
|:------|:---------------------------|:-------------|:-------------------|:--------------------|
| 1 hilo | 41.85, 42.58, 42.57, 42.35, 41.98 | 42.27 | 187 | 84.53 |
| 2 hilos | 81.19, 81.45, 81.45, 81.5, 42.31 | 73.58 | 157 | 147.16 |
| 4 hilos | 163.84, 164.43, 164.49, 164.51, 42.54 | 139.96 | 225 | 279.92 |


---

## Observaciones y análisis

- El tiempo promedio de procesamiento **aumenta proporcionalmente con el número de hilos**, lo que sugiere una **división de recursos del CPU** más que una ganancia paralela.
- El **quinto video** en cada lote mantiene un tiempo cercano a **42 segundos**, consistente con el rendimiento base de un solo hilo.
- Esto indica que los hilos concurrentes comparten el mismo recurso de CPU y **no hay paralelismo real** (solo concurrencia simulada).
- Posible causa: **lectura/escritura simultánea sobre archivos con el mismo nombre**, generando **bloqueos o esperas de E/S**.
- En el mismo entorno, usar el mismo nombre de archivo podría provocar **sobrescrituras temporales** y retrasos acumulados.

---

## Conclusiones

- Con **1 hilo**, el sistema mantiene una estabilidad de ~42s por video.  
- Con **2 hilos**, el tiempo promedio se **duplica (~81s)**.  
- Con **4 hilos**, el tiempo promedio **se cuadruplica (~164s)**.  
- Esto demuestra que **el CPU de 2 hilos no soporta paralelismo real** para tareas intensivas de E/S.  
- Para mejorar rendimiento se recomienda:
  - Asignar **número de workers <= núcleos físicos del CPU**.
  - Evitar **nombres de archivo idénticos** durante la carga concurrente.

---

## Capturas de ejecución

- Ejecución concurrente

<img width="1146" height="166" alt="imagen" src="https://github.com/user-attachments/assets/534c7895-f1fa-4a51-8740-a4303c80347a" />


- Worker en funcionamiento

<img width="1132" height="467" alt="imagen" src="https://github.com/user-attachments/assets/3c3892c9-2df4-445b-84da-19be4cb9703c" />


---

## Monitoreo de CPU y recursos durante la ejecución

- CPU:

<img width="1744" height="813" alt="imagen" src="https://github.com/user-attachments/assets/476fd107-a05b-4c08-a203-445e5689702f" />

Las pruebas comenzaron desde el tiempo 03:30:21, y acabaron en 03:43:39

| Hilos | Tiempo de inicio | Tiempo de finalización | Duración total (min:seg) |
|:------|:------------------|:------------------------|:--------------------------|
| 1 hilo | 03:30:21 | 03:33:28 | 03:07 |
| 2 hilos | 03:34:51 | 03:37:28 | 02:37 |
| 4 hilos | 03:39:54 | 03:43:39 | 03:45 |

- Network in:

<img width="1752" height="808" alt="imagen" src="https://github.com/user-attachments/assets/3bcbc767-cd4c-4217-8bed-347919aef32e" />

- Network out:
- 
<img width="1750" height="813" alt="imagen" src="https://github.com/user-attachments/assets/78115ead-21aa-49d9-9b11-d5c11d18e541" />

## Resumen general

Estas pruebas confirman que la capacidad de procesamiento del worker está limitada por la cantidad de hilos de CPU y que **la concurrencia sin aislamiento de E/S reduce el rendimiento total**.  
El escalamiento debe evaluarse en una instancia con más núcleos o mediante workers independientes con colas separadas.


