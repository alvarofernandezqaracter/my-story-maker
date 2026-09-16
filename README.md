# my-story-maker

Sistema de agentes creador de novelas históricas.

El diseño completo está en [`docs/spec/SPEC.md`](docs/spec/SPEC.md) y es la
fuente de verdad: si el código y el spec cuentan cosas distintas, manda el spec.
Este README solo dice cómo se arranca.

## Requisitos

Python 3.11 o superior (aquí corre sobre 3.13). El canon usa `sqlite3`, que
viene en la propia biblioteca estándar, así que el modo `simulado` no necesita
instalar nada. El modo `real` necesita `anthropic` y una credencial de la API en
el entorno. El modo `claude_code` no necesita ninguna de las dos cosas: le basta
con tener la CLI de Claude Code en el `PATH`.

## Arranque rápido, sin red y sin coste

```bash
python -m novela init
python -m novela brief brief.ejemplo.json
python -m novela preparar     # investigador y arquitecto
python -m novela escribir     # loop: escritor, validador, gate, cronista
python -m novela cerrar       # editor global y retoques.md
```

Con `ejecucion.modo` en `simulado`, que es el valor por defecto de
`config.json`, las llamadas a agentes las resuelve una capa local que devuelve
respuestas fijas con el formato correcto. Todo el harness corre por el mismo
camino que en ejecución real.

## Ejecución con modelos de verdad

Hay dos caminos y se eligen con `ejecucion.modo`, sin tocar nada más:

- `real`: contra la API de Claude. Instala el SDK (`pip install anthropic`) y
  deja la credencial en el entorno, nunca en `config.json`.
- `claude_code`: contra la CLI de Claude Code que ya tengas instalada, en modo
  headless. No hace falta clave de API porque la credencial es la de su sesión.
  `config.claude-code.json` viene ya puesto con ese modo:

```bash
python -m novela preparar --config config.claude-code.json
python -m novela escribir --config config.claude-code.json
python -m novela cerrar   --config config.claude-code.json
```

En los dos casos el modelo de cada rol sale de `modelo_por_rol`, y el resto del
harness es el mismo: mismas instrucciones, mismos validadores y mismo gate.

## Comandos

| Comando | Qué hace |
|---|---|
| `init` | Crea el canon vacío |
| `brief <fichero.json>` | Guarda el brief y deja el proyecto en `borrador` |
| `preparar` | Investigador y arquitecto |
| `escribir [--capitulo N]` | Loop de capítulo. Sin `--capitulo`, va hasta el final o hasta el primer bloqueo |
| `cerrar` | Editor global y `retoques.md` |
| `reanudar` | Sin argumentos: sigue desde el primer capítulo no aprobado |
| `estado` | Estado del proyecto y de cada capítulo, con sus notas |
| `ver <qué> [N]` | `dossier`, `personajes`, `escaleta`, `resumenes`, `timeline`, `hilos`, `contexto N`, `capitulo N` |
| `poner <qué> <fichero>` | `personaje`, `capitulo`, `dato` — escritura a mano en el canon |
| `desbloquear --capitulo N` | Salidas manuales del bloqueo. Con `--aprobar-intento K` o `--reiniciar` |
| `skills` | Lista las skills que el harness carga en cada llamada |

Opciones globales: `--config <ruta>` y `--canon <ruta>`.

## Qué hay en cada sitio

| Carpeta | Qué contiene |
|---|---|
| `novela/` | El harness: todo lo determinista, con la CLI en `__main__.py` |
| `agentes/` | Un `.md` por agente de §5, con su encargo y sus modos de fallo |
| `skills/` | Las skills de §10, que el harness carga al construir cada llamada |
| `capitulos/` | Un Markdown por intento. Los fallidos se quedan como rastro |
| `tests/` | Tests contra la capa simulada, sin red |
| `docs/spec/` | El spec |

`canon.db`, `capitulos/*.md` y `retoques.md` son salida y no se versionan.

## Tests

```bash
python -m unittest discover -s tests -t .
```

Corren en modo simulado. Dos variables de entorno inyectan fallos para
ejercitar los caminos que de otro modo no se ven: `NOVELA_SIM_FALLOS` hace que
el validador suspenda un intento concreto y `NOVELA_SIM_CORTOS` hace que el
escritor devuelva un capítulo demasiado corto. Ambas toman una lista de
`capitulo:intento` y solo tienen efecto en modo simulado.

```bash
# El capítulo 2 suspende a la primera y el reintento lo arregla
NOVELA_SIM_FALLOS="2:1" python -m novela escribir
```
