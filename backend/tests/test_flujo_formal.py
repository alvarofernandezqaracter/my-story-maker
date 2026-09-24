"""SPEC1 4.17: el validador formal del flujo y los arreglos que pidio.

Metodo: `prueba`. Cada contraejemplo que TLC saco sobre el modelo de
`backend/formal/tla/` tiene aqui su caso en el codigo, y la ultima prueba pasa
TLC sobre el modelo entero cuando Java y `tla2tools.jar` estan en la maquina.
Evidencia: el recuento de caminantes a la vez y la salida literal de TLC.
"""

import os
import shutil
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

import pytest

from dobles import CatalogoFingido, EjecutorFingido
from novela.almacen.artefactos import abrir_almacen
from novela.api.aplicacion import Produccion
from novela.nucleo import presupuesto
from novela.nucleo.caminante import Caminante


class _HilosLentos(dict[str, threading.Thread]):
    """Ensancha la ventana entre leer el hilo anterior y registrar el nuevo,
    que es donde cabian dos arranques a la vez."""

    def get(self, clave: str, defecto: Any = None) -> Any:
        leido = super().get(clave, defecto)
        time.sleep(0.05)
        return leido


class _CaminanteQueCuenta:
    def __init__(self, cuenta: dict[str, int], cerrojo: threading.Lock) -> None:
        self.cuenta = cuenta
        self.cerrojo = cerrojo

    def caminar_obra(self, id_obra: str, capitulos: int) -> list[Any]:
        with self.cerrojo:
            self.cuenta["ahora"] += 1
            self.cuenta["pico"] = max(self.cuenta["pico"], self.cuenta["ahora"])
        time.sleep(0.1)
        with self.cerrojo:
            self.cuenta["ahora"] -= 1
        return []


def test_dos_arranques_a_la_vez_no_dejan_dos_caminantes(tmp_path: Path) -> None:
    """Contraejemplo 01 (RF-166): dos `reanudar` que llegan a la vez leian el
    mismo hilo anterior y dejaban dos caminantes sobre la obra."""
    casa = Produccion(tmp_path / "arranque.sqlite3", EjecutorFingido())
    try:
        cuenta = {"ahora": 0, "pico": 0}
        cerrojo = threading.Lock()
        casa.hilos = _HilosLentos()
        casa.caminante = lambda: _CaminanteQueCuenta(cuenta, cerrojo)  # type: ignore[assignment,return-value]
        salida = threading.Barrier(2)

        def reanudar() -> None:
            salida.wait()
            casa.arrancar("obra_x", 1)

        ordenes = [threading.Thread(target=reanudar) for _ in range(2)]
        for orden in ordenes:
            orden.start()
        for orden in ordenes:
            orden.join()
        casa.hilos["obra_x"].join()
        assert cuenta["pico"] == 1
    finally:
        casa.cerrar()


def test_un_fallo_no_previsto_detiene_la_obra_y_dice_por_que(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Contraejemplo 02 (RF-167): una excepcion que no es la detencion mataba el
    hilo y dejaba la obra ni detenida ni terminada, sin que nada la moviese."""
    almacen = abrir_almacen(tmp_path / "fallo.sqlite3")
    try:
        id_obra = almacen.crear_obra(
            {"titulo": "T", "epoca": "Sevilla, 1587", "premisa": "P", "capitulos_objetivo": 2}
        )
        caminante = Caminante(almacen, EjecutorFingido(), catalogo=CatalogoFingido())  # type: ignore[arg-type]

        def no_cabe(id_obra: str, numero: int) -> Any:
            raise presupuesto.NoCabeNiPartiendo("la ventana no cabe y no hay en que partirla")

        monkeypatch.setattr(caminante, "caminar_capitulo", no_cabe)
        with pytest.raises(presupuesto.NoCabeNiPartiendo):
            caminante.caminar_obra(id_obra, 2)
        assert almacen.esta_detenida(id_obra)
        motivo = almacen.motivo_de_la_detencion(id_obra) or ""
        assert "NoCabeNiPartiendo" in motivo
    finally:
        almacen.cerrar()


# --- RF-160 a RF-162 y RF-168: TLC sobre el modelo entero ---------------------

MODELO = Path(__file__).resolve().parents[1] / "formal" / "tla"


def _java() -> str | None:
    casa = os.environ.get("JAVA_HOME")
    if casa:
        for nombre in ("java.exe", "java"):
            candidato = Path(casa) / "bin" / nombre
            if candidato.is_file():
                return str(candidato)
    return shutil.which("java")


@pytest.mark.lento
def test_tlc_recorre_el_modelo_sin_encontrar_error(tmp_path: Path) -> None:
    """TLC recorre entero `Produccion.cfg`: tres invariantes de seguridad, sus
    auxiliares y la vivacidad. Sin Java o sin `tla2tools.jar` se salta y dice
    que falta; los ficheros de trabajo de TLC van a un directorio temporal."""
    java = _java()
    jar = os.environ.get("NOVELA_TLA2TOOLS")
    if java is None:
        pytest.skip("no hay Java: ni JAVA_HOME ni `java` en el PATH")
    if not jar or not Path(jar).is_file():
        pytest.skip("NOVELA_TLA2TOOLS no apunta a un tla2tools.jar")
    salida = subprocess.run(
        [
            java, "-XX:+UseParallelGC", "-cp", jar, "tlc2.TLC",
            "-workers", "auto", "-noGenerateSpecTE", "-metadir", str(tmp_path / "tlc"),
            "-config", "Produccion.cfg", "Produccion.tla",
        ],
        cwd=MODELO, capture_output=True, text=True, timeout=1800, check=False,
    )
    texto = salida.stdout + salida.stderr
    assert "Model checking completed. No error has been found." in texto, texto[-4000:]
    assert salida.returncode == 0
    assert not list(MODELO.glob("*_TTrace_*")), "TLC dejo ficheros en el repositorio"
