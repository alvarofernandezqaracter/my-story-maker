"""Las tareas de una tanda corren a la vez (SPEC1 RF-13, D-88).

Metodo: `prueba`. Un ejecutor fingido que declara `simultaneo` y tarda un poco
en contestar deja ver cuantas tareas tiene abiertas a la vez. Lo que tiene que
salir: cada tanda abre todas sus tareas de golpe y ninguna mas, el recorrido es
el mismo que en serie, si una tarea detiene la obra la tanda cierra antes de
parar y un `reanudar` dado mientras cierra no se deshace, dos obras a la vez se
turnan las tandas en vez de sumarlas, los hilos no dejan lectores abiertos y
quien lee el capitulo entero lo lee en el orden de las escenas. De paso
ejercita el almacen con escrituras de verdad concurrentes, que es lo que
`validators.md` §6 pide no suponer.
"""

import threading
import time
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from dobles import CatalogoFingido, EjecutorFingido
from novela.almacen import Almacen
from novela.almacen.artefactos import abrir_almacen
from novela.nucleo import guion, presupuesto
from novela.nucleo.caminante import Apunte, Caminante, Informe, ProduccionDetenida
from novela.nucleo.guion import Encargo
from novela.nucleo.proyecciones import Ventana

BRIEF = {
    "titulo": "El taller de la calle de las Sierpes",
    "epoca": "Sevilla, 1587",
    "premisa": "Una impresora clandestina",
    "politicas_globales": {"pov": "tercera_limitada"},
    "capitulos_objetivo": 1,
}

# Lo que tarda en contestar cada tarea fingida. Basta con que sea mucho mas que
# lo que se tarda en abrir la tanda entera.
ESPERA_EN_SEGUNDOS = 0.05


@dataclass
class Contador:
    """Cuantas tareas hay abiertas a la vez, por paso y en total. Se puede
    compartir entre dos ejecutores para ver la instalacion entera."""

    abiertas_por_paso: dict[int, int] = field(default_factory=lambda: defaultdict(int))
    pico_por_paso: dict[int, int] = field(default_factory=lambda: defaultdict(int))
    abiertas: int = 0
    pico: int = 0
    _cerrojo: threading.Lock = field(default_factory=threading.Lock)

    def abrir(self, paso: int) -> None:
        with self._cerrojo:
            self.abiertas += 1
            self.pico = max(self.pico, self.abiertas)
            self.abiertas_por_paso[paso] += 1
            self.pico_por_paso[paso] = max(
                self.pico_por_paso[paso], self.abiertas_por_paso[paso]
            )

    def cerrar(self, paso: int) -> None:
        with self._cerrojo:
            self.abiertas -= 1
            self.abiertas_por_paso[paso] -= 1


def _espera_fija(_: Encargo) -> float:
    return ESPERA_EN_SEGUNDOS


def _nunca(_: Encargo) -> bool:
    return False


def _nada(_: Encargo) -> None:
    return None


@dataclass
class EjecutorEnParalelo(EjecutorFingido):
    """El fingido de siempre, pero admite tareas a la vez y las cuenta.

    Sus respuestas dependen del orden de llegada, asi que contesta de una en
    una; lo que corre a la vez es la espera, que es lo que en un subagente de
    verdad cuesta el tiempo.
    """

    simultaneo = True
    contador: Contador = field(default_factory=Contador)
    retraso: Callable[[Encargo], float] = _espera_fija
    falla: Callable[[Encargo], bool] = _nunca
    antes_de_fallar: Callable[[Encargo], None] = _nada
    _turno: threading.Lock = field(default_factory=threading.Lock)

    def ejecutar(self, encargo: Encargo, ventana: Ventana):  # type: ignore[no-untyped-def]
        self.contador.abrir(encargo.paso)
        try:
            time.sleep(self.retraso(encargo))
            if self.falla(encargo):
                with self._turno:
                    self.llamadas.append(encargo)
                self.antes_de_fallar(encargo)
                raise RuntimeError(f"{encargo.tarea} fallo a proposito")
            with self._turno:
                return super().ejecutar(encargo, ventana)
        finally:
            self.contador.cerrar(encargo.paso)


def _obra(almacen: Almacen, ejecutor: EjecutorFingido) -> tuple[str, Caminante]:
    id_obra = almacen.crear_obra(BRIEF)
    caminante = Caminante(almacen, ejecutor, catalogo=CatalogoFingido())
    caminante._fuera_del_guion("poblar_mundo", id_obra)
    return id_obra, caminante


