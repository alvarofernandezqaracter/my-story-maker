"""Etapa 8, primera mitad: la linea base de deteccion por dimension.

Metodo: `prueba`. Casos sembrados con un defecto conocido de una sola dimension
por caso, y los mismos casos con esa dimension intacta para contar falsos
positivos.

**La primera medida fija la linea base, no exige umbral.** Lo que esta prueba
deja es la tabla, no un aprobado.

Va marcada `gasta` porque invoca agentes de verdad. Se lanza a proposito:

    pytest -m gasta tests/test_linea_base.py --override-ini=addopts=
"""

import json
from pathlib import Path
from typing import Any

import pytest

from casos_sembrados import CASOS, Caso
from novela.ejecutor import EjecutorDeSubagentes
from novela.nucleo.guion import Encargo
from novela.nucleo.presupuesto import estimar_tokens
from novela.nucleo.proyecciones import Ventana
from novela.tareas import CatalogoDelRepositorio
from novela.vocabularios import ROL_DE_TAREA

MEDIDAS = Path(__file__).resolve().parent.parent / "medidas"


def _materiales(caso: Caso, proyeccion: tuple[str, ...], texto: str) -> dict[str, Any]:
    """Arma a mano la proyeccion minima que el contrato declara."""
    disponibles: dict[str, Any] = {
        "contrato_de_escena": caso.contrato_de_escena,
        "texto_producido": [
            {"tipo": "Borrador", "escena": caso.contrato_de_escena.get("id"), "texto": texto}
        ],
        "canon": caso.canon,
        "estado_en_n_menos_1": caso.estado,
        "voces_del_elenco": [f for f in caso.canon if f.get("tipo") == "Personaje"],
        **caso.extra,
    }
    faltan = [material for material in proyeccion if material not in disponibles]
    if faltan:
        raise AssertionError(f"{caso.dimension}: el caso no trae {faltan}")
    return {material: disponibles[material] for material in proyeccion}


def _preguntar(
    ejecutor: EjecutorDeSubagentes, caso: Caso, texto: str
) -> tuple[bool, str]:
    """Manda una comprobacion real y dice si salio `Critica` de esa dimension."""
    catalogo = CatalogoDelRepositorio()
    contrato = catalogo.contrato(caso.tarea, caso.dimension)
    proyeccion = ("contrato_de_verificacion",) + catalogo.proyeccion_minima(
        caso.tarea, caso.dimension
    )
    materiales = {"contrato_de_verificacion": contrato} | _materiales(
        caso, catalogo.proyeccion_minima(caso.tarea, caso.dimension), texto
    )
    cuerpo = json.dumps(materiales, ensure_ascii=False, sort_keys=True)
    ventana = Ventana(materiales=materiales, texto=cuerpo, tokens=estimar_tokens(cuerpo))
    encargo = Encargo(
        paso=4,
        tarea=caso.tarea,
        rol=ROL_DE_TAREA[caso.tarea],
        unidad="escena",
        proyeccion=proyeccion,
        id_obra="obr_medida",
        capitulo=1,
        escena=str(caso.contrato_de_escena.get("id") or "esc_00000001"),
        dimension=caso.dimension,
    )
    resultado = ejecutor.ejecutar(encargo, ventana)
    criticas = [a for a in resultado.artefactos if a.tipo == "Critica"]
    senala = any(
        (a.dimension or a.cuerpo.get("dimension")) == caso.dimension for a in criticas
    )
    return senala, resultado.salida


@pytest.mark.gasta
def test_linea_base_de_deteccion_y_falsos_positivos() -> None:
    ejecutor = EjecutorDeSubagentes(catalogo=CatalogoDelRepositorio())
    filas = []
    for caso in CASOS:
        detecta, _ = _preguntar(ejecutor, caso, caso.con_defecto)
        inventa, _ = _preguntar(ejecutor, caso, caso.intacto)
        filas.append(
            {
                "dimension": caso.dimension,
                "rol": ROL_DE_TAREA[caso.tarea],
                "detecta_el_defecto": detecta,
                "inventa_sobre_el_intacto": inventa,
            }
        )
        print(
            f"{caso.dimension:38} detecta={'si' if detecta else 'NO':3} "
            f"falso_positivo={'SI' if inventa else 'no'}"
        )

    detectados = sum(1 for fila in filas if fila["detecta_el_defecto"])
    falsos = sum(1 for fila in filas if fila["inventa_sobre_el_intacto"])
    _escribir_tabla(filas, detectados, falsos)

    # La primera medida fija la linea base, no exige umbral: lo unico que se
    # exige es que la medida exista y cubra todas las dimensiones sembradas.
    assert len(filas) == len(CASOS)


def _escribir_tabla(filas: list[dict[str, Any]], detectados: int, falsos: int) -> None:
    MEDIDAS.mkdir(exist_ok=True)
    lineas = [
        "# Linea base de deteccion por dimension",
        "",
        "Casos sembrados con un defecto conocido de una sola dimension por caso, y",
        "los mismos casos con esa dimension intacta. **Es la linea base, no un",
        "umbral**: lo que mide es de donde se parte.",
        "",
        "| Dimension | Rol | Detecta el defecto | Inventa sobre el intacto |",
        "| --- | --- | --- | --- |",
    ]
    for fila in filas:
        lineas.append(
            f"| `{fila['dimension']}` | {fila['rol']} | "
            f"{'si' if fila['detecta_el_defecto'] else '**no**'} | "
            f"{'**si**' if fila['inventa_sobre_el_intacto'] else 'no'} |"
        )
    lineas += [
        "",
        f"Deteccion: {detectados} de {len(filas)}. "
        f"Falsos positivos: {falsos} de {len(filas)}.",
        "",
    ]
    (MEDIDAS / "linea-base-de-deteccion.md").write_text("\n".join(lineas), encoding="utf-8")
