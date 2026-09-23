"""El esquema del almacen: una tabla por tipo de artefacto.

El esquema espeja las tres capas —Obra, Mundo y Produccion— mas la `Traza`, y
toda fila cuelga de un `id_obra`. La capa Obra referencia la capa Mundo por
`id` y nunca la duplica; la de Produccion referencia a las dos y ninguna la
referencia a ella. Eso se impone aqui con claves foraneas, no con buena
voluntad.

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
    DIMENSIONES,
    ESTADO_DE_COMPROMISO,
    ESTADO_DE_PRODUCCION,
    MEMORIA,
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
    """Lo que hay que saber de un tipo de artefacto para darle tabla."""

    tipo: str
    capa: str
    memoria: str
    consulta: tuple[str, ...] = ()
    vocabulario_de_estado: tuple[str, ...] | None = None
    inmutable: bool = False
    propias: tuple[Columna, ...] = ()
    indices: tuple[tuple[str, ...], ...] = ()
    notas: str = ""


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
    # --- Capa 2, el mundo: de que habla el texto --------------------------
    # Las fichas del Constructor de mundo se traen por `id` desde el contrato de
    # la escena, no por consulta: de ahi que no lleven mas columnas que las
    # comunes. Lo que recoge el Documentalista, en cambio, se recupera por
    # escena y se filtra por fecha y lugar, asi que lleva capitulo y escena.
    *(
        Tabla(tipo, "mundo", "obra")
        for tipo in TIPOS_DE_LA_CAPA_MUNDO
        if tipo not in DOCUMENTALES
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


def sentencias_iniciales() -> list[str]:
    """Todo el esquema de la migracion 1, en el orden en que se aplica."""
    sentencias: list[str] = [_sentencia_de_tabla(tabla) for tabla in TABLAS]
    for tabla in TABLAS:
        sentencias += _sentencias_de_indices(tabla)
        sentencias += _sentencias_de_disparadores(tabla)
    return sentencias + list(OTRAS_TABLAS)


assert {t.tipo for t in TABLAS} == set(
    TIPOS_DE_LA_CAPA_OBRA + TIPOS_DE_LA_CAPA_MUNDO + TIPOS_DE_LA_CAPA_PRODUCCION
), "El esquema y el censo de tipos de artefacto no dicen lo mismo"
