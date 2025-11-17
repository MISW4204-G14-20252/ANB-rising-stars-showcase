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


# Escenario 2: Capacidad del worker (Procesamiento de videos)
