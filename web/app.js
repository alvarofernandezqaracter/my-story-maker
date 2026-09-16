// El orquestador de la interfaz (§19): guarda el estado que llega del harness,
// lo reparte a las tres salas y decide cada cuanto vuelve a preguntar.
//
// Ninguna regla del sistema vive aqui. Lo que se ve es lo que el canon dice.
import { api } from './api.js';
import { crearBrief } from './brief.js';
import { crearTaller } from './taller.js';
import { crearLectura } from './lectura.js';

const $ = (id) => document.getElementById(id);

const COMANDO = {
  borrador: 'python -m novela preparar',
  investigado: 'python -m novela preparar',
  estructurado: 'python -m novela escribir',
  escribiendo: 'python -m novela escribir',
  escrito: 'python -m novela cerrar',
  editado: 'python -m novela estado',
  bloqueado: 'python -m novela desbloquear --capitulo N',
};

// Con el flujo vivo se pregunta a menudo, porque es cuando hay algo que contar.
const RITMO_VIVO = 900;
const RITMO_QUIETO = 4000;

const estado = {
  proyecto: null,
  flujo: { corriendo: false, diario: [], total: 0, error: null, detalles: [] },
  sala: 'brief',
  capitulo: null,
  vistos: 0,
};

let escena = null;
let temporizador = null;

const ctx = {
  api,
  estado,
  get escena() { return escena; },
  refrescar,
  ir,
  abrirLectura,
  elegirCapitulo,
  inmersion,
  previsualizar,
};

const brief = crearBrief(ctx);
const taller = crearTaller(ctx);
const lectura = crearLectura(ctx);

// ------------------------------------------------------------------ escena

// three.js viaja por CDN, que es lo unico de este repo que necesita red. Si no
// llega, la interfaz entera sigue funcionando: la escena es lectura.
import('./legajo.js')
  .then(({ crearLegajo }) => crearLegajo($('escena'), { onFoco: alSenalar }))
  .then((instancia) => { escena = instancia; previsualizar(); })
  .catch(() => {
    $('rail-foco').textContent = 'la mesa 3D no ha cargado (sin red)';
  });

function textoDeReposo() {
  const p = estado.proyecto;
  if (!p?.brief) return 'el legajo está en blanco';
  const aprobados = p.capitulos.filter((c) => c.estado === 'aprobado').length;
  const total = p.capitulos.length || p.brief.capitulos;
  return `${aprobados} de ${total} capítulos aprobados`;
}

function alSenalar(ficha, hizoClic) {
  if (!ficha) {
    $('rail-foco').textContent = textoDeReposo();
    return;
  }
  $('rail-foco').textContent = ficha.titulo
    ? `cap. ${ficha.numero} · ${ficha.estado} · ${ficha.titulo}`
    : `cap. ${ficha.numero} · aún sin ficha`;
  if (hizoClic) {
    elegirCapitulo(ficha.numero);
    const ficha_ = estado.proyecto?.capitulos.find((c) => c.numero === ficha.numero);
    if (ficha_?.legible) abrirLectura(ficha.numero);
  }
}

function previsualizar(briefEnCurso) {
  escena?.actualizar({
    brief: briefEnCurso || estado.proyecto?.brief || brief.leer(),
    capitulos: estado.proyecto?.capitulos || [],
  });
}

function elegirCapitulo(numero) {
  estado.capitulo = numero;
  escena?.elegir(numero);
  pintarRail();
}

// -------------------------------------------------------------------- salas

function ir(sala) {
  estado.sala = sala;
  document.body.dataset.sala = sala;
  for (const boton of document.querySelectorAll('.sala')) {
    boton.setAttribute('aria-current', boton.dataset.sala === sala ? 'true' : 'false');
  }
  for (const nombre of ['brief', 'taller', 'lectura']) {
    $(`sala-${nombre}`).hidden = nombre !== sala;
  }
  if (sala !== 'lectura') {
    escena?.modoLectura(false, 0);
    document.body.dataset.inmersion = 'no';
  }
}

