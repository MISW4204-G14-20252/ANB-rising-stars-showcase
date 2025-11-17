## Diagrama de componentes

![Diagrama de Componentes - Página 3](https://github.com/user-attachments/assets/f23f3e8e-6058-477a-964c-4ba29e53ab5c)

#  Integración de Amazon SQS para Procesamiento Asíncrono de Videos

Este documento describe los cambios realizados tanto en el **router de videos (FastAPI)** como en el **worker de procesamiento**, con el objetivo de implementar una arquitectura asíncrona basada en **Amazon SQS**.

La nueva arquitectura desacopla la subida de videos y su procesamiento, permitiendo **escalabilidad**, **tolerancia a fallos** y **procesamiento distribuido**.

---

# 1. Cambios en el Video Router (`src/routers`)

El router ahora cumple dos responsabilidades:

-  **Subir el video validado a S3**
-  **Encolar la tarea de procesamiento en Amazon SQS**

##  Cambio 1 — Se importa `send_to_sqs`  
```python
from src.utils.sqs_utils import send_to_sqs
```

Esto permite enviar mensajes a la cola después de guardar un video en la base de datos.

---

##  Cambio 2 — Se construye un diccionario serializable del video
```python
video_dict = new_video.to_dict()
```

Esto contiene:

- id  
- filename (ruta S3)  
- title  
- user_id / owner_id  
- timestamps  
- estado  

El worker lo recibirá y procesará en segundo plano.

---

##  Cambio 3 — Envío del mensaje a SQS
```python
sent = send_to_sqs(video_dict)

if not sent:
    logger.error("No se pudo encolar la tarea en SQS.")
    return {
        "message": "Error encolando tarea de procesamiento.",
        "task_id": new_video.id,
        "status": "error"
    }
```

Si SQS falla, el sistema devuelve error al usuario.

---

##  Cambio 4 — Respuesta indicando procesamiento asíncrono
```python
return {
    "message": "Video subido correctamente. Procesamiento en curso.",
    "task_id": new_video.id,
}
```

El cliente **ya no recibe un video procesado inmediatamente**, sino que lo consulta después con `/api/videos/{id}`.

---

# 2. Cambios en el Worker (`video_processor_task.py`)

El worker ahora es un proceso autónomo que:

-  **Escucha la cola SQS**
-  **Procesa videos**
-  **Sube resultados a S3**
-  **Actualiza la base de datos**
-  **Elimina el mensaje de SQS**

---

##  Cambio 1 — Se importan funciones de SQS

```python
from src.utils.sqs_utils import receive_from_sqs, delete_from_sqs
```

---

##  Cambio 2 — Se agrega un loop principal que escucha SQS

```python
def run_sqs_worker(poll_interval=10):
    logger.info("Iniciando worker de procesamiento de videos (SQS)...")

    while True:
        messages = receive_from_sqs(max_messages=1, wait_time=10)
        if not messages:
            time.sleep(poll_interval)
            continue

        for msg in messages:
            body = msg.get("Body")
            video_data = json.loads(body)

            result = process_video(video_data)

            delete_from_sqs(msg["ReceiptHandle"])
```

### Este loop:

- Permite escalar horizontalmente (más workers = más throughput)
- Evita reprocesar videos borrando el mensaje
- Soporta fallos del worker (SQS vuelve a entregar mensajes invisibles)

---

##  Cambio 3 — Cada mensaje recibido se procesa con `process_video()`

```python
result = process_video(video_data)
```

---

##  Cambio 4 — Manejo de errores robusto

- JSON malformado → se elimina mensaje  
- Video inexistente en S3 → logueado  
- FFmpeg falla → captura `CalledProcessError`  
- Error general → log y continuar  

---

##  Cambio 5 — Worker ejecutable directamente

```python
if __name__ == "__main__":
    run_sqs_worker()
```


---

# 3. Beneficios de la Integración SQS

| Beneficio | Explicación |
|----------|-------------|
| **Escalamiento automático** | El número de mensajes en SQS puede activar AWS Auto Scaling. |
| **Desacoplamiento total** | FastAPI no procesa videos; solo delega. |
| **Alta disponibilidad** | Si un worker muere, otro retoma el mensaje. |
| **Evita reprocesamiento** | Gracias a `delete_from_sqs` + long polling. |
| **Mejor manejo de carga** | Los workers procesan a su ritmo sin saturar al backend. |

---

# 4. Conclusión

Los cambios implementados permiten una arquitectura moderna y escalable:

- FastAPI produce mensajes
- SQS actúa como buffer confiable
- Los workers EC2 procesan videos de forma distribuida
- La infraestructura puede escalar automáticamente según la carga

Esta base soporta desde 10 hasta miles de videos por hora según la cantidad de workers desplegados.


