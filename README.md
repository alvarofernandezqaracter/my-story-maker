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
con tener la CLI de Claude Code en el `PATH`. Las trazas necesitan `langfuse` y
tampoco son obligatorias.

## Arranque rápido, sin red y sin coste

```bash
python -m novela init
python -m novela brief brief.ejemplo.json
python -m novela preparar     # investigador y arquitecto
python -m novela escribir     # loop: escritor, validador, gate, cronista
python -m novela cerrar       # editor global y retoques.md
```

O, si prefieres no tocar la consola, todo eso mismo desde el navegador:

```bash
python -m novela ui           # http://127.0.0.1:8787
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

## Ver qué hizo cada agente

El harness manda a [Langfuse](https://langfuse.com) qué se le pidió a cada
agente, qué contestó, con qué modelo y cuánto costó. Es la pregunta que ni el
canon ni la consola contestan: **por qué el modelo contestó lo que contestó**.

```bash
pip install "my-story-maker[trazas]"
cp .env.ejemplo .env          # y pon ahí tus claves de Langfuse
```

Una traza por unidad de trabajo —la preparación, **cada capítulo** y el cierre—,
agrupadas en una sesión por novela. Dentro de la de un capítulo se ve el paquete
de contexto que recibió el escritor, cada invocación del modelo por separado y
los dos puntos donde el harness decide solo: VD-08 y el gate. Las tres notas del
validador y la media viajan como puntuaciones, así que la calidad del libro se
mira en una gráfica en lugar de releyendo capítulos.

Se apagan con `trazas.activas` a `false`. Y no hacen falta para nada: sin el
paquete, sin credencial o con Langfuse caído, la capa se calla y la novela se
escribe igual.

### Y el camino delegado también traza

Ahí no hay llamada que interceptar —orquesta Claude Code— pero sí hay un punto
único donde está todo: el canon. `python -m novela trazar`, o el botón del panel
de trazas de la interfaz, levanta el mismo árbol desde `novela-cc/` y lo manda.
La sesión se deriva del brief con la misma cuenta que el harness, así que **las
dos orquestaciones del mismo brief caen en la misma sesión** y se comparan una
al lado de la otra.

Es observabilidad reconstruida y va marcada como tal, con las etiquetas
`delegado` y `reconstruido`: salen el árbol, las notas, los veredictos y una
puntuación extra que dice si la suma del gate cuadra con la fórmula; no salen la
latencia, los tokens, el coste ni el prompt exacto, porque nadie los guardó.

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
| `ui [--puerto N] [--camino X]` | Abre la interfaz web: brief, flujo, seguimiento y lectura |
| `trazar [--modelo M]` | Manda a Langfuse el canon delegado de `novela-cc/`, reconstruido |

Opciones globales: `--config <ruta>` y `--canon <ruta>`.

## La interfaz web

`python -m novela ui` levanta un servidor local —`http.server`, nada que
instalar— y abre el navegador. Son tres salas:

- **Brief.** Los cinco campos. Una escena en three.js dibuja un cuadernillo por
  capítulo: el grosor son las palabras, el color el estado en el canon y la luz
  la pone el tono, con el candil parpadeando encima de la mesa.
- **Escritorio.** El pipeline de estados, una tarjeta por subagente, la tabla de
  intentos con el escalón de VD-08 y la operación entera del gate, la auditoría
  de esa operación, la cronología de la novela por día de ficción, el reparto,
  el dossier de época con su verificación, los últimos ficheros escritos y el
  panel de trazas.
- **Lectura.** Los capítulos aprobados sobre vitela, con capitular y florones,
  índice lateral, las notas del validador, el resumen del cronista, los hilos
  que abrió o cerró y la deuda narrativa que queda viva. `←` y `→` cambian de
  capítulo y `f` entra en modo inmersión. Desde la ficha se abre el paquete de
  contexto con el que se escribió.

### Mira los dos caminos

Un conmutador en la barra cambia entre el canon delegado (`novela-cc/`) y el del
harness (`canon.db`) sin reiniciar nada. Por el delegado la página **solo
mira**: quien orquesta es una sesión de Claude Code y en ese canon escribe ella
sola, así que en vez de botones la página da el comando exacto que toca pegar.
Lo que sí hace, y solo puede hacer ahí, es rehacer la cuenta del gate con la
fórmula del spec y avisar si no coincide con la que escribió el orquestador.

Por el camino del harness los botones siguen donde estaban, y un capítulo
bloqueado se desbloquea desde su propia tarjeta.

Lo que el canon no guarda —la cuota diaria, las escenas, el focalizador, el
gancho final y, en el delegado, el coste y las citas de las incidencias—
aparece como «sin datos todavía» y está listado con su motivo en un panel. Es
aposta: preferimos el hueco a un número inventado.

El puerto y el camino de arranque salen de `interfaz.puerto` e
`interfaz.camino`. **Nunca corren dos flujos a la vez**: el servidor tiene un
solo hilo de trabajo y rechaza el segundo, que es lo que mantiene en pie el
invariante del spec. Con una novela en marcha tampoco deja rehacer el brief;
para eso está `python -m novela brief`, que lo pisa a sabiendas.

La escena baja three.js de un CDN, y es lo único del repo que necesita red. Si
no llega, la interfaz funciona igual.

## Qué hay en cada sitio

| Carpeta | Qué contiene |
|---|---|
| `novela/` | El harness: todo lo determinista, con la CLI en `__main__.py` |
| `agentes/` | Un `.md` por agente de §5, con su encargo y sus modos de fallo |
| `skills/` | Las skills de §10, que el harness carga al construir cada llamada |
| `capitulos/` | Un Markdown por intento. Los fallidos se quedan como rastro |
| `web/` | La interfaz: las tres salas, la escena three.js y la ambientación |
| `novela-cc/` | El canon en ficheros del camino delegado |
| `.claude/` | Los ocho subagentes, la skill que los orquesta y la de Langfuse (ver `PROCEDENCIA.md`) |
| `tests/` | Tests contra la capa simulada, sin red |
| `docs/spec/` | El spec |

`canon.db`, `capitulos/*.md`, `retoques.md` y `novela-cc/` son salida y no se
versionan.

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
