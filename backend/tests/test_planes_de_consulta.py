"""Ninguna consulta recorre una tabla que crece con la obra.

Metodo: `analisis`. Evidencia citable: el `EXPLAIN QUERY PLAN` de cada consulta
que el almacen ejecuta de verdad. En vez de copiar aqui las consultas —que se
separarian del codigo en cuanto una cambiase— se escucha a la conexion de
lectura mientras se ejerce la interfaz entera y se explica lo que haya pasado
por ella.

`SCAN` sobre una tabla que crece con la obra es un fallo, no un aviso.
"""

from pathlib import Path

import pytest

from novela.almacen import Almacen, Artefacto
from novela.almacen.artefactos import abrir_almacen

# Recorrer estas de arriba abajo no cuesta con la obra: `artefacto_obra` tiene
# una fila por obra y `control_de_ejecucion` tambien.
RECORRIDO_ADMITIDO = {"artefacto_obra", "control_de_ejecucion", "migracion"}


@pytest.fixture
def poblado(tmp_path: Path) -> tuple[Almacen, str]:
    almacen = abrir_almacen(tmp_path / "planes.sqlite3")
    id_obra = almacen.crear_obra({"titulo": "Obra de prueba"})
    for numero in (1, 2):
        almacen.guardar(
            [Artefacto("Capitulo", {"numero": numero}, id_obra=id_obra, capitulo=numero,
                       estado="planificado")]
        )
        for orden in (1, 2, 3):
            id_escena = almacen.guardar(
                [Artefacto("Escena", {"pov": "per_00000001"}, id_obra=id_obra,
                           capitulo=numero, orden=orden, estado="planificado")]
            )[0]
            id_borrador = almacen.guardar_borrador(
                Artefacto("Borrador", {"texto": "Llovia sobre el patio."}, id_obra=id_obra,
                          capitulo=numero, escena=id_escena, estado="redactado")
            )
            almacen.aceptar_borrador(id_borrador)
            almacen.guardar_critica(
                Artefacto("Critica", {"evidencia": "«llovia» dos veces"}, id_obra=id_obra,
                          capitulo=numero, escena=id_escena, severidad="menor",
                          dimension="fatiga_lexica", rol="editor_de_estilo")
            )
        almacen.anadir_eventos_de_estado(
            [Artefacto("EventoEstado", {"tipo_de_evento": "viaja_a"}, id_obra=id_obra,
                       capitulo=numero)]
        )
        almacen.materializar_estado(id_obra, numero, {"capitulo": numero})
    yield almacen, id_obra
    almacen.cerrar()


def test_ninguna_consulta_del_almacen_recorre_una_tabla_que_crece(
    poblado: tuple[Almacen, str],
) -> None:
    almacen, id_obra = poblado
    consultas: list[str] = []

    def escuchar(sentencia: str) -> None:
        if sentencia.lstrip().upper().startswith("SELECT"):
            consultas.append(sentencia)

    almacen._lector.set_trace_callback(escuchar)
    _ejercer_la_interfaz_de_lectura(almacen, id_obra)
    almacen._lector.set_trace_callback(None)

    assert len(consultas) >= 12, "no se ha ejercido bastante interfaz de lectura"

    recorridos: list[str] = []
    for consulta in consultas:
        for fila in almacen._lector.execute("EXPLAIN QUERY PLAN " + consulta):
            detalle = fila["detail"]
            if not detalle.startswith("SCAN "):
                continue
            tabla = detalle.split()[1]
            if tabla not in RECORRIDO_ADMITIDO:
                recorridos.append(f"{detalle}  <-  {consulta}")

    assert recorridos == [], "\n".join(recorridos)


def _ejercer_la_interfaz_de_lectura(almacen: Almacen, id_obra: str) -> None:
    almacen.leer_obra(id_obra)
    almacen.listar_obras()
    almacen.leer_capitulo(id_obra, 1)
    escena = almacen.listar("Escena", id_obra, capitulo=1, orden="orden")[0]
    almacen.borrador_vigente(id_obra, escena.id)
    almacen.manuscrito_aceptado(id_obra)
    almacen.listar_criticas_abiertas(id_obra)
    almacen.listar_criticas_abiertas(id_obra, escena=escena.id, severidad="menor")
    almacen.listar("Critica", id_obra, dimension="fatiga_lexica")
    almacen.eventos_del_capitulo(id_obra, 1)
    almacen.estado_en(id_obra, 1)
    almacen.listar_trazas(id_obra)
    almacen.trazas_abiertas(id_obra)
    almacen.contexto_de_entrada_abierto(id_obra)
    almacen.esta_detenida(id_obra)
    # Las mismas lecturas vistas desde una version (SPEC1 4.12), y las versiones.
    almacen.leer_capitulo(id_obra, 1, version=1)
    almacen.borrador_vigente(id_obra, escena.id, version=1)
    almacen.manuscrito_aceptado(id_obra, version=1)
    almacen.listar_criticas_abiertas(id_obra, version=1)
    almacen.estado_en(id_obra, 1, version=1)
    almacen.capitulos_de_uso(id_obra, version=1)
    almacen.listar_versiones(id_obra)
    almacen.leer_version(id_obra, 1)
    almacen.version_en_curso(id_obra)
    almacen.version_publicada(id_obra)
