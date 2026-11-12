/**
 * Panel técnico de la sustentación.
 *
 * Reúne cuatro demostraciones sobre la API real:
 *  1. arquitectura y latencia del servicio,
 *  2. contrato HTTP con códigos de estado,
 *  3. batería de valores límite (BVA),
 *  4. laboratorio de carga con Locust.
 */
import * as api from "./api.js";
import { dibujarSerie } from "./graficos.js";
import { mostrarMensaje } from "./ui.js";

const $ = (selector) => document.querySelector(selector);
const porTestId = (id) => document.querySelector(`[data-testid="${id}"]`);

const SONDEO_MS = 1000;
const MARGEN_ESPERA_S = 120;

const CASOS_BVA = [
  { nombre: "Todo cero", notas: [0, 0, 0], esperado: 0, estado: "REPROBADO" },
  { nombre: "Todo cinco", notas: [5, 5, 5], esperado: 5, estado: "APROBADO" },
  { nombre: "Frontera habilitar", notas: [2, 2, 2], esperado: 2, estado: "HABILITA" },
  { nombre: "Justo debajo de habilitar", notas: [3.0, 3.1, 0.4], esperado: 1.99, estado: "REPROBADO" },
  { nombre: "Frontera aprobar", notas: [3, 3, 3], esperado: 3, estado: "APROBADO" },
  { nombre: "Justo debajo de aprobar", notas: [1.6, 1.7, 5.0], esperado: 2.99, estado: "HABILITA" },
  { nombre: "Solo el momento 3", notas: [5, 0, 0], esperado: 1.5, estado: "REPROBADO" },
  { nombre: "Redondeo a 3.38", notas: [4.15, 3.27, 2.88], esperado: 3.38, estado: "APROBADO" },
  { nombre: "Nota mayor que 5.0", notas: [5.1, 3, 3], valido: false },
  { nombre: "Nota menor que 0.0", notas: [-0.1, 3, 3], valido: false },
  { nombre: "Texto en una nota", notas: ["abc", 3, 3], valido: false },
];

let ultimaSerie = null;

/* ------------------------------------------------------------------ pestañas */

/** Alterna entre la vista de operación y el panel técnico. */
export function iniciarPestanas() {
  const botones = [...document.querySelectorAll(".pestana")];
  const mostrar = (vista) => {
    for (const boton of botones) {
      const activo = boton.dataset.vista === vista;
      boton.setAttribute("aria-selected", String(activo));
      $(`#vista-${boton.dataset.vista}`).hidden = !activo;
    }
    if (vista === "tecnico") {
      verificarArquitectura();
      if (ultimaSerie) dibujarSerie($(".grafico"), ultimaSerie);
    }
  };
  for (const boton of botones) {
    boton.addEventListener("click", () => mostrar(boton.dataset.vista));
  }
}

/* --------------------------------------------------------------- arquitectura */

async function verificarArquitectura() {
  const chip = porTestId("chip-api");
  const latencia = porTestId("chip-latencia");
  chip.dataset.estado = "verificando";
  chip.textContent = "API: verificando…";

  const inicio = performance.now();
  try {
    await api.consultarSalud();
    chip.dataset.estado = "ok";
    chip.textContent = "API: en línea";
    latencia.textContent = `Latencia: ${Math.round(performance.now() - inicio)} ms`;
  } catch {
    chip.dataset.estado = "error";
    chip.textContent = "API: sin respuesta";
    latencia.textContent = "Latencia: —";
  }
}

/* ------------------------------------------------------------------- contrato */

function iniciarContrato() {
  const metodo = $("#contrato-metodo");
  const ruta = $("#contrato-ruta");
  const cuerpo = $("#contrato-cuerpo");
  const boton = porTestId("btn-contrato");
  const chipEstado = porTestId("contrato-estado");
  const chipLatencia = porTestId("contrato-latencia");
  const salida = porTestId("contrato-json");

  const sincronizarCuerpo = () => {
    const esPost = metodo.value === "POST";
    cuerpo.disabled = !esPost;
    if (!esPost) cuerpo.value = "";
  };
  metodo.addEventListener("change", sincronizarCuerpo);

  for (const atajo of document.querySelectorAll(".atajos [data-ruta]")) {
    atajo.addEventListener("click", () => {
      metodo.value = atajo.dataset.metodo;
      ruta.value = atajo.dataset.ruta;
      cuerpo.value = atajo.dataset.cuerpo;
      sincronizarCuerpo();
    });
  }

  const enviar = async () => {
    const destino = ruta.value.trim();
    if (!destino.startsWith("/")) {
      salida.textContent = 'La ruta debe empezar por "/".';
      return;
    }

    let datos;
    if (metodo.value !== "GET" && cuerpo.value.trim()) {
      try {
        datos = JSON.parse(cuerpo.value);
      } catch {
        chipEstado.dataset.estado = "error";
        chipEstado.textContent = "JSON inválido";
        salida.textContent = "El cuerpo no es JSON válido. Corrige la sintaxis y vuelve a enviar.";
        return;
      }
    }

    boton.disabled = true;
    chipEstado.dataset.estado = "neutro";
    chipEstado.textContent = "Enviando…";
    chipLatencia.textContent = "Latencia: —";

    const resultado = await api.peticionDetallada(metodo.value, destino, datos);

    chipEstado.dataset.estado = resultado.ok ? "ok" : "error";
    chipEstado.textContent = resultado.estado === 0 ? "Sin conexión" : `HTTP ${resultado.estado}`;
    chipLatencia.textContent = `Latencia: ${resultado.latenciaMs} ms`;
    salida.textContent = Object.keys(resultado.datos).length
      ? JSON.stringify(resultado.datos, null, 2)
      : "(respuesta sin cuerpo)";
    boton.disabled = false;
  };

  boton.addEventListener("click", enviar);
}

