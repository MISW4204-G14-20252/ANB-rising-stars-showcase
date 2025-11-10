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

# Escenario 2: Capacidad del worker (Procesamiento de videos)

## Objetivo de la prueba
Evaluar el rendimiento del worker encargado del procesamiento de videos al variar la cantidad de **hilos de ejecución (threads)**.  
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
| 1 hilo | 121.16, 121.22, 120.69, 121.48, 120.55 | 121.02 | 924 | 242.04 |
| 2 hilos | 221.79, 246.07, 245.62, 246.65, 145.14 | 221.05 | 1085 | 442.10 |
| 4 hilos | 431.28, 436.77, 439.12, 438.45, 182.84 | 385.69 | 1398 | 771.38 |

---

## Observaciones y análisis

- El tiempo promedio de procesamiento **aumenta con el número de hilos**, lo que sugiere una **competencia por recursos del CPU** más que una ganancia paralela real.
- El **quinto video** en cada lote presenta un tiempo mucho menor (en torno a 120–180 s), consistente con el rendimiento base del sistema bajo baja carga.
- Los resultados confirman que los hilos concurrentes **comparten el mismo recurso físico**, sin paralelismo efectivo en las tareas de procesamiento pesado.
- Esto puede deberse a que las operaciones se realizan sobre **archivos compartidos** o **rutas comunes**, generando **bloqueos o esperas de E/S**.
- En pruebas anteriores, cuando se empleaba almacenamiento NFS en lugar de S3, se observó **mayor sincronización entre procesos de lectura y escritura**, lo que se traducía en menores tiempos en escenarios concurrentes.
- En contraste, el uso de un **bucket S3 introduce mayor latencia** al añadir una capa de persistencia remota.

---

## Conclusiones

- Con **1 hilo**, el sistema mantiene una estabilidad media de **~121 s por video**, representando el comportamiento óptimo del entorno.  
- Con **2 hilos**, el tiempo promedio **casi se duplica (~221 s)**, lo que refleja una pérdida de eficiencia por saturación de CPU y E/S.  
- Con **4 hilos**, el tiempo promedio **se triplica (~386 s)**, demostrando que **no existe paralelismo real** y que el hardware o la configuración actual no soportan la carga concurrente.  
- Estos resultados demuestran que:
  - El CPU físico tiene **capacidad limitada para concurrencia intensiva**.
  - Las tareas son predominantemente **bloqueadas por I/O** (lectura, escritura o carga en S3).
- Para mejorar el rendimiento se recomienda:
  - Asignar **número de workers menor o igual al número de núcleos físicos del CPU**.
  - Evitar **nombres de archivo idénticos o rutas compartidas** durante ejecuciones simultáneas.
  - Optimizar la **persistencia remota (S3)**, o preferir un almacenamiento local (NFS) para reducir latencia en pruebas de carga.

---

## Capturas de ejecución

- Ejecución concurrente

<img width="1146" height="166" alt="imagen" src="https://github.com/user-attachments/assets/534c7895-f1fa-4a51-8740-a4303c80347a" />

- Worker en funcionamiento

<img width="1182" height="536" alt="imagen" src="https://github.com/user-attachments/assets/01503f0c-557b-44c7-ada3-aa382b7b0cb0" />

- Procesamiento del video

<img width="1200" height="501" alt="imagen" src="https://github.com/user-attachments/assets/628fccd0-770b-4269-a73b-39322e69120e" />

---

## Monitoreo de CPU y recursos durante la ejecución

- CPU:

<img width="1743" height="814" alt="imagen" src="https://github.com/user-attachments/assets/5bbcef04-c628-4dee-9b67-de25291b0e59" />

Las pruebas comenzaron desde el tiempo **06:18:29** y finalizaron a las **07:03:19**.

| Hilos | Tiempo de inicio | Tiempo de finalización | Duración total (min:seg) |
|:------|:------------------|:------------------------|:--------------------------|
| 1 hilo | 06:18:29 | 06:33:53 | 15:24 |
| 2 hilos | 06:36:18 | 06:54:23 | 18:05 |
| 4 hilos | 06:56:01 | 07:03:19 | 07:18 |

- Network in:

<img width="1096" height="549" alt="imagen" src="https://github.com/user-attachments/assets/9f44bd1e-4956-4e4f-84a8-2e71d069c291" />

- Network out:
  
<img width="1744" height="735" alt="imagen" src="https://github.com/user-attachments/assets/7c75756a-0781-45b5-a836-e53b0274db05" />

## Resumen general

Estas pruebas confirman que la capacidad de procesamiento del worker está limitada por la cantidad de hilos de CPU del worker y que **la concurrencia sin aislamiento de E/S reduce el rendimiento total**.
Frente a los cambios de las primeras pruebas, hubo un aumento del tiempo al añadir el bucket S3 para la carga de archivos.
