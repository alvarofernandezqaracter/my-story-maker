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
    propias: dict[str, Any] = field(default_factory=dict)


def _fila_a_artefacto(fila: sqlite3.Row) -> Artefacto:
    columnas = fila.keys()
    conocidas = {
        "id", "id_obra", "tipo", "cuerpo", "capitulo", "escena", "estado", "severidad",
        "dimension", "rol", "orden", "version", "memoria", "procedencia_rol",
        "procedencia_tarea", "procedencia_intento", "creado_en", "caducado_en",
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
        }
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
    ) -> list[Artefacto]:
        """Lista acotada por obra, que es como se consulta siempre (RD-06)."""
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
            condiciones.append("caducado_en IS NULL")
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
        return id_obra

    def listar_recuerdos(self, id_obra: str) -> list[Artefacto]:
        return self.listar("Recuerdo", id_obra)

    def leer_obra(self, id_obra: str) -> Artefacto | None:
        return self.leer("Obra", id_obra)

    def listar_obras(self) -> list[Artefacto]:
        filas = self._lector.execute(
            "SELECT * FROM artefacto_obra WHERE caducado_en IS NULL ORDER BY creado_en DESC"
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

    def leer_capitulo(self, id_obra: str, numero: int) -> dict[str, Any]:
        """Todo lo que hay de un capitulo: plan, escenas, borradores y criticas."""
        capitulos = self.listar("Capitulo", id_obra, capitulo=numero)
        return {
            "capitulo": capitulos[0] if capitulos else None,
            "plan": next(iter(self.listar("Plan", id_obra, capitulo=numero)), None),
            "escenas": self.listar("Escena", id_obra, capitulo=numero, orden="orden"),
            "borradores": self.listar("Borrador", id_obra, capitulo=numero),
            "criticas": self.listar("Critica", id_obra, capitulo=numero),
        }

    def marcar_capitulo(self, id_capitulo: str, estado: str) -> None:
        self._actualizar("Capitulo", id_capitulo, {"estado": estado})

    # --- Borradores --------------------------------------------------------

    def guardar_borrador(self, borrador: Artefacto) -> str:
        """Guarda un borrador candidato, con su numero de version."""
        if borrador.tipo != "Borrador":
            raise ArtefactoRechazado("guardar_borrador solo guarda borradores")
        return self.guardar([borrador])[0]

    def borrador_vigente(self, id_obra: str, escena: str) -> Artefacto | None:
        """El ultimo borrador vivo de una escena: el aceptado, si lo hay."""
        fila = self._lector.execute(
            "SELECT * FROM artefacto_borrador WHERE id_obra = ? AND escena = ? "
            "AND estado <> 'descartado' AND caducado_en IS NULL "
            "ORDER BY version DESC LIMIT 1",
            (id_obra, escena),
        ).fetchone()
        return _fila_a_artefacto(fila) if fila else None

    def aceptar_borrador(self, id_borrador: str) -> None:
        """Acepta el borrador y lo pasa a memoria de obra: a partir de aqui es
        inmutable y es lo unico que se indexa y se sirve como manuscrito."""
        self._actualizar("Borrador", id_borrador, {"estado": "aceptado", "memoria": "obra"})

    def descartar_borrador(self, id_borrador: str) -> None:
        self._actualizar("Borrador", id_borrador, {"estado": "descartado"})

    def manuscrito_aceptado(self, id_obra: str) -> list[Artefacto]:
        """Solo el texto aceptado, en orden (RF-50)."""
        filas = self._lector.execute(
            "SELECT b.* FROM artefacto_borrador AS b "
            "JOIN artefacto_escena AS e ON e.id = b.escena "
            "WHERE b.id_obra = ? AND b.estado = 'aceptado' AND b.caducado_en IS NULL "
            "ORDER BY b.capitulo, e.orden",
            (id_obra,),
        )
        return [_fila_a_artefacto(f) for f in filas]

    # --- Criticas ----------------------------------------------------------

    def guardar_critica(self, critica: Artefacto) -> str:
        if critica.tipo != "Critica":
            raise ArtefactoRechazado("guardar_critica solo guarda criticas")
        critica.estado = critica.estado or "abierta"
        return self.guardar([critica])[0]

    def listar_criticas_abiertas(
        self, id_obra: str, *, escena: str | None = None, severidad: str | None = None
    ) -> list[Artefacto]:
        return self.listar(
            "Critica", id_obra, escena=escena, estado="abierta", severidad=severidad
        )

    def resolver_critica(self, id_critica: str, estado: str) -> None:
        """Atendida, rechazada con motivo o descartada por falta de evidencia."""
        if estado not in esquema.ESTADO_DE_CRITICA:
            raise ArtefactoRechazado(f"{estado!r} no es un estado de critica")
        self._actualizar("Critica", id_critica, {"estado": estado})

    # --- La biblia: en que capitulos se usa cada hecho ---------------------

    def capitulos_de_uso(self, id_obra: str) -> dict[str, list[int]]:
        """En que capitulos se usa cada hecho. Se deriva, no se guarda (RF-84).

        Una mencion repetida no duplica el capitulo.
        """
        filas = self._lector.execute(
            "SELECT DISTINCT hecho, capitulo FROM artefacto_mencion "
            "WHERE id_obra = ? AND caducado_en IS NULL ORDER BY hecho, capitulo",
            (id_obra,),
        )
        usos: dict[str, list[int]] = {}
        for fila in filas:
            usos.setdefault(fila["hecho"], []).append(int(fila["capitulo"]))
        return usos

    def hechos_de_la_biblia(
        self, id_obra: str, *, tipo: str | None = None, licencia: str | None = None
    ) -> list[dict[str, Any]]:
        """Cada hecho con su tipo, nombre, licencia y capitulos de uso (RF-87)."""
        if tipo is not None and tipo not in HECHOS_DE_LA_BIBLIA:
            raise KeyError(f"{tipo!r} no es un hecho de la biblia")
        usos = self.capitulos_de_uso(id_obra)
        hechos: list[dict[str, Any]] = []
        for tipo_de_hecho in (tipo,) if tipo else HECHOS_DE_LA_BIBLIA:
            for ficha in self.listar(tipo_de_hecho, id_obra):
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

    def cronologia(self, id_obra: str) -> list[dict[str, Any]]:
        """Los sucesos de la obra en orden, con quien estaba presente (RF-86).

        Es una vista, no una tabla: una fila por `EventoEstado` y por `Evento`
        del mundo. Copia lo escrito y no calcula fechas ni edades; ordenar por
        la fecha escrita no es aritmetica de calendario.
        """
        personajes = {ficha.id: ficha for ficha in self.listar("Personaje", id_obra)}

        def presentes(identificadores: Any) -> list[dict[str, Any]]:
            if not isinstance(identificadores, list):
                return []
            filas = []
            for identificador in identificadores:
                ficha = personajes.get(identificador)
                filas.append(
                    {
                        "id": identificador,
                        "nombre": _nombre_del_hecho(ficha) if ficha else None,
                        "nacimiento": _nacimiento(ficha),
                    }
                )
            return filas

        sucesos: list[dict[str, Any]] = []
        for evento in self.listar("EventoEstado", id_obra, orden="capitulo"):
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
        for evento in self.listar("Evento", id_obra):
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

    def estado_en(self, id_obra: str, capitulo: int) -> dict[str, Any] | None:
        fila = self._lector.execute(
            "SELECT cuerpo FROM cache_estado_materializado WHERE id_obra = ? AND capitulo = ?",
            (id_obra, capitulo),
        ).fetchone()
        return json.loads(fila["cuerpo"]) if fila else None

    def descartar_estados_desde(self, id_obra: str, capitulo: int) -> int:
        """Regenerar el capitulo N descarta los estados de N en adelante.

        Se borra de verdad porque esto es cache: el estado no se almacena, se
        deriva, y lo que se descarta aqui se vuelve a plegar hacia delante.
        """
        with self._turno_de_escritura, escritura(self._escritor) as conexion:
            cursor = conexion.execute(
                "DELETE FROM cache_estado_materializado WHERE id_obra = ? AND capitulo >= ?",
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
    ) -> list[int]:
        """Las criticas de `auditar` y la constancia de hasta donde se audito,
        juntas o ninguna (RF-94)."""
        with self._turno_de_escritura, escritura(self._escritor) as conexion:
            rechazados = self._insertar_lotes(conexion, lotes, al_rechazar)
            conexion.execute(
                "UPDATE control_de_ejecucion SET auditada_hasta = MAX(auditada_hasta, ?), "
                "actualizado_en = ? WHERE id_obra = ?",
                (hasta, ahora(), id_obra),
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
        marca = ahora()
        caducados = 0
        with self._turno_de_escritura, escritura(self._escritor) as conexion:
            for tabla in esquema.TABLAS:
                if "capitulo" not in tabla.consulta or tabla.tipo == "Traza":
                    continue
                cursor = conexion.execute(
                    f"UPDATE {nombre_de_tabla(tabla.tipo)} SET caducado_en = ? "
                    "WHERE id_obra = ? AND capitulo >= ? AND caducado_en IS NULL",
                    (marca, id_obra, capitulo),
                )
                caducados += cursor.rowcount
            conexion.execute(
                "DELETE FROM cache_estado_materializado WHERE id_obra = ? AND capitulo >= ?",
                (id_obra, capitulo),
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
    ) -> None:
        traza = self.leer("Traza", id_traza)
        if traza is None:
            raise ArtefactoRechazado(f"no hay traza {id_traza!r} que cerrar")
        cuerpo = dict(traza.cuerpo)
        cuerpo["salida"] = salida
        cuerpo["recuperaciones"] = recuperaciones or []
        self._actualizar(
            "Traza",
            id_traza,
            {
                "cuerpo": json.dumps(cuerpo, ensure_ascii=False),
                "tokens_de_entrada_medidos": tokens_de_entrada_medidos,
                "tokens_de_salida": tokens_de_salida,
                "coste": coste,
                "latencia_ms": latencia_ms,
                "cerrada_en": ahora(),
            },
        )

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

    def esta_detenida(self, id_obra: str) -> bool:
        fila = self._lector.execute(
            "SELECT detenida FROM control_de_ejecucion WHERE id_obra = ?", (id_obra,)
        ).fetchone()
        return bool(fila and fila["detenida"])


def _materializar(
    conexion: sqlite3.Connection, id_obra: str, capitulo: int, cuerpo: dict[str, Any]
) -> None:
    conexion.execute(
        "INSERT INTO cache_estado_materializado "
        "(id_obra, capitulo, cuerpo, calculado_en) VALUES (?, ?, ?, ?) "
        "ON CONFLICT (id_obra, capitulo) DO UPDATE SET "
        "cuerpo = excluded.cuerpo, calculado_en = excluded.calculado_en",
        (id_obra, capitulo, json.dumps(cuerpo, ensure_ascii=False), ahora()),
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


def abrir_almacen(ruta: Path | str) -> Almacen:
    """Abre el almacen y lo deja migrado al dia."""
    almacen = Almacen(ruta)
    almacen.migrar()
    return almacen


def cuerpos(artefactos: Iterable[Artefacto]) -> list[dict[str, Any]]:
    """Atajo de lectura: los cuerpos de una lista de artefactos."""
    return [artefacto.cuerpo for artefacto in artefactos]
