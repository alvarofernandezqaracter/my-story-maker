// El orquestador de la interfaz (§19): guarda el estado que llega del servidor,
// lo reparte a las tres salas y decide cada cuánto vuelve a preguntar.
//
// Ninguna regla del sistema vive aquí. Lo que se ve es lo que el canon dice, y
// el canon es uno de los dos de §1 según el camino elegido.
import { api } from './api.js';
import { crearBrief } from './brief.js';
import { crearTaller } from './taller.js';
import { crearLectura } from './lectura.js';

const $ = (id) => document.getElementById(id);

// El comando que toca según por dónde vaya el proyecto. Cada camino tiene el
// suyo porque son dos orquestadores distintos: uno es Python y el otro es una
// sesión de Claude Code leyendo la skill.
const COMANDO = {
  harness: {
    borrador: 'python -m novela preparar',
    investigado: 'python -m novela preparar',
    estructurado: 'python -m novela escribir',
    escribiendo: 'python -m novela escribir',
    escrito: 'python -m novela cerrar',
    editado: 'python -m novela estado',
    bloqueado: 'python -m novela desbloquear --capitulo N',
  },
  delegado: {
    borrador: '/orquestar-novela preparar',
    investigado: '/orquestar-novela preparar',
    estructurado: '/orquestar-novela escribir',
    escribiendo: '/orquestar-novela continuar',
    escrito: '/orquestar-novela cerrar',
    editado: '/orquestar-novela',
    bloqueado: '/orquestar-novela desbloquear el capítulo N',
  },
};

// El camino delegado no tiene motor que escuchar: el canon cambia cuando la
// sesión de Claude Code escribe un fichero, y eso se ve releyendo el disco.
const RITMO_VIVO = 900;
const RITMO_QUIETO = 4000;
const RITMO_DELEGADO = 2500;

const FLUJO_VACIO = {
  corriendo: false, diario: [], total: 0, error: null, detalles: [], sin_motor: true,
};

const estado = {
  // null hasta la primera respuesta: la primera pregunta va sin camino para
  // que conteste `interfaz.camino` del perfil (§12).
  camino: null,
  proyecto: null,
  flujo: { ...FLUJO_VACIO },
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
  get camino() { return estado.camino; },
  refrescar,
  ir,
  abrirLectura,
  elegirCapitulo,
  inmersion,
  previsualizar,
  verContexto,
  comandoDe,
  perfilElegido: () => brief.perfil(),
};

const brief = crearBrief(ctx);
const taller = crearTaller(ctx);
const lectura = crearLectura(ctx);

function comandoDe(proyecto) {
  const tabla = COMANDO[estado.camino] || COMANDO.harness;
  return tabla[proyecto?.estado] || (estado.camino === 'delegado'
    ? '/orquestar-novela' : 'python -m novela estado');
}

// ------------------------------------------------------------------ escena

// three.js viaja por CDN, que es lo único de este repo que necesita red. Si no
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

// ------------------------------------------------------------------ camino

// Cambiar de camino es cambiar de canon, no de vista: se tira todo lo que había
// en pantalla y se vuelve a preguntar. Mezclar los dos sería lo peor que podría
// hacer esta página, porque los dos hablan de la misma novela.
function cambiarCamino(camino) {
  if (camino === estado.camino) return;
  estado.camino = camino;
  estado.proyecto = null;
  estado.flujo = { ...FLUJO_VACIO };
  estado.capitulo = null;
  estado.vistos = 0;
  document.body.dataset.camino = camino;
  pintarConmutador();
  refrescar();
}

function pintarConmutador() {
  for (const boton of $('conmutador-camino').children) {
    boton.setAttribute('aria-current', boton.dataset.camino === estado.camino ? 'true' : 'false');
  }
}

for (const boton of $('conmutador-camino').children) {
  boton.addEventListener('click', () => cambiarCamino(boton.dataset.camino));
}

// -------------------------------------------------- paquete de contexto (§7)

const cajon = $('cajon-contexto');

