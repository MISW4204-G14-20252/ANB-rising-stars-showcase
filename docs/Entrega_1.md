# Documentación

## 1. Diseño e implementación de la API RESTful

- Los endpoints necesarios para el login se implementarón en [https://github.com/MISW4204-G14-20252/ANB-rising-stars-showcase/blob/main/src/routers/auth_router.py](https://github.com/MISW4204-G14-20252/ANB-rising-stars-showcase/blob/main/src/routers/auth_router.py).
- Los endpoints necesarios para el procesamiento de videos se implementarón en [https://github.com/MISW4204-G14-20252/ANB-rising-stars-showcase/blob/main/src/routers/videos_router.py](https://github.com/MISW4204-G14-20252/ANB-rising-stars-showcase/blob/main/src/routers/videos_router.py)
- Los endpoints necesarios para el público y el ranking están en [https://github.com/MISW4204-G14-20252/ANB-rising-stars-showcase/blob/main/src/routers/public_router.py](https://github.com/MISW4204-G14-20252/ANB-rising-stars-showcase/blob/main/src/routers/public_router.py)

## 2. Autenticación y seguridad

En este archivo de rutas se encuentra la implementación para la autenticación y seguridad [https://github.com/MISW4204-G14-20252/ANB-rising-stars-showcase/blob/main/src/routers/auth_router.py](https://github.com/MISW4204-G14-20252/ANB-rising-stars-showcase/blob/main/src/routers/auth_router.py). En este mismo se genera el token y se proveen los endpoints para iniciar sesión y crear una cuenta. 

Para la protección de los endpoints utilizamos la siguiente función, la cual devuelve un error si el usuario no se encuentra autenticado. 

```python
def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    """
    Decodifica el token JWT y devuelve el usuario autenticado.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciales de autenticación inválidas.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.query(Usuario).filter(Usuario.email == username).first()
    if user is None:
        raise credentials_exception

    return user
```

## 3. Procesamiento asíncrono de tareas

El broker de mensajería seleccionado fue Redis ya que nos permitió como grupo continuar con lo desarrollado por el tutorial. En cuando al monitoreo de tareas asíncronas se definió que el worker hiciera `logging.info(...)` en todas las partes del proceso con el fin de saber el estado de las tareas. Al finalizar la tarea se deja una métrica sobre el tiempo total que demoró el procesamiento del video. 

En cuanto a la consideración de utilizar Kafka al equipo le gusto la idea, sin embargo, dado el poco conocimiento que teniamos utilizando este mismo preferimos utilizar el que se nos compartió en el tutorial. 

## 4. Gestión y almacenamiento de archivos

Los videos una vez se envian mediante una petición al backend son almacenados en una carpeta en el sistema de archivos donde se ejecuta la aplicación (`videos/`). Inicialmente se guarda en una subcarpeta `videos/unprocessed-videos/` con un nombre aleatorio generado por un UUID, luego se deja el mensaje en la cola y se procesa utilizando FFmpeg. Una vez se procesa todo el archivo se almacena el mismo en otra subcarpeta llamada `videos/processed-videos/` y se borra el archivo que inicialmente se subió desde la API. 

## 5. Despliegue y ejecución

Se construyeron 2 imagenes a partir de archivo Docker: una para el [worker](https://github.com/MISW4204-G14-20252/ANB-rising-stars-showcase/blob/main/Dockerfile.worker) y otra para el [backend](https://github.com/MISW4204-G14-20252/ANB-rising-stars-showcase/blob/main/Dockerfile). Estos archivos de Docker se utilizan en el archivo [`docker-compose.yaml`](https://github.com/MISW4204-G14-20252/ANB-rising-stars-showcase/blob/main/docker-compose.yaml), este mismo se utiliza para ejecutar todos los servicios requeridos para la aplicación. 

Para configurar Nginx se definió un servicio en el `docker-compose.yaml` y se realizo un volumen para utilizar el archivo [`nginx.conf`](https://github.com/MISW4204-G14-20252/ANB-rising-stars-showcase/blob/main/nginx.conf), el cual se define en el sistema de archivos de la maquina que hospeda Docker, junto al contenedor de Nginx. 

## 6. Documentación

## Modelo de datos

<img alt="image" src="https://github.com/user-attachments/assets/ef6836b8-b2c5-4acf-8213-2e3c10e3e156" />

## Documentación de la API

La documentación de la API completa se encuentra en una colección en [`collections/`](https://github.com/MISW4204-G14-20252/ANB-rising-stars-showcase/tree/main/collections) en el repositorio. En esta misma se encuentran las pruebas y la documentación de los endpoints de la API desarrollada.

## Diagrama de componentes

<img src="https://github.com/user-attachments/assets/14f22528-f51d-4a9d-8894-7e97f5003a2c" alt="Diagrama de componentes" style="max-width: 100%; height: auto; border-radius: 10px;" />

## Diagrama de flujo de procesos

<img alt="image" src="https://github.com/user-attachments/assets/015f15ad-1062-4707-9d7b-9191dee80fe0" />

## Despliegue

La información y pasos a seguir para desplegar la aplicación se encuentran en el archivo README del repositorio. Tenemos dos archivos para construir imagenes de Docker, uno de ellos se llama `Dockerfile`, este se encarga de definir la plantilla para la API, y el otro se llama `Dockerfile.worker`, el cual corresponde al código del worker que se encarga de leer de la cola de mensajería. Luego, en el archivo `docker-compose.yaml` se unifican todos los servicios que se requieren para ejecutar la aplicación: la base de datos, el backend, el worker, redis y el "reverese proxy". Para desplegar toda la aplicación es necesario ejecutar el comando `docker compose up -d` y a partir de esto ya se pueden hacer peticiones a `http://localhost:80/api/*`.

>[!important]
>Tenemos un archivo extra que se llama `docker-compose.dev.yaml` el cual usamos para el desarrollo de la API. Esto mismo debido a la facilidad para levantar los servicios requeridos para probar la API.

En la siguiente imagen se puede ver el despliegue realizado para esta entrega. 

<img alt="image" src="https://github.com/user-attachments/assets/b9d580b4-19c0-4f6f-8cf1-1b476c0ef661" />


## Reporte de análisis de SonarQube

El reporte de análisis sobre la rama principal en Sonarqube se puede consultar en este [enlace](https://sonarcloud.io/project/overview?id=MISW4204-G14-20252_ANB-rising-stars-showcase). Ahí mismo se puede ver lo siguiente:

<img alt="image" src="https://github.com/user-attachments/assets/ebabfff9-c951-4ebc-b711-997df48325a7" />

En este se puede observar:

- Métricas de bugs, vulnerabilidades y code smells es de 2, 4 y 4 respectivamente
- Una cobertura del **90.7%** dada por las pruebas unitarias
- Código duplicado se encuentra en **0%**
- El estado del quality gate se en cuentra **aprobado**

<img alt="image" src="https://github.com/user-attachments/assets/61cf8d43-9827-400e-9a08-2aad2908c532" />

# Pipeline de integración continua

Se implementó un pipeline de integración continua con Github Actions, lo que hace este es realizar las pruebas unitarias usando `pytest` y de API utilizando `newman`. Sobre las pruebas que se hacen con `pytest` se exporta un archivo sobre la cobertura y luego este es analizado por Sonarqube para presentar un reporte más detallado sobre el código en el repositorio.
