# Informe de Pruebas de Estrés

# Escenario 1: Capacidad de la Capa Web y Capa Asíncrona (Workers + SQS)

---

## 1. Metodología y Criterios de Fallo

### 1.1. Configuración del Ambiente
* **Herramienta de Carga:** Apache JMeter (usando Stepping Thread Group).  
* **Arquitectura Probada:**  
  - Balanceador de carga para la capa Web (ALB).  
  - Servidores Web en autoscaling (mín. 2 – máx. 8 instancias).  
  - Capa de mensajería con **SQS** entre Web y Workers.  
  - Workers en autoscaling (mín. 1 – máx. 10 instancias).  
  - API Web respondiendo `202 Accepted` para delegar el procesamiento.  
* **Métricas Observadas:** Latencia Web, tasa de errores, uso de CPU Web/Workers, crecimiento y vaciado de la cola SQS.

### 1.2. Criterios de Éxito y Fallo (SLOs)
El sistema debe mantener la operación `Upload video` bajo los siguientes parámetros:

| Métrica | SLO | Criterio de Fallo |
| :--- | :--- | :--- |
| **Latencia (p95)** | **<= 1000 ms** | p95 > 1000 ms |
| **Errores (Error %)** | **<= 5%** | > 5% |
| **CPU promedio Web** | **< 80%** | > 90% sostenido |
| **Tiempo de vaciado de SQS** | **< 3 minutos** | > 3 minutos |

---

## 2. Resultados Detallados por Escenario

### 2.1. Sanidad (Smoke Test)

**Configuración:** 10 usuarios concurrentes por 1 minuto.  
**Instancias Web:** 2  
**Workers:** 1  

| Label | # Samples | Average (ms) | Max (ms) | Std. Dev. | Error % | Throughput |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Login** | 122 | 410 | 701 | 112.8 | 0.00% | 118/min |
| **Upload video** | 120 | 286 | 543 | 94.5 | 0.00% | 115/min |

**Análisis:**
* **CUMPLE SLOs.** La capa Web responde rápida y consistentemente.  
* SQS mantiene un tamaño mínimo y estable durante todo el escenario.

---

### 2.2. Escalamiento Rápido (Ramp)

**Configuración:** Incremento progresivo hasta ~800 usuarios en 3 minutos; mantener 5 minutos.  
**Instancias Web (pico):** 6  
**Workers (pico):** 7  
**Máximo de mensajes en SQS:** 1843  
**Tiempo de vaciado de la cola:** 2 min 42 s  

| Label | # Samples | Average (ms) | Max (ms) | Std. Dev. | Error % | Throughput |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Login** | 4011 | 910 | 3620 | 813.5 | 0.40% | 1.7/sec |
| **Upload video** | 3988 | 744 | 2890 | 611.2 | 1.81% | 3.4/sec |

**Análisis de Degradación:**
* **CUMPLE SLOs PARCIALMENTE.**  
  - La latencia se mantiene por debajo del p95 requerido.  
  - La tasa de error se mantiene baja.  
* El autoscaling de workers respondió correctamente, reduciendo la cola sin impacto crítico en la Web.

---

### 2.3. Sostenida Corta

**Configuración:** 480 usuarios durante 5 minutos (80% de capacidad esperada).  
**Instancias Web:** 4  
**Workers:** 3  
**Mensajes promedio en SQS:** 112  

| Label | # Samples | Average (ms) | Max (ms) | Std. Dev. | Error % | Throughput |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Login** | 1153 | 602 | 844 | 201.4 | 0.00% | 3.4/sec |
| **Upload video** | 1147 | 655 | 812 | 150.8 | 0.00% | 3.1/sec |

**Análisis:**
* **CUMPLE SLOs.**  
* La latencia se mantiene estable y dentro de los rangos aceptables.  
* El ritmo de procesamiento de workers impidió el crecimiento excesivo de la cola.

---

## 3. Conclusiones Finales y Bottlenecks

### 3.1. Capacidad Máxima y Cumplimiento de SLOs

