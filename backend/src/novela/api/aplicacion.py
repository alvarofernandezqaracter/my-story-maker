"""Las operaciones del editor: la entrevista que completa el brief, el alta de
la obra y lo que hace falta para verla y controlarla.

Cada una es un procedimiento de principio a fin. Los mensajes de error van en
espanol. La interfaz web nunca lee ficheros ni la base de datos: todo lo que
muestra lo pide aqui.
"""

import threading
from collections.abc import AsyncIterable, AsyncIterator, Iterator
from contextlib import asynccontextmanager
from typing import Annotated, Any, Literal, cast, get_origin

from fastapi import Depends, FastAPI, HTTPException, Path, Query, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from fastapi.sse import EventSourceResponse, ServerSentEvent
from pydantic import BaseModel, ValidationError

from novela import __version__
from novela import observabilidad as observacion
from novela.ajustes import (
    PASADAS_DE_ENTREVISTA_A_LA_VEZ,
    RUTA_DE_LA_BASE,
    TECHO_DE_CONTEXTO_CONCURRENTE,
    tope_de_ventana,
)
from novela.almacen import Almacen, Artefacto
from novela.almacen.artefactos import (
    EscrituraProhibida,
    HechoSinMenciones,
    VersionNoAdmitida,
    abrir_almacen,
    ahora,
)
from novela.almacen.indice import Indice
from novela.api.modelos import (
    Brief,
    CapituloInspeccionado,
    Confirmacion,
    Contradiccion,
    CriticaServida,
    Cronologia,
    DecisionDePolicy,
    Destinatario,
    EstadoPlegado,
    FichaDeObra,
    HechoDeLaBiblia,
    HechoDescartado,
    HechoExtraido,
    Manuscrito,
    ObraCreada,
    ObraDelTaller,
    Orden,
    PasadaDeEntrevista,
    Pasaje,
    PeticionDeCambio,
    PeticionDeEntrevista,
    PeticionDeRehacer,
    Progreso,
    Publicacion,
    PuertaDePublicacion,
    RechazoDePublicacion,
    SituacionDeLaObra,
    Suceso,
    TrazaServida,
    UnidadDelManuscrito,
    VersionAbierta,
    VersionDeLaObra,
)
from novela.api.pdf import CapituloDelPdf, manuscrito_en_pdf
from novela.demostrador import DemostradorLean
from novela.ejecutor import EjecutorDeSubagentes, SubagenteFallo
from novela.nucleo import entrevista, versiones
from novela.nucleo.caminante import Caminante
from novela.nucleo.gobierno import puede_escribir
from novela.tareas import CatalogoDelRepositorio, prompt_de_tarea, tareas_declaradas


def _rutas_del_brief() -> tuple[frozenset[str], frozenset[str]]:
    """Los campos a los que puede ir un hecho, sacados del modelo del brief.

    El modelo es el unico sitio con tipos, asi que es el que dice que campos hay:
    `nucleo/` recibe las rutas y no las repite. `politicas_globales` no es un
    campo al que se llegue desde un texto pegado.
    """
    escalares: set[str] = set()
    listas: set[str] = set()

    def recorrer(modelo: type[BaseModel], prefijo: str) -> None:
        for nombre, campo in modelo.model_fields.items():
            ruta = prefijo + nombre
            if nombre == "destinatario":
                recorrer(Destinatario, ruta + ".")
            elif get_origin(campo.annotation) is list:
                listas.add(ruta)
            elif get_origin(campo.annotation) is not dict:
                escalares.add(ruta)

    recorrer(Brief, "")
    return frozenset(escalares), frozenset(listas)


ESCALARES_DEL_BRIEF, LISTAS_DEL_BRIEF = _rutas_del_brief()


def _alta(brief: Brief) -> tuple[dict[str, Any], list[str]]:
    """El cuerpo de la `Obra` y sus recuerdos, que salen de el como `Recuerdo`.

    La capa Obra referencia la capa Mundo, no la duplica.
    """
    cuerpo = brief.model_dump()
    recuerdos: list[str] = []
    if brief.destinatario is not None:
        recuerdos = list(brief.destinatario.recuerdos)
        cuerpo["destinatario"].pop("recuerdos", None)
    return cuerpo, recuerdos


def _validar(propuesta: entrevista.Propuesta) -> tuple[Brief | None, list[str], list[str]]:
    """Valida el brief propuesto contra el mismo modelo que `POST /obras` (RF-72).

    Lo que el agente aporto y el modelo no admite se quita, y el campo vuelve a
    faltar (RF-73). Lo que escribio la persona no se toca: si no vale, se dice.
    """
    while True:
        try:
            return Brief.model_validate(propuesta.brief), [], []
        except ValidationError as error:
            fallos = [(".".join(str(p) for p in f["loc"]), f) for f in error.errors()]
            del_agente = sorted({ruta for ruta, _ in fallos if ruta in propuesta.aportados})
            if not del_agente:
                faltan = [ruta for ruta, fallo in fallos if fallo["type"] == "missing"]
                no_validos = [
                    f"{ruta}: {fallo['msg']}"
                    for ruta, fallo in fallos
                    if fallo["type"] != "missing"
                ]
                return None, faltan, no_validos
            for ruta in del_agente:
                propuesta.retirar(ruta, "el brief no admite ese valor")


