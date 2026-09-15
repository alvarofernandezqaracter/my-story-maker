// El canon (§3), el generador de contexto (§7) y el flujo entero (§4, §8, §11)
// contra la capa simulada: sin red y sin coste, por el mismo camino que la
// ejecucion de verdad.
import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, rmSync, readFileSync, existsSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

import { cargarConfig } from '../src/config.mjs';
import { Canon, normalizarFecha } from '../src/canon.mjs';
import { Agentes } from '../src/agentes.mjs';
import { generarContexto, estimarTokens } from '../src/contexto.mjs';
import { preparar, escribirCapitulo, cerrar, reanudar } from '../src/flujo.mjs';

const BRIEF = {
  epoca: 'Sevilla, 1587',
  premisa: 'Un registro falsificado hunde a un cargador de Indias.',
  tono: 'seco',
  capitulos: 4,
  palabras_por_capitulo: 600,
};

/** Cada test corre en su propio directorio: el harness escribe en el cwd. */
function entorno(t) {
  const dir = mkdtempSync(join(tmpdir(), 'novela-'));
  const cwd = process.cwd();
  process.chdir(dir);
  const config = cargarConfig(join(cwd, 'config.json'));
  const canon = new Canon(join(dir, 'canon.db'));
  t.after(() => {
    process.chdir(cwd);
    // Windows no borra el fichero mientras SQLite lo tenga abierto.
    try { canon.cerrar(); } catch { /* ya cerrado */ }
    try { rmSync(dir, { recursive: true, force: true }); } catch { /* lo limpia el SO */ }
  });
  canon.guardarBrief(BRIEF);
  return { dir, canon, config, agentes: new Agentes(config) };
}

// -------------------------------------------------------------------- §3

test('canon: la escritura del cronista es una transaccion unica (VD-11)', (t) => {
  const { canon } = entorno(t);
  canon.guardarPersonajes([{
    id: 'ines', nombre: 'Ines', rol: 'protagonista', voz: 'v',
    motivacion: 'm', arco: 'a', ubicacion: 'Triana', sabe: [],
  }]);
  canon.guardarFichas([{
    numero: 1, titulo: 'T', acto: 1, sinopsis: 's', fecha: '1587-04',
    personajes: ['ines'], etiquetas: [], objetivo: 'o', palabras_objetivo: 600,
  }]);

  assert.throws(() => canon.escrituraDelCronista(1, {
    resumen: 'r', hilos_abiertos: [], hilos_cerrados: [], personajes_presentes: [],
    cambios_personaje: [{ id: 'no-existe', ubicacion: 'x' }],
  }));

  // Ni resumen ni cambio de ficha: o entra todo o no entra nada.
  assert.equal(canon.resumenes().length, 0);
  assert.equal(canon.personaje('ines').ubicacion, 'Triana');
  assert.equal(canon.ficha(1).estado, 'pendiente');
});

test('canon: fecha ISO parcial a clave comparable', () => {
  assert.equal(normalizarFecha('1587'), '1587-01-01');
  assert.equal(normalizarFecha('1587-04'), '1587-04-01');
  assert.ok(normalizarFecha('1587-04') < normalizarFecha('1587-05-02'));
});

// -------------------------------------------------------------------- §7

test('contexto: mismo capitulo y mismo canon dan el mismo paquete', async (t) => {
  const { canon, agentes, config } = entorno(t);
  await preparar({ canon, agentes, config });
  const a = generarContexto(canon, 2, config);
  const b = generarContexto(canon, 2, config);
  assert.equal(a.texto, b.texto);
});

