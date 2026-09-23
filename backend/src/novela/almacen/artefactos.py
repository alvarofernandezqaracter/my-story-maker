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
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from novela.almacen import esquema
from novela.almacen.conexion import abrir, escritura
from novela.almacen.esquema import TABLA_POR_TIPO, nombre_de_tabla
from novela.vocabularios import MEMORIA

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
    "Personaje": "per",
    "Lugar": "lug",
    "Evento": "evn",
    "Objeto": "obj",
    "Faccion": "fac",
    "Practica": "pra",
    "Concepto": "cnc",
    "RegistroLinguistico": "reg",
    "Fuente": "fue",
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


class Almacen:
    """La puerta. Se abre una vez y se pasa a quien la necesite."""

    def __init__(self, ruta: Path | str) -> None:
        self.ruta = Path(ruta)
        self._escritor = abrir(self.ruta)
        self._lector = abrir(self.ruta)
        self._turno_de_escritura = threading.Lock()

    def cerrar(self) -> None:
        self._escritor.close()
        self._lector.close()

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
            raise ArtefactoRechazado(f"{artefacto.tipo}: {error}") from error
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

    def crear_obra(self, cuerpo: dict[str, Any]) -> str:
        """Da de alta la obra. Cada obra nace en su propio espacio (RF-03)."""
        artefacto = Artefacto(tipo="Obra", cuerpo=cuerpo)
        with self._turno_de_escritura, escritura(self._escritor) as conexion:
            id_obra = self._insertar(conexion, artefacto)
            conexion.execute(
                "INSERT INTO control_de_ejecucion (id_obra, detenida, actualizado_en) "
                "VALUES (?, 0, ?)",
                (id_obra, ahora()),
            )
        return id_obra

    def leer_obra(self, id_obra: str) -> Artefacto | None:
        return self.leer("Obra", id_obra)

    def listar_obras(self) -> list[Artefacto]:
        filas = self._lector.execute(
            "SELECT * FROM artefacto_obra WHERE caducado_en IS NULL ORDER BY creado_en DESC"
        )
        return [_fila_a_artefacto(f) for f in filas]

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
            conexion.execute(
                "INSERT INTO cache_estado_materializado "
                "(id_obra, capitulo, cuerpo, calculado_en) VALUES (?, ?, ?, ?) "
                "ON CONFLICT (id_obra, capitulo) DO UPDATE SET "
                "cuerpo = excluded.cuerpo, calculado_en = excluded.calculado_en",
                (id_obra, capitulo, json.dumps(cuerpo, ensure_ascii=False), ahora()),
            )

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

        Lo ejecuta el Archivero como paso del guion. No borra: marca.
        """
        marca = ahora()
        caducados = 0
        with self._turno_de_escritura, escritura(self._escritor) as conexion:
            for tabla in esquema.TABLAS:
                if "capitulo" not in tabla.consulta:
                    continue
                cursor = conexion.execute(
                    f"UPDATE {nombre_de_tabla(tabla.tipo)} SET caducado_en = ? "
                    "WHERE id_obra = ? AND capitulo = ? AND memoria = 'capitulo' "
                    "AND caducado_en IS NULL",
                    (marca, id_obra, capitulo),
                )
                caducados += cursor.rowcount
        return caducados

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


def abrir_almacen(ruta: Path | str) -> Almacen:
    """Abre el almacen y lo deja migrado al dia."""
    almacen = Almacen(ruta)
    almacen.migrar()
    return almacen


def cuerpos(artefactos: Iterable[Artefacto]) -> list[dict[str, Any]]:
    """Atajo de lectura: los cuerpos de una lista de artefactos."""
    return [artefacto.cuerpo for artefacto in artefactos]
