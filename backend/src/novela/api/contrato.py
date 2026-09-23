"""El contrato de la frontera, volcado a un fichero (SPEC1 RI-10, RNF-09, D-11).

Es utillaje del ciclo de edicion, no del servidor: `principal.py` no lo importa
y nada de lo que corre en produccion lo carga. El documento OpenAPI no se
redacta, se genera desde los modelos declarados en `modelos.py`, que son el
unico sitio donde el backend impone tipos (D-01). Asi no hay dos descripciones
del mismo borde que puedan divergir: hay una, y la otra es su volcado.

Nadie tiene que acordarse de regenerarlo. Quien lo vuelca es la prueba de
`tests/test_contrato_de_frontera.py`: si el borde cambio, reescribe el fichero
y falla una vez, para que el movimiento de la frontera se vea en el diff.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from novela.api.aplicacion import crear_aplicacion

# src/novela/api/contrato.py -> backend/openapi.yaml
RUTA = Path(__file__).resolve().parents[3] / "openapi.yaml"

ENCABEZADO = (
    "# Contrato de la frontera entre backend/ y frontend/ (SPEC1 RI-10, D-11).\n"
    "# Generado desde los modelos del borde; no se edita a mano. Lo vuelca la\n"
    "# prueba tests/test_contrato_de_frontera.py cuando el borde cambia.\n"
)


def documento() -> dict[str, Any]:
    """El OpenAPI que publica la aplicacion, sin abrir la base de datos."""
    return crear_aplicacion().openapi()


def en_yaml() -> str:
    """El mismo documento como texto, que es lo que se versiona y se difunde."""
    cuerpo = yaml.safe_dump(
        documento(),
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
    )
    return ENCABEZADO + cuerpo


def esta_al_dia(ruta: Path = RUTA) -> bool:
    return ruta.is_file() and ruta.read_text(encoding="utf-8") == en_yaml()


def volcar(ruta: Path = RUTA) -> Path:
    ruta.write_text(en_yaml(), encoding="utf-8", newline="\n")
    return ruta
