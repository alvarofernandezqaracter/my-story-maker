"""El esquema del almacen: una tabla por tipo de artefacto.

El esquema espeja las tres capas —Obra, Mundo y Produccion— mas la `Traza`, y
toda fila cuelga de un `id_obra`, salvo las de la entrevista, que es anterior a
la obra y cuelga de su `id_entrevista` (SPEC1 RD-02, D-24). La capa Obra
referencia la capa Mundo por `id` y nunca la duplica; la de Produccion
referencia a las dos y ninguna la referencia a ella. Eso se impone aqui con
claves foraneas, no con buena voluntad.

De cada artefacto se guarda el cuerpo integro tal como lo escribio el agente y,
al lado, solo las columnas por las que hace falta consultar. Si aparece la
tentacion de una columna por atributo narrativo, es que se esta construyendo el
harness a medida que el proyecto prohibe.

Los vocabularios controlados se declaran como `CHECK` y salen de
`novela.vocabularios`: tenerlos en un solo sitio es lo que impide que la lista
de Python y la de SQL se separen sin que nadie se entere.
"""

from dataclasses import dataclass

from novela.vocabularios import (
    CICLO_DE_VIDA_DEL_CAPITULO,
    DECISION_DE_POLICY,
    DIMENSIONES,
    ESTADO_DE_COMPROMISO,
    ESTADO_DE_PRODUCCION,
    MEMORIA,
    NIVEL_DE_VETO,
    ROLES,
    SEVERIDAD,
    TIPOS_DE_LA_CAPA_MUNDO,
    TIPOS_DE_LA_CAPA_OBRA,
    TIPOS_DE_LA_CAPA_PRODUCCION,
)

# Estado de una `Critica`. Las cuatro palabras salen de los documentos —una
# critica se descarta sin evidencia (RF-31), se atiende o se rechaza con motivo
# en la `Revision` (architecture.md 2) y las que quedan se anotan abiertas
# (RF-33)—, pero `definitions.md` no las declara todavia como vocabulario.
ESTADO_DE_CRITICA: tuple[str, ...] = ("abierta", "atendida", "rechazada", "descartada")

# Lo que el Documentalista recoge para una escena concreta, y que por eso se
# consulta por capitulo y escena en vez de traerse por `id`.
DOCUMENTALES: tuple[str, ...] = ("Fuente", "Concepto", "Practica", "RegistroLinguistico")

# Las columnas por las que se consulta, mas alla de la obra. Ninguna tabla las
# lleva todas: cada tipo declara las suyas.
COLUMNAS_DE_CONSULTA: dict[str, str] = {
    "capitulo": "INT",
    "escena": "TEXT",
    "estado": "TEXT",
    "severidad": "TEXT",
    "dimension": "TEXT",
    "rol": "TEXT",
}


@dataclass(frozen=True)
class Columna:
    """Una columna propia de un tipo, cuando las siete comunes no bastan."""

    nombre: str
    tipo: str
    vocabulario: tuple[str, ...] | None = None


@dataclass(frozen=True)
class Tabla:
    """Lo que hay que saber de un tipo de artefacto para darle tabla.

    `desde_migracion` es en cual nace la tabla. Una migracion ya aplicada no se
    reescribe, asi que un tipo nuevo no se cuela en la 1: declara la suya y las
    bases viejas y las recien creadas acaban con el mismo esquema.
    """

    tipo: str
    capa: str
    memoria: str
    consulta: tuple[str, ...] = ()
    vocabulario_de_estado: tuple[str, ...] | None = None
    inmutable: bool = False
    propias: tuple[Columna, ...] = ()
    indices: tuple[tuple[str, ...], ...] = ()
    notas: str = ""
    desde_migracion: int = 1


