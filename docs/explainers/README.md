# Explainers

Uno por cada concepto del curso que el proyecto aplica. Son cortos a propósito:
no cuentan la teoría, cuentan **dónde y cómo** se aplica aquí, con un ejemplo
del propio sistema y el límite que tiene. Cada uno enlaza al documento donde
está el detalle.

| # | Concepto | Dónde se ve en el proyecto |
| --- | --- | --- |
| 01 | [El harness](01-harness.md) | Subagentes de Claude Code en lugar de un bucle propio |
| 02 | [Ingeniería de contexto](02-ingenieria-de-contexto.md) | Proyecciones por rol, arranque en frío, techo de 100 000 tokens |
| 03 | [Orquestación multiagente](03-orquestacion-multiagente.md) | Doce roles y un guion de diez pasos |
| 04 | [Quien escribe no juzga](04-quien-escribe-no-juzga.md) | Censo de roles y críticas con evidencia |
| 05 | [Salidas estructuradas](05-salidas-estructuradas.md) | Esquemas por tarea y vocabularios controlados |
| 06 | [Guardarraíles y hooks](06-guardarrailes-y-hooks.md) | Permisos, hooks `Stop` y puerta de publicación |
| 07 | [Memoria y estado derivado](07-memoria-y-estado-derivado.md) | Log de `EventoEstado` y tres memorias |
| 08 | [Recuperación por parecido (RAG)](08-recuperacion-hibrida.md) | FTS5 y `sqlite-vec`, fundidos |
| 09 | [Punto de guardado](09-punto-de-guardado.md) | El capítulo cerrado |
| 10 | [Verificar con un método declarado](10-verificacion-por-metodo.md) | `validators.md` y sus cinco métodos |
| 11 | [Un modelo como juez](11-llm-como-juez.md) | Juez de rúbrica y juez de la novela |
| 12 | [Observabilidad](12-observabilidad.md) | `Traza` en SQLite y Langfuse como espejo |
| 13 | [Comprobar el flujo con TLA+](13-tla-plus.md) | `backend/formal/tla/` |
| 14 | [Demostrar la cronología con Lean](14-lean.md) | `backend/src/novela/lean/` |
| 15 | [Red-teaming e inyección](15-red-teaming.md) | Marcas de datos, casos sembrados y briefs adversarios |
| 16 | [Desarrollo guiado por especificación](16-desarrollo-guiado-por-spec.md) | El ciclo spec, código y docs |
