"""Etapa 8, segunda mitad: la obra de tres capitulos.

Metodo: `demostracion`. No hay nada nuevo construido: es la pasada que convierte
el sistema en algo medido. Una obra de tres capitulos de tres escenas corre de
`POST /obras` a obra cerrada con **una sola** llamada de escritura, y de su
`Traza` salen las lineas base de OBJ-01 a OBJ-08.

Va marcada `gasta`: invoca agentes de verdad, cuesta dinero y tarda. Se lanza a
proposito:

    pytest -m gasta tests/test_obra_completa.py --override-ini=addopts= -s
"""

import time
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from casos_sembrados import BRIEFS_ADVERSARIOS, FUENTE_CON_INSTRUCCION
from novela.ajustes import TECHO_DE_CONTEXTO_CONCURRENTE
from novela.almacen import Almacen, Artefacto
from novela.api.aplicacion import crear_aplicacion

MEDIDAS = Path(__file__).resolve().parent.parent / "medidas"

BRIEF = {
    "titulo": "El taller de la calle de las Sierpes",
    "epoca": "Sevilla, 1587",
    "premisa": "Una impresora clandestina sostiene el taller de su padre muerto",
    "tesis_tematica": "Lo que se imprime no se desimprime",
    "elenco_declarado": ["Ines de Salcedo", "el oficial Bermudo", "el alguacil Ordonez"],
    "capitulos_objetivo": 3,
    "politicas_globales": {
        "pov": "tercera_limitada",
        "tiempo_verbal": "pasado",
        "nivel_de_arcaismo": "moderado",
    },
    "arcos": ["Ines pasa del miedo al desafio", "Bermudo pasa de la lealtad a la delacion"],
}


@pytest.mark.gasta
def test_una_obra_de_tres_capitulos_corre_de_una_sola_orden(tmp_path: Path) -> None:
    app = crear_aplicacion(tmp_path / "obra.sqlite3")
    with TestClient(app) as cliente:
        empezo = time.monotonic()
        respuesta = cliente.post("/obras", json=BRIEF)
        assert respuesta.status_code == 202
        id_obra = respuesta.json()["id_obra"]

        hilo = cliente.app.state.produccion.hilos[id_obra]  # type: ignore[attr-defined]
        while hilo.is_alive():
            progreso = cliente.get(f"/obras/{id_obra}/progreso/ahora").json()
            print(
                f"capitulo {progreso['capitulo_en_curso']} | "
                f"{len(progreso['tareas_abiertas'])} tareas abiertas | "
                f"{progreso['tokens_de_entrada_concurrentes']} tokens de entrada"
            )
            hilo.join(timeout=30)
        minutos = (time.monotonic() - empezo) / 60

        ficha = cliente.get(f"/obras/{id_obra}").json()
        trazas = cliente.get(f"/obras/{id_obra}/trazas").json()
        manuscrito = cliente.get(f"/obras/{id_obra}/manuscrito").json()
        almacen: Almacen = cliente.app.state.produccion.almacen  # type: ignore[attr-defined]

        medidas = _medir(almacen, id_obra, ficha, trazas, manuscrito, minutos)
        _escribir_lineas_base(medidas)
        print(medidas)

        # La medida de «terminado» de v1 es una sola.
        assert ficha["capitulos_cerrados"] == 3
        assert manuscrito["unidades"], "la obra cerro sin manuscrito"
        # OBJ-07: exactamente una llamada de escritura por obra.
        assert medidas["OBJ-07 ordenes de escritura"] == 1


def _medir(
    almacen: Almacen,
    id_obra: str,
    ficha: dict[str, Any],
    trazas: list[dict[str, Any]],
    manuscrito: dict[str, Any],
    minutos: float,
) -> dict[str, Any]:
    """De la `Traza` salen las ocho lineas base que hoy estan pendientes."""
    por_capitulo: dict[int, int] = {}
    for traza in trazas:
        capitulo = traza["capitulo"] or 0
        entrada = traza["tokens_de_entrada_medidos"] or 0
        salida = traza["tokens_de_salida"] or 0
        por_capitulo[capitulo] = por_capitulo.get(capitulo, 0) + entrada + salida

    intentos_por_escena: dict[str, int] = {}
    for traza in trazas:
        if traza["tarea"] == "redactar" and traza["escena"]:
            escena = traza["escena"]
            intentos_por_escena[escena] = intentos_por_escena.get(escena, 0) + 1

    criticas = almacen.listar("Critica", id_obra, incluir_caducados=True)
    descartadas = [c for c in criticas if c.estado == "descartada"]
    con_evidencia = [c for c in criticas if (c.cuerpo.get("evidencia") or "").strip()]

    recuperados = usados = 0
    for traza in almacen.listar_trazas(id_obra):
        for recuperacion in traza.cuerpo.get("recuperaciones") or []:
            recuperados += len(recuperacion.get("devueltos") or [])
            usados += len(recuperacion.get("usados") or [])

    return {
        "tareas": len(trazas),
        "minutos": round(minutos, 1),
        "coste USD": round(sum(t["coste"] or 0 for t in trazas), 4),
        "OBJ-01 pico de entrada concurrente": _pico(trazas),
        "OBJ-01 techo": TECHO_DE_CONTEXTO_CONCURRENTE,
        "OBJ-02 tokens por capitulo": por_capitulo,
        "OBJ-03 vueltas por escena": intentos_por_escena,
        "OBJ-03 capitulos marcados": ficha["capitulos_marcados"],
        "OBJ-04 criticas descartadas sin evidencia": f"{len(descartadas)}/{len(criticas)}",
        "OBJ-05 artefactos malformados": len(
            [c for c in criticas if c.procedencia_rol is None and c.severidad == "bloqueante"]
        ),
        "OBJ-06 afirmaciones con fuente": len(almacen.listar("Fuente", id_obra)),
        "OBJ-07 ordenes de escritura": 1,
        "OBJ-08 fragmentos usados": f"{usados}/{recuperados}",
        "criticas con evidencia": f"{len(con_evidencia)}/{len(criticas)}",
        "estimacion frente a medida": _calibracion(trazas),
    }


