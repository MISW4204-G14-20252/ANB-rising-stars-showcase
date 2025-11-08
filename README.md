# MISW 4204 - ANB Rising Stars Showcase

## Integrantes

Juan Leonardo Rangel Barrera
jl.rangel@uniandes.edu.co

Javier Steven Barrera Toro
js.barrerat1@uniandes.edu.co

Nicolas Lara Gómez
n.lara@uniandes.edu.co

Dionny Santiago Cardenas Salazar
ds.cardenass@uniandes.edu.co

## Entrega 1

- [Documentación](./docs/Entrega_1)
- [Sustentacion](./sustentacion/Entrega_1)
- [Capacity planning](./capacity-planning/plan_de_pruebas.md)

>[!important]
> Adicionalmente, el detalle de todos los entregables se encuentra en la [Wiki](https://github.com/MISW4204-G14-20252/ANB-rising-stars-showcase/wiki).

## Entrega 2 
- [Documentación](https://github.com/MISW4204-G14-20252/ANB-rising-stars-showcase/blob/main/docs/Entrega_2.md)
- [Sustentacion](https://github.com/MISW4204-G14-20252/ANB-rising-stars-showcase/blob/main/sustentacion/Entrega_2.md)
- [Capacity_planning](https://github.com/MISW4204-G14-20252/ANB-rising-stars-showcase/blob/main/capacity-planning/pruebas_de_carga_entrega2.md)

## Para ejecutar este proyecto

1. Crear un entorno virtual con `venv` (este módulo ya viene instalado) y activarlo:

```bash
$ python -m venv venv
$ ./venv/Scripts/activate
``` 

2. Instalar las dependencias del proyecto:

```bash
$ pip install -r requirements.txt
```

3. Ejecutar el proyecto:

```bash
$ uvicorn src.main:app --reload
```

## Para ejecutar los contenedores (dev)

1. Ejecutar el siguiente comando para levantar los servicios:

```bash
$ docker compose -f ./docker-compose.dev.yaml up
```

2. Si desea detener los servicios puede usar la instrucción `stop`, posteriormente se pueden volver a iniciar. Si por el contrario quiere eliminarlos hay que utilizar la instrucción `down`.

```bash
$ docker compose -f ./docker-compose.dev.yaml stop
$ docker compose -f ./docker-compose.dev.yaml down
```

## Agregar video

```bash
$ celery -A worker.video_proc worker --pool=solo --loglevel=info
```

```bash
$ python -i worker/video_proc.py

>>> procesar_video.delay("input_l30s.mp4")

```



