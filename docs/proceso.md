# Documentación de proceso

Cómo se ha construido el sistema, no cómo es: eso lo cuentan los otros cuatro
documentos de `docs/`. Cada pieza se escribe en un solo sitio; lo que ya existe
en otra parte del repositorio se enlaza desde aquí en vez de copiarse.

| Pieza | Dónde está | Estado |
| --- | --- | --- |
| Spec inicial | La primera versión de la spec del backend está en el historial de git: `git show 6c9dc20:specs/SPEC1.md`. Las specs vivas, que dicen cómo tiene que ser el sistema ahora, son [`specs/SPEC1.md`](../specs/SPEC1.md) (backend) y [`specs/SPEC2.md`](../specs/SPEC2.md) (frontend), con el plan de la interfaz en [`specs/PLAN-FRONTEND.md`](../specs/PLAN-FRONTEND.md) | Existe |
| Trade-offs | Las decisiones `D-` de las specs, cada una con su porqué y la alternativa descartada: [`SPEC1.md`](../specs/SPEC1.md) §8 y las tablas de decisiones de cada apartado de §4, y [`SPEC2.md`](../specs/SPEC2.md) §8. Lo que sigue sin decidir: [`architecture.md`](architecture.md) §8, SPEC1 §12 y SPEC2 §12 | Existe |
| Explainers | [`explainers/`](explainers/README.md) | Hueco: lo rellena T15b |
| Diagramas | Los del dominio, en [`domain-knowledge.md`](domain-knowledge.md). Los de la arquitectura —capas, entrevista, ciclo de vida del capítulo—, en [`architecture.md`](architecture.md). Los de cada requisito, junto a él en las specs. El flujo de producción como máquina de estados, en [`backend/formal/tla/`](../backend/formal/tla/mapeo.md) | Existe |
| Registro de iteraciones | [`registro-de-iteraciones.md`](registro-de-iteraciones.md): qué se cambió, por qué y qué pasó con los números | Se escribe por el camino. T13b le añade la iteración de ajuste con los números de antes y después |
| Red-team log | [`red-team-log.md`](red-team-log.md): los intentos de que el sistema se salte sus reglas y qué pasó con cada uno | Se escribe por el camino. T13b le añade los briefs adversarios cuando se corren |
