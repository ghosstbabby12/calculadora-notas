# Calculadora de notas universitarias

API Flask para registrar un estudiante, calcular su nota definitiva y exportar el listado de resultados a S3. Las notas viven en la memoria de un solo proceso y se pierden al reiniciar la API. El reporte incluye a quienes ya tienen definitiva.

## Ejecutar el proyecto

Desde la raíz, con Docker Desktop o Docker Engine y Compose v2:

```sh
docker compose up -d --build --wait api
curl http://localhost:5000/salud
```

En PowerShell se puede usar `curl.exe` para la consulta. Para ejecutar las pruebas HTTP desde cero:

```sh
docker compose up --build --abort-on-container-exit --exit-code-from test-runner
docker compose down -v
```

| Método y ruta | Entrada de ejemplo | Respuesta |
|---|---|---|
| GET /salud | — | 200, estado ok |
| POST /estudiantes | `{"nombre":"Ana","codigo":"A01"}` | 201 con id, nombre y código |
| POST /estudiantes/1/notas | `{"momento1":3,"momento2":4,"momento3":5}` | 201 con id, definitiva 4.1 y estado APROBADO |
| GET /estudiantes/1/promedio | — | 200 con id, nombre, definitiva y estado |
| POST /reportes/exportar | — | 201 con bucket y nombre del CSV |

Usa el id devuelto al crear el estudiante. Volver a enviar notas reemplaza las tres anteriores. La API devuelve 400 para campos inválidos, 404 para estudiantes inexistentes o promedios pendientes y 503 si falla la exportación. Se puede listar el resultado con `docker compose exec localstack awslocal s3 ls s3://reportes-notas`.

## Código y pruebas para la sustentación

- `app/calculadora.py` valida números de 0 a 5, aplica los pesos 30/30/40 y redondea a dos decimales antes de clasificar. `tests/unit/test_calculadora.py` muestra las particiones por tipo y rango. Los casos 1.99/2.00/2.01 y 2.99/3.00/3.01 comprueban los cambios de estado. Los extremos 0 y 5 son válidos y -0.1 y 5.1 quedan fuera.
- `app/main.py` expone las cinco rutas. Un bloqueo protege el diccionario cuando llegan peticiones simultáneas. `tests/unit/test_main.py` verifica que una actualización inválida conserve las notas anteriores y simula fallos de S3.
- `app/reportes.py` genera el CSV en UTF-8. `infra/setup_aws.py` prepara el bucket antes de iniciar Flask. Sus pruebas unitarias usan clientes simulados.
- `tests/api/schemas.py` define campos y tipos permitidos. `tests/api/test_api.py` usa HTTP real, comprueba el límite de 500 ms por petición y recupera el objeto de S3 para contrastarlo con el promedio.
- `requirements.txt` fija dependencias. `pytest.ini` exige 80 % de cobertura y genera HTML y XML. `.coveragerc` permite que Sonar ubique los archivos con rutas relativas. Los archivos `__init__.py` identifican los paquetes de Python.

Para ejecutar las pruebas unitarias con Python 3.11:

```sh
python -m venv .venv
# Windows PowerShell: .\.venv\Scripts\Activate.ps1
# Linux/macOS: source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pytest tests/unit
```

Abre `htmlcov/index.html`. Cada fila muestra instrucciones ejecutables, instrucciones omitidas y porcentaje cubierto. Selecciona un módulo para ver las líneas pendientes. `coverage.xml` transmite estos resultados a Sonar.

## Contenedores

El Dockerfile elige Python 3.11 slim con `FROM` y establece el directorio con `WORKDIR`. El primer `COPY` y `RUN pip install` permiten reutilizar dependencias en la caché. El segundo `COPY` incorpora el proyecto filtrado por `.dockerignore`. `EXPOSE` declara el puerto 5000 y `CMD` inicia Flask.

En `docker-compose.yml`, `image` fija la versión de LocalStack y da nombre a la imagen compartida entre la API y las pruebas. `build` construye esa imagen. `environment` configura S3 y `ports` permite acceder desde el equipo. `healthcheck` comprueba S3 y la API. `depends_on` espera a que estén saludables. `command` prepara el bucket al arrancar la API y ejecuta pytest en el test-runner. Compose crea una red privada de proyecto con DNS: desde test-runner, `api:5000` identifica otro contenedor y `localhost` identifica el propio.

## SonarQube Cloud en los pull requests

1. Abre el [proyecto del grupo](https://sonarcloud.io/dashboard?id=ghosstbabby12_calculadora-notas). En Administration → Analysis Method selecciona GitHub Actions y desactiva Automatic Analysis. La aplicación de SonarQube Cloud debe tener acceso al repositorio en GitHub.
2. Una persona con permiso de análisis genera un token en Sonar. Un administrador lo guarda en GitHub → Settings → Secrets and variables → Actions → New repository secret, con nombre `SONAR_TOKEN`. El valor se guarda únicamente como secreto.
3. `sonar-project.properties` identifica el proyecto y la organización, indica el origen de código y cobertura y espera el resultado del Quality Gate. Para iniciar la línea base, ejecuta CI sobre main una vez que esa rama contenga el workflow. Para el primer PR, si Sonar exige una línea base previa, analiza primero el commit actual de main con el escáner y las mismas claves.
4. Abre un PR desde una rama del repositorio hacia main y revisa Checks → sonar. Un Quality Gate fallido deja el check en rojo. Los PR de forks no reciben el secreto. Tras ejecutar el flujo por primera vez, en Settings → Rules → Rulesets protege main, exige PR con una aprobación y los checks `pruebas`, `api` y `sonar`.
5. Si falla el análisis, abre el paso “SonarQube Cloud Quality Gate”. Comprueba secreto, organización, clave, permisos y que exista un análisis de main. Tras corregir la configuración vuelve a ejecutar los jobs fallidos del PR.

[Documentación oficial de Sonar para GitHub Actions](https://docs.sonarsource.com/sonarqube-cloud/analyzing-source-code/ci-based-analysis/github-actions-for-sonarcloud)

## Integración, carga y publicación

En los tres YAML, `on` define el evento, `runs-on` selecciona la máquina y `steps` enumera comandos y acciones. `needs` exige que termine otro job correctamente. `secrets` permite inyectar credenciales durante el paso que las utiliza.

- `.github/workflows/ci.yml` prueba cada push y PR. Publica cobertura en el artefacto **cobertura**, ejecuta Compose y analiza los PR y main con Sonar. El checkout del análisis descarga el historial completo.
- `load/locustfile.py` crea un estudiante por usuario, registra notas y alterna consultas y escrituras con pesos 5:1. Agrupa rutas por operación. `.github/workflows/carga.yml` ejecuta 100 usuarios con una incorporación de 10 por segundo durante un minuto en pushes a main o desde Actions → Pruebas de carga → Run workflow. Falla por encima del 1 % de errores o de 800 ms en p95. Guarda el HTML y CSV en **reporte-carga**.
- `.github/workflows/cd.yml` recibe la finalización exitosa del CI de un push a main. Usa el token de GitHub con permiso de escritura en paquetes, publica en GHCR con el SHA y prueba la imagen publicada en /salud. Promueve la revisión vigente a staging tras el humo. Si el humo falla, repone la etiqueta previa cuando existe. En la primera publicación fallida no hay versión anterior. La publicación deja una imagen en el registro.

Para la demostración interactiva, levanta la API, activa el entorno Python e inicia `locust -f load/locustfile.py --host http://localhost:5000`. Abre http://localhost:8089. Para documentar resultados utiliza `load/informe.md`.
