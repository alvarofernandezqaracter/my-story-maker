// El panel de observabilidad (§20) en la página.
//
// Por el camino del harness no hay nada que pulsar: cada llamada a un agente ya
// deja traza según ocurre, y este panel solo dice si la capa está viva y por qué
// no lo está. Por el delegado no hay llamada que interceptar —orquesta otra
// sesión— así que el árbol se reconstruye del canon y se manda desde aquí.
//
// Ninguna de las dos cosas es fuente de verdad: si Langfuse no responde, la
// novela se escribe igual. Por eso un fallo aquí se cuenta y no interrumpe nada.

const $ = (id) => document.getElementById(id);

// Lo que sale en el plan, con el nombre que tiene en §20. El orden es el del
// árbol: primero las raíces, luego lo que cuelga de ellas.
const FILAS = [
  ['capitulos', 'trazas de capítulo', (p) => p.capitulos],
  ['tramos', 'preparar y cerrar', (p) => [p.preparar && 'preparar', p.cerrar && 'cerrar']
    .filter(Boolean).join(' + ') || 'ninguno'],
  ['intentos', 'intentos con escritor, VD-08 y gate', (p) => p.intentos],
  ['notas', 'puntuaciones', (p) => p.notas],
  ['retoques', 'retoques del editor global', (p) => p.retoques],
  ['sesion', 'sesión', (p) => p.sesion],
  ['entorno', 'entorno', (p) => p.entorno],
];

function fila(dl, nombre, valor) {
  const dt = document.createElement('dt');
  dt.textContent = nombre;
  const dd = document.createElement('dd');
  dd.textContent = String(valor);
  dl.append(dt, dd);
}

export function crearTrazas(ctx) {
  const panel = $('trazas');
  const estadoChip = $('trazas-estado');
  const pista = $('trazas-pista');
  const planCaja = $('trazas-plan');
  const boton = $('trazas-enviar');
  const ultimo = $('trazas-ultimo');
  let datos = null;
  let pidiendo = false;

  async function preguntar() {
    if (pidiendo) return;
    pidiendo = true;
    try {
      datos = await ctx.api.trazas(ctx.camino);
    } catch (error) {
      datos = { activas: false, lista: false, motivo: error.message, plan: null };
    } finally {
      pidiendo = false;
      pintarDatos();
    }
  }

  boton.addEventListener('click', async () => {
    boton.disabled = true;
    const antes = boton.textContent;
    boton.textContent = 'enviando…';
    try {
      const resultado = await ctx.api.exportarTrazas(ctx.camino);
      pista.textContent = resultado.enviado
        ? `${resultado.trazas} trazas enviadas a la sesión ${resultado.sesion}.`
          + ' Son reconstruidas: llevan la etiqueta «reconstruido» y no traen'
          + ' latencia, tokens ni coste, porque el canon no los guarda.'
        : `no se mandó nada: ${resultado.motivo}`;
    } catch (error) {
      pista.textContent = error.message;
    } finally {
      boton.textContent = antes;
      boton.disabled = false;
      await preguntar();
    }
  });

  function pintarDatos() {
    if (!datos) return;
    const delegado = datos.camino === 'delegado';
    estadoChip.textContent = datos.lista ? 'lista' : 'apagada';
    estadoChip.dataset.estado = datos.lista ? 'aprobado' : 'pendiente';

    planCaja.textContent = '';
    if (datos.plan) {
      for (const [clave, nombre, leer] of FILAS) {
        const valor = leer(datos.plan);
        if (valor === undefined || valor === null || valor === '') continue;
        fila(planCaja, nombre, valor);
        void clave;
      }
    }

    if (!delegado) {
      boton.hidden = true;
      pista.textContent = datos.lista
        ? `El harness traza mientras corre: cada llamada a un agente sale sola hacia`
          + ` Langfuse, entorno «${datos.entorno}». Aquí no hay nada que pulsar.`
        : `Las trazas están apagadas: ${datos.motivo}. La novela se escribe igual.`;
      return;
    }

    boton.hidden = false;
    boton.disabled = !datos.lista || !datos.plan;
    if (!datos.lista) {
      pista.textContent = `No se puede mandar nada: ${datos.motivo}.`
        + ' Las credenciales van en el .env de la raíz, que no se versiona.';
    } else if (!datos.plan) {
      pista.textContent = 'sin datos todavía: no hay canon delegado que reconstruir.';
    } else if (!pista.textContent || pista.dataset.inicial === 'si') {
      pista.textContent = 'Este camino no pasa por la capa de agentes, así que no hay'
        + ' llamada que interceptar: el árbol de §20 se reconstruye del canon que dejó'
        + ' el orquestador y se manda marcado como reconstruido.';
    }
    delete pista.dataset.inicial;

    ultimo.textContent = datos.ultimo
      ? `último envío ${new Date(datos.ultimo.cuando * 1000).toLocaleTimeString('es-ES')}`
        + (datos.ultimo.enviado ? ` · ${datos.ultimo.trazas} trazas` : ' · no salió')
      : '';
  }

  pista.dataset.inicial = 'si';

  return {
    pintar(proyecto) {
      panel.hidden = false;
      // Se pregunta cuando cambia lo que importa, no en cada vuelta del
      // refresco: el estado de la capa no cambia solo y el plan depende del canon.
      const huella = [proyecto.camino, proyecto.estado,
        proyecto.capitulos.length, proyecto.actualizado].join('|');
      if (panel.dataset.huella === huella) return;
      panel.dataset.huella = huella;
      preguntar();
    },
  };
}
