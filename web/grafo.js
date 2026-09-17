// El grafo de la arquitectura (§19). Un DAG por capas dibujado en SVG inline:
// las capas van de izquierda a derecha, los nodos de una capa se reparten en
// vertical y las vueltas atras del loop bajan a un carril propio por debajo.
//
// SVG y JS a pelo, sin ninguna libreria de grafos. Lo que se dibuja sale entero
// del modelo que le pasa arquitectura.js: este fichero no sabe nada del
// pipeline, solo de cajas, curvas y estados.
//
// Ninguna coordenada esta puesta a ojo. La columna la da el nivel del nodo y la
// fila la reparte `disponer` con una separacion minima garantizada, asi que el
// mismo modelo da el mismo dibujo en cualquier pantalla.

// La caja de un nodo y la rejilla sobre la que se posan. Todo lo demas se deriva
// de estos cinco numeros.
const CAJA = { ancho: 122, alto: 46 };
const SEPARACION_X = 164;   // entre centros de columna
const SEPARACION_Y = 72;    // separacion minima garantizada entre centros de fila
const CARRIL = 38;          // cuanto baja cada vuelta atras por debajo del grafo
const SUELO = 12;           // aire entre la ultima caja y el primer carril
const MARGEN = 30;          // aire alrededor del dibujo dentro del viewBox

// Diez columnas puestas en fila dan un dibujo casi cuatro veces mas ancho que
// alto, y encuadrarlo entero en un panel apaisado encoge la letra hasta que deja
// de leerse. La caja se aprieta todo lo que se puede y el nombre que no cabe en
// una linea se parte en dos, que es lo que permite apretarla.
const MAXIMO_LINEA = 12;

const SVG = 'http://www.w3.org/2000/svg';

const ZOOM = { min: 0.45, max: 3.2, paso: 1.12 };

// El flujo por una arista activa. La direccion se lee porque los guiones corren
// de origen a destino, y el punto que los acompana es lo que hace que se siga
// con la vista sin tener que buscar la punta de flecha.
const FLUJO = {
  velocidad: 78,   // unidades de trazo por segundo
  guion: 13,       // largo del guion que viaja
  hueco: 11,       // y el del hueco entre dos
};

function elemento(nombre, atributos = {}) {
  const nodo = document.createElementNS(SVG, nombre);
  for (const [clave, valor] of Object.entries(atributos)) {
    if (valor != null) nodo.setAttribute(clave, String(valor));
  }
  return nodo;
}

// --------------------------------------------------------------- el reparto

// Layout por capas y nada mas. El nivel es la columna; dentro de la columna los
// nodos se reparten simetricos alrededor del eje con SEPARACION_Y entre centros,
// que es la separacion minima y a la vez la unica, porque todas las cajas miden
// lo mismo.
export function disponer(nodos) {
  const columnas = new Map();
  for (const nodo of nodos) {
    if (!columnas.has(nodo.nivel)) columnas.set(nodo.nivel, []);
    columnas.get(nodo.nivel).push(nodo);
  }
  for (const [nivel, lista] of columnas) {
    lista.forEach((nodo, i) => {
      nodo.x = nivel * SEPARACION_X;
      nodo.y = (i - (lista.length - 1) / 2) * SEPARACION_Y;
      nodo.compartida = lista.length > 1;
    });
  }
  return nodos;
}

// ---------------------------------------------------------------- las curvas

// Camino feliz: sale por el costado derecho y entra por el izquierdo, con una
// cubica cuyos tiradores caen a media distancia. Con los dos nodos en la misma
// fila queda una recta, que es lo que tiene que quedar.
function caminoRecto(a, b) {
  const x1 = a.x + CAJA.ancho / 2;
  const x2 = b.x - CAJA.ancho / 2;
  const medio = x1 + (x2 - x1) / 2;
  return `M ${x1} ${a.y} C ${medio} ${a.y}, ${medio} ${b.y}, ${x2} ${b.y}`;
}

