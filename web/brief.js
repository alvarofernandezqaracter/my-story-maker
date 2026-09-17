// Sala del brief: los cinco campos de §3. Valida lo minimo para no dejar
// mandar un formulario vacio; la validacion que manda es la del servidor.
const CAMPOS = ['epoca', 'premisa', 'tono', 'capitulos', 'palabras_por_capitulo'];
const NUMEROS = ['capitulos', 'palabras_por_capitulo'];

// Ejemplo de arranque: la mesa no se ve vacia al abrir y se entiende de un
// vistazo que pide cada campo. Es el de brief.ejemplo.json.
const EJEMPLO = {
  epoca: 'Sevilla, 1587, barrio de Triana y la Casa de Contratacion',
  premisa: 'La hija de un cargador de Indias condenado por contrabando descubre'
    + ' que el registro que hundio a su padre estaba falsificado.',
  tono: 'seco',
  capitulos: 6,
  palabras_por_capitulo: 1800,
};

const $ = (id) => document.getElementById(id);

export function crearBrief(ctx) {
  const formulario = $('papeleta');
  const aviso = $('aviso-brief');
  const guardar = $('guardar');
  const crearYLanzar = $('crear-y-lanzar');
  const selector = $('perfil');
  const notaEjemplo = $('nota-ejemplo');
  let tocado = false;

  function leer() {
    const brief = {};
    for (const campo of CAMPOS) {
      const valor = $(campo).value.trim();
      brief[campo] = NUMEROS.includes(campo) ? Number(valor) : valor;
    }
    return brief;
  }

  function escribir(brief) {
    for (const campo of CAMPOS) $(campo).value = brief?.[campo] ?? '';
  }

  function decir(mensaje, tono) {
    aviso.hidden = !mensaje;
    aviso.textContent = mensaje || '';
    if (tono) aviso.dataset.tono = tono; else delete aviso.dataset.tono;
  }

  formulario.addEventListener('input', () => {
    tocado = true;
    notaEjemplo.hidden = true;
    ctx.previsualizar(leer());
  });

  $('vaciar').addEventListener('click', () => {
    escribir(null);
    tocado = true;
    notaEjemplo.hidden = true;
    decir('');
    ctx.previsualizar(leer());
    $('epoca').focus();
  });

  async function crear(lanzar) {
    guardar.disabled = true;
    crearYLanzar.disabled = true;
    decir('');
    try {
      await ctx.api.guardarBrief(leer(), ctx.camino);
      tocado = false;
      notaEjemplo.hidden = true;
      if (lanzar) {
        await ctx.api.arrancar('todo', ctx.perfilElegido(), ctx.camino);
        decir('Brief guardado y agentes lanzados. Al escritorio.', 'bien');
      } else {
        decir('Brief guardado. En el escritorio se lanza a los agentes cuando quieras.', 'bien');
      }
      await ctx.refrescar();
      setTimeout(() => ctx.ir('taller'), lanzar ? 300 : 700);
    } catch (error) {
      decir(error.message);
    } finally {
      guardar.disabled = false;
      crearYLanzar.disabled = false;
    }
  }

  formulario.addEventListener('submit', (e) => { e.preventDefault(); crear(true); });
  guardar.addEventListener('click', () => crear(false));

  // Los perfiles son los config*.json de la raiz. Si solo hay uno, el selector
  // sigue estando, porque es donde se mira para saber con cual se va a lanzar.
  function pintarPerfiles(proyecto) {
    const perfiles = proyecto?.perfiles || [];
    const elegido = selector.value;
    if (selector.dataset.pintados === String(perfiles.length) && elegido) return;
    selector.dataset.pintados = String(perfiles.length);
    selector.textContent = '';
    if (!perfiles.length) {
      const opcion = document.createElement('option');
      opcion.textContent = 'sin datos todavía';
      opcion.value = '';
      selector.append(opcion);
      selector.disabled = true;
      return;
    }
    selector.disabled = false;
    for (const p of perfiles) {
      const opcion = document.createElement('option');
      opcion.value = p.nombre;
      opcion.textContent = `${p.nombre} — modo ${p.modo}`;
      selector.append(opcion);
    }
    selector.value = elegido || (perfiles.find((p) => p.nombre === 'config')?.nombre
      ?? perfiles[0].nombre);
  }

  // Una ejecucion es un canon con su brief. Hoy el harness lleva uno por
  // carpeta, asi que la lista tiene una entrada o ninguna.
  function pintarEjecuciones(proyecto) {
    const lista = $('ejecuciones-lista');
    lista.textContent = '';
    if (!proyecto?.brief) {
      const vacio = document.createElement('p');
      vacio.className = 'vacio';
      vacio.textContent = 'sin datos todavía: no hay ningún brief guardado.';
      lista.append(vacio);
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
    lista.append(fila);
  }

  return {
    perfil: () => selector.value || null,
    pintar(proyecto) {
      pintarPerfiles(proyecto);
      pintarEjecuciones(proyecto);
      if (proyecto?.brief && !tocado) {
        escribir(proyecto.brief);
        notaEjemplo.hidden = true;
      } else if (!proyecto?.brief && !tocado && !$('epoca').value) {
        escribir(EJEMPLO);
        notaEjemplo.hidden = false;
      }
      // Por el camino delegado nunca es editable: en ese canon escribe el
      // orquestador y nadie mas (§21). Por el del harness solo deja de serlo
      // cuando el libro ya esta en marcha.
      const delegado = proyecto?.camino === 'delegado';
      if (proyecto && proyecto.editable === false) {
        guardar.disabled = true;
        crearYLanzar.disabled = true;
        for (const campo of CAMPOS) $(campo).disabled = true;
        decir(delegado
          ? 'Este brief lo escribe el orquestador, no la página: aquí se lee. Para'
            + ' empezar una novela, abre Claude Code y lanza /orquestar-novela; te'
            + ' pedirá los cinco campos y no se los inventará.'
          : 'El canon ya tiene una novela en marcha, así que la interfaz no toca el'
            + ' brief. Para rehacerlo a sabiendas: "python -m novela brief <fichero>".');
      } else if (proyecto) {
        guardar.disabled = false;
        crearYLanzar.disabled = false;
        for (const campo of CAMPOS) $(campo).disabled = false;
      }
    },
    leer,
  };
}
