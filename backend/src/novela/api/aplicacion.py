"""Las nueve operaciones del editor, en diez rutas.

Cada una es un procedimiento de principio a fin. Los mensajes de error van en
espanol. La interfaz web nunca lee ficheros ni la base de datos: todo lo que
muestra lo pide aqui.
"""

import threading
from collections.abc import AsyncIterable, AsyncIterator, Iterator
from contextlib import asynccontextmanager
from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException, Path, Query, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.sse import EventSourceResponse, ServerSentEvent

from novela.ajustes import RUTA_DE_LA_BASE, TECHO_DE_CONTEXTO_CONCURRENTE
from novela.almacen import Almacen, Artefacto
from novela.almacen.artefactos import abrir_almacen
from novela.almacen.indice import Indice
from novela.api.modelos import (
    Brief,
    CapituloInspeccionado,
    Confirmacion,
    CriticaServida,
    EstadoPlegado,
    FichaDeObra,
    Manuscrito,
    ObraCreada,
    Orden,
    Pasaje,
    Progreso,
    TrazaServida,
    UnidadDelManuscrito,
)
from novela.ejecutor import EjecutorDeSubagentes
from novela.nucleo.caminante import Caminante
from novela.tareas import CatalogoDelRepositorio


class Produccion:
    """Lo que la aplicacion necesita tener abierto: el almacen y quien camina."""

    def __init__(self, ruta: Any = None, ejecutor: Any = None) -> None:
        self.almacen: Almacen = abrir_almacen(ruta or RUTA_DE_LA_BASE)
        self.indice = Indice(self.almacen)
        self.catalogo = CatalogoDelRepositorio()
        self.ejecutor = ejecutor or EjecutorDeSubagentes(catalogo=self.catalogo)
        self.hilos: dict[str, threading.Thread] = {}

    def caminante(self) -> Caminante:
        return Caminante(
            self.almacen,
            self.ejecutor,
            catalogo=self.catalogo,
            indice=self.indice,
        )

    def arrancar(self, id_obra: str, capitulos: int) -> None:
        """Arranca la produccion completa y devuelve el turno enseguida.

        Es la unica orden que el editor tiene que dar: de aqui al ultimo
        capitulo cerrado no hay ninguna otra.
        """
        hilo = threading.Thread(
            target=self.caminante().caminar_obra,
            args=(id_obra, capitulos),
            name=f"produccion-{id_obra}",
            daemon=True,
        )
        self.hilos[id_obra] = hilo
        hilo.start()

    def cerrar(self) -> None:
        self.almacen.cerrar()


