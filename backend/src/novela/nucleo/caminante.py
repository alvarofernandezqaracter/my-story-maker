"""La pieza que camina el guion.

No conoce el dominio: lee cual es el paso siguiente y lo ejecuta. Por eso no
hay coordinador y ningun agente manda sobre otro ni enruta. Lo unico que
decide aqui son las dos bifurcaciones declaradas —el enrutado por severidad y
el tope de vueltas— y ninguna de las dos mira el texto: miran la severidad de
las criticas, que es un valor cerrado.

El testigo se pasa siempre por artefacto escrito en el almacen: ningun rol
invoca a otro ni recibe objetos en memoria.

El unico punto de guardado es el capitulo cerrado (SPEC1 4.10). Caminar una
obra empieza siempre volviendo a el, sea el arranque, un `reanudar` o un
relanzamiento tras una caida: lo que quedo a medias se descarta y el capitulo
siguiente empieza en el paso 1. Cuantas veces se intenta cada tarea y que pasa
al agotarse lo declara su paso en el guion; aqui solo se lee.
"""

import threading
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol

from novela.ajustes import (
    CADA_CUANTOS_CAPITULOS_SE_AUDITA,
    TOPE_DE_REGENERACIONES_POR_ESCENA,
    TOPE_DE_REVISIONES_POR_BORRADOR,
)
from novela.almacen import Almacen, Artefacto, ArtefactoRechazado, esquema
from novela.almacen.artefactos import sumar_totales
from novela.nucleo import calidad, ciclo, guion, presupuesto
from novela.nucleo.gobierno import comprobar_escritura
from novela.nucleo.guion import Encargo
from novela.nucleo.proyecciones import Ventana, ensamblar
from novela.vocabularios import CICLO_DE_VIDA_DEL_CAPITULO, ESTADO_DE_PRODUCCION


class ProduccionDetenida(Exception):
    """El editor ha dado la orden de detener, o una tarea cuyo paso declara
    `detener_obra` agoto sus intentos."""


# Una tanda a la vez en toda la instalacion. El techo es de la instalacion y no
# de la obra (SPEC1 §11): si hay dos obras caminando —relanzar las caidas al
# arrancar lo hace—, sus tandas se turnan en vez de sumarse (D-88).
_UNA_TANDA_A_LA_VEZ = threading.Lock()


class PlanSinEscenas(Exception):
    """El Planificador no dejo escenas del capitulo: el intento falla (RF-182)."""


# Las unidades que son un capitulo o caben en uno: en sus encargos, el capitulo
# de lo que vuelve lo pone el encargo (RF-181). Lo de la obra entera, no.
UNIDADES_DE_CAPITULO = frozenset({"capitulo", "escena", "parrafo"})

# Los tipos cuyo `estado` es el ciclo de vida del proceso: ese lo lleva el
# caminante, no el rol que los escribe (RF-181).
ESTADO_DEL_PROCESO = frozenset(
    tabla.tipo
    for tabla in esquema.TABLAS
    if tabla.vocabulario_de_estado in (ESTADO_DE_PRODUCCION, CICLO_DE_VIDA_DEL_CAPITULO)
)


# Lo que una tarea devolvio y todavia no se ha escrito: el encargo y sus
# artefactos. Es lo que esperan el cierre del capitulo y la auditoria para
# escribirse de una vez, en su punto de guardado.
Aplazados = list[tuple[Encargo, list[Artefacto]]]


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
    fragmentos_usados: list[str] = field(default_factory=list)
    recuperaciones: list[dict[str, Any]] = field(default_factory=list)
    estado_en_n: dict[str, Any] | None = None
    # Lo que dijeron los hooks de su paso, si los lleva (SPEC1 RF-127).
    ganchos: dict[str, Any] | None = None
    # Lo que hace falta para observarlo en Langfuse (SPEC1 4.20): con que modelo
    # corrio y que herramientas llamo, leidas del flujo del CLI.
    modelo: str | None = None
    herramientas: list[dict[str, Any]] = field(default_factory=list)


