/**
 * Comunicación con la API. Este módulo NO toca el DOM.
 *
 * Todas las rutas empiezan por /api: Nginx las reenvía al servicio "api"
 * de Docker Compose, así el navegador nunca conoce la URL real del backend.
 */
const BASE_API = "/api";

/** Error con el código HTTP (0 = no hubo respuesta: servidor caído o sin red). */
export class ErrorApi extends Error {
  constructor(mensaje, estado) {
    super(mensaje);
    this.name = "ErrorApi";
    this.estado = estado;
  }
}

const MENSAJE_SIN_CONEXION = "No se pudo conectar con el servidor. Verifica que la API esté en ejecución.";

/** Traduce un código HTTP a un mensaje claro, usando el texto de la API cuando existe. */
function mensajeDeError(estado, errorApi) {
  if (estado === 400) return `Datos inválidos: ${errorApi ?? "revisa la información enviada."}`;
  if (estado === 404) return `No encontrado: ${errorApi ?? "el recurso no existe."}`;
  if (estado === 503) return `Servicio no disponible: ${errorApi ?? "intenta más tarde."}`;
  // 502/504 los genera Nginx cuando la API no responde.
  if (estado === 502 || estado === 504) return MENSAJE_SIN_CONEXION;
  return errorApi ?? `Error inesperado del servidor (HTTP ${estado}).`;
}

async function leerJson(respuesta) {
  try {
    return await respuesta.json();
  } catch {
    return {};
  }
}

async function solicitar(ruta, { metodo = "GET", cuerpo } = {}) {
  const opciones = { method: metodo, headers: { Accept: "application/json" } };
  if (cuerpo !== undefined) {
    opciones.headers["Content-Type"] = "application/json";
    opciones.body = JSON.stringify(cuerpo);
  }

  let respuesta;
  try {
    respuesta = await fetch(`${BASE_API}${ruta}`, opciones);
  } catch {
    throw new ErrorApi(MENSAJE_SIN_CONEXION, 0);
  }

  const datos = await leerJson(respuesta);
  if (!respuesta.ok) {
    throw new ErrorApi(mensajeDeError(respuesta.status, datos.error), respuesta.status);
  }
  return datos;
}

export const consultarSalud = () => solicitar("/salud");

export const crearEstudiante = (nombre, codigo) =>
  solicitar("/estudiantes", { metodo: "POST", cuerpo: { nombre, codigo } });

export const registrarNotas = (id, notas) =>
  solicitar(`/estudiantes/${encodeURIComponent(id)}/notas`, { metodo: "POST", cuerpo: notas });

export const consultarPromedio = (id) =>
  solicitar(`/estudiantes/${encodeURIComponent(id)}/promedio`);

export const exportarReporte = () => solicitar("/reportes/exportar", { metodo: "POST" });
