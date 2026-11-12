/**
 * Manipulación del DOM. Este módulo NO hace peticiones.
 *
 * Regla de seguridad: los datos del usuario o de la API se escriben SIEMPRE
 * con textContent o createElement, nunca con innerHTML (evita XSS).
 */
import { crearMedidor } from "./graficos.js";

const ESTADOS = {
  APROBADO: { clase: "resultado--aprobado", icono: "✔" },
  HABILITA: { clase: "resultado--habilita", icono: "⚠" },
  REPROBADO: { clase: "resultado--reprobado", icono: "✖" },
};

const MENSAJE_NOTA_FUERA_DE_RANGO = "La nota debe estar entre 0.0 y 5.0.";

/* ---------------------------------------------------------------- mensajes */

/** tipo: "exito" | "error" | "info". contenido: texto o nodo. */
export function mostrarMensaje(elemento, contenido, tipo) {
  elemento.className = `mensaje mensaje--${tipo}`;
  elemento.replaceChildren(contenido);
  elemento.hidden = false;
}

export function ocultarMensaje(elemento) {
  elemento.hidden = true;
  elemento.replaceChildren();
}

/** Mensaje "Estudiante creado con id N" con el id en un nodo propio. */
export function crearMensajeEstudianteCreado(estudiante) {
  const fragmento = document.createDocumentFragment();
  const id = document.createElement("strong");
  id.dataset.testid = "id-creado";
  id.textContent = String(estudiante.id);
  fragmento.append(`Estudiante "${estudiante.nombre}" creado con id `, id, ".");
  return fragmento;
}

/* ---------------------------------------------------------- estado de carga */

/** Deshabilita el botón mientras se espera la respuesta (evita doble envío). */
export function ponerCargando(boton, cargando) {
  if (cargando) {
    boton.dataset.textoOriginal = boton.textContent;
    boton.textContent = "Procesando…";
    boton.disabled = true;
    boton.setAttribute("aria-busy", "true");
  } else {
    boton.textContent = boton.dataset.textoOriginal ?? boton.textContent;
    boton.disabled = false;
    boton.removeAttribute("aria-busy");
  }
}

/* ------------------------------------------------------- estado del servidor */

export function mostrarEstadoServidor(elemento, enLinea) {
  elemento.dataset.estado = enLinea ? "en-linea" : "fuera-de-linea";
  elemento.querySelector(".estado-servidor__texto").textContent = enLinea
    ? "Servidor en línea"
    : "Servidor fuera de línea";
}

/* ------------------------------------------------------ lista de estudiantes */

export function agregarEstudiante(lista, selector, estudiante) {
  const item = document.createElement("li");
  item.dataset.id = String(estudiante.id);
  const id = document.createElement("span");
  id.className = "lista-estudiantes__id";
  id.textContent = `#${estudiante.id}`;
  const datos = document.createElement("span");
  datos.textContent = `${estudiante.nombre} (${estudiante.codigo})`;
  item.append(datos, id);
  lista.append(item);

  const opcion = document.createElement("option");
  opcion.value = String(estudiante.id);
  opcion.textContent = `#${estudiante.id} · ${estudiante.nombre}`;
  selector.append(opcion);
  selector.value = opcion.value;
}

/* ---------------------------------------------- validación visual de notas */

/** Marca el input en rojo si la nota está fuera de 0.0–5.0. Solo es visual. */
export function marcarValidezNota(entrada) {
  const { rangeUnderflow, rangeOverflow, badInput } = entrada.validity;
  const invalida = rangeUnderflow || rangeOverflow || badInput;
  const error = document.getElementById(entrada.getAttribute("aria-describedby"));
  entrada.setAttribute("aria-invalid", String(invalida));
  error.textContent = invalida ? MENSAJE_NOTA_FUERA_DE_RANGO : "";
  error.hidden = !invalida;
}

/* --------------------------------------------------- tarjeta de resultado */

function crearFila(celdas) {
  const fila = document.createElement("tr");
  celdas.forEach((texto, indice) => {
    const celda = document.createElement(indice === 0 ? "th" : "td");
    if (indice === 0) celda.scope = "row";
    celda.textContent = texto;
    fila.append(celda);
  });
  return fila;
}

function pintarDesglose(tarjeta, desglose) {
  const tabla = tarjeta.querySelector(".desglose");
  const aviso = tarjeta.querySelector('[data-testid="desglose-no-disponible"]');
  tabla.hidden = desglose === null;
  aviso.hidden = desglose !== null;
  if (desglose === null) return;

  const filas = desglose.map(({ momento, nota, peso, aporte }) =>
    crearFila([`Momento ${momento}`, nota.toFixed(2), `× ${Math.round(peso * 100)} %`, aporte.toFixed(2)]),
  );
  tabla.tBodies[0].replaceChildren(...filas);
}

/**
 * resultado: respuesta de GET /promedio.
 * desglose: lista de { momento, nota, peso, aporte } o null si no se conoce.
 */
export function mostrarResultado(tarjeta, resultado, desglose) {
  const estilo = ESTADOS[resultado.estado] ?? { clase: "", icono: "•" };
  tarjeta.className = `resultado ${estilo.clase}`;
  tarjeta.querySelector('[data-testid="resultado-nombre"]').textContent =
    `#${resultado.id} · ${resultado.nombre}`;
  tarjeta.querySelector(".insignia__icono").textContent = estilo.icono;
  tarjeta.querySelector(".insignia__texto").textContent = resultado.estado;
  const definitiva = resultado.definitiva.toFixed(2);
  tarjeta.querySelector('[data-testid="resultado-definitiva"]').textContent = definitiva;
  tarjeta.querySelector(".desglose__total").textContent = definitiva;
  tarjeta
    .querySelector('[data-testid="resultado-medidor"]')
    .replaceChildren(crearMedidor(resultado.definitiva));
  pintarDesglose(tarjeta, desglose);
  tarjeta.hidden = false;
}

export function ocultarResultado(tarjeta) {
  tarjeta.hidden = true;
}
