"""La unica puerta de lectura y escritura del almacen.

Se declara como interfaz estrecha, con nombres de dominio —guardar borrador,
leer capitulo, anadir eventos, listar criticas abiertas—, no como pasamanos de
SQL ni como ORM. Nadie fuera de este paquete abre la base.

Dos reglas gobiernan todo lo de abajo. La primera: **no se borra nada**;
caducar y descartar son marcas, y el `DELETE` esta prohibido por disparador en
toda tabla de artefactos. La segunda: **lo caducado deja de servirse a
cualquier proyeccion**, asi que toda lectura filtra por `caducado_en IS NULL`
salvo que se pida lo contrario a proposito.
"""

import json
import sqlite3
import threading
import uuid
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from novela.almacen import esquema
from novela.almacen.conexion import abrir, escritura
from novela.almacen.esquema import TABLA_POR_TIPO, nombre_de_tabla
from novela.vocabularios import HECHOS_DE_LA_BIBLIA, MEMORIA

# Prefijo del identificador opaco de cada tipo. Un `id` dice de que es sin
# tener que abrirlo, que es lo que hace legible una `Critica` cuyo `objeto` es
# `esc_0007`.
PREFIJOS: dict[str, str] = {
    "Obra": "obr",
    "Parte": "par",
    "Capitulo": "cap",
    "Escena": "esc",
    "Beat": "bea",
    "Parrafo": "prf",
    "Compromiso": "cmp",
    "Mencion": "men",
    "Personaje": "per",
    "Lugar": "lug",
    "Evento": "evn",
    "Objeto": "obj",
    "Faccion": "fac",
    "Practica": "pra",
    "Concepto": "cnc",
    "RegistroLinguistico": "reg",
    "Fuente": "fue",
    "Recuerdo": "rcd",
    "Agente": "age",
    "Tarea": "tar",
    "Plan": "pla",
    "Borrador": "bor",
    "Critica": "cri",
    "Revision": "rev",
    "Decision": "dec",
    "EventoEstado": "evt",
    "ResumenCapitulo": "res",
    "Traza": "trz",
}


class ArtefactoRechazado(Exception):
    """El almacen no admite el artefacto tal como viene.

    Campo obligatorio del envoltorio ausente o valor fuera de vocabulario
    controlado. Quien la recoge la convierte en `Critica` bloqueante cuyo objeto
    es el artefacto, no el texto (RF-23).
    """


class EscrituraProhibida(Exception):
    """Se ha intentado cambiar algo inmutable o borrar algo que no se borra."""


def nuevo_identificador(prefijo: str) -> str:
    """Un `id` opaco con su prefijo de tres letras."""
    return f"{prefijo}_{uuid.uuid4().hex[:8]}"


def nuevo_id(tipo: str) -> str:
    if tipo not in PREFIJOS:
        raise KeyError(f"{tipo!r} no es un tipo de artefacto declarado")
    return nuevo_identificador(PREFIJOS[tipo])


def ahora() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


@dataclass
class Artefacto:
    """Un artefacto listo para guardarse.

    El `cuerpo` se guarda integro tal como lo escribio el agente y el backend no
    lo reinterpreta: las demas columnas son solo por donde se consulta.
    """

    tipo: str
    cuerpo: dict[str, Any]
    id: str = ""
    id_obra: str = ""
    memoria: str = ""
    capitulo: int | None = None
    escena: str | None = None
    estado: str | None = None
    severidad: str | None = None
    dimension: str | None = None
    rol: str | None = None
    orden: int | None = None
    version: int | None = None
    procedencia_rol: str | None = None
    procedencia_tarea: str | None = None
    procedencia_intento: int | None = None
    creado_en: str = ""
    caducado_en: str | None = None
    version_de_obra: int | None = None
    relevado_por: int | None = None
    propias: dict[str, Any] = field(default_factory=dict)


def _fila_a_artefacto(fila: sqlite3.Row) -> Artefacto:
    columnas = fila.keys()
    conocidas = {
        "id", "id_obra", "tipo", "cuerpo", "capitulo", "escena", "estado", "severidad",
        "dimension", "rol", "orden", "version", "memoria", "procedencia_rol",
        "procedencia_tarea", "procedencia_intento", "creado_en", "caducado_en",
        "version_de_obra", "relevado_por",
    }
    return Artefacto(
        tipo=fila["tipo"],
        cuerpo=json.loads(fila["cuerpo"]),
        id=fila["id"],
        id_obra=fila["id_obra"],
        memoria=fila["memoria"],
        capitulo=fila["capitulo"] if "capitulo" in columnas else None,
        escena=fila["escena"] if "escena" in columnas else None,
        estado=fila["estado"] if "estado" in columnas else None,
        severidad=fila["severidad"] if "severidad" in columnas else None,
        dimension=fila["dimension"] if "dimension" in columnas else None,
        rol=fila["rol"] if "rol" in columnas else None,
        orden=fila["orden"] if "orden" in columnas else None,
        version=fila["version"] if "version" in columnas else None,
        procedencia_rol=fila["procedencia_rol"],
        procedencia_tarea=fila["procedencia_tarea"],
        procedencia_intento=fila["procedencia_intento"],
        creado_en=fila["creado_en"],
        caducado_en=fila["caducado_en"],
        version_de_obra=fila["version_de_obra"] if "version_de_obra" in columnas else None,
        relevado_por=fila["relevado_por"] if "relevado_por" in columnas else None,
        propias={c: fila[c] for c in columnas if c not in conocidas},
    )


def _cuantos_borradores(
    conexion: sqlite3.Connection, id_obra: str, escena: str | None
) -> int:
    fila = conexion.execute(
        "SELECT COUNT(*) AS cuantos FROM artefacto_borrador "
        "WHERE id_obra = ? AND escena IS ?",
        (id_obra, escena),
    ).fetchone()
    return int(fila["cuantos"])


TIPO_POR_PREFIJO: dict[str, str] = {prefijo: tipo for tipo, prefijo in PREFIJOS.items()}


def _comprobar_mencion(conexion: sqlite3.Connection, artefacto: Artefacto) -> None:
    """Una `Mencion` apunta a un hecho de la biblia de su misma obra (RF-83).

    El `id` del hecho se extrae del cuerpo a su columna, que es por donde se
    consulta: no se reinterpreta nada. Lo que se comprueba es la referencia,
    como haria una clave foranea si el hecho viviera en una sola tabla.
    """
    hecho = artefacto.propias.get("hecho") or artefacto.cuerpo.get("hecho")
    if not isinstance(hecho, str) or not hecho:
        raise ArtefactoRechazado("Mencion [hecho=None]: falta el id del hecho que menciona")
    if artefacto.capitulo is None:
        raise ArtefactoRechazado(f"Mencion [hecho={hecho!r}]: falta el capitulo")
    tipo = TIPO_POR_PREFIJO.get(hecho.split("_", 1)[0])
    existe = None
    if tipo in HECHOS_DE_LA_BIBLIA:
        existe = conexion.execute(
            f"SELECT 1 FROM {nombre_de_tabla(tipo)} WHERE id = ? AND id_obra = ?",
            (hecho, artefacto.id_obra),
        ).fetchone()
    if existe is None:
        raise ArtefactoRechazado(
            f"Mencion [hecho={hecho!r}]: no es un hecho de la biblia de esta obra"
        )
    artefacto.propias["hecho"] = hecho


def _nombre_del_hecho(ficha: "Artefacto") -> str | None:
    """Un `Evento` no tiene nombre: se le conoce por su descripcion."""
    nombre = ficha.cuerpo.get("nombre") or ficha.cuerpo.get("descripcion")
    return str(nombre) if nombre is not None else None


def _nacimiento(ficha: "Artefacto | None") -> str | None:
    if ficha is None:
        return None
    fechas = ficha.cuerpo.get("fechas")
    if isinstance(fechas, dict) and fechas.get("nacimiento") is not None:
        return str(fechas["nacimiento"])
    return None


def _decisiones_de_policy(
    ganchos: dict[str, Any] | None,
) -> list[tuple[str, str, str, str]]:
    """Las filas del registro que salen del veredicto de los hooks (RF-135).

    Lo escribio el ejecutor en `ganchos`: lo que `policy` devolvio al agente en
    la sesion y lo que dejo sin pasar al final. Aqui solo se copia a filas.
    """
    if not ganchos:
        return []
    filas: list[tuple[str, str, str, str]] = []
    momentos = (("en_sesion", "devuelto_al_agente"), ("final", "intento_fallido"))
    for momento, decision in momentos:
        for dicho in ganchos.get(momento) or []:
            if not isinstance(dicho, dict) or dicho.get("gancho") != "policy":
                continue
            for hallada in dicho.get("coincidencias") or []:
                if isinstance(hallada, dict):
                    filas.append(
                        (
                            decision,
                            str(hallada.get("nivel")),
                            str(hallada.get("termino")),
                            str(hallada.get("encontrado")),
                        )
                    )
    return filas


