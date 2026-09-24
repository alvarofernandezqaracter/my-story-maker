"""El validador formal de la cronologia, con Lean 4 (SPEC1 4.16).

Dos piezas. `volcar` es una funcion pura: traduce la cronologia de una version
—lo que sirve la vista de RF-86, mas quien muere en cada suceso— a un modulo de
Lean con los datos y un teorema por invariante y suceso. `DemostradorLean`
copia el proyecto de `lean/` a un directorio temporal, escribe alli el modulo,
ejecuta `lake build` y lee de su salida que teoremas no se pudieron demostrar.
El directorio se borra al terminar: nada de lo que el sistema produce se queda
en disco (RD-08, D-62).

Aqui no se comprueba ningun invariante: los comprueba Lean. Lo unico que se
decide en Python es como se escribe una fecha en naturales y a que suceso
corresponde cada linea del modulo, para poder decir donde esta el fallo.
"""

import os
import re
import shutil
import subprocess
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from novela.vocabularios import INVARIANTE_DE_LA_CRONOLOGIA

# El proyecto de Lean versionado con el repositorio: los invariantes genericos.
PROYECTO = Path(__file__).parent / "lean"

# Lo que Lean tiene para terminar antes de que la comprobacion se de por fallida.
ESPERA_MAXIMA_EN_SEGUNDOS = 300

# Sin fecha, el intervalo que no choca con nada (Invariantes.lean).
SIN_DESDE = 0
SIN_HASTA = 99_999_999

_FECHA = re.compile(r"^(\d{4})(?:-(\d{2})(?:-(\d{2}))?)?$")
_ERROR_EN_EL_MODULO = re.compile(r"Obra\.lean:(\d+):\d+:\s*(.*)")

# Que teorema del modulo demuestra cada invariante, suceso a suceso.
_TEOREMA = {
    "orden_temporal": ("orden", "∀ b ∈ cronologia, Precede {s} b"),
    "edad_coherente": ("edad", "EdadCoherente {s}"),
    "un_solo_lugar": ("lugar", "∀ b ∈ cronologia, UnSoloLugar {s} b"),
    "no_reaparece": ("reaparece", "∀ b ∈ cronologia, NoReaparece {s} b"),
}
assert tuple(_TEOREMA) == INVARIANTE_DE_LA_CRONOLOGIA, (
    "El volcado y el vocabulario de invariantes de la cronologia no dicen lo mismo"
)

# Que lee de cada invariante quien no sabe Lean, en el detalle del fallo.
_EN_PALABRAS = {
    "orden_temporal": "ocurre despues de un suceso de un capitulo posterior",
    "edad_coherente": (
        "tiene presente a alguien que aun no habia nacido o que pasaria de 120 años"
    ),
    "un_solo_lugar": "tiene presente a alguien que ese mismo dia esta en otro lugar",
    "no_reaparece": "deja morir a alguien que vuelve a estar presente despues",
}


def intervalo(fecha: Any) -> tuple[int, int] | None:
    """Una fecha ISO parcial como intervalo de dias `AAAAMMDD` (D-28).

    `1587` da `(15870101, 15871231)`. Sin fecha, el intervalo neutro. Una fecha
    que no es ISO parcial devuelve `None`: no se puede volcar.
    """
    if fecha is None or fecha == "":
        return SIN_DESDE, SIN_HASTA
    coincide = _FECHA.match(str(fecha))
    if coincide is None:
        return None
    ano, mes, dia = coincide.groups()
    if mes is not None and not 1 <= int(mes) <= 12:
        return None
    if dia is not None and not 1 <= int(dia) <= 31:
        return None
    base = int(ano) * 10_000
    if mes is None:
        return base + 101, base + 1231
    base += int(mes) * 100
    if dia is None:
        return base + 1, base + 31
    return base + int(dia), base + int(dia)


@dataclass
class Teorema:
    """Lo que dice una linea del modulo: que invariante y de que suceso."""

    nombre: str
    invariante: str
    suceso: dict[str, Any]


@dataclass
class Volcado:
    """El modulo de Lean de una cronologia y como leer sus errores."""

    texto: str
    teoremas: dict[int, Teorema] = field(default_factory=dict)
    # Lo que no se pudo traducir: (suceso, campo, lo escrito).
    no_volcable: list[tuple[dict[str, Any], str, str]] = field(default_factory=list)


def _tabla(valores: Sequence[Any]) -> dict[Any, int]:
    """Cada `id` a su posicion desde 1, en orden de aparicion. El 0 es «no consta»."""
    posiciones: dict[Any, int] = {}
    for valor in valores:
        if valor is not None and valor not in posiciones:
            posiciones[valor] = len(posiciones) + 1
    return posiciones


