"""Las tareas de una tanda corren a la vez (SPEC1 RF-13, D-51).

Metodo: `prueba`. Un ejecutor fingido que declara `simultaneo` y tarda un poco
en contestar deja ver cuantas tareas tiene abiertas a la vez. Lo que tiene que
salir: cada tanda abre todas sus tareas de golpe y ninguna mas, el recorrido es
el mismo que en serie, y si una tarea detiene la obra la tanda cierra antes de
parar. De paso ejercita el almacen con escrituras de verdad concurrentes, que
es lo que `validators.md` §6 pide no suponer.
"""

import threading
import time
from collections import defaultdict
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
class EjecutorEnParalelo(EjecutorFingido):
    """El fingido de siempre, pero admite tareas a la vez y las cuenta.

    Sus respuestas dependen del orden de llegada, asi que contesta de una en
    una; lo que corre a la vez es la espera, que es lo que en un subagente de
    verdad cuesta el tiempo.
    """

    simultaneo = True
    falla_en: str | None = None
    abiertas_por_paso: dict[int, int] = field(default_factory=lambda: defaultdict(int))
    pico_por_paso: dict[int, int] = field(default_factory=lambda: defaultdict(int))
    _cuenta: threading.Lock = field(default_factory=threading.Lock)
    _turno: threading.Lock = field(default_factory=threading.Lock)

    def ejecutar(self, encargo: Encargo, ventana: Ventana):  # type: ignore[no-untyped-def]
        with self._cuenta:
            self.abiertas_por_paso[encargo.paso] += 1
            self.pico_por_paso[encargo.paso] = max(
                self.pico_por_paso[encargo.paso], self.abiertas_por_paso[encargo.paso]
            )
        try:
            time.sleep(ESPERA_EN_SEGUNDOS)
            if self.falla_en is not None and encargo.tarea == self.falla_en:
                with self._turno:
                    self.llamadas.append(encargo)
                raise RuntimeError(f"{encargo.tarea} fallo a proposito")
            with self._turno:
                return super().ejecutar(encargo, ventana)
        finally:
            with self._cuenta:
                self.abiertas_por_paso[encargo.paso] -= 1


def _caminar(ruta: Path, ejecutor: EjecutorFingido) -> tuple[Almacen, str, Informe]:
    almacen = abrir_almacen(ruta)
    id_obra = almacen.crear_obra(BRIEF)
    caminante = Caminante(almacen, ejecutor, catalogo=CatalogoFingido())
    caminante._fuera_del_guion("poblar_mundo", id_obra)
    return almacen, id_obra, caminante.caminar_capitulo(id_obra, 1)


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
            assert ejecutor.pico_por_paso[paso] == mas_ancha, (
                f"el paso {paso} no abrio su tanda entera a la vez"
            )
        assert ejecutor.pico_por_paso[4] > 1, "la criba de bloqueantes sigue yendo en serie"
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


def test_si_una_tarea_detiene_la_obra_su_tanda_cierra_antes_de_parar(tmp_path: Path) -> None:
    """El paso 3 declara `detener_obra` y las tres escenas fallan: la primera
    que agota sus intentos detiene la obra, y las otras dos, que ya estaban
    abiertas, agotan los suyos igual. En serie solo se habria intentado una."""
    ejecutor = EjecutorEnParalelo(falla_en="redactar")
    almacen = abrir_almacen(tmp_path / "detenida.sqlite3")
    id_obra = almacen.crear_obra(BRIEF)
    caminante = Caminante(almacen, ejecutor, catalogo=CatalogoFingido())
    caminante._fuera_del_guion("poblar_mundo", id_obra)
    try:
        with pytest.raises(ProduccionDetenida):
            caminante.caminar_capitulo(id_obra, 1)
        redactar = [e for e in ejecutor.llamadas if e.tarea == "redactar"]
        assert len(redactar) == 3 * guion.paso(3).reintentos
        assert almacen.esta_detenida(id_obra)
        assert almacen.trazas_abiertas(id_obra) == []
    finally:
        almacen.cerrar()
