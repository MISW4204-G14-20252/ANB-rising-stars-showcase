# Pruebas de Carga

En la carpeta `docs` del repositorio se encuentra el archivo **`LoadTest.jmx`**, el cual contiene la configuración completa del plan de pruebas en **Apache JMeter**.  
Este archivo define todos los **Thread Groups**, **HTTP Samplers**, **Header Managers**, **Post Processors** y **Listeners** necesarios para ejecutar pruebas de carga sobre los distintos endpoints expuestos por la aplicación.

Para el presente análisis se seleccionó el **endpoint de carga de videos (`/api/videos/upload`)**, dado que es el más exigente en términos de uso de recursos y el que potencialmente puede generar **cuellos de botella** a nivel de red, procesamiento de archivos y acceso a disco.


## Configuración de la prueba

- **Número de hilos (usuarios simultáneos):** 22  
- **Tiempo de ramp-up:** 20 segundos  
- **Duración:** hasta completar todas las solicitudes configuradas  
- **Tipo de contenido:** `multipart/form-data` (subida de video y metadatos como el título)  
- **Autenticación:** mediante token JWT extraído dinámicamente tras el login  
- **Archivo cargado:** video MP4 de prueba (≈ 3 MB)  
- **Servidor:** `localhost:8000` (FastAPI + PostgreSQL + Redis)  
- **Equipo de prueba:**  
  - **Procesador:** Intel Core i9-12900  
  - **Memoria RAM:** 32 GB  
  - **Sistema operativo:** Windows 11  


## Resultados obtenidos

### Escenario 1 — 22 usuarios simultáneos

| Métrica | Valor |
|:--|:--|
| **# de Samples** | 22 |
| **Promedio (ms)** | 499 |
| **Min (ms)** | 349 |
| **Max (ms)** | 532 |
| **Std Dev (ms)** | 52.62 |
| **Errores (%)** | 0.00 |
| **Throughput** | 3.6/min |
| **KB/sec enviados** | 10,767.85 |

### Escenario 2 — 100 usuarios simultáneos

| Métrica | Valor |
|:--|:--|
| **# de Samples** | 122 |
| **Promedio (ms)** | 1507 |
| **Min (ms)** | 575 |
| **Max (ms)** | 9495 |
| **Std Dev (ms)** | 6016.8 |
| **Errores (%)** | 6.56 |
| **Throughput** | 2.1/min |
| **KB/sec enviados** | 10,084.32 |

## Interpretación de los resultados

El primer escenario (22 usuarios) mostró **rendimiento estable y sin errores**, con una latencia promedio inferior a 0.5 segundos, lo que indica un sistema con **buen desempeño bajo carga moderada**.  

Sin embargo, al aumentar la concurrencia a **100 usuarios**, se observó un **incremento notable en la latencia promedio (≈ 1.5 s)** y una **variabilidad alta** (desviación estándar de 6 s), junto con una **tasa de error del 6.56%**.  
El throughput cayó de 3.6 a 2.1 solicitudes/minuto, lo que evidencia **saturación del servidor** y posibles cuellos de botella en el manejo de archivos concurrentes o acceso a la base de datos.


## Posibles cuellos de botella

1. **Límites de concurrencia del servidor FastAPI o del pool de conexiones a PostgreSQL.**   
2. **Sobrecarga de CPU o disco** debido al manejo simultáneo de multipart/form-data.  

---

## Recomendaciones y mejoras

- Ajustar el **pool de conexiones** y los límites de concurrencia de Uvicorn/Gunicorn.  
- Utilizar un **sistema de almacenamiento distribuido o cacheado** para las cargas de video.  
- Escalar horizontalmente la aplicación (balanceador de carga con múltiples instancias).  
- Monitorear el uso de CPU, RAM y disco durante las pruebas para identificar el componente más saturado.  
