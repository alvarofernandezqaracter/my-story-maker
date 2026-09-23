"""`nucleo/`: el guion, el presupuesto, el enrutado y los permisos.

Aqui no se decide nada del dominio. Se ensamblan proyecciones, se cuenta
contexto, se camina el guion y se enrutan criticas por severidad. No se pliega
el log, no se resume y no se juzga texto: eso es trabajo del Contable de
estado, del Archivero y de los verificadores.

Si esta carpeta engorda, esta reapareciendo el harness a medida que el proyecto
prohibe. Su tamano se vigila en cada etapa.
"""

from novela.nucleo.caminante import Caminante, Ejecutor, Informe, ProduccionDetenida, Resultado
from novela.nucleo.guion import CRIBAS, FUERA_DEL_GUION, PASOS, Encargo, Paso, expandir, paso

__all__ = [
    "CRIBAS",
    "FUERA_DEL_GUION",
    "PASOS",
    "Caminante",
    "Ejecutor",
    "Encargo",
    "Informe",
    "Paso",
    "ProduccionDetenida",
    "Resultado",
    "expandir",
    "paso",
]