async function verContexto(numero) {
  $('cajon-titulo').textContent = `Capítulo ${numero}`;
  $('cajon-texto').textContent = 'leyendo…';
  $('cajon-pista').textContent = '';
  if (!cajon.open) cajon.showModal();
  try {
    const paquete = await api.contexto(numero, estado.camino);
    $('cajon-texto').textContent = paquete.texto;
    $('cajon-pista').textContent = paquete.origen === 'guardado'
      ? `${paquete.ruta} — es el paquete con el que se escribió, tal cual quedó en disco.`
      : 'Regenerado ahora con el canon de este momento: no es exactamente el que vio'
        + ` el escritor. ${paquete.tokens} tokens estimados`
        + `${paquete.recortes.length ? `, recortado: ${paquete.recortes.join(', ')}` : ''}.`;
  } catch (error) {
    $('cajon-texto').textContent = error.message;
  }
}

$('cajon-cerrar').addEventListener('click', () => cajon.close());
cajon.addEventListener('click', (e) => { if (e.target === cajon) cajon.close(); });

// --------------------------------------------------------------------- rail

function pintarRail() {
  const p = estado.proyecto;
  const pastilla = $('pastilla-estado');
  pastilla.textContent = p?.estado || 'sin brief';
  pastilla.dataset.estado = p?.estado || '';
  $('dato-modo').textContent = p?.camino === 'delegado'
    ? 'orquesta Claude Code' : `modo ${p?.modo || '—'}`;
  $('dato-perfil').textContent = `perfil ${estado.flujo?.perfil || p?.perfil || '—'}`;
  $('barra-run').textContent = p?.canon || 'sin canon';
  $('siguiente-comando').textContent = comandoDe(p);

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
  let proyecto;
  try {
    proyecto = await api.proyecto(estado.camino);
  } catch {
    programar();
    return;
  }
  estado.proyecto = proyecto;
  // La primera respuesta es la que dice por qué camino se abrió.
  if (estado.camino !== proyecto.camino) {
    estado.camino = proyecto.camino;
    document.body.dataset.camino = proyecto.camino;
    pintarConmutador();
  }

  try {
    const flujo = await api.flujo(estado.vistos, estado.camino);
    estado.vistos = flujo.total;
    estado.flujo = flujo;
    taller.pintarDiario(flujo);
    taller.pintarAhora(flujo);
  } catch {
    // Sin motor no hay diario, pero el resto de la página sigue viva.
  }

  brief.pintar(proyecto);
  taller.pintar(proyecto, estado.flujo);
  pintarRail();
  previsualizar();

  const hayLectura = proyecto.capitulos.some((c) => c.legible);
  document.querySelector('.sala[data-sala="lectura"]').disabled = !hayLectura;

  programar();
}

function programar() {
  clearTimeout(temporizador);
  let ritmo = estado.flujo.corriendo ? RITMO_VIVO : RITMO_QUIETO;
  // Por el camino delegado el canon cambia sin avisar, porque lo escribe otra
  // sesión: se relee a ritmo fijo mientras la novela no esté cerrada.
  if (estado.camino === 'delegado') {
    ritmo = ['editado', null, undefined].includes(estado.proyecto?.estado)
      ? RITMO_QUIETO : RITMO_DELEGADO;
  }
  temporizador = setTimeout(() => { if (!document.hidden) refrescar(); else programar(); }, ritmo);
}

// La primera vez se entra por el brief si no hay ninguno, y por el escritorio si
// ya hay libro: lo que toca hacer es distinto y la página no debe hacerlo adivinar.
(async () => {
  await refrescar();
  // #capitulo/3 abre ese capítulo directamente: sirve para volver a donde se
  // estaba leyendo y para enlazar un capítulo concreto.
  const enlace = location.hash.match(/^#capitulo\/(\d+)$/);
  if (enlace && legible(Number(enlace[1]))) await abrirLectura(Number(enlace[1]));
  else if (estado.proyecto?.brief) ir('taller');
  else ir('brief');
})();
