// Sala del brief: los cinco campos de §3, en modo lectura.
//
// Fue un formulario mientras hubo un orquestador al que mandarle el brief. Ya no
// lo hay: en el canon de §21 escribe la sesion de Claude Code y nadie mas, asi
// que lo honesto es ensenar lo que hay escrito y decir con que comando se
// escribe, en vez de un formulario que siempre devolveria un 409.
const CAMPOS = [
  ['epoca', 'Época y lugar'],
  ['premisa', 'Premisa'],
  ['tono', 'Tono'],
  ['capitulos', 'Capítulos'],
  ['palabras_por_capitulo', 'Palabras por capítulo'],
];

const $ = (id) => document.getElementById(id);

export function crearBrief(ctx) {
  const lista = $('brief-leido');
  const aviso = $('aviso-brief');

  $('brief-copiar').addEventListener('click', async () => {
    try {
      await navigator.clipboard.writeText('/orquestar-novela');
      $('brief-copiar').textContent = 'copiado';
      setTimeout(() => { $('brief-copiar').textContent = 'copiar'; }, 1600);
    } catch {
      $('brief-copiar').textContent = 'cópialo a mano';
    }
  });

  function pintarCampos(brief) {
    lista.textContent = '';
    if (!brief) {
      const vacio = document.createElement('p');
      vacio.className = 'vacio';
      vacio.textContent = 'sin datos todavía: este canon no tiene brief.';
      lista.append(vacio);
      return;
    }
    for (const [clave, etiqueta] of CAMPOS) {
      const dt = document.createElement('dt');
      dt.textContent = etiqueta;
      const dd = document.createElement('dd');
      dd.textContent = brief[clave] ?? '—';
      lista.append(dt, dd);
    }
  }

  // Una ejecucion es un canon con su brief. Hay uno por carpeta, asi que la
  // lista tiene una entrada o ninguna.
  function pintarEjecuciones(proyecto) {
    const caja = $('ejecuciones-lista');
    caja.textContent = '';
    if (!proyecto?.brief) {
      const vacio = document.createElement('p');
      vacio.className = 'vacio';
      vacio.textContent = 'sin datos todavía: no hay ningún brief guardado.';
      caja.append(vacio);
      return;
    }
    const aprobados = proyecto.capitulos.filter((c) => c.estado === 'aprobado').length;
    const total = proyecto.capitulos.length || proyecto.brief.capitulos;

    const fila = document.createElement('button');
    fila.type = 'button';
    fila.className = 'ejecucion';
    fila.dataset.activa = 'si';

    const alto = document.createElement('div');
    alto.className = 'ejecucion__alto';
    const ruta = document.createElement('span');
    ruta.className = 'ejecucion__ruta';
    ruta.textContent = proyecto.canon;
    const badge = document.createElement('span');
    badge.className = 'pastilla';
    badge.dataset.estado = proyecto.estado || '';
    badge.textContent = proyecto.estado || 'sin estado';
    alto.append(ruta, badge);

    const premisa = document.createElement('p');
    premisa.className = 'ejecucion__premisa';
    premisa.textContent = proyecto.brief.premisa;

    const cuenta = document.createElement('span');
    cuenta.className = 'ejecucion__cuenta';
    cuenta.textContent = `${aprobados} de ${total} capítulos`;

    const barra = document.createElement('div');
    barra.className = 'barra-progreso';
    if (aprobados === total && total) barra.dataset.tono = 'ok';
    const relleno = document.createElement('span');
    relleno.style.width = total ? `${(aprobados / total) * 100}%` : '0';
    barra.append(relleno);

    fila.append(alto, premisa, cuenta, barra);
    fila.addEventListener('click', () => ctx.ir('taller'));
    caja.append(fila);
  }

  return {
    pintar(proyecto) {
      pintarCampos(proyecto?.brief);
      pintarEjecuciones(proyecto);
      aviso.hidden = Boolean(proyecto?.brief);
      if (!proyecto?.brief) {
        aviso.textContent = 'Todavía no hay novela en este canon. El comando de abajo'
          + ' la empieza: te pedirá los cinco campos.';
      }
      $('papeleta-titulo').textContent = proyecto?.brief
        ? 'El brief de esta novela' : 'Empieza una novela';
    },
    // La escena 3D se pinta con el brief del canon, que es el unico que hay: ya
    // no existe el brief a medio escribir de un formulario.
    leer: () => ctx.estado.proyecto?.brief || null,
  };
}
