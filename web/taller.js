// Sala del escritorio: ver trabajar a los agentes y ver lo que dejan escrito.
//
// Las tarjetas son el estado del canon. Por el camino del harness el relato es
// el diario que imprime la CLI, evento a evento; por el delegado no hay diario
// que servir —el relato está en la conversación de Claude Code— y lo que cuenta
// lo que ha pasado son los ficheros del canon.
import { crearTrazas } from './trazas.js';

// Los ocho subagentes de §21: los seis roles de §5 con el validador partido en
// tres. Por el camino del harness los tres validadores son el mismo rol, así que
// se colapsan en uno y la pista de abajo lo dice.
const SUBAGENTES = [
  { id: 'investigador', rol: 'investigador', nombre: 'investigador' },
  { id: 'arquitecto', rol: 'arquitecto', nombre: 'arquitecto' },
  { id: 'escritor', rol: 'escritor', nombre: 'escritor' },
  { id: 'validador-continuidad', rol: 'validador', nombre: 'continuidad', paralelo: true },
  { id: 'validador-anacronismos', rol: 'validador', nombre: 'anacronismos', paralelo: true },
  { id: 'validador-logica-ritmo', rol: 'validador', nombre: 'lógica y ritmo', paralelo: true },
  { id: 'cronista', rol: 'cronista', nombre: 'cronista' },
  { id: 'editor_global', rol: 'editor_global', nombre: 'editor global' },
];

const NOMBRE_ROL = {
  investigador: 'investigador',
  arquitecto: 'arquitecto',
  escritor: 'escritor',
  validador: 'validador',
  cronista: 'cronista',
  editor_global: 'editor',
};

const QUE_HACE = {
  investigador: 'levantando el dossier de la época',
  arquitecto: 'montando personajes y escaleta',
  escritor: 'redactando el capítulo',
  validador: 'puntuando su dimensión de 1 a 5',
  cronista: 'volcando el capítulo en el canon',
  editor_global: 'leyendo los resúmenes para los retoques',
};

// Qué deja escrito cada uno en el canon. Es lo que permite decir, sin diario,
// si un rol ya ha pasado por aquí: se mira su rastro, no su llamada.
const RASTRO = {
  investigador: (p) => p.dossier.length > 0,
  arquitecto: (p) => p.capitulos.length > 0,
  escritor: (p) => p.capitulos.some((c) => c.intentos > 0),
  validador: (p) => p.capitulos.some((c) => c.notas),
  cronista: (p) => p.capitulos.some((c) => c.resumen),
  editor_global: (p) => Boolean(p.retoques),
};

// La máquina de estados de §4, en su orden. `bloqueado` no ocupa puesto: es
// salida lateral, y se marca sobre el paso donde el proyecto se quedó.
const PASOS = ['borrador', 'investigado', 'estructurado', 'escribiendo', 'escrito', 'editado'];

const QUE_TOCA = {
  borrador: 'Toca «preparar»: el investigador levanta el dossier y el arquitecto la escaleta.',
  investigado: 'Hay dossier pero no escaleta. Vuelve a «preparar» para que el arquitecto acabe.',
  estructurado: 'Hay escaleta. Toca «escribir»: el primer capítulo pendiente entra en el loop.',
  escribiendo: 'A mitad del libro. «escribir» sigue por el primer capítulo no aprobado.',
  escrito: 'Todos los capítulos aprobados. Toca «cerrar»: el editor global y los retoques.',
  editado: 'Terminado. Los retoques se aplican a mano.',
  bloqueado: 'Hay un capítulo bloqueado. Desbloquéalo y luego reanuda.',
};

// Lo que esta página pediría y el canon no guarda (§19). Se enseña el hueco en
// vez de rellenarlo: un número inventado esconde dónde falta modelo de datos.
const HUECOS = [
  ['cuota del día', 'no hay contabilidad de llamadas ni límite configurado en ningún sitio'],
  ['escenas', 'la unidad de escritura es el capítulo entero mientras DA-09 siga abierta'],
  ['focalizador', 'la ficha de capítulo de §3 no guarda punto de vista'],
  ['gancho final', 'tampoco lo guarda: se lee en el texto y no está como dato'],
];

