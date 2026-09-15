// §3 Modelo de datos del canon y §6 memoria a largo plazo.
// El canon es una base SQLite y, al lado, un fichero Markdown por intento de
// capitulo en capitulos/. Ningun agente escribe aqui: el harness persiste lo
// que los agentes proponen y los validadores de §9 dejan pasar.
import { DatabaseSync } from 'node:sqlite';
import { mkdirSync } from 'node:fs';
import { dirname } from 'node:path';

const ESQUEMA = `
CREATE TABLE IF NOT EXISTS proyecto (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  epoca TEXT NOT NULL,
  premisa TEXT NOT NULL,
  tono TEXT NOT NULL,
  capitulos INTEGER NOT NULL,
  palabras_por_capitulo INTEGER NOT NULL,
  estado TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS personaje (
  id TEXT PRIMARY KEY,
  nombre TEXT NOT NULL,
  rol TEXT NOT NULL,
  voz TEXT NOT NULL,
  motivacion TEXT NOT NULL,
  arco TEXT NOT NULL,
  ubicacion TEXT NOT NULL,
  sabe TEXT NOT NULL DEFAULT '[]',
  actualizado_en INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS evento (
  id TEXT PRIMARY KEY,
  tipo TEXT NOT NULL,
  fecha TEXT NOT NULL,
  descripcion TEXT NOT NULL,
  capitulo INTEGER,
  personajes TEXT NOT NULL DEFAULT '[]',
  dato_id TEXT
);
CREATE TABLE IF NOT EXISTS dato (
  id TEXT PRIMARY KEY,
  categoria TEXT NOT NULL,
  dato TEXT NOT NULL,
  fuente TEXT NOT NULL,
  estado TEXT NOT NULL,
  etiquetas TEXT NOT NULL DEFAULT '[]'
);
CREATE TABLE IF NOT EXISTS ficha_capitulo (
  numero INTEGER PRIMARY KEY,
  titulo TEXT NOT NULL,
  acto INTEGER NOT NULL,
  sinopsis TEXT NOT NULL,
  fecha TEXT NOT NULL,
  personajes TEXT NOT NULL DEFAULT '[]',
  etiquetas TEXT NOT NULL DEFAULT '[]',
  objetivo TEXT NOT NULL,
  palabras_objetivo INTEGER NOT NULL,
  estado TEXT NOT NULL DEFAULT 'pendiente'
);
CREATE TABLE IF NOT EXISTS capitulo_redactado (
  capitulo INTEGER NOT NULL,
  intento INTEGER NOT NULL,
  ruta TEXT NOT NULL,
  palabras INTEGER NOT NULL,
  revisiones TEXT,
  faltantes TEXT,
  estado TEXT NOT NULL,
  creado TEXT NOT NULL,
  PRIMARY KEY (capitulo, intento)
);
CREATE TABLE IF NOT EXISTS resumen (
  capitulo INTEGER PRIMARY KEY,
  resumen TEXT NOT NULL,
  hilos_abiertos TEXT NOT NULL DEFAULT '[]',
  hilos_cerrados TEXT NOT NULL DEFAULT '[]',
  personajes_presentes TEXT NOT NULL DEFAULT '[]'
);
`;

const json = (v) => JSON.stringify(v ?? []);
const desdeJson = (v) => (v == null ? [] : JSON.parse(v));

/** Fecha ISO parcial (1587, 1587-04, 1587-04-12) a clave comparable. */
export function normalizarFecha(fecha) {
  if (!fecha) return null;
  const [a, m = '01', d = '01'] = String(fecha).split('-');
  return `${a.padStart(4, '0')}-${m.padStart(2, '0')}-${d.padStart(2, '0')}`;
}

export class Canon {
  constructor(ruta = 'canon.db') {
    const carpeta = dirname(ruta);
    mkdirSync(carpeta === '' ? '.' : carpeta, { recursive: true });
    this.db = new DatabaseSync(ruta);
    this.db.exec('PRAGMA foreign_keys = ON');
    this.db.exec(ESQUEMA);
  }

  cerrar() { this.db.close(); }

  // ---------- proyecto y brief (§3: el brief es fila unica de proyecto) ----------

  guardarBrief(brief) {
    this.db.prepare(`
      INSERT INTO proyecto (id, epoca, premisa, tono, capitulos, palabras_por_capitulo, estado)
      VALUES (1, ?, ?, ?, ?, ?, ?)
      ON CONFLICT(id) DO UPDATE SET
        epoca = excluded.epoca, premisa = excluded.premisa, tono = excluded.tono,
        capitulos = excluded.capitulos, palabras_por_capitulo = excluded.palabras_por_capitulo
    `).run(brief.epoca, brief.premisa, brief.tono, brief.capitulos,
      brief.palabras_por_capitulo, brief.estado ?? 'borrador');
    return this.proyecto();
  }