class Ejecutor(Protocol):
    """Quien lanza la tarea. En seco devuelve artefactos preparados; de verdad
    lanza un subagente de Claude Code.

    Si admite varias tareas a la vez lo declara con `simultaneo = True`, y
    entonces cada tanda corre entera a la vez (SPEC1 D-88). Sin declararlo, la
    tanda se manda en serie: los ejecutores fingidos contestan segun el orden
    en que les llegan los encargos.
    """

    def ejecutar(self, encargo: Encargo, ventana: Ventana) -> Resultado: ...


class Observador(Protocol):
    """Quien mira la produccion desde fuera: Langfuse, si hay claves (SPEC1 4.20).

    Recibe lo ya leido y no devuelve nada: la produccion no depende de lo que
    haga, y un fallo suyo no para nada (RF-190). Lo que recibe cada aviso lo
    fija quien lo implementa; aqui solo se nombran.
    """

    @property
    def abrir_capitulo(self) -> Callable[..., Any]: ...

    @property
    def cerrar_capitulo(self) -> Callable[..., Any]: ...

    @property
    def abrir_tarea(self) -> Callable[..., Any]: ...

    @property
    def cerrar_tarea(self) -> Callable[..., Any]: ...

    @property
    def version_terminada(self) -> Callable[..., Any]: ...

    @property
    def soltar(self) -> Callable[..., Any]: ...