def _version_en_curso(conexion: sqlite3.Connection, id_obra: str) -> int:
    """La ultima version de la obra, que es la unica que se produce (D-40)."""
    fila = conexion.execute(
        "SELECT COALESCE(MAX(numero), 1) AS numero FROM version_de_la_obra WHERE id_obra = ?",
        (id_obra,),
    ).fetchone()
    return int(fila["numero"])


def _visible(version: int | None, alias: str = "") -> tuple[str, dict[str, Any]]:
    """Que filas ve una version (SPEC1 RF-113).

    Sin version, lo vivo: lo que no esta caducado, que es lo que ve la version
    en curso y lo unico que lee la produccion. Con version V, lo escrito en V o
    antes que no haya relevado V ni una anterior, y que no se caduco por otro
    motivo —memoria de capitulo, capitulo a medias—: un relevo siempre lleva su
    marca, y un caducado sin relevo no lo ve ninguna version.
    """
    prefijo = f"{alias}." if alias else ""
    if version is None:
        return f"{prefijo}caducado_en IS NULL", {}
    return (
        f"{prefijo}version_de_obra <= :version_vista "
        f"AND ({prefijo}relevado_por IS NULL OR {prefijo}relevado_por > :version_vista) "
        f"AND ({prefijo}caducado_en IS NULL OR {prefijo}relevado_por IS NOT NULL)",
        {"version_vista": version},
    )


def _estado_visible(version: int | None) -> tuple[str, dict[str, Any]]:
    """Lo mismo para la cache del estado, que no se caduca: se releva o se borra."""
    if version is None:
        return "relevado_por IS NULL", {}
    return (
        "version_de_obra <= :version_vista "
        "AND (relevado_por IS NULL OR relevado_por > :version_vista)",
        {"version_vista": version},
    )


def _version_a_dict(fila: sqlite3.Row) -> dict[str, Any]:
    version = dict(fila)
    version["capitulos_cambiados"] = json.loads(version["capitulos_cambiados"])
    hecho = version.pop("cambio_hecho", None)
    tipo = version.pop("cambio_tipo", None)
    anterior = version.pop("cambio_anterior", None)
    nuevo = version.pop("cambio_nuevo", None)
    version["cambio"] = (
        {"hecho": hecho, "tipo": tipo, "anterior": anterior, "nuevo": nuevo}
        if hecho is not None
        else None
    )
    return version


# Las versiones con el cambio del lector del que nacen, si nacen de uno (RF-177).
_VERSIONES_CON_SU_CAMBIO = (
    "SELECT v.*, c.hecho AS cambio_hecho, c.tipo AS cambio_tipo, "
    "c.anterior AS cambio_anterior, c.nuevo AS cambio_nuevo "
    "FROM version_de_la_obra AS v LEFT JOIN cambio_del_lector AS c "
    "ON c.id_obra = v.id_obra AND c.version = v.numero"
)


def _campo_del_nombre(ficha: "Artefacto") -> str:
    """El campo que la lista de hechos ensena como nombre: un `Evento` no tiene
    nombre y se le conoce por su descripcion (como en `_nombre_del_hecho`)."""
    return "nombre" if ficha.cuerpo.get("nombre") is not None else "descripcion"



class VersionNoAdmitida(Exception):
    """La orden sobre una version no se puede cumplir tal como viene: rehacer
    con una version sin terminar, o publicar una que no ha terminado."""


class HechoSinMenciones(VersionNoAdmitida):
    """Ningun capitulo usa el hecho: no hay nada que reescribir (SPEC1 D-73)."""