  proyecto() {
    return this.db.prepare('SELECT * FROM proyecto WHERE id = 1').get() ?? null;
  }

  estado() { return this.proyecto()?.estado ?? null; }

  marcarEstado(estado) {
    this.db.prepare('UPDATE proyecto SET estado = ? WHERE id = 1').run(estado);
  }

  // ---------- dossier ----------

  guardarDatos(datos) {
    const stmt = this.db.prepare(`
      INSERT INTO dato (id, categoria, dato, fuente, estado, etiquetas)
      VALUES (?, ?, ?, ?, ?, ?)
      ON CONFLICT(id) DO UPDATE SET
        categoria = excluded.categoria, dato = excluded.dato, fuente = excluded.fuente,
        estado = excluded.estado, etiquetas = excluded.etiquetas
    `);
    for (const d of datos) {
      stmt.run(d.id, d.categoria, d.dato, d.fuente, d.estado, json(d.etiquetas));
    }
  }

  datos() {
    return this.db.prepare('SELECT * FROM dato ORDER BY id').all()
      .map((d) => ({ ...d, etiquetas: desdeJson(d.etiquetas) }));
  }

  // ---------- personajes ----------

  guardarPersonajes(personajes) {
    const stmt = this.db.prepare(`
      INSERT INTO personaje
        (id, nombre, rol, voz, motivacion, arco, ubicacion, sabe, actualizado_en)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
      ON CONFLICT(id) DO UPDATE SET
        nombre = excluded.nombre, rol = excluded.rol, voz = excluded.voz,
        motivacion = excluded.motivacion, arco = excluded.arco,
        ubicacion = excluded.ubicacion, sabe = excluded.sabe
    `);
    for (const p of personajes) {
      stmt.run(p.id, p.nombre, p.rol, p.voz, p.motivacion, p.arco, p.ubicacion,
        json(p.sabe), p.actualizado_en ?? 0);
    }
  }

  personajes(ids = null) {
    const filas = this.db.prepare('SELECT * FROM personaje ORDER BY id').all()
      .map((p) => ({ ...p, sabe: desdeJson(p.sabe) }));
    if (!ids) return filas;
    const set = new Set(ids);
    return filas.filter((p) => set.has(p.id));
  }

  personaje(id) { return this.personajes([id])[0] ?? null; }

  // ---------- escaleta ----------

  guardarFichas(fichas) {
    const stmt = this.db.prepare(`
      INSERT INTO ficha_capitulo
        (numero, titulo, acto, sinopsis, fecha, personajes, etiquetas,
         objetivo, palabras_objetivo, estado)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
      ON CONFLICT(numero) DO UPDATE SET
        titulo = excluded.titulo, acto = excluded.acto, sinopsis = excluded.sinopsis,
        fecha = excluded.fecha, personajes = excluded.personajes,
        etiquetas = excluded.etiquetas, objetivo = excluded.objetivo,
        palabras_objetivo = excluded.palabras_objetivo
    `);
    for (const f of fichas) {
      stmt.run(f.numero, f.titulo, f.acto, f.sinopsis, f.fecha, json(f.personajes),
        json(f.etiquetas), f.objetivo, f.palabras_objetivo, f.estado ?? 'pendiente');
    }
  }

  fichas() {
    return this.db.prepare('SELECT * FROM ficha_capitulo ORDER BY numero').all()
      .map((f) => ({
        ...f, personajes: desdeJson(f.personajes), etiquetas: desdeJson(f.etiquetas),
      }));
  }

  ficha(numero) {
    const f = this.db.prepare('SELECT * FROM ficha_capitulo WHERE numero = ?').get(numero);
    if (!f) return null;
    return { ...f, personajes: desdeJson(f.personajes), etiquetas: desdeJson(f.etiquetas) };
  }

  marcarFicha(numero, estado) {
    this.db.prepare('UPDATE ficha_capitulo SET estado = ? WHERE numero = ?').run(estado, numero);
  }

  // ---------- capitulos redactados ----------

  guardarIntento({ capitulo, intento, ruta, palabras, faltantes, estado = 'propuesto' }) {
    this.db.prepare(`
      INSERT INTO capitulo_redactado
        (capitulo, intento, ruta, palabras, revisiones, faltantes, estado, creado)
      VALUES (?, ?, ?, ?, NULL, ?, ?, ?)
      ON CONFLICT(capitulo, intento) DO UPDATE SET
        ruta = excluded.ruta, palabras = excluded.palabras, revisiones = NULL,
        faltantes = excluded.faltantes, estado = excluded.estado, creado = excluded.creado
    `).run(capitulo, intento, ruta, palabras, json(faltantes), estado, new Date().toISOString());
  }

  guardarRevisiones(capitulo, intento, revisiones) {
    this.db.prepare(
      'UPDATE capitulo_redactado SET revisiones = ? WHERE capitulo = ? AND intento = ?',
    ).run(JSON.stringify(revisiones), capitulo, intento);
  }

