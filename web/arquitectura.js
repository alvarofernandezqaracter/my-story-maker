// Sala de arquitectura: el sistema que escribe la novela, no la novela.
//
// Las otras tres salas contestan «cómo va el libro». Esta contesta «cómo está
// montado esto», que es la pregunta que no tenía dónde mirarse: la máquina de
// estados vive en el spec y en la skill, y la página solo enseñaba su resultado.
// Aquí el pipeline de §4, §7, §8 y §9 se dibuja entero, con el canon encima
// cuando lo hay.
//
// Todo lo que se lee en el panel sale del spec y va citado con su sección. Todo
// lo que se lee bajo «en este canon» sale de /api/proyecto. No hay una tercera
// fuente, y eso es deliberado: si aquí hiciera falta inventar un dato sería que
// falta modelo, igual que en el resto de la interfaz (§19).
import { crearGrafo } from './grafo.js';

const $ = (id) => document.getElementById(id);

// --------------------------------------------------------------- el modelo

// El pipeline como DAG por capas. `nivel` es la banda; dentro de una banda los
// nodos se reparten en X por orden de declaración, sin una sola coordenada
// puesta a mano.
//
// Un artefacto comparte banda con el agente que lo produce. Podría ir en una
// banda propia y el grafo sería más puro, pero serían dieciocho bandas en una
// pantalla de setecientos píxeles y los nombres no se leerían: la banda es la
// etapa del pipeline, y el fichero que sale de ella es parte de la etapa.
const NODOS = [
  {
    id: 'brief', nivel: 0, forma: 'artefacto', nombre: 'brief',
    descripcion: 'Los cinco campos con los que arranca todo. Los teclea una persona en la'
      + ' sesión de Claude Code: el orquestador los pide y no se los inventa.',
    entradas: ['Época, premisa, tono, número de capítulos y palabras por capítulo'],
    salidas: ['canon/brief.json'],
    reglas: [
      '§3 — los cinco campos son obligatorios y ninguno tiene valor por defecto',
      '§6 — parte inmutable: cambiarlo a mitad de libro invalida lo ya escrito',
      '§19 — esta página lo lee; escribirlo es de la sesión que orquesta',
    ],
    canon: (p) => (p.brief ? [
      ['época', p.brief.epoca],
      ['capítulos pedidos', p.brief.capitulos],
      ['palabras por capítulo', p.brief.palabras_por_capitulo],
    ] : null),
  },
  {
    id: 'investigador', nivel: 1, forma: 'agente', nombre: 'investigador',
    descripcion: 'Levanta el dossier de época a partir del brief. Trabaja de memoria: su'
      + ' subagente tiene solo Read y la búsqueda web no existe.',
    entradas: ['brief'],
    salidas: ['{ datos: [...] }, cada uno con categoría, fuente y estado'],
    reglas: [
      '§5 — cada dato sale verificado, sin_verificar o inventado',
      'VD-04 — todo dato lleva fuente y estado válido; un verificado con fuente'
        + ' «modelo» es inválido',
      '§10 — carga la skill formato-dossier',
      '§21 — devuelve JSON: en el canon escribe el orquestador',
    ],
    canon: (p) => (p.dossier.length ? [
      ['intervenciones', 'una, en la preparación'],
      ['datos entregados', p.dossier.length],
    ] : null),
  },
  {
    id: 'dossier', nivel: 1, forma: 'artefacto', nombre: 'dossier',
    descripcion: 'Las fichas de época contra las que se juzgan los anacronismos. Se escribe'
      + ' una vez en la preparación y nadie lo toca después.',
    entradas: ['La propuesta del investigador, una vez pasada VD-04'],
    salidas: ['canon/dossier.json', 'El bloque «época» del paquete de contexto'],
    reglas: [
      '§6 — parte inmutable del canon',
      '§7 — entra en el paquete por coincidencia de etiquetas, los verificados primero',
      '§9 — VD-04 no habilita al arquitecto hasta que todos los datos pasan',
    ],
    canon: (p) => (p.dossier.length ? [
      ['datos', p.dossier.length],
      ['verificados', p.dossier.filter((d) => d.estado === 'verificado').length],
      ['sin verificar', p.dossier.filter((d) => d.estado === 'sin_verificar').length],
      ['inventados', p.dossier.filter((d) => d.estado === 'inventado').length],
    ] : null),
  },
  {
    id: 'arquitecto', nivel: 2, forma: 'agente', nombre: 'arquitecto',
    descripcion: 'Monta el arco en tres actos, una ficha por capítulo y una por personaje,'
      + ' coherentes con el dossier ya cerrado.',
    entradas: ['brief', 'dossier ya cerrado'],
    salidas: ['{ personajes, capitulos }'],
    reglas: [
      'VD-07 — el número de capítulos cae dentro de capitulos_min y capitulos_max',
      'VD-03 — los ids que referencia existen en el canon',
      '§3 — cada ficha lleva fecha y etiquetas: sin ellas el paquete se queda sin'
        + ' época ni cronología',
      '§10 — carga la skill formato-fichas',
    ],
    canon: (p) => (p.capitulos.length ? [
      ['intervenciones', 'una, en la preparación'],
      ['capítulos de la escaleta', p.capitulos.length],
      ['personajes', p.reparto.length],
    ] : null),
  },
  {
    id: 'escaleta', nivel: 2, forma: 'artefacto', nombre: 'escaleta',
    descripcion: 'Las fichas de capítulo: encargo, personajes, sinopsis, día de ficción,'
      + ' etiquetas y palabras objetivo.',
    entradas: ['La propuesta del arquitecto, pasadas VD-03, VD-05 y VD-07'],
    salidas: ['canon/escaleta.json', 'El bloque «encargo» del paquete de contexto'],
    reglas: [
      '§6 — parte inmutable',
      '§4 — el estado de cada ficha es lo que hace reanudable el libro',
      '§7 — su fecha y sus etiquetas son lo único contra lo que se cruzan época y cronología',
    ],
    canon: (p) => (p.capitulos.length ? [
      ['capítulos', p.capitulos.length],
      ['aprobados', p.capitulos.filter((c) => c.estado === 'aprobado').length],
      ['con día de ficción', p.capitulos.filter((c) => c.fecha).length],
    ] : null),
  },
  {
    id: 'personajes', nivel: 2, forma: 'artefacto', nombre: 'personajes',
    descripcion: 'Las fichas de personaje. Voz, motivación y arco no se mueven; ubicación y'
      + ' sabe los va cambiando el cronista, un escalón por capítulo aprobado.',
    entradas: ['La propuesta del arquitecto', 'Los cambios del cronista al aprobar un capítulo'],
    salidas: ['canon/personajes.json', 'El bloque «personajes» del paquete de contexto'],
    reglas: [
      '§6 — identidad inmutable; ubicación y sabe evolucionan',
      '§7 — entran enteras las fichas de quien sale en el capítulo',
      'DA-14 — sabe solo acumula: hoy no hay forma de retractar un «Ignora»',
    ],
    canon: (p) => (p.reparto.length ? [
      ['fichas', p.reparto.length],
      ['cosas que saben o ignoran', p.reparto.reduce((n, x) => n + (x.sabe || []).length, 0)],
    ] : null),
  },
  {
    id: 'contexto', nivel: 3, forma: 'artefacto', nombre: 'paquete de contexto',
    descripcion: 'Los nueve bloques que ve el escritor, y lo único que ve: no consulta el'
      + ' canon por su cuenta. Queda en disco para poder auditar después por qué'
      + ' salió lo que salió.',
    entradas: ['escaleta, personajes, dossier, resúmenes, hilos y timeline del canon'],
    salidas: ['contexto/cap-NN.md'],
    reglas: [
      '§7 — nueve bloques: encargo, personajes, reparto de fondo, memoria reciente,'
        + ' memoria larga, hilos vivos, época, cronología y enganche',
      '§7 — el texto completo de capítulos anteriores no entra nunca, salvo el enganche',
      '§7 — si pasa de tope_contexto se recorta en orden: memoria larga, cronología,'
        + ' reparto de fondo, época',
      '§7 — encargo, personajes e hilos vivos no se recortan; si aun así no cabe, el'
        + ' capítulo se marca bloqueado',
      '§21 — el ensamblado lo hace un modelo: el determinismo pasa de garantizado a instruido',
    ],
    canon: (p) => {
      const con = p.capitulos.filter((c) => c.contexto_tokens != null);
      if (!con.length) return null;
      const tokens = con.map((c) => c.contexto_tokens);
      return [
        ['paquetes escritos', con.length],
        ['tokens', Math.min(...tokens) + ' – ' + Math.max(...tokens)],
        ['capítulos con recorte', p.capitulos.filter((c) => c.recortes.length).length],
      ];
    },
  },
  {
    id: 'escritor', nivel: 4, forma: 'agente', nombre: 'escritor',
    descripcion: 'Redacta el capítulo entero a partir del paquete. Deja el borrador en disco'
      + ' y devuelve la ruta, no el texto: un capítulo por tres intentos y por seis'
      + ' capítulos no cabe en una conversación.',
    entradas: ['paquete de contexto', 'incidencias del intento anterior, por severidad',
      'su propio texto, en todos los intentos menos el último'],
    salidas: ['{ ruta, faltantes }'],
    reglas: [
      '§8 — hasta max_intentos intentos por capítulo',
      '§8 — el último intento va desde cero, y el que descarta VD-08 también',
      '§8 — los demás reciben su texto para arreglo quirúrgico: tocar lo señalado y nada más',
      '§5 — lo que le falta lo anota en faltantes y resuelve la escena sin ello',
      '§10 — carga las skills formato-paquete-contexto y estilo-prosa',
    ],
    canon: (p) => {
      const tocados = p.capitulos.filter((c) => c.intentos);
      if (!tocados.length) return null;
      return [
        ['borradores escritos', tocados.reduce((n, c) => n + c.intentos, 0)],
        ['capítulos tocados', tocados.length],
        ['a la primera', tocados.filter((c) => c.intentos === 1
          && c.estado === 'aprobado').length],
      ];
    },
  },
  {
    id: 'borrador', nivel: 4, forma: 'artefacto', nombre: 'borrador',
    descripcion: 'El capítulo del intento, en capitulos/cap-NN-intento-K.md. Es la única'
      + ' excepción a que ningún subagente escriba: no es canon hasta que pasa el gate.',
    entradas: ['Lo que deja el escritor'],
    salidas: ['El texto que miden VD-08 y los tres validadores'],
    reglas: [
      '§21 — no es canon: entra por el cronista y solo si el gate lo aprobó',
      '§6 — los intentos descartados quedan en disco como rastro',
      '§6 — el generador de contexto no los lee jamás: un capítulo desaprobado no deja'
        + ' huella en lo que el escritor ve del siguiente',
    ],
    canon: (p) => {
      const intentos = p.capitulos.reduce((n, c) => n + c.intentos, 0);
      if (!intentos) return null;
      const aprobados = p.capitulos.filter((c) => c.estado === 'aprobado').length;
      return [['ficheros de intento', intentos], ['descartados', intentos - aprobados]];
    },
  },
  {
    id: 'vd08', nivel: 5, forma: 'decision', nombre: 'VD-08',
    descripcion: 'Cuenta palabras y párrafos antes de gastar las tres llamadas al validador.'
      + ' Es la única comprobación de dos escalones, y por eso lleva dos márgenes.',
    entradas: ['borrador del intento',
      'margenes.palabras_aviso, palabras_bloqueo y parrafos_min'],
    salidas: ['ok, aviso o bloqueo'],
    reglas: [
      '§9 — dentro de palabras_aviso sigue, y el aviso viaja al reintento',
      '§9 — fuera de palabras_bloqueo o por debajo de parrafos_min descarta el intento'
        + ' sin llamar al validador',
      '§8 — el intento que descarta vuelve al escritor desde cero: no hay arreglo'
        + ' quirúrgico en un texto al que le falta medio capítulo',
      '§9 — es la regla que ahorra dinero, y por eso va antes del validador y no después',
    ],
    canon: (p) => (p.margenes ? [
      ['aviso', '±' + Math.round(p.margenes.palabras_aviso * 100) + ' %'],
      ['bloqueo', '±' + Math.round(p.margenes.palabras_bloqueo * 100) + ' %'],
      ['párrafos mínimos', p.margenes.parrafos_min],
      ['borradores medidos', p.capitulos.reduce((n, c) => n + c.intentos, 0)],
    ] : null),
  },
  {
    id: 'val-continuidad', nivel: 6, forma: 'agente', nombre: 'continuidad', dimension: 0,
    descripcion: 'Puntúa de 1 a 5 la coherencia con el canon: dónde está cada uno, qué sabe'
      + ' cada uno y cuándo pasa cada cosa.',
    entradas: ['borrador del intento', 'paquete de contexto', 'encargo del capítulo'],
    salidas: ['un bloque de revisión: nota 1-5 e incidencias con cita, severidad y sugerencia'],
    reglas: [
      '§8 — nota 1 si contradice un hecho del canon; nota 5 si todo cuadra y lo usa'
        + ' con precisión',
      '§8 — contradecir el canon es incidencia grave, y una grave veta el capítulo por sí sola',
      '§21 — se lanza en el mismo mensaje que los otros dos y no los ve',
      'VD-10 — tres dimensiones, una vez cada una, nota entera de 1 a 5',
      '§10 — carga la skill rubricas-validador',
    ],
  },
  {
    id: 'val-anacronismos', nivel: 6, forma: 'agente', nombre: 'anacronismos', dimension: 1,
    descripcion: 'Puntúa objetos, costumbres, instituciones y léxico contra el dossier de época.',
    entradas: ['borrador del intento', 'dossier de época', 'paquete de contexto'],
    salidas: ['un bloque de revisión: nota 1-5 e incidencias con cita, severidad y sugerencia'],
    reglas: [
      '§8 — nota 1 si rompe un dato verificado; nota 3 si choca con un sin_verificar',
      '§8 — romper un verificado es incidencia grave',
      '§5 — sus fallos típicos son el falso positivo de léxico moderno pero válido y el'
        + ' anacronismo conceptual, que es el caro y el que menos salta',
      'VD-10 — nota entera de 1 a 5',
    ],
  },
  {
    id: 'val-logica', nivel: 6, forma: 'agente', nombre: 'lógica y ritmo', dimension: 2,
    descripcion: 'Puntúa causa y efecto, cumplimiento del objetivo del capítulo y tensión.',
    entradas: ['borrador del intento', 'encargo del capítulo'],
    salidas: ['un bloque de revisión: nota 1-5 e incidencias con cita, severidad y sugerencia'],
    reglas: [
      '§8 — nota 1 si la escena no lleva a ninguna parte; nota 5 si cada escena empuja'
        + ' la siguiente',
      '§5 — resuelve su dimensión sin releer lo ya juzgado, para no arrastrar una'
        + ' impresión general',
      'VD-10 — nota entera de 1 a 5',
    ],
  },
  {
    id: 'gate', nivel: 7, forma: 'decision', nombre: 'gate',
    descripcion: 'La única decisión que cierra un capítulo. Entran tres notas y sale un sí o'
      + ' un no: un capítulo se da por bueno aquí, no cuando el escritor termina.',
    entradas: ['los tres bloques de revisión, ya pasados por VD-10'],
    salidas: ['aprueba, o reintenta', 'al agotar los intentos, capítulo y proyecto bloqueados'],
    reglas: [
      '§8 — aprueba = min(notas) >= nota_minima y media >= media_minima y ninguna grave',
      '§8 — la incidencia grave veta por sí sola: tres cuatros caen por una'
        + ' contradicción de canon',
      '§8 — no existe nota global; siempre son tres números',
      '§8 — al agotar intentos conserva el de mejor media, en propuesto, y para el proceso',
      '§21 — la fórmula está escrita, pero la suma la hace un modelo: es el punto más'
        + ' débil del sistema, y por eso esta página la rehace (DA-15)',
    ],
    canon: (p) => {
      const filas = [
        ['nota mínima', p.gate.nota_minima],
        ['media mínima', p.gate.media_minima],
        ['intentos', p.gate.max_intentos],
      ];
      if (p.auditoria?.revisados) {
        filas.push(['cuentas revisadas', p.auditoria.revisados]);
        filas.push(['no cuadran', p.auditoria.discrepancias.length]);
      }
      return filas;
    },
  },
  {
    id: 'cronista', nivel: 8, forma: 'agente', nombre: 'cronista',
    descripcion: 'Corre una sola vez por capítulo, después del gate y solo sobre el intento'
      + ' aprobado: así pasa una vez por el texto que se queda en lugar de tres por'
      + ' borradores que se descartan.',
    entradas: ['el texto aprobado', 'la ficha del capítulo', 'las fichas de quien sale'],
    salidas: ['resumen, hilos abiertos y cerrados, cambios de ubicación y sabe,'
      + ' eventos de trama'],
    reglas: [
      'VD-09 — personajes presentes ⊆ personajes de la ficha',
      'VD-05 — el evento de trama lleva capítulo; el histórico no lo lleva',
      'VD-06 — solo hay resumen si el capítulo está aprobado',
      '§5 — callarse un hilo abierto es su fallo caro: el editor global solo ve lo que'
        + ' él escribió',
      '§21 — ningún VD-xx comprueba que respete un «Ignora» de una ficha: el hueco'
        + ' sigue abierto',
    ],
    canon: (p) => {
      const con = p.capitulos.filter((c) => c.resumen);
      if (!con.length) return null;
      return [
        ['intervenciones', con.length],
        ['eventos de trama', p.cronologia.filter((e) => e.capitulo).length],
        ['hilos que siguen vivos', p.deuda.length],
      ];
    },
  },
  {
    id: 'canon', nivel: 8, forma: 'artefacto', nombre: 'canon',
    descripcion: 'La memoria a largo plazo. Crece un escalón por capítulo aprobado y lo'
      + ' escribe el orquestador: ningún subagente toca estos ficheros.',
    entradas: ['la propuesta del cronista, ya comprobada'],
    salidas: ['resumenes/cap-NN.json, personajes.json, hilos.json y timeline.json',
      'el paquete de contexto del capítulo siguiente'],
    reglas: [
      '§21 — una sola escritura por capítulo, y de una vez',
      'VD-11 — o entran resumen, cambios de ficha y eventos juntos, o no entra nada',
      '§21 — el estado vive aquí y no en memoria del proceso: por eso reanudar no'
        + ' necesita argumentos, y por eso reanudar no desbloquea',
      '§4 — un capítulo a la vez: el N+1 se escribe con el canon que dejó el N',
    ],
    canon: (p) => {
      const aprobados = p.capitulos.filter((c) => c.estado === 'aprobado').length;
      if (!aprobados) return null;
      return [
        ['capítulos aprobados', aprobados],
        ['eventos en la cronología', p.cronologia.length],
        ['hilos vivos', p.deuda.length],
      ];
    },
  },
  {
    id: 'editor', nivel: 9, forma: 'agente', nombre: 'editor global',
    descripcion: 'Corre una sola vez, cuando el proyecto entra en escrito y fuera del loop.'
      + ' Lee los resúmenes, nunca el texto.',
    entradas: ['los resúmenes de todos los capítulos', 'la escaleta', 'las fichas de personaje'],
    salidas: ['{ retoques: [...] } con id, tipo, capítulos, descripción y severidad'],
    reglas: [
      '§11 — no lee el texto: si algo no se ve en los resúmenes es que el cronista no'
        + ' lo registró',
      '§11 — lista corta y accionable: diez que se puedan ejecutar valen más que'
        + ' cuarenta observaciones',
      '§11 — no aplica nada ni dispara reescrituras',
    ],
    canon: (p) => (p.retoques ? [['intervenciones', 'una, al cerrar']] : null),
  },
  {
    id: 'retoques', nivel: 9, forma: 'artefacto', nombre: 'retoques.md',
    descripcion: 'La lista de tareas para una persona. Se guarda junto al canon y no dentro:'
      + ' el canon es la verdad de la novela escrita, y esto es trabajo pendiente.',
    entradas: ['la lista del editor global'],
    salidas: ['retoques.md, al lado del canon'],
    reglas: [
      '§11 — se aplican a mano; automatizar esa vuelta está fuera de alcance (DA-07)',
      '§4 — al escribirlo el proyecto pasa a editado, que es el estado final',
    ],
    canon: (p) => (p.retoques ? [['fichero', p.ruta_retoques]] : null),
  },
];

