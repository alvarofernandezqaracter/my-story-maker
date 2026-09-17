// El panel de observabilidad (§20) en la página.
//
// Quien orquesta es otra sesión, así que desde aquí no hay ninguna llamada que
// interceptar: el árbol se reconstruye del canon y se manda con este botón. Lo
// que sí lleva tokens, latencia y coste lo manda el hook en vivo (§22), y eso no
// pasa por esta página.
//
// Nada de esto es fuente de verdad: si Langfuse no responde, la novela se
// escribe igual. Por eso un fallo aquí se cuenta y no interrumpe nada.

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
  // Con `trazas.texto` puesta lo que sale ya no son números: es la novela. Va en
  // palabras y no en «sí», porque el tamaño es justo la parte que hay que ver.
  ['texto', 'texto que sale', (p) => (p.texto
    ? `${p.palabras_fuera.toLocaleString('es-ES')} palabras (capítulos y paquetes)`
    : 'ninguno: solo el árbol y las notas')],
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
      datos = await ctx.api.trazas();
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
      const resultado = await ctx.api.exportarTrazas();
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

    boton.hidden = false;
    boton.disabled = !datos.lista || !datos.plan;
    if (!datos.lista) {
      pista.textContent = `No se puede mandar nada: ${datos.motivo}.`
        + ' Las credenciales van en el .env de la raíz, que no se versiona.';
    } else if (!datos.plan) {
      pista.textContent = 'sin datos todavía: no hay canon que reconstruir.';
    } else if (!pista.textContent || pista.dataset.inicial === 'si') {
      pista.textContent = 'Desde aquí no hay llamada que interceptar: el árbol de §20'
        + ' se reconstruye del canon que dejó el orquestador y se manda marcado como'
        + ` reconstruido, al entorno «${datos.entorno}».`;
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
      const huella = [proyecto.estado,
        proyecto.capitulos.length, proyecto.actualizado].join('|');
      if (panel.dataset.huella === huella) return;
      panel.dataset.huella = huella;
      preguntar();
    },
  };
}