// Un artefacto comparte columna con el agente que lo produce, asi que esa arista
// no viaja a ninguna parte: baja de una caja a la de debajo. Sale por el canto
// inferior y entra por el superior, que es lo unico que se lee como «esto sale
// de aquello» sin cruzar por delante de la propia caja.
function caminoVertical(a, b) {
  const y1 = a.y + CAJA.alto / 2;
  const y2 = b.y - CAJA.alto / 2;
  // Si se salta una fila -el arquitecto produce escaleta y personajes, y
  // personajes esta dos abajo- la curva se abomba por la izquierda: una recta
  // atravesaria la caja de en medio y se leeria como una cadena que no existe.
  const salta = Math.round(Math.abs(y2 - y1) / SEPARACION_Y) > 0;
  const desvio = salta ? CAJA.ancho / 2 + 18 : 0;
  const medio = y1 + (y2 - y1) / 2;
  return `M ${a.x} ${y1} C ${a.x - desvio} ${medio}, ${b.x - desvio} ${medio}, ${b.x} ${y2}`;
}

// Vuelta atras: baja por debajo de todo el grafo, recorre su carril hacia la
// izquierda y sube al destino. Es la misma flecha que las otras pero no el mismo
// viaje, y por eso no comparte espacio con ellas.
//
// Todas van de derecha a izquierda, porque eso es lo que las hace vueltas atras:
// una que fuera hacia delante seria camino feliz y no tendria por que bajar.
function caminoCarril(a, b, carril, suelo) {
  const y = suelo + CARRIL * (carril + 1);
  const r = 12;
  const x1 = a.x;
  // Sube por delante del destino y entra por su costado izquierdo, no por el
  // canto de abajo: el escritor tiene el borrador justo debajo, y una flecha que
  // llegara desde el suelo le pasaria por encima.
  const x2 = b.x - CAJA.ancho / 2 - 24;
  return [
    `M ${x1} ${a.y + CAJA.alto / 2}`,
    `L ${x1} ${y - r}`,
    `Q ${x1} ${y}, ${x1 - r} ${y}`,
    `L ${x2 + r} ${y}`,
    `Q ${x2} ${y}, ${x2} ${y - r}`,
    `L ${x2} ${b.y + r}`,
    `Q ${x2} ${b.y}, ${x2 + r} ${b.y}`,
    `L ${b.x - CAJA.ancho / 2} ${b.y}`,
  ].join(' ');
}

// El nombre en una o dos lineas, partido por palabras. Dos y no mas: a la
// tercera la caja crece mas que lo que se gana en ancho.
function lineasDe(nombre) {
  if (nombre.length <= MAXIMO_LINEA) return [nombre];
  const palabras = nombre.split(' ');
  const filas = [palabras.shift()];
  for (const palabra of palabras) {
    const ultima = filas.length - 1;
    if (filas.length < 2 && (filas[ultima] + ' ' + palabra).length > MAXIMO_LINEA) {
      filas.push(palabra);
    } else {
      filas[ultima] += ' ' + palabra;
    }
  }
  return filas;
}

// ------------------------------------------------------------------- dibujo

// La silueta de cada tipo de nodo. Tres y ninguna mas: una cuarta obliga a ir a
// mirar la leyenda cada vez.
function silueta(forma) {
  const w = CAJA.ancho;
  const h = CAJA.alto;
  if (forma === 'agente') {
    // Caja de esquinas muy redondeadas: lo que piensa.
    return elemento('rect', {
      x: -w / 2, y: -h / 2, width: w, height: h, rx: h / 2, class: 'nodo__silueta',
    });
  }
  if (forma === 'decision') {
    // Hexagono alargado: lo que decide.
    const p = h / 2;
    return elemento('polygon', {
      points: [`${-w / 2 + p},${-h / 2}`, `${w / 2 - p},${-h / 2}`, `${w / 2},0`,
        `${w / 2 - p},${h / 2}`, `${-w / 2 + p},${h / 2}`, `${-w / 2},0`].join(' '),
      class: 'nodo__silueta',
    });
  }
  // Caja recta: lo que se guarda.
  return elemento('rect', {
    x: -w / 2, y: -h / 2, width: w, height: h, rx: 3, class: 'nodo__silueta',
  });
}

