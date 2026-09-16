// Escena del legajo (§19). Un cuadernillo por capitulo sobre la mesa del
// archivo: cuantos son lo dice el brief, como de gordos lo dicen las palabras
// por capitulo, y de que color lo dice el estado que ya hay en el canon.
//
// La escena solo pinta. No valida, no guarda y no sabe hablar con la API: todo
// eso vive en papeleta.js, que le pasa el estado ya resuelto.
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

// Presupuesto de dibujo, no un umbral del sistema: un brief con doscientos
// capitulos sigue siendo valido, pero la mesa solo tiene sitio para estos.
const MAX_PIEZAS = 48;

const COLOR = {
  mesa: 0x0c1316,
  niebla: 0x16222a,
  pendiente: 0x5a6c74,
  en_curso: 0x8fa0a6,
  aprobado: 0x4fb3a3,
  bloqueado: 0xd9553b,
  canto: 0xe9e5db,
};

// El tono del brief enciende la luz de la mesa. Se busca por palabra suelta;
// lo que no reconoce cae en el ajuste neutro, que es el de "seco".
const TONOS = [
  { claves: ['seco', 'sobrio', 'austero', 'contenido'],
    luz: 0xd9d4c6, intensidad: 2.9, niebla: 0.055, rugosidad: 0.85, rasante: 0x4fb3a3 },
  { claves: ['lirico', 'lírico', 'poetico', 'poético', 'luminoso'],
    luz: 0xffe9c8, intensidad: 3.3, niebla: 0.035, rugosidad: 0.55, rasante: 0x6fd2c2 },
  { claves: ['sombrio', 'sombrío', 'oscuro', 'tragico', 'trágico', 'negro'],
    luz: 0x9fb4bd, intensidad: 2.1, niebla: 0.095, rugosidad: 0.95, rasante: 0x2f7d72 },
  { claves: ['epico', 'épico', 'aventura', 'heroico'],
    luz: 0xffd9a0, intensidad: 3.9, niebla: 0.045, rugosidad: 0.7, rasante: 0xd9553b },
  { claves: ['ironico', 'irónico', 'satirico', 'satírico', 'humor'],
    luz: 0xe8e2ff, intensidad: 3.1, niebla: 0.05, rugosidad: 0.4, rasante: 0x9f8fd6 },
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

  const camara = new THREE.PerspectiveCamera(38, 1, 0.1, 120);
  camara.position.set(1.3, 2.2, 6.6);

  const mandos = new OrbitControls(camara, canvas);
  mandos.target.set(0, 0.55, 0);
  mandos.enableDamping = true;
  mandos.enablePan = false;
  mandos.minDistance = 3.5;
  mandos.maxDistance = 22;
  mandos.maxPolarAngle = 1.48;
  mandos.update();

  escena.add(new THREE.HemisphereLight(0x2b3d47, 0x05090b, 0.7));

  const clave = new THREE.DirectionalLight(NEUTRO.luz, NEUTRO.intensidad);
  clave.position.set(4.5, 7.5, 5);
  clave.castShadow = true;
  clave.shadow.mapSize.set(1024, 1024);
  clave.shadow.camera.left = -12;
  clave.shadow.camera.right = 12;
  clave.shadow.camera.top = 12;
  clave.shadow.camera.bottom = -12;
  clave.shadow.bias = -0.0015;
  escena.add(clave);

  const rasante = new THREE.PointLight(NEUTRO.rasante, 22, 26, 2);
  rasante.position.set(-5, 1.1, 3.5);
  escena.add(rasante);

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
  let capituloEnFoco = null;

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
    grupo.add(cuerpo, canto);
    grupo.userData.cuerpo = cuerpo;
    grupo.userData.canto = canto;
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
      escala: new THREE.Vector3(grosor, alto, 1.05 + vibracion(i + 7) * 0.1),
    };
  }

  const estadoActual = { capitulos: 0, grosor: 0.2, tono: NEUTRO, fichas: [] };

  function actualizar({ brief, capitulos }) {
    const pedidos = Math.max(0, Math.min(Number(brief?.capitulos) || 0, MAX_PIEZAS));
    const palabras = Number(brief?.palabras_por_capitulo) || 0;
    // El grosor es lectura, no medida: comprime mucho para que 500 y 5000
    // palabras se distingan sin que un capitulo largo tape a su vecino.
    const grosor = Math.max(0.09, Math.min(0.62, 0.09 + Math.sqrt(palabras) / 130));
    const fichas = Array.isArray(capitulos) ? capitulos : [];
    const tono = tonoDe(brief?.tono);

    while (piezas.length < pedidos) nuevaPieza();
    while (piezas.length > pedidos) {
      const sobra = piezas.pop();
      sobra.userData.cuerpo.material.dispose();
      sobra.userData.canto.material.dispose();
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
    rasante.color.setHex(tono.rasante);
    escena.fog.density = tono.niebla;

    // La camara se echa atras conforme el arco se ensancha, para que el legajo
    // entero siga cabiendo sin tocar los mandos.
    mandos.minDistance = 3.5;
    const deseada = 6.4 + pedidos * 0.075;
    if (Math.abs(camara.position.length() - deseada) > 1.2) {
      camara.position.setLength(deseada);
    }

    Object.assign(estadoActual, { capitulos: pedidos, grosor, tono, fichas });
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

  function revisarFoco() {
    let encontrada = null;
    if (hayPuntero && piezas.length) {
      rayo.setFromCamera(puntero, camara);
      const tocados = rayo.intersectObjects(piezas.map((p) => p.userData.cuerpo), false);
      if (tocados.length) encontrada = tocados[0].object.parent;
    }
    piezas.forEach((p) => {
      p.userData.canto.material.opacity = p === encontrada ? 0.9 : 0.3;
    });
    const ficha = encontrada ? encontrada.userData.ficha : null;
    const numero = ficha ? ficha.numero : null;
    if (numero !== capituloEnFoco) {
      capituloEnFoco = numero;
      canvas.style.cursor = numero ? 'pointer' : 'grab';
      if (onFoco) onFoco(ficha);
    }
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
  let vivo = true;

  function fotograma() {
    if (!vivo) return;
    requestAnimationFrame(fotograma);
    const t = reloj.getElapsedTime();

    piezas.forEach((pieza) => {
      const destino = pieza.userData.destino;
      if (!destino) return;
      const vaiven = quieto ? 0 : Math.sin(t * 0.7 + destino.x) * 0.035;
      pieza.position.lerp(
        new THREE.Vector3(destino.x, destino.y + vaiven, destino.z), 0.08);
      pieza.rotation.y += (destino.giro - pieza.rotation.y) * 0.08;
      pieza.scale.lerp(destino.escala, 0.12);
    });

    if (!quieto) {
      motas.position.y = (Math.sin(t * 0.12) * 0.3) - 0.3;
      motas.rotation.y = t * 0.012;
    }

    revisarFoco();
    mandos.update();
    renderer.render(escena, camara);
  }
  fotograma();

  return {
    actualizar,
    destruir() {
      vivo = false;
      window.removeEventListener('resize', medir);
      mandos.dispose();
      renderer.dispose();
    },
  };
}