TABLAS: tuple[Tabla, ...] = (
    # --- Capa 1, la obra: como esta hecho el texto ------------------------
    Tabla("Obra", "obra", "obra", notas="Raiz: toda fila del almacen cuelga de ella"),
    Tabla("Parte", "obra", "obra"),
    Tabla(
        "Capitulo",
        "obra",
        "obra",
        consulta=("capitulo", "estado"),
        vocabulario_de_estado=CICLO_DE_VIDA_DEL_CAPITULO,
        indices=(("id_obra", "capitulo"),),
    ),
    Tabla(
        "Escena",
        "obra",
        "obra",
        consulta=("capitulo", "estado"),
        vocabulario_de_estado=ESTADO_DE_PRODUCCION,
        propias=(Columna("orden", "INT"),),
        indices=(("id_obra", "capitulo", "orden"),),
    ),
    Tabla(
        "Beat",
        "obra",
        "capitulo",
        consulta=("capitulo", "escena"),
        propias=(Columna("orden", "INT"),),
    ),
    Tabla(
        "Parrafo",
        "obra",
        "obra",
        consulta=("capitulo", "escena"),
        propias=(Columna("orden", "INT"),),
        indices=(("id_obra", "capitulo", "escena", "orden"),),
    ),
    Tabla(
        "Compromiso",
        "obra",
        "obra",
        consulta=("capitulo", "escena", "estado"),
        vocabulario_de_estado=ESTADO_DE_COMPROMISO,
        indices=(("id_obra", "estado"),),
    ),
    # Que hecho de la biblia nombra un capitulo cerrado (RF-80): la relacion
    # referencial `menciona`, escrita por el Archivero al destilar. La ficha no
    # se toca; en que capitulos se usa un hecho se deriva de aqui (RF-84).
    Tabla(
        "Mencion",
        "obra",
        "obra",
        consulta=("capitulo",),
        inmutable=True,
        propias=(Columna("hecho", "TEXT"),),
        indices=(("id_obra", "hecho"), ("id_obra", "capitulo")),
        desde_migracion=4,
        notas="Solo la escribe el Archivero; solo de anadir",
    ),
    # --- Capa 2, el mundo: de que habla el texto --------------------------
    # Las fichas del Constructor de mundo se traen por `id` desde el contrato de
    # la escena, no por consulta: de ahi que no lleven mas columnas que las
    # comunes. Lo que recoge el Documentalista, en cambio, se recupera por
    # escena y se filtra por fecha y lugar, asi que lleva capitulo y escena.
    *(
        Tabla(tipo, "mundo", "obra")
        for tipo in TIPOS_DE_LA_CAPA_MUNDO
        if tipo not in DOCUMENTALES and tipo != "Recuerdo"
    ),
    # Lo que el destinatario aporta de su vida (RF-07, D-13). Ningun rol del
    # censo lo escribe: nace con el alta de la obra, como la propia `Obra`. No
    # es una `Fuente` de tipo nuevo porque no es evidencia de una epoca sino de
    # una persona, y abrir esa puerta a un segundo escritor vaciaria de sentido
    # el invariante que hace detectable una alucinacion historica.
    Tabla(
        "Recuerdo",
        "mundo",
        "obra",
        inmutable=True,
        desde_migracion=3,
        notas="Lo aporta el editor en el brief; ningun rol lo escribe",
    ),
    *(
        Tabla(
            tipo,
            "mundo",
            "obra",
            consulta=("capitulo", "escena"),
            inmutable=(tipo == "Fuente"),
            indices=(("id_obra", "capitulo"),),
            notas=(
                "Solo la escribe el Documentalista"
                if tipo == "Fuente"
                else "Lo recoge el Documentalista"
            ),
        )
        for tipo in DOCUMENTALES
    ),
    # --- Capa 3, la produccion: como se ha llegado hasta aqui -------------
    Tabla("Agente", "produccion", "obra", consulta=("rol",)),
    Tabla(
        "Tarea",
        "produccion",
        "obra",
        consulta=("capitulo", "escena", "rol", "estado"),
        vocabulario_de_estado=ESTADO_DE_PRODUCCION,
        indices=(("id_obra", "capitulo"),),
    ),
    Tabla(
        "Plan",
        "produccion",
        "obra",
        consulta=("capitulo", "estado"),
        vocabulario_de_estado=ESTADO_DE_PRODUCCION,
        indices=(("id_obra", "capitulo"),),
    ),
    Tabla(
        "Borrador",
        "produccion",
        "capitulo",
        consulta=("capitulo", "escena", "estado"),
        vocabulario_de_estado=ESTADO_DE_PRODUCCION,
        propias=(Columna("version", "INT"),),
        indices=(("id_obra", "capitulo", "escena", "estado"),),
        notas="Inmutable en cuanto se acepta; hasta entonces es candidato",
    ),
    Tabla(
        "Critica",
        "produccion",
        "capitulo",
        consulta=("capitulo", "escena", "estado", "severidad", "dimension", "rol"),
        vocabulario_de_estado=ESTADO_DE_CRITICA,
        indices=(
            ("id_obra", "estado", "severidad"),
            ("id_obra", "capitulo", "escena", "estado"),
            ("id_obra", "dimension"),
        ),
    ),
    Tabla(
        "Revision",
        "produccion",
        "capitulo",
        consulta=("capitulo", "escena"),
        indices=(("id_obra", "capitulo", "escena"),),
    ),
    Tabla("Decision", "produccion", "obra", consulta=("capitulo",), inmutable=True),
    Tabla(
        "EventoEstado",
        "produccion",
        "obra",
        consulta=("capitulo",),
        inmutable=True,
        indices=(("id_obra", "capitulo"),),
        notas="Solo de anadir: el mundo no cambia por ninguna otra via",
    ),
    Tabla(
        "ResumenCapitulo",
        "produccion",
        "obra",
        consulta=("capitulo",),
        inmutable=True,
        indices=(("id_obra", "capitulo"),),
    ),
    Tabla(
        "Traza",
        "produccion",
        "obra",
        consulta=("capitulo", "escena", "rol"),
        propias=(
            Columna("tarea", "TEXT"),
            Columna("intento", "INT"),
            Columna("tokens_de_entrada_estimados", "INT"),
            Columna("tokens_de_entrada_medidos", "INT"),
            Columna("tokens_de_salida", "INT"),
            Columna("coste", "REAL"),
            Columna("latencia_ms", "INT"),
            Columna("abierta_en", "TEXT"),
            Columna("cerrada_en", "TEXT"),
        ),
        indices=(("id_obra", "cerrada_en"), ("id_obra", "capitulo", "rol")),
        notas="No es salida de ningun rol: se registra en toda tarea",
    ),
)

