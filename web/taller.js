// Las vistas de una novela: resumen, capitulos, intentos y canon (§19).
//
// Las tarjetas son el estado del canon. No hay relato evento a evento porque no
// hay motor que lo emita: lo que ha pasado esta en la conversacion de Claude
// Code, y lo que queda de ello son los ficheros del canon. Esta pagina lee esos
// ficheros y no inventa nada que no este en ellos.
import { crearTrazas } from './trazas.js';
import { crearColumna } from './tablero.js';

// Cómo se lee el estado de una ficha de capítulo cuando se cuenta en una línea.
const ESTADO = {
  aprobado: 'aprobado',
  en_curso: 'en curso',
  bloqueado: 'bloqueado',
  pendiente: 'pendiente',
};

// La media y el rango de una de las tres dimensiones a lo largo del libro. §5
// dice que la dispersión de las tres notas es lo que hay que vigilar para saber
// si juzgar en una sola pasada las estaba correlacionando, así que la tarjeta
// del validador la enseña en vez de repetir que ha pasado por aquí.
function porDimension(p, indice) {
  const conNota = p.capitulos.filter((c) => c.notas);
  if (!conNota.length) return null;
  const notas = conNota.map((c) => c.notas[indice]);
  const media = notas.reduce((a, b) => a + b, 0) / notas.length;
  return { conNota, notas, media, ultimo: conNota[conNota.length - 1] };
}

// Los ocho subagentes de §21: los seis roles de §5 con el validador partido en
// tres, porque los tres se lanzan a la vez y en un mismo mensaje.
//
// Cada uno lleva dos cosas. `produce` es lo que entrega, fijo y distinto en cada
// uno: es lo que separa una tarjeta de otra cuando todavía no ha corrido nada.
// `cuenta` es lo que lleva hecho en este canon, sacado de lo que dejó escrito
// (§19: no hay diario, hay rastro). Devuelve null cuando no ha pasado, y
// entonces no se pinta ninguna línea: ocho tarjetas repitiendo la misma frase
// son ruido con forma de dato.
const SUBAGENTES = [
  {
    id: 'investigador', rol: 'investigador', nombre: 'investigador',
    produce: 'el dossier de época, con categoría, fuente y estado por dato',
    cuenta: (p) => {
      if (!p.dossier.length) return null;
      const verificados = p.dossier.filter((d) => d.estado === 'verificado').length;
      return ['1 intervención, en la preparación',
        `${p.dossier.length} datos · ${verificados} verificados`];
    },
  },
  {
    id: 'arquitecto', rol: 'arquitecto', nombre: 'arquitecto',
    produce: 'la escaleta en tres actos y las fichas de personaje',
    cuenta: (p) => {
      if (!p.capitulos.length) return null;
      return ['1 intervención, en la preparación',
        `${p.capitulos.length} capítulos · ${p.reparto.length} personajes`];
    },
  },
  {
    id: 'escritor', rol: 'escritor', nombre: 'escritor',
    produce: 'el borrador de cada intento, en capitulos/',
    cuenta: (p) => {
      const tocados = p.capitulos.filter((c) => c.intentos);
      if (!tocados.length) return null;
      const total = tocados.reduce((n, c) => n + c.intentos, 0);
      const ultimo = tocados[tocados.length - 1];
      return [`${total} borradores en ${tocados.length} capítulos`,
        `último: cap. ${ultimo.numero}, intento ${ultimo.intentos},`
          + ` ${ESTADO[ultimo.estado] || ultimo.estado}`];
    },
  },
  {
    id: 'validador-continuidad', rol: 'validador', nombre: 'continuidad',
    paralelo: true, dimension: 0,
    produce: 'una nota de 1 a 5 de coherencia con el canon',
  },
  {
    id: 'validador-anacronismos', rol: 'validador', nombre: 'anacronismos',
    paralelo: true, dimension: 1,
    produce: 'una nota de 1 a 5 de época contra el dossier',
  },
  {
    id: 'validador-logica-ritmo', rol: 'validador', nombre: 'lógica y ritmo',
    paralelo: true, dimension: 2,
    produce: 'una nota de 1 a 5 de causa, efecto y tensión',
  },
  {
    id: 'cronista', rol: 'cronista', nombre: 'cronista',
    produce: 'el resumen, los hilos y los cambios de ficha',
    cuenta: (p) => {
      const con = p.capitulos.filter((c) => c.resumen);
      if (!con.length) return null;
      const eventos = p.cronologia.filter((e) => e.capitulo).length;
      return [`${con.length} intervenciones, una por capítulo aprobado`,
        `${eventos} eventos de trama · ${p.deuda.length} hilos vivos`,
        `último resumen: cap. ${con[con.length - 1].numero}`];
    },
  },
  {
    id: 'editor_global', rol: 'editor_global', nombre: 'editor global',
    produce: 'la lista corta de retoques finales',
    cuenta: (p) => (p.retoques
      ? ['1 intervención, al cerrar', `escritos en ${p.ruta_retoques}`]
      : null),
  },
];