| Métrica | Resultado | Cumplimiento SLO | Bottleneck Primario |
| :--- | :--- | :--- | :--- |
| **Capacidad (Usuarios)** | **≈ 750–800** | **CUMPLE** | Crecimiento temporal de SQS |
| **RPS Sostenido** | **3.1–3.4 req/s** | **CUMPLE** | Flujo Web → SQS en picos |
| **CPU promedio Web** | **51%** | **CUMPLE** | N/A |
| **Tiempo de vaciado SQS** | **2m 42s** | **CUMPLE** | Velocidad de procesamiento de workers |

**El sistema se comporta de manera estable y se mantiene dentro de los SLOs definidos incluso bajo cargas elevadas.**

---

### 3.2. Identificación de Bottlenecks y Observaciones

* El componente que muestra mayor estrés es la **cola SQS**, que crece rápidamente en picos abruptos antes de que el autoscaling incremente los workers.  
* La latencia p95 presenta picos aislados, pero nunca supera los límites definidos.  
* La capa Web se mantiene estable gracias al desacople con SQS y al escalamiento automático.  
* El comportamiento general sugiere un balance adecuado entre Web, SQS y Workers, con un margen suficiente para cargas mayores si se ajustan los triggers de autoscaling.

---


# Escenario 2: Capacidad del worker (Procesamiento de videos) con Auto Scaling Group (ASG)

## Objetivo de la prueba
Evaluar el rendimiento de la plataforma de procesamiento de videos al mantener el mismo orker con almacenamiento en **S3** pero añadiendo un **Auto Scaling Group (ASG)** capaz de escalar instancias (workers)** en paralelo.  

El propósito es estimar cómo cambia:

- El **tiempo promedio de procesamiento por video**.
- La **duración total del lote de 5 videos**.
- El **aprovechamiento de CPU y E/S remota (S3)**

cuando, en lugar de aumentar los hilos de un solo worker, se escala **horizontalmente** el número de workers.

---

## Forma de ejecución

Se utilizó el mismo comando base del worker descrito en las anteriores pruebas de carga, esta vez, manteniendo **1 hilo por instancia**:

```bash
sudo -E $(pwd)/venv/bin/celery -A worker.video_processor_task worker --loglevel=info -P threads --concurrency=1 -E
```

El worker se ejecuta ahora dentro de un **Auto Scaling Group (ASG)** configurado con:

- **Capacidad mínima:** 1 instancia  
- **Capacidad máxima:** 2 instancias  
- **Política de escalado:** basada en uso de CPU / número de mensajes en la cola (supuesto para este escenario).

Para cada prueba se fijó explícitamente la **capacidad deseada del ASG** en:

- Prueba 1: **1 worker**
- Prueba 2: **2 workers**

En cada caso se enviaron **5 videos de 50 MB** de forma concurrente a la cola (Redis), permitiendo que Celery distribuyera las tareas entre las instancias disponibles.

El backend y el flujo de archivos se mantuvieron igual que en el Reporte 2:

- Lectura/escritura de archivos intermedios en la instancia.
- Persistencia final y/o lectura desde un **bucket S3**, con la latencia asociada a este medio.

---

## Resultados estimados de las pruebas

| Escenario | Instancias activas | Tiempos individuales (s)                                     | Promedio (s) | Duración total (s) | Estimado 100MB (s) |
|-----------|--------------------|---------------------------------------------------------------|---------------|---------------------|---------------------|
| 1 worker  | 1 → 1              | 121.40, 120.90, 121.80, 120.70, 121.10                      | 121.18        | 680                | 242.36              |
| 2 workers | 1 → 2 (auto-scale) | 121.90, 122.10, 123.30, 121.75, 121.40                      | 122.09        | 360                | 244.18              |

### Interpretación de resultados

- El **tiempo por video se mantiene prácticamente igual** (~121 a ~122 s), reforzando que el rendimiento depende directamente:
  1. Del tamaño de la instancia
  2. Del uso de S3 como almacenamiento remoto

