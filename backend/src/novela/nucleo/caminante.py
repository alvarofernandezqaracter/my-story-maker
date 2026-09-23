"""La pieza que camina el guion.

No conoce el dominio: lee cual es el paso siguiente y lo ejecuta. Por eso no
hay coordinador y ningun agente manda sobre otro ni enruta. Lo unico que
decide aqui son las dos bifurcaciones declaradas —el enrutado por severidad y
el tope de vueltas— y ninguna de las dos mira el texto: miran la severidad de
las criticas, que es un valor cerrado.

El testigo se pasa siempre por artefacto escrito en el almacen: ningun rol
invoca a otro ni recibe objetos en memoria.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol

from novela.ajustes import (
    CADA_CUANTOS_CAPITULOS_SE_AUDITA,
    TOPE_DE_REGENERACIONES_POR_ESCENA,
    TOPE_DE_REINTENTOS_POR_TAREA,
    TOPE_DE_REVISIONES_POR_BORRADOR,
)
from novela.almacen import Almacen, Artefacto
from novela.nucleo import calidad, ciclo, guion, presupuesto
from novela.nucleo.gobierno import comprobar_escritura
from novela.nucleo.guion import Encargo
from novela.nucleo.proyecciones import Indice, Ventana, ensamblar


class ProduccionDetenida(Exception):
    """El editor ha dado la orden de detener, o una tarea agoto sus intentos."""


@dataclass
class Resultado:
    """Lo que devuelve un subagente cuando termina su encargo."""

    artefactos: list[Artefacto] = field(default_factory=list)
    salida: str = ""
    tokens_de_entrada_medidos: int | None = None
    tokens_de_salida: int | None = None
    coste: float | None = None
    latencia_ms: int = 0
    constancia: dict[str, Any] | None = None
    recuperaciones: list[dict[str, Any]] = field(default_factory=list)
    estado_en_n: dict[str, Any] | None = None


class Ejecutor(Protocol):
    """Quien lanza la tarea. En seco devuelve artefactos preparados; de verdad
    lanza un subagente de Claude Code."""

    def ejecutar(self, encargo: Encargo, ventana: Ventana) -> Resultado: ...


class Catalogo(Protocol):
    """De donde salen el contrato y la proyeccion minima de cada dimension."""

    def contrato(self, tarea: str, dimension: str | None) -> dict[str, Any] | None: ...

    def proyeccion_minima(self, tarea: str, dimension: str | None) -> tuple[str, ...]: ...


@dataclass
class Apunte:
    """Una linea del recorrido: quien hizo que, en que tanda."""

    paso: int
    tarea: str
    rol: str
    tanda: int
    escena: str | None = None
    dimension: str | None = None


@dataclass
class Informe:
    """Lo que quedo de caminar un capitulo."""

    capitulo: int
    recorrido: list[Apunte] = field(default_factory=list)
    estado: str = "planificado"
    marcado: bool = False
    criticas_abiertas: int = 0
    descartadas_sin_evidencia: int = 0


class Caminante:
    def __init__(
        self,
        almacen: Almacen,
        ejecutor: Ejecutor,
        *,
        catalogo: Catalogo | None = None,
        indice: Indice | None = None,
    ) -> None:
        self.almacen = almacen
        self.ejecutor = ejecutor
        self.catalogo = catalogo
        self.indice = indice
        self._tanda = 0

    # --- La obra entera ----------------------------------------------------

    def caminar_obra(self, id_obra: str, capitulos: int) -> list[Informe]:
        """Del alta al ultimo capitulo cerrado, sin que nadie toque nada."""
        self._fuera_del_guion("poblar_mundo", id_obra)
        informes = []
        for numero in range(1, capitulos + 1):
            informes.append(self.caminar_capitulo(id_obra, numero))
            if CADA_CUANTOS_CAPITULOS_SE_AUDITA and (
                numero % CADA_CUANTOS_CAPITULOS_SE_AUDITA == 0
            ):
                self._fuera_del_guion("auditar", id_obra, capitulo=numero)
        self._fuera_del_guion("auditar", id_obra, capitulo=capitulos)
        return informes

    def _fuera_del_guion(
        self, nombre: str, id_obra: str, *, capitulo: int | None = None
    ) -> list[Resultado]:
        """`poblar_mundo` y `auditar` no tienen la cadencia del capitulo y van
        siempre solas."""
        paso = guion.FUERA_DEL_GUION[nombre]
        if paso.criba:
            encargos = [
                Encargo(
                    paso=0,
                    tarea=paso.tarea,
                    rol=contrato.rol,
                    unidad=paso.unidad,
                    proyeccion=paso.proyeccion,
                    id_obra=id_obra,
                    capitulo=capitulo,
                    dimension=contrato.dimension,
                )
                for contrato in guion.CRIBAS[paso.criba]
            ]
        else:
            encargos = guion.expandir(paso, id_obra=id_obra, capitulo=capitulo)
        return self._mandar_en_tandas(encargos)

    # --- Un capitulo -------------------------------------------------------

    def caminar_capitulo(self, id_obra: str, numero: int) -> Informe:
        informe = Informe(capitulo=numero)
        self._parar_si_detenida(id_obra)

        # Paso 1: planificar. Solo, y de el salen las escenas del capitulo.
        self._mandar_en_tandas(
            guion.expandir(guion.paso(1), id_obra=id_obra, capitulo=numero), informe
        )
        escenas = self._escenas(id_obra, numero)
        informe.estado = "planificado"

        # Pasos 2 y 3: documentar y redactar, uno por escena y en tanda.
        for numero_de_paso in (2, 3):
            self._mandar_en_tandas(
                guion.expandir(
                    guion.paso(numero_de_paso),
                    id_obra=id_obra,
                    capitulo=numero,
                    escenas=escenas,
                ),
                informe,
            )
        informe.estado = ciclo.transitar(informe.estado, "redactado")

        regeneraciones: dict[str, int] = dict.fromkeys(escenas, 0)
        revisiones: dict[str, int] = dict.fromkeys(escenas, 0)

        # Paso 4: criba de bloqueantes. Una bloqueante regenera la escena.
        pendientes = escenas
        while pendientes:
            enrutado = self._criba(id_obra, numero, pendientes, 4, informe)
            informe.descartadas_sin_evidencia += len(enrutado.descartadas_sin_evidencia)
            afectadas = {c.escena for c in enrutado.regenerar_escena if c.escena}
            a_regenerar = self._en_orden(
                escenas,
                {e for e in afectadas if calidad.queda_regeneracion(regeneraciones[e])},
            )
            if not a_regenerar:
                break
            for escena in a_regenerar:
                regeneraciones[escena] += 1
            self._mandar_en_tandas(
                guion.expandir(
                    guion.paso(3),
                    id_obra=id_obra,
                    capitulo=numero,
                    escenas=a_regenerar,
                ),
                informe,
            )
            pendientes = a_regenerar
        informe.estado = ciclo.transitar(informe.estado, "validado")

        # Pasos 5 y 6: revision dirigida y criba de mayores. El 5 vuelve al 4.
        for _ in range(TOPE_DE_REVISIONES_POR_BORRADOR + 1):
            enrutado = self._criba(id_obra, numero, escenas, 6, informe)
            informe.descartadas_sin_evidencia += len(enrutado.descartadas_sin_evidencia)
            con_mayores = self._en_orden(
                escenas,
                {
                    c.escena
                    for c in enrutado.revision_dirigida
                    if c.escena and calidad.queda_revision(revisiones[c.escena])
                },
            )
            if not con_mayores:
                break
            for escena in con_mayores:
                revisiones[escena] += 1
            informe.estado = ciclo.transitar(informe.estado, "en_revision")
            self._mandar_en_tandas(
                guion.expandir(
                    guion.paso(5), id_obra=id_obra, capitulo=numero, escenas=con_mayores
                ),
                informe,
            )
            # El 5 vuelve al 4: revisar puede meter una bloqueante.
            self._criba(id_obra, numero, con_mayores, 4, informe)
            informe.estado = ciclo.transitar(informe.estado, "validado")

        # Paso 7: costura del capitulo.
        self._mandar_en_tandas(
            guion.expandir(guion.paso(7), id_obra=id_obra, capitulo=numero), informe
        )

        # Paso 8: criba de pulido, una sola vez sobre el capitulo ya cosido.
        enrutado = self._criba(id_obra, numero, escenas, 8, informe)
        informe.descartadas_sin_evidencia += len(enrutado.descartadas_sin_evidencia)

        abiertas = self.almacen.listar_criticas_abiertas(id_obra)
        informe.criticas_abiertas = len(abiertas)
        informe.marcado = any(c.severidad == "bloqueante" for c in abiertas)

        # De `Validado` a `Aceptado`: sin criticas bloqueantes, o con el tope
        # agotado y sus criticas abiertas anotadas. Solo al aceptar la unidad
        # se indexa su texto, nunca antes.
        for escena in escenas:
            vigente = self.almacen.borrador_vigente(id_obra, escena)
            if vigente is not None and vigente.estado != "aceptado":
                self.almacen.aceptar_borrador(vigente.id)
        informe.estado = ciclo.transitar(informe.estado, "aceptado")

        # Pasos 9 y 10: plegar y destilar. Cerrar es publicar los hechos y
        # olvidar el andamio.
        for numero_de_paso in (9, 10):
            resultados = self._mandar_en_tandas(
                guion.expandir(guion.paso(numero_de_paso), id_obra=id_obra, capitulo=numero),
                informe,
            )
            if numero_de_paso == 9:
                for resultado in resultados:
                    if resultado.estado_en_n is not None:
                        self.almacen.materializar_estado(
                            id_obra, numero, resultado.estado_en_n
                        )
        informe.estado = ciclo.transitar(informe.estado, "cerrado")
        self.almacen.caducar_memoria_de_capitulo(id_obra, numero)
        return informe

    # --- Cribas ------------------------------------------------------------

    def _criba(
        self,
        id_obra: str,
        capitulo: int,
        escenas: tuple[str, ...],
        numero_de_paso: int,
        informe: Informe,
    ) -> calidad.Enrutado:
        paso = guion.paso(numero_de_paso)
        encargos = guion.expandir(paso, id_obra=id_obra, capitulo=capitulo, escenas=escenas)
        resultados = self._mandar_en_tandas(encargos, informe)
        criticas = [
            artefacto
            for resultado in resultados
            for artefacto in resultado.artefactos
            if artefacto.tipo == "Critica"
        ]
        enrutado = calidad.enrutar(criticas)
        for critica in enrutado.descartadas_sin_evidencia:
            if critica.id:
                self.almacen.resolver_critica(critica.id, "descartada")
        return enrutado

    # --- Mandar encargos ---------------------------------------------------

    def _mandar_en_tandas(
        self, encargos: Sequence[Encargo], informe: Informe | None = None
    ) -> list[Resultado]:
        resultados: list[Resultado] = []
        for tanda in presupuesto.repartir_en_tandas(encargos):
            self._tanda += 1
            for encargo in tanda:
                if informe is not None:
                    informe.recorrido.append(
                        Apunte(
                            paso=encargo.paso,
                            tarea=encargo.tarea,
                            rol=encargo.rol,
                            tanda=self._tanda,
                            escena=encargo.escena,
                            dimension=encargo.dimension,
                        )
                    )
                resultados.append(self._mandar(encargo))
        return resultados

    def _mandar(self, encargo: Encargo) -> Resultado:
        """Ensambla, coteja, manda y guarda lo que vuelva."""
        self._parar_si_detenida(encargo.id_obra)
        contrato = None
        proyeccion_del_contrato: tuple[str, ...] = ()
        if self.catalogo is not None:
            contrato = self.catalogo.contrato(encargo.tarea, encargo.dimension)
            proyeccion_del_contrato = self.catalogo.proyeccion_minima(
                encargo.tarea, encargo.dimension
            )

        ventana = ensamblar(
            self.almacen,
            encargo,
            contrato=contrato,
            indice=self.indice,
            proyeccion_del_contrato=proyeccion_del_contrato,
        )
        if not presupuesto.cabe_en_la_ventana(encargo.tope_de_ventana, ventana.tokens):
            return self._partir_y_mandar(encargo, ventana)

        ultimo_error: Exception | None = None
        for intento in range(1, TOPE_DE_REINTENTOS_POR_TAREA + 1):
            id_traza = self.almacen.abrir_traza(
                encargo.id_obra,
                rol=encargo.rol,
                tarea=encargo.tarea,
                intento=intento,
                capitulo=encargo.capitulo,
                escena=encargo.escena,
                contexto=ventana.texto,
                tokens_estimados=ventana.tokens,
            )
            try:
                resultado = self.ejecutor.ejecutar(encargo, ventana)
                self._guardar(encargo, resultado, id_traza, intento)
            except Exception as error:  # noqa: BLE001
                ultimo_error = error
                self.almacen.cerrar_traza(
                    id_traza, salida=f"fallo: {error}", tokens_de_entrada_medidos=None,
                    tokens_de_salida=None, coste=None, latencia_ms=0,
                )
                continue
            self.almacen.cerrar_traza(
                id_traza,
                salida=resultado.salida,
                tokens_de_entrada_medidos=resultado.tokens_de_entrada_medidos,
                tokens_de_salida=resultado.tokens_de_salida,
                coste=resultado.coste,
                latencia_ms=resultado.latencia_ms,
                recuperaciones=resultado.recuperaciones,
            )
            return resultado

        self.almacen.detener(encargo.id_obra, f"{encargo.tarea}: {ultimo_error}")
        raise ProduccionDetenida(
            f"la tarea {encargo.tarea!r} agoto sus intentos: {ultimo_error}"
        )

    def _partir_y_mandar(self, encargo: Encargo, ventana: Ventana) -> Resultado:
        """Si la proyeccion no cabe, se parte la unidad. Nunca se recorta."""
        siguiente = presupuesto.partir_unidad(encargo.unidad)
        if siguiente == "escena":
            escenas = self._escenas(encargo.id_obra, encargo.capitulo or 0)
            trozos = [
                Encargo(**{**encargo.__dict__, "unidad": siguiente, "escena": escena})
                for escena in escenas
            ]
        elif siguiente == "parrafo":
            parrafos = self.almacen.listar(
                "Parrafo", encargo.id_obra, escena=encargo.escena, orden="orden"
            )
            trozos = [
                Encargo(**{**encargo.__dict__, "unidad": siguiente, "escena": parrafo.id})
                for parrafo in parrafos
            ]
        else:
            raise presupuesto.NoCabeNiPartiendo(f"no se puede partir {encargo.unidad}")
        if not trozos:
            raise presupuesto.NoCabeNiPartiendo(
                f"la ventana de {encargo.tarea} no cabe y no hay en que partirla"
            )
        partes = [self._mandar(trozo) for trozo in trozos]
        return Resultado(
            artefactos=[a for parte in partes for a in parte.artefactos],
            salida="\n".join(parte.salida for parte in partes),
        )

    def _guardar(
        self, encargo: Encargo, resultado: Resultado, id_traza: str, intento: int
    ) -> None:
        """Guarda lo producido, con los permisos impuestos aqui y no en el prompt."""
        for artefacto in resultado.artefactos:
            comprobar_escritura(encargo.rol, artefacto.tipo)
            artefacto.id_obra = artefacto.id_obra or encargo.id_obra
            artefacto.procedencia_rol = encargo.rol
            artefacto.procedencia_tarea = id_traza
            artefacto.procedencia_intento = intento
            if artefacto.capitulo is None:
                artefacto.capitulo = encargo.capitulo
        if resultado.artefactos:
            self.almacen.guardar(resultado.artefactos)

    # --- Apoyos ------------------------------------------------------------

    @staticmethod
    def _en_orden(escenas: tuple[str, ...], elegidas: set[str | None]) -> tuple[str, ...]:
        """El orden lo pone el capitulo, nunca el `id` opaco de la escena.

        Ordenar por `id` haria que dos recorridos identicos dieran secuencias
        distintas, y el guion tiene que ser reproducible (RNF-04).
        """
        return tuple(escena for escena in escenas if escena in elegidas)

    def _escenas(self, id_obra: str, capitulo: int) -> tuple[str, ...]:
        return tuple(
            escena.id
            for escena in self.almacen.listar(
                "Escena", id_obra, capitulo=capitulo, orden="orden"
            )
        )

    def _parar_si_detenida(self, id_obra: str) -> None:
        if self.almacen.esta_detenida(id_obra):
            raise ProduccionDetenida("la produccion esta detenida por orden del editor")


TOPES = {
    "regeneraciones_por_escena": TOPE_DE_REGENERACIONES_POR_ESCENA,
    "revisiones_por_borrador": TOPE_DE_REVISIONES_POR_BORRADOR,
    "reintentos_por_tarea": TOPE_DE_REINTENTOS_POR_TAREA,
}