TABLA_POR_TIPO: dict[str, Tabla] = {tabla.tipo: tabla for tabla in TABLAS}

# La migracion que da versiones a la obra (SPEC1 4.12), y las dos columnas que
# anade a toda tabla de artefactos: en que version se escribio la fila y que
# version la relevo. Lo que ve cada version se deduce de esas dos (RF-113).
MIGRACION_DE_LAS_VERSIONES = 7
COLUMNAS_DE_LA_VERSION: tuple[str, ...] = (
    "version_de_obra INT NOT NULL DEFAULT 1",
    "relevado_por INT",
)

TIPOS_INMUTABLES: tuple[str, ...] = tuple(t.tipo for t in TABLAS if t.inmutable)

CAPA_POR_TIPO: dict[str, str] = {tabla.tipo: tabla.capa for tabla in TABLAS}


def nombre_de_tabla(tipo: str) -> str:
    """De `EventoEstado` a `artefacto_evento_estado`."""
    if tipo not in TABLA_POR_TIPO:
        raise KeyError(f"{tipo!r} no es un tipo de artefacto declarado")
    partes: list[str] = []
    for letra in tipo:
        if letra.isupper() and partes:
            partes.append("_")
        partes.append(letra.lower())
    return "artefacto_" + "".join(partes)


def _check(columna: str, valores: tuple[str, ...], obligatoria: bool = False) -> str:
    lista = ", ".join(f"'{valor}'" for valor in sorted(valores))
    if obligatoria:
        return f"CHECK ({columna} IN ({lista}))"
    return f"CHECK ({columna} IS NULL OR {columna} IN ({lista}))"


def _sentencia_de_tabla(tabla: Tabla) -> str:
    nombre = nombre_de_tabla(tabla.tipo)
    lineas = [
        "  id TEXT NOT NULL PRIMARY KEY",
        "  id_obra TEXT NOT NULL REFERENCES artefacto_obra(id)",
        f"  tipo TEXT NOT NULL CHECK (tipo = '{tabla.tipo}')",
        "  cuerpo TEXT NOT NULL",
    ]
    for columna in tabla.consulta:
        linea = f"  {columna} {COLUMNAS_DE_CONSULTA[columna]}"
        if columna == "estado" and tabla.vocabulario_de_estado:
            linea += " " + _check("estado", tabla.vocabulario_de_estado)
        elif columna == "severidad":
            linea += " " + _check("severidad", SEVERIDAD)
        elif columna == "dimension":
            linea += " " + _check("dimension", DIMENSIONES)
        elif columna == "rol":
            linea += " " + _check("rol", ROLES)
        lineas.append(linea)
    for propia in tabla.propias:
        linea = f"  {propia.nombre} {propia.tipo}"
        if propia.vocabulario:
            linea += " " + _check(propia.nombre, propia.vocabulario)
        lineas.append(linea)
    if tabla.desde_migracion > MIGRACION_DE_LAS_VERSIONES:
        # Una tabla que nace despues de las versiones las lleva desde el
        # principio; a las anteriores se las anade esa migracion.
        lineas += [f"  {columna}" for columna in COLUMNAS_DE_LA_VERSION]
    lineas += [
        f"  memoria TEXT NOT NULL {_check('memoria', MEMORIA, obligatoria=True)}",
        f"  procedencia_rol TEXT {_check('procedencia_rol', ROLES)}",
        "  procedencia_tarea TEXT",
        "  procedencia_intento INT",
        "  creado_en TEXT NOT NULL",
        "  caducado_en TEXT",
    ]
    cuerpo = ",\n".join(lineas)
    return f"CREATE TABLE {nombre} (\n{cuerpo}\n) STRICT"


