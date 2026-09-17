// El grafo de la arquitectura (§19). Un DAG por capas dibujado con three.js:
// esfera para el agente LLM, cilindro para el artefacto o estado y rombo para
// la decision. Nada mas; tres formas se aprenden de una vez y una cuarta ya hay
// que ir a buscarla a la leyenda.
//
// Esta escena solo pinta. No sabe que es un capitulo ni que es el gate: recibe
// los nodos ya colocados y las aristas ya resueltas desde arquitectura.js, y
// devuelve por callback el nodo que el raton toca. Es la misma division que
// legajo.js: el dibujo aqui, las reglas fuera.
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

// Los mismos colores de estilo.css. El naranja de Qaracter no se reparte: es
// del nodo activo y de sus aristas, y por eso se ve desde lejos cual es.
const COLOR = {
  apagado: 0x2d4152,
  agente: 0x8ea5b4,
  artefacto: 0x60788c,
  decision: 0xc9a45c,
  activo: 0xff7932,
  arista: 0x33495b,
  aristaActiva: 0xff7932,
  etiqueta: '#8ea5b4',
  etiquetaViva: '#eef4f8',
};

const RADIO = 0.46;

// Lo que baja el resto cuando hay un nodo activo. El enunciado es el del
// diseno: lo tocado al 100 %, lo demas al 25 %.
const TENUE = 0.25;

// Holgura alrededor del grafo al encuadrar, en unidades de mundo.
const MARGEN = 1.1;

// Alto de la caja de una etiqueta, en unidades de mundo. Todas miden igual, asi
// que el texto no cambia de cuerpo de un nodo a otro.
const ALTO_ETIQUETA = 0.52;
const CUERPO = 48;

function geometriaDe(forma) {
  if (forma === 'agente') return new THREE.SphereGeometry(RADIO, 32, 20);
  if (forma === 'decision') return new THREE.OctahedronGeometry(RADIO * 1.2);
  return new THREE.CylinderGeometry(RADIO * 0.82, RADIO * 0.82, RADIO * 1.2, 32);
}

function colorDe(nodo) {
  if (!nodo.vivo) return COLOR.apagado;
  if (nodo.forma === 'agente') return COLOR.agente;
  if (nodo.forma === 'decision') return COLOR.decision;
  return COLOR.artefacto;
}

// Una etiqueta es un lienzo 2D convertido en textura: no hace falta cargar
// ninguna fuente 3D y el texto sale con la misma mono que el resto de la
// interfaz.
function texturaTexto(texto, tono) {
  const fuente = '500 ' + CUERPO + 'px "IBM Plex Mono", "Cascadia Mono", Consolas, monospace';
  const medidor = document.createElement('canvas').getContext('2d');
  medidor.font = fuente;
  const ancho = Math.ceil(medidor.measureText(texto).width) + 20;
  const alto = Math.ceil(CUERPO * 1.45);
  const lienzo = document.createElement('canvas');
  lienzo.width = ancho;
  lienzo.height = alto;
  const c = lienzo.getContext('2d');
  c.font = fuente;
  c.fillStyle = tono;
  c.textAlign = 'center';
  c.textBaseline = 'middle';
  c.fillText(texto, ancho / 2, alto / 2 + 1);
  const textura = new THREE.CanvasTexture(lienzo);
  textura.minFilter = THREE.LinearFilter;
  textura.magFilter = THREE.LinearFilter;
  textura.colorSpace = THREE.SRGBColorSpace;
  textura.userData = { proporcion: ancho / alto };
  return textura;
}

// El carril por el que baja -o sube- una arista que no va a la banda de al
// lado. Va por la izquierda, donde no hay etiquetas, y cada una lleva el suyo
// para que dos vueltas atras no se dibujen encima.
function carrilDe(arista) {
  return -(3.2 + (arista.carril || 0) * 1.4);
}

function puntosArista(a, b, arista) {
  const desde = new THREE.Vector3(a.x, a.y, 0);
  const hasta = new THREE.Vector3(b.x, b.y, 0);
  if (arista.tipo !== 'realimenta') {
    const dir = hasta.clone().sub(desde).normalize();
    return [desde.clone().addScaledVector(dir, RADIO + 0.04),
            hasta.clone().addScaledVector(dir, -(RADIO + 0.24))];
  }
  const x = carrilDe(arista);
  return new THREE.CubicBezierCurve3(
    desde.clone().add(new THREE.Vector3(-RADIO - 0.04, 0, 0)),
    new THREE.Vector3(x, a.y, 0),
    new THREE.Vector3(x, b.y, 0),
    hasta.clone().add(new THREE.Vector3(-RADIO - 0.24, 0, 0)),
  ).getPoints(56);
}