// El flujo. Las de `realimenta` son las vueltas atrás del loop de §8 y la del
// canon que alimenta el capítulo siguiente (§4): van por un carril propio a la
// izquierda y discontinuas, porque son la misma flecha pero no el mismo viaje.
//
// La entrada «brief» del arquitecto no se dibuja: sería una recta por encima de
// la columna del investigador y del dossier, que es justo lo que un grafo por
// capas evita. Está donde tiene que estar, en sus ENTRADAS.
const ARISTAS = [
  { de: 'brief', a: 'investigador' },
  { de: 'investigador', a: 'dossier' },
  { de: 'dossier', a: 'arquitecto' },
  { de: 'arquitecto', a: 'escaleta' },
  { de: 'arquitecto', a: 'personajes' },
  { de: 'escaleta', a: 'contexto' },
  { de: 'personajes', a: 'contexto' },
  { de: 'contexto', a: 'escritor' },
  { de: 'escritor', a: 'borrador' },
  { de: 'borrador', a: 'vd08' },
  { de: 'vd08', a: 'val-continuidad' },
  { de: 'vd08', a: 'val-anacronismos' },
  { de: 'vd08', a: 'val-logica' },
  { de: 'val-continuidad', a: 'gate' },
  { de: 'val-anacronismos', a: 'gate' },
  { de: 'val-logica', a: 'gate' },
  { de: 'gate', a: 'cronista' },
  { de: 'cronista', a: 'canon' },
  { de: 'canon', a: 'editor' },
  { de: 'editor', a: 'retoques' },
  { de: 'vd08', a: 'escritor', tipo: 'realimenta', carril: 0 },
  { de: 'gate', a: 'escritor', tipo: 'realimenta', carril: 1 },
  { de: 'canon', a: 'contexto', tipo: 'realimenta', carril: 2 },
];