def _sentencias_de_indices(tabla: Tabla) -> list[str]:
    nombre = nombre_de_tabla(tabla.tipo)
    return [
        f"CREATE INDEX indice_{nombre}_{numero} ON {nombre} ({', '.join(columnas)})"
        for numero, columnas in enumerate(tabla.indices, start=1)
    ]


def _sentencias_de_disparadores(tabla: Tabla) -> list[str]:
    """No se borra nada, y lo inmutable no se toca.

    Caducar y descartar son marcas, asi que el borrado esta prohibido en toda
    tabla de artefactos. La modificacion esta prohibida en los tipos inmutables
    y en el `Borrador` que ya se acepto.
    """
    nombre = nombre_de_tabla(tabla.tipo)
    sentencias = [
        f"CREATE TRIGGER {nombre}_no_se_borra BEFORE DELETE ON {nombre} "
        "BEGIN SELECT RAISE(ABORT, 'no se borra nada: caducar y descartar son marcas'); END"
    ]
    if tabla.inmutable:
        aviso = f"{tabla.tipo} es inmutable: cambiar algo es escribir una version nueva"
        sentencias.append(
            f"CREATE TRIGGER {nombre}_es_inmutable BEFORE UPDATE ON {nombre} "
            f"BEGIN SELECT RAISE(ABORT, '{aviso}'); END"
        )
    if tabla.tipo == "Borrador":
        aviso = "un borrador aceptado es inmutable: se escribe una version nueva"
        sentencias.append(
            f"CREATE TRIGGER {nombre}_aceptado_es_inmutable BEFORE UPDATE ON {nombre} "
            f"WHEN OLD.estado = 'aceptado' BEGIN SELECT RAISE(ABORT, '{aviso}'); END"
        )
    return sentencias


# --- Tablas que no guardan artefactos --------------------------------------

OTRAS_TABLAS: tuple[str, ...] = (
    # Cache descartable, no almacen: el estado en N no se almacena, se deriva
    # plegando el log. Esta tabla existe solo para no replegar desde cero y se
    # puede vaciar entera sin perder nada (RF-25).
    """CREATE TABLE cache_estado_materializado (
  id_obra TEXT NOT NULL REFERENCES artefacto_obra(id),
  capitulo INT NOT NULL,
  cuerpo TEXT NOT NULL,
  calculado_en TEXT NOT NULL,
  PRIMARY KEY (id_obra, capitulo)
) STRICT""",
    # La unica orden del editor que no se deriva de los artefactos: detener y
    # reanudar (RF-04). Todo lo demas del avance se deriva de lo ya escrito.
    """CREATE TABLE control_de_ejecucion (
  id_obra TEXT NOT NULL PRIMARY KEY REFERENCES artefacto_obra(id),
  detenida INT NOT NULL CHECK (detenida IN (0, 1)),
  motivo TEXT,
  actualizado_en TEXT NOT NULL
) STRICT""",
    """CREATE TABLE migracion (
  numero INT NOT NULL PRIMARY KEY,
  nombre TEXT NOT NULL,
  aplicada_en TEXT NOT NULL
) STRICT""",
)


def _sentencias_de(tablas: tuple[Tabla, ...]) -> list[str]:
    sentencias: list[str] = [_sentencia_de_tabla(tabla) for tabla in tablas]
    for tabla in tablas:
        sentencias += _sentencias_de_indices(tabla)
        sentencias += _sentencias_de_disparadores(tabla)
    return sentencias