class Almacen:
    """La puerta. Se abre una vez y se pasa a quien la necesite."""

    def __init__(self, ruta: Path | str) -> None:
        self.ruta = Path(ruta)
        self._escritor = abrir(self.ruta)
        self._turno_de_escritura = threading.Lock()
        self._locales = threading.local()
        self._lectores: list[sqlite3.Connection] = []

    @property
    def _lector(self) -> sqlite3.Connection:
        """Una conexion de lectura por hilo.

        Un solo escritor serializado, y lecturas aparte que no lo bloquean. Una
        conexion de SQLite no se comparte entre hilos que leen a la vez: la
        produccion corre en su hilo y la API contesta en el suyo, asi que cada
        uno abre la suya y WAL se encarga de que no se estorben.
        """
        conexion: sqlite3.Connection | None = getattr(self._locales, "conexion", None)
        if conexion is None:
            conexion = abrir(self.ruta)
            self._locales.conexion = conexion
            with self._turno_de_escritura:
                self._lectores.append(conexion)
        return conexion

    def soltar_lector(self) -> None:
        """Cierra el lector del hilo que llama, si lo abrio.

        Lo llama quien abre hilos de vida corta, como los de una tanda: sin
        soltarlo, cada hilo dejaria su conexion abierta hasta cerrar el almacen.
        """
        conexion: sqlite3.Connection | None = getattr(self._locales, "conexion", None)
        if conexion is None:
            return
        self._locales.conexion = None
        with self._turno_de_escritura:
            self._lectores.remove(conexion)
        conexion.close()

    def cerrar(self) -> None:
        self._escritor.close()
        for lector in self._lectores:
            lector.close()
        self._lectores.clear()

    # --- Migraciones -------------------------------------------------------

    def migrar(self) -> int:
        """Aplica las migraciones que falten y devuelve la ultima aplicada."""
        from novela.almacen.migraciones import aplicar

        with self._turno_de_escritura:
            return aplicar(self._escritor)

    # --- Escritura ---------------------------------------------------------

    def guardar(self, artefactos: Sequence[Artefacto]) -> list[str]:
        """Guarda lo que una tarea produjo: la unidad entera o nada.

        Es la unica escritura generica que existe. Lo que decide que columnas
        lleva cada artefacto es el esquema de su tipo, no quien llama.
        """
        with self._turno_de_escritura, escritura(self._escritor) as conexion:
            return [self._insertar(conexion, artefacto) for artefacto in artefactos]

    def _insertar(self, conexion: sqlite3.Connection, artefacto: Artefacto) -> str:
        tabla = TABLA_POR_TIPO.get(artefacto.tipo)
        if tabla is None:
            raise ArtefactoRechazado(f"{artefacto.tipo!r} no es un tipo de artefacto declarado")
        artefacto.id = artefacto.id or nuevo_id(artefacto.tipo)
        artefacto.creado_en = artefacto.creado_en or ahora()
        artefacto.memoria = artefacto.memoria or tabla.memoria
        if artefacto.memoria not in MEMORIA:
            raise ArtefactoRechazado(
                f"la memoria {artefacto.memoria!r} no esta en el vocabulario"
            )
        if artefacto.tipo == "Obra":
            artefacto.id_obra = artefacto.id_obra or artefacto.id
        if artefacto.tipo == "Borrador":
            artefacto.estado = artefacto.estado or "redactado"
            if artefacto.version is None:
                artefacto.version = 1 + _cuantos_borradores(
                    conexion, artefacto.id_obra, artefacto.escena
                )
        if not artefacto.id_obra:
            raise ArtefactoRechazado("todo artefacto cuelga de un id_obra")
        if artefacto.tipo == "Mencion":
            _comprobar_mencion(conexion, artefacto)

        valores: dict[str, Any] = {
            "id": artefacto.id,
            "id_obra": artefacto.id_obra,
            "tipo": artefacto.tipo,
            "cuerpo": json.dumps(artefacto.cuerpo, ensure_ascii=False),
            "memoria": artefacto.memoria,
            "procedencia_rol": artefacto.procedencia_rol,
            "procedencia_tarea": artefacto.procedencia_tarea,
            "procedencia_intento": artefacto.procedencia_intento,
            "creado_en": artefacto.creado_en,
            "caducado_en": artefacto.caducado_en,
            # Toda fila nace en la version que se esta produciendo (RF-112).
            "version_de_obra": artefacto.version_de_obra
            or _version_en_curso(conexion, artefacto.id_obra),
        }
        artefacto.version_de_obra = valores["version_de_obra"]
        for columna in tabla.consulta:
            valores[columna] = getattr(artefacto, columna)
        for propia in tabla.propias:
            if hasattr(artefacto, propia.nombre):
                valores[propia.nombre] = getattr(artefacto, propia.nombre)
            else:
                valores[propia.nombre] = artefacto.propias.get(propia.nombre)

        nombres = ", ".join(valores)
        huecos = ", ".join(f":{nombre}" for nombre in valores)
        tabla_sql = nombre_de_tabla(artefacto.tipo)
        sentencia = f"INSERT INTO {tabla_sql} ({nombres}) VALUES ({huecos})"
        try:
            conexion.execute(sentencia, valores)
        except sqlite3.IntegrityError as error:
            # El mensaje lleva los valores que se intentaron escribir porque es
            # lo unico que sirve de evidencia citable en la `Critica` que sale
            # de aqui: el texto de SQLite dice que vocabulario fallo, no con que.
            intentado = ", ".join(
                f"{columna}={valores[columna]!r}"
                for columna in ("tipo", "estado", "severidad", "dimension", "rol", "memoria")
                if columna in valores and valores[columna] is not None
            )
            raise ArtefactoRechazado(f"{artefacto.tipo} [{intentado}]: {error}") from error
        return artefacto.id

    def _actualizar(
        self, tipo: str, id_artefacto: str, cambios: dict[str, Any]
    ) -> None:
        asignaciones = ", ".join(f"{columna} = :{columna}" for columna in cambios)
        sentencia = (
            f"UPDATE {nombre_de_tabla(tipo)} SET {asignaciones} WHERE id = :id_artefacto"
        )
        with self._turno_de_escritura, escritura(self._escritor) as conexion:
            try:
                conexion.execute(sentencia, {**cambios, "id_artefacto": id_artefacto})
            except sqlite3.IntegrityError as error:
                mensaje = str(error)
                if "inmutable" in mensaje or "no se borra" in mensaje:
                    raise EscrituraProhibida(mensaje) from error
                raise ArtefactoRechazado(mensaje) from error
            except sqlite3.OperationalError as error:
                raise EscrituraProhibida(str(error)) from error

    # --- Lectura generica --------------------------------------------------

    def leer(
        self, tipo: str, id_artefacto: str, *, incluir_caducados: bool = False
    ) -> Artefacto | None:
        condicion = "" if incluir_caducados else " AND caducado_en IS NULL"
        fila = self._lector.execute(
            f"SELECT * FROM {nombre_de_tabla(tipo)} WHERE id = ?{condicion}",
            (id_artefacto,),
        ).fetchone()
        return _fila_a_artefacto(fila) if fila else None

    def listar(
        self,
        tipo: str,
        id_obra: str,
        *,
        capitulo: int | None = None,
        escena: str | None = None,
        estado: str | None = None,
        severidad: str | None = None,
        dimension: str | None = None,
        orden: str = "creado_en",
        incluir_caducados: bool = False,
        version: int | None = None,
    ) -> list[Artefacto]:
        """Lista acotada por obra, que es como se consulta siempre (RD-06).

        Sin `version`, lo vivo; con ella, lo que ve esa version (RF-113).
        """
        tabla = TABLA_POR_TIPO[tipo]
        condiciones = ["id_obra = :id_obra"]
        parametros: dict[str, Any] = {"id_obra": id_obra}
        for columna, valor in (
            ("capitulo", capitulo),
            ("escena", escena),
            ("estado", estado),
            ("severidad", severidad),
            ("dimension", dimension),
        ):
            if valor is not None:
                if columna not in tabla.consulta:
                    raise KeyError(f"{tipo} no se consulta por {columna}")
                condiciones.append(f"{columna} = :{columna}")
                parametros[columna] = valor
        if not incluir_caducados:
            visible, de_la_version = _visible(version)
            condiciones.append(visible)
            parametros |= de_la_version
        sentencia = (
            f"SELECT * FROM {nombre_de_tabla(tipo)} "
            f"WHERE {' AND '.join(condiciones)} ORDER BY {orden}"
        )
        return [_fila_a_artefacto(f) for f in self._lector.execute(sentencia, parametros)]

    # --- Obra --------------------------------------------------------------

    def crear_obra(self, cuerpo: dict[str, Any], recuerdos: list[str] | None = None) -> str:
        """Da de alta la obra. Cada obra nace en su propio espacio (RF-03).

        Los recuerdos del destinatario entran en la misma transaccion que la
        obra: o nace entera o no nace. Se guardan como `Recuerdo`, que ningun
        rol del censo escribe (RF-07).
        """
        with self._turno_de_escritura, escritura(self._escritor) as conexion:
            return self._dar_de_alta(conexion, cuerpo, recuerdos)

    def _dar_de_alta(
        self, conexion: sqlite3.Connection, cuerpo: dict[str, Any], recuerdos: list[str] | None
    ) -> str:
        id_obra = self._insertar(conexion, Artefacto(tipo="Obra", cuerpo=cuerpo))
        for orden, texto in enumerate(recuerdos or [], start=1):
            self._insertar(
                conexion,
                Artefacto(
                    tipo="Recuerdo",
                    id_obra=id_obra,
                    cuerpo={"orden": orden, "texto": texto},
                ),
            )
        conexion.execute(
            "INSERT INTO control_de_ejecucion (id_obra, detenida, actualizado_en) "
            "VALUES (?, 0, ?)",
            (id_obra, ahora()),
        )
        # La obra nace con su version 1, que no sale de ninguna (RF-110).
        conexion.execute(
            "INSERT INTO version_de_la_obra (id_obra, numero, base, capitulos_cambiados, "
            "creada_en) VALUES (?, 1, NULL, '[]', ?)",
            (id_obra, ahora()),
        )
        return id_obra

    def listar_recuerdos(self, id_obra: str) -> list[Artefacto]:
        return self.listar("Recuerdo", id_obra)

    def leer_obra(self, id_obra: str) -> Artefacto | None:
        return self.leer("Obra", id_obra)

    def listar_obras(self) -> list[Artefacto]:
        """De la mas reciente a la mas antigua (SPEC1 RF-204). El alta tiene
        resolucion de segundos: dos del mismo segundo se desempatan por el orden
        en que se insertaron."""
        filas = self._lector.execute(
            "SELECT * FROM artefacto_obra WHERE caducado_en IS NULL "
            "ORDER BY creado_en DESC, rowid DESC"
        )
        return [_fila_a_artefacto(f) for f in filas]

    # --- Entrevista: el espacio anterior a la obra ------------------------

    def abrir_entrevista(self) -> str:
        """Abre el espacio de una entrevista. Todavia no hay obra (SPEC1 D-24)."""
        id_entrevista = nuevo_identificador("ent")
        with self._turno_de_escritura, escritura(self._escritor) as conexion:
            conexion.execute(
                "INSERT INTO entrevista (id, abierta_en) VALUES (?, ?)",
                (id_entrevista, ahora()),
            )
        return id_entrevista

    def leer_entrevista(self, id_entrevista: str) -> dict[str, Any] | None:
        fila = self._lector.execute(
            "SELECT id, abierta_en, id_obra, lanzada_en FROM entrevista WHERE id = ?",
            (id_entrevista,),
        ).fetchone()
        return dict(fila) if fila else None

    def registrar_pasada(
        self,
        id_entrevista: str,
        *,
        entrada: dict[str, Any],
        salida: dict[str, Any],
        descartes: dict[str, int],
        traza: dict[str, Any],
        alta: tuple[dict[str, Any], list[str]] | None = None,
    ) -> tuple[int, str | None]:
        """Deja la huella de una pasada y, si el brief quedo completo, lanza la obra.

        Todo en la misma transaccion: la pasada, la `Obra`, sus `Recuerdo` y la
        marca de la entrevista se escriben enteras o no se escribe nada. Una
        entrevista que ya lanzo su obra no admite otra pasada (SPEC1 RF-78).
        Devuelve el numero de la pasada y el `id_obra`, si la lanzo.
        """
        with self._turno_de_escritura, escritura(self._escritor) as conexion:
            entrevista = conexion.execute(
                "SELECT id_obra FROM entrevista WHERE id = ?", (id_entrevista,)
            ).fetchone()
            if entrevista is None:
                raise KeyError(f"no hay ninguna entrevista {id_entrevista}")
            if entrevista["id_obra"] is not None:
                raise EscrituraProhibida(
                    f"la entrevista {id_entrevista} ya lanzo la obra {entrevista['id_obra']}"
                )
            numero = 1 + int(
                conexion.execute(
                    "SELECT COUNT(*) AS cuantas FROM pasada_de_entrevista "
                    "WHERE id_entrevista = ?",
                    (id_entrevista,),
                ).fetchone()["cuantas"]
            )
            id_obra = self._dar_de_alta(conexion, *alta) if alta is not None else None
            conexion.execute(
                "INSERT INTO pasada_de_entrevista (id, id_entrevista, numero, rol, tarea, "
                "entrada, salida, hechos_descartados, contradicciones_descartadas, "
                "artefactos_rechazados, tokens_de_entrada_estimados, "
                "tokens_de_entrada_medidos, tokens_de_salida, coste, latencia_ms, "
                "abierta_en, cerrada_en, id_obra) VALUES (?, ?, ?, 'entrevistador', "
                "'entrevistar', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    nuevo_identificador("pas"),
                    id_entrevista,
                    numero,
                    json.dumps(entrada, ensure_ascii=False),
                    json.dumps(salida, ensure_ascii=False),
                    descartes.get("hechos", 0),
                    descartes.get("contradicciones", 0),
                    descartes.get("artefactos", 0),
                    traza.get("tokens_de_entrada_estimados"),
                    traza.get("tokens_de_entrada_medidos"),
                    traza.get("tokens_de_salida"),
                    traza.get("coste"),
                    traza.get("latencia_ms"),
                    traza["abierta_en"],
                    traza.get("cerrada_en") or ahora(),
                    id_obra,
                ),
            )
            if id_obra is not None:
                conexion.execute(
                    "UPDATE entrevista SET id_obra = ?, lanzada_en = ? WHERE id = ?",
                    (id_obra, ahora(), id_entrevista),
                )
        return numero, id_obra

    def listar_pasadas(self, id_entrevista: str) -> list[dict[str, Any]]:
        filas = self._lector.execute(
            "SELECT * FROM pasada_de_entrevista WHERE id_entrevista = ? ORDER BY numero",
            (id_entrevista,),
        )
        pasadas = []
        for fila in filas:
            pasada = dict(fila)
            pasada["entrada"] = json.loads(pasada["entrada"])
            pasada["salida"] = json.loads(pasada["salida"])
            pasadas.append(pasada)
        return pasadas

    # --- Capitulo ----------------------------------------------------------

    def leer_capitulo(
        self, id_obra: str, numero: int, *, version: int | None = None
    ) -> dict[str, Any]:
        """Todo lo que hay de un capitulo: plan, escenas, borradores y criticas."""
        capitulos = self.listar("Capitulo", id_obra, capitulo=numero, version=version)
        return {
            "capitulo": capitulos[0] if capitulos else None,
            "plan": next(
                iter(self.listar("Plan", id_obra, capitulo=numero, version=version)), None
            ),
            "escenas": self.listar(
                "Escena", id_obra, capitulo=numero, orden="orden", version=version
            ),
            "borradores": self.listar("Borrador", id_obra, capitulo=numero, version=version),
            "criticas": self.listar("Critica", id_obra, capitulo=numero, version=version),
        }

    def marcar_capitulo(self, id_capitulo: str, estado: str) -> None:
        self._actualizar("Capitulo", id_capitulo, {"estado": estado})

    # --- Borradores --------------------------------------------------------

    def guardar_borrador(self, borrador: Artefacto) -> str:
        """Guarda un borrador candidato, con su numero de version."""
        if borrador.tipo != "Borrador":
            raise ArtefactoRechazado("guardar_borrador solo guarda borradores")
        return self.guardar([borrador])[0]

    def borrador_vigente(
        self, id_obra: str, escena: str, *, version: int | None = None
    ) -> Artefacto | None:
        """El ultimo borrador vivo de una escena: el aceptado, si lo hay."""
        visible, parametros = _visible(version)
        fila = self._lector.execute(
            "SELECT * FROM artefacto_borrador WHERE id_obra = :id_obra AND escena = :escena "
            f"AND estado <> 'descartado' AND {visible} "
            "ORDER BY version DESC LIMIT 1",
            {"id_obra": id_obra, "escena": escena} | parametros,
        ).fetchone()
        return _fila_a_artefacto(fila) if fila else None

    def aceptar_borrador(self, id_borrador: str) -> None:
        """Acepta el borrador y lo pasa a memoria de obra: a partir de aqui es
        inmutable y es lo unico que se indexa y se sirve como manuscrito."""
        self._actualizar("Borrador", id_borrador, {"estado": "aceptado", "memoria": "obra"})

    def descartar_borrador(self, id_borrador: str) -> None:
        self._actualizar("Borrador", id_borrador, {"estado": "descartado"})

    def manuscrito_aceptado(
        self, id_obra: str, *, version: int | None = None
    ) -> list[Artefacto]:
        """Solo el texto aceptado, en orden (RF-50), de la version pedida."""
        visible, parametros = _visible(version, "b")
        filas = self._lector.execute(
            "SELECT b.* FROM artefacto_borrador AS b "
            "JOIN artefacto_escena AS e ON e.id = b.escena "
            f"WHERE b.id_obra = :id_obra AND b.estado = 'aceptado' AND {visible} "
            "ORDER BY b.capitulo, e.orden",
            {"id_obra": id_obra} | parametros,
        )
        return [_fila_a_artefacto(f) for f in filas]

    # --- Criticas ----------------------------------------------------------

    def guardar_critica(self, critica: Artefacto) -> str:
        if critica.tipo != "Critica":
            raise ArtefactoRechazado("guardar_critica solo guarda criticas")
        critica.estado = critica.estado or "abierta"
        return self.guardar([critica])[0]

    def listar_criticas_abiertas(
        self,
        id_obra: str,
        *,
        escena: str | None = None,
        severidad: str | None = None,
        version: int | None = None,
    ) -> list[Artefacto]:
        return self.listar(
            "Critica",
            id_obra,
            escena=escena,
            estado="abierta",
            severidad=severidad,
            version=version,
        )

    def resolver_critica(self, id_critica: str, estado: str) -> None:
        """Atendida, rechazada con motivo o descartada por falta de evidencia."""
        if estado not in esquema.ESTADO_DE_CRITICA:
            raise ArtefactoRechazado(f"{estado!r} no es un estado de critica")
        self._actualizar("Critica", id_critica, {"estado": estado})

    # --- La biblia: en que capitulos se usa cada hecho ---------------------

    def capitulos_de_uso(
        self, id_obra: str, *, version: int | None = None
    ) -> dict[str, list[int]]:
        """En que capitulos se usa cada hecho. Se deriva, no se guarda (RF-84).

        Una mencion repetida no duplica el capitulo.
        """
        visible, parametros = _visible(version)
        filas = self._lector.execute(
            "SELECT DISTINCT hecho, capitulo FROM artefacto_mencion "
            f"WHERE id_obra = :id_obra AND {visible} ORDER BY hecho, capitulo",
            {"id_obra": id_obra} | parametros,
        )
        usos: dict[str, list[int]] = {}
        for fila in filas:
            usos.setdefault(fila["hecho"], []).append(int(fila["capitulo"]))
        return usos

    def hechos_de_la_biblia(
        self,
        id_obra: str,
        *,
        tipo: str | None = None,
        licencia: str | None = None,
        version: int | None = None,
    ) -> list[dict[str, Any]]:
        """Cada hecho con su tipo, nombre, licencia y capitulos de uso (RF-87)."""
        if tipo is not None and tipo not in HECHOS_DE_LA_BIBLIA:
            raise KeyError(f"{tipo!r} no es un hecho de la biblia")
        usos = self.capitulos_de_uso(id_obra, version=version)
        hechos: list[dict[str, Any]] = []
        for tipo_de_hecho in (tipo,) if tipo else HECHOS_DE_LA_BIBLIA:
            for ficha in self.listar(tipo_de_hecho, id_obra, version=version):
                if licencia is not None and ficha.cuerpo.get("licencia") != licencia:
                    continue
                hechos.append(
                    {
                        "id": ficha.id,
                        "tipo": ficha.tipo,
                        "nombre": _nombre_del_hecho(ficha),
                        "licencia": ficha.cuerpo.get("licencia"),
                        "capitulos": usos.get(ficha.id, []),
                    }
                )
        return hechos

    def cronologia(self, id_obra: str, *, version: int | None = None) -> list[dict[str, Any]]:
        """Los sucesos de la obra en orden, con quien estaba presente (RF-86).

        Es una vista, no una tabla: una fila por `EventoEstado` y por `Evento`
        del mundo. Copia lo escrito y no calcula fechas ni edades; ordenar por
        la fecha escrita no es aritmetica de calendario.
        """
        personajes = {
            ficha.id: ficha for ficha in self.listar("Personaje", id_obra, version=version)
        }
        # Un presente de un capitulo compartido puede apuntar a una ficha que un
        # cambio del lector relevo: se sigue su sustituta, por `id` (RF-177).
        sustituidas = self.fichas_sustituidas(
            id_obra, version if version is not None else self.version_en_curso(id_obra)
        )

        def resolver(identificador: str) -> Artefacto | None:
            vistos: set[str] = set()
            while identificador not in personajes and identificador in sustituidas:
                if identificador in vistos:
                    break
                vistos.add(identificador)
                identificador = sustituidas[identificador]
            return personajes.get(identificador)

        def presentes(identificadores: Any) -> list[dict[str, Any]]:
            if not isinstance(identificadores, list):
                return []
            filas = []
            for identificador in identificadores:
                ficha = resolver(identificador) if isinstance(identificador, str) else None
                filas.append(
                    {
                        "id": identificador,
                        "nombre": _nombre_del_hecho(ficha) if ficha else None,
                        "nacimiento": _nacimiento(ficha),
                    }
                )
            return filas

        sucesos: list[dict[str, Any]] = []
        for evento in self.listar("EventoEstado", id_obra, orden="capitulo", version=version):
            cuerpo = evento.cuerpo
            sucesos.append(
                {
                    "origen": "evento_de_estado",
                    "id": evento.id,
                    "capitulo": evento.capitulo,
                    "suceso": cuerpo.get("tipo_de_evento"),
                    "momento": cuerpo.get("fecha_resultante"),
                    "lugar": cuerpo.get("lugar_resultante"),
                    "presentes": presentes(cuerpo.get("presentes")),
                }
            )
        for evento in self.listar("Evento", id_obra, version=version):
            cuerpo = evento.cuerpo
            sucesos.append(
                {
                    "origen": "evento_del_mundo",
                    "id": evento.id,
                    "capitulo": evento.capitulo,
                    "suceso": _nombre_del_hecho(evento),
                    "momento": cuerpo.get("momento"),
                    "lugar": cuerpo.get("lugar"),
                    "presentes": presentes(cuerpo.get("participantes")),
                }
            )
        sucesos.sort(
            key=lambda s: (s["momento"] is None, str(s["momento"] or ""), s["capitulo"] or 0)
        )
        return sucesos

    # --- Log de estado y su pliegue ---------------------------------------

    def anadir_eventos_de_estado(self, eventos: Sequence[Artefacto]) -> list[str]:
        """Anade los `EventoEstado` de un capitulo. El log es de solo anadir."""
        for evento in eventos:
            if evento.tipo != "EventoEstado":
                raise ArtefactoRechazado("aqui solo entran EventoEstado")
        return self.guardar(eventos)

    def eventos_del_capitulo(self, id_obra: str, capitulo: int) -> list[Artefacto]:
        return self.listar("EventoEstado", id_obra, capitulo=capitulo)

    def materializar_estado(self, id_obra: str, capitulo: int, cuerpo: dict[str, Any]) -> None:
        """Guarda el estado en N como cache descartable, no como almacen."""
        with self._turno_de_escritura, escritura(self._escritor) as conexion:
            _materializar(conexion, id_obra, capitulo, cuerpo)

    def estado_en(
        self, id_obra: str, capitulo: int, *, version: int | None = None
    ) -> dict[str, Any] | None:
        visible, parametros = _estado_visible(version)
        fila = self._lector.execute(
            "SELECT cuerpo FROM cache_estado_materializado "
            f"WHERE id_obra = :id_obra AND capitulo = :capitulo AND {visible}",
            {"id_obra": id_obra, "capitulo": capitulo} | parametros,
        ).fetchone()
        return json.loads(fila["cuerpo"]) if fila else None

    def descartar_estados_desde(self, id_obra: str, capitulo: int) -> int:
        """Regenerar el capitulo N descarta los estados de N en adelante.

        Se borra de verdad porque esto es cache: el estado no se almacena, se
        deriva, y lo que se descarta aqui se vuelve a plegar hacia delante.
        """
        with self._turno_de_escritura, escritura(self._escritor) as conexion:
            cursor = conexion.execute(
                "DELETE FROM cache_estado_materializado "
                "WHERE id_obra = ? AND capitulo >= ? AND relevado_por IS NULL",
                (id_obra, capitulo),
            )
            return cursor.rowcount

    # --- Memoria -----------------------------------------------------------

    def caducar_memoria_de_capitulo(self, id_obra: str, capitulo: int) -> int:
        """Retira la memoria de capitulo: lo caducado deja de servirse.

        Lo ejecuta el Archivero como paso del guion. No borra: marca. Y no se
        lleva por delante lo que sigue abierto: una `Critica` que nadie atendio
        es justamente la anotacion con la que el capitulo se cierra marcado
        (RF-33), asi que sobrevive al cierre.
        """
        with self._turno_de_escritura, escritura(self._escritor) as conexion:
            return _caducar_memoria(conexion, id_obra, capitulo)

    # --- Punto de guardado (SPEC1 4.10) -----------------------------------

    def cerrar_capitulo(
        self,
        id_obra: str,
        capitulo: int,
        lotes: Sequence[Sequence[Artefacto]],
        estado_en_n: dict[str, Any] | None,
        al_rechazar: Callable[[int, ArtefactoRechazado], Artefacto],
    ) -> list[int]:
        """El punto de guardado: cerrar el capitulo N en una sola transaccion.

        Entran a la vez lo que devolvieron `plegar` y `destilar`, el estado en N,
        la marca `cerrado` y la retirada de la memoria de capitulo (RF-90).
        Antes del commit no existe nada del cierre; despues existe entero. Un
        lote malformado se deshace solo y en su lugar entra lo que `al_rechazar`
        devuelva, que es la `Critica` de RF-23. Devuelve los lotes rechazados.
        """
        with self._turno_de_escritura, escritura(self._escritor) as conexion:
            rechazados = self._insertar_lotes(conexion, lotes, al_rechazar)
            if estado_en_n is not None:
                _materializar(conexion, id_obra, capitulo, estado_en_n)
            conexion.execute(
                "UPDATE artefacto_capitulo SET estado = 'cerrado' "
                "WHERE id_obra = ? AND capitulo = ? AND caducado_en IS NULL",
                (id_obra, capitulo),
            )
            _caducar_memoria(conexion, id_obra, capitulo)
        return rechazados

    def guardar_auditoria(
        self,
        id_obra: str,
        hasta: int,
        lotes: Sequence[Sequence[Artefacto]],
        al_rechazar: Callable[[int, ArtefactoRechazado], Artefacto],
        *,
        de_cierre: bool = False,
    ) -> list[int]:
        """Las criticas de `auditar` y la constancia de hasta donde se audito,
        juntas o ninguna (RF-94). La de cierre termina ademas la version en
        curso, en la misma transaccion (RF-110)."""
        with self._turno_de_escritura, escritura(self._escritor) as conexion:
            rechazados = self._insertar_lotes(conexion, lotes, al_rechazar)
            conexion.execute(
                "UPDATE control_de_ejecucion SET auditada_hasta = MAX(auditada_hasta, ?), "
                "actualizado_en = ? WHERE id_obra = ?",
                (hasta, ahora(), id_obra),
            )
            if de_cierre:
                conexion.execute(
                    "UPDATE version_de_la_obra SET terminada_en = ? "
                    "WHERE id_obra = ? AND numero = ? AND terminada_en IS NULL",
                    (ahora(), id_obra, _version_en_curso(conexion, id_obra)),
                )
        return rechazados

    def _insertar_lotes(
        self,
        conexion: sqlite3.Connection,
        lotes: Sequence[Sequence[Artefacto]],
        al_rechazar: Callable[[int, ArtefactoRechazado], Artefacto],
    ) -> list[int]:
        """Cada lote es lo que devolvio una tarea: entra entero o no entra."""
        rechazados: list[int] = []
        for numero, lote in enumerate(lotes):
            conexion.execute("SAVEPOINT lote")
            try:
                for artefacto in lote:
                    self._insertar(conexion, artefacto)
            except ArtefactoRechazado as rechazo:
                conexion.execute("ROLLBACK TO lote")
                conexion.execute("RELEASE lote")
                self._insertar(conexion, al_rechazar(numero, rechazo))
                rechazados.append(numero)
                continue
            conexion.execute("RELEASE lote")
        return rechazados

    def auditada_hasta(self, id_obra: str) -> int:
        """Hasta que capitulo consta auditada la obra. Cero si nunca."""
        fila = self._lector.execute(
            "SELECT auditada_hasta FROM control_de_ejecucion WHERE id_obra = ?", (id_obra,)
        ).fetchone()
        return int(fila["auditada_hasta"]) if fila else 0

    def ultimo_capitulo_cerrado(self, id_obra: str) -> int:
        """El ultimo punto de guardado de la obra. Cero si no hay ninguno."""
        fila = self._lector.execute(
            "SELECT COALESCE(MAX(capitulo), 0) AS ultimo FROM artefacto_capitulo "
            "WHERE id_obra = ? AND estado = 'cerrado' AND caducado_en IS NULL",
            (id_obra,),
        ).fetchone()
        return int(fila["ultimo"])

    def descartar_desde(self, id_obra: str, capitulo: int) -> int:
        """Descarta todo lo que cuelga del capitulo N en adelante (RF-91).

        Es lo que queda a medias al volver al punto de guardado: se caduca, no se
        borra (RD-07), incluidos los inmutables, a los que se les admite la marca
        y solo la marca (D-32). La `Traza` no se toca: es el registro de lo que
        paso, tambien de lo que se tiro. El estado materializado es cache y se
        descarta de verdad.
        """
        with self._turno_de_escritura, escritura(self._escritor) as conexion:
            caducados = _marcar_desde(conexion, id_obra, capitulo, relevo=None)
            conexion.execute(
                "DELETE FROM cache_estado_materializado "
                "WHERE id_obra = ? AND capitulo >= ? AND relevado_por IS NULL",
                (id_obra, capitulo),
            )
        return caducados

    def capitulos_cerrados(self, id_obra: str) -> list[int]:
        """Los capitulos con cierre vivo: el punto de guardado entero (RF-176)."""
        filas = self._lector.execute(
            "SELECT DISTINCT capitulo FROM artefacto_capitulo WHERE id_obra = ? "
            "AND estado = 'cerrado' AND caducado_en IS NULL AND capitulo IS NOT NULL "
            "ORDER BY capitulo",
            (id_obra,),
        )
        return [int(fila["capitulo"]) for fila in filas]

    def descartar_sin_cerrar(self, id_obra: str) -> int:
        """Descarta lo que cuelga de todo capitulo sin cierre vivo (RF-91, RF-176).

        En una obra que se escribe en orden son los posteriores al ultimo
        cerrado, igual que `descartar_desde`; en una version que reescribe
        capitulos sueltos, son tambien los que reescribe y no han cerrado, sin
        tocar los cerrados de detras. El estado materializado es cache y se
        descarta de verdad.
        """
        sin_cierre = (
            "NOT IN (SELECT c.capitulo FROM artefacto_capitulo AS c "
            "WHERE c.id_obra = :id_obra AND c.estado = 'cerrado' "
            "AND c.caducado_en IS NULL AND c.capitulo IS NOT NULL)"
        )
        with self._turno_de_escritura, escritura(self._escritor) as conexion:
            caducados = _marcar(conexion, id_obra, sin_cierre, {}, relevo=None)
            conexion.execute(
                "DELETE FROM cache_estado_materializado WHERE id_obra = :id_obra "
                f"AND relevado_por IS NULL AND capitulo {sin_cierre}",
                {"id_obra": id_obra},
            )
        return caducados

    def cerrar_trazas_interrumpidas(self, id_obra: str) -> int:
        """Una traza que sigue abierta al reanudar es de una tarea que corto una
        caida: no fallo, se interrumpio, y no cuenta como intento (RF-98)."""
        interrumpidas = self.trazas_abiertas(id_obra)
        for traza in interrumpidas:
            self.cerrar_traza(
                traza.id,
                salida="interrumpida",
                tokens_de_entrada_medidos=None,
                tokens_de_salida=None,
                coste=None,
                latencia_ms=0,
            )
        return len(interrumpidas)

    # --- Traza -------------------------------------------------------------

    def abrir_traza(
        self,
        id_obra: str,
        *,
        rol: str,
        tarea: str,
        intento: int,
        capitulo: int | None,
        escena: str | None,
        contexto: str,
        tokens_estimados: int,
    ) -> str:
        """Abre la traza al mandar la ventana. Mientras no se cierre, la tarea
        cuenta como abierta y sus tokens de entrada ocupan techo."""
        traza = Artefacto(
            tipo="Traza",
            cuerpo={"contexto_enviado": contexto},
            id_obra=id_obra,
            rol=rol,
            capitulo=capitulo,
            escena=escena,
            procedencia_rol=rol,
            procedencia_tarea=tarea,
            procedencia_intento=intento,
            propias={
                "tarea": tarea,
                "intento": intento,
                "tokens_de_entrada_estimados": tokens_estimados,
                "abierta_en": ahora(),
            },
        )
        return self.guardar([traza])[0]

    def cerrar_traza(
        self,
        id_traza: str,
        *,
        salida: str,
        tokens_de_entrada_medidos: int | None,
        tokens_de_salida: int | None,
        coste: float | None,
        latencia_ms: int,
        recuperaciones: list[dict[str, Any]] | None = None,
        ganchos: dict[str, Any] | None = None,
    ) -> None:
        traza = self.leer("Traza", id_traza)
        if traza is None:
            raise ArtefactoRechazado(f"no hay traza {id_traza!r} que cerrar")
        cuerpo = dict(traza.cuerpo)
        cuerpo["salida"] = salida
        cuerpo["recuperaciones"] = recuperaciones or []
        # El veredicto de los hooks va en el cuerpo, no en una columna: nadie
        # consulta por el todavia (SPEC1 RD-25).
        if ganchos is not None:
            cuerpo["ganchos"] = ganchos
        cerrada_en = ahora()
        # La traza y lo que `policy` encontro en ese intento se escriben juntos:
        # el registro no puede quedar sin su traza ni al reves (RF-136).
        with self._turno_de_escritura, escritura(self._escritor) as conexion:
            conexion.execute(
                "UPDATE artefacto_traza SET cuerpo = ?, tokens_de_entrada_medidos = ?, "
                "tokens_de_salida = ?, coste = ?, latencia_ms = ?, cerrada_en = ? "
                "WHERE id = ?",
                (
                    json.dumps(cuerpo, ensure_ascii=False),
                    tokens_de_entrada_medidos,
                    tokens_de_salida,
                    coste,
                    latencia_ms,
                    cerrada_en,
                    id_traza,
                ),
            )
            for decision, nivel, termino, encontrado in _decisiones_de_policy(ganchos):
                conexion.execute(
                    "INSERT INTO decision_de_policy (id_obra, id_traza, decision, nivel, "
                    "termino, encontrado, registrada_en) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (traza.id_obra, id_traza, decision, nivel, termino, encontrado, cerrada_en),
                )

    # --- Lo vetado (SPEC1 4.14) -------------------------------------------

    def terminos_vetados_globales(self) -> list[str]:
        """La lista global de la instalacion, en orden (RF-131)."""
        filas = self._lector.execute(
            "SELECT termino FROM termino_vetado_global ORDER BY termino"
        )
        return [str(fila["termino"]) for fila in filas]

    def listar_decisiones_de_policy(
        self,
        id_obra: str,
        *,
        capitulo: int | None = None,
        nivel: str | None = None,
        decision: str | None = None,
    ) -> list[dict[str, Any]]:
        """El registro de policy de la obra, en el orden en que se escribio.

        Capitulo, escena, tarea e intento no se copian al registro: se leen de
        la `Traza` de la que cuelga cada fila (RD-27).
        """
        condiciones = ["d.id_obra = :id_obra"]
        parametros: dict[str, Any] = {"id_obra": id_obra}
        for columna, valor in (
            ("t.capitulo", capitulo),
            ("d.nivel", nivel),
            ("d.decision", decision),
        ):
            if valor is not None:
                clave = columna.split(".")[1]
                condiciones.append(f"{columna} = :{clave}")
                parametros[clave] = valor
        filas = self._lector.execute(
            "SELECT d.id, d.id_traza, d.decision, d.nivel, d.termino, d.encontrado, "
            "d.registrada_en, t.capitulo, t.escena, t.tarea, t.intento "
            "FROM decision_de_policy AS d JOIN artefacto_traza AS t ON t.id = d.id_traza "
            f"WHERE {' AND '.join(condiciones)} ORDER BY d.id",
            parametros,
        )
        return [dict(fila) for fila in filas]

    def trazas_abiertas(self, id_obra: str) -> list[Artefacto]:
        filas = self._lector.execute(
            "SELECT * FROM artefacto_traza WHERE id_obra = ? AND cerrada_en IS NULL",
            (id_obra,),
        )
        return [_fila_a_artefacto(f) for f in filas]

    def contexto_de_entrada_abierto(self, id_obra: str) -> int:
        """Lo que ocupa ahora mismo el techo: la suma de las ventanas abiertas."""
        fila = self._lector.execute(
            "SELECT COALESCE(SUM(tokens_de_entrada_estimados), 0) AS suma "
            "FROM artefacto_traza WHERE id_obra = ? AND cerrada_en IS NULL",
            (id_obra,),
        ).fetchone()
        return int(fila["suma"])

    def listar_trazas(
        self,
        id_obra: str,
        *,
        capitulo: int | None = None,
        rol: str | None = None,
        tarea: str | None = None,
    ) -> list[Artefacto]:
        condiciones = ["id_obra = :id_obra"]
        parametros: dict[str, Any] = {"id_obra": id_obra}
        for columna, valor in (("capitulo", capitulo), ("rol", rol), ("tarea", tarea)):
            if valor is not None:
                condiciones.append(f"{columna} = :{columna}")
                parametros[columna] = valor
        filas = self._lector.execute(
            f"SELECT * FROM artefacto_traza WHERE {' AND '.join(condiciones)} "
            "ORDER BY abierta_en",
            parametros,
        )
        return [_fila_a_artefacto(f) for f in filas]

    def sumar_trazas(
        self, id_obra: str, *, version: int | None = None, capitulo: int | None = None
    ) -> dict[str, Any]:
        """Tareas, tokens, coste y latencia sumados de las `Traza` de la obra, de
        una version o de un capitulo de esa version (SPEC1 RF-186).

        La `Traza` lleva la version en que se abrio, asi que la suma de una
        version es lo que costo producirla, sin lo que comparte con la anterior.
        """
        condiciones = ["id_obra = :id_obra"]
        parametros: dict[str, Any] = {"id_obra": id_obra}
        for columna, valor in (("version_de_obra", version), ("capitulo", capitulo)):
            if valor is not None:
                condiciones.append(f"{columna} = :{columna}")
                parametros[columna] = valor
        fila = self._lector.execute(
            "SELECT COUNT(*) AS tareas, "
            "COALESCE(SUM(tokens_de_entrada_medidos), 0) AS tokens_de_entrada, "
            "COALESCE(SUM(tokens_de_salida), 0) AS tokens_de_salida, "
            "COALESCE(SUM(coste), 0) AS coste, "
            "COALESCE(SUM(latencia_ms), 0) AS latencia_ms "
            f"FROM artefacto_traza WHERE {' AND '.join(condiciones)}",
            parametros,
        ).fetchone()
        return _totales(fila)

    def sumar_pasadas(self, id_entrevista: str) -> dict[str, Any]:
        """Lo mismo, de las pasadas de una entrevista (RF-79, RF-186)."""
        fila = self._lector.execute(
            "SELECT COUNT(*) AS tareas, "
            "COALESCE(SUM(tokens_de_entrada_medidos), 0) AS tokens_de_entrada, "
            "COALESCE(SUM(tokens_de_salida), 0) AS tokens_de_salida, "
            "COALESCE(SUM(coste), 0) AS coste, "
            "COALESCE(SUM(latencia_ms), 0) AS latencia_ms "
            "FROM pasada_de_entrevista WHERE id_entrevista = ?",
            (id_entrevista,),
        ).fetchone()
        return _totales(fila)

    # --- Control de la ejecucion ------------------------------------------

    def detener(self, id_obra: str, motivo: str) -> None:
        self._control(id_obra, detenida=1, motivo=motivo)

    def reanudar(self, id_obra: str) -> None:
        self._control(id_obra, detenida=0, motivo=None)

    def _control(self, id_obra: str, *, detenida: int, motivo: str | None) -> None:
        with self._turno_de_escritura, escritura(self._escritor) as conexion:
            conexion.execute(
                "UPDATE control_de_ejecucion SET detenida = ?, motivo = ?, actualizado_en = ? "
                "WHERE id_obra = ?",
                (detenida, motivo, ahora(), id_obra),
            )

    def motivo_de_la_detencion(self, id_obra: str) -> str | None:
        """Por que esta detenida la obra; nada si no lo esta (RF-137)."""
        fila = self._lector.execute(
            "SELECT detenida, motivo FROM control_de_ejecucion WHERE id_obra = ?", (id_obra,)
        ).fetchone()
        if not fila or not fila["detenida"]:
            return None
        return str(fila["motivo"]) if fila["motivo"] is not None else None

    def esta_detenida(self, id_obra: str) -> bool:
        fila = self._lector.execute(
            "SELECT detenida FROM control_de_ejecucion WHERE id_obra = ?", (id_obra,)
        ).fetchone()
        return bool(fila and fila["detenida"])

    # --- Versiones de la obra (SPEC1 4.12) ---------------------------------

    def listar_versiones(self, id_obra: str) -> list[dict[str, Any]]:
        filas = self._lector.execute(
            f"{_VERSIONES_CON_SU_CAMBIO} WHERE v.id_obra = ? ORDER BY v.numero", (id_obra,)
        )
        return [_version_a_dict(fila) for fila in filas]

    def leer_version(self, id_obra: str, numero: int) -> dict[str, Any] | None:
        fila = self._lector.execute(
            f"{_VERSIONES_CON_SU_CAMBIO} WHERE v.id_obra = ? AND v.numero = ?",
            (id_obra, numero),
        ).fetchone()
        return _version_a_dict(fila) if fila else None

    def version_en_curso(self, id_obra: str) -> int:
        """La ultima version, que es la unica que se produce (D-40)."""
        return _version_en_curso(self._lector, id_obra)

    def version_publicada(self, id_obra: str) -> int | None:
        """La de la ultima publicacion, o ninguna (RF-116)."""
        fila = self._lector.execute(
            "SELECT numero FROM publicacion_de_version WHERE id_obra = ? "
            "ORDER BY id DESC LIMIT 1",
            (id_obra,),
        ).fetchone()
        return int(fila["numero"]) if fila else None

    def abrir_version(self, id_obra: str, desde: int, hasta: int) -> int:
        """Rehacer desde el capitulo `desde`: nace la version siguiente (RF-111).

        En una sola transaccion: la version nueva con los capitulos que cambian,
        el relevo de lo que colgaba de ellos en el mundo de la anterior (RF-112) y
        de su estado materializado (RF-115), y la constancia de auditoria
        rebajada a lo que sigue valiendo, para que la nueva se audite al cerrar.
        La anterior tiene que haber terminado (D-40). Devuelve el numero nuevo.
        """
        with self._turno_de_escritura, escritura(self._escritor) as conexion:
            ultima = conexion.execute(
                "SELECT numero, terminada_en FROM version_de_la_obra WHERE id_obra = ? "
                "ORDER BY numero DESC LIMIT 1",
                (id_obra,),
            ).fetchone()
            if ultima is None:
                raise KeyError(f"no hay ninguna obra {id_obra}")
            if ultima["terminada_en"] is None:
                raise VersionNoAdmitida(
                    f"la version {ultima['numero']} de {id_obra} no ha terminado: "
                    "solo se rehace desde una version terminada"
                )
            nueva = int(ultima["numero"]) + 1
            conexion.execute(
                "INSERT INTO version_de_la_obra (id_obra, numero, base, capitulos_cambiados, "
                "creada_en) VALUES (?, ?, ?, ?, ?)",
                (
                    id_obra,
                    nueva,
                    ultima["numero"],
                    json.dumps(list(range(desde, hasta + 1))),
                    ahora(),
                ),
            )
            _marcar_desde(conexion, id_obra, desde, relevo=nueva)
            conexion.execute(
                "UPDATE cache_estado_materializado SET relevado_por = ? "
                "WHERE id_obra = ? AND capitulo >= ? AND relevado_por IS NULL",
                (nueva, id_obra, desde),
            )
            conexion.execute(
                "UPDATE control_de_ejecucion SET auditada_hasta = MIN(auditada_hasta, ?), "
                "detenida = 0, motivo = NULL, actualizado_en = ? WHERE id_obra = ?",
                (desde - 1, ahora(), id_obra),
            )
        return nueva

    def abrir_version_por_cambio(
        self, id_obra: str, hecho: str, valor: str
    ) -> tuple[int, list[int]]:
        """El cambio del lector: nace la version siguiente (SPEC1 RF-170 a RF-173).

        En una sola transaccion: la version nueva con los capitulos que usan el
        hecho en la ultima, el relevo de lo que cuelga de cada uno y de su estado
        materializado, el relevo de la ficha vieja y la ficha nueva con el nombre
        cambiado, el registro del cambio y la constancia de auditoria rebajada.
        Devuelve el numero nuevo y los capitulos que se reescriben.

        `KeyError` si la ultima version no ve ese hecho; `ValueError` si el
        nombre no vale; `VersionNoAdmitida` si la ultima no ha terminado, y su
        hija `HechoSinMenciones` si ningun capitulo lo usa.
        """
        valor = valor.strip()
        tipo = TIPO_POR_PREFIJO.get(hecho.split("_", 1)[0])
        with self._turno_de_escritura, escritura(self._escritor) as conexion:
            fila = None
            if tipo in HECHOS_DE_LA_BIBLIA:
                fila = conexion.execute(
                    f"SELECT * FROM {nombre_de_tabla(tipo)} "
                    "WHERE id = ? AND id_obra = ? AND caducado_en IS NULL",
                    (hecho, id_obra),
                ).fetchone()
            if fila is None or tipo is None:
                raise KeyError(f"la ultima version de {id_obra} no tiene ningun hecho {hecho}")
            vieja = _fila_a_artefacto(fila)
            campo = _campo_del_nombre(vieja)
            anterior = str(vieja.cuerpo.get(campo) or "")
            if not valor:
                raise ValueError("el nombre nuevo no puede ir vacio")
            if valor == anterior:
                raise ValueError(
                    f"«{valor}» ya es el nombre de {hecho}: no hay nada que cambiar"
                )
            ultima = conexion.execute(
                "SELECT numero, terminada_en FROM version_de_la_obra WHERE id_obra = ? "
                "ORDER BY numero DESC LIMIT 1",
                (id_obra,),
            ).fetchone()
            if ultima["terminada_en"] is None:
                raise VersionNoAdmitida(
                    f"la version {ultima['numero']} de {id_obra} no ha terminado: "
                    "solo se cambia un hecho de una version terminada"
                )
            capitulos = [
                int(f["capitulo"])
                for f in conexion.execute(
                    "SELECT DISTINCT capitulo FROM artefacto_mencion "
                    "WHERE id_obra = ? AND hecho = ? AND caducado_en IS NULL ORDER BY capitulo",
                    (id_obra, hecho),
                )
            ]
            if not capitulos:
                raise HechoSinMenciones(
                    f"ningun capitulo de la version {ultima['numero']} menciona {hecho}: "
                    "no hay nada que reescribir"
                )
            nueva = int(ultima["numero"]) + 1
            conexion.execute(
                "INSERT INTO version_de_la_obra (id_obra, numero, base, capitulos_cambiados, "
                "creada_en) VALUES (?, ?, ?, ?, ?)",
                (id_obra, nueva, ultima["numero"], json.dumps(capitulos), ahora()),
            )
            en_lista = ", ".join(str(capitulo) for capitulo in capitulos)
            _marcar(conexion, id_obra, f"IN ({en_lista})", {}, relevo=nueva)
            conexion.execute(
                "UPDATE cache_estado_materializado SET relevado_por = ? "
                f"WHERE id_obra = ? AND capitulo IN ({en_lista}) AND relevado_por IS NULL",
                (nueva, id_obra),
            )
            # El hecho se versiona: la vieja la sigue viendo la version anterior y
            # la nueva nace en esta, escrita por el backend y no por un rol (D-72).
            conexion.execute(
                f"UPDATE {nombre_de_tabla(tipo)} SET caducado_en = ?, relevado_por = ? "
                "WHERE id = ?",
                (ahora(), nueva, hecho),
            )
            cuerpo = dict(vieja.cuerpo) | {campo: valor, "sustituye": hecho}
            tratamientos = cuerpo.get("tratamientos")
            if isinstance(tratamientos, list):
                cuerpo["tratamientos"] = [
                    valor if tratamiento == anterior else tratamiento
                    for tratamiento in tratamientos
                ]
            ficha_nueva = self._insertar(
                conexion,
                Artefacto(
                    tipo=tipo,
                    cuerpo=cuerpo,
                    id_obra=id_obra,
                    memoria=vieja.memoria,
                    version_de_obra=nueva,
                ),
            )
            conexion.execute(
                "INSERT INTO cambio_del_lector (id_obra, version, hecho, tipo, ficha_nueva, "
                "anterior, nuevo, pedido_en) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (id_obra, nueva, hecho, tipo, ficha_nueva, anterior, valor, ahora()),
            )
            conexion.execute(
                "UPDATE control_de_ejecucion SET auditada_hasta = MIN(auditada_hasta, ?), "
                "detenida = 0, motivo = NULL, actualizado_en = ? WHERE id_obra = ?",
                (capitulos[0] - 1, ahora(), id_obra),
            )
        return nueva, capitulos

    def fichas_sustituidas(self, id_obra: str, version: int) -> dict[str, str]:
        """De cada ficha que un cambio del lector relevo, la que la sustituye en
        la version pedida o antes (RF-177). Solo referencias por `id`."""
        filas = self._lector.execute(
            "SELECT hecho, ficha_nueva FROM cambio_del_lector "
            "WHERE id_obra = ? AND version <= ? ORDER BY version",
            (id_obra, version),
        )
        return {fila["hecho"]: fila["ficha_nueva"] for fila in filas}

    def salidas_de_rol_de_la_version(self, id_obra: str, numero: int) -> list[Artefacto]:
        """Lo que ve la version y escribio un rol (SPEC1 RF-141).

        La `Traza` no es salida de ningun rol, y lo que escribe el backend —las
        criticas de un malformado o de un «no comprobado»— no lleva rol.
        """
        salidas: list[Artefacto] = []
        for tabla in esquema.TABLAS:
            if tabla.tipo == "Traza":
                continue
            salidas += [
                artefacto
                for artefacto in self.listar(tabla.tipo, id_obra, version=numero)
                if artefacto.procedencia_rol is not None
            ]
        return salidas

    def publicar_version(self, id_obra: str, numero: int) -> str:
        """Anade la publicacion al registro. Solo una version terminada (RF-116).

        No se llama desde ningun otro sitio que `nucleo.versiones.publicar`: es el
        unico camino por el que una version queda publicada.
        """
        with self._turno_de_escritura, escritura(self._escritor) as conexion:
            version = conexion.execute(
                "SELECT terminada_en FROM version_de_la_obra WHERE id_obra = ? AND numero = ?",
                (id_obra, numero),
            ).fetchone()
            if version is None:
                raise KeyError(f"la obra {id_obra} no tiene version {numero}")
            if version["terminada_en"] is None:
                raise VersionNoAdmitida(
                    f"la version {numero} de {id_obra} no ha terminado: no se publica"
                )
            publicada_en = ahora()
            conexion.execute(
                "INSERT INTO publicacion_de_version (id_obra, numero, publicada_en) "
                "VALUES (?, ?, ?)",
                (id_obra, numero, publicada_en),
            )
        return publicada_en


