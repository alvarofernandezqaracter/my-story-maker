// El orquestador de la interfaz (§19): lee la ruta, pide lo que la vista
// necesita, lo reparte a los modulos y decide cada cuanto vuelve a preguntar.
//
// Ninguna regla del sistema vive aqui. Lo que se ve es lo que el canon dice, y
// esta pagina no escribe en el: lo escribe la sesion de Claude Code que
// orquesta (§21).
//
// La forma es la de un gestor de proyectos: un taller con todas las novelas en
// un tablero, y dentro de cada novela un lateral con sus vistas. Cada vista
// tiene su URL, y la URL es lo unico que hay que mandar para ensenar algo.
import { api } from './api.js';
import { crearBrief } from './brief.js';
import { crearTablero } from './tablero.js';
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

// Las vistas de dentro de una novela, en el orden del lateral.
const VISTAS_NOVELA = ['resumen', 'capitulos', 'intentos', 'canon', 'lectura', 'arquitectura'];
const TITULOS = {
  taller: 'Taller',
  encargo: 'Nueva novela',
  resumen: 'Resumen',
  capitulos: 'Capítulos',
  intentos: 'Intentos y gate',
  canon: 'Canon',
  lectura: 'Lectura',
  arquitectura: 'Arquitectura',
};
const TODAS = ['taller', 'encargo', ...VISTAS_NOVELA, 'perdida'];

// No hay motor que escuchar: el canon cambia cuando la sesión de Claude Code
// escribe un fichero, y eso solo se ve releyendo el disco.
const RITMO_TRABAJANDO = 2500;
const RITMO_QUIETO = 4000;

const estado = {
  vista: 'taller',
  novela: null,       // la carpeta de la URL; null fuera de una novela
  proyecto: null,     // /api/proyecto de esa novela, o de la de ahora
  novelas: null,      // /api/novelas
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
  abrirNovela,
  abrirLectura,
  elegirCapitulo,
  inmersion,
  previsualizar,
  verContexto,
  comandoDe,
};

const tablero = crearTablero();
const brief = crearBrief(ctx);
const taller = crearTaller(ctx);
const arquitectura = crearArquitectura(ctx);
const lectura = crearLectura(ctx);

function comandoDe(proyecto) {
  return COMANDO[proyecto?.estado] || '/orquestar-novela';
}

// ------------------------------------------------------------------- rutas