def _caminar(ruta: Path, ejecutor: EjecutorFingido) -> tuple[Almacen, str, Informe]:
    almacen = abrir_almacen(ruta)
    id_obra, caminante = _obra(almacen, ejecutor)
    return almacen, id_obra, caminante.caminar_capitulo(id_obra, 1)


def _posicion(almacen: Almacen, encargo: Encargo) -> int:
    escenas = almacen.listar(
        "Escena", encargo.id_obra, capitulo=encargo.capitulo, orden="orden"
    )
    return [escena.id for escena in escenas].index(encargo.escena)


def _normalizar(recorrido: list[Apunte]) -> list[tuple[int, str, str, int, int, str | None]]:
    """La misma secuencia con las escenas por su orden, no por su `id`."""
    orden: dict[str, int] = {}
    for apunte in recorrido:
        if apunte.escena and apunte.escena not in orden:
            orden[apunte.escena] = len(orden)
    return [
        (a.paso, a.tarea, a.rol, a.tanda, orden.get(a.escena or "", -1), a.dimension)
        for a in recorrido
    ]


def _la_tanda_mas_ancha() -> int:
    """La tanda mas ancha de un capitulo de tres escenas, paso a paso."""
    return max(
        presupuesto.anchura_de_tanda(
            guion.expandir(guion.paso(paso), escenas=("a", "b", "c"))
        )
        for paso in (2, 3, 4, 6, 8)
    )


def test_cada_tanda_abre_todas_sus_tareas_a_la_vez_y_ninguna_mas(tmp_path: Path) -> None:
    ejecutor = EjecutorEnParalelo()
    almacen, _, informe = _caminar(tmp_path / "paralelo.sqlite3", ejecutor)
    try:
        for paso in (2, 3, 4, 6, 8):
            encargos = guion.expandir(guion.paso(paso), escenas=("a", "b", "c"))
            anchura = presupuesto.anchura_de_tanda(encargos)
            mas_ancha = max(
                sum(1 for a in informe.recorrido if a.tanda == numero)
                for numero in {a.tanda for a in informe.recorrido if a.paso == paso}
            )
            assert mas_ancha <= anchura, f"el paso {paso} abre una tanda mas ancha que la suya"
            assert ejecutor.contador.pico_por_paso[paso] == mas_ancha, (
                f"el paso {paso} no abrio su tanda entera a la vez"
            )
        assert ejecutor.contador.pico_por_paso[4] > 1, "la criba de bloqueantes sigue en serie"
    finally:
        almacen.cerrar()


def test_en_paralelo_el_recorrido_es_el_mismo_que_en_serie(tmp_path: Path) -> None:
    en_serie, _, serie = _caminar(tmp_path / "serie.sqlite3", EjecutorFingido())
    en_paralelo, id_obra, paralelo = _caminar(
        tmp_path / "paralelo.sqlite3", EjecutorEnParalelo()
    )
    try:
        assert _normalizar(paralelo.recorrido) == _normalizar(serie.recorrido)
        assert paralelo.estado == serie.estado == "cerrado"
        assert en_paralelo.trazas_abiertas(id_obra) == []
    finally:
        en_serie.cerrar()
        en_paralelo.cerrar()


def test_los_hilos_de_la_tanda_no_dejan_lectores_abiertos(tmp_path: Path) -> None:
    """Cada hilo de una tanda abre su lector del almacen y lo suelta al morir:
    un capitulo entero deja, como mucho, el del hilo que camina."""
    almacen, _, _ = _caminar(tmp_path / "lectores.sqlite3", EjecutorEnParalelo())
    try:
        assert len(almacen._lectores) <= 1
    finally:
        almacen.cerrar()


def test_quien_lee_el_capitulo_entero_lo_lee_en_el_orden_de_las_escenas(
    tmp_path: Path,
) -> None:
    """Las escenas se redactan a la vez y aqui terminan al reves, la ultima la
    primera: la costura tiene que recibirlas igualmente en su orden."""
    almacen = abrir_almacen(tmp_path / "orden.sqlite3")

    def al_reves(encargo: Encargo) -> float:
        if encargo.tarea != "redactar":
            return ESPERA_EN_SEGUNDOS
        return 0.1 * (3 - _posicion(almacen, encargo))

    ejecutor = EjecutorEnParalelo(retraso=al_reves)
    id_obra, caminante = _obra(almacen, ejecutor)
    try:
        caminante.caminar_capitulo(id_obra, 1)
        escenas = [e.id for e in almacen.listar("Escena", id_obra, capitulo=1, orden="orden")]
        costura = next(
            ventana
            for encargo, ventana in zip(ejecutor.llamadas, ejecutor.ventanas, strict=True)
            if encargo.paso == 7
        )
        leidas = [fila["escena"] for fila in costura.materiales["texto_producido"]]
        assert leidas == escenas
    finally:
        almacen.cerrar()


