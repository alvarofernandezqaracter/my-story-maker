// El orquestador de la interfaz (§19): guarda el estado que llega del servidor,
// lo reparte a las tres salas y decide cada cuánto vuelve a preguntar.
//
// Ninguna regla del sistema vive aquí. Lo que se ve es lo que el canon de
// el canon dice, y esta página no escribe en él: lo escribe la sesión de
// Claude Code que orquesta (§21).
import { api } from './api.js';
import { crearBrief } from './brief.js';
import { crearTaller } from './taller.js';
import { crearArquitectura } from './arquitectura.js';
import { crearLectura } from './lectura.js';

const $ = (id) => document.getElementById(id);

// Lo que toca hacer según por dónde vaya el proyecto. Siempre es un comando que
// se teclea en otro sitio: quien orquesta es una sesión de Claude Code leyendo
// la skill, y esta página no tiene ningún botón que lo haga por ella.
const COMANDO = {
  borrador: '/orquestar-novela preparar',
  investigado: '/orquestar-novela preparar',
  estructurado: '/orquestar-novela escribir',
  escribiendo: '/orquestar-novela continuar',
  escrito: '/orquestar-novela cerrar',
  retocando: '/orquestar-novela continuar',
  editado: '/orquestar-novela',
  bloqueado: '/orquestar-novela desbloquear el capítulo N',
};

// No hay motor que escuchar: el canon cambia cuando la sesión de Claude Code
// escribe un fichero, y eso solo se ve releyendo el disco.
const RITMO_TRABAJANDO = 2500;
const RITMO_QUIETO = 4000;

const estado = {
  proyecto: null,
  sala: 'brief',
  capitulo: null,
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
  verContexto,
  comandoDe,
};

const brief = crearBrief(ctx);
const taller = crearTaller(ctx);
const arquitectura = crearArquitectura(ctx);
const lectura = crearLectura(ctx);

function comandoDe(proyecto) {
  return COMANDO[proyecto?.estado] || '/orquestar-novela';
}

// ------------------------------------------------------------------ escena

// three.js viaja por CDN, que es lo único de este repo que necesita red. Si no
// llega, la interfaz entera sigue funcionando: la escena es lectura.
//
// Ya no se monta al abrir la página, porque ya no es el fondo de la página: es
// el fondo del brief. Se carga la primera vez que se entra en esa sala y se
// para entera al salir, que es lo mismo que hace el grafo de arquitectura.
let montandoEscena = null;

function montarEscena() {
  if (montandoEscena) return montandoEscena;
  montandoEscena = import('./legajo.js')
    .then(({ crearLegajo }) => crearLegajo($('escena'), { onFoco: alSenalar }))
    .then((instancia) => { escena = instancia; previsualizar(); })
    .catch(() => {
      $('rail-foco').textContent = 'la mesa 3D no ha cargado (sin red)';
    });
  return montandoEscena;
}

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

// Cada sala tiene su enlace, igual que cada capitulo tiene el suyo: #arquitectura
// abre el grafo directamente. Sirve para enviar a alguien a lo que se le quiere
// ensenar sin tener que decirle donde hacer clic.
const SALAS = ['brief', 'taller', 'arquitectura', 'lectura'];

function ir(sala) {
  estado.sala = sala;
  document.body.dataset.sala = sala;
  if (sala !== 'lectura') history.replaceState(null, '', '#' + sala);
  for (const boton of document.querySelectorAll('.sala')) {
    boton.setAttribute('aria-current', boton.dataset.sala === sala ? 'true' : 'false');
  }
  for (const nombre of SALAS) {
    $(`sala-${nombre}`).hidden = nombre !== sala;
  }
  // El grafo tiene su propio bucle de dibujo y se para cuando no se ve: una
  // pestana oculta no tiene por que seguir gastando GPU.
  arquitectura.mostrar(sala === 'arquitectura');
  if (sala === 'brief') montarEscena().then(() => escena?.mostrar(true));
  else escena?.mostrar(false);
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

// -------------------------------------------------- paquete de contexto (§7)

const cajon = $('cajon-contexto');

async function verContexto(numero) {
  $('cajon-titulo').textContent = `Capítulo ${numero}`;
  $('cajon-texto').textContent = 'leyendo…';
  $('cajon-pista').textContent = '';
  if (!cajon.open) cajon.showModal();
  try {
    const paquete = await api.contexto(numero);
    $('cajon-texto').textContent = paquete.texto;
    $('cajon-pista').textContent =
      `${paquete.ruta} — es el paquete con el que se escribió, tal cual quedó en disco.`;
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
    proyecto = await api.proyecto();
  } catch {
    programar();
    return;
  }
  estado.proyecto = proyecto;

  brief.pintar(proyecto);
  taller.pintar(proyecto);
  arquitectura.pintar(proyecto);
  pintarRail();
  previsualizar();

  const hayLectura = proyecto.capitulos.some((c) => c.legible);
  document.querySelector('.sala[data-sala="lectura"]').disabled = !hayLectura;

  programar();
}

function programar() {
  clearTimeout(temporizador);
  // El canon cambia sin avisar, porque lo escribe otra sesión: se relee a ritmo
  // fijo mientras la novela no esté cerrada, y más despacio cuando ya lo está.
  const ritmo = ['editado', null, undefined].includes(estado.proyecto?.estado)
    ? RITMO_QUIETO : RITMO_TRABAJANDO;
  temporizador = setTimeout(() => { if (!document.hidden) refrescar(); else programar(); }, ritmo);
}

// La primera vez se entra por el brief si no hay ninguno, y por el escritorio si
// ya hay libro: lo que toca hacer es distinto y la página no debe hacerlo adivinar.
(async () => {
  await refrescar();
  // #capitulo/3 abre ese capítulo directamente: sirve para volver a donde se
  // estaba leyendo y para enlazar un capítulo concreto.
  const enlace = location.hash.match(/^#capitulo\/(\d+)$/);
  const sala = location.hash.slice(1);
  if (enlace && legible(Number(enlace[1]))) await abrirLectura(Number(enlace[1]));
  else if (SALAS.includes(sala) && sala !== 'lectura') ir(sala);
  else if (estado.proyecto?.brief) ir('taller');
  else ir('brief');
})();