const TIPO = { agente: 'agente', artefacto: 'artefacto', decision: 'decisión' };

// --------------------------------------------------------------- el reparto

const PASO_Y = 1.75;
const SEPARACION_X = 3.6;   // separación mínima garantizada entre centros

// Layout por capas y nada más: la banda la da el nivel, y dentro de la banda los
// nodos se reparten simétricos con una separación fija. Mismo modelo, mismo
// dibujo, siempre y en cualquier pantalla.
function disponer(nodos) {
  const bandas = new Map();
  for (const nodo of nodos) {
    if (!bandas.has(nodo.nivel)) bandas.set(nodo.nivel, []);
    bandas.get(nodo.nivel).push(nodo);
  }
  for (const [, lista] of bandas) {
    lista.forEach((nodo, i) => {
      nodo.x = (i - (lista.length - 1) / 2) * SEPARACION_X;
      nodo.y = -nodo.nivel * PASO_Y;
      nodo.compartida = lista.length > 1;
    });
  }
  return nodos;
}

// --------------------------------------------------------- lo que ha corrido

// El mismo criterio del rastro de §19: no hay diario que mirar, así que un nodo
// está encendido si lo que produce está escrito en el canon.
function vivosDe(p) {
  const intentos = p.capitulos.reduce((n, c) => n + c.intentos, 0);
  const conResumen = p.capitulos.some((c) => c.resumen);
  const juzgados = Boolean(p.auditoria?.revisados);
  return {
    brief: Boolean(p.brief),
    investigador: p.dossier.length > 0,
    dossier: p.dossier.length > 0,
    arquitecto: p.capitulos.length > 0,
    escaleta: p.capitulos.length > 0,
    personajes: p.reparto.length > 0,
    contexto: p.capitulos.some((c) => c.contexto_tokens != null),
    escritor: intentos > 0,
    borrador: intentos > 0,
    vd08: intentos > 0,
    'val-continuidad': juzgados,
    'val-anacronismos': juzgados,
    'val-logica': juzgados,
    gate: juzgados,
    cronista: conResumen,
    canon: conResumen,
    editor: Boolean(p.retoques),
    retoques: Boolean(p.retoques),
  };
}