def crear_aplicacion(ruta_de_la_base: Any = None, ejecutor: Any = None) -> FastAPI:
    """Monta la aplicacion. `ejecutor` se pasa solo para recorrer en seco."""

    @asynccontextmanager
    async def ciclo(app: FastAPI) -> AsyncIterator[None]:
        app.state.produccion = Produccion(ruta_de_la_base, ejecutor)
        yield
        app.state.produccion.cerrar()

    app = FastAPI(
        title="Generador de novela historica por agentes",
        summary="Lanza una obra desde un brief e inspecciona lo que los agentes producen",
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

    # --- RI-01. La unica llamada de escritura por obra --------------------

    @app.post("/obras", status_code=status.HTTP_202_ACCEPTED)
    def lanzar_obra(brief: Brief, casa: ProduccionDep) -> ObraCreada:
        id_obra = casa.almacen.crear_obra(brief.model_dump())
        casa.arrancar(id_obra, brief.capitulos_objetivo)
        return ObraCreada(id_obra=id_obra, estado="en produccion")

    # --- RI-02. Ficha y avance ---------------------------------------------

    @app.get("/obras/{id_obra}")
    def ver_obra(id_obra: IdObra, casa: ProduccionDep) -> FichaDeObra:
        obra = _obra_o_404(casa, id_obra)
        capitulos = casa.almacen.listar("Capitulo", id_obra)
        cerrados = [c for c in capitulos if c.estado == "cerrado"]
        abiertas = casa.almacen.listar_criticas_abiertas(id_obra)
        con_criticas = {c.capitulo for c in abiertas}
        en_curso = [c for c in capitulos if c.estado not in {"cerrado", "descartado"}]
        return FichaDeObra(
            id_obra=id_obra,
            titulo=str(obra.cuerpo.get("titulo", "")),
            detenida=casa.almacen.esta_detenida(id_obra),
            capitulo_en_curso=min((c.capitulo or 0 for c in en_curso), default=None),
            capitulos_cerrados=len(cerrados),
            capitulos_marcados=len([c for c in cerrados if c.capitulo in con_criticas]),
            criticas_abiertas=len(abiertas),
        )

    # --- RI-03. Leer -------------------------------------------------------

    @app.get("/obras/{id_obra}/manuscrito")
    def leer_manuscrito(id_obra: IdObra, casa: ProduccionDep) -> Manuscrito:
        """Solo el texto aceptado, en orden, con los capitulos marcados."""
        _obra_o_404(casa, id_obra)
        marcados = {c.capitulo for c in casa.almacen.listar_criticas_abiertas(id_obra)}
        return Manuscrito(
            id_obra=id_obra,
            unidades=[
                UnidadDelManuscrito(
                    capitulo=borrador.capitulo or 0,
                    escena=borrador.escena or "",
                    texto=str(borrador.cuerpo.get("texto", "")),
                    capitulo_marcado=borrador.capitulo in marcados,
                )
                for borrador in casa.almacen.manuscrito_aceptado(id_obra)
            ],
        )

    # --- RI-04. Inspeccionar un capitulo -----------------------------------

    @app.get("/obras/{id_obra}/capitulos/{numero}")
    def ver_capitulo(
        id_obra: IdObra,
        numero: Annotated[int, Path(ge=1)],
        casa: ProduccionDep,
    ) -> CapituloInspeccionado:
        _obra_o_404(casa, id_obra)
        leido = casa.almacen.leer_capitulo(id_obra, numero)
        escenas = leido["escenas"]
        vigentes = {}
        for escena in escenas:
            borrador = casa.almacen.borrador_vigente(id_obra, escena.id)
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
    ) -> list[CriticaServida]:
        _obra_o_404(casa, id_obra)
        criticas = casa.almacen.listar(
            "Critica",
            id_obra,
            estado=estado,
            dimension=dimension,
            severidad=severidad,
            capitulo=capitulo,
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
            )
            for traza in casa.almacen.listar_trazas(
                id_obra, capitulo=capitulo, rol=rol, tarea=tarea
            )
        ]

    # --- RI-07. Auditar continuidad ----------------------------------------

    @app.get("/obras/{id_obra}/estado")
    def ver_estado(
        id_obra: IdObra,
        casa: ProduccionDep,
        capitulo: Annotated[int, Query(ge=1)] = 1,
    ) -> EstadoPlegado:
        _obra_o_404(casa, id_obra)
        return EstadoPlegado(
            id_obra=id_obra,
            capitulo=capitulo,
            estado=casa.almacen.estado_en(id_obra, capitulo),
            eventos=[
                evento.cuerpo | {"id": evento.id, "capitulo": evento.capitulo}
                for evento in casa.almacen.listar("EventoEstado", id_obra, orden="capitulo")
                if (evento.capitulo or 0) <= capitulo
            ],
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

    @app.get("/obras/{id_obra}/progreso", response_class=EventSourceResponse)
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
        """Retoma el paso siguiente al ultimo cerrado; no repite lo aceptado."""
        obra = _obra_o_404(casa, id_obra)
        casa.almacen.reanudar(id_obra)
        cerrados = [
            c.capitulo or 0
            for c in casa.almacen.listar("Capitulo", id_obra)
            if c.estado == "cerrado"
        ]
        objetivo = int(obra.cuerpo.get("capitulos_objetivo", 1))
        if max(cerrados, default=0) < objetivo:
            casa.arrancar(id_obra, objetivo)
        return Confirmacion(id_obra=id_obra, detenida=False, motivo=None)

    return app


def operaciones_de_escritura(app: FastAPI) -> list[str]:
    """Las rutas por las que el editor escribe algo. Tienen que ser tres."""
    escrituras: list[str] = []
    for ruta in app.routes:
        metodos: Iterator[str] = iter(getattr(ruta, "methods", []) or [])
        for metodo in metodos:
            if metodo in {"POST", "PUT", "PATCH", "DELETE"}:
                escrituras.append(f"{metodo} {getattr(ruta, 'path', '')}")
    return sorted(escrituras)
