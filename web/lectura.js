// Sala de lectura: el capitulo aprobado, tal y como quedo en capitulos/.
//
// Solo se leen capitulos aprobados. Un intento descartado sigue en disco como
// rastro (§6), pero no es la novela.

const $ = (id) => document.getElementById(id);

const DIMENSIONES = ['continuidad', 'anacronismos', 'lógica y ritmo'];

// Las tres dimensiones viajan con su nombre interno; en la pagina se leen.
const NOMBRE_DIMENSION = {
  continuidad: 'continuidad',
  anacronismos: 'anacronismos',
  logica_ritmo: 'lógica y ritmo',
};

function escapar(texto) {
  return texto.replace(/[&<>]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c]));
}

// Los capitulos son Markdown sencillo: un titulo y parrafos. No hace falta una
// biblioteca para eso, y asi la pagina no baja nada mas.
function aHtml(markdown) {
  return markdown
    .replace(/\r\n/g, '\n')
    // El escritor deja marcas en comentario HTML cuando reescribe sobre las
    // incidencias del intento anterior: son notas del orquestador para el propio
    // agente, no prosa de la novela.
    .replace(/<!--[\s\S]*?-->/g, '')
    .split(/\n{2,}/)
    .map((bloque) => {
      const t = bloque.trim();
      if (!t) return '';
      // El titulo del capitulo ya va en la cabecera del lector.
      if (t.startsWith('# ')) return '';
      // Separador de escena, si el escritor lo puso: nadie obliga a
      // ninguno porque la unidad de escritura es el capitulo entero (DA-09).
      if (/^(\*\s*){3,}$|^-{3,}$|^_{3,}$/.test(t)) {
        return '<p class="separador-escena" aria-hidden="true">❦</p>';
      }
      if (/^#{2,6} /.test(t)) return `<h3>${escapar(t.replace(/^#+\s*/, ''))}</h3>`;
      return `<p>${escapar(t).replace(/\n/g, '<br>')}</p>`;
    })
    .join('');
}

// La capitular va sobre el primer párrafo de verdad del capítulo, y solo si
// empieza por letra: una raya de diálogo o unas comillas no se dibujan bien a
// cuatro líneas de alto y quedarían peor que sin adorno.
function ponerCapitular(caja) {
  const primero = caja.querySelector('p:not(.separador-escena)');
  if (primero && /^[\p{L}]/u.test(primero.textContent.trim())) {
    primero.classList.add('capitular');
  }
}

// Lo que el canon no sabe se sigue diciendo, pero una vez (§19). Escenas,
// focalizador y gancho final no existen en el modelo de datos -la unidad de
// escritura sigue siendo el capitulo entero (DA-09) y la ficha no guarda punto
// de vista-, y repetir «sin datos todavia» cuatro veces seguidas tapaba los dos
// campos que si tenian valor. Los vacios se cuentan en una linea y el detalle de
// cuales son se lee al pasar por encima.
function pintarDatos(caja, hueco, campos) {
  caja.textContent = '';
  const pendientes = [];
  for (const [nombre, valor] of campos) {
    if (valor === null || valor === undefined || valor === '') {
      pendientes.push(nombre);
      continue;
    }
    const dt = document.createElement('dt');
    dt.textContent = nombre;
    const dd = document.createElement('dd');
    dd.textContent = String(valor);
    caja.append(dt, dd);
  }
  hueco.hidden = pendientes.length === 0;
  hueco.textContent = pendientes.length === 1
    ? '1 campo pendiente' : `${pendientes.length} campos pendientes`;
  hueco.title = `${pendientes.join(', ')} — el canon no los guarda todavía (§19)`;
}

export function crearLectura(ctx) {
  const sala = $('sala-lectura');
  const texto = $('lector-texto');
  let capitulo = null;

  function numerosLegibles() {
    return (ctx.estado.proyecto?.capitulos || []).filter((c) => c.legible).map((c) => c.numero);
  }

  function pintarNotas(datos) {
    const caja = $('lector-notas');
    caja.textContent = '';
    if (!datos.notas) return;
    const notas = document.createElement('span');
    notas.className = 'notas';
    notas.title = DIMENSIONES.join(' / ');
    datos.notas.forEach((n, i) => {
      const nota = document.createElement('span');
      nota.className = 'nota';
      nota.textContent = n;
      nota.title = `${DIMENSIONES[i]}: ${n}`;
      if (n >= 4) nota.dataset.alta = 'si';
      notas.append(nota);
    });
    const media = document.createElement('span');
    media.className = 'dato';
    media.textContent = `media ${datos.media} · ${datos.palabras} palabras · intento ${datos.intento}`;
    caja.append(notas, media);
  }

  function pintarFicha(datos) {
    const caja = $('ficha-resumen');
    caja.textContent = '';
    if (datos.resumen) {
      const p = document.createElement('p');
      p.textContent = datos.resumen;
      caja.append(p);
    }
    const hilos = [
      ...datos.hilos_abiertos.map((h) => ({ texto: h, cerrado: false })),
      ...datos.hilos_cerrados.map((h) => ({ texto: h, cerrado: true })),
    ];
    if (hilos.length) {
      const titulo = document.createElement('p');
      titulo.innerHTML = '<strong>Hilos</strong>';
      const ul = document.createElement('ul');
      for (const h of hilos) {
        const li = document.createElement('li');
        li.textContent = h.texto;
        if (h.cerrado) li.className = 'hilo-cerrado';
        ul.append(li);
      }
      caja.append(titulo, ul);
    }
    // El canon delegado no guarda el bloque entero de revisión, solo la nota y
    // los avisos que el orquestador arrastró. Se enseña lo que hay.
    if (datos.avisos?.length) {
      const titulo = document.createElement('p');
      titulo.innerHTML = '<strong>Avisos del gate</strong>';
      const ul = document.createElement('ul');
      for (const a of datos.avisos) {
        const li = document.createElement('li');
        li.textContent = a;
        ul.append(li);
      }
      caja.append(titulo, ul);
    }
    for (const r of datos.revisiones || []) {
      const incidencias = r.incidencias || [];
      if (!incidencias.length) continue;
      const titulo = document.createElement('p');
      titulo.innerHTML = `<strong>${escapar(NOMBRE_DIMENSION[r.dimension] || r.dimension)}</strong>`;
      const ul = document.createElement('ul');
      for (const i of incidencias) {
        const li = document.createElement('li');
        li.textContent = `${i.severidad}: ${i.sugerencia || i.cita || ''}`;
        ul.append(li);
      }
      caja.append(titulo, ul);
    }
  }

  function pintarIndice(numero) {
    const caja = $('indice');
    caja.textContent = '';
    const capitulos = ctx.estado.proyecto?.capitulos || [];
    if (!capitulos.length) {
      const p = document.createElement('p');
      p.className = 'vacio';
      p.textContent = 'sin datos todavía: no hay escaleta.';
      caja.append(p);
      return;
    }
    for (const c of capitulos) {
      const entrada = document.createElement('button');
      entrada.type = 'button';
      entrada.className = 'indice__entrada';
      entrada.dataset.estado = c.estado;
      if (c.numero === numero) entrada.dataset.actual = 'si';
      entrada.disabled = !c.legible;

      const lomo = document.createElement('span');
      lomo.className = 'indice__lomo';

      const cuerpo = document.createElement('span');
      const titulo = document.createElement('span');
      titulo.className = 'indice__titulo';
      titulo.textContent = `${String(c.numero).padStart(2, '0')} · ${c.titulo}`;
      const datos = document.createElement('span');
      datos.className = 'indice__datos';
      // Las escenas no existen en el canon (DA-09) y el indice lo repetia seis
      // veces sin decir nada. Se declara una vez, en el panel de huecos (§19).
      datos.textContent = [
        c.media !== null ? `media ${c.media}` : 'sin nota',
        c.palabras ? `${c.palabras} pal.` : `${c.palabras_objetivo} pal. objetivo`,
      ].join(' · ');
      cuerpo.append(titulo, document.createElement('br'), datos);

      entrada.append(lomo, cuerpo);
      entrada.addEventListener('click', () => ctx.abrirLectura(c.numero));
      caja.append(entrada);
    }
  }

  function pintarMetadatos(datos) {
    pintarDatos($('metadatos'), $('metadatos-pendientes'), [
      ['focalizador', null],
      ['día de ficción', datos.fecha],
      ['acto', datos.acto],
      ['palabras', datos.palabras],
    ]);
  }

  function pintarFichaDatos(datos) {
    pintarDatos($('ficha-datos'), $('ficha-pendientes'), [
      ['media', datos.media],
      ['palabras', datos.palabras],
      ['intento aprobado', datos.intento],
      ['focalizador por escena', null],
      ['escenas', null],
      ['gancho final', null],
    ]);
  }

  // Deuda narrativa: los hilos que un capitulo abrio y ninguno posterior cerro.
  function pintarDeuda() {
    const caja = $('deuda');
    caja.textContent = '';
    const deuda = ctx.estado.proyecto?.deuda || [];
    if (!deuda.length) {
      const p = document.createElement('p');
      p.textContent = 'Ninguna: todos los hilos abiertos se cerraron.';
      caja.append(p);
      return;
    }
    const ul = document.createElement('ul');
    for (const d of deuda) {
      const li = document.createElement('li');
      li.textContent = `cap. ${d.capitulo}: ${d.hilo}`;
      ul.append(li);
    }
    caja.append(ul);
  }

  async function abrir(numero) {
    try {
      capitulo = await ctx.api.capitulo(numero);
    } catch (error) {
      texto.innerHTML = `<p>${escapar(error.message)}</p>`;
      return;
    }
    $('lector-eyebrow').textContent = `Capítulo ${capitulo.numero} · acto ${capitulo.acto}`
      + (capitulo.fecha ? ` · ${capitulo.fecha}` : '');
    $('lector-titulo').textContent = capitulo.titulo;
    texto.innerHTML = aHtml(capitulo.texto);
    ponerCapitular(texto);
    pintarNotas(capitulo);
    pintarMetadatos(capitulo);
    pintarFichaDatos(capitulo);
    pintarFicha(capitulo);
    pintarDeuda();
    pintarIndice(numero);
    $('marca-fin').hidden = false;

    const legibles = numerosLegibles();
    const i = legibles.indexOf(numero);
    $('lector-indice').textContent = `${i + 1} de ${legibles.length}`;
    $('anterior').disabled = i <= 0;
    $('siguiente').disabled = i < 0 || i >= legibles.length - 1;
    $('lector-pie').textContent = capitulo.resumen
      ? `Lo que el cronista dejó escrito: ${capitulo.resumen}` : '';

    sala.scrollTop = 0;
    ctx.elegirCapitulo(numero);
    ctx.escena?.modoLectura(true, 0);
  }

  function saltar(paso) {
    const legibles = numerosLegibles();
    const i = legibles.indexOf(capitulo?.numero);
    const destino = legibles[i + paso];
    if (destino) ctx.abrirLectura(destino);
  }

  sala.addEventListener('scroll', () => {
    const recorrido = sala.scrollHeight - sala.clientHeight;
    const fraccion = recorrido > 0 ? sala.scrollTop / recorrido : 0;
    $('progreso').style.width = `${(fraccion * 100).toFixed(1)}%`;
    ctx.escena?.modoLectura(true, fraccion);
  });

  // El paquete con el que se escribió: es lo único que explica después por qué
  // el escritor escribió lo que escribió (§7, §21).
  $('ver-contexto').addEventListener('click', () => {
    if (capitulo) ctx.verContexto(capitulo.numero);
  });

  $('anterior').addEventListener('click', () => saltar(-1));
  $('siguiente').addEventListener('click', () => saltar(1));
  $('inmersion').addEventListener('click', () => ctx.inmersion());

  document.addEventListener('keydown', (e) => {
    if (ctx.estado.sala !== 'lectura') return;
    if (e.target.matches('input, textarea')) return;
    if (e.key === 'ArrowLeft') saltar(-1);
    if (e.key === 'ArrowRight') saltar(1);
    if (e.key === 'f') ctx.inmersion();
    if (e.key === 'Escape') {
      if (document.body.dataset.inmersion === 'si') ctx.inmersion();
      else ctx.ir('taller');
    }
  });

  return { abrir, get capitulo() { return capitulo; } };
}
