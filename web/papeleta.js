// Interfaz del brief (§19): lee el formulario, habla con la API del harness y
// le pasa a la escena el estado ya resuelto. Ninguna regla del sistema vive
// aqui; el servidor vuelve a validar todo lo que llegue.

const CAMPOS = ['epoca', 'premisa', 'tono', 'capitulos', 'palabras_por_capitulo'];
const NUMEROS = ['capitulos', 'palabras_por_capitulo'];

// Ejemplo de arranque: la mesa no se ve vacia al abrir y se entiende de un
// vistazo que pide cada campo. Es el mismo brief de brief.ejemplo.json.
const EJEMPLO = {
  epoca: 'Sevilla, 1587, barrio de Triana y la Casa de Contratacion',
  premisa: 'La hija de un cargador de Indias condenado por contrabando descubre'
    + ' que el registro que hundio a su padre estaba falsificado.',
  tono: 'seco',
  capitulos: 6,
  palabras_por_capitulo: 1800,
};

const SIGUIENTE_COMANDO = {
  borrador: 'python -m novela preparar',
  investigado: 'python -m novela preparar',
  estructurado: 'python -m novela escribir',
  escribiendo: 'python -m novela escribir',
  escrito: 'python -m novela cerrar',
  editado: 'python -m novela estado',
  bloqueado: 'python -m novela desbloquear --capitulo N',
};

const $ = (id) => document.getElementById(id);
const formulario = $('papeleta');
const aviso = $('aviso');
const botonGuardar = $('guardar');
const notaEjemplo = $('nota-ejemplo');

let legajo = null;
let tocado = false;       // el usuario ya ha escrito: no le pisamos el texto
let proyecto = null;

// ------------------------------------------------------------------ escena

// three.js viaja por CDN, que es lo unico de este repo que necesita red. Si no
// llega, el formulario sigue entero: la escena es lectura, no herramienta.
import('./legajo.js')
  .then(({ crearLegajo }) => crearLegajo($('escena'), { onFoco: pintarFoco }))
  .then((instancia) => { legajo = instancia; pintarEscena(); })
  .catch(() => {
    $('escena').setAttribute('aria-hidden', 'true');
    $('rail-foco').textContent = 'la mesa 3D no ha cargado (sin red)';
  });

function pintarEscena() {
  if (legajo) legajo.actualizar({ brief: leer(), capitulos: proyecto?.capitulos || [] });
}

function pintarFoco(ficha) {
  const destino = $('rail-foco');
  if (!ficha) {
    destino.textContent = proyecto?.brief
      ? `${proyecto.capitulos.length || proyecto.brief.capitulos} cuadernillos en la mesa`
      : 'el legajo está en blanco';
    return;
  }
  destino.textContent = ficha.titulo
    ? `cap. ${ficha.numero} · ${ficha.estado} · ${ficha.titulo}`
    : `cap. ${ficha.numero} · aún sin ficha`;
}

// ---------------------------------------------------------------- formulario

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
  pintarEscena();
});

$('vaciar').addEventListener('click', () => {
  escribir(null);
  tocado = true;
  notaEjemplo.hidden = true;
  decir('');
  pintarEscena();
  $('epoca').focus();
});

$('copiar').addEventListener('click', async () => {
  try {
    await navigator.clipboard.writeText($('siguiente-comando').textContent);
    $('copiar').textContent = 'copiado';
    setTimeout(() => { $('copiar').textContent = 'copiar'; }, 1600);
  } catch {
    $('copiar').textContent = 'cópialo a mano';
  }
});

formulario.addEventListener('submit', async (e) => {
  e.preventDefault();
  botonGuardar.disabled = true;
  decir('');
  try {
    const respuesta = await fetch('/api/brief', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(leer()),
    });
    const datos = await respuesta.json();
    if (!respuesta.ok) {
      decir(datos.error || 'el harness no ha aceptado el brief');
      return;
    }
    proyecto = datos;
    tocado = false;
    notaEjemplo.hidden = true;
    decir('Brief guardado en el canon. Sigue en la consola con el comando de abajo.', 'bien');
    pintarRail();
    pintarEscena();
  } catch {
    decir('no se ha podido hablar con el harness: ¿sigue corriendo "python -m novela ui"?');
  } finally {
    botonGuardar.disabled = !(proyecto?.editable ?? true);
  }
});

// ---------------------------------------------------------------------- rail

function pintarRail() {
  const estado = proyecto?.estado || 'sin brief';
  const pastilla = $('pastilla-estado');
  pastilla.textContent = estado;
  pastilla.dataset.estado = proyecto?.estado || '';
  $('rail-modo').textContent = `modo ${proyecto?.modo || '—'}`;
  $('siguiente-comando').textContent = SIGUIENTE_COMANDO[proyecto?.estado]
    || 'python -m novela preparar';

  const tramos = $('rail-capitulos');
  tramos.textContent = '';
  for (const c of proyecto?.capitulos || []) {
    const tramo = document.createElement('span');
    tramo.className = 'tramo';
    tramo.dataset.estado = c.estado;
    tramo.title = c.media
      ? `cap. ${c.numero} · ${c.estado} · notas ${c.notas.join('/')} · media ${c.media}`
      : `cap. ${c.numero} · ${c.estado} · ${c.titulo}`;
    tramos.append(tramo);
  }
  pintarFoco(null);
}

function bloquearSiHayLibro() {
  if (proyecto && proyecto.editable === false) {
    botonGuardar.disabled = true;
    decir('El canon ya tiene una novela en marcha, así que la interfaz no toca el'
      + ' brief. Para rehacerlo a sabiendas, "python -m novela brief <fichero>".');
  }
}

// --------------------------------------------------------------- arranque

async function refrescar() {
  try {
    const respuesta = await fetch('/api/proyecto');
    proyecto = await respuesta.json();
  } catch {
    return;
  }
  // El flujo puede estar corriendo en otra consola: el rail sigue vivo. Lo que
  // no se toca nunca es lo que el usuario esta escribiendo.
  if (proyecto.brief && !tocado) {
    escribir(proyecto.brief);
    notaEjemplo.hidden = true;
  } else if (!proyecto.brief && !tocado && !$('epoca').value) {
    escribir(EJEMPLO);
    notaEjemplo.hidden = false;
  }
  pintarRail();
  bloquearSiHayLibro();
  pintarEscena();
}

refrescar();
setInterval(() => { if (!document.hidden) refrescar(); }, 4000);
