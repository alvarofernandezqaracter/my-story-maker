// La vista del encargo: los cinco campos de §3, y el boton que arranca.
//
// El formulario no escribe en el canon. Manda el brief a POST /api/lanzar, que
// arranca una sesion de Claude Code con esos cinco campos delante y se aparta:
// quien escribe la novela sigue siendo esa sesion, igual que si se hubiera
// abierto a mano (§21). Lo que la pagina hace despues es lo de siempre, mirar
// el canon llenarse, y para eso lleva a la novela recien apartada.
const CAMPOS = ['epoca', 'premisa', 'tono', 'capitulos', 'palabras_por_capitulo'];

const PISTA = 'Ninguno de los cinco campos tiene valor por defecto que el orquestador'
  + ' vaya a inventarse. La novela nace en su propia carpeta de biblioteca/ y no toca'
  + ' ninguna otra.';

const $ = (id) => document.getElementById(id);

export function crearBrief(ctx) {
  const formulario = $('brief-form');
  const boton = $('brief-lanzar');
  const linea = $('brief-estado');
  const pista = $('brief-pista');
  const partir = $('brief-partir');

  let corriendo = false;
  let novelas = [];

  $('brief-copiar').addEventListener('click', async () => {
    try {
      await navigator.clipboard.writeText('/orquestar-novela');
      $('brief-copiar').textContent = 'copiado';
      setTimeout(() => { $('brief-copiar').textContent = 'copiar'; }, 1600);
    } catch {
      $('brief-copiar').textContent = 'cópialo a mano';
    }
  });

  function leerFormulario() {
    const datos = {};
    for (const campo of CAMPOS) datos[campo] = formulario.elements[campo].value;
    return datos;
  }

  // Partir del brief de otra novela copia sus cinco campos al formulario y nada
  // mas: la novela nueva sigue naciendo en su propia carpeta.
  partir.addEventListener('change', () => {
    const origen = novelas.find((n) => n.nombre === partir.value);
    if (!origen?.brief) return;
    for (const campo of CAMPOS) formulario.elements[campo].value = origen.brief[campo] ?? '';
    ctx.previsualizar(leerFormulario());
  });

  formulario.addEventListener('input', () => ctx.previsualizar(leerFormulario()));

  function pintarLanzamiento(estado) {
    corriendo = Boolean(estado?.corriendo);
    boton.disabled = corriendo;
    boton.textContent = corriendo ? 'Agentes en marcha' : 'Lanzar agentes';
    if (corriendo) {
      linea.textContent = `sesión ${estado.pid} escribiendo`;
      pista.textContent = estado.lanzado?.log
        ? `Una novela a la vez. Lo que imprima la sesión va a ${estado.lanzado.log}.`
        : 'Una novela a la vez: la sesión arrancada sigue escribiendo.';
    } else {
      linea.textContent = '';
      pista.textContent = PISTA;
    }
  }

  formulario.addEventListener('submit', async (e) => {
    e.preventDefault();
    if (corriendo) return;
    boton.disabled = true;
    linea.textContent = 'arrancando…';
    try {
      const salida = await ctx.api.lanzar(leerFormulario());
      pintarLanzamiento({ corriendo: true, pid: salida.pid, lanzado: salida });
      // A la novela recien apartada: ahi es donde se va a ver el canon llenarse.
      ctx.abrirNovela(salida.novela);
    } catch (error) {
      boton.disabled = false;
      linea.textContent = '';
      // El porqué viene del servidor entero: es el mismo criterio de §3 que
      // aplicaría el orquestador, y decirlo a medias no ayuda a arreglarlo.
      pista.textContent = error.message;
    }
  });

  return {
    pintarLanzamiento,
    pintar(lista) {
      const conBrief = lista.filter((n) => n.brief);
      // Rehacer el desplegable en cada refresco lo cerraria en la mano de quien
      // lo esta abriendo: solo se toca si ha cambiado la biblioteca.
      const huella = conBrief.map((n) => n.nombre).join('|');
      novelas = conBrief;
      if (partir.dataset.huella === huella) return;
      partir.dataset.huella = huella;
      const elegida = partir.value;
      partir.textContent = '';
      const blanco = document.createElement('option');
      blanco.value = '';
      blanco.textContent = novelas.length ? 'En blanco' : 'En blanco (no hay otras novelas)';
      partir.append(blanco);
      for (const n of novelas) {
        const opcion = document.createElement('option');
        opcion.value = n.nombre;
        opcion.textContent = `${n.brief.epoca} — ${n.nombre}`;
        partir.append(opcion);
      }
      partir.value = novelas.some((n) => n.nombre === elegida) ? elegida : '';
    },
    // El legajo se pinta con lo que hay tecleado, no con lo guardado: asi se
    // monta mientras se escribe el brief y no despues.
    leer: () => (formulario.elements.epoca.value ? leerFormulario() : null),
  };
}