// Las tres tarjetas del validador cuentan lo mismo con su propia dimensión, así
// que la función es una y se reparte por índice.
for (const sub of SUBAGENTES) {
  if (sub.dimension === undefined) continue;
  const indice = sub.dimension;
  sub.cuenta = (p) => {
    const d = porDimension(p, indice);
    if (!d) return null;
    const revisados = p.auditoria?.revisados || d.conNota.length;
    return [`${revisados} puntuaciones, una por intento juzgado`,
      `media ${d.media.toFixed(2)} en los aprobados`
        + ` · rango ${Math.min(...d.notas)}–${Math.max(...d.notas)}`,
      `última: ${d.ultimo.notas[indice]} en el cap. ${d.ultimo.numero}`];
  };
}

// La máquina de estados de §4, en su orden. `bloqueado` no ocupa puesto: es
// salida lateral, y se marca sobre el paso donde el proyecto se quedó.
const PASOS = ['borrador', 'investigado', 'estructurado', 'escribiendo', 'escrito',
  'retocando', 'editado'];

// Las columnas del tablero de capítulos: los cuatro estados de una ficha (§3).
const COLUMNAS_CAPITULO = [
  { estado: 'pendiente', titulo: 'Pendiente' },
  { estado: 'en_curso', titulo: 'En curso' },
  { estado: 'aprobado', titulo: 'Aprobado' },
  { estado: 'bloqueado', titulo: 'Bloqueado' },
];

const QUE_TOCA = {
  borrador: 'Toca «preparar»: el investigador levanta el dossier y el arquitecto la escaleta.',
  investigado: 'Hay dossier pero no escaleta. Vuelve a «preparar» para que el arquitecto acabe.',
  estructurado: 'Hay escaleta. Toca «escribir»: el primer capítulo pendiente entra en el loop.',
  escribiendo: 'A mitad del libro. «escribir» sigue por el primer capítulo no aprobado.',
  escrito: 'Todos los capítulos aprobados. Toca «cerrar»: el editor global y los retoques.',
  retocando: 'El editor global ha entregado su lista y el sistema aplica los retoques (§11).',
  editado: 'Terminado: los retoques están aplicados y su desenlace, en retoques.md.',
  bloqueado: 'Hay un capítulo bloqueado. Desbloquéalo y luego reanuda.',
};

// Lo que esta página pediría y el canon no guarda (§19). Se enseña el hueco en
// vez de rellenarlo: un número inventado esconde dónde falta modelo de datos.
const HUECOS = [
  ['cuota del día', 'no hay contabilidad de llamadas ni límite configurado en ningún sitio'],
  ['escenas', 'la unidad de escritura es el capítulo entero mientras DA-09 siga abierta'],
  ['focalizador', 'la ficha de capítulo de §3 no guarda punto de vista'],
  ['gancho final', 'tampoco lo guarda: se lee en el texto y no está como dato'],
  ['coste y tokens', 'el canon en ficheros no guarda lo que costó cada llamada; las trazas'
    + ' reconstruidas tampoco lo inventan, y las del hook viven en Langfuse (§22)'],
  ['citas de las incidencias', 'estado.json guarda la nota y el aviso, no el bloque entero'
    + ' de revisión del validador'],
];

const $ = (id) => document.getElementById(id);

function vacio(texto) {
  const p = document.createElement('p');
  p.className = 'vacio';
  p.textContent = texto;
  return p;
}

function hora(marca) {
  return new Date(marca * 1000).toLocaleTimeString('es-ES', {
    hour: '2-digit', minute: '2-digit', second: '2-digit',
  });
}