def volcar(sucesos: Sequence[dict[str, Any]]) -> Volcado:
    """Traduce la cronologia a un modulo de Lean (RF-150).

    Cada suceso trae lo de la vista de RF-86 —`id`, `capitulo`, `momento`,
    `lugar` y `presentes`, cada uno con `id` y `nacimiento`— y `muere`, el `id`
    del personaje que muere en el, si muere alguno. Copia lo escrito: no
    calcula edades ni distancias, eso lo demuestra Lean.
    """
    volcado = Volcado(texto="")
    personas = _tabla(
        [p.get("id") for s in sucesos for p in s.get("presentes") or []]
        + [s.get("muere") for s in sucesos]
    )
    lugares = _tabla([s.get("lugar") for s in sucesos])
    lineas = [
        "-- Generado por novela.demostrador para una sola comprobacion (SPEC1 4.16).",
        "-- Vive en un directorio temporal y se borra al terminar: no se edita.",
        "import Cronologia.Invariantes",
        "open Cronologia",
        "set_option maxRecDepth 100000",
        "",
    ]
    lineas += [f"-- persona {n}: {identificador}" for identificador, n in personas.items()]
    lineas += [f"-- lugar {n}: {identificador}" for identificador, n in lugares.items()]
    nombres: list[str] = []
    for posicion, suceso in enumerate(sucesos, start=1):
        momento = intervalo(suceso.get("momento"))
        if momento is None:
            volcado.no_volcable.append((suceso, "momento", str(suceso.get("momento"))))
            momento = SIN_DESDE, SIN_HASTA
        presentes = []
        for presente in suceso.get("presentes") or []:
            nacimiento = intervalo(presente.get("nacimiento"))
            if nacimiento is None:
                campo = f"nacimiento de {presente.get('id')}"
                volcado.no_volcable.append((suceso, campo, str(presente.get("nacimiento"))))
                nacimiento = SIN_DESDE, SIN_HASTA
            presentes.append(
                f"⟨{personas.get(presente.get('id'), 0)}, {nacimiento[0]}, {nacimiento[1]}⟩"
            )
        nombre = f"s{posicion}"
        nombres.append(nombre)
        lineas.append(f"-- {nombre}: {suceso.get('id')}")
        lineas.append(
            f"def {nombre} : Suceso := ⟨{int(suceso.get('capitulo') or 0)}, {momento[0]}, "
            f"{momento[1]}, {lugares.get(suceso.get('lugar'), 0)}, [{', '.join(presentes)}], "
            f"{personas.get(suceso.get('muere'), 0)}⟩"
        )
    lineas.append(f"def cronologia : List Suceso := [{', '.join(nombres)}]")
    lineas.append("")
    for invariante, (prefijo, enunciado) in _TEOREMA.items():
        for nombre, suceso in zip(nombres, sucesos, strict=True):
            teorema = f"{prefijo}_{nombre}"
            lineas.append(
                f"theorem {teorema} : {enunciado.format(s=nombre)} := by decide +kernel"
            )
            volcado.teoremas[len(lineas)] = Teorema(teorema, invariante, dict(suceso))
    lineas.append("")
    lineas.append("-- Los cuatro invariantes sobre la cronologia entera, de lo anterior.")
    lineas.append("theorem cronologia_coherente : Coherente cronologia :=")
    partes = []
    for prefijo, _ in _TEOREMA.values():
        cadena = "todos_nil"
        for nombre in reversed(nombres):
            cadena = f"todos_cons {prefijo}_{nombre} ({cadena})"
        partes.append(f"  ({cadena})")
    lineas.append("  coherente_de cronologia\n" + "\n".join(partes))
    volcado.texto = "\n".join(lineas) + "\n"
    return volcado


def _detalle(teorema: Teorema, mensaje: str) -> str:
    suceso = teorema.suceso
    presentes = ", ".join(
        f"{p.get('id')} (nacido {p.get('nacimiento') or 'sin fecha'})"
        for p in suceso.get("presentes") or []
    )
    return (
        f"{teorema.invariante}: el suceso {suceso.get('id')} "
        f"({suceso.get('momento') or 'sin fecha'}, en {suceso.get('lugar') or 'lugar sin dato'}"
        f"{', con ' + presentes if presentes else ''}) {_EN_PALABRAS[teorema.invariante]}. "
        f"Lean no demuestra `{teorema.nombre}`: {mensaje}"
    )


def fallo_formal(
    invariante: str, suceso: dict[str, Any] | None, detalle: str, evidencia: str
) -> dict[str, Any]:
    """Un fallo de la cronologia, con lo que la puerta y la `Critica` necesitan."""
    return {
        "invariante": invariante,
        "suceso": (suceso or {}).get("id"),
        "capitulo": (suceso or {}).get("capitulo"),
        "detalle": detalle,
        "evidencia": evidencia,
    }


