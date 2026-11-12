# Informe de carga

**Fecha:** 2026-11-11, 20:02–20:10 (America/Bogota)
**Commit:** `9959aa3` (main) más los cambios de Persona C en `persona-c/automatizacion-calidad`
**Entorno:** MacBook Air, Apple M4, 16 GB, macOS 27.0.1, Docker Desktop 29.8.1, imagen `calculadora-notas:local` (329 MB, `python:3.11-slim`) y LocalStack 3.8.1.

Escenario: publicación de notas. Cada usuario crea un estudiante, registra sus tres notas y consulta o actualiza el promedio con pesos 5:1. Espera entre 1 y 3 segundos entre tareas. La API corre con el servidor de desarrollo de Flask (`flask run`) dentro de un único contenedor.

## Corrida de aceptación (la del pipeline)

| Usuarios | Altas por segundo | Duración | Peticiones | RPS | Latencia media (ms) | p95 (ms) | Fallos (%) |
|---|---|---|---|---|---|---|---|
| 100 | 10 | 1 minuto | 3003 | 50.8 | 6.0 | 14 | 0.00 |

Umbrales: menos del 1 % de errores y p95 de 800 ms como máximo. **Se cumplen con holgura.**

| Operación | Peticiones | RPS | Media (ms) | p95 (ms) | Máx. (ms) |
|---|---|---|---|---|---|
| POST /estudiantes | 100 | 1.7 | 14.7 | 29 | 40 |
| POST /estudiantes/[id]/notas | 555 | 9.4 | 7.4 | 19 | 41 |
| GET /estudiantes/[id]/promedio | 2348 | 39.7 | 5.3 | 10 | 34 |

La proporción observada es 2348 / 555 = 4.2:1 y no 5:1 porque `on_start` registra notas una vez por usuario: 555 − 100 = 455 escrituras de tarea, es decir 2348 / 455 = 5.2:1 en régimen.

## Punto de quiebre

Se repitió la corrida con niveles crecientes (incorporación de 50 usuarios por segundo, 30 s por nivel) para encontrar el primer nivel fuera de umbral:

| Usuarios | Duración | Peticiones | RPS | Media (ms) | p95 (ms) | Fallos (%) |
|---|---|---|---|---|---|---|
| 200 | 30 s | 3239 | 111.5 | 15.6 | 74 | 0.00 |
| 400 | 30 s | 6056 | 208.5 | 16.0 | 62 | 0.00 |
| 600 | 30 s | 8360 | 284.1 | 55.3 | 270 | 0.00 |
| 800 | 30 s | 9101 | 313.3 | 107.9 | 770 | **54.32** |

**Punto de quiebre: entre 600 y 800 usuarios.** El primer nivel que incumple es 800: el p95 (770 ms) todavía entra en el umbral, pero el 54 % de las peticiones falla. El error dominante es `RemoteDisconnected: Remote end closed connection without response` en las tres rutas, es decir, conexiones cerradas por el servidor: el servidor de desarrollo de Werkzeug agota su capacidad de aceptar conexiones antes de que la latencia supere los 800 ms. Alrededor del 3 % de las consultas también devolvió 404 porque el alta del estudiante había fallado antes.

## Conclusiones

- La corrida de aceptación cumple ambos umbrales: 0 % de fallos y p95 de 14 ms, 57 veces por debajo del límite.
- La operación más lenta es `POST /estudiantes` (media de 14.7 ms y p95 de 29 ms), por delante de la escritura de notas y de la consulta. El alta es la única ruta que crea estado y serializa el diccionario bajo bloqueo; aun así, el costo es de milisegundos.
- El límite no lo pone la lógica de notas sino el servidor de desarrollo de Flask, de un solo proceso: entre 600 y 800 usuarios concurrentes empieza a cerrar conexiones. Para producción habría que servir la app con un servidor WSGI multihilo o multiproceso (por ejemplo Gunicorn) y, sobre todo, sacar el estado de la memoria del proceso.
- Los números corresponden a una laptop con Docker Desktop, donde la red del contenedor y el reenvío de puertos agregan latencia; en un runner de GitHub Actions los valores pueden variar, pero el orden de magnitud y el punto de quiebre deberían mantenerse.

## Reproducir

```sh
docker compose up -d --build --wait api
locust -f load/locustfile.py --host http://127.0.0.1:5000 --headless \
  -u 100 -r 10 -t 1m --html reporte-carga.html --csv resultados
```

Usa `127.0.0.1` y no `localhost`: en macOS el Receptor de AirPlay ocupa el puerto 5000 y responde 403. El `locustfile` consulta `/salud` antes de medir y aborta con un mensaje explícito si el puerto no apunta a la API. En GitHub Actions, `.github/workflows/carga.yml` publica el HTML y los CSV en el artefacto **reporte-carga**.
