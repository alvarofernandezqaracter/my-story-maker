// Sala del taller: lanzar el flujo y verlo pasar. Las tarjetas son el estado
// del canon; el diario es el mismo que imprime la CLI, evento a evento.

const ROLES = ['investigador', 'arquitecto', 'escritor', 'validador', 'cronista', 'editor_global'];

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
  validador: 'puntuando continuidad, anacronismos y ritmo',
  cronista: 'volcando el capítulo en el canon',
  editor_global: 'leyendo los resúmenes para los retoques',
};

// La maquina de estados de §4, en su orden. `bloqueado` no ocupa puesto: es
// salida lateral, y se marca sobre el paso donde el proyecto se quedo.
const PASOS = ['borrador', 'investigado', 'estructurado', 'escribiendo', 'escrito', 'editado'];

const QUE_TOCA = {
  borrador: 'Toca «preparar»: el investigador levanta el dossier y el arquitecto la escaleta.',
  investigado: 'Hay dossier pero no escaleta. Vuelve a «preparar» para que el arquitecto acabe.',
  estructurado: 'Hay escaleta. Toca «escribir»: el primer capítulo pendiente entra en el loop.',
  escribiendo: 'A mitad del libro. «escribir» sigue por el primer capítulo no aprobado.',
  escrito: 'Todos los capítulos aprobados. Toca «cerrar»: el editor global y retoques.md.',
  editado: 'Terminado. Los retoques están en retoques.md y se aplican a mano.',
  bloqueado: 'Hay un capítulo bloqueado. Desbloquéalo desde su tarjeta y luego «reanudar».',
};

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

