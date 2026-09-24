// El taller: todas las novelas de biblioteca/ en un tablero por estados, al
// estilo de Jira (§19).
//
// Cada novela es una tarjeta en la columna de su estado de §4. Las tarjetas no
// se arrastran, y no por falta de ganas: mover una novela de columna seria
// escribir su estado, y en el canon escribe el orquestador y nadie mas (§21).
// Lo que hace una tarjeta es abrir su novela.
//
// Todo lo que pinta sale de /api/novelas, que a su vez sale del canon de cada
// carpeta. Lo que una novela aun no tiene se dice y no se rellena.

// Las columnas son los estados de §4, en su orden. `bloqueado` es salida
// lateral y va la ultima, en rojo: es la unica columna de la que no se sale
// sola, y la que pide mano humana.
export const COLUMNAS = [
  { estado: 'borrador', titulo: 'Borrador' },
  { estado: 'investigado', titulo: 'Investigado' },
  { estado: 'estructurado', titulo: 'Estructurado' },
  { estado: 'escribiendo', titulo: 'Escribiendo' },
  { estado: 'escrito', titulo: 'Escrito' },
  { estado: 'retocando', titulo: 'Retocando' },
  { estado: 'editado', titulo: 'Editado' },
  { estado: 'bloqueado', titulo: 'Bloqueado' },
];

const $ = (id) => document.getElementById(id);

function el(etiqueta, clase, texto) {
  const nodo = document.createElement(etiqueta);
  if (clase) nodo.className = clase;
  if (texto !== undefined && texto !== null) nodo.textContent = texto;
  return nodo;
}

function plural(n, uno, varios) {
  return `${n} ${n === 1 ? uno : varios}`;
}

// «hace 5 min» a partir de la fecha de la ultima senal de vida de la carpeta.
export function hace(marca) {
  if (!marca) return '';
  const segundos = Math.max(0, Date.now() / 1000 - marca);
  if (segundos < 60) return 'hace un momento';
  if (segundos < 3600) return `hace ${Math.round(segundos / 60)} min`;
  if (segundos < 86400) return `hace ${Math.round(segundos / 3600)} h`;
  const dias = Math.round(segundos / 86400);
  return dias === 1 ? 'hace un día' : `hace ${dias} días`;
}

// Una columna del tablero: cabecera con su nombre y su cuenta, y el hueco de
// las tarjetas. La usan los dos tableros, el de novelas y el de capitulos.
export function crearColumna({ clave, titulo, cuenta }) {
  const columna = el('section', 'columna');
  columna.dataset.columna = clave;
  columna.setAttribute('role', 'listitem');
  columna.setAttribute('aria-label', `${titulo}: ${cuenta}`);
  const cabecera = el('header', 'columna__cabecera');
  cabecera.append(el('h2', null, titulo), el('span', 'columna__cuenta', String(cuenta)));
  const tarjetas = el('div', 'columna__tarjetas');
  if (!cuenta) tarjetas.append(el('p', 'columna__vacia', 'ninguna'));
  columna.append(cabecera, tarjetas);
  return { columna, tarjetas };
}

export function columnaDe(novela) {
  return COLUMNAS.some((c) => c.estado === novela.estado) ? novela.estado : 'borrador';
}

