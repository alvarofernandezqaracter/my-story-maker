# Punto de guardado

**La idea.** Un proceso largo se va a cortar: alguien lo para, algo falla o la
máquina se cae. Hay que decidir de antemano a qué punto se vuelve y qué se hace
con lo que quedó a medias.

**Cómo se aplica aquí.** El único punto de guardado es **el capítulo cerrado**,
y cerrar es una sola transacción. Al volver, todo lo de los capítulos no
cerrados se descarta y se rehace. Tras una caída, la obra se relanza sola al
arrancar el backend, sin que nadie pulse nada.

**Ejemplo.** Si la máquina se apaga a mitad del capítulo 3, al volver se
descarta lo que hubiera del 3 y se planifica de nuevo; el 1 y el 2 no se tocan.

**El límite.** Se repite el trabajo del capítulo cortado, fuentes incluidas. A
cambio no hay que reconstruir en qué vuelta del bucle estaba cada escena. TLC
encontró que la regla «descartar lo posterior al último cerrado» fallaba con el
cambio del lector; ahora es «descartar todo lo no cerrado».

*Más:* [`architecture.md`](../architecture.md) §4.