def _materializar(
    conexion: sqlite3.Connection, id_obra: str, capitulo: int, cuerpo: dict[str, Any]
) -> None:
    conexion.execute(
        "INSERT INTO cache_estado_materializado "
        "(id_obra, version_de_obra, capitulo, cuerpo, calculado_en) VALUES (?, ?, ?, ?, ?) "
        "ON CONFLICT (id_obra, version_de_obra, capitulo) DO UPDATE SET "
        "cuerpo = excluded.cuerpo, calculado_en = excluded.calculado_en",
        (
            id_obra,
            _version_en_curso(conexion, id_obra),
            capitulo,
            json.dumps(cuerpo, ensure_ascii=False),
            ahora(),
        ),
    )


def _caducar_memoria(conexion: sqlite3.Connection, id_obra: str, capitulo: int) -> int:
    marca = ahora()
    caducados = 0
    for tabla in esquema.TABLAS:
        if "capitulo" not in tabla.consulta:
            continue
        sigue_abierta = "AND estado IS NOT 'abierta'" if "estado" in tabla.consulta else ""
        cursor = conexion.execute(
            f"UPDATE {nombre_de_tabla(tabla.tipo)} SET caducado_en = ? "
            "WHERE id_obra = ? AND capitulo = ? AND memoria = 'capitulo' "
            f"AND caducado_en IS NULL {sigue_abierta}",
            (marca, id_obra, capitulo),
        )
        caducados += cursor.rowcount
    return caducados