class Produccion:
    """Lo que la aplicacion necesita tener abierto: el almacen y quien camina."""

    def __init__(
        self,
        ruta: Any = None,
        ejecutor: Any = None,
        demostrador: Any = None,
        observabilidad: observacion.Observabilidad | None = None,
    ) -> None:
        self.almacen: Almacen = abrir_almacen(ruta or RUTA_DE_LA_BASE)
        self.indice = Indice(self.almacen)
        self.catalogo = CatalogoDelRepositorio()
        self.ejecutor = ejecutor or EjecutorDeSubagentes(catalogo=self.catalogo)
        # Quien demuestra la cronologia en la puerta: Lean con `lake build`
        # (SPEC1 4.16). Si Lean no esta en la maquina, la puerta lo dice y no
        # bloquea por eso (D-61).
        self.demostrador = demostrador or DemostradorLean()
        self.hilos: dict[str, threading.Thread] = {}
        # Leer el hilo anterior de una obra y registrar el nuevo van juntos (RF-166).
        self._turno_de_arranque = threading.Lock()
        # Una pasada de entrevista a la vez en la instalacion: es lo que hace que
        # quepa en el margen del techo (SPEC1 RF-70).
        self.turno_de_entrevista = threading.BoundedSemaphore(PASADAS_DE_ENTREVISTA_A_LA_VEZ)
        # Langfuse, si hay claves; si no, apagada y sin coste (SPEC1 4.20). Los
        # prompts de todas las tareas se versionan al arrancar, sin esperar a la
        # red (RF-188).
        self.observabilidad = observabilidad or observacion.actual()
        self.observabilidad.leer_prompt = prompt_de_tarea
        self.hilo_de_los_prompts = self.observabilidad.registrar_prompts_en_segundo_plano(
            tareas_declaradas()
        )

    def caminante(self) -> Caminante:
        return Caminante(
            self.almacen,
            self.ejecutor,
            catalogo=self.catalogo,
            indice=self.indice,
            observador=self.observabilidad if self.observabilidad.activa else None,
        )

    def arrancar(self, id_obra: str, capitulos: int) -> None:
        """Arranca la produccion completa y devuelve el turno enseguida.

        Es la unica orden que el editor tiene que dar: de aqui al ultimo
        capitulo cerrado no hay ninguna otra. Si la misma obra todavia tiene un
        hilo vivo —se detuvo y se reanudo mientras una tarea seguia abierta—, el
        nuevo espera a que ese termine antes de volver al punto de guardado: dos
        caminantes sobre la misma obra se descartarian el trabajo el uno al otro.
        Por eso leer el anterior y registrar el nuevo es una sola operacion: las
        rutas son sincronas y corren a la vez, y dos `reanudar` seguidos que
        leyesen el mismo anterior dejarian dos caminantes sueltos (RF-166).
        """
        caminante = self.caminante()
        with self._turno_de_arranque:
            anterior = self.hilos.get(id_obra)

            def caminar() -> None:
                if anterior is not None:
                    anterior.join()
                caminante.caminar_obra(id_obra, capitulos)

            hilo = threading.Thread(target=caminar, name=f"produccion-{id_obra}", daemon=True)
            self.hilos[id_obra] = hilo
            hilo.start()

    def terminada(self, obra: Artefacto) -> bool:
        """Una obra ha terminado cuando consta su auditoria de cierre (RF-93)."""
        return self.almacen.auditada_hasta(obra.id) >= self.capitulos_objetivo(obra)

    @staticmethod
    def capitulos_objetivo(obra: Artefacto) -> int:
        return int(obra.cuerpo.get("capitulos_objetivo", 1))

    def relanzar_las_caidas(self) -> list[str]:
        """Al arrancar, toda obra que no este detenida ni terminada se relanza.

        Es lo que hace que una caida no pida ninguna orden (D-33): el hilo de
        produccion murio con el proceso, y relanzar pasa por el mismo camino que
        reanudar, que vuelve al ultimo capitulo cerrado.
        """
        relanzadas: list[str] = []
        for obra in self.almacen.listar_obras():
            if self.almacen.esta_detenida(obra.id) or self.terminada(obra):
                continue
            self.arrancar(obra.id, self.capitulos_objetivo(obra))
            relanzadas.append(obra.id)
        return relanzadas

    def cerrar(self) -> None:
        self.observabilidad.vaciar()
        self.almacen.cerrar()