def test_si_una_tarea_detiene_la_obra_su_tanda_cierra_antes_de_parar(tmp_path: Path) -> None:
    """El paso 3 declara `detener_obra` y las tres escenas fallan a la vez: las
    tres agotan sus dos intentos, la tanda cierra entera y solo entonces sube
    la excepcion. En serie solo se habria intentado una."""
    ejecutor = EjecutorEnParalelo(falla=lambda encargo: encargo.tarea == "redactar")
    almacen = abrir_almacen(tmp_path / "detenida.sqlite3")
    id_obra, caminante = _obra(almacen, ejecutor)
    try:
        with pytest.raises(ProduccionDetenida):
            caminante.caminar_capitulo(id_obra, 1)
        redactar = [e for e in ejecutor.llamadas if e.tarea == "redactar"]
        assert len(redactar) == 3 * guion.paso(3).reintentos
        assert almacen.esta_detenida(id_obra)
        assert almacen.trazas_abiertas(id_obra) == []
    finally:
        almacen.cerrar()


def test_reanudar_mientras_cierra_la_tanda_no_se_deshace(tmp_path: Path) -> None:
    """La primera escena agota enseguida y detiene la obra. Mientras las otras
    dos terminan, el editor reanuda: ellas ya no intentan otra vez ni vuelven a
    detenerla, asi que la orden del editor se queda como la dio."""
    almacen = abrir_almacen(tmp_path / "reanudada.sqlite3")
    # La primera no falla hasta que las otras dos estan dentro de su intento:
    # si no, podria detener la obra antes de que empezaran y no habria nada
    # abierto que cerrar.
    dentro: list[Encargo] = []
    las_dos_dentro = threading.Event()

    def retraso(encargo: Encargo) -> float:
        if encargo.tarea != "redactar":
            return 0.0
        if _posicion(almacen, encargo) == 0:
            las_dos_dentro.wait(timeout=5)
            return 0.0
        dentro.append(encargo)
        if len(dentro) >= 2:
            las_dos_dentro.set()
        return 0.3

    def reanuda_el_editor(encargo: Encargo) -> None:
        if almacen.esta_detenida(encargo.id_obra):
            almacen.reanudar(encargo.id_obra)

    ejecutor = EjecutorEnParalelo(
        retraso=retraso,
        falla=lambda encargo: encargo.tarea == "redactar",
        antes_de_fallar=reanuda_el_editor,
    )
    id_obra, caminante = _obra(almacen, ejecutor)
    try:
        with pytest.raises(ProduccionDetenida):
            caminante.caminar_capitulo(id_obra, 1)
        assert not almacen.esta_detenida(id_obra), "la tanda deshizo el reanudar del editor"
        assert almacen.trazas_abiertas(id_obra) == []
    finally:
        almacen.cerrar()


def test_dos_obras_a_la_vez_se_turnan_las_tandas(tmp_path: Path) -> None:
    """El techo es de la instalacion (SPEC1 §11): con dos obras caminando, lo
    abierto a la vez entre las dos no pasa de la tanda mas ancha de una."""
    almacen = abrir_almacen(tmp_path / "dos.sqlite3")
    contador = Contador()
    obras = [_obra(almacen, EjecutorEnParalelo(contador=contador)) for _ in range(2)]
    errores: list[BaseException] = []

    def caminar(id_obra: str, caminante: Caminante) -> None:
        try:
            caminante.caminar_capitulo(id_obra, 1)
        except BaseException as error:  # noqa: BLE001
            errores.append(error)

    hilos = [threading.Thread(target=caminar, args=obra) for obra in obras]
    try:
        for hilo in hilos:
            hilo.start()
        for hilo in hilos:
            hilo.join()
        assert errores == []
        assert contador.pico <= _la_tanda_mas_ancha()
    finally:
        almacen.cerrar()