def tablas_de_la_migracion(numero: int) -> tuple[Tabla, ...]:
    return tuple(tabla for tabla in TABLAS if tabla.desde_migracion == numero)


def sentencias_iniciales() -> list[str]:
    """Todo el esquema de la migracion 1, en el orden en que se aplica."""
    return _sentencias_de(tablas_de_la_migracion(1)) + list(OTRAS_TABLAS)


def sentencias_del_recuerdo() -> list[str]:
    """La migracion 3: la tabla de `Recuerdo` y nada mas."""
    return _sentencias_de(tablas_de_la_migracion(3))


def _columnas_salvo_la_marca(tabla: Tabla) -> list[str]:
    """Todas las columnas de la tabla menos `caducado_en`."""
    return [
        "id", "id_obra", "tipo", "cuerpo",
        *tabla.consulta,
        *(propia.nombre for propia in tabla.propias),
        "memoria", "procedencia_rol", "procedencia_tarea", "procedencia_intento",
        "creado_en",
    ]


def _disparadores_que_admiten_la_marca(tabla: Tabla) -> list[str]:
    """Marcar no es modificar (D-32).

    A un inmutable, y a un `Borrador` ya aceptado, se le puede poner la marca
    de caducado: es lo unico que permite descartar un capitulo a medias sin
    borrar (RD-07). Solo esa marca, solo una vez, y nunca se quita. Cualquier
    otra columna sigue sin poder cambiar.
    """
    nombre = nombre_de_tabla(tabla.tipo)
    columnas = ", ".join(_columnas_salvo_la_marca(tabla))
    if tabla.tipo == "Borrador":
        viejo = f"{nombre}_aceptado_es_inmutable"
        aviso = "un borrador aceptado es inmutable: se escribe una version nueva"
        cuando = "WHEN OLD.estado = 'aceptado' "
    else:
        viejo = f"{nombre}_es_inmutable"
        aviso = f"{tabla.tipo} es inmutable: cambiar algo es escribir una version nueva"
        cuando = ""
    aviso_de_la_marca = f"{tabla.tipo} es inmutable: la marca de caducado no se quita"
    return [
        f"DROP TRIGGER IF EXISTS {viejo}",
        f"CREATE TRIGGER {viejo} BEFORE UPDATE OF {columnas} ON {nombre} "
        f"{cuando}BEGIN SELECT RAISE(ABORT, '{aviso}'); END",
        f"CREATE TRIGGER {nombre}_la_marca_no_se_quita BEFORE UPDATE OF caducado_en "
        f"ON {nombre} WHEN OLD.caducado_en IS NOT NULL "
        f"BEGIN SELECT RAISE(ABORT, '{aviso_de_la_marca}'); END",
    ]


def sentencias_del_punto_de_guardado() -> list[str]:
    """La migracion 6: lo que necesita volver al ultimo capitulo cerrado.

    La constancia de hasta que capitulo se audito, que es lo que dice si una
    obra ha terminado (RF-93, RF-94), y los disparadores de inmutabilidad
    rehechos para admitir la marca de caducado. Las obras que ya existian se
    dan por auditadas hasta su ultimo capitulo cerrado, para que reanudarlas
    no repita una auditoria que ya corrio.
    """
    sentencias = [
        "ALTER TABLE control_de_ejecucion ADD COLUMN auditada_hasta INT NOT NULL DEFAULT 0",
        "UPDATE control_de_ejecucion SET auditada_hasta = COALESCE(("
        "SELECT MAX(c.capitulo) FROM artefacto_capitulo AS c "
        "WHERE c.id_obra = control_de_ejecucion.id_obra AND c.estado = 'cerrado' "
        "AND c.caducado_en IS NULL), 0)",
    ]
    for tabla in TABLAS:
        if tabla.inmutable or tabla.tipo == "Borrador":
            sentencias += _disparadores_que_admiten_la_marca(tabla)
        # Descartar desde un capitulo busca por obra y capitulo en toda tabla que
        # tenga capitulo: ninguna puede quedarse recorriendose entera.
        if "capitulo" in tabla.consulta and not any(
            indice[:2] == ("id_obra", "capitulo") for indice in tabla.indices
        ):
            nombre = nombre_de_tabla(tabla.tipo)
            sentencias.append(
                f"CREATE INDEX indice_{nombre}_por_capitulo ON {nombre} (id_obra, capitulo)"
            )
    return sentencias
