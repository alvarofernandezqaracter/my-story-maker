// Lo determinista del harness: config (§12), gate (§8) y validadores (§9).
// Estos tests no llaman a ningun agente ni tocan disco.
import test from 'node:test';
import assert from 'node:assert/strict';

import { validarConfig, ErrorConfig } from '../src/config.mjs';
import { gate, mejorIntento, incidenciasOrdenadas } from '../src/gate.mjs';
import {
  comprobarSalidaDeAgente, comprobarDossier, comprobarEventos, comprobarReferencias,
  comprobarNumeroDeCapitulos, comprobarCapituloRedactado, comprobarPersonajesPresentes,
  comprobarRevisiones, comprobarResumenSoloSiAprobado, contarPalabras, contarParrafos,
} from '../src/validadores.mjs';

const CONFIG = JSON.parse(JSON.stringify({
  ejecucion: { modo: 'simulado' },
  gate: { nota_minima: 3, media_minima: 3.7, max_intentos: 3 },
  contexto: { tope_contexto: 40000, ventana_resumenes: 3, palabras_enganche: 400 },
  validador: { modo: 'unico' },
  margenes: {
    capitulos_min: 0.8, capitulos_max: 1.2,
    palabras_aviso: 0.15, palabras_bloqueo: 0.4, parrafos_min: 5,
  },
  modelo_por_rol: {
    investigador: 'claude-opus-5', arquitecto: 'claude-opus-5', escritor: 'claude-opus-5',
    validador: 'claude-sonnet-5', cronista: 'claude-sonnet-5', editor_global: 'claude-opus-5',
  },
  busqueda_web: true,
}));

const MARGENES = CONFIG.margenes;
const revision = (dimension, nota, incidencias = []) => ({ dimension, nota, incidencias });

// ------------------------------------------------------------------- §12

test('config: el fichero del proyecto es valido', () => {
  assert.deepEqual(validarConfig(CONFIG), CONFIG);
});

test('config: para si falta una clave', () => {
  const roto = { ...CONFIG };
  delete roto.busqueda_web;
  assert.throws(() => validarConfig(roto), ErrorConfig);
});

test('config: para si un valor cae fuera de rango', () => {
  const roto = { ...CONFIG, gate: { ...CONFIG.gate, media_minima: 9 } };
  assert.throws(() => validarConfig(roto), /media_minima/);
});

test('config: el margen de bloqueo tiene que superar al de aviso', () => {
  const roto = { ...CONFIG, margenes: { ...MARGENES, palabras_bloqueo: 0.1 } };
  assert.throws(() => validarConfig(roto), /palabras_bloqueo/);
});

// -------------------------------------------------------------------- §8

test('gate: aprueba con tres notas buenas y sin graves', () => {
  const v = gate([revision('continuidad', 4), revision('anacronismos', 4),
    revision('logica_ritmo', 4)], CONFIG.gate);
  assert.equal(v.aprueba, true);
});

test('gate: una nota por debajo del suelo tumba el capitulo', () => {
  const v = gate([revision('continuidad', 2), revision('anacronismos', 5),
    revision('logica_ritmo', 5)], CONFIG.gate);
  assert.equal(v.aprueba, false);
  assert.match(v.motivos.join(' '), /nota minima/);
});

test('gate: la media manda aunque ninguna nota baje del suelo', () => {
  // 3/3/5 da media 3,67, por debajo de 3,7, con todas las notas en el suelo.
  const v = gate([revision('continuidad', 3), revision('anacronismos', 3),
    revision('logica_ritmo', 5)], CONFIG.gate);
  assert.equal(v.aprueba, false);
  assert.match(v.motivos.join(' '), /media/);
});

test('gate: una incidencia grave veta por si sola con tres cuatros', () => {
  const v = gate([
    revision('continuidad', 4, [{ cita: 'x', severidad: 'grave', sugerencia: 'y' }]),
    revision('anacronismos', 4), revision('logica_ritmo', 4),
  ], CONFIG.gate);
  assert.equal(v.aprueba, false);
  assert.equal(v.graves.length, 1);
});

test('gate: al agotar intentos se conserva el de mejor media', () => {
  const intentos = [
    { intento: 1, revisiones: [revision('continuidad', 2), revision('anacronismos', 2),
      revision('logica_ritmo', 2)] },
    { intento: 2, revisiones: [revision('continuidad', 3), revision('anacronismos', 3),
      revision('logica_ritmo', 4)] },
    { intento: 3, revisiones: [revision('continuidad', 1), revision('anacronismos', 5),
      revision('logica_ritmo', 2)] },
  ];
  assert.equal(mejorIntento(intentos).intento, 2);
});

test('gate: las incidencias del reintento van por severidad', () => {
  const orden = incidenciasOrdenadas([
    revision('continuidad', 3, [{ cita: 'a', severidad: 'aviso', sugerencia: '' }]),
    revision('anacronismos', 2, [{ cita: 'b', severidad: 'grave', sugerencia: '' }]),
  ]);
  assert.equal(orden[0].severidad, 'grave');
});

// -------------------------------------------------------------------- §9

