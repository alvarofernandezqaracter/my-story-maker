# §3 Modelo de datos del canon y §6 memoria a largo plazo.
# El canon es una base SQLite y, al lado, un fichero Markdown por intento de
# capitulo en capitulos/. Ningun agente escribe aqui: el harness persiste lo
# que los agentes proponen y los validadores de §9 dejan pasar.
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

ESQUEMA = """
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
"""


def _json(valor):
    return json.dumps(valor if valor is not None else [])


def _desde_json(valor):
    return [] if valor is None else json.loads(valor)


def _ahora():
    return datetime.now(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z')


def normalizar_fecha(fecha):
    """Fecha ISO parcial (1587, 1587-04, 1587-04-12) a clave comparable."""
    if not fecha:
        return None
    partes = str(fecha).split('-')
    anyo = partes[0]
    mes = partes[1] if len(partes) > 1 else '01'
    dia = partes[2] if len(partes) > 2 else '01'
    return '{}-{}-{}'.format(anyo.rjust(4, '0'), mes.rjust(2, '0'), dia.rjust(2, '0'))


class Canon:
    def __init__(self, ruta='canon.db'):
        Path(ruta).parent.mkdir(parents=True, exist_ok=True)
        # isolation_level=None deja las transacciones en manos del codigo: la
        # del cronista (VD-11) es explicita y tiene que verse como tal.
        self.db = sqlite3.connect(ruta, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA foreign_keys = ON')
        self.db.executescript(ESQUEMA)

    def cerrar(self):
        self.db.close()

    def _fila(self, sql, parametros=()):
        fila = self.db.execute(sql, parametros).fetchone()
        return dict(fila) if fila else None

    def _filas(self, sql, parametros=()):
        return [dict(f) for f in self.db.execute(sql, parametros).fetchall()]

    # ---------- proyecto y brief (§3: el brief es fila unica de proyecto) ----------

    def guardar_brief(self, brief):
        self.db.execute(
            """
            INSERT INTO proyecto (id, epoca, premisa, tono, capitulos,
                                  palabras_por_capitulo, estado)
            VALUES (1, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
              epoca = excluded.epoca, premisa = excluded.premisa, tono = excluded.tono,
              capitulos = excluded.capitulos,
              palabras_por_capitulo = excluded.palabras_por_capitulo
            """,
            (brief['epoca'], brief['premisa'], brief['tono'], brief['capitulos'],
             brief['palabras_por_capitulo'], brief.get('estado') or 'borrador'),
        )
        return self.proyecto()

    def proyecto(self):
        return self._fila('SELECT * FROM proyecto WHERE id = 1')

    def estado(self):
        p = self.proyecto()
        return p['estado'] if p else None

    def marcar_estado(self, estado):
        self.db.execute('UPDATE proyecto SET estado = ? WHERE id = 1', (estado,))

    # ---------- dossier ----------

    def guardar_datos(self, datos):
        self.db.executemany(
            """
            INSERT INTO dato (id, categoria, dato, fuente, estado, etiquetas)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
              categoria = excluded.categoria, dato = excluded.dato,
              fuente = excluded.fuente, estado = excluded.estado,
              etiquetas = excluded.etiquetas
            """,
            [(d['id'], d['categoria'], d['dato'], d['fuente'], d['estado'],
              _json(d.get('etiquetas'))) for d in datos],
        )

    def datos(self):
        filas = self._filas('SELECT * FROM dato ORDER BY id')
        for d in filas:
            d['etiquetas'] = _desde_json(d['etiquetas'])
        return filas

    # ---------- personajes ----------

    def guardar_personajes(self, personajes):
        self.db.executemany(
            """
            INSERT INTO personaje
              (id, nombre, rol, voz, motivacion, arco, ubicacion, sabe, actualizado_en)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
              nombre = excluded.nombre, rol = excluded.rol, voz = excluded.voz,
              motivacion = excluded.motivacion, arco = excluded.arco,
              ubicacion = excluded.ubicacion, sabe = excluded.sabe
            """,
            [(p['id'], p['nombre'], p['rol'], p['voz'], p['motivacion'], p['arco'],
              p['ubicacion'], _json(p.get('sabe')), p.get('actualizado_en') or 0)
             for p in personajes],
        )

    def personajes(self, ids=None):
        filas = self._filas('SELECT * FROM personaje ORDER BY id')
        for p in filas:
            p['sabe'] = _desde_json(p['sabe'])
        if ids is None:
            return filas
        permitidos = set(ids)
        return [p for p in filas if p['id'] in permitidos]

    def personaje(self, id_personaje):
        encontrados = self.personajes([id_personaje])
        return encontrados[0] if encontrados else None

    # ---------- escaleta ----------

    def guardar_fichas(self, fichas):
        self.db.executemany(
            """
            INSERT INTO ficha_capitulo
              (numero, titulo, acto, sinopsis, fecha, personajes, etiquetas,
               objetivo, palabras_objetivo, estado)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(numero) DO UPDATE SET
              titulo = excluded.titulo, acto = excluded.acto,
              sinopsis = excluded.sinopsis, fecha = excluded.fecha,
              personajes = excluded.personajes, etiquetas = excluded.etiquetas,
              objetivo = excluded.objetivo,
              palabras_objetivo = excluded.palabras_objetivo
            """,
            [(f['numero'], f['titulo'], f['acto'], f['sinopsis'], f['fecha'],
              _json(f.get('personajes')), _json(f.get('etiquetas')), f['objetivo'],
              f['palabras_objetivo'], f.get('estado') or 'pendiente') for f in fichas],
        )

    def fichas(self):
        filas = self._filas('SELECT * FROM ficha_capitulo ORDER BY numero')
        for f in filas:
            f['personajes'] = _desde_json(f['personajes'])
            f['etiquetas'] = _desde_json(f['etiquetas'])
        return filas

    def ficha(self, numero):
        f = self._fila('SELECT * FROM ficha_capitulo WHERE numero = ?', (numero,))
        if not f:
            return None
        f['personajes'] = _desde_json(f['personajes'])
        f['etiquetas'] = _desde_json(f['etiquetas'])
        return f

    def marcar_ficha(self, numero, estado):
        self.db.execute(
            'UPDATE ficha_capitulo SET estado = ? WHERE numero = ?', (estado, numero))

    # ---------- capitulos redactados ----------

    def guardar_intento(self, capitulo, intento, ruta, palabras,
                        faltantes=None, estado='propuesto'):
        self.db.execute(
            """
            INSERT INTO capitulo_redactado
              (capitulo, intento, ruta, palabras, revisiones, faltantes, estado, creado)
            VALUES (?, ?, ?, ?, NULL, ?, ?, ?)
            ON CONFLICT(capitulo, intento) DO UPDATE SET
              ruta = excluded.ruta, palabras = excluded.palabras, revisiones = NULL,
              faltantes = excluded.faltantes, estado = excluded.estado,
              creado = excluded.creado
            """,
            (capitulo, intento, ruta, palabras, _json(faltantes), estado, _ahora()),
        )

    def guardar_revisiones(self, capitulo, intento, revisiones):
        self.db.execute(
            'UPDATE capitulo_redactado SET revisiones = ? WHERE capitulo = ? AND intento = ?',
            (json.dumps(revisiones), capitulo, intento),
        )

    def intentos(self, capitulo):
        filas = self._filas(
            'SELECT * FROM capitulo_redactado WHERE capitulo = ? ORDER BY intento',
            (capitulo,),
        )
        for i in filas:
            i['revisiones'] = json.loads(i['revisiones']) if i['revisiones'] else None
            i['faltantes'] = _desde_json(i['faltantes'])
        return filas

    def intento_aprobado(self, capitulo):
        for i in self.intentos(capitulo):
            if i['estado'] == 'aprobado':
                return i
        return None

    def marcar_intento(self, capitulo, intento, estado):
        self.db.execute(
            'UPDATE capitulo_redactado SET estado = ? WHERE capitulo = ? AND intento = ?',
            (estado, capitulo, intento),
        )

    def fijar_intento_aprobado(self, capitulo, intento):
        """Al aprobar: el intento bueno se queda, los demas se descartan (§8)."""
        self.db.execute(
            """UPDATE capitulo_redactado
               SET estado = CASE WHEN intento = ? THEN 'aprobado' ELSE 'descartado' END
               WHERE capitulo = ?""",
            (intento, capitulo),
        )

    # ---------- resumenes y timeline ----------

    def resumenes(self):
        filas = self._filas('SELECT * FROM resumen ORDER BY capitulo')
        for r in filas:
            r['hilos_abiertos'] = _desde_json(r['hilos_abiertos'])
            r['hilos_cerrados'] = _desde_json(r['hilos_cerrados'])
            r['personajes_presentes'] = _desde_json(r['personajes_presentes'])
        return filas

    def eventos(self):
        filas = self._filas('SELECT * FROM evento ORDER BY fecha, id')
        for e in filas:
            e['personajes'] = _desde_json(e['personajes'])
        return filas

    def guardar_eventos(self, eventos):
        self.db.executemany(
            """
            INSERT INTO evento (id, tipo, fecha, descripcion, capitulo, personajes, dato_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
              tipo = excluded.tipo, fecha = excluded.fecha,
              descripcion = excluded.descripcion, capitulo = excluded.capitulo,
              personajes = excluded.personajes, dato_id = excluded.dato_id
            """,
            [(e['id'], e['tipo'], e['fecha'], e['descripcion'], e.get('capitulo'),
              _json(e.get('personajes')), e.get('dato_id')) for e in eventos],
        )

    def escritura_del_cronista(self, capitulo, propuesta):
        """VD-11: la escritura del cronista es una transaccion unica.

        O entran resumen, cambios de ficha y eventos juntos, o no entra nada.
        """
        self.db.execute('BEGIN')
        try:
            self.db.execute(
                """
                INSERT INTO resumen
                  (capitulo, resumen, hilos_abiertos, hilos_cerrados, personajes_presentes)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(capitulo) DO UPDATE SET
                  resumen = excluded.resumen, hilos_abiertos = excluded.hilos_abiertos,
                  hilos_cerrados = excluded.hilos_cerrados,
                  personajes_presentes = excluded.personajes_presentes
                """,
                (capitulo, propuesta['resumen'], _json(propuesta.get('hilos_abiertos')),
                 _json(propuesta.get('hilos_cerrados')),
                 _json(propuesta.get('personajes_presentes'))),
            )

            for cambio in propuesta.get('cambios_personaje') or []:
                actual = self.personaje(cambio['id'])
                if not actual:
                    raise ValueError('personaje desconocido: {}'.format(cambio['id']))
                self.db.execute(
                    """UPDATE personaje
                       SET ubicacion = ?, sabe = ?, actualizado_en = ? WHERE id = ?""",
                    (cambio.get('ubicacion') or actual['ubicacion'],
                     _json(cambio.get('sabe') if cambio.get('sabe') is not None
                           else actual['sabe']),
                     capitulo, cambio['id']),
                )

            self.guardar_eventos(propuesta.get('eventos') or [])
            self.db.execute(
                "UPDATE ficha_capitulo SET estado = 'aprobado' WHERE numero = ?", (capitulo,))
            self.db.execute('COMMIT')
        except Exception:
            self.db.execute('ROLLBACK')
            raise

    # ---------- consultas de apoyo ----------

    def ids_conocidos(self):
        return {
            'personajes': {p['id'] for p in self.personajes()},
            'datos': {d['id'] for d in self.datos()},
            'capitulos': {f['numero'] for f in self.fichas()},
        }

    def hilos_vivos(self):
        """Hilos abiertos en algun resumen y no cerrados en ninguno (§7)."""
        abiertos = []
        cerrados = set()
        for r in self.resumenes():
            for h in r['hilos_abiertos']:
                abiertos.append({'hilo': h, 'capitulo': r['capitulo']})
            for h in r['hilos_cerrados']:
                cerrados.add(h)
        return [a for a in abiertos if a['hilo'] not in cerrados]
