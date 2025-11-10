# Diagrama de despliegue

<img src="https://github.com/user-attachments/assets/d3afa459-f3ad-4eb7-a786-7df750e1f88a" style="max-width:100%; height:auto;" alt="imagen" />

---

La arquitectura propuesta despliega la aplicación en Amazon Web Services (AWS) dentro de una VPC que integra los servicios requeridos para la escalabilidad de la capa web.
El tráfico proveniente de los clientes (usuarios o Postman) llega al Application Load Balancer (ALB), que distribuye las solicitudes hacia un Auto Scaling Group con hasta tres instancias EC2 configuradas con Nginx y FastAPI, garantizando la disponibilidad y el balanceo de carga de la API REST.

Los archivos de video se almacenan en Amazon S3, reemplazando el uso de NFS y permitiendo un acceso escalable y de bajo costo. El procesamiento asíncrono de videos se maneja mediante una instancia EC2 Worker con Redis, que actúa como cola de mensajes para coordinar tareas entre los web servers y el worker.

La capa de datos está soportada por Amazon RDS (PostgreSQL), que almacena la información de usuarios, videos y votos. El monitoreo y la gestión del escalamiento automático se realizan a través de Amazon CloudWatch, que recopila métricas de las instancias EC2 y ajusta la capacidad del Auto Scaling Group según la demanda.

En conjunto, esta arquitectura garantiza escalabilidad, balanceo de carga, procesamiento asíncrono y almacenamiento distribuido, cumpliendo con los requerimientos establecidos para la Entrega 3 del proyecto.

# Migración del almacenamiento NFS a S3

## 1. Objetivo de la migración

El objetivo de esta tarea fue reemplazar el almacenamiento local de videos (ubicado en `videos/unprocessed-videos` y `videos/processed-videos`) por un sistema basado en Amazon S3. 

Esta migración permite eliminar la dependencia del sistema de archivos compartido (NFS), mejorar la escalabilidad y facilitar que tanto el backend FastAPI como el worker Celery compartan archivos a través de S3, sin requerir volúmenes físicos comunes.

---

## 2. Cambios implementados

### a) Creación del módulo de utilidades S3 (`src/utils/s3_utils.py`)

Se creó un nuevo módulo para manejar todas las operaciones con AWS S3 utilizando la librería boto3.

El archivo `src/utils/s3_utils.py` define:

- `upload_to_s3(local_path, s3_key)`: sube un archivo local al bucket S3.
- `download_from_s3(s3_key, local_path)`: descarga un archivo desde S3.
- `delete_from_s3(s3_key)`: elimina un objeto del bucket S3.
- La constante `BUCKET_NAME`, que se obtiene desde la variable de entorno `S3_BUCKET`.

También se configuró un cliente global de boto3 (`s3_client = boto3.client("s3")`) y un logger para registrar las operaciones.

---

### b) Modificación del router de videos (`src/routers/videos_router.py`)

El router de FastAPI fue actualizado para usar el nuevo módulo de S3. 

Principales cambios:
- Se eliminaron las referencias a directorios locales (`UPLOAD_DIR` y `PROCESSED_DIR`).
- Se validan los videos localmente (tipo, tamaño, duración y resolución) y luego se suben a S3 usando `upload_to_s3()`.
- Se elimina el archivo temporal local después de la subida exitosa.
- Se actualizó el campo `processed_url` para construir la URL pública en S3.
- Se mantuvo la lógica de validación de duración y resolución mediante `pymediainfo`.

---

### c) Modificación del worker Celery (`worker/video_processor_task.py`)

El worker ahora utiliza el almacenamiento en S3 durante todo el flujo de procesamiento.

Flujo del worker:
1. Descarga el video original desde S3 mediante `download_from_s3()`.
2. Procesa el video usando FFmpeg (recorte, escalado, concatenación con watermark, normalización).
3. Sube el resultado procesado nuevamente al bucket S3 con `upload_to_s3()`.
4. Elimina los archivos locales temporales (`source`, `tmp`, `destination`).
5. Actualiza el estado del video en la base de datos a `processed`.

De esta forma, los workers no necesitan acceso directo al sistema de archivos del backend, solo las credenciales de AWS.

---
