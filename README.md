# my-story-maker

Sistema de agentes creador de novelas históricas.

El diseño completo está en [`docs/spec/SPEC.md`](docs/spec/SPEC.md) y es la
fuente de verdad: si el código y el spec cuentan cosas distintas, manda el spec.
Este README solo dice cómo se arranca.

## Requisitos

Node 22.5 o superior (aquí corre sobre 24). El canon usa `node:sqlite`, que
viene en el propio Node, así que el modo `simulado` no necesita instalar nada.
El modo `real` necesita `@anthropic-ai/sdk` y una credencial de la API en el
entorno.

## Arranque rápido, sin red y sin coste

```bash
node bin/novela.mjs init
node bin/novela.mjs brief brief.ejemplo.json
node bin/novela.mjs preparar     # investigador y arquitecto
node bin/novela.mjs escribir     # loop: escritor, validador, gate, cronista
node bin/novela.mjs cerrar       # editor global y retoques.md
```

Con `ejecucion.modo` en `simulado`, que es el valor por defecto de
`config.json`, las llamadas a agentes las resuelve una capa local que devuelve
respuestas fijas con el formato correcto. Todo el harness corre por el mismo
camino que en ejecución real.

Para la ejecución de verdad, pon `ejecucion.modo` en `real` en `config.json`,
instala el SDK (`npm install`) y deja la credencial en el entorno.

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
| `src/` | El harness: todo lo determinista |
| `agentes/` | Un `.md` por agente de §5, con su encargo y sus modos de fallo |
| `skills/` | Las skills de §10, que el harness carga al construir cada llamada |
| `capitulos/` | Un Markdown por intento. Los fallidos se quedan como rastro |
| `test/` | Tests contra la capa simulada, sin red |
| `docs/spec/` | El spec |

`canon.db`, `capitulos/*.md` y `retoques.md` son salida y no se versionan.

## Tests

```bash
npm test
```

Corren en modo simulado. Dos variables de entorno inyectan fallos para
ejercitar los caminos que de otro modo no se ven: `NOVELA_SIM_FALLOS` hace que
el validador suspenda un intento concreto y `NOVELA_SIM_CORTOS` hace que el
escritor devuelva un capítulo demasiado corto. Ambas toman una lista de
`capitulo:intento` y solo tienen efecto en modo simulado.

```bash
# El capítulo 2 suspende a la primera y el reintento lo arregla
NOVELA_SIM_FALLOS="2:1" node bin/novela.mjs escribir
```
