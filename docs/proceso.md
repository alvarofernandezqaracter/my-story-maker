# Documentación de proceso

Cómo se ha construido el sistema, no cómo es: eso lo cuentan los otros cuatro
documentos de referencia de `docs/`. Aquí no se corrige el resultado, se cuenta
el razonamiento que llevó a él: qué se decidió, con qué opciones delante, y qué
cambió cuando una medida, un contraejemplo o un ataque demostró que estaba mal.

Cada pieza se escribe en un solo sitio; lo que ya existe en otra parte del
repositorio se enlaza desde aquí en vez de copiarse.

| Pieza | Qué es | Dónde está |
| --- | --- | --- |
| Spec inicial | Qué se decidió construir y por qué, antes de escribir código | [`spec-inicial.md`](spec-inicial.md), resumen de la primera spec del backend, que sigue entera en `git show 6c9dc20:specs/SPEC1.md` |
| Trade-offs | Cada decisión de diseño relevante con sus opciones, criterios y elección: un agente o muchos, formato de la story bible, elección del modelo y cómo lee el juez, integración de TLA+ con el flujo real, invariantes de Lean priorizados, y siete más | [`trade-offs.md`](trade-offs.md). El detalle de cada decisión, con su `D-nn`, en las specs; lo que sigue abierto, en [`architecture.md`](architecture.md) §8 |
| Explainers | Uno por concepto del curso aplicado, breve | [`explainers/`](explainers/README.md), dieciséis |
| Diagramas | Arquitectura del harness, máquina de estados de TLA+, esquema de SQLite y tabla de validadores con su punto de ejecución | [`diagramas.md`](diagramas.md). Los del dominio, en [`domain-knowledge.md`](domain-knowledge.md); los de capas, entrevista y ciclo del capítulo, en [`architecture.md`](architecture.md) |
| Registro de iteraciones | Qué cambió tras cada medida, contraejemplo de TLC o fallo de Lean, con causa y efecto | [`registro-de-iteraciones.md`](registro-de-iteraciones.md). Las trazas literales de TLC, en [`backend/formal/tla/contraejemplos/`](../backend/formal/tla/contraejemplos/) |
| Red-team log | Casos adversariales probados, qué validador los paró (o no) y cómo se resolvió | [`red-team-log.md`](red-team-log.md) |

## Lo que todavía falta, y por qué

Estas piezas están completas con lo que se ha medido hasta hoy. Hay dos cosas
que no se pueden escribir sin gastar, porque salen de lanzar agentes de verdad:

- **Los cinco briefs de prueba corridos de principio a fin** (T13b). Hasta
  entonces, el red-team log recoge lo esperado de los briefs adversarios y los
  marca «sin correr», y el registro de iteraciones no tiene la vuelta de ajuste
  con los números de antes y después.
- **Volver a medir los dos últimos arreglos** en una obra entera: la lectura de
  lo que entrega un agente y la regla de un solo lugar. Están marcados «falta
  volver a medir» en el registro.