export async function crearGrafo(lienzo, { nodos, aristas, onSenalar, onElegir } = {}) {
  // Las etiquetas se dibujan con la mono de la pagina: si se montan antes de
  // que la fuente llegue salen en la de reserva y ya no se rehacen solas.
  if (document.fonts && document.fonts.ready) {
    try { await document.fonts.ready; } catch { /* la de reserva vale */ }
  }

  const render = new THREE.WebGLRenderer({ canvas: lienzo, antialias: true, alpha: true });
  render.setPixelRatio(Math.min(window.devicePixelRatio, 2));

  const escena = new THREE.Scene();
  const camara = new THREE.OrthographicCamera(-1, 1, 1, -1, 0.1, 100);

  escena.add(new THREE.HemisphereLight(0xcfe0ea, 0x0d161d, 1.6));
  const foco = new THREE.DirectionalLight(0xfff0dc, 2.1);
  foco.position.set(-6, 8, 12);
  escena.add(foco);

  const porId = new Map(nodos.map((n) => [n.id, n]));
  const piezas = new Map();
  const trazos = [];

  // ------------------------------------------------------------- los nodos

  for (const nodo of nodos) {
    const grupo = new THREE.Group();
    grupo.position.set(nodo.x, nodo.y, 0);

    const material = new THREE.MeshStandardMaterial({
      color: colorDe(nodo),
      roughness: 0.55,
      metalness: 0.1,
      transparent: true,
    });
    const cuerpo = new THREE.Mesh(geometriaDe(nodo.forma), material);
    if (nodo.forma === 'decision') cuerpo.rotation.y = Math.PI / 4;
    grupo.add(cuerpo);

    // Blanco de raton mas ancho que la pieza: apuntar a una esfera de catorce
    // pixeles con el grafo encuadrado entero es un ejercicio de punteria.
    const blanco = new THREE.Mesh(
      new THREE.SphereGeometry(RADIO * 1.9, 8, 6),
      new THREE.MeshBasicMaterial({ visible: false }),
    );
    blanco.userData.id = nodo.id;
    grupo.add(blanco);

    // Con un solo nodo en la banda la etiqueta cabe al lado; con varios se va
    // debajo, que es la unica forma de que tres nombres no se pisen.
    const debajo = Boolean(nodo.compartida);
    const etiqueta = new THREE.Sprite(new THREE.SpriteMaterial({ transparent: true }));
    etiqueta.raycast = () => {};
    etiqueta.position.set(debajo ? 0 : RADIO + 0.24, debajo ? -(RADIO + 0.36) : 0, 0.2);
    etiqueta.center.set(debajo ? 0.5 : 0, 0.5);
    grupo.add(etiqueta);

    escena.add(grupo);
    piezas.set(nodo.id, { nodo, grupo, cuerpo, material, etiqueta, debajo });
  }

  function ponerEtiqueta(id, texto, tono) {
    const pieza = piezas.get(id);
    const vieja = pieza.etiqueta.material.map;
    const textura = texturaTexto(texto, tono);
    pieza.etiqueta.material.map = textura;
    pieza.etiqueta.material.needsUpdate = true;
    pieza.etiqueta.scale.set(ALTO_ETIQUETA * textura.userData.proporcion, ALTO_ETIQUETA, 1);
    if (vieja) vieja.dispose();
  }

  for (const nodo of nodos) {
    ponerEtiqueta(nodo.id, nodo.nombre, nodo.vivo ? COLOR.etiquetaViva : COLOR.etiqueta);
  }

  // ----------------------------------------------------------- las aristas

  for (const arista of aristas) {
    const a = porId.get(arista.de);
    const b = porId.get(arista.a);
    if (!a || !b) continue;
    const puntos = puntosArista(a, b, arista);
    const vuelta = arista.tipo === 'realimenta';

    // La vuelta atras va discontinua: es la misma flecha pero no es el mismo
    // viaje, y verlas iguales haria parecer el loop una etapa mas.
    const material = vuelta
      ? new THREE.LineDashedMaterial({
        color: COLOR.arista, transparent: true, dashSize: 0.18, gapSize: 0.14 })
      : new THREE.LineBasicMaterial({ color: COLOR.arista, transparent: true });
    const linea = new THREE.Line(new THREE.BufferGeometry().setFromPoints(puntos), material);
    if (vuelta) linea.computeLineDistances();
    linea.raycast = () => {};
    escena.add(linea);

    // Punta pequena: una flecha grande en un grafo de dieciocho nodos lo
    // convierte en una coleccion de triangulos.
    const puntaMat = new THREE.MeshBasicMaterial({ color: COLOR.arista, transparent: true });
    const punta = new THREE.Mesh(new THREE.ConeGeometry(0.082, 0.21, 12), puntaMat);
    punta.raycast = () => {};
    const fin = puntos[puntos.length - 1];
    const antes = puntos[puntos.length - 2];
    punta.position.copy(fin);
    punta.quaternion.setFromUnitVectors(
      new THREE.Vector3(0, 1, 0), fin.clone().sub(antes).normalize());
    escena.add(punta);

    trazos.push({ arista, clave: arista.de + '>' + arista.a, linea, material, punta, puntaMat });
  }

  // -------------------------------------------------------------- encuadre

  // Los limites salen de lo que hay dibujado, etiquetas y carriles incluidos:
  // encuadrar solo con los centros deja media palabra fuera de la pantalla.
  const limites = new THREE.Box3();
  for (const [, pieza] of piezas) {
    const { nodo, etiqueta, debajo } = pieza;
    const ancho = etiqueta.scale.x;
    limites.expandByPoint(new THREE.Vector3(nodo.x - RADIO - (debajo ? ancho / 2 : 0),
      nodo.y - RADIO - (debajo ? ALTO_ETIQUETA : 0), 0));
    limites.expandByPoint(new THREE.Vector3(nodo.x + (debajo ? ancho / 2 : RADIO + 0.24 + ancho),
      nodo.y + RADIO, 0));
  }
  for (const { arista } of trazos) {
    if (arista.tipo === 'realimenta') {
      limites.expandByPoint(new THREE.Vector3(carrilDe(arista) - 0.2, 0, 0));
    }
  }
  const centro = limites.getCenter(new THREE.Vector3());
  const tamano = limites.getSize(new THREE.Vector3());

  camara.position.set(centro.x, centro.y, 20);

  const mandos = new OrbitControls(camara, lienzo);
  mandos.target.set(centro.x, centro.y, 0);
  mandos.enableDamping = false;
  mandos.screenSpacePanning = true;
  // Se puede girar un poco, para que las tres formas se lean como volumenes y
  // no como siluetas, pero no dar la vuelta: un DAG por capas boca abajo no
  // dice nada.
  mandos.minPolarAngle = Math.PI / 2 - 0.3;
  mandos.maxPolarAngle = Math.PI / 2 + 0.3;
  mandos.minAzimuthAngle = -0.3;
  mandos.maxAzimuthAngle = 0.3;
  mandos.update();

  function encuadrar() {
    const ancho = lienzo.clientWidth || 1;
    const alto = lienzo.clientHeight || 1;
    render.setSize(ancho, alto, false);
    const proporcion = ancho / alto;
    const mitad = Math.max((tamano.y + MARGEN) / 2, (tamano.x + MARGEN) / 2 / proporcion);
    camara.left = -mitad * proporcion;
    camara.right = mitad * proporcion;
    camara.top = mitad;
    camara.bottom = -mitad;
    camara.updateProjectionMatrix();
  }

  // ------------------------------------------------------------- el enfasis

  let senalado = null;
  let elegido = null;
  let recorrido = null;        // Map id -> sufijo de etiqueta, o null si no hay
  let fueraAristas = null;     // Set de claves "de>a" que el recorrido no uso
  let pendiente = true;

  const activo = () => senalado || elegido;
  const relacionada = (arista, id) => arista.de === id || arista.a === id;

  function aplicar() {
    const id = activo();
    const vecinos = id
      ? new Set(aristas.filter((a) => relacionada(a, id)).flatMap((a) => [a.de, a.a]))
      : null;

    for (const [clave, pieza] of piezas) {
      const enRecorrido = !recorrido || recorrido.has(clave);
      const tocado = !id || vecinos.has(clave);
      const opacidad = !enRecorrido ? TENUE * 0.6 : (tocado ? 1 : TENUE);
      pieza.material.opacity = opacidad;
      pieza.material.color.setHex(clave === id ? COLOR.activo : colorDe(pieza.nodo));
      pieza.material.emissive.setHex(clave === id ? 0x351803 : 0x000000);
      pieza.etiqueta.material.opacity = opacidad;
    }

    for (const trazo of trazos) {
      const { arista, clave, material, puntaMat } = trazo;
      const enRecorrido = !recorrido
        || (recorrido.has(arista.de) && recorrido.has(arista.a) && !fueraAristas?.has(clave));
      const tocada = Boolean(id) && relacionada(arista, id);
      const opacidad = !enRecorrido ? TENUE * 0.6 : (!id || tocada ? 1 : TENUE);
      const color = tocada ? COLOR.aristaActiva : COLOR.arista;
      material.color.setHex(color);
      puntaMat.color.setHex(color);
      material.opacity = opacidad;
      puntaMat.opacity = opacidad;
    }
    pendiente = true;
  }

  // ------------------------------------------------------------ el puntero

  const rayo = new THREE.Raycaster();
  const raton = new THREE.Vector2();
  let arrastrando = false;

  function nodoBajo(evento) {
    const caja = lienzo.getBoundingClientRect();
    raton.x = ((evento.clientX - caja.left) / caja.width) * 2 - 1;
    raton.y = -((evento.clientY - caja.top) / caja.height) * 2 + 1;
    rayo.setFromCamera(raton, camara);
    const tocado = rayo.intersectObjects(escena.children, true)
      .find((t) => t.object.userData.id);
    return tocado ? tocado.object.userData.id : null;
  }

  lienzo.addEventListener('pointermove', (evento) => {
    if (arrastrando) return;
    const id = nodoBajo(evento);
    if (id === senalado) return;
    senalado = id;
    lienzo.style.cursor = id ? 'pointer' : 'grab';
    aplicar();
    onSenalar?.(id);
  });

  lienzo.addEventListener('pointerleave', () => {
    if (!senalado) return;
    senalado = null;
    aplicar();
    onSenalar?.(null);
  });

  lienzo.addEventListener('pointerdown', () => { arrastrando = false; });
  mandos.addEventListener('change', () => { arrastrando = true; pendiente = true; });

  lienzo.addEventListener('click', (evento) => {
    if (arrastrando) { arrastrando = false; return; }
    const id = nodoBajo(evento);
    if (!id) return;
    elegido = id;
    aplicar();
    onElegir?.(id);
  });

  // ---------------------------------------------------------- el fotograma

  // Uno solo, y se pinta cuando hay algo que pintar: la escena es estatica, asi
  // que un bucle que dibuje sesenta veces por segundo lo mismo solo calienta el
  // portatil. Con la pestana fuera de pantalla no se dibuja nada.
  let visible = false;
  let vivo = true;

  function fotograma() {
    if (!vivo) return;
    requestAnimationFrame(fotograma);
    if (!visible || document.hidden || !pendiente) return;
    pendiente = false;
    render.render(escena, camara);
  }
  requestAnimationFrame(fotograma);

  const observador = new ResizeObserver(() => { encuadrar(); pendiente = true; });
  observador.observe(lienzo);
  document.addEventListener('visibilitychange', () => { pendiente = true; });

  encuadrar();
  aplicar();

  function reetiquetar() {
    for (const [id, pieza] of piezas) {
      ponerEtiqueta(id, pieza.nodo.nombre + (recorrido?.get(id) || ''),
        pieza.nodo.vivo ? COLOR.etiquetaViva : COLOR.etiqueta);
    }
  }

  return {
    // Un nodo se enciende cuando el canon dice que ya ha corrido: es el criterio
    // del rastro de §19 -no hay diario, hay lo que quedo escrito- aplicado al
    // dibujo en vez de a una tarjeta.
    refrescar(vivos) {
      for (const [id, pieza] of piezas) pieza.nodo.vivo = Boolean(vivos[id]);
      reetiquetar();
      aplicar();
    },
    // El recorrido de un capitulo: por donde paso y cuantas veces. Lo que no
    // recorrio se apaga, no se esconde, para que se vea lo que no se uso.
    marcarRecorrido(mapa, aristasFuera) {
      recorrido = mapa;
      fueraAristas = aristasFuera || null;
      reetiquetar();
      aplicar();
    },
    elegir(id) {
      elegido = id;
      aplicar();
    },
    mostrar(si) {
      visible = si;
      if (si) { encuadrar(); pendiente = true; }
    },
    destruir() {
      vivo = false;
      observador.disconnect();
      mandos.dispose();
      render.dispose();
    },
  };
}