export async function crearGrafo(svg, { nodos, aristas, onSenalar, onElegir } = {}) {
  svg.textContent = '';
  svg.setAttribute('preserveAspectRatio', 'xMidYMid meet');

  const porId = new Map(nodos.map((n) => [n.id, n]));
  const suelo = Math.max(...nodos.map((n) => n.y)) + CAJA.alto / 2 + SUELO;

  // Cada arista lleva su id estable `de>a`, que es el mismo que usa el recorrido
  // de un capitulo para decir cual no se recorrio.
  const conAristas = aristas.map((a) => ({
    ...a,
    id: `${a.de}>${a.a}`,
    origen: porId.get(a.de),
    destino: porId.get(a.a),
  }));

  // ------------------------------------------------------------ defs y capas
  const defs = elemento('defs');
  for (const [nombre, clase] of [['punta', 'punta'], ['punta-viva', 'punta punta--viva']]) {
    const marcador = elemento('marker', {
      id: nombre, viewBox: '0 0 10 10', refX: 9, refY: 5,
      markerUnits: 'userSpaceOnUse', markerWidth: 10, markerHeight: 10,
      orient: 'auto',
    });
    marcador.append(elemento('path', { d: 'M 0 0 L 10 5 L 0 10 z', class: clase }));
    defs.append(marcador);
  }
  svg.append(defs);

  // El lienzo entero cuelga de un solo grupo: el zoom y el arrastre mueven el
  // viewBox, no las cajas, asi que nada se recalcula al navegar.
  const capaAristas = elemento('g', { class: 'grafo__aristas' });
  const capaNodos = elemento('g', { class: 'grafo__nodos' });
  svg.append(capaAristas, capaNodos);

  const piezasArista = new Map();
  for (const arista of conAristas) {
    const d = arista.tipo === 'realimenta'
      ? caminoCarril(arista.origen, arista.destino, arista.carril || 0, suelo)
      : (arista.origen.nivel === arista.destino.nivel
        ? caminoVertical(arista.origen, arista.destino)
        : caminoRecto(arista.origen, arista.destino));
    const g = elemento('g', { class: 'arista', 'data-tipo': arista.tipo || 'recta' });
    const trazo = elemento('path', {
      d, class: 'arista__trazo', 'marker-end': 'url(#punta)',
    });
    const viajero = elemento('circle', { class: 'arista__viajero', r: 3.4 });
    g.append(trazo, viajero);
    capaAristas.append(g);
    piezasArista.set(arista.id, { g, trazo, viajero, arista, largo: null });
  }

  const piezasNodo = new Map();
  for (const nodo of nodos) {
    const g = elemento('g', {
      class: 'nodo',
      'data-forma': nodo.forma,
      'data-estado': 'pendiente',
      transform: `translate(${nodo.x} ${nodo.y})`,
      tabindex: '0',
      role: 'button',
      'aria-label': nodo.nombre,
    });
    const forma = silueta(nodo.forma);
    // La marca del nodo completado. Discreta y en el canto, porque lo que tiene
    // que leerse de un vistazo es el color del borde y no un icono.
    // La marca vive en el canto de arriba a la derecha, pegada al filo: mas
    // adentro se le echa encima al nombre, que en esta caja llega a doce
    // caracteres de ancho.
    const marca = elemento('path', {
      class: 'nodo__marca',
      d: `M ${CAJA.ancho / 2 - 16} ${-CAJA.alto / 2 + 9} l 3 3.2 l 5.6 -6.4`,
    });
    const etiqueta = elemento('text', { class: 'nodo__nombre' });
    // El contador de intentos cuelga por debajo de la caja y solo aparece cuando
    // hay algo que contar: un "0/3" permanente es ruido.
    const pie = elemento('text', { class: 'nodo__pie', y: CAJA.alto / 2 + 15 });

    g.append(forma, marca, etiqueta, pie);
    capaNodos.append(g);
    piezasNodo.set(nodo.id, { g, etiqueta, pie, nodo });

    g.addEventListener('pointerenter', () => onSenalar?.(nodo.id));
    g.addEventListener('pointerleave', () => onSenalar?.(null));
    g.addEventListener('click', () => elegirNodo(nodo.id));
    g.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); elegirNodo(nodo.id); }
    });
  }

  // ------------------------------------------------------------- el latido

  // Un solo requestAnimationFrame para el grafo entero, y solo mientras hay algo
  // que mover. Con la sala cerrada o la pestana del navegador de fondo no se
  // pide ni un fotograma: una animacion de adorno no tiene por que gastar bateria
  // de alguien que esta mirando otra cosa.
  //
  // Con prefers-reduced-motion el bucle no arranca nunca. La arista activa se
  // sigue distinguiendo -cambia de color y de grosor-, que es la misma regla que
  // gobierna los estados de nodo: lo que se pierde es la urgencia, no el dato.
  const quieto = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const activas = new Set();
  let visible = false;
  let latiendo = false;

  function fotograma(t) {
    if (!latiendo) return;
    const avance = (t / 1000) * FLUJO.velocidad;
    const ciclo = FLUJO.guion + FLUJO.hueco;
    for (const id of activas) {
      const pieza = piezasArista.get(id);
      if (!pieza) continue;
      if (pieza.largo == null) pieza.largo = pieza.trazo.getTotalLength();
      // Los guiones corren hacia el destino: en SVG eso es restarle al offset.
      pieza.trazo.style.strokeDashoffset = String(-(avance % ciclo));
      const punto = pieza.trazo.getPointAtLength(avance % pieza.largo);
      pieza.viajero.setAttribute('cx', punto.x);
      pieza.viajero.setAttribute('cy', punto.y);
    }
    requestAnimationFrame(fotograma);
  }

  function revisarLatido() {
    const deberia = visible && !quieto && activas.size > 0 && !document.hidden;
    if (deberia === latiendo) return;
    latiendo = deberia;
    if (latiendo) requestAnimationFrame(fotograma);
  }

  document.addEventListener('visibilitychange', revisarLatido);

  // --------------------------------------------------------- estado dibujado
  let elegido = null;
  let recorrido = null;
  let fueraAristas = null;

  function elegirNodo(id) {
    elegido = id;
    for (const [otro, pieza] of piezasNodo) {
      pieza.g.classList.toggle('nodo--elegido', otro === id);
    }
    onElegir?.(id);
  }

  function ponerNombre(pieza, sufijo) {
    const filas = lineasDe(pieza.nodo.nombre);
    filas[filas.length - 1] += sufijo;
    pieza.etiqueta.textContent = '';
    // Con dos lineas el bloque sube media linea para seguir centrado en la caja.
    const primera = filas.length === 1 ? 0 : -0.52;
    filas.forEach((fila, i) => {
      const tspan = elemento('tspan', { x: 0, dy: `${i === 0 ? primera : 1.05}em` });
      tspan.textContent = fila;
      pieza.etiqueta.append(tspan);
    });
  }

  function reetiquetar() {
    for (const [id, pieza] of piezasNodo) {
      ponerNombre(pieza, recorrido?.get(id) || '');
      pieza.g.classList.toggle('nodo--fuera',
        Boolean(recorrido) && !recorrido.has(id));
    }
    for (const [id, pieza] of piezasArista) {
      pieza.g.classList.toggle('arista--fuera', Boolean(fueraAristas?.has(id)));
    }
  }

  // ------------------------------------------------------------ zoom y pan

  // El encuadre es el viewBox y nada mas. Con preserveAspectRatio puesto, la
  // misma caja se ve igual en cualquier proporcion de pantalla.
  const limites = (() => {
    const xs = nodos.map((n) => n.x);
    const ys = nodos.map((n) => n.y);
    const carriles = conAristas.filter((a) => a.tipo === 'realimenta').length;
    return {
      x: Math.min(...xs) - CAJA.ancho / 2 - 24 - MARGEN,
      y: Math.min(...ys) - CAJA.alto / 2 - MARGEN,
      ancho: (Math.max(...xs) - Math.min(...xs)) + CAJA.ancho + 24 + MARGEN * 2,
      alto: (Math.max(...ys) - Math.min(...ys)) + CAJA.alto + MARGEN * 2
        + SUELO + CARRIL * carriles,
    };
  })();

  const vista = { ...limites };

  function pintarVista() {
    svg.setAttribute('viewBox', `${vista.x} ${vista.y} ${vista.ancho} ${vista.alto}`);
  }

  function encuadrar() {
    Object.assign(vista, limites);
    pintarVista();
  }

  // El zoom es sobre el puntero: lo que hay debajo del raton se queda debajo del
  // raton, que es lo unico que no marea.
  svg.addEventListener('wheel', (e) => {
    e.preventDefault();
    const caja = svg.getBoundingClientRect();
    const fx = (e.clientX - caja.left) / caja.width;
    const fy = (e.clientY - caja.top) / caja.height;
    const factor = e.deltaY < 0 ? 1 / ZOOM.paso : ZOOM.paso;
    const anchoNuevo = Math.min(
      Math.max(vista.ancho * factor, limites.ancho / ZOOM.max), limites.ancho / ZOOM.min);
    const escala = anchoNuevo / vista.ancho;
    const altoNuevo = vista.alto * escala;
    vista.x += (vista.ancho - anchoNuevo) * fx;
    vista.y += (vista.alto - altoNuevo) * fy;
    vista.ancho = anchoNuevo;
    vista.alto = altoNuevo;
    pintarVista();
  }, { passive: false });

  let arrastre = null;
  svg.addEventListener('pointerdown', (e) => {
    if (e.button !== 0) return;
    arrastre = { x: e.clientX, y: e.clientY, vx: vista.x, vy: vista.y, movido: false };
    svg.setPointerCapture(e.pointerId);
  });
  svg.addEventListener('pointermove', (e) => {
    if (!arrastre) return;
    const caja = svg.getBoundingClientRect();
    const dx = (e.clientX - arrastre.x) * (vista.ancho / caja.width);
    const dy = (e.clientY - arrastre.y) * (vista.alto / caja.height);
    if (Math.abs(dx) + Math.abs(dy) > 2) arrastre.movido = true;
    vista.x = arrastre.vx - dx;
    vista.y = arrastre.vy - dy;
    pintarVista();
    svg.classList.add('grafo__svg--arrastrando');
  });
  const soltar = (e) => {
    if (!arrastre) return;
    if (arrastre.movido) svg.classList.add('grafo__svg--movido');
    arrastre = null;
    svg.classList.remove('grafo__svg--arrastrando');
    if (e?.pointerId != null && svg.hasPointerCapture(e.pointerId)) {
      svg.releasePointerCapture(e.pointerId);
    }
  };
  svg.addEventListener('pointerup', soltar);
  svg.addEventListener('pointercancel', soltar);

  // Un clic que ha arrastrado no es un clic: si no, mover el grafo abre fichas.
  capaNodos.addEventListener('click', (e) => {
    if (svg.classList.contains('grafo__svg--movido')) {
      e.stopPropagation();
      svg.classList.remove('grafo__svg--movido');
    }
  }, true);

  reetiquetar();
  encuadrar();

  // Los cinco estados en los que puede estar un nodo, y ninguno mas. Un nodo
  // tiene exactamente uno: son excluyentes porque describen el mismo momento.
  const ESTADOS = ['pendiente', 'activo', 'completado', 'reintento', 'bloqueado'];

  // La superficie con la que se gobierna el grafo desde fuera. Deliberadamente
  // tonta: el grafo no sabe de donde sale el dato -de un canon leido, de una
  // ejecucion en curso o de un replay- y por eso puede servir a los tres.
  function setNodeState(id, estado, pie = '') {
    const pieza = piezasNodo.get(id);
    if (!pieza) return;
    if (!ESTADOS.includes(estado)) throw new Error('estado desconocido: ' + estado);
    pieza.g.dataset.estado = estado;
    pieza.pie.textContent = pie;
  }

  function setEdgeActive(id, activa) {
    const pieza = piezasArista.get(id);
    if (!pieza) return;
    const si = Boolean(activa);
    pieza.g.classList.toggle('arista--activa', si);
    pieza.trazo.setAttribute('marker-end', si ? 'url(#punta-viva)' : 'url(#punta)');
    if (si) {
      activas.add(id);
      pieza.trazo.style.strokeDasharray = `${FLUJO.guion} ${FLUJO.hueco}`;
    } else {
      activas.delete(id);
      pieza.trazo.style.strokeDasharray = '';
      pieza.trazo.style.strokeDashoffset = '';
    }
    revisarLatido();
  }

  return {
    setNodeState,
    setEdgeActive,
    // Un nodo se enciende cuando el canon dice que ya ha corrido: es el criterio
    // del rastro de §19 -no hay diario, hay lo que quedo escrito- aplicado al
    // dibujo en vez de a una tarjeta.
    refrescar(vivos) {
      for (const id of piezasNodo.keys()) {
        setNodeState(id, vivos[id] ? 'completado' : 'pendiente');
      }
      reetiquetar();
    },
    // El recorrido de un capitulo: por donde paso y cuantas veces. Lo que no
    // recorrio se apaga, no se esconde, para que se vea lo que no se uso.
    marcarRecorrido(mapa, aristasFuera) {
      recorrido = mapa;
      fueraAristas = aristasFuera || null;
      reetiquetar();
    },
    elegir: elegirNodo,
    encuadrar,
    mostrar(si) {
      visible = si;
      if (si) encuadrar();
      revisarLatido();
    },
    destruir() {
      visible = false;
      activas.clear();
      revisarLatido();
      document.removeEventListener('visibilitychange', revisarLatido);
    },
  };
}