# --- La entrevista: el espacio anterior a la obra --------------------------
#
# No guarda artefactos: el Entrevistador no escribe ninguno (SPEC1 RF-70). Guarda
# la huella de cada pasada —lo que entro, lo que salio, lo que se descarto y su
# traza— colgando de un `id_entrevista`, igual que una obra cuelga de su
# `id_obra` (RF-79). Nada se borra, una pasada no se modifica y la entrevista
# anota una sola vez la obra que lanzo.

_NO_SE_BORRA = "SELECT RAISE(ABORT, 'no se borra nada: caducar y descartar son marcas')"

SENTENCIAS_DE_LA_ENTREVISTA: tuple[str, ...] = (
    """CREATE TABLE entrevista (
  id TEXT NOT NULL PRIMARY KEY,
  abierta_en TEXT NOT NULL,
  id_obra TEXT REFERENCES artefacto_obra(id),
  lanzada_en TEXT
) STRICT""",
    "CREATE TRIGGER entrevista_no_se_borra BEFORE DELETE ON entrevista "
    f"BEGIN {_NO_SE_BORRA}; END",
    "CREATE TRIGGER entrevista_lanza_una_sola_obra BEFORE UPDATE ON entrevista "
    "WHEN OLD.id_obra IS NOT NULL "
    "BEGIN SELECT RAISE(ABORT, 'la entrevista ya lanzo su obra'); END",
    """CREATE TABLE pasada_de_entrevista (
  id TEXT NOT NULL PRIMARY KEY,
  id_entrevista TEXT NOT NULL REFERENCES entrevista(id),
  numero INT NOT NULL,
  rol TEXT NOT NULL CHECK (rol = 'entrevistador'),
  tarea TEXT NOT NULL CHECK (tarea = 'entrevistar'),
  entrada TEXT NOT NULL,
  salida TEXT NOT NULL,
  hechos_descartados INT NOT NULL,
  contradicciones_descartadas INT NOT NULL,
  artefactos_rechazados INT NOT NULL,
  tokens_de_entrada_estimados INT,
  tokens_de_entrada_medidos INT,
  tokens_de_salida INT,
  coste REAL,
  latencia_ms INT,
  abierta_en TEXT NOT NULL,
  cerrada_en TEXT NOT NULL,
  id_obra TEXT REFERENCES artefacto_obra(id),
  UNIQUE (id_entrevista, numero)
) STRICT""",
    "CREATE TRIGGER pasada_de_entrevista_no_se_borra BEFORE DELETE ON pasada_de_entrevista "
    f"BEGIN {_NO_SE_BORRA}; END",
    "CREATE TRIGGER pasada_de_entrevista_es_inmutable BEFORE UPDATE ON pasada_de_entrevista "
    "BEGIN SELECT RAISE(ABORT, 'una pasada de entrevista es inmutable'); END",
)


def sentencias_de_la_entrevista() -> list[str]:
    """La migracion 5: el espacio de la entrevista y nada mas."""
    return list(SENTENCIAS_DE_LA_ENTREVISTA)
def sentencias_de_la_mencion() -> list[str]:
    """La migracion 4: la tabla de `Mencion` y nada mas."""
    return _sentencias_de(tablas_de_la_migracion(4))




# --- Las versiones de la obra (SPEC1 4.12) --------------------------------
#
# Ni la version ni la publicacion son artefactos: las escribe el backend, no un
# rol, igual que el control de ejecucion. Nada se borra; de una version solo
# cambia, una vez, la marca de terminada, y una publicacion no cambia nunca.

