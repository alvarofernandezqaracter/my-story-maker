---
description: Lanza una tarea de TAREAS-PENDIENTES.md recorriendo el ciclo de edición entero de AGENTS.md
argument-hint: <Tn> [nota libre]
---

Vas a ejecutar la tarea **$1** de `TAREAS-PENDIENTES.md` recorriendo el ciclo de
edición de `AGENTS.md`: spec, código y docs, en ese orden, sin saltarte ninguna
fase y sin parar entre fases. Nota del humano, si la hay: $ARGUMENTS

Antes de nada:

1. Lee el apartado de **$1** en `TAREAS-PENDIENTES.md`: qué entrega, de qué
   depende y qué hay que decidir antes. Si depende de una tarea que no está
   hecha en esta rama, dilo y para: saltarse una obliga a rehacerla.
2. Mira en la tabla de interrogatorios de ese mismo fichero si a **$1** le toca
   interrogatorio propio o si ya lo cubrió el de su fase en esta conversación.

Después, el ciclo:

1. **Interrogatorio.** Si le toca, invoca la skill `grill-me` y pregunta de una
   sola vez el porqué de la tarea o de la fase entera. Es el único momento en
   que interrumpes al humano; a partir de ahí ejecutas todo seguido.
2. **Spec.** Si la tarea toca `backend/`, enmienda `specs/SPEC1.md` con lo
   decidido y la justificación del interrogatorio. Lo que el cambio retire sale
   del documento, no se narra como pasado. La versión de la cabecera,
   `backend/pyproject.toml` y `novela/__init__.py` suben juntas.
3. **Código.** Abre antes la skill de la parte de la pila que vas a tocar
   (`fastapi`, `frontend-react`, `backend-sqlite`, `sqlite-vec`) e implementa lo
   que dice la spec y nada más. Si aparece una decisión de fondo que la spec no
   cubre, vuelve al paso 2.
4. **Docs.** Destila en `docs/` según la tabla de la fase 3 de `AGENTS.md`, y en
   la sección «Estructura del repositorio» de `AGENTS.md` si cambia el reparto.
5. **Verificación.** Lanza `/verificar` para el código y delega en el subagente
   `verificador` el cotejo de todo lo entregado contra `docs/validators.md`:
   quien escribe no valida su propia salida.
6. **Registros.** Si el cambio movió una medida, una entrada en
   `docs/registro-de-iteraciones.md`; si probaste un ataque, una en
   `docs/red-team-log.md`. Si no aplica, no inventes ninguna.

Deja el trabajo en los commits mínimos que lo expliquen, en la rama actual. Al
terminar, cuenta en lenguaje llano qué cambió y en qué ficheros, con qué método
se verificó cada cosa, y si algo deja abierta o cerrada una decisión de
`docs/architecture.md` §8: eso se dice, no se cierra por tu cuenta.