function tarjeta(novela) {
  const enlace = el('a', 'tarjeta-novela');
  enlace.href = `#/novela/${encodeURIComponent(novela.nombre)}`;
  enlace.dataset.estado = novela.estado || '';
  enlace.dataset.novela = novela.nombre;

  const alto = el('div', 'tarjeta-novela__alto');
  const insignia = el('span', 'insignia', novela.estado || 'sin canon');
  insignia.dataset.estado = novela.estado || '';
  alto.append(insignia);
  const marcas = el('span', 'tarjeta-novela__marcas');
  if (novela.sesion) {
    const sesion = el('span', 'marca-viva', 'sesión');
    sesion.title = 'Hay una sesión de Claude Code arrancada desde aquí escribiendo esta novela';
    marcas.append(sesion);
  }
  if (novela.actual) {
    const actual = el('span', 'etiqueta', 'en curso');
    actual.title = 'Es la novela que se tocó más tarde: la que abre por defecto el orquestador';
    marcas.append(actual);
  }
  alto.append(marcas);

  const brief = novela.brief;
  const titulo = el('h3', 'tarjeta-novela__titulo', brief?.epoca || novela.nombre);
  const premisa = el('p', 'tarjeta-novela__premisa', brief?.premisa
    || 'Sin brief todavía: la carpeta está apartada y el orquestador aún no ha escrito en ella.');
  if (!brief) premisa.dataset.vacio = 'si';
  enlace.append(alto, titulo, premisa);

  if (brief) {
    const datos = [brief.tono, brief.capitulos && `${brief.capitulos} cap. pedidos`,
      brief.palabras_por_capitulo && `${brief.palabras_por_capitulo} pal.`].filter(Boolean);
    enlace.append(el('p', 'tarjeta-novela__datos', datos.join(' · ')));
  }

  const { total, aprobados, en_curso: enCurso, bloqueados } = novela.capitulos;
  const progreso = el('div', 'tarjeta-novela__progreso');
  if (total) {
    const fila = el('div', 'fila-entre');
    fila.append(el('span', null, 'Capítulos'), el('span', null, `${aprobados} / ${total}`));
    const barra = el('div', 'barra-progreso');
    barra.setAttribute('role', 'progressbar');
    barra.setAttribute('aria-valuemin', '0');
    barra.setAttribute('aria-valuemax', String(total));
    barra.setAttribute('aria-valuenow', String(aprobados));
    barra.setAttribute('aria-label', `Capítulos aprobados de ${brief?.epoca || novela.nombre}`);
    if (aprobados === total) barra.dataset.tono = 'ok';
    const relleno = el('span');
    relleno.style.width = `${(aprobados / total) * 100}%`;
    barra.append(relleno);
    progreso.append(fila, barra);
  } else {
    progreso.append(el('span', 'tarjeta-novela__nada', 'sin escaleta todavía'));
  }
  enlace.append(progreso);

  // Lo que pide mirar: un capitulo bloqueado es el unico punto de intervencion
  // humana (§4), y una cuenta del gate que no cuadra es la debilidad de §21
  // hecha dato. Van en rojo porque son lo primero que hay que ver.
  const alertas = [];
  if (bloqueados) alertas.push(['mal', plural(bloqueados, 'capítulo bloqueado', 'capítulos bloqueados')]);
  if (novela.discrepancias) {
    alertas.push(['mal', plural(novela.discrepancias, 'cuenta del gate no cuadra',
      'cuentas del gate no cuadran')]);
  }
  if (enCurso) alertas.push(['vivo', plural(enCurso, 'capítulo en el loop', 'capítulos en el loop')]);
  if (novela.retoques) alertas.push(['bien', 'retoques escritos']);
  for (const [tono, texto] of alertas) {
    const alerta = el('p', 'tarjeta-novela__alerta', texto);
    alerta.dataset.tono = tono;
    enlace.append(alerta);
  }

  const pie = el('div', 'tarjeta-novela__pie');
  pie.append(el('span', 'clave', novela.nombre));
  const cuando = el('span', null, novela.intentos
    ? `${plural(novela.intentos, 'intento', 'intentos')} · ${hace(novela.cuando)}`
    : hace(novela.cuando));
  pie.append(cuando);
  enlace.append(pie);
  return enlace;
}

export function crearTablero() {
  const caja = $('tablero');
  const subtitulo = $('taller-subtitulo');
  const filtro = $('taller-filtro');
  const error = $('taller-error');
  let ultimas = null;

  filtro.addEventListener('input', () => { if (ultimas) pintarTablero(ultimas); });

  function coincide(novela, texto) {
    if (!texto) return true;
    const b = novela.brief || {};
    return [novela.nombre, b.epoca, b.premisa, b.tono]
      .filter(Boolean).some((v) => String(v).toLowerCase().includes(texto));
  }

  function pintarTablero(novelas) {
    caja.textContent = '';
    if (!novelas.length) {
      const vacio = el('div', 'estado-vacio');
      vacio.append(el('h2', null, 'Todavía no hay ninguna novela'));
      vacio.append(el('p', 'pista', 'La biblioteca está vacía. Cada novela nace en su propia'
        + ' carpeta de biblioteca/ en cuanto se lanza.'));
      const boton = el('a', 'boton boton--primario', 'Encarga la primera');
      boton.href = '#/nuevo';
      vacio.append(boton);
      caja.append(vacio);
      return;
    }
    const texto = filtro.value.trim().toLowerCase();
    const visibles = novelas.filter((n) => coincide(n, texto));
    for (const c of COLUMNAS) {
      const suyas = visibles.filter((n) => columnaDe(n) === c.estado);
      const { columna, tarjetas } = crearColumna({
        clave: c.estado, titulo: c.titulo, cuenta: suyas.length,
      });
      for (const n of suyas) tarjetas.append(tarjeta(n));
      caja.append(columna);
    }
  }

  return {
    pintar(datos) {
      error.hidden = true;
      ultimas = datos.novelas;
      const n = ultimas.length;
      const escribiendo = ultimas.filter((x) => ['escribiendo', 'retocando'].includes(x.estado)).length;
      const bloqueadas = ultimas.filter((x) => x.estado === 'bloqueado').length;
      subtitulo.textContent = n
        ? [plural(n, 'novela', 'novelas'), `${escribiendo} en marcha`,
          plural(bloqueadas, 'bloqueada', 'bloqueadas')].join(' · ')
        : 'Las novelas de la biblioteca, por estados';
      pintarTablero(ultimas);
    },
    fallo() {
      // Lo que se ve es lo ultimo que llego: un servidor que no contesta no es
      // motivo para vaciar el tablero, pero si para decirlo.
      error.hidden = false;
      error.textContent = ultimas
        ? 'El servidor no responde; se sigue intentando. Lo que ves es lo último que llegó.'
        : 'No se puede hablar con el servidor: ¿sigue corriendo «python -m novela ui»?';
    },
  };
}
