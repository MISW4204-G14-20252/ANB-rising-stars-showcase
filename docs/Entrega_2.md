## Documentación

# Resumen de correcciones solicitadas por SonarQube

Este documento resume los cambios que aplicamos en el repositorio para abordar las advertencias/bugs reportados por SonarQube. Incluye el mapeo de issues, los archivos modificados, cómo verificar localmente y recomendaciones posteriores.

## Objetivos

- Evitar construcción de rutas a partir de datos controlados por el usuario (path traversal / filename injection).
- Eliminar funciones `async` que no usan `await`.
- Evitar I/O síncrono dentro de funciones `async`.
- No comparar floats con igualdad exacta.
- Usar la API `Path` y `unlink()` en lugar de `os.remove()` cuando estemos trabajando con objetos `Path`.

---

## Cambios aplicados (lista detallada)

### `src/routers/videos_router.py`
- Generación de nombre de archivo seguro:
  - Antes: `unique_name = f"{uuid4()}_{video_file.filename}"` (construía parte del nombre a partir del filename del usuario).
  - Ahora: se usa sólo la extensión del archivo y un identificador seguro: `unique_name = f"{uuid4().hex}{ext}"`.
  - Esto evita inyección de rutas y problemas con caracteres inesperados en `video_file.filename`.
- Validación explícita de extensión `.mp4` (se valida `Path(video_file.filename).suffix.lower()`).
- Escritura asíncrona del archivo con `aiofiles` dentro de la función `async` (se reutiliza el `contents` previamente leído para validar tamaño):
  - `async with aiofiles.open(file_path, "wb") as out_f: await out_f.write(contents)`.
  - Se añadió `aiofiles` a `requirements.txt`.
- Reemplazo de `os.remove(...)` por `Path.unlink()` con `try/except` donde correspondía para consistencia y robustez.
- Evitar comparación exacta de floats: `if dur == 0.0:` -> `if dur <= 0.0:`.

### `src/routers/auth_router.py`
- `verify_token` y `get_current_user` pasaron de `async def` a `def` porque no usan `await`.
- Esto evita advertencias de funciones `async` sin `await` y simplifica consumo en tests y dependencias.

### `tests/api/test_auth_endpoints.py`
- Actualizadas las pruebas que llamaban `await verify_token(...)` y `await get_current_user(...)` para invocarlas sin `await`.
- Se eliminó `pytest.mark.asyncio` en las pruebas afectadas.

### `requirements.txt`
- Añadido `aiofiles==23.1.0` para soportar la escritura asíncrona en `upload_video`.

---

## Mapeo de issues Sonar (resumen)

- No construir rutas a partir de datos controlados por el usuario  
  - **Archivo:** `src/routers/videos_router.py`  
  - **Acción:** Generar un nombre seguro (UUID) y conservar únicamente la extensión; no utilizar el nombre completo del archivo proporcionado por el usuario.  

- Usar una API de archivos asíncrona en lugar de `open()` sincrónico dentro de una función `async`  
  - **Archivo:** `src/routers/videos_router.py`  
  - **Acción:** Reemplazar `open(...)` por `aiofiles.open(...)` y realizar las operaciones de escritura de forma asíncrona.  

- No realizar comparaciones de igualdad con valores de punto flotante  
  - **Archivo:** `src/routers/videos_router.py`  
  - **Acción:** Cambiar `if dur == 0.0` por `if dur <= 0.0`.  

- Las funciones declaradas como `async` deben usar `await`  
  - **Archivo:** `src/routers/auth_router.py`  
  - **Acción:** Convertir las funciones a síncronas cuando no utilicen `await`.  

- No mezclar `os.remove` con objetos `Path`  
  - **Archivo:** `src/routers/videos_router.py`  
  - **Acción:** Utilizar `Path.unlink()` y manejar los posibles errores mediante un bloque `try/except`.  

---

## Verificación y pruebas

- Se ejecutó la suite de tests en el contenedor de desarrollo del proyecto (Docker Compose `docker-compose.dev.yaml`). Resultado de la última ejecución:
  - Tests: `34 passed`
  - Warnings: 8 (deprecations relacionados con pydantic/SQLAlchemy, no relacionados con los fixes)
  - Coverage global: `~91%`

## Diagrama de Componentes
<img src="https://github.com/user-attachments/assets/5ecebf31-26ff-4136-b037-c0a41c4266f7" style="max-width:100%; height:auto;" alt="imagen" />


## Diagrama de Despliegue
<img src="https://github.com/user-attachments/assets/57926150-ad65-4f0c-819c-a857f18aa91f" style="max-width:100%; height:auto;" alt="imagen" />

## Despliegue en AWS

Durante esta entrega se desplegaron los componentes principales de la aplicación en la nube pública de AWS, siguiendo el modelo de referencia propuesto. En total se configuraron y ejecutaron seis servicios: un worker, un servidor NFS, una API REST, un servidor web Nginx, un servidor Redis y una base de datos en Amazon RDS. Todos los servicios fueron desplegados sobre instancias de Amazon EC2 y aislados dentro de una misma VPC, lo que permitió establecer un entorno controlado y seguro para la comunicación entre los diferentes componentes. Asimismo, se configuraron las reglas de ingreso y egreso del firewall (Security Groups) para permitir el tráfico necesario entre las máquinas virtuales, garantizando así la protección de los servicios expuestos.

Para esta fase se optó por instalar directamente los servicios en las máquinas virtuales, sin utilizar contenedores Docker, con el objetivo de tener un mayor control sobre el entorno de configuración inicial. Sin embargo, se identificó que este enfoque ralentiza la replicabilidad y la puesta en marcha de nuevos entornos, por lo que se decidió que, para futuras entregas, se adoptará un esquema basado en contenedores Docker. De esta forma, se instalará Docker en cada instancia EC2 y se ejecutará el servicio correspondiente mediante archivos docker-compose.yml, simplificando el despliegue y asegurando la consistencia entre entornos.

Para optimizar este proceso, se planea generar una plantilla (AMI) de máquina virtual con Docker preinstalado y configurado, a partir de la cual se podrán lanzar nuevas instancias que solo requerirán ejecutar el comando `docker compose up -d [componente]` para levantar el servicio deseado. Este cambio permitirá una gestión más ágil del ciclo de vida de los servicios, una mejor reproducibilidad de los entornos y una reducción significativa en los tiempos de aprovisionamiento y despliegue.

### Sobre los servicios utilizados

Para esta entrega se utilizaron los siguientes servicios en la nube:
- Amazon EC2 para la ejecución del servidor web, el worker y el servidor NFS
- Amazon RDS para la gestión de la base de datos relacional
- Amazon VPC para el aislamiento y la comunicación segura entre las instancias