def _marcar_desde(
    conexion: sqlite3.Connection, id_obra: str, capitulo: int, *, relevo: int | None
) -> int:
    """Caduca lo vivo que cuelga del capitulo N en adelante (RF-112, RF-118).

    Cuelga de un capitulo lo que lleva ese capitulo y lo que, sin llevarlo, lo
    escribio una tarea de ese capitulo, como un `Evento` que el Planificador
    anadio al mundo: su `Traza` dice de que capitulo era. La `Traza` misma no se
    marca: es el registro de lo que paso. Con `relevo`, la marca dice ademas que
    version lo relevo, y la version anterior lo sigue viendo.
    """
    return _marcar(conexion, id_obra, ">= :capitulo", {"capitulo": capitulo}, relevo=relevo)


def _marcar(
    conexion: sqlite3.Connection,
    id_obra: str,
    que_capitulos: str,
    parametros_propios: dict[str, Any],
    *,
    relevo: int | None,
) -> int:
    """Caduca lo vivo que cuelga de los capitulos que dice `que_capitulos`, una
    condicion SQL sobre el numero de capitulo (`>= :capitulo`, `IN (2, 5)`).

    Es la misma regla para rehacer desde N, para descartar lo que no llego a
    cerrar y para el cambio del lector (RF-112, RF-118, RF-172, RF-176).
    """
    marca = ahora()
    relevo_sql = ", relevado_por = :relevo" if relevo is not None else ""
    parametros = {"marca": marca, "id_obra": id_obra, "relevo": relevo} | parametros_propios
    caducados = 0
    for tabla in esquema.TABLAS:
        if tabla.tipo in ("Traza", "Obra"):
            continue
        if "capitulo" in tabla.consulta:
            de_que_capitulo = f"capitulo IS NOT NULL AND capitulo {que_capitulos}"
        else:
            de_que_capitulo = (
                "procedencia_tarea IN (SELECT id FROM artefacto_traza "
                "WHERE id_obra = :id_obra AND capitulo IS NOT NULL "
                f"AND capitulo {que_capitulos})"
            )
        cursor = conexion.execute(
            f"UPDATE {nombre_de_tabla(tabla.tipo)} SET caducado_en = :marca{relevo_sql} "
            f"WHERE id_obra = :id_obra AND caducado_en IS NULL AND {de_que_capitulo}",
            parametros,
        )
        caducados += cursor.rowcount
    return caducados