  intentos(capitulo) {
    return this.db.prepare(
      'SELECT * FROM capitulo_redactado WHERE capitulo = ? ORDER BY intento',
    ).all(capitulo).map((i) => ({
      ...i,
      revisiones: i.revisiones ? JSON.parse(i.revisiones) : null,
      faltantes: desdeJson(i.faltantes),
    }));
  }

  intentoAprobado(capitulo) {
    return this.intentos(capitulo).find((i) => i.estado === 'aprobado') ?? null;
  }

  marcarIntento(capitulo, intento, estado) {
    this.db.prepare(
      'UPDATE capitulo_redactado SET estado = ? WHERE capitulo = ? AND intento = ?',
    ).run(estado, capitulo, intento);
  }

  /** Al aprobar: el intento bueno se queda, los demas se descartan (§8). */
  fijarIntentoAprobado(capitulo, intento) {
    this.db.prepare(`UPDATE capitulo_redactado
      SET estado = CASE WHEN intento = ? THEN 'aprobado' ELSE 'descartado' END
      WHERE capitulo = ?`).run(intento, capitulo);
  }

  // ---------- resumenes y timeline ----------

  resumenes() {
    return this.db.prepare('SELECT * FROM resumen ORDER BY capitulo').all().map((r) => ({
      ...r,
      hilos_abiertos: desdeJson(r.hilos_abiertos),
      hilos_cerrados: desdeJson(r.hilos_cerrados),
      personajes_presentes: desdeJson(r.personajes_presentes),
    }));
  }

  eventos() {
    return this.db.prepare('SELECT * FROM evento ORDER BY fecha, id').all()
      .map((e) => ({ ...e, personajes: desdeJson(e.personajes) }));
  }

  guardarEventos(eventos) {
    const stmt = this.db.prepare(`
      INSERT INTO evento (id, tipo, fecha, descripcion, capitulo, personajes, dato_id)
      VALUES (?, ?, ?, ?, ?, ?, ?)
      ON CONFLICT(id) DO UPDATE SET
        tipo = excluded.tipo, fecha = excluded.fecha, descripcion = excluded.descripcion,
        capitulo = excluded.capitulo, personajes = excluded.personajes,
        dato_id = excluded.dato_id
    `);
    for (const e of eventos) {
      stmt.run(e.id, e.tipo, e.fecha, e.descripcion, e.capitulo ?? null,
        json(e.personajes), e.dato_id ?? null);
    }
  }

  /**
   * VD-11: la escritura del cronista es una transaccion unica. O entran resumen,
   * cambios de ficha y eventos juntos, o no entra nada.
   */
  escrituraDelCronista(capitulo, propuesta) {
    this.db.exec('BEGIN');
    try {
      this.db.prepare(`
        INSERT INTO resumen
          (capitulo, resumen, hilos_abiertos, hilos_cerrados, personajes_presentes)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(capitulo) DO UPDATE SET
          resumen = excluded.resumen, hilos_abiertos = excluded.hilos_abiertos,
          hilos_cerrados = excluded.hilos_cerrados,
          personajes_presentes = excluded.personajes_presentes
      `).run(capitulo, propuesta.resumen, json(propuesta.hilos_abiertos),
        json(propuesta.hilos_cerrados), json(propuesta.personajes_presentes));

      for (const cambio of propuesta.cambios_personaje ?? []) {
        const actual = this.personaje(cambio.id);
        if (!actual) throw new Error(`personaje desconocido: ${cambio.id}`);
        this.db.prepare(`UPDATE personaje
          SET ubicacion = ?, sabe = ?, actualizado_en = ? WHERE id = ?`)
          .run(cambio.ubicacion ?? actual.ubicacion,
            json(cambio.sabe ?? actual.sabe), capitulo, cambio.id);
      }

      this.guardarEventos(propuesta.eventos ?? []);
      this.db.prepare("UPDATE ficha_capitulo SET estado = 'aprobado' WHERE numero = ?")
        .run(capitulo);
      this.db.exec('COMMIT');
    } catch (e) {
      this.db.exec('ROLLBACK');
      throw e;
    }
  }

  // ---------- consultas de apoyo ----------

  idsConocidos() {
    return {
      personajes: new Set(this.personajes().map((p) => p.id)),
      datos: new Set(this.datos().map((d) => d.id)),
      capitulos: new Set(this.fichas().map((f) => f.numero)),
    };
  }

  /** Hilos abiertos en algun resumen y no cerrados en ninguno (§7). */
  hilosVivos() {
    const abiertos = [];
    const cerrados = new Set();
    for (const r of this.resumenes()) {
      for (const h of r.hilos_abiertos) abiertos.push({ hilo: h, capitulo: r.capitulo });
      for (const h of r.hilos_cerrados) cerrados.add(h);
    }
    return abiertos.filter((a) => !cerrados.has(a.hilo));
  }
}
