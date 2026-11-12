"""Arranca Locust con el volcado de estadísticas cada segundo.

Locust escribe una fila por segundo en `*_stats_history.csv`, pero solo la
vuelca a disco cada cinco segundos; en corridas cortas se pierden las últimas
muestras y el gráfico del panel técnico queda incompleto.

Este envoltorio baja ese intervalo a un segundo y delega el resto de los
argumentos en la CLI normal de Locust, así que se usa igual que `locust`.
"""

import locust.stats as stats_module
from locust.main import main

# Debe fijarse antes de que arranque el escritor de CSV.
stats_module.CSV_STATS_FLUSH_INTERVAL_SEC = 1

if __name__ == "__main__":
    main()
