/**
 * Comunicación con la API. Este módulo NO toca el DOM.
 *
 * Todas las rutas de negocio empiezan por /api: Nginx las reenvía al servicio
 * "api" de Docker Compose, así el navegador nunca conoce la URL real del
 * backend. Las del laboratorio de carga usan /carga, proxy al contenedor que
 * ejecuta Locust.
 */
const BASE_API = "/api";
const BASE_CARGA = "/carga";

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
  if (estado === 409) return errorApi ?? "Ya hay una operación en curso.";
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

function opcionesDe(metodo, cuerpo) {
  const opciones = { method: metodo, headers: { Accept: "application/json" } };
  if (cuerpo !== undefined && metodo !== "GET") {
    opciones.headers["Content-Type"] = "application/json";
    opciones.body = JSON.stringify(cuerpo);
  }
  return opciones;
}

async function solicitar(ruta, { metodo = "GET", cuerpo } = {}, base = BASE_API) {
  let respuesta;
  try {
    respuesta = await fetch(`${base}${ruta}`, opcionesDe(metodo, cuerpo));
  } catch {
    throw new ErrorApi(MENSAJE_SIN_CONEXION, 0);
  }

  const datos = await leerJson(respuesta);
  if (!respuesta.ok) {
    throw new ErrorApi(mensajeDeError(respuesta.status, datos.error), respuesta.status);
  }
  return datos;
}

/**
 * Igual que solicitar, pero devuelve el código y la latencia en lugar de
 * lanzar excepción. La usa el panel técnico para mostrar el contrato tal cual.
 */
export async function peticionDetallada(metodo, ruta, cuerpo) {
  const inicio = performance.now();
  try {
    const respuesta = await fetch(`${BASE_API}${ruta}`, opcionesDe(metodo, cuerpo));
    const datos = await leerJson(respuesta);
    return {
      estado: respuesta.status,
      ok: respuesta.ok,
      datos,
      latenciaMs: Math.round(performance.now() - inicio),
    };
  } catch {
    return {
      estado: 0,
      ok: false,
      datos: { error: MENSAJE_SIN_CONEXION },
      latenciaMs: Math.round(performance.now() - inicio),
    };
  }
}

export const consultarSalud = () => solicitar("/salud");

export const crearEstudiante = (nombre, codigo) =>
  solicitar("/estudiantes", { metodo: "POST", cuerpo: { nombre, codigo } });

export const registrarNotas = (id, notas) =>
  solicitar(`/estudiantes/${encodeURIComponent(id)}/notas`, { metodo: "POST", cuerpo: notas });

export const consultarPromedio = (id) =>
  solicitar(`/estudiantes/${encodeURIComponent(id)}/promedio`);

export const exportarReporte = () => solicitar("/reportes/exportar", { metodo: "POST" });

/* ------------------------------------------- laboratorio de carga (Locust) */

export const ejecutarCarga = (usuarios, duracion) =>
  solicitar("/ejecutar", { metodo: "POST", cuerpo: { usuarios, duracion } }, BASE_CARGA);

export const consultarEstadoCarga = () => solicitar("/estado", {}, BASE_CARGA);
