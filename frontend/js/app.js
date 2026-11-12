/**
 * Punto de entrada: conecta los formularios (ui.js) con la API (api.js).
 */
import * as api from "./api.js";
import * as ui from "./ui.js";

// Solo para MOSTRAR el desglose. El cálculo oficial lo hace el backend.
const PESOS = { 1: 0.3, 2: 0.3, 3: 0.4 };

// Notas registradas en esta sesión, por id de estudiante (para el desglose).
const notasPorEstudiante = new Map();

const $ = (selector) => document.querySelector(selector);
const porTestId = (id) => document.querySelector(`[data-testid="${id}"]`);

/** Convierte el valor de un input numérico. Vacío -> null (la API responde 400). */
function leerNota(entrada) {
  return entrada.value === "" ? null : Number(entrada.value);
}

/**
 * Envuelve un envío: deshabilita el botón, ejecuta la acción y muestra
 * el error de la API en el elemento de mensaje si algo falla.
 */
async function conCarga(boton, mensaje, accion) {
  ui.ponerCargando(boton, true);
  ui.ocultarMensaje(mensaje);
  try {
    await accion();
  } catch (error) {
    const texto = error instanceof api.ErrorApi ? error.message : "Ocurrió un error inesperado.";
    ui.mostrarMensaje(mensaje, texto, "error");
  } finally {
    ui.ponerCargando(boton, false);
  }
}

/* ------------------------------------------------- 1. registrar estudiante */
function iniciarFormularioEstudiante() {
  const formulario = $("#form-estudiante");
  const mensaje = porTestId("mensaje-estudiante");
  const boton = porTestId("btn-crear-estudiante");

  formulario.addEventListener("submit", (evento) => {
    evento.preventDefault();
    conCarga(boton, mensaje, async () => {
      const estudiante = await api.crearEstudiante(
        $("#nombre").value.trim(),
        $("#codigo").value.trim(),
      );
      ui.agregarEstudiante($("#lista-estudiantes"), $("#estudiante-notas"), estudiante);
      $("#lista-vacia").hidden = true;
      ui.mostrarMensaje(mensaje, ui.crearMensajeEstudianteCreado(estudiante), "exito");
      formulario.reset();
    });
  });
}

/* ----------------------------------------------------- 2. registrar notas */
function iniciarFormularioNotas() {
  const formulario = $("#form-notas");
  const mensaje = porTestId("mensaje-notas");
  const boton = porTestId("btn-registrar-notas");
  const entradas = [$("#momento1"), $("#momento2"), $("#momento3")];

  entradas.forEach((entrada) => entrada.addEventListener("input", () => ui.marcarValidezNota(entrada)));

  formulario.addEventListener("submit", (evento) => {
    evento.preventDefault();
    // La validación del navegador es solo visual: SIEMPRE se envía al backend,
    // que es la fuente de verdad y devuelve el mensaje de error definitivo.
    entradas.forEach(ui.marcarValidezNota);
    const id = $("#estudiante-notas").value;
    if (id === "") {
      ui.mostrarMensaje(mensaje, "Selecciona primero un estudiante.", "error");
      return;
    }
    const [momento1, momento2, momento3] = entradas.map(leerNota);

    conCarga(boton, mensaje, async () => {
      const resultado = await api.registrarNotas(id, { momento1, momento2, momento3 });
      notasPorEstudiante.set(String(resultado.id), [momento1, momento2, momento3]);
      $("#id-consulta").value = String(resultado.id);
      ui.mostrarMensaje(
        mensaje,
        `Notas registradas. Definitiva: ${resultado.definitiva.toFixed(2)} (${resultado.estado}).`,
        "exito",
      );
    });
  });
}

/* --------------------------------------------------- 3. consultar resultado */
function calcularDesglose(id) {
  const notas = notasPorEstudiante.get(String(id));
  if (!notas) return null;
  return notas.map((nota, indice) => {
    const momento = indice + 1;
    return { momento, nota, peso: PESOS[momento], aporte: nota * PESOS[momento] };
  });
}

function iniciarFormularioConsulta() {
  const formulario = $("#form-consulta");
  const mensaje = porTestId("mensaje-consulta");
  const boton = porTestId("btn-consultar");
  const tarjeta = porTestId("resultado");

  formulario.addEventListener("submit", (evento) => {
    evento.preventDefault();
    ui.ocultarResultado(tarjeta);
    const id = $("#id-consulta").value.trim();
    if (!/^\d+$/.test(id)) {
      ui.mostrarMensaje(mensaje, "Escribe un id numérico válido.", "error");
      return;
    }
    conCarga(boton, mensaje, async () => {
      const resultado = await api.consultarPromedio(id);
      ui.mostrarResultado(tarjeta, resultado, calcularDesglose(resultado.id));
    });
  });
}

/* ------------------------------------------------------ 4. exportar reporte */
function iniciarExportacion() {
  const boton = porTestId("btn-exportar");
  const mensaje = porTestId("mensaje-exportar");

  boton.addEventListener("click", () =>
    conCarga(boton, mensaje, async () => {
      const { bucket, archivo } = await api.exportarReporte();
      ui.mostrarMensaje(mensaje, `Reporte exportado: s3://${bucket}/${archivo}`, "exito");
    }),
  );
}

/* --------------------------------------------------- 5. estado del servidor */
async function verificarServidor() {
  const indicador = porTestId("estado-servidor");
  try {
    const { estado } = await api.consultarSalud();
    ui.mostrarEstadoServidor(indicador, estado === "ok");
  } catch {
    ui.mostrarEstadoServidor(indicador, false);
  }
}

iniciarFormularioEstudiante();
iniciarFormularioNotas();
iniciarFormularioConsulta();
iniciarExportacion();
verificarServidor();
