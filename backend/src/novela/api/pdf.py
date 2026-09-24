"""El manuscrito de una version en PDF, fabricado al vuelo (SPEC1 RF-178, D-75).

Se compone en memoria y se devuelve como bytes: no se escribe en disco ni se
guarda en ningun sitio (RD-08). No interpreta el texto: lo pinta en orden, con
una portada, un indice con la pagina de cada capitulo y los capitulos.

Las fuentes de serie de `fpdf2` cubren Latin-1, que es todo el castellano
escrito —acentos, ñ, ¿, ¡, comillas angulares—. Lo que queda fuera, la
tipografia fina, se cambia por su equivalente mas cercano antes de escribir.
"""

import math
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass

from fpdf import FPDF
from fpdf.enums import XPos, YPos
from fpdf.outline import OutlineSection

# Lo que Latin-1 no tiene y el castellano usa: su equivalente mas cercano.
EQUIVALENTES: dict[str, str] = {
    "—": "-",  # raya
    "–": "-",  # semirraya
    "‒": "-",
    "―": "-",
    "‘": "'",
    "’": "'",
    "‚": ",",
    "“": '"',
    "”": '"',
    "„": '"',
    "…": "...",
    "•": "·",
    "′": "'",
    "″": '"',
    " ": " ",
    " ": " ",
    " ": " ",
    " ": " ",
    "⁂": "* * *",
    "⸺": "--",
    "⸻": "---",
}

# Capitulos que caben en una pagina A5 del indice, con margen.
CAPITULOS_POR_PAGINA_DE_INDICE = 18


def a_latin1(texto: str) -> str:
    """El texto con lo que las fuentes de serie no tienen ya sustituido.

    Primero la tabla de equivalentes; despues, lo que se pueda descomponer en
    letra y tilde se compone en Latin-1, y lo que ni asi cabe sale como `?`.
    """
    cambiado = "".join(EQUIVALENTES.get(letra, letra) for letra in texto)
    compuesto = unicodedata.normalize("NFC", cambiado)
    return compuesto.encode("latin-1", errors="replace").decode("latin-1")


@dataclass(frozen=True)
class CapituloDelPdf:
    numero: int
    escenas: Sequence[str]


class _Libro(FPDF):
    def footer(self) -> None:
        if self.page_no() <= 1:
            return
        self.set_y(-15)
        self.set_font("Times", "I", 9)
        self.cell(0, 10, str(self.page_no()), align="C")


def _parrafos(texto: str) -> list[str]:
    """Un parrafo por bloque separado por una linea en blanco, como en la web."""
    return [p.strip() for p in texto.replace("\r\n", "\n").split("\n\n") if p.strip()]


def manuscrito_en_pdf(
    titulo: str,
    destinatario: str | None,
    dedicatoria: str | None,
    capitulos: Sequence[CapituloDelPdf],
    *,
    version: int,
) -> bytes:
    """Portada, indice y capitulos. Devuelve el PDF entero en memoria."""
    libro = _Libro(format=(148, 210))  # A5, en milimetros
    libro.set_title(a_latin1(titulo))
    libro.set_creator("my-story-maker")
    libro.set_margins(18, 18, 18)
    libro.set_auto_page_break(auto=True, margin=20)

    # Portada.
    libro.add_page()
    libro.set_y(60)
    libro.set_font("Times", "B", 24)
    libro.multi_cell(0, 11, a_latin1(titulo), align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    if destinatario:
        libro.ln(10)
        libro.set_font("Times", "", 14)
        libro.multi_cell(
            0, 8, a_latin1(f"Para {destinatario}"), align="C",
            new_x=XPos.LMARGIN, new_y=YPos.NEXT,
        )
    if dedicatoria:
        libro.ln(8)
        libro.set_font("Times", "I", 12)
        libro.multi_cell(
            0, 7, a_latin1(dedicatoria), align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT
        )
    libro.set_y(-40)
    libro.set_font("Times", "", 9)
    libro.cell(0, 6, a_latin1(f"Versión {version}"), align="C")

    # Indice, con la pagina de cada capitulo, que se sabe al terminar.
    def pintar_indice(pdf: FPDF, secciones: list[OutlineSection]) -> None:
        pdf.set_font("Times", "B", 16)
        pdf.cell(0, 12, a_latin1("Índice"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.ln(4)
        pdf.set_font("Times", "", 12)
        for seccion in secciones:
            pdf.cell(pdf.epw - 15, 8, seccion.name)
            pdf.cell(15, 8, str(seccion.page_number), align="R",
                     new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    if capitulos:
        # El hueco del indice empieza en su propia pagina y deja la siguiente
        # abierta: ahi empieza el primer capitulo.
        libro.add_page()
        paginas = max(1, math.ceil(len(capitulos) / CAPITULOS_POR_PAGINA_DE_INDICE))
        libro.insert_toc_placeholder(
            pintar_indice, pages=paginas, allow_extra_pages=True, reset_page_indices=False
        )

    for orden_del_capitulo, capitulo in enumerate(capitulos):
        if orden_del_capitulo:
            libro.add_page()
        nombre = f"Capítulo {capitulo.numero}"
        libro.start_section(a_latin1(nombre))
        libro.set_font("Times", "B", 16)
        libro.cell(0, 12, a_latin1(nombre), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        libro.ln(4)
        libro.set_font("Times", "", 11)
        for orden, escena in enumerate(capitulo.escenas):
            if orden:
                libro.ln(2)
                libro.cell(0, 6, "* * *", align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                libro.ln(2)
            for parrafo in _parrafos(escena):
                libro.multi_cell(0, 5.5, a_latin1(parrafo), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                libro.ln(2)

    return bytes(libro.output())
