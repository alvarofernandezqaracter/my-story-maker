# Registro de iteraciones

Qué se cambió en el sistema, por qué, y qué pasó con los números al cambiarlo.
Se escribe **por el camino, no al final**: una entrada por cada cambio que
mueva una medida —un prompt reescrito, un umbral movido, un validador nuevo—.

Las cifras salen de Langfuse, no de una hoja aparte. Si un cambio no movió
ninguna medida, se anota igual: un cambio que no mejora nada es información.

## Formato de una entrada

| Campo | Qué va |
| --- | --- |
| Fecha | Cuándo se aplicó |
| Tarea | La tarea de `TAREAS-PENDIENTES.md` dentro de la que se hizo |
| Qué se cambió | El prompt, el umbral o la regla, con su versión en Langfuse |
| Por qué | Qué problema medido lo motivó |
| Antes | La medida antes del cambio, con dónde mirarla |
| Después | La misma medida después |
| Veredicto | Si se queda, se revierte o se vuelve a intentar |

## Entradas

| Fecha | Tarea | Qué se cambió | Por qué | Antes | Después | Veredicto |
| --- | --- | --- | --- | --- | --- | --- |
| 2026-09-23 | T6 | Cada subagente de tarea corre en un directorio vacío fuera del repositorio (SPEC1 RF-100), y el coste fijo declarado baja de 10 500 a 3 500 tokens (RF-101). Sin Langfuse todavía: las cifras salen del campo `usage` que devuelve el CLI, que es el que va a la `Traza` | Lanzado desde el repositorio, el subagente cargaba el `CLAUDE.md` con `AGENTS.md` dentro: material que ninguna proyección declara y que ocupaba techo | Entrada de una tarea vacía: 10 751 tokens, en el campo `usage` de `claude --print --output-format json` lanzado a mano con la orden del ejecutor, sin `Traza` porque no pasó por el almacén. Verificadores por tanda: 4 | Entrada de una tarea vacía: 1 548 sin herramientas y 3 191 con las del Documentalista; un Redactor por el ejecutor real, 1 695. Verificadores por tanda: 6 | Se queda |