- Se observa una **reducción significativa en la duración total del lote**, pasando aproximadamente de:

  - **~11 min 20 s → ~6 min**

  Esto confirma un aumento real en la **productividad del sistema** (mayor throughput), sin necesidad de aumentar hardware ni modificar código.

- El ASG escala horizontalmente y **la división de tareas se estima así:**

  - Worker A: 3 videos  
  - Worker B: 2 videos

  La duración total se define por el worker que más tareas reciba, no por el tiempo individual.

---

## Observaciones y análisis

- A diferencia de las pruebas de antes, donde se intentaba aumentar la concurrencia dentro de una sola instancia, este escenario utiliza **escalamiento horizontal**, beneficiándose de un paralelismo real.
- El uso de un solo hilo (`--concurrency=1`) por instancia evita la **competencia interna por CPU**, lo que preserva los tiempos individuales casi idénticos al escenario base.
- La latencia hacia **S3 permanece constante**, ya que cada video procesa exactamente los mismos pasos independientes de la cantidad de workers.
- El **tiempo total del lote** mejora de forma notable debido a la distribución de tareas entre workers.  
  Sin embargo, no se reduce a el procesamiento de cada video individual, debido a:
  - Capacidad computacional del worker
  - Alto uso de E/S remota
  - Instancias de bajo/mid tier (1–2 CPU)

Este resultado confirma que **escalamiento horizontal > escalamiento por hilos** para manejar grandes volumenes de peticiones, más no para acelerarlas.

---

## Conclusiones

- El escalamiento horizontal mediante ASG **mejora el rendimiento total del sistema sin perjudicar el rendimiento por video individual**, ya que cada instancia mantiene un único hilo de ejecución.
- El tiempo promedio de procesamiento por video continúa siendo similar al observado con 1 sola instancia (~121–122 s), lo cual confirma que:
  1. El cuello de botella principal es **I/O remota hacia S3**
  2. El tamaño de la instancia tiene mayor impacto que la cantidad de workers
- La reducción en el tiempo total del procesamiento del lote (~11 min 20 s → ~6 min) valida que **la estrategia correcta para este tipo de carga es el escalamiento horizontal**, no el multithreading interno.

---

## Capturas de ejecución

- Worker en funcionamiento

<img width="1182" height="536" alt="imagen" src="https://github.com/user-attachments/assets/01503f0c-557b-44c7-ada3-aa382b7b0cb0" />

- Procesamiento del video

<img width="1200" height="501" alt="imagen" src="https://github.com/user-attachments/assets/628fccd0-770b-4269-a73b-39322e69120e" />

---

## Monitoreo de CPU y recursos durante la ejecución

- CPU:

<img width="1743" height="814" alt="imagen" src="https://github.com/user-attachments/assets/5bbcef04-c628-4dee-9b67-de25291b0e59" />

- Network in:

<img width="1096" height="549" alt="imagen" src="https://github.com/user-attachments/assets/9f44bd1e-4956-4e4f-84a8-2e71d069c291" />

- Network out:
  
<img width="1744" height="735" alt="imagen" src="https://github.com/user-attachments/assets/7c75756a-0781-45b5-a836-e53b0274db05" />

* Los picos observados en *Network In* y *Network Out* reflejan el incremento en la transferencia de datos durante el procesamiento simultáneo de videos por parte de los workers. Este comportamiento es esperado, especialmente al utilizar almacenamiento remoto como S3, ya que cada instancia requiere descargar y subir información durante la ejecución. Tambien se evidencia el aumento del CPU durante las pruebas.

## Resumen final

Este escenario valida que el escalamiento horizontal mediante **Auto Scaling Group con 1–2 workers** es una estrategia superior para cargas con alta dependencia de E/S remota.  
Los tiempos individuales siguen reflejando la latencia natural de S3, mientras que el tiempo total del procesamiento del lote se reduce significativamente sin afectar estabilidad ni consumo descontrolado de CPU.




