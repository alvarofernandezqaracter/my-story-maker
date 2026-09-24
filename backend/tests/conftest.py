"""Lo que vale para toda la bateria.

**La bateria no manda nada a Langfuse** (SPEC1 RF-192), aunque la maquina tenga
un `.env` con claves en la raiz: cada prueba arranca con la observacion
apagada, y la que quiera mirar lo que se manda instala su Langfuse fingido.
"""

from collections.abc import Iterator

import pytest

from novela import observabilidad


@pytest.fixture(autouse=True)
def observacion_apagada() -> Iterator[None]:
    anterior = observabilidad.instalar(observabilidad.Observabilidad())
    yield
    observabilidad.instalar(anterior)