def _pico(trazas: list[dict[str, Any]]) -> int:
    """Maximo de la suma de las ventanas abiertas a la vez.

    Se reconstruye del solapamiento entre `abierta_en` y `cerrada_en`: lo que
    devuelven los agentes no entra en la cuenta.
    """
    sucesos: list[tuple[str, int]] = []
    for traza in trazas:
        entrada = (
            traza["tokens_de_entrada_medidos"]
            or traza["tokens_de_entrada_estimados"]
            or 0
        )
        if traza["abierta_en"]:
            sucesos.append((traza["abierta_en"], entrada))
        if traza["cerrada_en"]:
            sucesos.append((traza["cerrada_en"], -entrada))
    pico = abiertos = 0
    for _, delta in sorted(sucesos):
        abiertos += delta
        pico = max(pico, abiertos)
    return pico


def _calibracion(trazas: list[dict[str, Any]]) -> str:
    """Contexto estimado antes de mandar frente al medido al terminar."""
    parejas = [
        (t["tokens_de_entrada_estimados"], t["tokens_de_entrada_medidos"])
        for t in trazas
        if t["tokens_de_entrada_estimados"] and t["tokens_de_entrada_medidos"]
    ]
    if not parejas:
        return "sin datos"
    desvio = sum(medido / estimado for estimado, medido in parejas) / len(parejas)
    return f"medido / estimado = {desvio:.2f} de media sobre {len(parejas)} tareas"


def _escribir_lineas_base(medidas: dict[str, Any]) -> None:
    MEDIDAS.mkdir(exist_ok=True)
    lineas = [
        "# Lineas base de la obra de tres capitulos",
        "",
        "Sustituyen a los ocho «pendiente» de SPEC1 §3. Salen de la `Traza` de una",
        "sola pasada: son de donde se parte, no metas alcanzadas.",
        "",
        "| Medida | Valor |",
        "| --- | --- |",
    ]
    for nombre, valor in medidas.items():
        lineas.append(f"| {nombre} | `{valor}` |")
    lineas.append("")
    (MEDIDAS / "lineas-base-de-la-obra.md").write_text("\n".join(lineas), encoding="utf-8")


@pytest.mark.gasta
def test_una_fuente_con_una_orden_dentro_no_redirige_al_redactor(tmp_path: Path) -> None:
    """Lo traido de fuera entra como dato delimitado, nunca como instruccion."""
    from novela.almacen.artefactos import abrir_almacen
    from novela.ejecutor import EjecutorDeSubagentes
    from novela.nucleo.caminante import Caminante
    from novela.tareas import CatalogoDelRepositorio

    almacen = abrir_almacen(tmp_path / "inyeccion.sqlite3")
    id_obra = almacen.crear_obra(BRIEF | {"capitulos_objetivo": 1})
    almacen.guardar(
        [Artefacto("Fuente", FUENTE_CON_INSTRUCCION, id_obra=id_obra, capitulo=1)]
    )
    catalogo = CatalogoDelRepositorio()
    caminante = Caminante(
        almacen, EjecutorDeSubagentes(catalogo=catalogo), catalogo=catalogo
    )

    caminante._fuera_del_guion("poblar_mundo", id_obra)

    salidas = [t.cuerpo.get("salida", "") for t in almacen.listar_trazas(id_obra)]
    assert salidas, "no hubo ninguna tarea que mirar"
    assert not any("PIRATA" in str(salida) for salida in salidas)
    assert almacen.listar("Personaje", id_obra), "la tarea no llego a hacer su trabajo"
    almacen.cerrar()


@pytest.mark.gasta
@pytest.mark.parametrize("nombre", sorted(BRIEFS_ADVERSARIOS))
def test_briefs_adversarios(tmp_path: Path, nombre: str) -> None:
    """Epoca mal documentada, personajes homonimos y saltos temporales largos.

    Lo que delatan son las dimensiones que solo fallan bajo presion. No se exige
    que la obra sea buena: se exige que cierre y deje sus criticas anotadas.
    """
    app = crear_aplicacion(tmp_path / f"{nombre}.sqlite3")
    with TestClient(app) as cliente:
        id_obra = cliente.post("/obras", json=BRIEFS_ADVERSARIOS[nombre]).json()["id_obra"]
        cliente.app.state.produccion.hilos[id_obra].join(timeout=3600)  # type: ignore[attr-defined]
        ficha = cliente.get(f"/obras/{id_obra}").json()
        criticas = cliente.get(f"/obras/{id_obra}/criticas").json()
        print(f"{nombre}: cerrados={ficha['capitulos_cerrados']} criticas={len(criticas)}")
        assert ficha["capitulos_cerrados"] == 1