SENTENCIAS_DE_LAS_VERSIONES: tuple[str, ...] = (
    """CREATE TABLE version_de_la_obra (
  id_obra TEXT NOT NULL REFERENCES artefacto_obra(id),
  numero INT NOT NULL CHECK (numero >= 1),
  base INT,
  capitulos_cambiados TEXT NOT NULL,
  creada_en TEXT NOT NULL,
  terminada_en TEXT,
  PRIMARY KEY (id_obra, numero)
) STRICT""",
    "CREATE TRIGGER version_de_la_obra_no_se_borra BEFORE DELETE ON version_de_la_obra "
    f"BEGIN {_NO_SE_BORRA}; END",
    "CREATE TRIGGER version_de_la_obra_es_inmutable BEFORE UPDATE OF id_obra, numero, base, "
    "capitulos_cambiados, creada_en ON version_de_la_obra "
    "BEGIN SELECT RAISE(ABORT, 'una version es inmutable: rehacer es abrir otra'); END",
    "CREATE TRIGGER version_de_la_obra_termina_una_vez BEFORE UPDATE OF terminada_en "
    "ON version_de_la_obra WHEN OLD.terminada_en IS NOT NULL "
    "BEGIN SELECT RAISE(ABORT, 'una version termina una sola vez'); END",
    """CREATE TABLE publicacion_de_version (
  id INTEGER PRIMARY KEY,
  id_obra TEXT NOT NULL,
  numero INT NOT NULL,
  publicada_en TEXT NOT NULL,
  FOREIGN KEY (id_obra, numero) REFERENCES version_de_la_obra (id_obra, numero)
) STRICT""",
    "CREATE INDEX indice_publicacion_de_version ON publicacion_de_version (id_obra, id)",
    "CREATE TRIGGER publicacion_de_version_no_se_borra BEFORE DELETE ON publicacion_de_version "
    f"BEGIN {_NO_SE_BORRA}; END",
    "CREATE TRIGGER publicacion_de_version_es_inmutable "
    "BEFORE UPDATE ON publicacion_de_version "
    "BEGIN SELECT RAISE(ABORT, 'una publicacion es inmutable: se publica otra vez'); END",
    # Las obras que ya existian son su version 1, terminada si ya consta su
    # auditoria de cierre. La primera version no tiene base, y por eso no tiene
    # capitulos cambiados respecto de ninguna.
    "INSERT INTO version_de_la_obra (id_obra, numero, base, capitulos_cambiados, creada_en, "
    "terminada_en) SELECT o.id, 1, NULL, '[]', o.creado_en, CASE WHEN c.auditada_hasta >= "
    "COALESCE(json_extract(o.cuerpo, '$.capitulos_objetivo'), 1) "
    "THEN strftime('%Y-%m-%dT%H:%M:%S+00:00', 'now') END "
    "FROM artefacto_obra AS o LEFT JOIN control_de_ejecucion AS c ON c.id_obra = o.id",
    # La cache del estado pasa a ser por version: rehacer la releva en vez de
    # borrarla (D-44). SQLite no cambia una clave primaria en sitio, asi que se
    # rehace la tabla; lo que habia es de la version 1.
    """CREATE TABLE cache_estado_por_version (
  id_obra TEXT NOT NULL REFERENCES artefacto_obra(id),
  version_de_obra INT NOT NULL,
  capitulo INT NOT NULL,
  cuerpo TEXT NOT NULL,
  calculado_en TEXT NOT NULL,
  relevado_por INT,
  PRIMARY KEY (id_obra, version_de_obra, capitulo)
) STRICT""",
    "INSERT INTO cache_estado_por_version (id_obra, version_de_obra, capitulo, cuerpo, "
    "calculado_en) SELECT id_obra, 1, capitulo, cuerpo, calculado_en "
    "FROM cache_estado_materializado",
    "DROP TABLE cache_estado_materializado",
    "ALTER TABLE cache_estado_por_version RENAME TO cache_estado_materializado",
    "CREATE INDEX indice_cache_estado_materializado ON cache_estado_materializado "
    "(id_obra, capitulo)",
)


def _versiones_en_la_tabla(tabla: Tabla) -> list[str]:
    """Las dos columnas de la version y sus dos reglas (RD-21).

    La version en que nacio una fila no cambia nunca. La que la relevo se pone
    una sola vez, y solo junto con la marca de caducado: marcar no es modificar
    (D-32). Los disparadores de inmutabilidad anteriores nombran sus columnas,
    asi que estas dos no los disparan: las guardan estos.
    """
    nombre = nombre_de_tabla(tabla.tipo)
    return [
        *(f"ALTER TABLE {nombre} ADD COLUMN {columna}" for columna in COLUMNAS_DE_LA_VERSION),
        f"CREATE TRIGGER {nombre}_la_version_no_cambia BEFORE UPDATE OF version_de_obra "
        f"ON {nombre} WHEN NEW.version_de_obra IS NOT OLD.version_de_obra "
        "BEGIN SELECT RAISE(ABORT, 'la version en que nacio una fila no cambia'); END",
        f"CREATE TRIGGER {nombre}_se_releva_una_vez BEFORE UPDATE OF relevado_por "
        f"ON {nombre} WHEN OLD.relevado_por IS NOT NULL OR NEW.caducado_en IS NULL "
        "BEGIN SELECT RAISE(ABORT, 'el relevo se marca una vez y junto al caducado'); END",
    ]