def crear_aplicacion(
    ruta_de_la_base: Any = None,
    ejecutor: Any = None,
    demostrador: Any = None,
    observabilidad: observacion.Observabilidad | None = None,
) -> FastAPI:
    """Monta la aplicacion. `ejecutor` se pasa solo para recorrer en seco,
    `demostrador` solo para comprobar la puerta sin Lean de por medio y
    `observabilidad` solo para mirar lo que se manda a un Langfuse fingido."""

    @asynccontextmanager
    async def ciclo(app: FastAPI) -> AsyncIterator[None]:
        app.state.produccion = Produccion(
            ruta_de_la_base, ejecutor, demostrador, observabilidad
        )
        app.state.produccion.relanzar_las_caidas()
        yield
        app.state.produccion.cerrar()

    app = FastAPI(
        title="Generador de novela historica por agentes",
        summary="Lanza una obra desde un brief e inspecciona lo que los agentes producen",
        version=__version__,
        lifespan=ciclo,
    )

    @app.exception_handler(RequestValidationError)
    async def en_espanol(peticion: Request, error: RequestValidationError) -> JSONResponse:
        """Un brief al que le falta un campo se rechaza nombrando el campo."""
        faltan = [
            ".".join(str(parte) for parte in fallo["loc"][1:])
            for fallo in error.errors()
            if fallo["type"] == "missing"
        ]
        if faltan:
            detalle = "Falta un campo obligatorio del brief: " + ", ".join(faltan)
        else:
            detalle = "; ".join(
                f"{'.'.join(str(p) for p in fallo['loc'][1:])}: {fallo['msg']}"
                for fallo in error.errors()
            )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content={"detalle": detalle, "campos": faltan},
        )

    def produccion(peticion: Request) -> Produccion:
        return peticion.app.state.produccion  # type: ignore[no-any-return]

    ProduccionDep = Annotated[Produccion, Depends(produccion)]
    IdObra = Annotated[str, Path(description="Identificador de la obra")]

    def _obra_o_404(casa: Produccion, id_obra: str) -> Artefacto:
        obra = casa.almacen.leer_obra(id_obra)
        if obra is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"No hay ninguna obra {id_obra}")
        return obra

    VersionPedida = Annotated[
        int | None,
        Query(
            ge=1,
            description="Version que se lee. Sin ella, la publicada, y si no hay, la ultima",
        ),
    ]

    def _version(casa: Produccion, id_obra: str, version: int | None) -> int:
        """La version que se sirve: la pedida, o la de referencia (RF-117)."""
        if version is None:
            return versiones.de_referencia(casa.almacen, id_obra)
        if casa.almacen.leer_version(id_obra, version) is None:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND, f"La obra {id_obra} no tiene version {version}"
            )
        return version

    # --- RI-01. La unica llamada de escritura por obra --------------------

    @app.post("/obras", status_code=status.HTTP_202_ACCEPTED)
    def lanzar_obra(brief: Brief, casa: ProduccionDep) -> ObraCreada:
        id_obra = casa.almacen.crear_obra(*_alta(brief))
        casa.arrancar(id_obra, brief.capitulos_objetivo)
        return ObraCreada(id_obra=id_obra, estado="en produccion")

    # --- RF-70 a RF-79. La entrevista que completa el brief ----------------

    def _pasada(
        casa: Produccion, peticion: PeticionDeEntrevista, id_entrevista: str | None
    ) -> PasadaDeEntrevista:
        """Una pasada en frio, de principio a fin.

        Se mide antes de abrir nada: si no cabe en el tope del rol, no se abre
        la entrevista ni se recorta ningun texto (RF-71).
        """
        borrador = peticion.borrador.model_dump(exclude_none=True)
        asumidas = list(peticion.contradicciones_asumidas)
        ventana = entrevista.ventana(borrador, peticion.textos, asumidas)
        tope = tope_de_ventana(entrevista.ROL)
        if ventana.tokens > tope:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                f"La pasada no cabe en la ventana del Entrevistador: ocupa {ventana.tokens} "
                f"tokens, el tope es {tope} y sobran {ventana.tokens - tope}. Manda menos "
                "texto pegado en esta pasada.",
            )
        if id_entrevista is None:
            id_entrevista = casa.almacen.abrir_entrevista()
        else:
            abierta = casa.almacen.leer_entrevista(id_entrevista)
            if abierta is None:
                raise HTTPException(
                    status.HTTP_404_NOT_FOUND, f"No hay ninguna entrevista {id_entrevista}"
                )
            if abierta["id_obra"] is not None:
                raise HTTPException(
                    status.HTTP_409_CONFLICT,
                    f"La entrevista {id_entrevista} ya lanzo la obra {abierta['id_obra']}",
                )

        abierta_en = ahora()
        # La pasada es una generacion en la traza de su entrevista (RF-185).
        observada = f"{id_entrevista}:{abierta_en}"
        casa.observabilidad.abrir_pasada(observada, id_entrevista)
        with casa.turno_de_entrevista:
            try:
                resultado = casa.ejecutor.ejecutar(entrevista.encargo(), ventana)
            except SubagenteFallo as fallo:
                casa.observabilidad.cerrar_tarea(observada, error=str(fallo))
                raise HTTPException(
                    status.HTTP_502_BAD_GATEWAY,
                    f"La pasada de entrevista no se pudo completar: {fallo}",
                ) from fallo

        # El Entrevistador no escribe nada en el almacen (RF-70): lo que devuelva
        # como artefacto no se guarda, se cuenta.
        rechazados = [
            a for a in resultado.artefactos if not puede_escribir(entrevista.ROL, a.tipo)
        ]
        propuesta = entrevista.aplicar_pasada(
            borrador,
            peticion.textos,
            resultado.constancia,
            escalares=ESCALARES_DEL_BRIEF,
            listas=LISTAS_DEL_BRIEF,
            asumidas=asumidas,
        )
        brief, faltan, no_validos = _validar(propuesta)
        abiertas = [c for c in propuesta.contradicciones if not c["asumida"]]
        alta = None
        if brief is not None and not abiertas:
            cuerpo, recuerdos = _alta(brief)
            alta = (cuerpo | {"id_entrevista": id_entrevista}, recuerdos)

        salida = {
            "brief_propuesto": propuesta.brief,
            "faltan": faltan,
            "no_validos": no_validos,
            "hechos": propuesta.hechos,
            "hechos_descartados": propuesta.hechos_descartados,
            "contradicciones": propuesta.contradicciones,
            "contradicciones_descartadas": propuesta.contradicciones_descartadas,
            "respuesta_del_agente": resultado.salida,
        }
        try:
            numero, id_obra = casa.almacen.registrar_pasada(
                id_entrevista,
                entrada={
                    "borrador": borrador,
                    "textos": list(peticion.textos),
                    "contradicciones_asumidas": asumidas,
                },
                salida=salida,
                descartes={
                    "hechos": len(propuesta.hechos_descartados),
                    "contradicciones": len(propuesta.contradicciones_descartadas),
                    "artefactos": len(rechazados),
                },
                traza={
                    "tokens_de_entrada_estimados": ventana.tokens,
                    "tokens_de_entrada_medidos": resultado.tokens_de_entrada_medidos,
                    "tokens_de_salida": resultado.tokens_de_salida,
                    "coste": resultado.coste,
                    "latencia_ms": resultado.latencia_ms,
                    "abierta_en": abierta_en,
                    "cerrada_en": ahora(),
                },
                alta=alta,
            )
        except EscrituraProhibida as error:
            casa.observabilidad.cerrar_tarea(observada, error=str(error))
            raise HTTPException(status.HTTP_409_CONFLICT, str(error)) from error
        casa.observabilidad.cerrar_tarea(
            observada,
            salida=resultado.salida,
            tokens_de_entrada=resultado.tokens_de_entrada_medidos,
            tokens_de_salida=resultado.tokens_de_salida,
            coste=resultado.coste,
            latencia_ms=resultado.latencia_ms,
            modelo=resultado.modelo,
            herramientas=resultado.herramientas,
        )
        if id_obra is not None and brief is not None:
            casa.arrancar(id_obra, brief.capitulos_objetivo)

        return PasadaDeEntrevista(
            id_entrevista=id_entrevista,
            numero=numero,
            estado="lanzada" if id_obra else "pendiente",
            id_obra=id_obra,
            brief_propuesto=propuesta.brief,
            faltan=faltan,
            no_validos=no_validos,
            hechos=[HechoExtraido(**hecho) for hecho in propuesta.hechos],
            hechos_descartados=[HechoDescartado(**d) for d in propuesta.hechos_descartados],
            contradicciones=[Contradiccion(**c) for c in propuesta.contradicciones],
            contradicciones_descartadas=len(propuesta.contradicciones_descartadas),
        )

    @app.post("/entrevistas", status_code=status.HTTP_201_CREATED)
    def abrir_entrevista(
        peticion: PeticionDeEntrevista, casa: ProduccionDep
    ) -> PasadaDeEntrevista:
        """Abre una entrevista y hace su primera pasada. Si el brief queda
        completo y sin contradicciones abiertas, la obra se lanza sola (RF-78)."""
        return _pasada(casa, peticion, None)

    @app.post("/entrevistas/{id_entrevista}/pasadas", status_code=status.HTTP_201_CREATED)
    def pasar_entrevista(
        id_entrevista: Annotated[str, Path(description="Identificador de la entrevista")],
        peticion: PeticionDeEntrevista,
        casa: ProduccionDep,
    ) -> PasadaDeEntrevista:
        """La pasada siguiente. No recibe nada de las anteriores (D-20)."""
        return _pasada(casa, peticion, id_entrevista)

    # --- RI-02. Ficha y avance ---------------------------------------------

    def _ficha(casa: Produccion, obra: Artefacto) -> FichaDeObra:
        """La ficha de una obra. La sirven igual su ruta y el listado (RF-204)."""
        id_obra = obra.id
        destinatario = obra.cuerpo.get("destinatario")
        if not isinstance(destinatario, dict):
            destinatario = {}
        capitulos = casa.almacen.listar("Capitulo", id_obra)
        cerrados = [c for c in capitulos if c.estado == "cerrado"]
        abiertas = casa.almacen.listar_criticas_abiertas(id_obra)
        con_criticas = {c.capitulo for c in abiertas}
        en_curso = [c for c in capitulos if c.estado not in {"cerrado", "descartado"}]
        return FichaDeObra(
            id_obra=id_obra,
            titulo=str(obra.cuerpo.get("titulo", "")),
            situacion=cast(SituacionDeLaObra, versiones.situacion(casa.almacen, id_obra)),
            detenida=casa.almacen.esta_detenida(id_obra),
            capitulo_en_curso=min((c.capitulo or 0 for c in en_curso), default=None),
            capitulos_cerrados=len(cerrados),
            capitulos_marcados=len([c for c in cerrados if c.capitulo in con_criticas]),
            criticas_abiertas=len(abiertas),
            version_en_curso=casa.almacen.version_en_curso(id_obra),
            version_publicada=casa.almacen.version_publicada(id_obra),
            motivo_de_la_detencion=casa.almacen.motivo_de_la_detencion(id_obra),
            destinatario=destinatario.get("nombre"),
            dedicatoria=destinatario.get("dedicatoria"),
        )

    # --- RI-20. El taller: todas las obras con su situacion ----------------

    @app.get("/obras")
    def listar_obras(casa: ProduccionDep) -> list[ObraDelTaller]:
        """Todas las obras, de la mas reciente a la mas antigua (RF-204)."""
        return [
            ObraDelTaller(
                **_ficha(casa, obra).model_dump(),
                epoca=str(obra.cuerpo.get("epoca", "")),
                capitulos_objetivo=casa.capitulos_objetivo(obra),
                creada_en=obra.creado_en,
            )
            for obra in casa.almacen.listar_obras()
        ]

    @app.get("/obras/{id_obra}")
    def ver_obra(id_obra: IdObra, casa: ProduccionDep) -> FichaDeObra:
        return _ficha(casa, _obra_o_404(casa, id_obra))

    # --- RI-03. Leer -------------------------------------------------------

    @app.get("/obras/{id_obra}/manuscrito")
    def leer_manuscrito(
        id_obra: IdObra, casa: ProduccionDep, version: VersionPedida = None
    ) -> Manuscrito:
        """Solo el texto aceptado, en orden, con los capitulos marcados, de la
        version pedida o de la de referencia."""
        _obra_o_404(casa, id_obra)
        numero = _version(casa, id_obra, version)
        marcados = {
            c.capitulo
            for c in casa.almacen.listar_criticas_abiertas(id_obra, version=numero)
        }
        return Manuscrito(
            id_obra=id_obra,
            version=numero,
            publicada=casa.almacen.version_publicada(id_obra) == numero,
            unidades=[
                UnidadDelManuscrito(
                    capitulo=borrador.capitulo or 0,
                    escena=borrador.escena or "",
                    texto=str(borrador.cuerpo.get("texto", "")),
                    capitulo_marcado=borrador.capitulo in marcados,
                )
                for borrador in casa.almacen.manuscrito_aceptado(id_obra, version=numero)
            ],
        )

    # --- RI-04. Inspeccionar un capitulo -----------------------------------

    @app.get("/obras/{id_obra}/capitulos/{numero}")
    def ver_capitulo(
        id_obra: IdObra,
        numero: Annotated[int, Path(ge=1)],
        casa: ProduccionDep,
        version: VersionPedida = None,
    ) -> CapituloInspeccionado:
        _obra_o_404(casa, id_obra)
        de_la_version = _version(casa, id_obra, version)
        leido = casa.almacen.leer_capitulo(id_obra, numero, version=de_la_version)
        escenas = leido["escenas"]
        vigentes = {}
        for escena in escenas:
            borrador = casa.almacen.borrador_vigente(
                id_obra, escena.id, version=de_la_version
            )
            if borrador is not None:
                vigentes[escena.id] = borrador.cuerpo | {"id": borrador.id}
        capitulo = leido["capitulo"]
        plan = leido["plan"]
        return CapituloInspeccionado(
            capitulo=numero,
            estado=capitulo.estado if capitulo else None,
            plan=plan.cuerpo if plan else None,
            escenas=[escena.cuerpo | {"id": escena.id} for escena in escenas],
            borrador_vigente_por_escena=vigentes,
            criticas=[c.cuerpo | {"id": c.id} for c in leido["criticas"]],
        )

    # --- RI-05. Ver defectos -----------------------------------------------

    @app.get("/obras/{id_obra}/criticas")
    def ver_criticas(
        id_obra: IdObra,
        casa: ProduccionDep,
        estado: Annotated[str | None, Query()] = None,
        dimension: Annotated[str | None, Query()] = None,
        severidad: Annotated[str | None, Query()] = None,
        capitulo: Annotated[int | None, Query(ge=1)] = None,
        version: VersionPedida = None,
    ) -> list[CriticaServida]:
        _obra_o_404(casa, id_obra)
        criticas = casa.almacen.listar(
            "Critica",
            id_obra,
            estado=estado,
            dimension=dimension,
            severidad=severidad,
            capitulo=capitulo,
            version=_version(casa, id_obra, version),
        )
        return [
            CriticaServida(
                id=critica.id,
                capitulo=critica.capitulo,
                escena=critica.escena,
                estado=critica.estado,
                severidad=critica.severidad,
                dimension=critica.dimension,
                detectada_por=critica.procedencia_rol,
                evidencia=critica.cuerpo.get("evidencia"),
                accion_sugerida=critica.cuerpo.get("accion_sugerida"),
            )
            for critica in criticas
        ]

    # --- RI-06. Medir el sistema -------------------------------------------

    @app.get("/obras/{id_obra}/trazas")
    def ver_trazas(
        id_obra: IdObra,
        casa: ProduccionDep,
        capitulo: Annotated[int | None, Query(ge=1)] = None,
        rol: Annotated[str | None, Query()] = None,
        tarea: Annotated[str | None, Query()] = None,
    ) -> list[TrazaServida]:
        _obra_o_404(casa, id_obra)
        return [
            TrazaServida(
                id=traza.id,
                capitulo=traza.capitulo,
                escena=traza.escena,
                rol=traza.rol,
                tarea=traza.propias.get("tarea"),
                intento=traza.propias.get("intento"),
                tokens_de_entrada_estimados=traza.propias.get("tokens_de_entrada_estimados"),
                tokens_de_entrada_medidos=traza.propias.get("tokens_de_entrada_medidos"),
                tokens_de_salida=traza.propias.get("tokens_de_salida"),
                coste=traza.propias.get("coste"),
                latencia_ms=traza.propias.get("latencia_ms"),
                abierta_en=traza.propias.get("abierta_en"),
                cerrada_en=traza.propias.get("cerrada_en"),
                ganchos=traza.cuerpo.get("ganchos"),
            )
            for traza in casa.almacen.listar_trazas(
                id_obra, capitulo=capitulo, rol=rol, tarea=tarea
            )
        ]

    # --- RI-16. Lo que encontro la politica de lo vetado --------------------

    @app.get("/obras/{id_obra}/policy")
    def ver_policy(
        id_obra: IdObra,
        casa: ProduccionDep,
        capitulo: Annotated[int | None, Query(ge=1)] = None,
        nivel: Annotated[
            Literal["global", "palabra_del_comprador", "tema_del_comprador"] | None, Query()
        ] = None,
        decision: Annotated[
            Literal["devuelto_al_agente", "intento_fallido"] | None, Query()
        ] = None,
    ) -> list[DecisionDePolicy]:
        """El registro de auditoria de `policy`, en orden (RF-138). Solo lectura."""
        _obra_o_404(casa, id_obra)
        return [
            DecisionDePolicy(**fila)
            for fila in casa.almacen.listar_decisiones_de_policy(
                id_obra, capitulo=capitulo, nivel=nivel, decision=decision
            )
        ]

    # --- RI-07. Auditar continuidad ----------------------------------------

    @app.get("/obras/{id_obra}/estado")
    def ver_estado(
        id_obra: IdObra,
        casa: ProduccionDep,
        capitulo: Annotated[int, Query(ge=1)] = 1,
        version: VersionPedida = None,
    ) -> EstadoPlegado:
        _obra_o_404(casa, id_obra)
        numero = _version(casa, id_obra, version)
        return EstadoPlegado(
            id_obra=id_obra,
            capitulo=capitulo,
            estado=casa.almacen.estado_en(id_obra, capitulo, version=numero),
            eventos=[
                evento.cuerpo | {"id": evento.id, "capitulo": evento.capitulo}
                for evento in casa.almacen.listar(
                    "EventoEstado", id_obra, orden="capitulo", version=numero
                )
                if (evento.capitulo or 0) <= capitulo
            ],
        )

    # --- RF-87. La biblia con su uso por capitulo, y la cronologia --------

    @app.get("/obras/{id_obra}/hechos")
    def ver_hechos(
        id_obra: IdObra,
        casa: ProduccionDep,
        tipo: Annotated[
            Literal["Personaje", "Lugar", "Objeto", "Faccion", "Evento"] | None, Query()
        ] = None,
        licencia: Annotated[
            Literal["canon", "plausible", "licencia", "personal"] | None, Query()
        ] = None,
        version: VersionPedida = None,
    ) -> list[HechoDeLaBiblia]:
        """Cada hecho de la biblia con los capitulos en que se ha usado."""
        _obra_o_404(casa, id_obra)
        return [
            HechoDeLaBiblia(**hecho)
            for hecho in casa.almacen.hechos_de_la_biblia(
                id_obra,
                tipo=tipo,
                licencia=licencia,
                version=_version(casa, id_obra, version),
            )
        ]

    @app.get("/obras/{id_obra}/cronologia")
    def ver_cronologia(
        id_obra: IdObra, casa: ProduccionDep, version: VersionPedida = None
    ) -> Cronologia:
        """Sucesos en orden, con momento, lugar y presentes con su nacimiento."""
        _obra_o_404(casa, id_obra)
        numero = _version(casa, id_obra, version)
        return Cronologia(
            id_obra=id_obra,
            sucesos=[
                Suceso(**suceso) for suceso in casa.almacen.cronologia(id_obra, version=numero)
            ],
        )

    # --- RI-11 a RI-13. Versiones: rehacer, publicar y verlas --------------

    @app.get("/obras/{id_obra}/versiones")
    def ver_versiones(id_obra: IdObra, casa: ProduccionDep) -> list[VersionDeLaObra]:
        """Cada version con su base, lo que cambio y si es la publicada."""
        _obra_o_404(casa, id_obra)
        publicada = casa.almacen.version_publicada(id_obra)
        return [
            VersionDeLaObra(
                **version,
                terminada=version["terminada_en"] is not None,
                publicada=version["numero"] == publicada,
            )
            for version in casa.almacen.listar_versiones(id_obra)
        ]

    @app.post("/obras/{id_obra}/versiones", status_code=status.HTTP_202_ACCEPTED)
    def rehacer(
        id_obra: IdObra, peticion: PeticionDeRehacer, casa: ProduccionDep
    ) -> VersionAbierta:
        """Rehacer desde un capitulo: la version anterior se conserva entera y la
        nueva reescribe de ese capitulo al final (RF-111). No espera a que termine."""
        obra = _obra_o_404(casa, id_obra)
        ultimo = casa.capitulos_objetivo(obra)
        if peticion.desde_capitulo > ultimo:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                f"La obra tiene {ultimo} capitulos: no se rehace desde el "
                f"{peticion.desde_capitulo}",
            )
        hilo = casa.hilos.get(id_obra)
        if hilo is not None and hilo.is_alive():
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"La obra {id_obra} esta produciendo: se rehace cuando termine",
            )
        try:
            nueva = versiones.rehacer_desde(
                casa.almacen, casa.indice, id_obra, peticion.desde_capitulo, ultimo
            )
        except VersionNoAdmitida as error:
            raise HTTPException(status.HTTP_409_CONFLICT, str(error)) from error
        casa.arrancar(id_obra, ultimo)
        return VersionAbierta(
            id_obra=id_obra,
            version=nueva,
            capitulos_cambiados=list(range(peticion.desde_capitulo, ultimo + 1)),
            estado="en produccion",
        )

    @app.post("/obras/{id_obra}/cambios", status_code=status.HTTP_202_ACCEPTED)
    def cambiar_hecho(
        id_obra: IdObra, peticion: PeticionDeCambio, casa: ProduccionDep
    ) -> VersionAbierta:
        """El cambio del lector: el hecho toma su nombre nuevo en una version que
        reescribe solo los capitulos que lo mencionan (RF-170, RF-171). La
        anterior se conserva entera. No espera a que termine."""
        obra = _obra_o_404(casa, id_obra)
        hilo = casa.hilos.get(id_obra)
        if hilo is not None and hilo.is_alive():
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"La obra {id_obra} esta produciendo: se cambia cuando termine",
            )
        try:
            nueva, capitulos = versiones.cambiar_hecho(
                casa.almacen, casa.indice, id_obra, peticion.hecho, peticion.valor
            )
        except KeyError as error:
            raise HTTPException(status.HTTP_404_NOT_FOUND, error.args[0]) from error
        except ValueError as error:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(error)) from error
        except (HechoSinMenciones, VersionNoAdmitida) as error:
            raise HTTPException(status.HTTP_409_CONFLICT, str(error)) from error
        casa.arrancar(id_obra, casa.capitulos_objetivo(obra))
        return VersionAbierta(
            id_obra=id_obra,
            version=nueva,
            capitulos_cambiados=capitulos,
            estado="en produccion",
        )

    @app.post(
        "/obras/{id_obra}/versiones/{numero}/publicar",
        response_model=Publicacion,
        responses={
            409: {
                "model": RechazoDePublicacion,
                "description": (
                    "No se publica: la version no ha terminado, o no pasa la puerta y "
                    "`puerta` dice que fallo y en que capitulo (RI-18)"
                ),
            }
        },
    )
    def publicar(
        id_obra: IdObra,
        numero: Annotated[int, Path(ge=1, description="Version que se publica")],
        casa: ProduccionDep,
    ) -> Publicacion | JSONResponse:
        """Publicar es una orden: terminar no publica (RF-116), y la version pasa
        antes por la puerta (RF-146), cronologia en Lean incluida (RF-152). Si no
        pasa, no se publica y se explica; si falla la cronologia, el fallo queda
        ademas como critica del capitulo (RF-154)."""
        _obra_o_404(casa, id_obra)
        try:
            publicada_en, comprobacion = versiones.publicar(
                casa.almacen, id_obra, numero, casa.catalogo, casa.demostrador
            )
        except KeyError as error:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND, f"La obra {id_obra} no tiene version {numero}"
            ) from error
        except VersionNoAdmitida as error:
            raise HTTPException(status.HTTP_409_CONFLICT, str(error)) from error
        except versiones.PuertaNoSuperada as rechazo:
            casa.observabilidad.resultado_de_la_puerta(
                id_obra,
                numero,
                rechazo.resultado["fallos"],
                rechazo.resultado["comprobacion_formal"],
            )
            return JSONResponse(
                status_code=status.HTTP_409_CONFLICT,
                content=RechazoDePublicacion(
                    detail=str(rechazo),
                    puerta=PuertaDePublicacion.model_validate(rechazo.resultado),
                ).model_dump(),
            )
        # Paso la puerta: todos los validadores, a 1 (RF-187).
        casa.observabilidad.resultado_de_la_puerta(id_obra, numero, [], comprobacion)
        return Publicacion(
            id_obra=id_obra,
            version=numero,
            publicada_en=publicada_en,
            comprobacion_formal=comprobacion,  # type: ignore[arg-type]
        )

    @app.get("/obras/{id_obra}/versiones/{numero}/puerta")
    def ver_puerta(
        id_obra: IdObra,
        numero: Annotated[int, Path(ge=1, description="Version que se comprueba")],
        casa: ProduccionDep,
    ) -> PuertaDePublicacion:
        """La puerta pasada ahora sobre la version, sin publicar nada (RF-147)."""
        _obra_o_404(casa, id_obra)
        try:
            resultado = versiones.puerta(
                casa.almacen, id_obra, numero, casa.catalogo, casa.demostrador
            )
        except KeyError as error:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND, f"La obra {id_obra} no tiene version {numero}"
            ) from error
        casa.observabilidad.resultado_de_la_puerta(
            id_obra, numero, resultado["fallos"], resultado["comprobacion_formal"]
        )
        return PuertaDePublicacion.model_validate(resultado)

    # --- RF-178. El manuscrito en PDF, al vuelo ------------------------------

    @app.get(
        "/obras/{id_obra}/pdf",
        response_class=Response,
        responses={
            200: {
                "content": {
                    "application/pdf": {"schema": {"type": "string", "format": "binary"}}
                },
                "description": "El PDF de la version, como descarga. No se guarda",
            }
        },
    )
    def descargar_pdf(
        id_obra: IdObra, casa: ProduccionDep, version: VersionPedida = None
    ) -> Response:
        """Portada, indice y texto aceptado de la version, fabricado en memoria
        (RF-178). Nada toca el disco (RD-08)."""
        obra = _obra_o_404(casa, id_obra)
        numero = _version(casa, id_obra, version)
        destinatario = obra.cuerpo.get("destinatario")
        if not isinstance(destinatario, dict):
            destinatario = {}
        por_capitulo: dict[int, list[str]] = {}
        for borrador in casa.almacen.manuscrito_aceptado(id_obra, version=numero):
            por_capitulo.setdefault(borrador.capitulo or 0, []).append(
                str(borrador.cuerpo.get("texto", ""))
            )
        titulo = str(obra.cuerpo.get("titulo", ""))
        contenido = manuscrito_en_pdf(
            titulo,
            destinatario.get("nombre"),
            destinatario.get("dedicatoria"),
            [CapituloDelPdf(n, escenas) for n, escenas in sorted(por_capitulo.items())],
            version=numero,
        )
        nombre = "".join(c if c.isascii() and c.isalnum() else "-" for c in titulo).strip("-")
        fichero = f"{nombre or id_obra}-v{numero}.pdf"
        return Response(
            content=contenido,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{fichero}"'},
        )

    # --- RI-08. Ver la ejecucion en vivo -----------------------------------

    def _progreso(casa: Produccion, id_obra: str) -> Progreso:
        abiertas = casa.almacen.trazas_abiertas(id_obra)
        capitulos = casa.almacen.listar("Capitulo", id_obra)
        en_curso = [c for c in capitulos if c.estado not in {"cerrado", "descartado"}]
        return Progreso(
            id_obra=id_obra,
            detenida=casa.almacen.esta_detenida(id_obra),
            capitulo_en_curso=min((c.capitulo or 0 for c in en_curso), default=None),
            tareas_abiertas=[
                {
                    "rol": traza.rol,
                    "tarea": traza.propias.get("tarea"),
                    "capitulo": traza.capitulo,
                    "escena": traza.escena,
                    "tokens": traza.propias.get("tokens_de_entrada_estimados"),
                }
                for traza in abiertas
            ],
            tokens_de_entrada_concurrentes=casa.almacen.contexto_de_entrada_abierto(id_obra),
            techo=TECHO_DE_CONTEXTO_CONCURRENTE,
        )

    @app.get(
        "/obras/{id_obra}/progreso",
        response_class=EventSourceResponse,
        responses={
            200: {
                "description": (
                    "Flujo abierto mientras la obra corre. Cada evento `progreso` "
                    "lleva un `Progreso`; el evento `terminada` lo cierra."
                ),
            }
        },
    )
    async def ver_progreso(
        id_obra: IdObra, casa: ProduccionDep
    ) -> AsyncIterable[ServerSentEvent]:
        """Flujo de eventos de progreso mientras la obra corre."""
        import anyio

        _obra_o_404(casa, id_obra)
        while True:
            yield ServerSentEvent(data=_progreso(casa, id_obra).model_dump(), event="progreso")
            hilo = casa.hilos.get(id_obra)
            if hilo is not None and not hilo.is_alive():
                yield ServerSentEvent(data={"id_obra": id_obra}, event="terminada")
                return
            await anyio.sleep(1)

    @app.get("/obras/{id_obra}/progreso/ahora")
    def ver_progreso_ahora(id_obra: IdObra, casa: ProduccionDep) -> Progreso:
        """El mismo progreso de una sola vez, para quien no quiera el flujo."""
        _obra_o_404(casa, id_obra)
        return _progreso(casa, id_obra)

    # --- RF-55. Localizar un pasaje sin recordar sus palabras --------------

    @app.get("/obras/{id_obra}/pasajes")
    def buscar_pasaje(
        id_obra: IdObra,
        casa: ProduccionDep,
        consulta: Annotated[str, Query(min_length=2)],
        k: Annotated[int, Query(ge=1, le=20)] = 5,
    ) -> list[Pasaje]:
        _obra_o_404(casa, id_obra)
        return [
            Pasaje(
                fragmento=fragmento["id"],
                texto=fragmento["texto"],
                capitulo=fragmento["capitulo"],
                escena=fragmento["escena"],
            )
            for fragmento in casa.indice.recuperar(
                id_obra, "obra_prosa", consulta, "editor_de_estilo", k=k
            )
        ]

    # --- RI-09. Control, no mantenimiento ----------------------------------

    @app.post("/obras/{id_obra}/detener")
    def detener(id_obra: IdObra, orden: Orden, casa: ProduccionDep) -> Confirmacion:
        _obra_o_404(casa, id_obra)
        casa.almacen.detener(id_obra, orden.motivo or "orden del editor")
        return Confirmacion(id_obra=id_obra, detenida=True, motivo=orden.motivo)

    @app.post("/obras/{id_obra}/reanudar")
    def reanudar(id_obra: IdObra, casa: ProduccionDep) -> Confirmacion:
        """Vuelve al ultimo capitulo cerrado; no repite nada de lo cerrado."""
        obra = _obra_o_404(casa, id_obra)
        casa.almacen.reanudar(id_obra)
        if not casa.terminada(obra):
            casa.arrancar(id_obra, casa.capitulos_objetivo(obra))
        return Confirmacion(id_obra=id_obra, detenida=False, motivo=None)

    return app


def operaciones_de_escritura(app: FastAPI) -> list[str]:
    """Las rutas por las que el editor escribe algo: entrevistar, lanzar,
    detener, reanudar, rehacer, cambiar un hecho y publicar. Ninguna es de
    mantenimiento."""
    escrituras: list[str] = []
    for ruta in app.routes:
        metodos: Iterator[str] = iter(getattr(ruta, "methods", []) or [])
        for metodo in metodos:
            if metodo in {"POST", "PUT", "PATCH", "DELETE"}:
                escrituras.append(f"{metodo} {getattr(ruta, 'path', '')}")
    return sorted(escrituras)
