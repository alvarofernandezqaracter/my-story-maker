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

  formulario.addEventListener('submit', async (e) => {
    e.preventDefault();
    guardar.disabled = true;
    decir('');
    try {
      await ctx.api.guardarBrief(leer());
      tocado = false;
      notaEjemplo.hidden = true;
      decir('Brief guardado. Vamos al taller: ahí se lanza a los agentes.', 'bien');
      await ctx.refrescar();
      setTimeout(() => ctx.ir('taller'), 700);
    } catch (error) {
      decir(error.message);
    } finally {
      guardar.disabled = false;
    }
  });

  return {
    pintar(proyecto) {
      if (proyecto?.brief && !tocado) {
        escribir(proyecto.brief);
        notaEjemplo.hidden = true;
      } else if (!proyecto?.brief && !tocado && !$('epoca').value) {
        escribir(EJEMPLO);
        notaEjemplo.hidden = false;
      }
      if (proyecto && proyecto.editable === false) {
        guardar.disabled = true;
        for (const campo of CAMPOS) $(campo).disabled = true;
        decir('El canon ya tiene una novela en marcha, así que la interfaz no toca el'
          + ' brief. Para rehacerlo a sabiendas: "python -m novela brief <fichero>".');
      }
    },
    leer,
  };
}