test('VD-01/VD-02: distingue forma rota de campo ausente', () => {
  const sinCampo = comprobarSalidaDeAgente('escritor', { faltantes: [] });
  assert.equal(sinCampo.comprobaciones.find((c) => c.id === 'VD-02').ok, false);

  const formaMala = comprobarSalidaDeAgente('escritor', { texto: 42 });
  assert.equal(formaMala.comprobaciones.find((c) => c.id === 'VD-01').ok, false);
});

test('VD-03: rechaza la propuesta entera, no la parte buena', () => {
  const conocidos = { personajes: new Set(['ines']), datos: new Set(), capitulos: new Set() };
  const c = comprobarReferencias('cronista', {
    personajes_presentes: ['ines', 'fantasma'],
  }, conocidos);
  assert.equal(c.ok, false);
  assert.match(c.detalles.join(' '), /fantasma/);
});

test('VD-04: un dato verificado no puede tener fuente "modelo"', () => {
  const c = comprobarDossier([
    { id: 'a', categoria: 'comida', dato: 'x', fuente: 'modelo', estado: 'verificado' },
    { id: 'b', categoria: 'comida', dato: 'x', fuente: 'modelo', estado: 'sin_verificar' },
  ]);
  assert.equal(c.ok, false);
  assert.deepEqual(c.malos.map((m) => m.id), ['a']);
});

test('VD-05: trama lleva capitulo, historico no', () => {
  assert.equal(comprobarEventos([{ id: 'e', tipo: 'trama' }]).ok, false);
  assert.equal(comprobarEventos([{ id: 'e', tipo: 'historico', capitulo: 3 }]).ok, false);
  assert.equal(comprobarEventos([{ id: 'e', tipo: 'trama', capitulo: 3 }]).ok, true);
});

test('VD-06: no hay resumen sin intento aprobado', () => {
  assert.equal(comprobarResumenSoloSiAprobado(null).ok, false);
  assert.equal(comprobarResumenSoloSiAprobado({ intento: 1 }).ok, true);
});

test('VD-07: el numero de capitulos se mide contra los margenes', () => {
  assert.equal(comprobarNumeroDeCapitulos(10, 10, MARGENES).ok, true);
  assert.equal(comprobarNumeroDeCapitulos(8, 10, MARGENES).ok, true);
  assert.equal(comprobarNumeroDeCapitulos(5, 10, MARGENES).ok, false);
  assert.equal(comprobarNumeroDeCapitulos(20, 10, MARGENES).ok, false);
});

test('VD-08: los dos escalones, que es la razon de los dos margenes', () => {
  const parrafos = (n, palabrasPorParrafo = 100) => Array.from(
    { length: n }, () => 'palabra '.repeat(palabrasPorParrafo).trim(),
  ).join('\n\n');

  // Dentro del margen de aviso: el texto vale y no genera nada.
  assert.equal(comprobarCapituloRedactado(parrafos(10, 100), 1000, MARGENES).ok, true);

  // Desvio del 20%: aviso, y el capitulo sigue camino del validador.
  const aviso = comprobarCapituloRedactado(parrafos(8, 100), 1000, MARGENES);
  assert.equal(aviso.severidad, 'aviso');

  // Desvio del 50%: bloqueante, no se gasta la llamada al validador.
  const bloqueo = comprobarCapituloRedactado(parrafos(5, 100), 1000, MARGENES);
  assert.equal(bloqueo.severidad, 'bloqueante');

  // Pocos parrafos bloquea aunque las palabras cuadren.
  const pocos = comprobarCapituloRedactado(parrafos(2, 500), 1000, MARGENES);
  assert.equal(pocos.severidad, 'bloqueante');
});

test('VD-08: el titulo markdown no cuenta como parrafo, pero si como palabras', () => {
  const texto = `# Titulo\n\n${['a b c', 'd e f'].join('\n\n')}`;
  assert.equal(contarParrafos(texto), 2);
  assert.equal(contarPalabras(texto), 8);
});

test('VD-09: personajes presentes es subconjunto de la ficha', () => {
  assert.equal(comprobarPersonajesPresentes(['a'], ['a', 'b']).ok, true);
  assert.equal(comprobarPersonajesPresentes(['a', 'z'], ['a', 'b']).ok, false);
});

test('VD-10: tres dimensiones, una vez cada una, nota entera 1-5', () => {
  const buenas = [revision('continuidad', 3), revision('anacronismos', 3),
    revision('logica_ritmo', 3)];
  assert.equal(comprobarRevisiones(buenas).ok, true);

  assert.equal(comprobarRevisiones(buenas.slice(0, 2)).ok, false);
  assert.equal(comprobarRevisiones([...buenas, revision('continuidad', 4)]).ok, false);
  assert.equal(comprobarRevisiones([revision('continuidad', 3.5),
    revision('anacronismos', 3), revision('logica_ritmo', 3)]).ok, false);
  assert.equal(comprobarRevisiones([revision('continuidad', 7),
    revision('anacronismos', 3), revision('logica_ritmo', 3)]).ok, false);
});
