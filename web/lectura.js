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
    // incidencias del intento anterior: son notas del harness para el propio
    // agente, no prosa de la novela.
    .replace(/<!--[\s\S]*?-->/g, '')
    .split(/\n{2,}/)
    .map((bloque) => {
      const t = bloque.trim();
      if (!t) return '';
      // El titulo del capitulo ya va en la cabecera del lector.
      if (t.startsWith('# ')) return '';
      if (/^#{2,6} /.test(t)) return `<h3>${escapar(t.replace(/^#+\s*/, ''))}</h3>`;
      return `<p>${escapar(t).replace(/\n/g, '<br>')}</p>`;
    })
    .join('');
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
    pintarNotas(capitulo);
    pintarFicha(capitulo);

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