const HUECOS_DELEGADO = [
  ['coste y tokens', 'el canon en ficheros no guarda lo que costó cada llamada; las trazas'
    + ' reconstruidas tampoco lo inventan'],
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

// Cada evento del diario, a una línea. El texto sigue al de la CLI a propósito:
// quien mire las dos cosas tiene que reconocer lo mismo.
function linea(e) {
  switch (e.tipo) {
    case 'agente':
      return { marca: '›', texto: `${NOMBRE_ROL[e.rol] || e.rol} — ${QUE_HACE[e.rol] || 'trabajando'}`
        + (e.vuelta > 1 ? ` (vuelta ${e.vuelta})` : '') };
    case 'dossier':
      return { marca: '•', texto: `dossier: ${e.datos} datos`, tono: 'bien' };
    case 'escaleta':
      return { marca: '•', texto: `escaleta: ${e.capitulos} capítulos, ${e.personajes} personajes`,
        tono: 'bien' };
    case 'recorte':
      return { marca: '•', texto: `cap. ${e.capitulo}: contexto recortado (${e.bloques.join(', ')})` };
    case 'vd08':
      return { marca: '!', texto: `cap. ${e.capitulo} intento ${e.intento}: VD-08 — ${e.detalles.join('; ')}`,
        tono: 'mal' };
    case 'gate':
      return {
        marca: e.aprueba ? '✓' : '✗',
        tono: e.aprueba ? 'bien' : 'mal',
        texto: `cap. ${e.capitulo} intento ${e.intento}: notas ${e.notas.join('/')}`
          + ` media ${e.media} → ${e.aprueba ? 'aprobado' : `rechazado (${e.motivos.join('; ')})`}`,
      };
    case 'canon':
      return { marca: '•', texto: `cap. ${e.capitulo}: canon actualizado (+${e.hilos_abiertos} hilos,`
        + ` -${e.hilos_cerrados}, ${e.eventos} eventos)`, tono: 'bien' };
    case 'bloqueado':
      return { marca: '✗', tono: 'mal', texto: `cap. ${e.capitulo} BLOQUEADO: ${e.motivo}` };
    case 'parada':
      return { marca: '✗', tono: 'mal', texto: `parada: ${e.motivo}` };
    case 'trazas':
      // Aviso, no error: sin observabilidad la novela se escribe igual (§20).
      return { marca: '!', texto: `trazas: ${e.motivo}` };
    case 'retoques':
      return { marca: '✓', tono: 'bien', texto: `${e.total} retoques en ${e.ruta}` };
    default:
      return { marca: '•', texto: e.tipo };
  }
}

export function crearTaller(ctx) {
  const lista = $('diario');
  const caja = $('diario-caja');
  const tarjetas = $('tarjetas');
  const agentes = $('agentes');
  const aviso = $('aviso-flujo');
  const arrancar = $('arrancar');
  const trazas = crearTrazas(ctx);
  let ultimoRolVisto = null;
  const rolesVistos = new Set();

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
    tarea.textContent = 'en reposo';
    tarjeta.append(alto, tarea);
    agentes.append(tarjeta);
  }

  $('plegar-diario').addEventListener('click', () => {
    const plegado = caja.dataset.plegado === 'si';
    caja.dataset.plegado = plegado ? 'no' : 'si';
    $('plegar-diario').textContent = plegado ? 'plegar' : 'desplegar';
  });

  function decir(mensaje, tono) {
    aviso.hidden = !mensaje;
    aviso.textContent = mensaje || '';
    if (tono) aviso.dataset.tono = tono; else delete aviso.dataset.tono;
  }

  async function lanzar(accion) {
    decir('');
    try {
      await ctx.api.arrancar(accion, ctx.perfilElegido(), ctx.camino);
      lista.textContent = '';
      rolesVistos.clear();
      ultimoRolVisto = null;
      await ctx.refrescar();
    } catch (error) {
      decir(error.message);
    }
  }

  arrancar.addEventListener('click', () => lanzar(siguienteAccion()));
  $('que-toca').addEventListener('click', () => {
    const estado = ctx.estado.proyecto?.estado;
    decir(QUE_TOCA[estado] || 'Todavía no hay brief: empieza por ahí.', 'bien');
  });
  $('solo-preparar').addEventListener('click', () => lanzar('preparar'));
  $('reanudar').addEventListener('click', () => lanzar('reanudar'));
  $('cerrar').addEventListener('click', () => lanzar('cerrar'));

  $('consola-copiar').addEventListener('click', async () => {
    try {
      await navigator.clipboard.writeText($('consola-comando').textContent);
      $('consola-copiar').textContent = 'copiado';
      setTimeout(() => { $('consola-copiar').textContent = 'copiar'; }, 1600);
    } catch {
      $('consola-copiar').textContent = 'cópialo a mano';
    }
  });

  // Qué hace el botón grande depende de por dónde va el proyecto. Es la misma
  // decisión que toma un humano leyendo "novela estado".
  function siguienteAccion() {
    const estado = ctx.estado.proyecto?.estado;
    if (!estado || estado === 'borrador') return 'todo';
    if (estado === 'bloqueado') return 'reanudar';
    if (estado === 'escrito') return 'cerrar';
    if (estado === 'editado') return 'cerrar';
    return 'todo';
  }

  const ETIQUETA_ACCION = {
    todo: 'Lanzar agentes',
    reanudar: 'Reanudar donde se quedó',
    cerrar: 'Cerrar con el editor global',
  };

  function pintarDiario(flujo) {
    for (const evento of flujo.diario) {
      const { marca, texto, tono } = linea(evento);
      const li = document.createElement('li');
      li.dataset.marca = marca;
      if (tono) li.dataset.tono = tono;
      li.append(document.createTextNode(texto));
      lista.append(li);
      if (evento.tipo === 'agente') {
        ultimoRolVisto = evento.rol;
        rolesVistos.add(evento.rol);
      }
    }
    if (flujo.diario.length) lista.scrollTop = lista.scrollHeight;
  }

  function pintarAhora(flujo) {
    const ahora = $('ahora');
    ahora.hidden = !flujo.corriendo || !ultimoRolVisto;
    if (!ahora.hidden) {
      $('ahora-rol').textContent = NOMBRE_ROL[ultimoRolVisto] || ultimoRolVisto;
      $('ahora-que').textContent = QUE_HACE[ultimoRolVisto] || '';
    }
  }

  // ------------------------------------------------------- componentes

  function pintarAgentes(proyecto, flujo) {
    const delegado = proyecto.camino === 'delegado';
    for (const nodo of agentes.children) {
      const rol = nodo.dataset.rol;
      // Con el harness corriendo, el diario dice quién trabaja ahora mismo. Sin
      // él, lo único honesto es decir quién ha dejado rastro en el canon.
      const activo = flujo.corriendo && rol === ultimoRolVisto;
      const trabajado = delegado
        ? Boolean(RASTRO[rol]?.(proyecto))
        : rolesVistos.has(rol);
      nodo.dataset.activo = activo ? 'si' : 'no';
      nodo.dataset.visto = trabajado ? 'si' : 'no';
      nodo.querySelector('.agente__tarea').textContent = activo
        ? QUE_HACE[rol]
        : (trabajado
          ? (delegado ? 'ha dejado su rastro en el canon' : 'ha trabajado en esta pasada')
          : 'en reposo');
    }
    $('agentes-pista').textContent = delegado
      ? 'Los tres validadores se lanzan en un mismo mensaje y no se ven entre sí: esa'
        + ' independencia es lo que permite que un texto brillante caiga por continuidad.'
      : 'El harness llama a un solo validador salvo que el perfil ponga'
        + ' validador.modo en «separado»; los tres nombres son sus tres dimensiones.';
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

    const epoca = document.createElement('span');
    epoca.className = 'linea-estado__epoca';
    epoca.textContent = proyecto.brief.epoca;
    caja.append(epoca, document.createElement('br'));

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
    const consola = $('consola');
    const delegado = proyecto.camino === 'delegado';
    consola.hidden = !delegado;
    $('mandos-harness').hidden = delegado;
    if (!delegado) return;
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
    const panel = $('panel-auditoria');
    const caja = $('auditoria');
    panel.hidden = !proyecto.auditoria;
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
    if (!proyecto.dossier.length) {
      caja.append(vacio('sin datos todavía: el investigador aún no ha pasado.'));
      return;
    }
    for (const dato of proyecto.dossier) {
      const chip = document.createElement('span');
      chip.className = 'chip';
      chip.dataset.estado = dato.estado;
      chip.textContent = dato.id;
      chip.title = [dato.categoria, dato.estado, dato.fuente && `fuente: ${dato.fuente}`,
        dato.dato].filter(Boolean).join(' · ');
      caja.append(chip);
    }
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

  function pintarHuecos(proyecto) {
    const caja = $('huecos');
    caja.textContent = '';
    const todos = proyecto.camino === 'delegado'
      ? [...HUECOS, ...HUECOS_DELEGADO] : HUECOS;
    for (const [nombre, porque] of todos) {
      const dt = document.createElement('dt');
      dt.textContent = nombre;
      const dd = document.createElement('dd');
      dd.textContent = porque;
      caja.append(dt, dd);
    }
  }

  function pintarOrigen(proyecto, flujo) {
    const caja = $('origen-eventos');
    if (proyecto.camino === 'delegado') {
      caja.textContent = 'el relato de esta pasada está en la sesión de Claude Code;'
        + ' aquí se ve lo que quedó escrito';
      return;
    }
    if (flujo.corriendo) {
      caja.textContent = `flujo en marcha: ${flujo.accion}`;
    } else if (proyecto.en_curso && !flujo.total) {
      caja.textContent = 'hay un capítulo en curso lanzado fuera de esta interfaz: aquí no hay stream';
    } else {
      caja.textContent = flujo.total ? 'última pasada' : 'sin eventos todavía';
    }
  }

  function pintarTarjetas(proyecto) {
    tarjetas.textContent = '';
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

      if (c.estado === 'bloqueado' && proyecto.camino === 'harness') {
        const desbloquear = document.createElement('span');
        desbloquear.className = 'enlace';
        desbloquear.textContent = 'desbloquear y reintentar';
        desbloquear.addEventListener('click', async (e) => {
          e.stopPropagation();
          try {
            await ctx.api.desbloquear({ capitulo: c.numero, modo: 'reintentar' }, ctx.camino);
            await ctx.refrescar();
            decir(`Capítulo ${c.numero} desbloqueado. Dale a reanudar.`, 'bien');
          } catch (error) {
            decir(error.message);
          }
        });
        tarjeta.append(desbloquear);
      }

      tarjeta.addEventListener('click', () => {
        ctx.elegirCapitulo(c.numero);
        if (c.legible) ctx.abrirLectura(c.numero);
      });
      tarjetas.append(tarjeta);
    }
  }

  return {
    pintar(proyecto, flujo) {
      pintarTarjetas(proyecto);
      pintarPipeline(proyecto);
      pintarLineaEstado(proyecto);
      pintarConsola(proyecto);
      pintarAgentes(proyecto, flujo);
      pintarIntentos(proyecto);
      pintarAuditoria(proyecto);
      pintarCronologia(proyecto);
      pintarReparto(proyecto);
      pintarLedger(proyecto);
      pintarArchivos(proyecto);
      pintarHuecos(proyecto);
      pintarOrigen(proyecto, flujo);
      trazas.pintar(proyecto);

      const delegado = proyecto.camino === 'delegado';
      const accion = siguienteAccion();
      arrancar.textContent = ETIQUETA_ACCION[accion] || 'Lanzar agentes';
      const sinBrief = !proyecto.brief;
      arrancar.disabled = flujo.corriendo || sinBrief;
      for (const id of ['solo-preparar', 'reanudar', 'cerrar']) {
        $(id).disabled = flujo.corriendo || sinBrief;
      }

      $('mando-eyebrow').textContent = delegado
        ? 'Escritorio · orquesta Claude Code' : 'Escritorio · orquesta el harness';
      $('mando-titulo').textContent = flujo.corriendo ? 'Los agentes trabajando'
        : (proyecto.estado === 'editado' ? 'Novela terminada'
          : (delegado ? 'Los ocho subagentes' : 'Los seis agentes'));
      $('mando-texto').textContent = delegado
        ? 'Investigador y arquitecto preparan el libro; luego, capítulo a capítulo, el'
          + ' escritor redacta, los tres validadores puntúan a la vez, el gate decide y'
          + ' el cronista escribe en el canon. Ninguno escribe el canon: escribe el'
          + ' orquestador con la propuesta ya comprobada delante.'
        : 'Investigador y arquitecto preparan el libro; luego, capítulo a capítulo, el'
          + ' escritor redacta, el validador puntúa, el gate decide y el cronista'
          + ' escribe en el canon.';

      if (delegado) {
        decir(proyecto.brief ? '' : 'Todavía no hay canon delegado. Abre Claude Code en'
          + ' este repositorio y lanza /orquestar-novela: te pedirá los cinco campos.');
      } else if (sinBrief) {
        decir('Primero el brief: sin él, el investigador no tiene de qué tirar.');
      } else if (flujo.error) {
        decir(`${flujo.error}${flujo.detalles.length ? ` — ${flujo.detalles.join('; ')}` : ''}`);
      } else if (!flujo.corriendo && proyecto.estado === 'editado') {
        decir('Novela terminada. Los retoques se aplican a mano, y los capítulos se'
          + ' leen en la pestaña de lectura.', 'bien');
      } else {
        decir('');
      }
    },
    pintarDiario,
    pintarAhora,
  };
}