for (const boton of document.querySelectorAll('.sala')) {
  boton.addEventListener('click', () => {
    if (boton.disabled) return;
    if (boton.dataset.sala === 'lectura') {
      const primero = estado.proyecto?.capitulos.find((c) => c.legible);
      if (primero) { abrirLectura(estado.capitulo && legible(estado.capitulo)
        ? estado.capitulo : primero.numero); return; }
    }
    ir(boton.dataset.sala);
  });
}

function legible(numero) {
  return Boolean(estado.proyecto?.capitulos.find((c) => c.numero === numero && c.legible));
}

async function abrirLectura(numero) {
  ir('lectura');
  await lectura.abrir(numero);
}

function inmersion() {
  const dentro = document.body.dataset.inmersion === 'si';
  document.body.dataset.inmersion = dentro ? 'no' : 'si';
  $('inmersion').textContent = dentro ? 'inmersión' : 'salir';
}

// --------------------------------------------------------------------- rail

function pintarRail() {
  const p = estado.proyecto;
  const pastilla = $('pastilla-estado');
  pastilla.textContent = p?.estado || 'sin brief';
  pastilla.dataset.estado = p?.estado || '';
  $('dato-modo').textContent = `modo ${p?.modo || '—'}`;
  $('siguiente-comando').textContent = COMANDO[p?.estado] || 'python -m novela estado';

  const tramos = $('rail-capitulos');
  tramos.textContent = '';
  for (const c of p?.capitulos || []) {
    const tramo = document.createElement('button');
    tramo.type = 'button';
    tramo.className = 'tramo';
    tramo.dataset.estado = c.estado;
    if (c.numero === estado.capitulo) tramo.dataset.foco = 'si';
    tramo.title = c.media
      ? `cap. ${c.numero} · ${c.estado} · notas ${c.notas.join('/')} · media ${c.media}`
      : `cap. ${c.numero} · ${c.estado} · ${c.titulo}`;
    tramo.addEventListener('click', () => {
      elegirCapitulo(c.numero);
      if (c.legible) abrirLectura(c.numero);
    });
    tramos.append(tramo);
  }
  $('rail-foco').textContent = textoDeReposo();
}

$('copiar').addEventListener('click', async () => {
  try {
    await navigator.clipboard.writeText($('siguiente-comando').textContent);
    $('copiar').textContent = 'copiado';
    setTimeout(() => { $('copiar').textContent = 'copiar'; }, 1600);
  } catch {
    $('copiar').textContent = 'cópialo a mano';
  }
});

// ---------------------------------------------------------------- refresco

async function refrescar() {
  try {
    estado.proyecto = await api.proyecto();
  } catch {
    return;
  }
  try {
    const flujo = await api.flujo(estado.vistos);
    estado.vistos = flujo.total;
    estado.flujo = flujo;
    taller.pintarDiario(flujo);
    taller.pintarAhora(flujo);
  } catch {
    // Sin motor no hay diario, pero el resto de la pagina sigue viva.
  }

  brief.pintar(estado.proyecto);
  taller.pintar(estado.proyecto, estado.flujo);
  pintarRail();
  previsualizar();

  const hayLectura = estado.proyecto.capitulos.some((c) => c.legible);
  document.querySelector('.sala[data-sala="lectura"]').disabled = !hayLectura;

  programar();
}

function programar() {
  clearTimeout(temporizador);
  const ritmo = estado.flujo.corriendo ? RITMO_VIVO : RITMO_QUIETO;
  temporizador = setTimeout(() => { if (!document.hidden) refrescar(); else programar(); }, ritmo);
}

// La primera vez se entra por el brief si no hay ninguno, y por el taller si ya
// hay libro: lo que toca hacer es distinto y la pagina no debe hacerlo adivinar.
(async () => {
  await refrescar();
  // #capitulo/3 abre ese capitulo directamente: sirve para volver a donde se
  // estaba leyendo y para enlazar un capitulo concreto.
  const enlace = location.hash.match(/^#capitulo\/(\d+)$/);
  if (enlace && legible(Number(enlace[1]))) await abrirLectura(Number(enlace[1]));
  else if (estado.proyecto?.brief) ir('taller');
  else ir('brief');
})();
