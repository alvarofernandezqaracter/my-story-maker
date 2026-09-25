# Observabilidad

**La idea.** Sin ver qué recibió cada agente, qué devolvió y cuánto costó, no se
puede saber por qué salió mal un capítulo ni si un cambio de prompt mejoró algo.

**Cómo se aplica aquí.** Toda tarea deja una `Traza` en SQLite: qué rol, qué
capítulo, qué intento, qué había en la ventana, tokens de entrada estimados y
medidos, salida, coste, latencia y lo que dijo cada hook. Si hay claves,
Langfuse recibe lo mismo agrupado por novela y versión, con la versión del
prompt que produjo cada respuesta.

**Ejemplo.** Los 44 intentos fallidos de una obra de prueba se contaron en sus
trazas, y así se vio que casi ninguno era de contenido: eran JSON con texto
alrededor y tipos escritos con tilde.

**El límite.** Langfuse es un espejo de salida: si falla o falta, la novela se
escribe igual, y la producción nunca lee nada de él.

*Más:* [`architecture.md`](../architecture.md) §4, «La producción, vista desde Langfuse».
