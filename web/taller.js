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

const $ = (id) => document.getElementById(id);

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
  const relevo = $('relevo');
  const aviso = $('aviso-flujo');
  const arrancar = $('arrancar');
  let ultimoRolVisto = null;
  const rolesVistos = new Set();

  relevo.innerHTML = ROLES.map(
    (r) => `<span class="relevo__rol" data-rol="${r}">${NOMBRE_ROL[r]}</span>`).join('');

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
      await ctx.api.arrancar(accion);
      lista.textContent = '';
      rolesVistos.clear();
      ultimoRolVisto = null;
      await ctx.refrescar();
    } catch (error) {
      decir(error.message);
    }
  }

  arrancar.addEventListener('click', () => lanzar(siguienteAccion()));
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
    todo: 'Escribir la novela',
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
    for (const nodo of relevo.children) {
      const activo = flujo.corriendo && nodo.dataset.rol === ultimoRolVisto;
      nodo.dataset.activo = activo ? 'si' : 'no';
      nodo.dataset.visto = rolesVistos.has(nodo.dataset.rol) ? 'si' : 'no';
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

      const accion = siguienteAccion();
      arrancar.textContent = ETIQUETA_ACCION[accion] || 'Escribir la novela';
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
