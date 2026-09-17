// El replay del ultimo capitulo (§19). Reproduce paso a paso por donde fue el
// flujo la ultima vez que se escribio un capitulo, sobre el mismo grafo.
//
// Por que existe: la orquestacion es una conversacion en Claude Code y esta
// pagina no la ve pasar (§21). Lo que si queda es lo que el canon escribio
// -cuantos intentos, que puntuo cada validador, que decidio el gate y por que-,
// y con eso el recorrido se puede rehacer entero y en orden. No es una
// simulacion: cada paso sale de un dato guardado, y donde el canon no dice nada
// el paso no se inventa.
//
// El grafo no sabe que esto existe. Se le habla por setNodeState y setEdgeActive
// como se le hablaria desde una ejecucion en vivo, que es lo que permite que la
// misma pantalla sirva para las dos cosas.

const VELOCIDADES = [1, 2, 4];

// Lo que dura cada clase de paso a velocidad 1. Un agente LLM tarda de verdad y
// una comprobacion no, asi que el reloj del replay se parece al del sistema en
// vez de repartir el tiempo a partes iguales.
const DURACION = { agente: 1500, paso: 700, decision: 950 };

// ----------------------------------------------------------- el recorrido

// El estado de los dieciocho nodos, que es lo que se va fotografiando.
function estadoInicial() {
  return {
    nodos: {
      brief: ['completado', ''],
      investigador: ['completado', ''],
      dossier: ['completado', ''],
      arquitecto: ['completado', ''],
      escaleta: ['completado', ''],
      personajes: ['completado', ''],
      contexto: ['pendiente', ''],
      escritor: ['pendiente', ''],
      borrador: ['pendiente', ''],
      vd08: ['pendiente', ''],
      'val-continuidad': ['pendiente', ''],
      'val-anacronismos': ['pendiente', ''],
      'val-logica': ['pendiente', ''],
      gate: ['pendiente', ''],
      cronista: ['pendiente', ''],
      canon: ['pendiente', ''],
      editor: ['pendiente', ''],
      retoques: ['pendiente', ''],
    },
    aristas: [],
  };
}

const VALIDADORES = ['val-continuidad', 'val-anacronismos', 'val-logica'];

/**
 * Rehace el recorrido del ultimo capitulo trabajado a partir del canon.
 *
 * Devuelve null cuando no hay con que: el detalle de los intentos -notas, VD-08
 * y veredicto- solo lo expone /api/proyecto del capitulo en curso o del ultimo
 * que se trabajo, y sin ese detalle no hay recorrido que contar. Lo honesto es
 * decir que no lo hay, no repartir un capitulo aprobado en pasos supuestos.
 */
export function construir(proyecto, maxIntentos) {
  const capitulo = proyecto?.en_curso;
  if (!capitulo?.intentos?.length) return null;

  const estado = estadoInicial();
  const pasos = [];

  // Cada paso es una foto entera del grafo, no un delta: asi mover el deslizador
  // a cualquier sitio es aplicar una foto y no rehacer la historia desde el
  // principio.
  const foto = (etiqueta, duracion) => {
    pasos.push({
      etiqueta,
      duracion,
      nodos: JSON.parse(JSON.stringify(estado.nodos)),
      aristas: [...estado.aristas],
    });
  };

  const poner = (id, valor, pie = '') => { estado.nodos[id] = [valor, pie]; };
  const correr = (...ids) => { estado.aristas = ids; };

  const total = capitulo.intentos.length;

  for (const intento of capitulo.intentos) {
    const k = intento.intento;
    const deN = `intento ${k}/${maxIntentos}`;

    // --- el paquete de contexto (§7)
    poner('contexto', 'activo');
    correr('escaleta>contexto', 'personajes>contexto');
    foto(`Se arma el paquete de contexto del capitulo ${capitulo.numero}`, DURACION.paso);
    poner('contexto', 'completado');

    // --- el escritor
    poner('escritor', 'activo', deN);
    correr('contexto>escritor');
    foto(`El escritor redacta el intento ${k}`, DURACION.agente);
    poner('escritor', 'completado', deN);
    poner('borrador', 'completado',
      intento.palabras ? `${intento.palabras} palabras` : '');
    correr('escritor>borrador');
    foto(intento.palabras
      ? `Borrador ${k}: ${intento.palabras} palabras en ${intento.parrafos} parrafos`
      : `Borrador ${k}`, DURACION.paso);

    // --- VD-08, que corre antes del validador para no gastar tres llamadas
    poner('vd08', 'activo');
    correr('borrador>vd08');
    foto('VD-08 mira el borrador antes de gastar tres llamadas al validador',
      DURACION.decision);

    if (intento.vd08 === 'bloqueo') {
      poner('vd08', 'reintento', 'bloqueo');
      poner('escritor', 'reintento', `intento ${k + 1}/${maxIntentos}`);
      correr('vd08>escritor');
      foto('VD-08 bloquea: se descarta el borrador y se reintenta de cero',
        DURACION.paso);
      continue;
    }

    poner('vd08', 'completado', intento.vd08 === 'aviso' ? 'aviso' : '');

    // --- los tres validadores, en un mismo mensaje y sin verse entre si (§21)
    for (const id of VALIDADORES) poner(id, 'activo');
    correr(...VALIDADORES.map((id) => `vd08>${id}`));
    foto('Los tres validadores puntuan a la vez, en un mismo mensaje y sin verse',
      DURACION.agente);

    const notas = intento.notas || [];
    VALIDADORES.forEach((id, i) => {
      poner(id, 'completado', notas[i] != null ? `nota ${notas[i]}` : '');
    });
    correr(...VALIDADORES.map((id) => `${id}>gate`));
    poner('gate', 'activo');
    foto(notas.length
      ? `Notas ${notas.join(' / ')} — el gate hace la cuenta`
      : 'El gate hace la cuenta', DURACION.decision);

    if (intento.estado === 'aprobado') {
      poner('gate', 'completado', intento.media != null ? `media ${intento.media}` : '');
      correr('gate>cronista');
      poner('cronista', 'activo');
      foto(intento.regla || 'El gate aprueba', DURACION.agente);

      poner('cronista', 'completado');
      poner('canon', 'completado');
      correr('cronista>canon');
      foto('El cronista escribe en el canon de una vez: resumen, fichas y eventos',
        DURACION.paso);
      correr();
      foto(`Capitulo ${capitulo.numero} aprobado en el intento ${k}`, DURACION.paso);
      break;
    }

    // --- el gate rechaza
    const ultimo = k === total;
    poner('gate', ultimo ? 'bloqueado' : 'reintento',
      intento.media != null ? `media ${intento.media}` : '');
    if (ultimo) {
      correr();
      foto(intento.regla || 'El gate rechaza y no quedan intentos', DURACION.paso);
      break;
    }
    poner('escritor', 'reintento', `intento ${k + 1}/${maxIntentos}`);
    correr('gate>escritor');
    foto(intento.regla || 'El gate rechaza: vuelve al escritor', DURACION.paso);
  }

  return { numero: capitulo.numero, titulo: capitulo.titulo, pasos };
}

