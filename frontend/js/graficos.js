/**
 * Gráficos del panel técnico, dibujados con DOM y canvas (sin librerías).
 *
 * Regla: aquí solo se pintan números; los textos se crean con textContent.
 */

const COLOR_RPS = "#2f6fb3";
const COLOR_P95 = "#b45309";
const COLOR_EJE = "#8a93a6";
const COLOR_GRILLA = "#e6eaf1";

const ZONAS_MEDIDOR = [
  { clase: "medidor__zona--reprobado", ancho: 40 }, // 0.0 – 2.0
  { clase: "medidor__zona--habilita", ancho: 20 }, // 2.0 – 3.0
  { clase: "medidor__zona--aprobado", ancho: 40 }, // 3.0 – 5.0
];

/**
 * Medidor horizontal de 0.0 a 5.0 con las tres franjas de estado y una
 * marca en la definitiva. Ayuda a ver de un golpe cuán cerca está del borde.
 */
export function crearMedidor(definitiva) {
  const contenedor = document.createElement("div");

  const escala = document.createElement("div");
  escala.className = "medidor__escala";
  for (const { clase, ancho } of ZONAS_MEDIDOR) {
    const zona = document.createElement("span");
    zona.className = clase;
    zona.style.width = `${ancho}%`;
    escala.append(zona);
  }

  const marcador = document.createElement("span");
  marcador.className = "medidor__marcador";
  const porcentaje = Math.min(100, Math.max(0, (definitiva / 5) * 100));
  marcador.style.left = `${porcentaje}%`;
  escala.append(marcador);
  contenedor.append(escala);

  const ticks = document.createElement("div");
  ticks.className = "medidor__ticks";
  for (const valor of [0, 2, 3, 5]) {
    const tick = document.createElement("span");
    tick.className = "medidor__tick";
    tick.style.left = `${(valor / 5) * 100}%`;
    tick.textContent = valor.toFixed(1);
    ticks.append(tick);
  }
  contenedor.append(ticks);
  return contenedor;
}

/** Ajusta el lienzo al tamaño real en píxeles de la pantalla (nitidez). */
function prepararLienzo(lienzo) {
  const proporcion = window.devicePixelRatio || 1;
  const ancho = lienzo.clientWidth || 640;
  const alto = lienzo.clientHeight || 240;
  lienzo.width = Math.round(ancho * proporcion);
  lienzo.height = Math.round(alto * proporcion);
  const contexto = lienzo.getContext("2d");
  contexto.setTransform(proporcion, 0, 0, proporcion, 0, 0);
  return { contexto, ancho, alto };
}

function texto(contexto, contenido, x, y, color, alineacion = "left") {
  contexto.fillStyle = color;
  contexto.textAlign = alineacion;
  contexto.textBaseline = "middle";
  contexto.fillText(contenido, x, y);
}

/**
 * Dibuja dos series en el mismo lienzo: RPS (eje izquierdo) y p95 en ms
 * (eje derecho). Cada una se escala a su propio máximo para que ambas se vean.
 */
export function dibujarSerie(lienzo, serie) {
  const { contexto, ancho, alto } = prepararLienzo(lienzo);
  contexto.clearRect(0, 0, ancho, alto);

  const margen = { arriba: 26, derecha: 46, abajo: 26, izquierda: 40 };
  const utilAncho = ancho - margen.izquierda - margen.derecha;
  const utilAlto = alto - margen.arriba - margen.abajo;
  contexto.font = "11px system-ui, sans-serif";

  if (!serie || serie.length < 2) {
    texto(contexto, "Sin muestras suficientes: usa una duración de 10 s o más.",
      ancho / 2, alto / 2, COLOR_EJE, "center");
    return;
  }

  const tMax = Math.max(1, serie[serie.length - 1].t);
  const maxRps = Math.max(1, ...serie.map((punto) => punto.rps));
  const maxP95 = Math.max(1, ...serie.map((punto) => punto.p95_ms));
  const x = (t) => margen.izquierda + (t / tMax) * utilAncho;
  const yRps = (v) => margen.arriba + utilAlto - (v / maxRps) * utilAlto;
  const yP95 = (v) => margen.arriba + utilAlto - (v / maxP95) * utilAlto;

  // Grilla horizontal y etiquetas de los dos ejes.
  for (let fila = 0; fila <= 4; fila += 1) {
    const y = margen.arriba + (utilAlto / 4) * fila;
    contexto.strokeStyle = COLOR_GRILLA;
    contexto.lineWidth = 1;
    contexto.beginPath();
    contexto.moveTo(margen.izquierda, y);
    contexto.lineTo(ancho - margen.derecha, y);
    contexto.stroke();

    const rps = (maxRps * (4 - fila)) / 4;
    const p95 = (maxP95 * (4 - fila)) / 4;
    texto(contexto, rps.toFixed(0), margen.izquierda - 6, y, COLOR_RPS, "right");
    texto(contexto, `${p95.toFixed(0)}`, ancho - margen.derecha + 6, y, COLOR_P95, "left");
  }

  // Etiquetas del eje X (segundos).
  for (const t of [0, tMax / 2, tMax]) {
    texto(contexto, `${t.toFixed(0)} s`, x(t), alto - margen.abajo + 12, COLOR_EJE, "center");
  }

  const linea = (valores, color, escalaY) => {
    contexto.strokeStyle = color;
    contexto.lineWidth = 2;
    contexto.beginPath();
    valores.forEach((punto, indice) => {
      const px = x(punto.t);
      const py = escalaY(punto.valor);
      if (indice === 0) contexto.moveTo(px, py);
      else contexto.lineTo(px, py);
    });
    contexto.stroke();
  };

  linea(
    serie.map((punto) => ({ t: punto.t, valor: punto.rps })),
    COLOR_RPS,
    yRps,
  );
  linea(
    serie.map((punto) => ({ t: punto.t, valor: punto.p95_ms })),
    COLOR_P95,
    yP95,
  );

  // Leyenda: cada serie con su color, separadas para no solaparse.
  contexto.fillStyle = COLOR_RPS;
  contexto.fillRect(margen.izquierda, 8, 8, 8);
  texto(contexto, "RPS", margen.izquierda + 14, 12, COLOR_RPS);
  contexto.fillStyle = COLOR_P95;
  contexto.fillRect(margen.izquierda + 108, 8, 8, 8);
  texto(contexto, "p95 (ms)", margen.izquierda + 122, 12, COLOR_P95);
}
