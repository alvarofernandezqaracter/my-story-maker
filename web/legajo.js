// La escena del legajo (§19). Un cuadernillo por capitulo sobre la mesa:
// cuantos son lo dice el brief, el grosor las palabras por capitulo, el color
// el estado que tiene en el canon y la luz el tono.
//
// La escena solo pinta. No valida, no guarda y no habla con la API: recibe el
// estado ya resuelto desde app.js.
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

// Presupuesto de dibujo, no un umbral del sistema: un brief con doscientos
// capitulos sigue siendo valido, pero la mesa solo tiene sitio para estos.
const MAX_PIEZAS = 48;

// Los mismos colores que estilo.css, que son los de Qaracter.
const COLOR = {
  mesa: 0x101b23,
  niebla: 0x18262f,
  naranja: 0xff7932,
  pendiente: 0x3d5464,
  en_curso: 0xff7932,
  aprobado: 0x35c08a,
  bloqueado: 0xe8556d,
  canto: 0xeef4f8,
};

// El tono del brief enciende la luz de la mesa. Se busca por palabra suelta; lo
// que no reconoce cae en el ajuste neutro, que es el de "seco".
const TONOS = [
  { claves: ['seco', 'sobrio', 'austero', 'contenido'],
    luz: 0xdfe6ea, intensidad: 2.9, niebla: 0.05, rugosidad: 0.85 },
  { claves: ['lirico', 'lírico', 'poetico', 'poético', 'luminoso'],
    luz: 0xffe9c8, intensidad: 3.3, niebla: 0.032, rugosidad: 0.55 },
  { claves: ['sombrio', 'sombrío', 'oscuro', 'tragico', 'trágico', 'negro'],
    luz: 0x9fb4bd, intensidad: 2.1, niebla: 0.09, rugosidad: 0.95 },
  { claves: ['epico', 'épico', 'aventura', 'heroico'],
    luz: 0xffd9a0, intensidad: 3.9, niebla: 0.042, rugosidad: 0.7 },
  { claves: ['ironico', 'irónico', 'satirico', 'satírico', 'humor'],
    luz: 0xe8e2ff, intensidad: 3.1, niebla: 0.048, rugosidad: 0.4 },
];

const NEUTRO = TONOS[0];

function tonoDe(texto) {
  const limpio = String(texto || '').toLowerCase();
  return TONOS.find((t) => t.claves.some((c) => limpio.includes(c))) || NEUTRO;
}

// Ruido estable por indice: los cuadernillos se desalinean un poco, pero el
// mismo capitulo se desalinea siempre igual. Nada de Math.random por fotograma.
function vibracion(i) {
  const s = Math.sin(i * 12.9898) * 43758.5453;
  return s - Math.floor(s);
}