class IndiceDeLaObra(Protocol):
    """El indice visto desde el guion: se consulta y se alimenta.

    Se alimenta en tres momentos y ninguno mas: al recoger la `Fuente`, al
    aceptar la unidad —nunca antes— y al cerrar el capitulo.
    """

    def recuperar(
        self, id_obra: str, coleccion: str, consulta: str, rol: str
    ) -> list[dict[str, Any]]: ...

    def indexar_fuentes(self, id_obra: str, capitulo: int) -> int: ...

    def indexar_prosa_aceptada(self, id_obra: str, capitulo: int) -> int: ...

    def indexar_estructura(self, id_obra: str, capitulo: int) -> int: ...

    def retirar_desde(self, id_obra: str, capitulo: int) -> int: ...

    def retirar_capitulos(self, id_obra: str, capitulos: Iterable[int]) -> int: ...

    def retirar_sin_cerrar(self, id_obra: str, cerrados: Iterable[int]) -> int: ...


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
        indice: IndiceDeLaObra | None = None,
        observador: Observador | None = None,
    ) -> None:
        self.almacen = almacen
        self.ejecutor = ejecutor
        self.catalogo = catalogo
        self.indice = indice
        self.observador = observador
        self._tanda = 0
        # Lo pone la primera tarea de una tanda que detiene la obra. Las demas
        # de su tanda ya no intentan otra vez ni vuelven a detenerla: si el
        # editor reanuda mientras terminan, su orden no se deshace (D-88).
        self._detenida = threading.Event()
        self._turno_de_detener = threading.Lock()

    # --- La obra entera ----------------------------------------------------

    def caminar_obra(self, id_obra: str, capitulos: int) -> list[Informe]:
        """Del alta al ultimo capitulo cerrado, sin que nadie toque nada.

        Detener es una orden normal del editor, no una averia: la produccion se
        para donde este y lo cerrado se queda escrito. Arrancar, reanudar y
        relanzar tras una caida son este mismo camino: no hay dos formas de
        reanudar que puedan divergir (D-33).
        """
        informes: list[Informe] = []
        try:
            self.volver_al_punto_de_guardado(id_obra)
            if not self.almacen.listar("Personaje", id_obra):
                self._fuera_del_guion("poblar_mundo", id_obra)
            for numero in range(1, capitulos + 1):
                if not self._ya_cerrado(id_obra, numero):
                    informes.append(self.caminar_capitulo(id_obra, numero))
                self._auditar_si_toca(id_obra, numero, capitulos)
        except ProduccionDetenida:
            return informes
        except Exception as error:
            # Un fallo que no es de ninguna tarea —una ventana que no cabe ni
            # partiendo, una proyeccion incompleta— mataba el hilo y dejaba la
            # obra ni detenida ni terminada, sin nadie que la moviese (RF-167).
            # Se detiene con su motivo, como `detener_obra`, y se deja subir.
            self.almacen.detener(
                id_obra, f"fallo no previsto del caminante: {type(error).__name__}: {error}"
            )
            raise
        finally:
            # Lo que quede abierto se cierra como interrumpido: sin cerrar,
            # Langfuse no lo recibe (RF-185).
            self._observar("soltar", id_obra)
        return informes

    # --- Lo que ve Langfuse (SPEC1 4.20) ----------------------------------

    def _observar(self, metodo: str, *args: Any, **datos: Any) -> None:
        """Avisa al observador. Nada de lo que haga, ni un fallo suyo, ni leer lo
        que necesita, cambia la produccion (RF-190, RNF-10)."""
        if self.observador is None:
            return
        try:
            getattr(self.observador, metodo)(*args, **datos)
        except Exception:  # noqa: BLE001
            return

    def _de_la_obra(self, id_obra: str) -> dict[str, Any]:
        """La version en curso, la entrevista de la que sale y el titulo."""
        obra = self.almacen.leer_obra(id_obra)
        cuerpo = obra.cuerpo if obra is not None else {}
        return {
            "version": self.almacen.version_en_curso(id_obra),
            "id_entrevista": cuerpo.get("id_entrevista"),
            "titulo": cuerpo.get("titulo"),
        }

    def _observar_capitulo(self, id_obra: str, numero: int, *, abrir: bool) -> None:
        if self.observador is None:
            return
        try:
            obra = self._de_la_obra(id_obra)
            version = obra.pop("version")
            if abrir:
                self._observar("abrir_capitulo", id_obra, version, numero, **obra)
            else:
                totales = self.almacen.sumar_trazas(id_obra, version=version, capitulo=numero)
                self._observar("cerrar_capitulo", id_obra, version, numero, totales)
        except Exception:  # noqa: BLE001
            return

    def _observar_fin_de_version(self, id_obra: str) -> None:
        """Los totales de la version y los de la novela entera, entrevista
        incluida (RF-186)."""
        if self.observador is None:
            return
        try:
            obra = self._de_la_obra(id_obra)
            version = obra.pop("version")
            de_la_version = self.almacen.sumar_trazas(id_obra, version=version)
            partes = [self.almacen.sumar_trazas(id_obra)]
            if obra["id_entrevista"]:
                partes.append(self.almacen.sumar_pasadas(obra["id_entrevista"]))
            self._observar(
                "version_terminada",
                id_obra,
                version,
                totales_de_la_version=de_la_version,
                totales_de_la_novela=sumar_totales(*partes),
                **obra,
            )
        except Exception:  # noqa: BLE001
            return

    def _observar_tarea(
        self, encargo: Encargo, id_traza: str, intento: int, tokens: int
    ) -> None:
        if self.observador is None:
            return
        try:
            self._observar(
                "abrir_tarea",
                id_traza,
                id_obra=encargo.id_obra,
                rol=encargo.rol,
                tarea=encargo.tarea,
                intento=intento,
                capitulo=encargo.capitulo,
                escena=encargo.escena,
                dimension=encargo.dimension,
                tokens_estimados=tokens,
                **self._de_la_obra(encargo.id_obra),
            )
        except Exception:  # noqa: BLE001
            return

    def volver_al_punto_de_guardado(self, id_obra: str) -> int:
        """Deja la obra tal como quedo al cerrar su ultimo capitulo (RF-91).

        Las trazas que siguen abiertas son de tareas que corto una caida y se
        cierran como interrumpidas. Todo lo de cualquier capitulo sin cierre vivo
        se caduca y sale del indice —en una version que reescribe capitulos
        sueltos puede no ser solo el siguiente al ultimo cerrado (RF-176)—, y lo
        que a los cerrados les falte en el indice se indexa ahora; indexar lo ya
        indexado no hace nada. Devuelve el ultimo capitulo cerrado.
        """
        self.almacen.cerrar_trazas_interrumpidas(id_obra)
        self.almacen.descartar_sin_cerrar(id_obra)
        cerrados = self.almacen.capitulos_cerrados(id_obra)
        if self.indice is not None:
            self.indice.retirar_sin_cerrar(id_obra, cerrados)
            for cerrado in cerrados:
                self.indice.indexar_fuentes(id_obra, cerrado)
                self.indice.indexar_prosa_aceptada(id_obra, cerrado)
                self.indice.indexar_estructura(id_obra, cerrado)
        return max(cerrados, default=0)

    def _ya_cerrado(self, id_obra: str, numero: int) -> bool:
        """Lo cerrado no se repite: es el punto de guardado."""
        return any(
            capitulo.estado == "cerrado"
            for capitulo in self.almacen.listar("Capitulo", id_obra, capitulo=numero)
        )

    def _auditar_si_toca(self, id_obra: str, numero: int, capitulos: int) -> None:
        """`auditar` entra cada N capitulos y al cierre, con su propio punto de
        guardado: sus criticas y la constancia de hasta donde se audito se
        escriben juntas (RF-94). Si la de cadencia cae en el ultimo capitulo, es
        la de cierre y corre una sola vez."""
        toca = numero == capitulos or bool(
            CADA_CUANTOS_CAPITULOS_SE_AUDITA and numero % CADA_CUANTOS_CAPITULOS_SE_AUDITA == 0
        )
        if not toca or self.almacen.auditada_hasta(id_obra) >= numero:
            return
        aplazados: Aplazados = []
        self._fuera_del_guion("auditar", id_obra, capitulo=numero, aplazados=aplazados)
        self.almacen.guardar_auditoria(
            id_obra,
            numero,
            [artefactos for _, artefactos in aplazados],
            lambda lote, rechazo: self._critica_de_malformado(aplazados[lote][0], rechazo),
            # La de cierre termina la version en curso (RF-110): terminar no
            # publica, pero sin terminar no se publica.
            de_cierre=numero == capitulos,
        )
        if numero == capitulos:
            self._observar_fin_de_version(id_obra)

    def _fuera_del_guion(
        self,
        nombre: str,
        id_obra: str,
        *,
        capitulo: int | None = None,
        aplazados: Aplazados | None = None,
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
                    reintentos=paso.reintentos,
                    al_agotarse=paso.al_agotarse,
                )
                for contrato in guion.CRIBAS[paso.criba]
            ]
        else:
            encargos = guion.expandir(paso, id_obra=id_obra, capitulo=capitulo)
        return self._mandar_en_tandas(encargos, aplazados=aplazados)

    # --- Un capitulo -------------------------------------------------------

    def caminar_capitulo(self, id_obra: str, numero: int) -> Informe:
        informe = Informe(capitulo=numero)
        self._parar_si_detenida(id_obra)
        self._observar_capitulo(id_obra, numero, abrir=True)

        # Paso 1: planificar. Solo, y de el salen las escenas del capitulo.
        self._mandar_en_tandas(
            guion.expandir(guion.paso(1), id_obra=id_obra, capitulo=numero), informe
        )
        self._abrir_capitulo(id_obra, numero)
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
            if numero_de_paso == 2 and self.indice is not None:
                self.indice.indexar_fuentes(id_obra, numero)
        self._transitar(informe, id_obra, "redactado")

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
            self._dar_por_atendidas(enrutado.regenerar_escena, a_regenerar)
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
        self._transitar(informe, id_obra, "validado")

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
            self._dar_por_atendidas(enrutado.revision_dirigida, con_mayores)
            self._transitar(informe, id_obra, "en_revision")
            self._mandar_en_tandas(
                guion.expandir(
                    guion.paso(5), id_obra=id_obra, capitulo=numero, escenas=con_mayores
                ),
                informe,
            )
            # El 5 vuelve al 4: revisar puede meter una bloqueante.
            self._criba(id_obra, numero, con_mayores, 4, informe)
            self._transitar(informe, id_obra, "validado")

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
        if self.indice is not None:
            self.indice.indexar_prosa_aceptada(id_obra, numero)
        self._transitar(informe, id_obra, "aceptado")

        # Pasos 9 y 10: plegar y destilar. Cerrar es publicar los hechos y
        # olvidar el andamio, y es el punto de guardado: lo que devuelven las
        # dos tareas espera a que terminen ambas y entra de una vez, con la
        # marca `cerrado` y la retirada de la memoria de capitulo (RF-90).
        cerrado = ciclo.transitar(informe.estado, "cerrado")
        aplazados: Aplazados = []
        estado_en_n: dict[str, Any] | None = None
        for resultado in self._mandar_en_tandas(
            guion.expandir(guion.paso(9), id_obra=id_obra, capitulo=numero),
            informe,
            aplazados=aplazados,
        ):
            if resultado.estado_en_n is not None:
                estado_en_n = resultado.estado_en_n
        self._mandar_en_tandas(
            guion.expandir(guion.paso(10), id_obra=id_obra, capitulo=numero),
            informe,
            aplazados=aplazados,
        )
        self.almacen.cerrar_capitulo(
            id_obra,
            numero,
            [artefactos for _, artefactos in aplazados],
            estado_en_n,
            lambda lote, rechazo: self._critica_de_malformado(aplazados[lote][0], rechazo),
        )
        informe.estado = cerrado
        self._observar_capitulo(id_obra, numero, abrir=False)
        # El indice es derivado: si una caida lo deja a medias, volver al punto
        # de guardado lo completa.
        if self.indice is not None:
            self.indice.indexar_estructura(id_obra, numero)
        return informe

    def _abrir_capitulo(self, id_obra: str, numero: int) -> None:
        """Si el Planificador no escribio el `Capitulo`, lo escribe el backend:
        sin el, el ciclo de vida y la marca `cerrado` no tienen donde ir
        (RF-180)."""
        abiertos = self.almacen.listar("Capitulo", id_obra, capitulo=numero)
        for capitulo in abiertos:
            if capitulo.estado is None:
                self.almacen.marcar_capitulo(capitulo.id, "planificado")
        if abiertos:
            return
        self.almacen.guardar(
            [
                Artefacto(
                    tipo="Capitulo",
                    cuerpo={"numero": numero},
                    id_obra=id_obra,
                    capitulo=numero,
                    estado="planificado",
                )
            ]
        )

    def _transitar(self, informe: Informe, id_obra: str, hasta: str) -> None:
        """Mueve el capitulo por su ciclo de vida y lo deja escrito.

        Llevarlo solo en memoria haria que detener y reanudar perdiesen de vista
        por donde iba el capitulo.
        """
        informe.estado = ciclo.transitar(informe.estado, hasta)
        for capitulo in self.almacen.listar("Capitulo", id_obra, capitulo=informe.capitulo):
            self.almacen.marcar_capitulo(capitulo.id, hasta)

    def _dar_por_atendidas(
        self, criticas: list[Artefacto], escenas: tuple[str, ...]
    ) -> None:
        """Lo que se manda regenerar o revisar queda atendido.

        Lo que no se atiende se queda abierto, y con ello el capitulo se cierra
        marcado: es la anotacion que el Arquitecto de arcos vera en su siguiente
        auditoria.
        """
        for critica in criticas:
            if critica.id and critica.escena in escenas:
                self.almacen.resolver_critica(critica.id, "atendida")

    # --- El pliegue --------------------------------------------------------

    def _plegar_capitulo(
        self, id_obra: str, numero: int, informe: Informe | None = None
    ) -> None:
        """Paso 9: el Contable emite los eventos y el estado en N.

        El estado no se almacena, se deriva: lo que se guarda es una cache del
        pliegue que el Contable acaba de hacer.
        """
        resultados = self._mandar_en_tandas(
            guion.expandir(guion.paso(9), id_obra=id_obra, capitulo=numero), informe
        )
        for resultado in resultados:
            if resultado.estado_en_n is not None:
                self.almacen.materializar_estado(id_obra, numero, resultado.estado_en_n)

    def replegar_desde(self, id_obra: str, capitulo: int, hasta: int) -> None:
        """Regenerar el capitulo N descarta los estados de N en adelante y
        repliega hacia delante, capitulo a capitulo."""
        self.almacen.descartar_estados_desde(id_obra, capitulo)
        for numero in range(capitulo, hasta + 1):
            self._plegar_capitulo(id_obra, numero)

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
        self,
        encargos: Sequence[Encargo],
        informe: Informe | None = None,
        *,
        aplazados: Aplazados | None = None,
    ) -> list[Resultado]:
        """Manda los encargos en tandas. Con `aplazados`, lo que devuelvan no se
        escribe: se deja ahi para que su punto de guardado lo escriba de una vez."""
        # Cuando se abre una tanda no queda ninguna de antes corriendo: la que
        # detuvo la obra cerro entera antes de subir la excepcion.
        self._detenida.clear()
        resultados: list[Resultado] = []
        for tanda in presupuesto.repartir_en_tandas(encargos):
            with _UNA_TANDA_A_LA_VEZ:
                self._tanda += 1
                if informe is not None:
                    informe.recorrido.extend(
                        Apunte(
                            paso=encargo.paso,
                            tarea=encargo.tarea,
                            rol=encargo.rol,
                            tanda=self._tanda,
                            escena=encargo.escena,
                            dimension=encargo.dimension,
                        )
                        for encargo in tanda
                    )
                resultados.extend(self._mandar_tanda(tanda, aplazados))
        return resultados

    def _mandar_tanda(
        self, tanda: Sequence[Encargo], aplazados: Aplazados | None
    ) -> list[Resultado]:
        """Las tareas de una tanda corren a la vez y la tanda cierra cuando
        cierran todas (SPEC1 RF-13, D-88).

        Lo que devuelven se recoge en el orden del guion y no en el de llegada:
        es lo que deja el recorrido igual de una vez a otra (RNF-04). Si una
        detiene la obra, las demas ya estan abiertas y terminan; lo que dejen se
        descarta al volver al punto de guardado.
        """
        if len(tanda) == 1 or not getattr(self.ejecutor, "simultaneo", False):
            return [self._mandar(encargo, aplazados) for encargo in tanda]
        propios: list[Aplazados] = [[] for _ in tanda]
        resultados: list[Resultado | None] = [None] * len(tanda)
        errores: list[BaseException | None] = [None] * len(tanda)

        def correr(posicion: int) -> None:
            try:
                resultados[posicion] = self._mandar(
                    tanda[posicion], None if aplazados is None else propios[posicion]
                )
            except BaseException as error:  # noqa: BLE001
                errores[posicion] = error
            finally:
                # El hilo muere al cerrar la tanda y su lector con el.
                self.almacen.soltar_lector()

        # Hilos de la tanda y no un reparto que dure mas que ella: si el proceso
        # se apaga a mitad, no se queda esperando a subagentes cuyo resultado ya
        # no tiene donde guardarse, igual que el hilo de produccion.
        hilos = [
            threading.Thread(
                target=correr, args=(posicion,), name=f"tanda-{self._tanda}-{posicion}",
                daemon=True,
            )
            for posicion in range(len(tanda))
        ]
        for hilo in hilos:
            hilo.start()
        for hilo in hilos:
            hilo.join()
        if aplazados is not None:
            for propio in propios:
                aplazados.extend(propio)
        for error in errores:
            if error is not None:
                raise error
        return [resultado for resultado in resultados if resultado is not None]

    def _mandar(self, encargo: Encargo, aplazados: Aplazados | None = None) -> Resultado:
        """Ensambla, coteja, manda y guarda lo que vuelva.

        Se intenta tantas veces como declara el paso. Falla un intento cuando el
        ejecutor devuelve un error o no contesta a tiempo; un artefacto
        malformado no es un intento fallido, es la `Critica` de RF-23 (RF-98).
        """
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
            return self._partir_y_mandar(encargo, ventana, aplazados)

        ultimo_error: Exception | None = None
        id_traza = ""
        for intento in range(1, encargo.reintentos + 1):
            if self._detenida.is_set():
                raise ProduccionDetenida("otra tarea de la tanda detuvo la obra")
            id_traza = self.almacen.abrir_traza(
                encargo.id_obra,
                rol=encargo.rol,
                tarea=encargo.tarea,
                intento=intento,
                capitulo=encargo.capitulo,
                escena=encargo.escena,
                contexto=ventana.texto,
                # Lo que de verdad ocupa techo: la proyeccion mas lo que el
                # subagente arrastra de su parte. Asi la estimacion previa y la
                # medida exacta que el subagente devuelve miden lo mismo y se
                # pueden comparar tarea por tarea.
                tokens_estimados=presupuesto.coste_de_abrir(ventana.tokens),
            )
            self._observar_tarea(
                encargo, id_traza, intento, presupuesto.coste_de_abrir(ventana.tokens)
            )
            try:
                resultado = self.ejecutor.ejecutar(encargo, ventana)
                if aplazados is None:
                    self._guardar(encargo, resultado, id_traza, intento)
                else:
                    self._preparar(encargo, resultado, id_traza, intento)
                    if resultado.artefactos:
                        aplazados.append((encargo, resultado.artefactos))
            except Exception as error:  # noqa: BLE001
                ultimo_error = error
                self.almacen.cerrar_traza(
                    id_traza, salida=f"fallo: {error}", tokens_de_entrada_medidos=None,
                    tokens_de_salida=None, coste=None, latencia_ms=0,
                    # Un intento que no pasa un hook tambien deja su veredicto.
                    ganchos=getattr(error, "ganchos", None),
                )
                self._observar(
                    "cerrar_tarea",
                    id_traza,
                    error=f"fallo: {error}",
                    ganchos=getattr(error, "ganchos", None),
                )
                continue
            self.almacen.cerrar_traza(
                id_traza,
                salida=resultado.salida,
                tokens_de_entrada_medidos=resultado.tokens_de_entrada_medidos,
                tokens_de_salida=resultado.tokens_de_salida,
                coste=resultado.coste,
                latencia_ms=resultado.latencia_ms,
                recuperaciones=[
                    recuperacion | {"usados": resultado.fragmentos_usados}
                    for recuperacion in ventana.recuperaciones
                ],
                ganchos=resultado.ganchos,
            )
            self._observar(
                "cerrar_tarea",
                id_traza,
                salida=resultado.salida,
                tokens_de_entrada=resultado.tokens_de_entrada_medidos,
                tokens_de_salida=resultado.tokens_de_salida,
                coste=resultado.coste,
                latencia_ms=resultado.latencia_ms,
                modelo=resultado.modelo,
                herramientas=resultado.herramientas,
                ganchos=resultado.ganchos,
            )
            return resultado

        return self._agotado(encargo, id_traza, ultimo_error, aplazados)

    def _agotado(
        self,
        encargo: Encargo,
        id_traza: str,
        error: Exception | None,
        aplazados: Aplazados | None,
    ) -> Resultado:
        """Lo que pasa cuando se agotan los intentos lo dice el paso, no se
        improvisa aqui (RF-96)."""
        motivo = f"{encargo.tarea}: {error}"
        if encargo.al_agotarse == "seguir":
            # La constancia del intento ya esta en la `Traza`, como la busqueda
            # infructuosa de RF-69: la produccion sigue.
            return Resultado(salida=f"agotado, se sigue: {motivo}")
        if encargo.al_agotarse == "critica_abierta":
            critica = self._critica_no_comprobado(encargo, id_traza, error)
            if aplazados is None:
                self.almacen.guardar_critica(critica)
            else:
                aplazados.append((encargo, [critica]))
            return Resultado(salida=f"no comprobado: {motivo}")
        with self._turno_de_detener:
            primera = not self._detenida.is_set()
            self._detenida.set()
        if primera:
            self.almacen.detener(
                encargo.id_obra, f"{motivo} (intento {encargo.reintentos}, traza {id_traza})"
            )
        raise ProduccionDetenida(f"la tarea {encargo.tarea!r} agoto sus intentos: {error}")

    def _partir_y_mandar(
        self, encargo: Encargo, ventana: Ventana, aplazados: Aplazados | None = None
    ) -> Resultado:
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
        partes = [self._mandar(trozo, aplazados) for trozo in trozos]
        return Resultado(
            artefactos=[a for parte in partes for a in parte.artefactos],
            salida="\n".join(parte.salida for parte in partes),
        )

    def _preparar(
        self, encargo: Encargo, resultado: Resultado, id_traza: str, intento: int
    ) -> None:
        """Los permisos se imponen aqui y no en el prompt, y la procedencia la
        pone el backend. Tambien a que capitulo va y en que punto de su ciclo
        de vida esta: eso no lo decide el rol (RF-181). Y la escena: la del
        encargo, o una del capitulo, nunca un `id` inventado (RF-216)."""
        del_capitulo = encargo.unidad in UNIDADES_DE_CAPITULO and encargo.capitulo is not None
        validas: set[str] | None = None
        if encargo.unidad == "capitulo" and encargo.tarea != "planificar" and del_capitulo:
            validas = {
                escena.id
                for escena in self.almacen.listar(
                    "Escena", encargo.id_obra, capitulo=encargo.capitulo
                )
            }
        for artefacto in resultado.artefactos:
            comprobar_escritura(encargo.rol, artefacto.tipo)
            artefacto.id_obra = artefacto.id_obra or encargo.id_obra
            artefacto.procedencia_rol = encargo.rol
            artefacto.procedencia_tarea = id_traza
            artefacto.procedencia_intento = intento
            if del_capitulo or artefacto.capitulo is None:
                artefacto.capitulo = encargo.capitulo
            if encargo.unidad == "escena" and encargo.escena is not None:
                artefacto.escena = encargo.escena
            elif validas is not None and artefacto.escena not in validas:
                artefacto.escena = None
            if artefacto.tipo in ESTADO_DEL_PROCESO:
                artefacto.estado = None

    def _guardar(
        self, encargo: Encargo, resultado: Resultado, id_traza: str, intento: int
    ) -> None:
        """Guarda lo producido, con los permisos impuestos aqui y no en el prompt."""
        self._preparar(encargo, resultado, id_traza, intento)
        if encargo.tarea == "planificar":
            self._guardar_el_plan(resultado.artefactos)
            return
        if not resultado.artefactos:
            return
        try:
            self.almacen.guardar(resultado.artefactos)
        except ArtefactoRechazado as rechazo:
            # Campo obligatorio ausente o valor fuera de vocabulario: el
            # rechazo es una `Critica` bloqueante cuyo objeto es el artefacto,
            # no el texto, y no llega al Revisor como si fuera prosa mala.
            self.almacen.guardar_critica(self._critica_de_malformado(encargo, rechazo))

    def _guardar_el_plan(self, artefactos: list[Artefacto]) -> None:
        """Sin escenas del capitulo no hay testigo para nadie: el intento falla
        y no se escribe nada de el, tampoco la critica de RF-23 (RF-182)."""
        if not any(artefacto.tipo == "Escena" for artefacto in artefactos):
            raise PlanSinEscenas("el plan no trae ninguna Escena del capitulo")
        try:
            self.almacen.guardar(artefactos)
        except ArtefactoRechazado as rechazo:
            raise PlanSinEscenas(f"el almacen rechazo el plan: {rechazo}") from rechazo

    @staticmethod
    def _critica_de_malformado(encargo: Encargo, rechazo: ArtefactoRechazado) -> Artefacto:
        """La escribe el backend, no un rol: ningun agente valida su salida."""
        return Artefacto(
            tipo="Critica",
            cuerpo={
                "objeto": encargo.escena or f"capitulo {encargo.capitulo}",
                "evidencia": str(rechazo),
                "accion_sugerida": "volver a escribir el artefacto con su esquema",
                "detectada_por": {"rol": None, "tarea": encargo.tarea},
            },
            id_obra=encargo.id_obra,
            capitulo=encargo.capitulo,
            escena=encargo.escena,
            severidad="bloqueante",
            estado="abierta",
        )

    @staticmethod
    def _critica_no_comprobado(
        encargo: Encargo, id_traza: str, error: Exception | None
    ) -> Artefacto:
        """Una comprobacion que agoto sus intentos no se da por buena (RF-99).

        La escribe el backend, como la de un artefacto malformado. No se enruta:
        no regenera ni manda a revision. Se queda abierta y el capitulo se cierra
        marcado, que es como el Arquitecto de arcos la ve.
        """
        return Artefacto(
            tipo="Critica",
            cuerpo={
                "objeto": encargo.escena or f"capitulo {encargo.capitulo}",
                "evidencia": (
                    f"no comprobado: traza {id_traza}, intento {encargo.reintentos} "
                    f"de {encargo.reintentos}: {error}"
                ),
                "accion_sugerida": "volver a comprobar la dimension en la siguiente auditoria",
                "detectada_por": {"rol": None, "tarea": encargo.tarea},
            },
            id_obra=encargo.id_obra,
            capitulo=encargo.capitulo,
            escena=encargo.escena,
            dimension=encargo.dimension,
            severidad="bloqueante",
            estado="abierta",
        )

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


# Los topes de vueltas del bucle. Los de reintentos no estan aqui: cada paso del
# guion declara el suyo junto a lo que pasa al agotarse (RF-95).
TOPES = {
    "regeneraciones_por_escena": TOPE_DE_REGENERACIONES_POR_ESCENA,
    "revisiones_por_borrador": TOPE_DE_REVISIONES_POR_BORRADOR,
}
