// Sala del brief: los cinco campos de §3, y el boton que arranca.
//
// El formulario no escribe en el canon. Manda el brief a POST /api/lanzar, que
// arranca una sesion de Claude Code con esos cinco campos delante y se aparta:
// quien escribe la novela sigue siendo esa sesion, igual que si se hubiera
// abierto a mano (§21). Lo que la pagina hace despues es lo de siempre, mirar
// el canon llenarse.
const CAMPOS = ['epoca', 'premisa', 'tono', 'capitulos', 'palabras_por_capitulo'];

const $ = (id) => document.getElementById(id);

export function crearBrief(ctx) {
  const formulario = $('brief-form');
  const boton = $('brief-lanzar');
  const linea = $('brief-estado');
  const pista = $('brief-pista');
  const aviso = $('aviso-brief');

  let corriendo = false;
  let rellenado = false;

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

  function pintarLanzamiento(estado) {
    corriendo = Boolean(estado?.corriendo);
    boton.disabled = corriendo;
    boton.textContent = corriendo ? 'agentes en marcha' : 'Lanzar agentes';
    if (corriendo) {
      linea.textContent = `sesión ${estado.pid} escribiendo`;
      pista.textContent = estado.lanzado?.log
        ? `Lo que imprima la sesión va a ${estado.lanzado.log}. El canon se llena`
          + ' solo y esta página lo va viendo.'
        : 'El canon se llena solo y esta página lo va viendo.';
    } else {
      linea.textContent = '';
    }
  }

  async function mirarLanzamiento() {
    try {
      pintarLanzamiento(await ctx.api.lanzamiento());
    } catch {
      // Que no se pueda preguntar por el lanzamiento no es motivo para romper
      // la sala: el formulario sigue sirviendo.
    }
  }

  formulario.addEventListener('submit', async (e) => {
    e.preventDefault();
    if (corriendo) return;
    boton.disabled = true;
    linea.textContent = 'arrancando…';
    pista.textContent = '';
    try {
      const salida = await ctx.api.lanzar(leerFormulario());
      pintarLanzamiento({ corriendo: true, pid: salida.pid, lanzado: salida });
      ctx.refrescar();
    } catch (error) {
      boton.disabled = false;
      linea.textContent = '';
      // El porqué viene del servidor entero: es el mismo criterio de §3 que
      // aplicaría el orquestador, y decirlo a medias no ayuda a arreglarlo.
      pista.textContent = error.message;
    }
  });

  mirarLanzamiento();

  return {
    pintar(proyecto) {
      // El brief del canon se vuelca una sola vez sobre el formulario: si se
      // reescribiera en cada refresco, borraria lo que se este tecleando.
      if (proyecto?.brief && !rellenado) {
        rellenado = true;
        for (const campo of CAMPOS) {
          formulario.elements[campo].value = proyecto.brief[campo] ?? '';
        }
      }

      aviso.hidden = !proyecto?.brief;
      if (proyecto?.brief) {
        aviso.textContent = 'Abajo está el brief de la novela en curso, por si'
          + ' quieres partir de él. Lanzar empieza una novela nueva en su propia'
          + ' carpeta y no toca esta. Para seguir una a medias, pídeselo a'
          + ' Claude Code: «reanuda la novela».';
      }
      $('papeleta-titulo').textContent = proyecto?.brief
        ? 'El brief de la novela en curso' : 'Empieza una novela';
      pintarEjecuciones(proyecto);
      if (!corriendo) mirarLanzamiento();
    },
    // La escena 3D se pinta con lo que hay tecleado, no solo con lo guardado:
    // asi el legajo se monta mientras se escribe el brief y no despues.
    leer: () => (rellenado || formulario.elements.epoca.value
      ? leerFormulario() : ctx.estado.proyecto?.brief || null),
  };

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
}
