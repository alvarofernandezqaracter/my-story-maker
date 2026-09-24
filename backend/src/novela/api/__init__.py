"""`api/`: el borde HTTP, y el unico sitio del backend con tipos declarados.

Aqui es donde el backend habla con algo que no es un agente, asi que aqui es
donde se imponen tipos: el contrato HTTP se valida en el borde con modelos
declarados. Hacia dentro, el artefacto es un documento declarativo y el backend
no lo tipa.

Cada operacion es un procedimiento de principio a fin. No hay capa de servicios
intermedia que reutilizar.

**Tres operaciones de escritura y ni una mas**: dar de alta una obra, detener y
reanudar. Detener y reanudar son control, no mantenimiento. No hay limpieza ni
archivado que el editor deba ejecutar: un paso manual periodico seria un
defecto de diseno, no una instruccion de uso.
"""

from novela.api.aplicacion import crear_aplicacion

__all__ = ["crear_aplicacion"]