function celda(texto, clase) {
  const td = document.createElement('td');
  if (clase) td.className = clase;
  td.textContent = texto;
  return td;
}

function metrica(caja, { nombre, valor, pie, tono, objetivo }) {
  const tarjeta = document.createElement('div');
  tarjeta.className = 'metrica';
  if (tono) tarjeta.dataset.tono = tono;
  const titulo = document.createElement('span');
  titulo.className = 'metrica__nombre';
  titulo.textContent = nombre;
  if (objetivo) {
    const ob = document.createElement('span');
    ob.className = 'etiqueta';
    ob.textContent = objetivo;
    titulo.append(' ', ob);
  }
  const cifra = document.createElement('strong');
  cifra.className = 'metrica__valor';
  cifra.textContent = valor;
  const nota = document.createElement('span');
  nota.className = 'metrica__pie';
  nota.textContent = pie;
  tarjeta.append(titulo, cifra, nota);
  caja.append(tarjeta);
}

function decimal(valor, cifras = 2) {
  return valor.toLocaleString('es-ES', { minimumFractionDigits: cifras, maximumFractionDigits: cifras });
}

export function crearTaller(ctx) {
  const tarjetas = $('tarjetas');
  const agentes = $('agentes');
  const trazas = crearTrazas(ctx);

  // Una tarjeta por subagente, en el orden en que trabajan. Los tres
  // validadores van juntos porque se lanzan en un mismo mensaje (§21).
  for (const sub of SUBAGENTES) {
    const tarjeta = document.createElement('div');
    tarjeta.className = 'agente';
    tarjeta.dataset.rol = sub.rol;
    tarjeta.dataset.sub = sub.id;
    if (sub.paralelo) tarjeta.dataset.paralelo = 'si';
    const alto = document.createElement('div');
    alto.className = 'agente__alto';
    const luz = document.createElement('span');
    luz.className = 'agente__luz';
    const nombre = document.createElement('span');
    nombre.className = 'agente__nombre';
    nombre.textContent = sub.nombre;
    alto.append(luz, nombre);
    const tarea = document.createElement('p');
    tarea.className = 'agente__tarea';
    tarea.textContent = sub.produce;
    const cuenta = document.createElement('p');
    cuenta.className = 'agente__cuenta';
    tarjeta.append(alto, tarea, cuenta);
    agentes.append(tarjeta);
  }

  $('consola-copiar').addEventListener('click', async () => {
    try {
      await navigator.clipboard.writeText($('consola-comando').textContent);
      $('consola-copiar').textContent = 'copiado';
      setTimeout(() => { $('consola-copiar').textContent = 'copiar'; }, 1600);
    } catch {
      $('consola-copiar').textContent = 'cópialo a mano';
    }
  });

  function pintarAgentes(proyecto) {
    for (const nodo of agentes.children) {
      const sub = SUBAGENTES.find((x) => x.id === nodo.dataset.sub);
      // No hay diario que diga quién trabaja ahora mismo, así que lo que se
      // cuenta es lo que cada uno dejó escrito: cuánto entregó y qué fue lo
      // último. La línea que no tiene dato detrás no se pinta.
      const lineas = sub.cuenta?.(proyecto) || null;
      nodo.dataset.activo = 'no';
      nodo.dataset.visto = lineas ? 'si' : 'no';
      const caja = nodo.querySelector('.agente__cuenta');
      caja.textContent = '';
      for (const linea of lineas || []) {
        const fila = document.createElement('span');
        fila.textContent = linea;
        caja.append(fila);
      }
    }
    $('agentes-pista').textContent = 'Los tres validadores se lanzan en un mismo'
      + ' mensaje y no se ven entre sí: esa independencia es lo que permite que un'
      + ' texto brillante caiga por continuidad. La dispersión de sus tres notas es'
      + ' lo que dice si esa independencia está funcionando (§5).';
  }

  function pintarPipeline(proyecto) {
    const caja = $('pipeline');
    caja.textContent = '';
    const estado = proyecto.estado;
    const bloqueado = estado === 'bloqueado';
    // Con el proyecto bloqueado, el paso que se marca es aquel en el que se
    // quedó, que es `escribiendo`: es el único desde el que se bloquea.
    const actual = bloqueado ? 'escribiendo' : estado;
    const alcanzado = PASOS.indexOf(actual);
    PASOS.forEach((paso, i) => {
      const li = document.createElement('li');
      li.className = 'paso';
      li.dataset.orden = String(i + 1).padStart(2, '0');
      li.textContent = paso;
      if (alcanzado >= 0 && i < alcanzado) li.dataset.hecho = 'si';
      if (i === alcanzado) {
        if (bloqueado) li.dataset.bloqueado = 'si'; else li.dataset.actual = 'si';
      }
      caja.append(li);
    });
    if (bloqueado) {
      const li = document.createElement('li');
      li.className = 'paso';
      li.dataset.orden = '!';
      li.dataset.bloqueado = 'si';
      li.textContent = 'bloqueado';
      caja.append(li);
    }
  }

  function pintarLineaEstado(proyecto) {
    const caja = $('linea-estado');
    caja.textContent = '';
    if (!proyecto.brief) {
      caja.textContent = 'sin datos todavía: no hay brief.';
      return;
    }
    const enCurso = proyecto.en_curso;
    const premisa = document.createElement('b');
    premisa.textContent = proyecto.brief.premisa;
    caja.append(premisa, document.createElement('br'));

    // La epoca ya es el titulo de la vista: aqui se diria dos veces.
    caja.append(`${proyecto.brief.tono} · `);
    if (enCurso && enCurso.activo) {
      caja.append(`capítulo ${enCurso.numero} · ${enCurso.titulo} · intento`
        + ` ${enCurso.intentos.length} de ${proyecto.gate.max_intentos}`);
    } else {
      const aprobados = proyecto.capitulos.filter((c) => c.estado === 'aprobado').length;
      caja.append(proyecto.capitulos.length
        ? `${aprobados} de ${proyecto.capitulos.length} capítulos aprobados · ningún capítulo en curso`
        : 'sin escaleta todavía');
    }
    if (proyecto.actualizado) {
      const cuando = document.createElement('span');
      cuando.className = 'dato';
      cuando.textContent = ` · canon escrito el ${proyecto.actualizado.replace('T', ' a las ')}`;
      caja.append(cuando);
    }
  }

  function pintarConsola(proyecto) {
    $('consola').hidden = false;
    $('consola-comando').textContent = ctx.comandoDe(proyecto);
    $('consola-pista').textContent = proyecto.brief
      ? QUE_TOCA[proyecto.estado] || 'Abre Claude Code en este repositorio y pega el comando.'
      : 'Todavía no hay brief. El orquestador te pedirá los cinco campos: no se los'
        + ' inventa, y esta página tampoco los escribe por él.';
  }

  function pintarIntentos(proyecto) {
    const cuerpo = $('cuerpo-intentos');
    const umbrales = $('umbrales');
    cuerpo.textContent = '';
    const g = proyecto.gate;
    umbrales.textContent = g
      ? `umbrales activos — nota mínima ${g.nota_minima} · media mínima ${g.media_minima}`
        + ` · ${g.max_intentos} intentos · una incidencia grave veta por sí sola`
      : 'sin datos todavía';

    const enCurso = proyecto.en_curso;
    $('intentos-titulo').textContent = enCurso
      ? `Intentos del capítulo ${enCurso.numero} · ${enCurso.titulo}` : 'Intentos del capítulo';
    if (enCurso && !enCurso.activo) {
      umbrales.textContent += ` — ningún capítulo en curso ahora mismo; se muestra`
        + ` el último trabajado, el ${enCurso.numero}`;
    }
    if (!enCurso || !enCurso.intentos.length) {
      const fila = document.createElement('tr');
      const hueco = document.createElement('td');
      hueco.colSpan = 6;
      hueco.append(vacio('sin datos todavía: ningún capítulo ha entrado en el loop.'));
      fila.append(hueco);
      cuerpo.append(fila);
      return;
    }
    for (const i of enCurso.intentos) {
      const fila = document.createElement('tr');
      if (i.cuadra === false) fila.dataset.discrepa = 'si';

      const borrador = document.createElement('td');
      const ruta = document.createElement('button');
      ruta.type = 'button';
      ruta.className = 'enlace enlace--ruta';
      ruta.textContent = i.ruta.split('/').pop() || i.ruta;
      ruta.title = i.ruta;
      ruta.addEventListener('click', () => ctx.verContexto(enCurso.numero));
      borrador.append(ruta);
      if (i.palabras) {
        const cuenta = document.createElement('span');
        cuenta.className = 'dato';
        cuenta.textContent = `${i.palabras} pal.`
          + (i.parrafos ? ` · ${i.parrafos} párr.` : '');
        borrador.append(document.createElement('br'), cuenta);
      }

      const vd08 = document.createElement('td');
      const sello = document.createElement('span');
      sello.className = 'vd08';
      sello.dataset.escalon = i.vd08 || 'sin_dato';
      sello.textContent = i.vd08 || '—';
      if (i.avisos?.length) sello.title = i.avisos.join('\n');
      vd08.append(sello);

      const notas = document.createElement('td');
      if (i.notas) {
        const grupo = document.createElement('span');
        grupo.className = 'notas';
        grupo.title = 'continuidad / anacronismos / lógica y ritmo';
        for (const n of i.notas) {
          const nota = document.createElement('span');
          nota.className = 'nota';
          nota.textContent = n;
          if (n >= 4) nota.dataset.alta = 'si';
          if (n < (proyecto.gate?.nota_minima ?? 3)) nota.dataset.baja = 'si';
          grupo.append(nota);
        }
        notas.append(grupo);
        const media = document.createElement('span');
        media.className = 'dato';
        media.textContent = `media ${i.media}`;
        notas.append(document.createElement('br'), media);
      } else {
        notas.textContent = '—';
      }

      const regla = document.createElement('td');
      regla.className = 'operacion';
      regla.textContent = i.regla;
      if (i.motivos?.length) {
        const motivos = document.createElement('span');
        motivos.className = 'dato';
        motivos.textContent = i.motivos.join('; ');
        regla.append(document.createElement('br'), motivos);
      }
      if (i.tipo_reintento) {
        const tipo = document.createElement('span');
        tipo.className = 'dato';
        tipo.textContent = `reintento ${i.tipo_reintento}`;
        regla.append(document.createElement('br'), tipo);
      }

      const veredicto = document.createElement('td');
      const chip = document.createElement('span');
      chip.className = 'veredicto';
      chip.dataset.estado = i.estado;
      chip.textContent = i.estado;
      veredicto.append(chip);
      if (i.cuadra === false) {
        const alerta = document.createElement('span');
        alerta.className = 'discrepa';
        alerta.textContent = 'la cuenta no cuadra';
        veredicto.append(document.createElement('br'), alerta);
      }

      fila.append(celda(String(i.intento)), borrador, vd08, notas, regla, veredicto);
      cuerpo.append(fila);
    }
  }

  function pintarAuditoria(proyecto) {
    const caja = $('auditoria');
    caja.textContent = '';
    if (!proyecto.auditoria) return;
    const { revisados, discrepancias } = proyecto.auditoria;
    const resumen = document.createElement('p');
    resumen.className = 'auditoria__resumen';
    resumen.dataset.tono = discrepancias.length ? 'mal' : 'bien';
    resumen.textContent = revisados
      ? (discrepancias.length
        ? `${discrepancias.length} de ${revisados} cuentas no cuadran con la fórmula de §8.`
        : `Las ${revisados} cuentas del gate cuadran con la fórmula de §8.`)
      : 'sin datos todavía: ningún intento ha llegado al gate.';
    caja.append(resumen);
    if (!discrepancias.length) return;
    const ul = document.createElement('ul');
    for (const d of discrepancias) {
      const li = document.createElement('li');
      li.textContent = `cap. ${d.capitulo} intento ${d.intento}: el canon dice`
        + ` ${d.canon ? 'aprueba' : 'rechaza'} y la fórmula da`
        + ` ${d.formula ? 'aprueba' : 'rechaza'} — ${d.operacion}`;
      ul.append(li);
    }
    caja.append(ul);
  }

  function pintarCronologia(proyecto) {
    const caja = $('cronologia');
    caja.textContent = '';
    $('cuenta-cronologia').textContent = proyecto.cronologia?.length || '';
    if (!proyecto.cronologia?.length) {
      caja.append(vacio('sin datos todavía: el cronista aún no ha escrito ningún evento.'));
      return;
    }
    for (const e of proyecto.cronologia) {
      const li = document.createElement('li');
      li.className = 'evento';
      li.dataset.tipo = e.tipo || 'trama';

      const fecha = document.createElement('time');
      fecha.className = 'evento__fecha';
      fecha.textContent = e.fecha || 'sin fecha';

      const cuerpo = document.createElement('div');
      const texto = document.createElement('p');
      texto.className = 'evento__texto';
      texto.textContent = e.descripcion;
      cuerpo.append(texto);

      const pie = document.createElement('p');
      pie.className = 'evento__pie';
      // VD-05: un evento de trama lleva capítulo y uno histórico no lo lleva.
      pie.textContent = e.capitulo ? `capítulo ${e.capitulo} · ${e.tipo}` : `${e.tipo}`;
      if (e.personajes?.length) pie.textContent += ` · ${e.personajes.join(', ')}`;
      cuerpo.append(pie);

      li.append(fecha, cuerpo);
      if (e.capitulo) {
        li.tabIndex = 0;
        li.addEventListener('click', () => ctx.elegirCapitulo(e.capitulo));
      }
      caja.append(li);
    }
  }

  function pintarReparto(proyecto) {
    const caja = $('reparto');
    caja.textContent = '';
    $('cuenta-reparto').textContent = proyecto.reparto?.length || '';
    if (!proyecto.reparto?.length) {
      caja.append(vacio('sin datos todavía: el arquitecto aún no ha escrito las fichas.'));
      return;
    }
    for (const p of proyecto.reparto) {
      const ficha = document.createElement('article');
      ficha.className = 'personaje';
      ficha.dataset.rol = p.rol || '';

      const alto = document.createElement('div');
      alto.className = 'personaje__alto';
      const nombre = document.createElement('span');
      nombre.className = 'personaje__nombre';
      nombre.textContent = p.nombre || p.id;
      const rol = document.createElement('span');
      rol.className = 'pastilla pastilla--fina';
      rol.textContent = p.rol || 'sin rol';
      alto.append(nombre, rol);
      ficha.append(alto);

      if (p.ubicacion) {
        const donde = document.createElement('p');
        donde.className = 'personaje__donde';
        donde.textContent = p.ubicacion;
        ficha.append(donde);
      }
      // `sabe` es acumulativo y hoy no hay forma de retractar un «Ignora»
      // (DA-14): se cuenta lo que hay y se enseña entero al pasar por encima.
      const sabe = p.sabe || [];
      if (sabe.length) {
        const cuenta = document.createElement('p');
        cuenta.className = 'personaje__sabe';
        cuenta.textContent = `${sabe.length} cosas que sabe o ignora`;
        cuenta.title = sabe.join('\n');
        ficha.append(cuenta);
      }
      caja.append(ficha);
    }
  }

  function pintarLedger(proyecto) {
    const caja = $('ledger');
    caja.textContent = '';
    $('cuenta-dossier').textContent = proyecto.dossier.length || '';
    if (!proyecto.dossier.length) {
      const fila = caja.insertRow();
      const hueco = fila.insertCell();
      hueco.append(vacio('sin datos todavía: el investigador aún no ha pasado.'));
      return;
    }
    const cabecera = caja.createTHead().insertRow();
    for (const titulo of ['Dato', 'Categoría', 'Qué dice', 'Fuente', 'Estado']) {
      const th = document.createElement('th');
      th.textContent = titulo;
      cabecera.append(th);
    }
    const cuerpo = caja.createTBody();
    for (const dato of proyecto.dossier) {
      const fila = cuerpo.insertRow();
      fila.append(celda(dato.id, 'clave'), celda(dato.categoria || '—'),
        celda(dato.dato || '—'), celda(dato.fuente || '—'));
      const estado = document.createElement('td');
      const chip = document.createElement('span');
      chip.className = 'chip';
      chip.dataset.estado = dato.estado;
      chip.textContent = dato.estado || 'sin estado';
      estado.append(chip);
      fila.append(estado);
    }
  }

  // La deuda narrativa: lo que un capitulo abrio y ninguno cerro (§7).
  function pintarHilos(proyecto) {
    const caja = $('hilos');
    caja.textContent = '';
    $('cuenta-hilos').textContent = proyecto.deuda?.length || '';
    if (!proyecto.deuda?.length) {
      const li = document.createElement('li');
      li.append(vacio(proyecto.capitulos.some((c) => c.resumen)
        ? 'Ninguno: todos los hilos abiertos se cerraron.'
        : 'sin datos todavía: el cronista aún no ha escrito ningún resumen.'));
      caja.append(li);
      return;
    }
    for (const h of proyecto.deuda) {
      const li = document.createElement('li');
      const cap = document.createElement('span');
      cap.className = 'etiqueta';
      cap.textContent = `cap. ${h.capitulo}`;
      li.append(cap, ` ${h.hilo}`);
      caja.append(li);
    }
  }

  // Tres de los objetivos de §23 se leen en el canon de una sola novela, y la
  // cuarta cifra es la que da sentido a las otras tres: cuanto va escrito.
  function pintarMetricas(proyecto) {
    const caja = $('metricas');
    caja.textContent = '';
    const total = proyecto.capitulos.length;
    const aprobados = proyecto.capitulos.filter((c) => c.estado === 'aprobado');
    metrica(caja, {
      nombre: 'Capítulos aprobados',
      valor: total ? `${aprobados.length} / ${total}` : '—',
      pie: total ? `${proyecto.brief?.palabras_por_capitulo || '—'} palabras por capítulo`
        : 'sin escaleta todavía',
      tono: total && aprobados.length === total ? 'bien' : null,
    });

    const tocados = proyecto.capitulos.filter((c) => c.intentos);
    const intentos = tocados.reduce((n, c) => n + c.intentos, 0);
    metrica(caja, {
      nombre: 'Intentos por capítulo', objetivo: 'OB-02',
      valor: tocados.length ? decimal(intentos / tocados.length) : '—',
      pie: tocados.length ? `${intentos} en ${tocados.length} · meta ≤ 1,15` : 'ningún capítulo en el loop',
      tono: tocados.length ? (intentos / tocados.length <= 1.15 ? 'bien' : 'aviso') : null,
    });

    const { revisados = 0, discrepancias = [] } = proyecto.auditoria || {};
    metrica(caja, {
      nombre: 'El gate cuadra', objetivo: 'OB-04',
      valor: revisados ? `${Math.round(((revisados - discrepancias.length) / revisados) * 100)} %` : '—',
      pie: revisados ? `${revisados - discrepancias.length} de ${revisados} cuentas · meta 100 %`
        : 'ningún intento ha llegado al gate',
      tono: revisados ? (discrepancias.length ? 'mal' : 'bien') : null,
    });

    const medias = aprobados.map((c) => c.media).filter((m) => typeof m === 'number');
    const minima = proyecto.gate?.media_minima;
    const margen = medias.length && typeof minima === 'number' ? Math.min(...medias) - minima : null;
    metrica(caja, {
      nombre: 'Margen más justo', objetivo: 'OB-07',
      valor: margen === null ? '—' : decimal(margen),
      pie: margen === null ? 'ningún capítulo aprobado'
        : `media del peor aprobado menos ${decimal(minima)} · meta ≥ 0,10`,
      tono: margen === null ? null : (margen >= 0.1 ? 'bien' : 'aviso'),
    });
  }

  function pintarArchivos(proyecto) {
    const caja = $('archivos');
    caja.textContent = '';
    if (!proyecto.archivos.length) {
      caja.append(vacio('sin datos todavía: no hay ningún fichero de trabajo.'));
      return;
    }
    for (const archivo of proyecto.archivos) {
      const li = document.createElement('li');
      const cuando = document.createElement('time');
      cuando.textContent = hora(archivo.cuando);
      const ruta = document.createElement('span');
      ruta.textContent = archivo.ruta;
      li.append(cuando, ruta);
      caja.append(li);
    }
  }

  function pintarHuecos() {
    const caja = $('huecos');
    caja.textContent = '';
    for (const [nombre, porque] of HUECOS) {
      const dt = document.createElement('dt');
      dt.textContent = nombre;
      const dd = document.createElement('dd');
      dd.textContent = porque;
      caja.append(dt, dd);
    }
  }

  function pintarTarjetas(proyecto) {
    tarjetas.textContent = '';
    const aprobados = proyecto.capitulos.filter((c) => c.estado === 'aprobado').length;
    $('capitulos-subtitulo').textContent = proyecto.capitulos.length
      ? `${aprobados} de ${proyecto.capitulos.length} aprobados · la escaleta, por el estado de cada ficha`
      : 'sin datos todavía: el arquitecto aún no ha escrito la escaleta.';
    if (!proyecto.capitulos.length) return;
    const huecos = {};
    for (const col of COLUMNAS_CAPITULO) {
      const suyos = proyecto.capitulos.filter((c) => c.estado === col.estado).length;
      const { columna, tarjetas: hueco } = crearColumna({
        clave: col.estado, titulo: col.titulo, cuenta: suyos,
      });
      huecos[col.estado] = hueco;
      tarjetas.append(columna);
    }
    for (const c of proyecto.capitulos) {
      const tarjeta = document.createElement('button');
      tarjeta.type = 'button';
      tarjeta.className = 'tarjeta';
      tarjeta.dataset.estado = c.estado;
      tarjeta.dataset.capitulo = c.numero;

      const alto = document.createElement('div');
      alto.className = 'tarjeta__alto';
      const num = document.createElement('span');
      num.className = 'tarjeta__num';
      num.textContent = String(c.numero).padStart(2, '0');
      const chip = document.createElement('span');
      chip.className = 'pastilla';
      chip.dataset.estado = c.estado;
      chip.textContent = c.estado;
      alto.append(num, chip);

      const titulo = document.createElement('div');
      titulo.className = 'tarjeta__titulo';
      titulo.textContent = c.titulo;

      // El día de ficción de la ficha: es lo que convierte una lista de
      // capítulos en una novela histórica y no en un índice cualquiera.
      const fecha = document.createElement('div');
      fecha.className = 'tarjeta__fecha';
      if (c.fecha) fecha.textContent = c.fecha;
      else fecha.hidden = true;

      const pie = document.createElement('div');
      pie.className = 'tarjeta__pie';
      if (c.notas) {
        const notas = document.createElement('span');
        notas.className = 'notas';
        notas.title = 'continuidad / anacronismos / lógica y ritmo';
        for (const n of c.notas) {
          const nota = document.createElement('span');
          nota.className = 'nota';
          nota.textContent = n;
          if (n >= 4) nota.dataset.alta = 'si';
          if (n < (proyecto.gate?.nota_minima ?? 3)) nota.dataset.baja = 'si';
          notas.append(nota);
        }
        pie.append(notas);
        const media = document.createElement('span');
        media.textContent = `media ${c.media}`;
        pie.append(media);
      }
      if (c.intentos) {
        const intentos = document.createElement('span');
        intentos.textContent = `${c.intentos} intento${c.intentos > 1 ? 's' : ''}`;
        pie.append(intentos);
      }
      if (c.contexto_tokens) {
        const tokens = document.createElement('span');
        tokens.textContent = `${c.contexto_tokens} tok. de contexto`;
        pie.append(tokens);
      }
      if (c.legible) {
        const leer = document.createElement('span');
        leer.className = 'tarjeta__leer';
        leer.textContent = 'leer →';
        pie.append(leer);
      }

      tarjeta.append(alto, titulo, fecha, pie);

      // Un aprobado se lee; uno que esta o estuvo en el loop se mira por sus
      // intentos, que es lo unico que el canon guarda de el hasta aprobarse.
      if (!c.legible && !c.intentos) tarjeta.disabled = true;
      tarjeta.addEventListener('click', () => {
        ctx.elegirCapitulo(c.numero);
        if (c.legible) ctx.abrirLectura(c.numero);
        else if (c.intentos) ctx.ir('intentos');
      });
      (huecos[c.estado] || huecos.pendiente).append(tarjeta);
    }
  }

  return {
    pintar(proyecto) {
      pintarTarjetas(proyecto);
      pintarPipeline(proyecto);
      pintarLineaEstado(proyecto);
      pintarConsola(proyecto);
      pintarAgentes(proyecto);
      pintarIntentos(proyecto);
      pintarAuditoria(proyecto);
      pintarCronologia(proyecto);
      pintarReparto(proyecto);
      pintarLedger(proyecto);
      pintarHilos(proyecto);
      pintarMetricas(proyecto);
      pintarArchivos(proyecto);
      pintarHuecos();
      trazas.pintar(proyecto);

      $('resumen-titulo').textContent = proyecto.brief?.epoca || proyecto.novela || 'Resumen';
      $('mando-titulo').textContent = proyecto.estado === 'editado'
        ? 'Novela terminada' : 'Los ocho subagentes';
    },
  };
}