/* ------------------------------------------------------------------------ BVA */

function textoNotas(notas) {
  return notas
    .map((nota) => (typeof nota === "number" ? nota.toFixed(1) : `"${nota}"`))
    .join(" · ");
}

function crearCelda(contenido, clase) {
  const celda = document.createElement("td");
  celda.textContent = contenido;
  if (clase) celda.className = clase;
  return celda;
}

function filaBva(caso, respuesta) {
  const fila = document.createElement("tr");
  const definitiva = respuesta.datos.definitiva;
  const cumple = caso.valido === false
    ? respuesta.estado === 400
    : respuesta.ok &&
      Math.abs(definitiva - caso.esperado) < 0.005 &&
      respuesta.datos.estado === caso.estado;

  const esperado = caso.valido === false
    ? "HTTP 400 · rechazo"
    : `${caso.esperado.toFixed(2)} · ${caso.estado}`;
  let obtenido;
  if (respuesta.estado === 0) obtenido = "Sin conexión";
  else if (respuesta.ok) obtenido = `${definitiva.toFixed(2)} · ${respuesta.datos.estado}`;
  else obtenido = `HTTP ${respuesta.estado} · ${respuesta.datos.error ?? "error"}`;

  fila.append(
    crearCelda(caso.nombre),
    crearCelda(textoNotas(caso.notas), "numero"),
    crearCelda(esperado, "numero"),
    crearCelda(obtenido, "numero"),
    crearCelda(cumple ? "✔ cumple" : "✘ falla"),
  );
  fila.className = cumple ? "fila-ok" : "fila-falla";
  return fila;
}

function iniciarBva() {
  const boton = porTestId("btn-bva");
  const resumen = porTestId("bva-resumen");
  const cuerpoTabla = porTestId("tabla-bva").tBodies[0];

  boton.addEventListener("click", async () => {
    boton.disabled = true;
    cuerpoTabla.replaceChildren();
    resumen.dataset.estado = "neutro";
    resumen.textContent = "Ejecutando…";

    let estudiante;
    try {
      estudiante = await api.crearEstudiante("Batería BVA", `bva-${Date.now()}`);
    } catch {
      resumen.dataset.estado = "error";
      resumen.textContent = "No se pudo crear el estudiante de prueba";
      boton.disabled = false;
      return;
    }

    let cumplen = 0;
    for (const caso of CASOS_BVA) {
      const respuesta = await api.peticionDetallada(
        "POST",
        `/estudiantes/${estudiante.id}/notas`,
        { momento1: caso.notas[0], momento2: caso.notas[1], momento3: caso.notas[2] },
      );
      const fila = filaBva(caso, respuesta);
      if (fila.classList.contains("fila-ok")) cumplen += 1;
      cuerpoTabla.append(fila);
    }

    resumen.dataset.estado = cumplen === CASOS_BVA.length ? "ok" : "error";
    resumen.textContent = `${cumplen} de ${CASOS_BVA.length} casos cumplen`;
    boton.disabled = false;
  });
}

/* ----------------------------------------------------------------------- carga */

function pintarProgreso(estado, duracion) {
  const progreso = porTestId("carga-progreso");
  const barra = progreso.querySelector(".barra");
  const relleno = progreso.querySelector(".barra__relleno");
  const textoEstado = porTestId("carga-estado");
  const transcurrido = Math.min(estado.transcurrido ?? 0, duracion);
  const porcentaje = duracion > 0 ? Math.min(100, (transcurrido / duracion) * 100) : 0;
  relleno.style.width = `${porcentaje}%`;
  barra.setAttribute("aria-valuenow", String(Math.round(porcentaje)));
  textoEstado.textContent =
    `Corriendo ${estado.usuarios} usuarios · ${transcurrido.toFixed(0)} s de ${duracion} s`;
}

