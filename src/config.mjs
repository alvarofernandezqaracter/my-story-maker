// §12 Configuracion. Un unico config.json en la raiz. El harness lo carga al
// arrancar, lo valida entero y para si falta una clave o un valor cae fuera de
// rango: una errata en un umbral sale mas barata descubierta al arrancar.
import { readFileSync } from 'node:fs';

export const ROLES = [
  'investigador', 'arquitecto', 'escritor', 'validador', 'cronista', 'editor_global',
];

export class ErrorConfig extends Error {
  constructor(mensaje) { super(mensaje); this.name = 'ErrorConfig'; }
}

const entero = (v) => Number.isInteger(v);
const numero = (v) => typeof v === 'number' && Number.isFinite(v);
const fraccion = (v) => numero(v) && v > 0 && v < 1;

// [clave, predicado, que se espera]
const REGLAS = [
  ['ejecucion.modo', (v) => v === 'simulado' || v === 'real', '"simulado" o "real"'],
  ['gate.nota_minima', (v) => entero(v) && v >= 1 && v <= 5, 'entero entre 1 y 5'],
  ['gate.media_minima', (v) => numero(v) && v >= 1 && v <= 5, 'numero entre 1 y 5'],
  ['gate.max_intentos', (v) => entero(v) && v >= 1, 'entero >= 1'],
  ['contexto.tope_contexto', (v) => entero(v) && v > 0, 'entero > 0'],
  ['contexto.ventana_resumenes', (v) => entero(v) && v >= 0, 'entero >= 0'],
  ['contexto.palabras_enganche', (v) => entero(v) && v >= 0, 'entero >= 0'],
  ['validador.modo', (v) => v === 'unico' || v === 'separado', '"unico" o "separado"'],
  ['margenes.capitulos_min', (v) => numero(v) && v > 0 && v <= 1, 'numero en (0, 1]'],
  ['margenes.capitulos_max', (v) => numero(v) && v >= 1, 'numero >= 1'],
  ['margenes.palabras_aviso', fraccion, 'fraccion en (0, 1)'],
  ['margenes.palabras_bloqueo', fraccion, 'fraccion en (0, 1)'],
  ['margenes.parrafos_min', (v) => entero(v) && v >= 1, 'entero >= 1'],
  ['modelo_por_rol', (v) => !!v && ROLES.every((r) => typeof v[r] === 'string' && v[r]),
    'un modelo por cada rol de §5'],
  ['busqueda_web', (v) => typeof v === 'boolean', 'booleano'],
];

function leer(obj, ruta) {
  return ruta.split('.').reduce((o, k) => (o == null ? undefined : o[k]), obj);
}

export function validarConfig(bruto) {
  const fallos = [];
  for (const [clave, ok, esperado] of REGLAS) {
    const valor = leer(bruto, clave);
    if (valor === undefined) { fallos.push(`falta la clave ${clave}`); continue; }
    if (!ok(valor)) fallos.push(`${clave}: se esperaba ${esperado} y hay ${JSON.stringify(valor)}`);
  }
  // Los dos margenes de palabras de VD-08 solo tienen sentido en escalones.
  const aviso = leer(bruto, 'margenes.palabras_aviso');
  const bloqueo = leer(bruto, 'margenes.palabras_bloqueo');
  if (fraccion(aviso) && fraccion(bloqueo) && bloqueo <= aviso) {
    fallos.push('margenes.palabras_bloqueo debe ser mayor que margenes.palabras_aviso');
  }
  const min = leer(bruto, 'margenes.capitulos_min');
  const max = leer(bruto, 'margenes.capitulos_max');
  if (numero(min) && numero(max) && max < min) {
    fallos.push('margenes.capitulos_max debe ser mayor o igual que margenes.capitulos_min');
  }
  if (fallos.length) {
    throw new ErrorConfig(`config.json no es valido:\n  - ${fallos.join('\n  - ')}`);
  }
  return bruto;
}

export function cargarConfig(ruta = 'config.json') {
  let bruto;
  try {
    bruto = JSON.parse(readFileSync(ruta, 'utf8'));
  } catch (e) {
    throw new ErrorConfig(`no se pudo leer ${ruta}: ${e.message}`);
  }
  return validarConfig(bruto);
}
