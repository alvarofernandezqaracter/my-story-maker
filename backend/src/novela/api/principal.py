"""El punto de entrada del servidor.

    fastapi dev    para desarrollo
    fastapi run    para produccion
"""

from novela.api.aplicacion import crear_aplicacion

app = crear_aplicacion()
