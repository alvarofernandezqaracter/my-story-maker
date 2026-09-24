"""Recuperacion por parecido: tres colecciones y ninguna mas.

Buena parte de lo que un agente necesita no se localiza por identificador sino
por semejanza. Para eso hay tres colecciones indexadas —documental, obra por su
prosa y obra por su estructura— y cada una tiene un solo momento de escritura y
un solo lector.

Un fragmento no es una entidad del dominio: es un trozo de un artefacto que ya
existe y vive en el indice, no en la ontologia. El indice es derivado y los
artefactos no: se puede borrar entero y reconstruir desde ellos.

**La busqueda es hibrida, siempre.** `sqlite-vec` para el parecido de sentido y
FTS5 para la palabra exacta sobre la misma coleccion, con los dos ordenes
fundidos en uno solo antes de recortar a `k`. Ninguna de las dos vias se
consulta a solas: el nombre propio y la fecha exacta son justo lo que peor
encuentra el parecido de sentido, y son la mitad de lo que el Documentalista
busca.

**Lo que no se indexa.** Solo texto aceptado. Un borrador candidato o
descartado no puede recuperarse nunca como eco.
"""

import json
import threading
from dataclasses import dataclass
from typing import Any

from novela.ajustes import (
    DIMENSIONES_DE_LA_HUELLA,
    K_POR_ROL,
    MODELO_DE_HUELLAS,
    SOLAPE_ENTRE_FRAGMENTOS_EN_CARACTERES,
    TAMANO_DE_FRAGMENTO_EN_CARACTERES,
    TOPE_DE_TOKENS_RECUPERADOS_POR_ROL,
    tope_de_ventana,
)
from novela.almacen.artefactos import Almacen, ahora, nuevo_identificador
from novela.almacen.conexion import escritura

COLECCIONES: tuple[str, ...] = ("documental", "obra_prosa", "obra_estructura")

# De que sale cada coleccion y por que campo del cuerpo se trocea.
DE_DONDE_SALE: dict[str, tuple[tuple[str, str], ...]] = {
    "documental": (("Fuente", "texto_integro"),),
    "obra_prosa": (("Borrador", "texto"),),
    "obra_estructura": (("Escena", ""), ("ResumenCapitulo", "")),
}

# Constante de la fusion de los dos ordenes. Sesenta es el valor habitual: alto
# para que ningun primer puesto suelto se coma el resultado.
AMORTIGUADOR_DE_LA_FUSION = 60


@dataclass
class Fragmento:
    """Un trozo indexado, con de que artefacto sale."""

    id: str
    texto: str
    artefacto: str
    tipo_de_artefacto: str
    capitulo: int | None
    escena: str | None
    fecha: str | None
    lugar: str | None
    ambito: str | None

    def a_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "texto": self.texto,
            "artefacto": self.artefacto,
            "tipo": self.tipo_de_artefacto,
            "capitulo": self.capitulo,
            "escena": self.escena,
            "fecha": self.fecha,
            "lugar": self.lugar,
            "ambito": self.ambito,
        }


def sentencias_del_indice() -> list[str]:
    """Migracion 2: las tres colecciones, su huella y su palabra exacta."""
    return [
        f"""CREATE TABLE fragmento (
  id TEXT NOT NULL PRIMARY KEY,
  id_obra TEXT NOT NULL REFERENCES artefacto_obra(id),
  coleccion TEXT NOT NULL CHECK (coleccion IN ({', '.join(repr(c) for c in COLECCIONES)})),
  artefacto TEXT NOT NULL,
  tipo_de_artefacto TEXT NOT NULL,
  capitulo INT,
  escena TEXT,
  fecha TEXT,
  lugar TEXT,
  ambito TEXT,
  texto TEXT NOT NULL,
  orden INT NOT NULL,
  modelo TEXT NOT NULL,
  creado_en TEXT NOT NULL
) STRICT""",
        "CREATE INDEX indice_fragmento_1 ON fragmento (id_obra, coleccion)",
        "CREATE INDEX indice_fragmento_2 ON fragmento (id_obra, artefacto)",
        # La palabra exacta. Contenido externo: el texto vive una sola vez, en
        # `fragmento`, y FTS5 guarda solo su indice.
        "CREATE VIRTUAL TABLE fts_fragmento USING fts5("
        "texto, content='fragmento', content_rowid='rowid')",
        # El parecido de sentido, particionado por obra: ninguna consulta cruza
        # de una obra a otra.
        f"""CREATE VIRTUAL TABLE vec_fragmento USING vec0(
  fragmento integer primary key,
  id_obra text partition key,
  coleccion text,
  huella float[{DIMENSIONES_DE_LA_HUELLA}] distance_metric=cosine
)""",
    ]


