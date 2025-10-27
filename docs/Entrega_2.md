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

- Do not construct paths from user-controlled data
  - Archivo: `src/routers/videos_router.py`
  - Acción: Generar nombre seguro (UUID) y usar sólo la extensión; no usar el filename entero del usuario.

- Use an asynchronous file API instead of synchronous open() in this async function
  - Archivo: `src/routers/videos_router.py`
  - Acción: reemplazar `open(...)` por `aiofiles.open(...)` y escribir de forma asíncrona.

- Do not perform equality checks with floating point values
  - Archivo: `src/routers/videos_router.py`
  - Acción: `if dur == 0.0` -> `if dur <= 0.0`.

- Functions declared async should use await
  - Archivo: `src/routers/auth_router.py`
  - Acción: Convertir funciones a síncronas cuando no usan `await`.

- Do not mix `os.remove` with `Path` objects
  - Archivo: `src/routers/videos_router.py`
  - Acción: usar `Path.unlink()` y manejar errores con try/except.

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