def sentencias_de_las_versiones() -> list[str]:
    """La migracion 7: versiones, publicaciones y las dos marcas en toda tabla.

    Recorre todas las tablas de artefactos que ya existen, asi que va detras de
    cualquier migracion que cree una.
    """
    sentencias = list(SENTENCIAS_DE_LAS_VERSIONES)
    for tabla in TABLAS:
        if tabla.desde_migracion <= MIGRACION_DE_LAS_VERSIONES:
            sentencias += _versiones_en_la_tabla(tabla)
    return sentencias


# --- Lo vetado: la lista global y el registro de policy (SPEC1 4.14) -------
#
# Ninguna de las dos es un artefacto: no las escribe ningun rol. La lista global
# es de la instalacion y no cuelga de ninguna obra (RD-26); el registro es la
# constancia de lo que hizo `policy` y, como la `Traza`, no se caduca ni se
# releva (RD-27). Ninguna de las dos se borra ni se modifica.

# La lista de serie (RF-131, D-51). Corta a proposito: fuera quedan palabras con
# un sentido historico o inocente que la normalizacion confundiria. Ampliarla es
# anadir una migracion, no reescribir esta.
TERMINOS_VETADOS_DE_SERIE: tuple[str, ...] = (
    "cabrón",
    "cojones",
    "coño",
    "estúpido",
    "follar",
    "gilipollas",
    "hijo de puta",
    "hijoputa",
    "imbécil",
    "joder",
    "malparido",
    "marica",
    "maricón",
    "mierda",
    "puta",
    "subnormal",
    "sudaca",
)


def _literal(texto: str) -> str:
    return "'" + texto.replace("'", "''") + "'"


def sentencias_de_lo_vetado() -> list[str]:
    """La migracion 8: la lista global sembrada y el registro de policy."""
    return [
        """CREATE TABLE termino_vetado_global (
  termino TEXT NOT NULL PRIMARY KEY,
  incorporado_en TEXT NOT NULL
) STRICT""",
        "CREATE TRIGGER termino_vetado_global_no_se_borra BEFORE DELETE "
        f"ON termino_vetado_global BEGIN {_NO_SE_BORRA}; END",
        "CREATE TRIGGER termino_vetado_global_es_inmutable BEFORE UPDATE "
        "ON termino_vetado_global "
        "BEGIN SELECT RAISE(ABORT, 'la lista global es inmutable: se amplia con otra "
        "migracion'); END",
        *(
            "INSERT INTO termino_vetado_global (termino, incorporado_en) "
            f"VALUES ({_literal(termino)}, strftime('%Y-%m-%dT%H:%M:%S+00:00', 'now'))"
            for termino in TERMINOS_VETADOS_DE_SERIE
        ),
        f"""CREATE TABLE decision_de_policy (
  id INTEGER PRIMARY KEY,
  id_obra TEXT NOT NULL REFERENCES artefacto_obra(id),
  id_traza TEXT NOT NULL REFERENCES artefacto_traza(id),
  decision TEXT NOT NULL {_check('decision', DECISION_DE_POLICY, obligatoria=True)},
  nivel TEXT NOT NULL {_check('nivel', NIVEL_DE_VETO, obligatoria=True)},
  termino TEXT NOT NULL,
  encontrado TEXT NOT NULL,
  registrada_en TEXT NOT NULL
) STRICT""",
        "CREATE INDEX indice_decision_de_policy ON decision_de_policy (id_obra, id)",
        "CREATE TRIGGER decision_de_policy_no_se_borra BEFORE DELETE ON decision_de_policy "
        f"BEGIN {_NO_SE_BORRA}; END",
        "CREATE TRIGGER decision_de_policy_es_inmutable BEFORE UPDATE ON decision_de_policy "
        "BEGIN SELECT RAISE(ABORT, 'el registro de policy es de solo anadir'); END",
    ]


assert {t.tipo for t in TABLAS} == set(
    TIPOS_DE_LA_CAPA_OBRA + TIPOS_DE_LA_CAPA_MUNDO + TIPOS_DE_LA_CAPA_PRODUCCION
), "El esquema y el censo de tipos de artefacto no dicen lo mismo"
