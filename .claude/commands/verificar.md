---
description: Corre las comprobaciones del backend que validators.md §6 manda pasar en cada commit y las resume con su evidencia
allowed-tools: Bash(cd:*), Bash(python -m ruff:*), Bash(python -m mypy:*), Bash(python -m pytest:*), Bash(lint-imports:*), Bash(git status:*), Bash(git diff:*)
---

Corre, desde `backend/` y con el entorno de `backend/.venv` activo, estas cuatro
comprobaciones. Son las de `docs/validators.md` §6 que no gastan: ninguna invoca
un agente real.

| Comprobación | Orden | Método | Qué sostiene |
| --- | --- | --- | --- |
| Estilo y errores comunes | `python -m ruff check src tests` | `analisis` | Que el código se lee igual en todas partes |
| Tipos en el borde | `python -m mypy` | `analisis` | Que el único sitio con tipos declarados, `api/`, los cumple |
| Contratos de importación | `lint-imports` | `analisis` | Las capas, la independencia de las tareas y que solo `almacen/` abre la base |
| Pruebas | `python -m pytest` | `prueba` | Todo lo demás, incluido el recorrido en seco y el contrato OpenAPI |

Si la prueba del contrato de la frontera falla una vez y deja `backend/openapi.yaml`
cambiado, es RNF-09 funcionando: el borde se movió. Enséñame el diff con
`git diff backend/openapi.yaml` y vuelve a correr las pruebas; no lo des por
arreglado sin mirarlo.

No corras `pytest -m gasta`: esas pruebas lanzan subagentes de verdad y cuestan
dinero. Si $ARGUMENTS pide expresamente `gasta`, avísame antes de lanzarlas.

Devuélveme una tabla con cada comprobación, su resultado y la evidencia —la
última línea de la salida, o el primer fallo citado literal—. Si algo falla, no
lo arregles: di qué falla y dónde. Arreglarlo es otro turno.