// ---------------------------------------------- el recorrido de un capítulo

// Por dónde pasó un capítulo concreto. Lo que el canon no da no se cuenta: de
// los capítulos ya cerrados /api/proyecto expone el número de intentos, no el
// detalle de cada uno, así que las veces que corrió el validador solo se
// afirman cuando están delante.
function recorridoDe(p, numero) {
  const ficha = p.capitulos.find((c) => c.numero === numero);
  if (!ficha) return null;
  const detalle = p.en_curso?.numero === numero ? p.en_curso.intentos : null;
  const mapa = new Map();
  const veces = (n) => (n > 1 ? ' ×' + n : '');

  for (const id of ['brief', 'investigador', 'dossier', 'arquitecto', 'escaleta',
    'personajes', 'contexto']) mapa.set(id, '');

  mapa.set('escritor', veces(ficha.intentos));
  mapa.set('borrador', veces(ficha.intentos));
  mapa.set('vd08', veces(ficha.intentos));

  const juzgados = detalle ? detalle.filter((i) => i.notas).length : null;
  for (const id of ['val-continuidad', 'val-anacronismos', 'val-logica', 'gate']) {
    mapa.set(id, juzgados == null ? '' : veces(juzgados));
  }

  if (ficha.resumen) { mapa.set('cronista', ''); mapa.set('canon', ''); }

  // El editor global no es de ningún capítulo, y las dos vueltas atrás solo se
  // encienden cuando el canon dice cuál de las dos se usó: que hubo reintento se
  // sabe por el número de intentos, pero por dónde volvió no, y eso no se rellena.
  const fuera = new Set(['canon>editor', 'editor>retoques',
    'gate>escritor', 'vd08>escritor']);
  if (detalle) {
    if (detalle.some((i) => i.vd08 === 'bloqueo')) fuera.delete('vd08>escritor');
    if (detalle.some((i) => i.estado === 'descartado' && i.notas)) fuera.delete('gate>escritor');
  }
  if (numero === p.capitulos[0]?.numero) fuera.add('canon>contexto');
  if (!ficha.resumen) { fuera.add('gate>cronista'); fuera.add('cronista>canon'); }

  return { mapa, fuera, ficha, detalle };
}