// -------------------------------------------------------------- el mando

/**
 * El transporte: play/pausa, velocidad y deslizador sobre un recorrido ya hecho.
 *
 * No toca el DOM del grafo: aplica fotos con las dos funciones que el grafo
 * expone. Por eso el mismo mando serviria para una ejecucion en vivo el dia que
 * haya eventos que escuchar.
 */
export function crearMando({ caja, grafo, alPintar }) {
  const boton = document.createElement('button');
  boton.type = 'button';
  boton.className = 'boton boton--fino replay__play';

  const deslizador = document.createElement('input');
  deslizador.type = 'range';
  deslizador.className = 'replay__linea';
  deslizador.min = '0';
  deslizador.step = '1';
  deslizador.setAttribute('aria-label', 'Paso del recorrido');

  const velocidad = document.createElement('div');
  velocidad.className = 'replay__velocidad';
  velocidad.setAttribute('role', 'group');
  velocidad.setAttribute('aria-label', 'Velocidad');
  const botonesVelocidad = VELOCIDADES.map((v) => {
    const b = document.createElement('button');
    b.type = 'button';
    b.className = 'enlace';
    b.textContent = `${v}x`;
    b.addEventListener('click', () => elegirVelocidad(v));
    velocidad.append(b);
    return [v, b];
  });

  caja.append(boton, deslizador, velocidad);

  let recorrido = null;
  let indice = 0;
  let corriendo = false;
  let factor = 1;
  let temporizador = null;

  // El transporte y el grafo se pintan por separado a proposito: cargar un
  // recorrido tiene que dejar los mandos listos sin tocar lo que el grafo este
  // enseñando. Solo se pisa el grafo cuando alguien le da a reproducir o mueve
  // el deslizador, que es cuando ha pedido ver el recorrido.
  function pintarMandos() {
    boton.textContent = corriendo ? 'pausa' : 'reproducir';
    boton.setAttribute('aria-pressed', String(corriendo));
    for (const [v, b] of botonesVelocidad) {
      b.setAttribute('aria-current', String(v === factor));
    }
    deslizador.value = String(indice);
  }

  function pintar() {
    pintarMandos();
    const paso = recorrido?.pasos[indice];
    if (!paso) return;
    for (const [id, [valor, pie]] of Object.entries(paso.nodos)) {
      grafo.setNodeState(id, valor, pie);
    }
    for (const id of todasLasAristas) grafo.setEdgeActive(id, paso.aristas.includes(id));
    alPintar?.(paso, indice, recorrido.pasos.length);
  }

  // Las aristas que el recorrido llega a encender alguna vez. Solo esas hay que
  // apagar al cambiar de paso, y asi el mando no necesita la lista del grafo.
  let todasLasAristas = [];

  function programar() {
    clearTimeout(temporizador);
    if (!corriendo || !recorrido) return;
    const paso = recorrido.pasos[indice];
    temporizador = setTimeout(() => {
      if (indice >= recorrido.pasos.length - 1) { parar(); return; }
      indice += 1;
      pintar();
      programar();
    }, (paso?.duracion || 700) / factor);
  }

  function parar() {
    corriendo = false;
    clearTimeout(temporizador);
    pintarMandos();
  }

  function arrancar() {
    if (!recorrido?.pasos.length) return;
    // Darle a reproducir en el ultimo paso vuelve a empezar, que es lo que
    // espera cualquiera que le da dos veces seguidas.
    if (indice >= recorrido.pasos.length - 1) indice = 0;
    corriendo = true;
    pintar();
    programar();
  }

  function elegirVelocidad(v) {
    factor = v;
    pintar();
    programar();
  }

  boton.addEventListener('click', () => (corriendo ? parar() : arrancar()));
  deslizador.addEventListener('input', () => {
    parar();
    indice = Number(deslizador.value);
    pintar();
  });

  return {
    cargar(nuevo) {
      parar();
      recorrido = nuevo;
      indice = 0;
      todasLasAristas = [...new Set(nuevo?.pasos.flatMap((p) => p.aristas) || [])];
      deslizador.max = String(Math.max((nuevo?.pasos.length || 1) - 1, 0));
      deslizador.disabled = !nuevo;
      boton.disabled = !nuevo;
      pintarMandos();
    },
    parar,
    get activo() { return Boolean(recorrido); },
    get reproduciendo() { return corriendo; },
  };
}
