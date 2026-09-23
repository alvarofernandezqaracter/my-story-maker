"""El contrato de la frontera entre backend/ y frontend/ (SPEC1 RI-10, RNF-09).

Metodo: `prueba`. Evidencia citable: el documento OpenAPI que genera el codigo
frente al fichero `backend/openapi.yaml` que esta versionado. Si el borde cambia
y el contrato no se regenera, estas pruebas fallan y dicen con que orden se
arregla; mientras no fallen, lo que hay escrito es lo que hace el servidor.
"""

from typing import Any

from novela import __version__
from novela.api.contrato import RUTA, documento, esta_al_dia, volcar

# La unica operacion sin respuesta tipada, y a proposito: OpenAPI no describe el
# interior de un flujo abierto (SPEC1 RI-08).
FLUJO = ("/obras/{id_obra}/progreso", "get")


def test_el_contrato_versionado_es_el_que_genera_el_codigo() -> None:
    """No hay orden que recordar: si el borde se movio, aqui mismo se vuelve a
    volcar el contrato y la prueba falla una vez, para que el cambio de frontera
    pase por el diff en lugar de descubrirse cuando rompa el cliente."""
    if esta_al_dia():
        return
    volcar()
    raise AssertionError(
        f"el borde HTTP cambio y el contrato no. Lo he vuelto a volcar en {RUTA}: "
        "revisa el diff y llevalo en el mismo commit que el cambio del borde."
    )


def test_el_contrato_dice_de_que_version_del_backend_es() -> None:
    assert documento()["info"]["version"] == __version__


def test_toda_operacion_declara_la_forma_de_lo_que_devuelve() -> None:
    """Un cliente generado desde el contrato solo sirve si el contrato tipa las
    respuestas. Una ruta sin tipo de retorno pasa desapercibida hasta aqui."""
    sin_forma = []
    for ruta, operaciones in documento()["paths"].items():
        for verbo, operacion in operaciones.items():
            if (ruta, verbo) == FLUJO:
                continue
            respuestas = operacion["responses"]
            correcta = next(c for c in respuestas if c.startswith("2"))
            contenido: dict[str, Any] = respuestas[correcta].get("content", {})
            if not contenido.get("application/json", {}).get("schema"):
                sin_forma.append(f"{verbo.upper()} {ruta}")
    assert not sin_forma, f"operaciones sin respuesta tipada: {sin_forma}"


def test_el_flujo_en_vivo_dice_que_viaja_dentro() -> None:
    """La excepcion de arriba no es un agujero. El cuerpo de un flujo no es un
    objeto y por eso no se tipa, pero la respuesta si nombra la forma que viaja
    en cada evento, y esa forma esta descrita en el contrato."""
    esquema = documento()
    respuesta = esquema["paths"][FLUJO[0]][FLUJO[1]]["responses"]["200"]
    assert "text/event-stream" in respuesta["content"]
    assert "Progreso" in respuesta["description"], (
        "el flujo no dice que forma lleva cada evento"
    )
    assert "Progreso" in esquema["components"]["schemas"], (
        "el flujo nombra una forma que el contrato no describe"
    )