def trocear(texto: str) -> list[str]:
    """Trozos de tamano declarado con el solape declarado.

    Cuanto mide un fragmento y cuanto se solapa con el siguiente es una
    decision abierta (SPEC1 12): corto recupera preciso y pierde contexto,
    largo al reves. Estos son los valores de partida.
    """
    limpio = texto.strip()
    if not limpio:
        return []
    tamano = TAMANO_DE_FRAGMENTO_EN_CARACTERES
    salto = max(1, tamano - SOLAPE_ENTRE_FRAGMENTOS_EN_CARACTERES)
    trozos = (limpio[i : i + tamano] for i in range(0, len(limpio), salto))
    return [trozo for trozo in trozos if trozo]


class Indice:
    """La puerta de la recuperacion por parecido. La abre `almacen/`."""

    def __init__(self, almacen: Almacen) -> None:
        self.almacen = almacen
        self._modelo: Any = None
        # Las tareas de una tanda consultan a la vez (D-51): el modelo se carga
        # una sola vez y las huellas se calculan de una en una.
        self._turno_del_modelo = threading.Lock()

    # --- Huellas -----------------------------------------------------------

    def _huellas(self, textos: list[str]) -> list[list[float]]:
        """Se calculan en la propia maquina: ni indexar ni consultar sale al
        exterior."""
        with self._turno_del_modelo:
            if self._modelo is None:
                from fastembed import TextEmbedding

                self._modelo = TextEmbedding(MODELO_DE_HUELLAS)
            return [list(map(float, huella)) for huella in self._modelo.embed(textos)]

    # --- Escritura del indice ---------------------------------------------

    def indexar(
        self,
        id_obra: str,
        coleccion: str,
        artefactos: list[Any],
        *,
        campo: str = "",
    ) -> int:
        """Indexa artefactos ya aceptados. Devuelve cuantos fragmentos quedaron."""
        if coleccion not in COLECCIONES:
            raise ValueError(f"{coleccion!r} no es una de las tres colecciones")
        filas: list[tuple[Any, ...]] = []
        textos: list[str] = []
        for artefacto in artefactos:
            escena = artefacto.escena
            if escena is None and artefacto.tipo == "Escena":
                escena = artefacto.id
            crudo = artefacto.cuerpo.get(campo) if campo else None
            if not isinstance(crudo, str):
                crudo = json.dumps(artefacto.cuerpo, ensure_ascii=False, sort_keys=True)
            marco = artefacto.cuerpo.get("marco") or {}
            for orden, trozo in enumerate(trocear(crudo)):
                filas.append(
                    (
                        nuevo_identificador("frg"),
                        id_obra,
                        coleccion,
                        artefacto.id,
                        artefacto.tipo,
                        artefacto.capitulo,
                        escena,
                        marco.get("instante") if isinstance(marco, dict) else None,
                        marco.get("lugar") if isinstance(marco, dict) else None,
                        artefacto.cuerpo.get("ambito"),
                        trozo,
                        orden,
                        MODELO_DE_HUELLAS,
                        ahora(),
                    )
                )
                textos.append(trozo)
        if not filas:
            return 0

        huellas = self._huellas(textos)
        conexion = self.almacen._escritor
        with self.almacen._turno_de_escritura, escritura(conexion):
            for fila, huella in zip(filas, huellas, strict=True):
                cursor = conexion.execute(
                    "INSERT INTO fragmento (id, id_obra, coleccion, artefacto, "
                    "tipo_de_artefacto, capitulo, escena, fecha, lugar, ambito, texto, "
                    "orden, modelo, creado_en) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    fila,
                )
                numero = cursor.lastrowid
                conexion.execute(
                    "INSERT INTO fts_fragmento (rowid, texto) VALUES (?, ?)",
                    (numero, fila[10]),
                )
                conexion.execute(
                    "INSERT INTO vec_fragmento (fragmento, id_obra, coleccion, huella) "
                    "VALUES (?, ?, ?, ?)",
                    (numero, id_obra, coleccion, _a_blob(huella)),
                )
        return len(filas)

    def indexar_prosa_aceptada(self, id_obra: str, capitulo: int) -> int:
        """Al aceptar la unidad, nunca antes."""
        aceptados = [
            b
            for b in self.almacen.listar("Borrador", id_obra, capitulo=capitulo)
            if b.estado == "aceptado" and not self._ya_indexado(b.id)
        ]
        return self.indexar(id_obra, "obra_prosa", aceptados, campo="texto")

    def indexar_fuentes(self, id_obra: str, capitulo: int) -> int:
        """Al recoger la `Fuente`."""
        fuentes = [
            f
            for f in self.almacen.listar("Fuente", id_obra, capitulo=capitulo)
            if not self._ya_indexado(f.id)
        ]
        return self.indexar(id_obra, "documental", fuentes, campo="texto_integro")

    def indexar_estructura(self, id_obra: str, capitulo: int) -> int:
        """Al cerrar el capitulo: contratos cumplidos y resumenes."""
        cuantos = 0
        for tipo in ("Escena", "ResumenCapitulo"):
            artefactos = [
                a
                for a in self.almacen.listar(tipo, id_obra, capitulo=capitulo)
                if not self._ya_indexado(a.id)
            ]
            cuantos += self.indexar(id_obra, "obra_estructura", artefactos)
        return cuantos

    def _ya_indexado(self, artefacto: str) -> bool:
        fila = self.almacen._lector.execute(
            "SELECT 1 FROM fragmento WHERE artefacto = ? LIMIT 1", (artefacto,)
        ).fetchone()
        return fila is not None

    def vaciar(self, id_obra: str) -> None:
        """El indice es derivado: se puede borrar entero y reconstruir."""
        conexion = self.almacen._escritor
        with self.almacen._turno_de_escritura, escritura(conexion):
            numeros = [
                fila["rowid"]
                for fila in conexion.execute(
                    "SELECT rowid FROM fragmento WHERE id_obra = ?", (id_obra,)
                )
            ]
            for numero in numeros:
                conexion.execute("DELETE FROM fts_fragmento WHERE rowid = ?", (numero,))
                conexion.execute("DELETE FROM vec_fragmento WHERE fragmento = ?", (numero,))
            conexion.execute("DELETE FROM fragmento WHERE id_obra = ?", (id_obra,))

    def retirar_desde(self, id_obra: str, capitulo: int) -> int:
        """Saca del indice lo del capitulo N en adelante (RF-91).

        Es lo que se hace con un capitulo que no llego a cerrar: sus artefactos se
        caducan y sus fragmentos no pueden seguir recuperandose como eco (RF-64).
        El indice es derivado, asi que aqui si se borra.
        """
        conexion = self.almacen._escritor
        with self.almacen._turno_de_escritura, escritura(conexion):
            numeros = [
                fila["rowid"]
                for fila in conexion.execute(
                    "SELECT rowid FROM fragmento WHERE id_obra = ? AND capitulo >= ?",
                    (id_obra, capitulo),
                )
            ]
            for numero in numeros:
                conexion.execute("DELETE FROM fts_fragmento WHERE rowid = ?", (numero,))
                conexion.execute("DELETE FROM vec_fragmento WHERE fragmento = ?", (numero,))
                conexion.execute("DELETE FROM fragmento WHERE rowid = ?", (numero,))
        return len(numeros)

    def reconstruir(self, id_obra: str) -> int:
        """Borrarlo y rehacerlo desde los artefactos da los mismos fragmentos."""
        self.vaciar(id_obra)
        capitulos = sorted(
            {c.capitulo for c in self.almacen.listar("Capitulo", id_obra) if c.capitulo}
        )
        cuantos = 0
        for capitulo in capitulos:
            cuantos += self.indexar_fuentes(id_obra, capitulo)
            cuantos += self.indexar_prosa_aceptada(id_obra, capitulo)
            cuantos += self.indexar_estructura(id_obra, capitulo)
        return cuantos

    # --- Lectura del indice -------------------------------------------------

    def recuperar(
        self, id_obra: str, coleccion: str, consulta: str, rol: str, k: int | None = None
    ) -> list[dict[str, Any]]:
        """Busqueda hibrida sobre una coleccion, acotada a una obra.

        `k` sale del reparto por rol y lo recuperado se descuenta del tope de
        ventana de quien consulta: si no cabe, baja `k`, no sube el tope. Un rol
        con `k = 0` no consulta por parecido, y eso es diseno, no olvido.
        """
        if k is None:
            k = K_POR_ROL.get(rol, 0)
        if k <= 0:
            return []
        k = min(k, self._k_que_cabe(rol))
        if k <= 0:
            return []

        candidatos = max(k * 3, 10)
        por_parecido = self._por_parecido(id_obra, coleccion, consulta, candidatos)
        por_palabra = self._por_palabra(id_obra, coleccion, consulta, candidatos)
        numeros = _fundir(por_parecido, por_palabra)[:k]
        return [f.a_dict() for f in self._leer(numeros)]

    def _k_que_cabe(self, rol: str) -> int:
        tope = TOPE_DE_TOKENS_RECUPERADOS_POR_ROL.get(rol, 0)
        if tope <= 0:
            return 0
        por_fragmento = max(1, TAMANO_DE_FRAGMENTO_EN_CARACTERES // 4)
        del_rol = tope_de_ventana(rol)
        return max(0, min(tope, del_rol) // por_fragmento)

    def _por_parecido(
        self, id_obra: str, coleccion: str, consulta: str, cuantos: int
    ) -> list[int]:
        huella = self._huellas([consulta])[0]
        filas = self.almacen._lector.execute(
            "SELECT fragmento FROM vec_fragmento WHERE huella MATCH ? AND k = ? "
            "AND id_obra = ? AND coleccion = ? ORDER BY distance",
            (_a_blob(huella), cuantos, id_obra, coleccion),
        )
        return [int(fila["fragmento"]) for fila in filas]

    def _por_palabra(
        self, id_obra: str, coleccion: str, consulta: str, cuantos: int
    ) -> list[int]:
        termino = _termino_de_busqueda(consulta)
        if not termino:
            return []
        filas = self.almacen._lector.execute(
            "SELECT f.rowid AS numero FROM fts_fragmento AS t "
            "JOIN fragmento AS f ON f.rowid = t.rowid "
            "WHERE fts_fragmento MATCH ? AND f.id_obra = ? AND f.coleccion = ? "
            "ORDER BY bm25(fts_fragmento) LIMIT ?",
            (termino, id_obra, coleccion, cuantos),
        )
        return [int(fila["numero"]) for fila in filas]

    def _leer(self, numeros: list[int]) -> list[Fragmento]:
        if not numeros:
            return []
        huecos = ", ".join("?" * len(numeros))
        filas = {
            fila["rowid"]: fila
            for fila in self.almacen._lector.execute(
                f"SELECT rowid, * FROM fragmento WHERE rowid IN ({huecos})", numeros
            )
        }
        return [
            Fragmento(
                id=filas[numero]["id"],
                texto=filas[numero]["texto"],
                artefacto=filas[numero]["artefacto"],
                tipo_de_artefacto=filas[numero]["tipo_de_artefacto"],
                capitulo=filas[numero]["capitulo"],
                escena=filas[numero]["escena"],
                fecha=filas[numero]["fecha"],
                lugar=filas[numero]["lugar"],
                ambito=filas[numero]["ambito"],
            )
            for numero in numeros
            if numero in filas
        ]

    def modelos_en_uso(self, id_obra: str) -> set[str]:
        """Dos modelos conviviendo en el indice de una obra son un defecto."""
        return {
            fila["modelo"]
            for fila in self.almacen._lector.execute(
                "SELECT DISTINCT modelo FROM fragmento WHERE id_obra = ?", (id_obra,)
            )
        }


def _fundir(por_parecido: list[int], por_palabra: list[int]) -> list[int]:
    """Los dos ordenes se funden en uno solo antes de recortar a `k`."""
    puntos: dict[int, float] = {}
    for orden in (por_parecido, por_palabra):
        for puesto, numero in enumerate(orden, start=1):
            puntos[numero] = puntos.get(numero, 0.0) + 1 / (AMORTIGUADOR_DE_LA_FUSION + puesto)
    return sorted(puntos, key=lambda numero: (-puntos[numero], numero))


def _termino_de_busqueda(consulta: str) -> str:
    """FTS5 tiene sintaxis propia; la consulta entra como palabras sueltas."""
    palabras = [p for p in "".join(c if c.isalnum() else " " for c in consulta).split() if p]
    return " OR ".join(f'"{palabra}"' for palabra in palabras)


def _a_blob(huella: list[float]) -> bytes:
    import struct

    return struct.pack(f"{len(huella)}f", *huella)