test('contexto: el encargo y los personajes nunca se recortan', async (t) => {
  const { canon, agentes, config } = entorno(t);
  await preparar({ canon, agentes, config });
  await escribirCapitulo({ canon, agentes, config, numero: 1 });

  // Un tope absurdamente bajo fuerza todos los recortes posibles.
  const apretado = { ...config, contexto: { ...config.contexto, tope_contexto: 120 } };
  const p = generarContexto(canon, 2, apretado);

  assert.match(p.texto, /# Encargo del capitulo 2/);
  assert.match(p.texto, /# Personajes en escena/);
  assert.equal(p.bloques.memoria_larga.length, 0);
  assert.equal(p.bloques.epoca.length, 0);
  // Ni aun asi cabe: el capitulo se marcaria bloqueado en lugar de mutilarse.
  assert.equal(p.cabe, false);
});

test('contexto: el texto entero del capitulo anterior no entra, solo el enganche', async (t) => {
  const { canon, agentes, config } = entorno(t);
  await preparar({ canon, agentes, config });
  await escribirCapitulo({ canon, agentes, config, numero: 1 });

  const p = generarContexto(canon, 2, config);
  const textoCap1 = readFileSync(canon.intentoAprobado(1).ruta, 'utf8');
  assert.ok(!p.texto.includes(textoCap1));
  assert.match(p.texto, /# Enganche con el capitulo anterior/);

  const palabrasEnganche = p.bloques.enganche.split(/\s+/).length;
  assert.ok(palabrasEnganche <= config.contexto.palabras_enganche);
});

test('contexto: la epoca se filtra por etiquetas y pone verificado primero', async (t) => {
  const { canon, agentes, config } = entorno(t);
  await preparar({ canon, agentes, config });
  canon.guardarDatos([
    { id: 'z-verificado', categoria: 'comida', dato: 'd', fuente: 'https://ejemplo',
      estado: 'verificado', etiquetas: ['vestimenta'] },
    { id: 'sin-etiqueta', categoria: 'comida', dato: 'd', fuente: 'modelo',
      estado: 'sin_verificar', etiquetas: ['nada-que-ver'] },
  ]);
  canon.guardarFichas([{ ...canon.ficha(1), etiquetas: ['vestimenta'] }]);

  const p = generarContexto(canon, 1, config);
  assert.equal(p.bloques.epoca[0].id, 'z-verificado');
  assert.ok(!p.bloques.epoca.some((d) => d.id === 'sin-etiqueta'));
});

test('contexto: estimar tokens crece con el texto', () => {
  assert.ok(estimarTokens('a'.repeat(400)) > estimarTokens('a'.repeat(40)));
});

// ------------------------------------------------------------- §4, §8, §11

test('flujo: la preparacion deja dossier y escaleta coherentes entre si', async (t) => {
  const { canon, agentes, config } = entorno(t);
  const { estado } = await preparar({ canon, agentes, config });

  assert.equal(estado, 'estructurado');
  assert.ok(canon.datos().length > 0);
  assert.equal(canon.fichas().length, BRIEF.capitulos);

  // Cada ficha apunta a personajes que existen, y trae fecha y etiquetas.
  const ids = new Set(canon.personajes().map((p) => p.id));
  for (const f of canon.fichas()) {
    assert.ok(f.fecha, `el capitulo ${f.numero} no trae fecha`);
    assert.ok(f.etiquetas.length, `el capitulo ${f.numero} no trae etiquetas`);
    for (const id of f.personajes) assert.ok(ids.has(id));
  }
});

test('flujo: un capitulo aprobado actualiza el canon una sola vez', async (t) => {
  const { canon, agentes, config } = entorno(t);
  await preparar({ canon, agentes, config });
  const r = await escribirCapitulo({ canon, agentes, config, numero: 1 });

  assert.equal(r.aprobado, true);
  assert.equal(canon.ficha(1).estado, 'aprobado');
  assert.equal(canon.resumenes().length, 1);
  assert.equal(canon.personaje(canon.ficha(1).personajes[0]).actualizado_en, 1);
  assert.ok(existsSync(canon.intentoAprobado(1).ruta));
});

test('flujo: un capitulo malo se rechaza y el reintento lo arregla', async (t) => {
  const { canon, agentes, config } = entorno(t);
  await preparar({ canon, agentes, config });

  process.env.NOVELA_SIM_FALLOS = '1:1';
  t.after(() => { delete process.env.NOVELA_SIM_FALLOS; });

  const diario = [];
  const r = await escribirCapitulo({ canon, agentes, config, numero: 1, diario });

  assert.equal(r.aprobado, true);
  assert.equal(r.intento, 2);
  const puertas = diario.filter((e) => e.tipo === 'gate');
  assert.equal(puertas[0].aprueba, false);
  assert.equal(puertas[1].aprueba, true);
  // El intento malo queda como rastro, descartado.
  assert.equal(canon.intentos(1).find((i) => i.intento === 1).estado, 'descartado');
});

test('flujo: VD-08 descarta el intento sin llamar al validador', async (t) => {
  const { canon, agentes, config } = entorno(t);
  await preparar({ canon, agentes, config });

  process.env.NOVELA_SIM_CORTOS = '1:1';
  t.after(() => { delete process.env.NOVELA_SIM_CORTOS; });

  const diario = [];
  await escribirCapitulo({ canon, agentes, config, numero: 1, diario });

  assert.ok(diario.some((e) => e.tipo === 'vd08' && e.intento === 1));
  // El primer intento no llego al gate: la unica entrada de gate es la del segundo.
  const puertas = diario.filter((e) => e.tipo === 'gate');
  assert.equal(puertas.length, 1);
  assert.equal(puertas[0].intento, 2);
  // Y el intento descartado no tiene revisiones guardadas.
  assert.equal(canon.intentos(1).find((i) => i.intento === 1).revisiones, null);
});

test('flujo: al agotar intentos se bloquea el capitulo y el proyecto', async (t) => {
  const { canon, agentes, config } = entorno(t);
  await preparar({ canon, agentes, config });

  process.env.NOVELA_SIM_FALLOS = '1:1,1:2,1:3';
  t.after(() => { delete process.env.NOVELA_SIM_FALLOS; });

  const r = await escribirCapitulo({ canon, agentes, config, numero: 1 });

  assert.equal(r.aprobado, false);
  assert.equal(canon.ficha(1).estado, 'bloqueado');
  assert.equal(canon.estado(), 'bloqueado');
  // Se conserva un intento en propuesto y el resto descartados.
  const intentos = canon.intentos(1);
  assert.equal(intentos.filter((i) => i.estado === 'propuesto').length, 1);
  assert.equal(intentos.filter((i) => i.estado === 'descartado').length, 2);
  // Y el canon no creció: sin resumen, no hay agujero que propagar.
  assert.equal(canon.resumenes().length, 0);
});

test('flujo: reanudar no desbloquea', async (t) => {
  const { canon, agentes, config } = entorno(t);
  await preparar({ canon, agentes, config });

  process.env.NOVELA_SIM_FALLOS = '1:1,1:2,1:3';
  await escribirCapitulo({ canon, agentes, config, numero: 1 });
  delete process.env.NOVELA_SIM_FALLOS;

  const r = await reanudar({ canon, agentes, config });
  assert.equal(r.estado, 'bloqueado');
  assert.equal(canon.ficha(2).estado, 'pendiente');
});

test('flujo: reanudar localiza el primer capitulo no aprobado y termina el libro', async (t) => {
  const { canon, agentes, config } = entorno(t);
  await preparar({ canon, agentes, config });
  await escribirCapitulo({ canon, agentes, config, numero: 1 });

  const r = await reanudar({ canon, agentes, config });

  assert.equal(r.estado, 'editado');
  assert.equal(canon.fichas().every((f) => f.estado === 'aprobado'), true);
  assert.equal(canon.resumenes().length, BRIEF.capitulos);
  assert.ok(existsSync('retoques.md'));
});

test('flujo: el editor global deja retoques accionables fuera del canon', async (t) => {
  const { canon, agentes, config } = entorno(t);
  await preparar({ canon, agentes, config });
  for (const f of canon.fichas()) {
    await escribirCapitulo({ canon, agentes, config, numero: f.numero });
  }
  canon.marcarEstado('escrito');

  const { retoques, ruta } = await cerrar({ canon, agentes });

  assert.ok(retoques.length > 0);
  assert.equal(canon.estado(), 'editado');
  assert.match(readFileSync(ruta, 'utf8'), /# Retoques finales/);
  // retoques.md vive junto al canon, no dentro.
  assert.equal(canon.db.prepare(
    "SELECT name FROM sqlite_master WHERE type='table' AND name='retoque'",
  ).get(), undefined);
});

test('flujo: el modo separado del validador compone las tres dimensiones', async (t) => {
  const { canon, agentes: _, config } = entorno(t);
  const separado = { ...config, validador: { modo: 'separado' } };
  const agentes = new Agentes(separado);

  await preparar({ canon, agentes, config: separado });
  const r = await escribirCapitulo({ canon, agentes, config: separado, numero: 1 });

  assert.equal(r.aprobado, true);
  assert.deepEqual(r.revisiones.map((x) => x.dimension),
    ['continuidad', 'anacronismos', 'logica_ritmo']);
});
