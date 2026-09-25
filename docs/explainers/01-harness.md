# El harness, y por qué aquí no se escribe uno

**La idea.** Un modelo de lenguaje solo contesta. Lo que lo convierte en un
agente es el *harness*: el programa que le da herramientas, le pasa el contexto,
repite llamadas y decide cuándo ha terminado. Casi todo lo que sale bien o mal
en un sistema de agentes sale de ahí, no del modelo.

**Cómo se aplica aquí.** El proyecto no escribe su propio harness. Cada tarea
la hace un subagente de Claude Code, que ya trae el suyo —herramientas,
permisos, bucle—, y el backend se limita a repartir turnos: ensambla la ventana,
lanza el subagente en un directorio vacío y recoge lo que devuelve. El estado
no vive en objetos de Python en memoria sino en artefactos de SQLite que
cualquier agente puede leer.

**Ejemplo.** Que el Redactor no pueda buscar en internet no es una línea de su
prompt: es que su subagente arranca sin esa herramienta. Pedírselo sería una
petición; quitársela es una garantía.

**El límite.** Se depende del CLI: cómo arranca, cómo cuenta tokens y cómo
escribe su salida. Cuando los agentes entregaban el JSON con texto alrededor,
hubo que leerlo con más tolerancia (registro de iteraciones, 2026-09-25).

*Más:* [`trade-offs.md`](../trade-offs.md) §3.
