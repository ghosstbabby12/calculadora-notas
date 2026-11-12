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

## Prueba de estrés con Gunicorn

**Fecha:** 2026-11-11, 22:48–22:54 (America/Bogota)
**Commit:** `56452f6` (main, después del PR #4 que sirve la API con Gunicorn: 1 worker y 8 hilos)
**Entorno:** el mismo MacBook Air M4 con Docker Desktop. Locust 2.31.8 en un solo proceso.

La prueba de carga responde «¿cumple con la carga esperada?». La de estrés responde «¿hasta dónde aguanta y se recupera?». `load/estres.py` reutiliza el mismo usuario y los mismos umbrales (1 % de errores, p95 de 800 ms). Sube por escalones de 30 s, incorporando 200 usuarios por segundo. Mide cada escalón por separado y se detiene en el primero que incumple. Al final baja a 50 usuarios durante 30 s para comprobar la recuperación.

| Fase | Usuarios | Peticiones | RPS | Media (ms) | p95 (ms) | Fallos (%) | ¿Roto? |
|---|---|---|---|---|---|---|---|
| subida | 100 | 1737 | 57.7 | 14.6 | 74 | 0.12 | no |
| subida | 250 | 4150 | 137.9 | 8.3 | 10 | 0.07 | no |
| subida | 500 | 8097 | 269.4 | 6.7 | 16 | 0.06 | no |
| subida | 1000 | 16057 | 534.2 | 6.5 | 28 | 0.08 | no |
| subida | 1500 | 23571 | 784.4 | 5.7 | 13 | 0.06 | no |
| subida | 2000 | 31053 | 1033.7 | 5.6 | 20 | 0.03 | no |
| subida | 3000 | 46424 | 1542.0 | 11.4 | 88 | 0.04 | no |
| subida | 4000 | 61284 | 2037.1 | 13.6 | 77 | 0.03 | no |
| subida | 5000* | 76106 | 2509.1 | 30.2 | 170 | 0.05 | no |
| recuperación | 50 | 2722 | 90.2 | 16.8 | 120 | 0.00 | no |

\* En el escalón de 5000 usuarios Locust avisó «CPU usage above 90 %». El generador de carga, no la API, fue el cuello de botella. Por eso ese escalón no se considera una medición válida de la API.

**Punto de quiebre: no alcanzado.** Con Gunicorn la API sostuvo 4000 usuarios (unos 2000 RPS) con un p95 de 77 ms y un 0.03 % de fallos. Con el servidor de desarrollo de Flask se rompía entre 600 y 800 usuarios. La latencia empieza a crecer desde 3000 usuarios (la media pasa de unos 6 ms a 11–14 ms), pero sigue lejos de los 800 ms. Para encontrar el quiebre real hace falta un generador más potente: Locust distribuido en varias máquinas o un runner con más CPU.

**Recuperación:** al bajar a 50 usuarios no hubo fallos. El p95 de 120 ms refleja la cola que quedaba del escalón anterior en los primeros segundos.

**Errores residuales:** en todos los escalones aparece entre 0.03 % y 0.12 % de `RemoteDisconnected`. Ese porcentaje no crece con la carga: con 100 usuarios es igual o mayor que con 4000. Esto indica que no es saturación de la API. Se probó subir `--keep-alive` de Gunicorn a 5 s y los errores se mantuvieron, por lo que se descartó esa causa y se revirtió el cambio. La hipótesis restante es el reenvío de puertos de Docker Desktop en macOS. Queda muy por debajo del umbral del 1 %.

### Reproducir la prueba de estrés

```sh
docker compose up -d --build --wait api
locust -f load/estres.py --host http://127.0.0.1:5000 --headless \
  --html reporte-estres.html --csv resultados_estres
```

No se pasan `-u`, `-r` ni `-t`: la clase `EstresEscalonado` define la forma de la carga. El resumen por escalón queda en `resultados_estres_escalones.csv`. No se usa `--processes`: combinado con la forma de carga personalizada, el proceso maestro dejó de responder.

## Reproducir

```sh
docker compose up -d --build --wait api
locust -f load/locustfile.py --host http://127.0.0.1:5000 --headless \
  -u 100 -r 10 -t 1m --html reporte-carga.html --csv resultados
```

Usa `127.0.0.1` y no `localhost`: en macOS el Receptor de AirPlay ocupa el puerto 5000 y responde 403. El `locustfile` consulta `/salud` antes de medir y aborta con un mensaje explícito si el puerto no apunta a la API. En GitHub Actions, `.github/workflows/carga.yml` publica el HTML y los CSV en el artefacto **reporte-carga**.