// Cada evento del diario, a una linea. El texto sigue al de la CLI a proposito:
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
  let ultimoRolVisto = null;
  const rolesVistos = new Set();

  // Una tarjeta por agente de §5, en el orden en que trabajan.
  for (const rol of ROLES) {
    const tarjeta = document.createElement('div');
    tarjeta.className = 'agente';
    tarjeta.dataset.rol = rol;
    const alto = document.createElement('div');
    alto.className = 'agente__alto';
    const luz = document.createElement('span');
    luz.className = 'agente__luz';
    const nombre = document.createElement('span');
    nombre.className = 'agente__nombre';
    nombre.textContent = NOMBRE_ROL[rol];
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
      await ctx.api.arrancar(accion, ctx.perfilElegido());
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

  // Que hace el boton grande depende de por donde va el proyecto. Es la misma
  // decision que toma un humano leyendo "novela estado".
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
    for (const nodo of agentes.children) {
      const rol = nodo.dataset.rol;
      const activo = flujo.corriendo && rol === ultimoRolVisto;
      nodo.dataset.activo = activo ? 'si' : 'no';
      nodo.dataset.visto = rolesVistos.has(rol) ? 'si' : 'no';
      nodo.querySelector('.agente__tarea').textContent = activo
        ? QUE_HACE[rol]
        : (rolesVistos.has(rol) ? 'ha trabajado en esta pasada' : 'en reposo');
    }
  }

  // ------------------------------------------------------- componentes

  function pintarPipeline(proyecto) {
    const caja = $('pipeline');
    caja.textContent = '';
    const estado = proyecto.estado;
    const bloqueado = estado === 'bloqueado';
    // Con el proyecto bloqueado, el paso que se marca es aquel en el que se
    // quedo, que es `escribiendo`: es el unico desde el que se bloquea.
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
    if (enCurso && enCurso.activo) {
      caja.append(`capítulo ${enCurso.numero} · ${enCurso.titulo} · iteración`
        + ` ${enCurso.intentos.length} de ${proyecto.gate.max_intentos}`);
    } else {
      const aprobados = proyecto.capitulos.filter((c) => c.estado === 'aprobado').length;
      caja.append(proyecto.capitulos.length
        ? `${aprobados} de ${proyecto.capitulos.length} capítulos aprobados · ningún capítulo en curso`
        : 'sin escaleta todavía');
    }
  }

  function pintarIntentos(proyecto) {
    const cuerpo = $('cuerpo-intentos');
    const umbrales = $('umbrales');
    cuerpo.textContent = '';
    const g = proyecto.gate;
    umbrales.textContent = g
      ? `umbrales activos — nota mínima ${g.nota_minima} · media mínima ${g.media_minima}`
        + ` · ${g.max_intentos} intentos · una incidencia grave veta`
      : 'sin datos todavía';

    const enCurso = proyecto.en_curso;
    if (enCurso && !enCurso.activo) {
      umbrales.textContent += ` — ningún capítulo en curso ahora mismo; se muestra`
        + ` el último trabajado, el ${enCurso.numero}`;
    }
    if (!enCurso || !enCurso.intentos.length) {
      const fila = document.createElement('tr');
      const celda = document.createElement('td');
      celda.colSpan = 5;
      celda.append(vacio('sin datos todavía: no hay ningún capítulo en curso.'));
      fila.append(celda);
      cuerpo.append(fila);
      return;
    }
    for (const i of enCurso.intentos) {
      const fila = document.createElement('tr');
      const celdas = [
        String(i.intento),
        i.ruta,
        i.media !== null ? `${i.media} (${i.notas.join('/')})` : '—',
        i.regla,
      ].map((texto) => {
        const td = document.createElement('td');
        td.textContent = texto;
        return td;
      });
      const veredicto = document.createElement('td');
      const chip = document.createElement('span');
      chip.className = 'veredicto';
      chip.dataset.estado = i.estado;
      chip.textContent = i.estado;
      veredicto.append(chip);
      fila.append(...celdas, veredicto);
      cuerpo.append(fila);
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
      chip.title = `${dato.categoria} · ${dato.estado}`;
      caja.append(chip);
    }
  }

  function pintarArchivos(proyecto) {
    const caja = $('archivos');
    caja.textContent = '';
    if (!proyecto.archivos.length) {
      caja.append(vacio('sin datos todavía: el harness no ha escrito ningún fichero.'));
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

  function pintarOrigen(proyecto, flujo) {
    const caja = $('origen-eventos');
    if (flujo.corriendo) {
      caja.textContent = `flujo en marcha: ${flujo.accion}`;
    } else if (proyecto.en_curso && !flujo.total) {
      // El canon dice que hay un capitulo a medias pero esta interfaz no lo
      // lanzo: no hay stream que ensenar y conviene decirlo.
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
      if (c.legible) {
        const leer = document.createElement('span');
        leer.textContent = 'leer →';
        leer.style.color = 'var(--qa-naranja)';
        pie.append(leer);
      }

      tarjeta.append(alto, titulo, pie);

      if (c.estado === 'bloqueado') {
        const desbloquear = document.createElement('span');
        desbloquear.className = 'enlace';
        desbloquear.textContent = 'desbloquear y reintentar';
        desbloquear.addEventListener('click', async (e) => {
          e.stopPropagation();
          try {
            await ctx.api.desbloquear({ capitulo: c.numero, modo: 'reintentar' });
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
      pintarIntentos(proyecto);
      pintarLedger(proyecto);
      pintarArchivos(proyecto);
      pintarOrigen(proyecto, flujo);

      const accion = siguienteAccion();
      arrancar.textContent = ETIQUETA_ACCION[accion] || 'Lanzar agentes';
      const sinBrief = !proyecto.brief;
      arrancar.disabled = flujo.corriendo || sinBrief;
      for (const id of ['solo-preparar', 'reanudar', 'cerrar']) {
        $(id).disabled = flujo.corriendo || sinBrief;
      }

      $('mando-titulo').textContent = flujo.corriendo ? 'Los agentes trabajando'
        : (proyecto.estado === 'editado' ? 'Novela terminada' : 'Los seis agentes');

      if (sinBrief) {
        decir('Primero el brief: sin él, el investigador no tiene de qué tirar.');
      } else if (flujo.error) {
        decir(`${flujo.error}${flujo.detalles.length ? ` — ${flujo.detalles.join('; ')}` : ''}`);
      } else if (!flujo.corriendo && proyecto.estado === 'editado') {
        decir('Novela terminada. Los retoques están en retoques.md, y los capítulos'
          + ' se leen en la pestaña de lectura.', 'bien');
      }
    },
    pintarDiario,
    pintarAhora,
  };
}