function resumenDelRecorrido(recorrido) {
  const c = recorrido.ficha;
  const partes = ['capítulo ' + c.numero,
    c.intentos + (c.intentos === 1 ? ' intento' : ' intentos')];
  if (c.estado === 'aprobado') partes.push('aprobado en el ' + c.intentos);
  else partes.push(c.estado.replace('_', ' '));
  if (c.contexto_tokens != null) partes.push(c.contexto_tokens + ' tokens de paquete');
  if (c.recortes.length) partes.push('recortado: ' + c.recortes.join(', '));
  if (!recorrido.detalle && c.intentos > 1) {
    partes.push('hubo reintento, pero por cuál de las dos vueltas volvió solo se ve en'
      + ' el capítulo en curso: sin ese dato no se enciende ninguna');
  }
  return partes.join(' · ');
}

// ------------------------------------------------------------------ el panel

function lista(titulo, filas) {
  const seccion = document.createElement('section');
  const h4 = document.createElement('h4');
  h4.textContent = titulo;
  const ul = document.createElement('ul');
  for (const fila of filas) {
    const li = document.createElement('li');
    li.textContent = fila;
    ul.append(li);
  }
  seccion.append(h4, ul);
  return seccion;
}

export function crearArquitectura(ctx) {
  const nodos = disponer(NODOS.map((n) => ({ ...n, vivo: false })));
  const porId = new Map(nodos.map((n) => [n.id, n]));
  const caja = $('ficha-nodo');
  const selector = $('recorrido');
  const nota = $('grafo-nota');

  let grafo = null;
  let arrancando = null;
  let elegido = 'gate';
  let ultimo = null;

  // La dispersión de las tres notas es lo que §5 dice que hay que vigilar para
  // saber si juzgar en una sola pasada las estaba correlacionando. Se mide sobre
  // los intentos aprobados, que es lo que el canon expone capítulo a capítulo.
  function dimensionDe(p, indice) {
    const conNota = p.capitulos.filter((c) => c.notas);
    if (!conNota.length) return null;
    const notas = conNota.map((c) => c.notas[indice]);
    const media = notas.reduce((a, b) => a + b, 0) / notas.length;
    return [
      ['puntuaciones aprobadas', notas.length],
      ['media de la dimensión', media.toFixed(2)],
      ['rango', Math.min(...notas) + ' – ' + Math.max(...notas)],
    ];
  }

  function pintarFicha(id) {
    const nodo = porId.get(id);
    caja.textContent = '';
    if (!nodo) return;

    const alto = document.createElement('div');
    alto.className = 'ficha-nodo__alto';
    const h3 = document.createElement('h3');
    h3.textContent = nodo.nombre;
    const tipo = document.createElement('span');
    tipo.className = 'ficha-nodo__tipo';
    tipo.dataset.forma = nodo.forma;
    tipo.textContent = TIPO[nodo.forma];
    alto.append(h3, tipo);

    const desc = document.createElement('p');
    desc.className = 'ficha-nodo__desc';
    desc.textContent = nodo.descripcion;

    caja.append(alto, desc,
      lista('Entradas', nodo.entradas),
      lista('Salidas', nodo.salidas),
      lista('Reglas', nodo.reglas));

    // El único bloque que puede faltar: con el canon vacío no hay nada que
    // contar, y entonces no se pinta un hueco (§19).
    const filas = ultimo && nodo.canon ? nodo.canon(ultimo) : null;
    const notas = ultimo && nodo.dimension != null ? dimensionDe(ultimo, nodo.dimension) : null;
    if (!filas && !notas) return;

    const bloque = document.createElement('div');
    bloque.className = 'ficha-nodo__canon';
    const h4 = document.createElement('h4');
    h4.textContent = 'En este canon';
    const dl = document.createElement('dl');
    for (const [clave, valor] of (filas || []).concat(notas || [])) {
      const dt = document.createElement('dt');
      dt.textContent = clave;
      const dd = document.createElement('dd');
      dd.textContent = String(valor);
      dl.append(dt, dd);
    }
    bloque.append(h4, dl);
    caja.append(bloque);
  }

  function pintarSelector(p) {
    const antes = selector.value;
    selector.textContent = '';
    const todo = document.createElement('option');
    todo.value = '';
    todo.textContent = 'todo el libro';
    selector.append(todo);
    for (const c of p.capitulos) {
      const opcion = document.createElement('option');
      opcion.value = String(c.numero);
      opcion.textContent = 'capítulo ' + c.numero + ' — ' + c.titulo;
      selector.append(opcion);
    }
    selector.value = antes;
    selector.disabled = !p.capitulos.length;
  }

  function aplicarRecorrido() {
    if (!grafo || !ultimo) return;
    const numero = Number(selector.value);
    if (!numero) {
      grafo.marcarRecorrido(null, null);
      nota.textContent = ultimo.capitulos.length
        ? 'Todo el libro. Elige un capítulo para ver por dónde pasó.'
        : 'Sin escaleta todavía: el grafo enseña el sistema, no este libro.';
      return;
    }
    const recorrido = recorridoDe(ultimo, numero);
    if (!recorrido) return;
    grafo.marcarRecorrido(recorrido.mapa, recorrido.fuera);
    nota.textContent = resumenDelRecorrido(recorrido);
  }

  selector.addEventListener('change', () => {
    aplicarRecorrido();
    // El capítulo elegido aquí es el mismo que el de la mesa y el del rail: son
    // tres vistas del mismo foco y descuadrarlas confunde más de lo que ayuda.
    const numero = Number(selector.value);
    if (numero) ctx.elegirCapitulo(numero);
  });

  // El grafo no se monta hasta que se abre la pestaña: es una segunda escena
  // WebGL, y montarla de entrada se la cobraría a quien no va a verla.
  function arrancar() {
    if (arrancando) return arrancando;
    arrancando = crearGrafo($('lienzo-arquitectura'), {
      nodos,
      aristas: ARISTAS,
      onSenalar: () => {},   // el hover solo resalta; el panel lo fija el clic
      onElegir: (id) => { elegido = id; pintarFicha(id); },
    }).then((instancia) => {
      grafo = instancia;
      if (ultimo) grafo.refrescar(vivosDe(ultimo));
      grafo.elegir(elegido);
      aplicarRecorrido();
      return instancia;
    }).catch(() => {
      const aviso = $('grafo-aviso');
      aviso.hidden = false;
      aviso.textContent = 'La escena no ha cargado: three.js viaja por CDN y es lo único'
        + ' de este repositorio que necesita red. El panel de la derecha sigue contando'
        + ' el sistema entero.';
      return null;
    });
    return arrancando;
  }

  pintarFicha(elegido);

  return {
    pintar(proyecto) {
      ultimo = proyecto;
      pintarSelector(proyecto);
      grafo?.refrescar(vivosDe(proyecto));
      aplicarRecorrido();
      pintarFicha(elegido);
    },
    async mostrar(si) {
      if (si) await arrancar();
      grafo?.mostrar(si);
    },
  };
}
