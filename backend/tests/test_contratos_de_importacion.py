"""La frontera se comprueba sin ejecutar nada (validators.md 6).

Metodo: `analisis`. Evidencia citable: la salida de import-linter en verde
sobre el paquete y en rojo sobre una copia en la que se siembra, uno a uno, un
fichero que rompe cada contrato a proposito. Un contrato que no falla cuando
debe no protege de nada.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
FUENTE = RAIZ / "src" / "novela"
CONFIGURACION = RAIZ / ".importlinter"

# Un fichero por contrato, con la importacion que lo rompe.
SIEMBRAS: dict[str, dict[str, str]] = {
    "El apilado es api sobre nucleo sobre almacen": {
        "almacen/sembrado.py": "from novela import api\n\n__all__ = ['api']\n",
    },
    "Ninguna carpeta de tareas importa otra: se comunican por artefactos": {
        "tareas/alfa/__init__.py": "from novela.tareas import beta\n\n__all__ = ['beta']\n",
        "tareas/beta/__init__.py": "",
    },
    "Solo almacen abre la base de datos": {
        "nucleo/sembrado.py": "import sqlite3\n\n__all__ = ['sqlite3']\n",
    },
    "nucleo no importa ninguna tarea ni decide nada del dominio": {
        "nucleo/sembrado.py": "from novela import tareas\n\n__all__ = ['tareas']\n",
    },
    "El unico sitio con tipos declarados es el borde HTTP": {
        "almacen/sembrado.py": "import pydantic\n\n__all__ = ['pydantic']\n",
    },
    "Los validadores son funciones puras: no leen el almacen ni las tareas": {
        "validadores.py": "from novela import almacen\n\n__all__ = ['almacen']\n",
    },
    "El demostrador recibe la cronologia ya leida: no toca el almacen": {
        "demostrador.py": "from novela import almacen\n\n__all__ = ['almacen']\n",
    },
    "La observabilidad recibe lo ya leido: no toca el almacen ni las tareas": {
        "observabilidad.py": "from novela import almacen\n\n__all__ = ['almacen']\n",
    },
    "El juez de la novela no lee tareas, ni la API, ni Langfuse": {
        "juez_de_la_novela.py": "from novela import tareas\n\n__all__ = ['tareas']\n",
    },
}


def _pasar_el_linter(raiz_del_paquete: Path) -> subprocess.CompletedProcess[str]:
    entorno = dict(os.environ, PYTHONPATH=str(raiz_del_paquete))
    invocacion = "from importlinter.cli import lint_imports_command; lint_imports_command()"
    return subprocess.run(
        [sys.executable, "-c", invocacion, "--config", str(CONFIGURACION)],
        cwd=raiz_del_paquete,
        env=entorno,
        capture_output=True,
        text=True,
    )


def test_los_contratos_se_cumplen_sobre_el_paquete() -> None:
    resultado = _pasar_el_linter(RAIZ / "src")
    assert resultado.returncode == 0, resultado.stdout + resultado.stderr
    assert "0 broken" in resultado.stdout


@pytest.mark.parametrize("contrato", list(SIEMBRAS))
def test_cada_contrato_falla_sobre_un_fichero_sembrado(contrato: str, tmp_path: Path) -> None:
    copia = tmp_path / "novela"
    shutil.copytree(FUENTE, copia)
    for ruta_relativa, contenido in SIEMBRAS[contrato].items():
        destino = copia / ruta_relativa
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(contenido, encoding="utf-8")

    resultado = _pasar_el_linter(tmp_path)

    assert resultado.returncode != 0, (
        f"El contrato {contrato!r} no ha fallado sobre el fichero sembrado:\n"
        + resultado.stdout
    )
    assert f"{contrato} BROKEN" in resultado.stdout, resultado.stdout
