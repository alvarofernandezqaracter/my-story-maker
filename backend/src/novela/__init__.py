"""Generador de novelas historicas por agentes.

El paquete se reparte en cuatro cortes verticales (`architecture.md` 7):
`tareas/` una carpeta por tipo de tarea del censo, `nucleo/` el guion y el
presupuesto, `almacen/` la unica puerta de la persistencia y `api/` el borde
HTTP. Junto a ellos viven dos ficheros declarativos: `ajustes.py`, que es lo
que hoy es configuracion, y `vocabularios.py`, que son los valores cerrados.
"""

__version__ = "0.2.0"
