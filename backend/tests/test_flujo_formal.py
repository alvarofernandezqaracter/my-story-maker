"""SPEC1 4.17: el validador formal del flujo y los arreglos que pidio.

Metodo: `prueba`. Cada contraejemplo que TLC saco sobre el modelo de
`backend/formal/tla/` tiene aqui su caso en el codigo, y la ultima prueba pasa
TLC sobre el modelo entero cuando Java y `tla2tools.jar` estan en la maquina.
Evidencia: el recuento de caminantes a la vez y la salida literal de TLC.
"""

import threading
import time
from pathlib import Path
from typing import Any

from dobles import EjecutorFingido
from novela.api.aplicacion import Produccion


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
