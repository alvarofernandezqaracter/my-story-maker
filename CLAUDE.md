# CLAUDE.md — my-story-maker

Instrucciones para Claude Code en este repositorio. Las reglas del proyecto
—qué es el sistema, sus invariantes, el reparto de carpetas y el ciclo de
edición— viven en `AGENTS.md`, que se importa entero aquí debajo y manda sobre
este fichero. Lo que sigue es solo lo que **Claude Code** necesita saber además:
con qué herramientas de `.claude/` se recorre ese ciclo y qué trampas tiene
trabajar aquí.

@AGENTS.md

## Este fichero es del desarrollo, no de la novela

Los once roles del censo también son Claude Code, pero **no leen este fichero**:
el ejecutor lanza cada subagente de tarea en un directorio vacío fuera del
repositorio, sin `CLAUDE.md`, sin `.claude/` y sin servidores MCP (SPEC1 RF-100
y RF-102). Así que:

- Nada de lo que escribas aquí cambia cómo redacta el Redactor o cómo critica el
  Verificador. Lo que un rol sabe está en `backend/src/novela/tareas/<tipo>/`:
  su `prompt.md`, su `contrato.toml` y su `esquema.json`.
- Si alguna vez un subagente de tarea vuelve a medir unos 10 000 tokens de
  entrada en vez de unos 1 500–3 200, lo más probable es que haya vuelto a
  arrancar desde el repositorio y esté leyendo esto. Es un defecto, no una
  medida.

## El ciclo, con las herramientas de `.claude/`

| Fase de `AGENTS.md` | Qué usar |
| --- | --- |
| Lanzar una tarea entera | `/ciclo <Tn>`: lee la tarea en `TAREAS-PENDIENTES.md` y recorre spec, código y docs sin parar |
| 1 · Interrogatorio | La skill `grill-me`, una sola vez y con dos a cuatro preguntas con opciones |
| 2 · Código | La skill de la pila que se toca, siempre antes de escribir: `fastapi`, `frontend-react`, `backend-sqlite`, `sqlite-vec` |
| Cierre de la fase 2 | `/verificar`: ruff, mypy, contratos de importación y pruebas, con la evidencia |
| Cierre de cada fase | El subagente `verificador`: coteja lo entregado contra `docs/validators.md`. Quien escribió no se valida a sí mismo |
| Algo sin método de verificación | La skill `disenar-verificacion`, y se registra en `validators.md` |

### La skill reutilizable

`grill-me` (`.claude/skills/grill-me/`) es la skill del repositorio que no
depende de él: no nombra ningún fichero ni ninguna entidad del proyecto y
sirve tal cual en cualquier otro. Está commiteada porque `AGENTS.md` la hace
obligatoria en la fase 1, y una fase obligatoria no puede depender de lo que
cada uno tenga instalado en su máquina. Las otras cinco skills de
`.claude/skills/` son específicas de esta pila o de este dominio.

### Comandos y subagentes propios

| Pieza | Fichero | Qué hace | Qué no hace |
| --- | --- | --- | --- |
| `/ciclo` | `.claude/commands/ciclo.md` | Lanza una tarea de `TAREAS-PENDIENTES.md` con el ciclo entero | Saltarse una fase o una tarea de la que depende |
| `/verificar` | `.claude/commands/verificar.md` | Corre las comprobaciones que no gastan y las resume | Correr `pytest -m gasta`, que lanza agentes de verdad, ni arreglar lo que falle |
| `verificador` | `.claude/agents/verificador.md` | Comprueba cada entregable con el método que le asigna `validators.md` | Editar ficheros: solo lee y cita |

## El navegador: `.claude/mcp.json`

Declara un servidor MCP de Playwright, con versión fijada, que abre Chromium sin
cabeza y con el perfil en memoria. **No se carga solo**: Claude Code solo lee
por su cuenta el `.mcp.json` de la raíz, y ese no existe a propósito, para no
gastar las definiciones de sus herramientas en cada conversación que no mira
ninguna página (SPEC1 D-37). Se pide por su nombre en la sesión que tiene que
mirar la lectura web:

```sh
claude --mcp-config .claude/mcp.json
```

La primera vez en una máquina hace falta el navegador que esa versión espera:

```sh
npx -y -p @playwright/mcp@0.0.82 playwright install chromium
```

Subir la versión del servidor es cambiarla en los dos sitios: `mcp.json` y la
orden de instalación de aquí arriba.

## Cómo se trabaja con el backend

Desde `backend/`, con Python 3.13:

```sh
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"   # en Linux o macOS: .venv/bin/python
```

- `python -m pytest` no gasta: las pruebas que lanzan subagentes reales llevan
  la marca `gasta` y quedan fuera por defecto. Lanzarlas es una decisión, no una
  comprobación de rutina: se avisa antes.
- `backend/openapi.yaml` no se edita a mano. Si la prueba del contrato falla una
  vez y lo deja cambiado, el borde se ha movido: se mira el diff y se commitea
  junto al cambio que lo movió (RNF-09).
- Nada de lo que el sistema produce va a disco: todo vive en SQLite (RD-08). Una
  carpeta de trabajo o un volcado para inspeccionar es un defecto, no una ayuda.

## Trampas conocidas

- **La versión va en trío.** La cabecera de `specs/SPEC1.md`,
  `backend/pyproject.toml` y `backend/src/novela/__init__.py` dicen siempre el
  mismo número. Si uno se mueve y los otros no, el cambio está a medias.
- **Los identificadores no se reutilizan.** Un `RF-`, `RD-` o `D-` retirado de
  la spec deja su número vacío (SPEC1 §1.4).
- **Las decisiones abiertas.** Las de `docs/architecture.md` §8 no se cierran
  dentro de un cambio. Se dice cuáles toca el cambio y se espera.
- **La consola.** En Windows, Git Bash es el intérprete de las órdenes de arriba;
  en PowerShell `&&` no existe en la 5.1.
