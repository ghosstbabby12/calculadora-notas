FROM nginx:alpine

# Configuración del sitio y del proxy inverso hacia la API.
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Archivos estáticos (sin build: HTML, CSS y JS puros).
COPY index.html /usr/share/nginx/html/
COPY css/ /usr/share/nginx/html/css/
COPY js/ /usr/share/nginx/html/js/

EXPOSE 80