export async function crearLegajo(canvas, { onFoco } = {}) {
  const quieto = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;

  const escena = new THREE.Scene();
  escena.fog = new THREE.FogExp2(COLOR.niebla, NEUTRO.niebla);

  const camara = new THREE.PerspectiveCamera(38, 1, 0.1, 140);
  camara.position.set(1.3, 2.9, 8.2);

  const mandos = new OrbitControls(camara, canvas);
  mandos.target.set(0, 0.35, 0);
  mandos.enableDamping = true;
  mandos.enablePan = false;
  mandos.minDistance = 3.2;
  mandos.maxDistance = 24;
  mandos.maxPolarAngle = 1.48;
  mandos.update();

  // En cuanto el usuario toca la escena, la camara deja de moverse sola: la
  // mesa es suya y no se le quita el encuadre de las manos.
  let camaraAutomatica = true;
  mandos.addEventListener('start', () => { camaraAutomatica = false; });

  escena.add(new THREE.HemisphereLight(0x2b3d47, 0x05090b, 0.7));

  const clave = new THREE.DirectionalLight(NEUTRO.luz, NEUTRO.intensidad);
  clave.position.set(4.5, 7.5, 5);
  clave.castShadow = true;
  clave.shadow.mapSize.set(1024, 1024);
  clave.shadow.camera.left = -14;
  clave.shadow.camera.right = 14;
  clave.shadow.camera.top = 14;
  clave.shadow.camera.bottom = -14;
  clave.shadow.bias = -0.0015;
  escena.add(clave);

  // La luz rasante hace de candil: es la unica de la mesa que no esta quieta.
  // El parpadeo es minimo a proposito -no es una hoguera- y se apaga entero si
  // el sistema pide menos movimiento.
  const rasante = new THREE.PointLight(COLOR.naranja, 22, 28, 2);
  rasante.position.set(-5, 1.1, 3.5);
  escena.add(rasante);
  const INTENSIDAD_CANDIL = rasante.intensity;

  const relleno = new THREE.DirectionalLight(0xbfd3d8, 0.9);
  relleno.position.set(-3, 2.5, 6);
  escena.add(relleno);

  const mesa = new THREE.Mesh(
    new THREE.PlaneGeometry(400, 400),
    new THREE.MeshStandardMaterial({ color: COLOR.mesa, roughness: 0.97, metalness: 0 }),
  );
  mesa.rotation.x = -Math.PI / 2;
  mesa.position.y = -0.02;
  mesa.receiveShadow = true;
  escena.add(mesa);

  const legajo = new THREE.Group();
  escena.add(legajo);

  // Motas de polvo en el haz de luz. Puro ambiente, y lo primero que se apaga
  // si el sistema pide menos movimiento.
  const motas = (() => {
    const total = 260;
    const posiciones = new Float32Array(total * 3);
    for (let i = 0; i < total; i += 1) {
      posiciones[i * 3] = (Math.random() - 0.5) * 20;
      posiciones[i * 3 + 1] = Math.random() * 7;
      posiciones[i * 3 + 2] = (Math.random() - 0.5) * 14;
    }
    const geometria = new THREE.BufferGeometry();
    geometria.setAttribute('position', new THREE.BufferAttribute(posiciones, 3));
    const puntos = new THREE.Points(geometria, new THREE.PointsMaterial({
      color: COLOR.canto, size: 0.035, transparent: true, opacity: 0.32,
      sizeAttenuation: true, depthWrite: false,
    }));
    escena.add(puntos);
    return puntos;
  })();

  const cajaUnidad = new THREE.BoxGeometry(1, 1, 1);
  const cantosUnidad = new THREE.EdgesGeometry(cajaUnidad);
  const piezas = [];

  let capituloEnFoco = null;     // el que senala el raton
  let capituloElegido = null;    // el que se esta leyendo o mirando
  let leyendo = false;
  let progresoLectura = 0;
  let tono = NEUTRO;

  function nuevaPieza() {
    const grupo = new THREE.Group();
    const cuerpo = new THREE.Mesh(cajaUnidad, new THREE.MeshStandardMaterial({
      color: COLOR.pendiente, roughness: NEUTRO.rugosidad, metalness: 0.05,
    }));
    cuerpo.castShadow = true;
    cuerpo.receiveShadow = true;

    const canto = new THREE.LineSegments(cantosUnidad, new THREE.LineBasicMaterial({
      color: COLOR.canto, transparent: true, opacity: 0.3,
    }));

    // El relleno sube desde abajo segun se lee el capitulo. Sin lectura en
    // curso mide cero y no se ve.
    const barra = new THREE.Mesh(cajaUnidad, new THREE.MeshBasicMaterial({
      color: COLOR.naranja, transparent: true, opacity: 0.85,
    }));
    barra.scale.set(1.04, 0.0001, 1.04);
    barra.visible = false;

    grupo.add(cuerpo, canto, barra);
    Object.assign(grupo.userData, { cuerpo, canto, barra });
    grupo.scale.set(0.001, 0.001, 0.001);
    legajo.add(grupo);
    piezas.push(grupo);
    return grupo;
  }

  function colocar(pieza, i, total, grosor) {
    const paso = Math.min(0.135, 2.4 / Math.max(total, 1));
    const angulo = (i - (total - 1) / 2) * paso;
    const radio = 4.2;
    const alto = 2.0 + vibracion(i) * 0.3;
    pieza.userData.destino = {
      x: Math.sin(angulo) * radio,
      y: alto / 2,
      z: radio - Math.cos(angulo) * radio,
      giro: angulo,
      alto,
      escala: new THREE.Vector3(grosor, alto, 1.05 + vibracion(i + 7) * 0.1),
    };
  }

  function actualizar({ brief, capitulos }) {
    const pedidos = Math.max(0, Math.min(Number(brief?.capitulos) || 0, MAX_PIEZAS));
    const palabras = Number(brief?.palabras_por_capitulo) || 0;
    // El grosor es lectura, no medida: comprime mucho para que 500 y 5000
    // palabras se distingan sin que un capitulo largo tape a su vecino.
    const grosor = Math.max(0.09, Math.min(0.62, 0.09 + Math.sqrt(palabras) / 130));
    const fichas = Array.isArray(capitulos) ? capitulos : [];
    tono = tonoDe(brief?.tono);

    while (piezas.length < pedidos) nuevaPieza();
    while (piezas.length > pedidos) {
      const sobra = piezas.pop();
      sobra.userData.cuerpo.material.dispose();
      sobra.userData.canto.material.dispose();
      sobra.userData.barra.material.dispose();
      legajo.remove(sobra);
    }

    piezas.forEach((pieza, i) => {
      colocar(pieza, i, pedidos, grosor);
      const ficha = fichas.find((f) => f.numero === i + 1);
      pieza.userData.ficha = ficha || { numero: i + 1, estado: null, titulo: null };
      const material = pieza.userData.cuerpo.material;
      material.color.setHex(COLOR[ficha?.estado] ?? COLOR.pendiente);
      material.roughness = tono.rugosidad;
    });

    clave.color.setHex(tono.luz);
    clave.intensity = tono.intensidad;
    escena.fog.density = tono.niebla;

    if (camaraAutomatica && !leyendo) {
      const deseada = 7.8 + pedidos * 0.09;
      if (Math.abs(camara.position.length() - deseada) > 1.2) {
        camara.position.setLength(deseada);
      }
    }
  }

  function elegir(numero) {
    capituloElegido = numero;
  }

  function modoLectura(activo, progreso = 0) {
    leyendo = activo;
    progresoLectura = Math.max(0, Math.min(1, progreso));
  }

  // ------------------------------------------------------------------ foco
  const rayo = new THREE.Raycaster();
  const puntero = new THREE.Vector2();
  let hayPuntero = false;

  canvas.addEventListener('pointermove', (e) => {
    const caja = canvas.getBoundingClientRect();
    puntero.x = ((e.clientX - caja.left) / caja.width) * 2 - 1;
    puntero.y = -((e.clientY - caja.top) / caja.height) * 2 + 1;
    hayPuntero = true;
  });
  canvas.addEventListener('pointerleave', () => { hayPuntero = false; });

  function piezaBajoElPuntero() {
    if (!hayPuntero || !piezas.length) return null;
    rayo.setFromCamera(puntero, camara);
    const tocados = rayo.intersectObjects(piezas.map((p) => p.userData.cuerpo), false);
    return tocados.length ? tocados[0].object.parent : null;
  }

  canvas.addEventListener('click', () => {
    const pieza = piezaBajoElPuntero();
    if (pieza && onFoco) onFoco(pieza.userData.ficha, true);
  });

  function revisarFoco() {
    const encontrada = piezaBajoElPuntero();
    const ficha = encontrada ? encontrada.userData.ficha : null;
    const numero = ficha ? ficha.numero : null;
    if (numero !== capituloEnFoco) {
      capituloEnFoco = numero;
      canvas.style.cursor = numero ? 'pointer' : 'grab';
      if (onFoco) onFoco(ficha, false);
    }
    return encontrada;
  }

  // --------------------------------------------------------------- tamano
  function medir() {
    const ancho = canvas.clientWidth || window.innerWidth;
    const alto = canvas.clientHeight || window.innerHeight;
    renderer.setSize(ancho, alto, false);
    camara.aspect = ancho / Math.max(alto, 1);
    camara.updateProjectionMatrix();
  }
  medir();
  window.addEventListener('resize', medir);

  // --------------------------------------------------------------- dibujo
  const reloj = new THREE.Clock();
  const puntoAuxiliar = new THREE.Vector3();
  let vivo = true;

  function fotograma() {
    if (!vivo) return;
    requestAnimationFrame(fotograma);
    const t = reloj.getElapsedTime();
    const senalada = revisarFoco();

    piezas.forEach((pieza, i) => {
      const destino = pieza.userData.destino;
      if (!destino) return;
      const numero = i + 1;
      const elegida = numero === capituloElegido;
      const trabajando = pieza.userData.ficha?.estado === 'en_curso';

      // El capitulo en curso se levanta y respira; el elegido se adelanta.
      const vaiven = quieto ? 0 : Math.sin(t * 0.7 + destino.x) * 0.035;
      const subida = trabajando && !quieto ? 0.16 + Math.sin(t * 2.4) * 0.07 : 0;
      const adelanto = elegida ? 0.55 : 0;

      puntoAuxiliar.set(
        destino.x,
        destino.y + vaiven + subida,
        destino.z + adelanto,
      );
      pieza.position.lerp(puntoAuxiliar, 0.08);
      pieza.rotation.y += (destino.giro - pieza.rotation.y) * 0.08;
      pieza.scale.lerp(destino.escala, 0.12);

      pieza.userData.canto.material.opacity =
        pieza === senalada ? 0.9 : (elegida ? 0.65 : 0.3);

      const barra = pieza.userData.barra;
      const relleno = elegida && leyendo ? progresoLectura : 0;
      barra.visible = relleno > 0.001;
      if (barra.visible) {
        barra.scale.set(1.05, Math.max(relleno, 0.001), 1.05);
        barra.position.y = -0.5 + relleno / 2;
      }
    });

    if (!quieto) {
      motas.position.y = (Math.sin(t * 0.12) * 0.3) - 0.3;
      motas.rotation.y = t * 0.012;
      // Dos senos que no casan: la llama no repite el mismo ciclo.
      rasante.intensity = INTENSIDAD_CANDIL
        * (1 + Math.sin(t * 2.1) * 0.05 + Math.sin(t * 5.7) * 0.025);
    }

    // La camara solo se mueve sola mientras nadie la haya tocado.
    if (camaraAutomatica) {
      const elegida = piezas[capituloElegido - 1];
      const objetivo = elegida && elegida.userData.destino
        ? puntoAuxiliar.set(
          elegida.userData.destino.x,
          elegida.userData.destino.alto / 2 - 0.6,
          elegida.userData.destino.z)
        : puntoAuxiliar.set(0, 0.35, 0);
      mandos.target.lerp(objetivo, 0.05);
      const distancia = leyendo ? 9.5 : 7.8 + piezas.length * 0.09;
      const actual = camara.position.distanceTo(mandos.target);
      if (Math.abs(actual - distancia) > 0.05) {
        camara.position.lerp(
          camara.position.clone().sub(mandos.target).setLength(
            actual + (distancia - actual) * 0.04).add(mandos.target), 1);
      }
    }

    mandos.update();
    renderer.render(escena, camara);
  }
  fotograma();

  return {
    actualizar,
    elegir,
    modoLectura,
    destruir() {
      vivo = false;
      window.removeEventListener('resize', medir);
      mandos.dispose();
      renderer.dispose();
    },
  };
}