function pintarResultadoCarga(resultado) {
  porTestId("carga-resultado").hidden = false;

  const fallos = `${resultado.fallos} (${(resultado.proporcion_fallos * 100).toFixed(2)} %)`;
  porTestId("kpi-peticiones").textContent = resultado.peticiones;
  porTestId("kpi-rps").textContent = resultado.rps.toFixed(1);
  porTestId("kpi-p95").textContent = resultado.p95_ms.toFixed(1);
  porTestId("kpi-media").textContent = resultado.media_ms.toFixed(1);
  porTestId("kpi-fallos").textContent = fallos;

  const veredicto = porTestId("carga-veredicto");
  veredicto.hidden = false;
  veredicto.className = `veredicto ${resultado.cumple ? "veredicto--ok" : "veredicto--falla"}`;
  veredicto.textContent = resultado.cumple
    ? `Cumple los umbrales: ${(resultado.proporcion_fallos * 100).toFixed(2)} % de errores ` +
      `y p95 de ${resultado.p95_ms.toFixed(0)} ms (límite: 1 % y 800 ms).`
    : `No cumple los umbrales: ${(resultado.proporcion_fallos * 100).toFixed(2)} % de errores ` +
      `y p95 de ${resultado.p95_ms.toFixed(0)} ms (límite: 1 % y 800 ms).`;

  const figura = porTestId("figura-carga");
  figura.hidden = false;
  ultimaSerie = resultado.serie ?? [];
  dibujarSerie($(".grafico"), ultimaSerie);

  const contenedor = porTestId("tabla-carga-contenedor");
  const cuerpo = porTestId("tabla-carga-endpoints").tBodies[0];
  cuerpo.replaceChildren();
  for (const endpoint of resultado.endpoints) {
    const fila = document.createElement("tr");
    fila.append(
      crearCelda(endpoint.metodo),
      crearCelda(endpoint.ruta),
      crearCelda(String(endpoint.peticiones), "numero"),
      crearCelda(String(endpoint.fallos), "numero"),
      crearCelda(endpoint.media_ms.toFixed(1), "numero"),
      crearCelda(endpoint.p95_ms.toFixed(1), "numero"),
      crearCelda(endpoint.max_ms.toFixed(1), "numero"),
    );
    cuerpo.append(fila);
  }
  contenedor.hidden = false;
}

function iniciarCarga() {
  const boton = porTestId("btn-carga");
  const mensaje = porTestId("mensaje-carga");

  boton.addEventListener("click", async () => {
    const usuarios = Number($("#carga-usuarios").value);
    const duracion = Number($("#carga-duracion").value);
    mensaje.hidden = true;

    if (!Number.isInteger(usuarios) || usuarios < 5 || usuarios > 200) {
      mostrarMensaje(mensaje, "Los usuarios deben ser un entero entre 5 y 200.", "error");
      return;
    }
    if (!Number.isInteger(duracion) || duracion < 10 || duracion > 60) {
      mostrarMensaje(mensaje, "La duración debe ser un entero entre 10 y 60 segundos.", "error");
      return;
    }

    boton.disabled = true;
    porTestId("carga-resultado").hidden = true;
    porTestId("carga-veredicto").hidden = true;
    porTestId("figura-carga").hidden = true;
    porTestId("tabla-carga-contenedor").hidden = true;
    const progreso = porTestId("carga-progreso");
    progreso.hidden = false;
    progreso.querySelector(".barra__relleno").style.width = "0%";
    porTestId("carga-estado").textContent = `Preparando ${usuarios} usuarios…`;

    try {
      await api.ejecutarCarga(usuarios, duracion);
      const limite = Date.now() + (duracion + MARGEN_ESPERA_S) * 1000;
      while (Date.now() < limite) {
        await new Promise((resolver) => setTimeout(resolver, SONDEO_MS));
        const estado = await api.consultarEstadoCarga();
        if (estado.estado === "ejecutando") {
          pintarProgreso(estado, duracion);
          continue;
        }
        if (estado.estado === "error") {
          throw new Error(estado.error ?? "La corrida terminó con error.");
        }
        pintarResultadoCarga(estado.resultado);
        porTestId("carga-estado").textContent =
          `Terminado en ${estado.transcurrido.toFixed(0)} s · último código de salida ` +
          `${estado.resultado.codigo_salida}.`;
        return;
      }
      throw new Error("La corrida no respondió a tiempo.");
    } catch (error) {
      mostrarMensaje(mensaje, error.message, "error");
      progreso.hidden = true;
    } finally {
      boton.disabled = false;
    }
  });
}

/* ------------------------------------------------------------- inicialización */

export function iniciarPanelTecnico() {
  iniciarPestanas();
  porTestId("btn-verificar-arquitectura").addEventListener("click", verificarArquitectura);
  iniciarContrato();
  iniciarBva();
  iniciarCarga();

  // El lienzo se redibuja al cambiar el ancho de la ventana.
  let temporizador;
  window.addEventListener("resize", () => {
    if (!ultimaSerie) return;
    clearTimeout(temporizador);
    temporizador = setTimeout(() => dibujarSerie($(".grafico"), ultimaSerie), 150);
  });
}
