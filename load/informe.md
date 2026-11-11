# Informe de carga

Fecha, commit, entorno, recursos de CPU/memoria y versión de la imagen:

Escenario: publicación de notas. Cada usuario crea un estudiante, registra sus tres notas y consulta o actualiza el promedio con pesos 5:1. Espera entre 1 y 3 segundos entre tareas.

| Usuarios | Altas por segundo | Duración | Peticiones | RPS | Latencia media (ms) | p95 (ms) | Fallos (%) |
|---|---|---|---|---|---|---|---|
| 100 | 10 | 1 minuto | | | | | |

Adjunta el HTML y los CSV de Locust. Usa la fila Aggregated de resultados_stats.csv. El p95 indica el tiempo dentro del que terminó el 95 % de las peticiones.

**Punto de quiebre.** Repite con niveles crecientes de usuarios y anota el primer nivel con más de 1 % de fallos o con p95 superior a 800 ms. Si solo se hizo una corrida dentro de los umbrales, indica «no alcanzado».

**Conclusiones.** Registra qué umbral se cumplió, cuál fue la operación más lenta y qué limitación del entorno pudo influir.