def _totales(fila: sqlite3.Row) -> dict[str, Any]:
    return {
        "tareas": int(fila["tareas"]),
        "tokens_de_entrada": int(fila["tokens_de_entrada"]),
        "tokens_de_salida": int(fila["tokens_de_salida"]),
        "coste": float(fila["coste"]),
        "latencia_ms": int(fila["latencia_ms"]),
    }


def sumar_totales(*partes: dict[str, Any]) -> dict[str, Any]:
    """Suma campo a campo varios totales de `sumar_trazas` o `sumar_pasadas`."""
    suma: dict[str, Any] = {
        "tareas": 0, "tokens_de_entrada": 0, "tokens_de_salida": 0, "coste": 0.0,
        "latencia_ms": 0,
    }
    for parte in partes:
        for clave in suma:
            suma[clave] += parte.get(clave, 0)
    return suma


def abrir_almacen(ruta: Path | str) -> Almacen:
    """Abre el almacen y lo deja migrado al dia."""
    almacen = Almacen(ruta)
    almacen.migrar()
    return almacen


def cuerpos(artefactos: Iterable[Artefacto]) -> list[dict[str, Any]]:
    """Atajo de lectura: los cuerpos de una lista de artefactos."""
    return [artefacto.cuerpo for artefacto in artefactos]