// #/                               el taller
// #/nuevo                          el encargo de una novela nueva
// #/arquitectura                   el grafo, con el canon de la novela en curso
// #/novela/<carpeta>[/<vista>]     una novela; sin vista, su resumen
// #/novela/<carpeta>/lectura/<n>   un capitulo aprobado
//
// Los enlaces de antes siguen valiendo: #arquitectura abre el grafo y
// #capitulo/3 abre ese capitulo de la novela en curso.
function leerRuta(hash) {
  const h = hash.replace(/^#/, '');
  if (h === 'arquitectura') return { vista: 'arquitectura', novela: null };
  if (h === 'brief') return { vista: 'encargo', novela: null };
  const antiguo = h.match(/^capitulo\/(\d+)$/);
  if (antiguo) return { vista: 'lectura', novela: null, capitulo: Number(antiguo[1]) };

  const partes = h.replace(/^\//, '').split('/').filter(Boolean).map(decodeURIComponent);
  if (partes[0] === 'nuevo') return { vista: 'encargo', novela: null };
  if (partes[0] === 'arquitectura') return { vista: 'arquitectura', novela: null };
  if (partes[0] === 'novela' && partes[1]) {
    const vista = VISTAS_NOVELA.includes(partes[2]) ? partes[2] : 'resumen';
    const capitulo = vista === 'lectura' && /^\d+$/.test(partes[3] || '') ? Number(partes[3]) : null;
    return { vista, novela: partes[1], capitulo };
  }
  return { vista: 'taller', novela: null };
}

function rutaDe(novela, vista, capitulo) {
  const base = `#/novela/${encodeURIComponent(novela)}`;
  if (!vista || vista === 'resumen') return base;
  if (vista === 'lectura' && capitulo) return `${base}/lectura/${capitulo}`;
  return `${base}/${vista}`;
}

function ir(vista) {
  if (estado.novela && VISTAS_NOVELA.includes(vista)) location.hash = rutaDe(estado.novela, vista);
  else location.hash = vista === 'encargo' ? '#/nuevo' : '#/';
}

function abrirNovela(nombre) {
  location.hash = rutaDe(nombre);
}

async function abrirLectura(numero) {
  const novela = estado.novela || estado.proyecto?.novela;
  if (!novela) return;
  const destino = rutaDe(novela, 'lectura', numero);
  if (location.hash !== destino) { location.hash = destino; return; }
  await lectura.abrir(numero);
}

async function aplicarRuta() {
  const ruta = leerRuta(location.hash);
  const cambiaNovela = ruta.novela !== estado.novela;
  estado.vista = ruta.vista;
  estado.novela = ruta.novela;
  api.novela = ruta.novela;
  if (cambiaNovela) {
    estado.proyecto = null;
    estado.capitulo = null;
  }

  document.body.dataset.vista = ruta.vista;
  for (const nombre of TODAS) $(`vista-${nombre}`).hidden = nombre !== ruta.vista;
  $('lateral').hidden = !ruta.novela;
  if (ruta.vista !== 'lectura') document.body.dataset.inmersion = 'no';
  pintarNavegacion();

  // El grafo y el legajo tienen su propio bucle de dibujo y se paran cuando no
  // se ven: una vista oculta no tiene por que seguir gastando GPU.
  arquitectura.mostrar(ruta.vista === 'arquitectura');
  if (ruta.vista === 'encargo') montarEscena().then(() => escena?.mostrar(true));
  else escena?.mostrar(false);

  await refrescar();

  if (ruta.vista === 'lectura') {
    // #capitulo/N no nombra novela: se abre en la de ahora, y la URL se pone
    // la de verdad para que lo que se comparta despues diga cual es.
    if (!ruta.novela && estado.proyecto?.novela) {
      location.replace(rutaDe(estado.proyecto.novela, 'lectura', ruta.capitulo));
      return;
    }
    const legibles = (estado.proyecto?.capitulos || []).filter((c) => c.legible);
    const numero = legibles.some((c) => c.numero === ruta.capitulo)
      ? ruta.capitulo
      : (legibles.find((c) => c.numero === estado.capitulo) || legibles[0])?.numero;
    if (numero) await lectura.abrir(numero);
    else pintarSinLectura();
  }
}

window.addEventListener('hashchange', aplicarRuta);

function pintarSinLectura() {
  $('lector-titulo').textContent = 'Todavía no hay ningún capítulo aprobado';
  $('lector-eyebrow').textContent = 'Lectura';
  $('lector-texto').innerHTML = '<p class="vacio">Aquí se lee lo que el gate aprueba y el'
    + ' cronista vuelca en el canon. Un intento descartado sigue en capitulos/ como'
    + ' rastro, pero no es la novela.</p>';
  for (const id of ['lector-notas', 'metadatos', 'ficha-datos', 'ficha-resumen', 'deuda', 'indice']) {
    $(id).textContent = '';
  }
  $('marca-fin').hidden = true;
  $('lector-indice').textContent = '—';
}

// ------------------------------------------------------------- navegacion

function pintarNavegacion() {
  const { vista, novela } = estado;
  for (const enlace of document.querySelectorAll('[data-global]')) {
    const activa = !novela && enlace.dataset.global === vista;
    enlace.setAttribute('aria-current', activa ? 'page' : 'false');
  }
  for (const enlace of document.querySelectorAll('.lateral__enlace')) {
    if (novela) enlace.href = rutaDe(novela, enlace.dataset.vista);
    enlace.setAttribute('aria-current', enlace.dataset.vista === vista ? 'page' : 'false');
  }
  pintarMigas();
}

function pintarMigas() {
  const caja = $('migas');
  caja.textContent = '';
  const trozos = [['Taller', '#/']];
  if (estado.novela) {
    const titulo = estado.proyecto?.brief?.epoca
      || estado.novelas?.novelas.find((n) => n.nombre === estado.novela)?.brief?.epoca
      || estado.novela;
    trozos.push([titulo, rutaDe(estado.novela)]);
  }
  if (estado.vista !== 'taller' && estado.vista !== 'perdida') trozos.push([TITULOS[estado.vista], null]);
  trozos.forEach(([texto, href], i) => {
    if (i) caja.append(Object.assign(document.createElement('span'), { className: 'migas__sep', textContent: '/' }));
    const trozo = document.createElement(href && i < trozos.length - 1 ? 'a' : 'span');
    trozo.textContent = texto;
    if (trozo.tagName === 'A') trozo.href = href;
    caja.append(trozo);
  });
}

function pintarLateral(p) {
  const titulo = p.brief?.epoca || p.novela || estado.novela;
  $('lateral-titulo').textContent = titulo;
  $('lateral-clave').textContent = estado.novela;
  // El avatar de la novela, como el de un proyecto: la inicial del lugar y las
  // dos ultimas cifras del ano, que es lo que se recuerda de un libro.
  const ano = (p.brief?.epoca || '').match(/\b(\d{2})(\d{2})\b/);
  $('lateral-avatar').textContent = (titulo || '?').trim().charAt(0).toUpperCase()
    + (ano ? ano[2] : '');
  const insignia = $('lateral-estado');
  insignia.textContent = p.estado || 'sin canon';
  insignia.dataset.estado = p.estado || '';
  $('siguiente-comando').textContent = comandoDe(p);
  const lectura = document.querySelector('.lateral__enlace[data-vista="lectura"]');
  lectura.dataset.vacio = p.capitulos.some((c) => c.legible) ? 'no' : 'si';
}

function pintarSesion(lanzado) {
  const chip = $('sesion');
  if (!lanzado?.corriendo) { chip.hidden = true; return; }
  chip.hidden = false;
  chip.textContent = `sesión ${lanzado.pid} escribiendo`;
  chip.title = lanzado.lanzado?.log ? `Lo que imprime va a ${lanzado.lanzado.log}` : '';
  chip.href = lanzado.lanzado?.novela ? rutaDe(lanzado.lanzado.novela) : '#/';
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

// Las pestañas del canon: una sola visible, y el resto a un clic.
for (const pestana of document.querySelectorAll('.pestana')) {
  pestana.addEventListener('click', () => {
    for (const otra of document.querySelectorAll('.pestana')) {
      otra.setAttribute('aria-selected', otra === pestana ? 'true' : 'false');
    }
    for (const panel of document.querySelectorAll('[data-panel]')) {
      panel.hidden = panel.dataset.panel !== pestana.dataset.pestana;
    }
  });
}

// ------------------------------------------------------------------ escena

// three.js viaja por CDN, que es lo único de este repo que necesita red. Si no
// llega, la interfaz entera sigue funcionando: la escena es lectura.
//
// Es el legajo del encargo: se monta la primera vez que se entra en esa vista,
// con lo que se va tecleando, y se para entera al salir.
let montandoEscena = null;

function montarEscena() {
  if (montandoEscena) return montandoEscena;
  montandoEscena = import('./legajo.js')
    .then(({ crearLegajo }) => crearLegajo($('escena'), { onFoco: alSenalar }))
    .then((instancia) => { escena = instancia; previsualizar(); })
    .catch(() => {
      $('legajo-foco').textContent = 'el legajo 3D no ha cargado (sin red)';
    });
  return montandoEscena;
}

function textoDeReposo() {
  const b = brief.leer();
  if (!b) return 'el legajo está en blanco';
  return `${b.capitulos || '—'} cuadernillos de ${b.palabras_por_capitulo || '—'} palabras`;
}

function alSenalar(ficha) {
  $('legajo-foco').textContent = ficha ? `cuadernillo ${ficha.numero}` : textoDeReposo();
}

function previsualizar(briefEnCurso) {
  // Es una novela que aun no existe: no tiene capitulos que colorear.
  escena?.actualizar({ brief: briefEnCurso || brief.leer(), capitulos: [] });
  $('legajo-foco').textContent = textoDeReposo();
}

function elegirCapitulo(numero) {
  estado.capitulo = numero;
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

// ---------------------------------------------------------------- refresco

// Cada vista pide lo suyo: el taller y el encargo la biblioteca entera, y las
// vistas de una novela su proyecto. El grafo global y el #capitulo/N de antes,
// que no nombran novela, miran la novela en curso.
async function refrescar() {
  const vista = estado.vista;
  const quiereNovelas = vista === 'taller' || vista === 'encargo' || !estado.novelas;
  const quiereProyecto = Boolean(estado.novela) || vista === 'arquitectura' || vista === 'lectura';

  const [novelas, proyecto, lanzado] = await Promise.all([
    quiereNovelas ? api.novelas().catch((e) => e) : null,
    quiereProyecto ? api.proyecto().catch((e) => e) : null,
    api.lanzamiento().catch(() => null),
  ]);
  pintarSesion(lanzado);
  if (lanzado) brief.pintarLanzamiento(lanzado);

  if (novelas instanceof Error) {
    if (vista === 'taller') tablero.fallo();
  } else if (novelas) {
    estado.novelas = novelas;
    tablero.pintar(novelas);
    brief.pintar(novelas.novelas);
  }

  if (proyecto instanceof Error) {
    // Una carpeta que no esta en la biblioteca no se va a arreglar sola: se
    // dice y no se vuelve a preguntar. Lo demas es un servidor que no contesta.
    if (proyecto.codigo === 404 && estado.novela) {
      for (const nombre of TODAS) $(`vista-${nombre}`).hidden = nombre !== 'perdida';
      $('lateral').hidden = true;
      $('perdida-motivo').textContent = proyecto.message;
      estado.vista = 'perdida';
      document.body.dataset.vista = 'perdida';
      pintarMigas();
      return;
    }
  } else if (proyecto && proyecto.novela === (estado.novela ?? proyecto.novela)) {
    estado.proyecto = proyecto;
    taller.pintar(proyecto);
    arquitectura.pintar(proyecto);
    if (estado.novela) pintarLateral(proyecto);
    $('arquitectura-subtitulo').textContent = proyecto.novela
      ? `El sistema que escribe la novela, con el canon de ${proyecto.brief?.epoca || proyecto.novela} encima.`
      : 'El sistema que escribe la novela. Todavía no hay canon que ponerle encima.';
    pintarMigas();
  } else if (proyecto && !proyecto.novela && !estado.novela) {
    // El grafo global sin ninguna novela en la biblioteca: el sistema se
    // ensena igual, sin canon encima.
    estado.proyecto = proyecto;
    arquitectura.pintar(proyecto);
  }

  programar();
}

function programar() {
  clearTimeout(temporizador);
  // El canon cambia sin avisar, porque lo escribe otra sesión: se relee a ritmo
  // fijo mientras la novela no esté cerrada, y más despacio cuando ya lo está.
  // Con la pestaña oculta no se pregunta nada: se vuelve a mirar al volver.
  const quieto = estado.novela
    ? ['editado', null, undefined].includes(estado.proyecto?.estado)
    : !estado.novelas?.novelas.some((n) => n.sesion || n.capitulos.en_curso);
  temporizador = setTimeout(() => {
    if (!document.hidden) refrescar(); else programar();
  }, quieto ? RITMO_QUIETO : RITMO_TRABAJANDO);
}

document.addEventListener('visibilitychange', () => {
  if (!document.hidden) refrescar();
});

aplicarRuta();