def leer_salida(volcado: Volcado, salida: str) -> list[dict[str, Any]]:
    """Que teoremas del modulo no se demostraron, segun la salida de `lake build`.

    Un error que no cae en la linea de un teorema de invariante —el modulo no
    compila, o Lean se rompe— no se puede atribuir a un suceso y vuelve como un
    fallo sin suceso: con Lean instalado, lo que no se demuestra no pasa (D-61).
    """
    fallos: list[dict[str, Any]] = []
    sin_atribuir: list[str] = []
    vistos: set[int] = set()
    for linea in salida.splitlines():
        if "error" not in linea:
            continue
        coincide = _ERROR_EN_EL_MODULO.search(linea)
        numero = int(coincide.group(1)) if coincide else None
        teorema = volcado.teoremas.get(numero) if numero is not None else None
        if teorema is None:
            sin_atribuir.append(linea.strip())
            continue
        if numero in vistos:
            continue
        vistos.add(numero)
        mensaje = coincide.group(2).strip() if coincide else ""
        fallos.append(
            fallo_formal(
                teorema.invariante,
                teorema.suceso,
                _detalle(teorema, mensaje),
                f"Obra.lean:{numero}: theorem {teorema.nombre} — {linea.strip()}",
            )
        )
    if sin_atribuir and not fallos:
        fallos.append(
            fallo_formal(
                "sin_atribuir",
                None,
                "Lean no pudo comprobar la cronologia: " + " | ".join(sin_atribuir[:3]),
                "\n".join(sin_atribuir[:10]),
            )
        )
    return fallos


def _no_volcable(volcado: Volcado) -> list[dict[str, Any]]:
    return [
        fallo_formal(
            "formato",
            suceso,
            f"formato: el {campo} del suceso {suceso.get('id')}, «{escrito}», no es una "
            "fecha ISO parcial (AAAA, AAAA-MM o AAAA-MM-DD) y no se puede volcar",
            f"{suceso.get('id')}.{campo} = «{escrito}»",
        )
        for suceso, campo, escrito in volcado.no_volcable
    ]


def buscar_lake() -> str | None:
    """Donde esta `lake`: en el PATH o donde lo deja elan. `None` si no esta."""
    encontrado = shutil.which("lake")
    if encontrado:
        return encontrado
    for nombre in ("lake.exe", "lake"):
        candidato = Path.home() / ".elan" / "bin" / nombre
        if candidato.is_file():
            return str(candidato)
    return None


@dataclass
class DemostradorLean:
    """Ejecuta `lake build` sobre el volcado de una cronologia (RF-151, RF-152).

    `lake` es la orden que se ejecuta; sin ella, se busca. Si no esta en la
    maquina, la comprobacion no se hace y se dice: que Lean no este instalado
    no tumba una version (D-61).
    """

    lake: str | None = None
    espera: int = ESPERA_MAXIMA_EN_SEGUNDOS
    salida: str = field(default="", init=False)

    def comprobar(self, sucesos: Sequence[dict[str, Any]]) -> dict[str, Any]:
        """El resultado: `comprobacion` y la lista de `fallos` de la cronologia."""
        volcado = volcar(sucesos)
        de_formato = _no_volcable(volcado)
        lake = self.lake or buscar_lake()
        if lake is None:
            return {"comprobacion": "sin_comprobacion", "fallos": de_formato}
        with tempfile.TemporaryDirectory(prefix="novela-lean-") as directorio:
            proyecto = Path(directorio) / "cronologia"
            shutil.copytree(PROYECTO, proyecto, ignore=shutil.ignore_patterns(".lake"))
            (proyecto / "Cronologia" / "Obra.lean").write_text(volcado.texto, encoding="utf-8")
            entorno = dict(os.environ)
            entorno["PATH"] = str(Path(lake).parent) + os.pathsep + entorno.get("PATH", "")
            try:
                terminado = subprocess.run(
                    [lake, "build"],
                    cwd=proyecto,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=self.espera,
                    env=entorno,
                    check=False,
                )
            except FileNotFoundError:
                return {"comprobacion": "sin_comprobacion", "fallos": de_formato}
            except subprocess.TimeoutExpired:
                fallo = fallo_formal(
                    "sin_atribuir",
                    None,
                    f"Lean no termino la comprobacion en {self.espera} s",
                    f"lake build: sin respuesta en {self.espera} s",
                )
                return {"comprobacion": "fallida", "fallos": [*de_formato, fallo]}
        self.salida = (terminado.stdout or "") + (terminado.stderr or "")
        if terminado.returncode == 0:
            fallos = de_formato
        else:
            fallos = [*de_formato, *leer_salida(volcado, self.salida)]
            if not fallos:
                fallos = [
                    fallo_formal(
                        "sin_atribuir",
                        None,
                        f"lake build termino con codigo {terminado.returncode}",
                        self.salida[-2000:],
                    )
                ]
        return {"comprobacion": "fallida" if fallos else "demostrada", "fallos": fallos}
