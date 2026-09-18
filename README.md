# my-story-maker

Sistema de agentes creador de novelas históricas.

El diseño completo está en [`docs/spec/SPEC.md`](docs/spec/SPEC.md) y es la
fuente de verdad: si el código y el spec cuentan cosas distintas, manda el spec.
Este README solo dice cómo se arranca.

## Cómo se escribe una novela

No con un comando. Se abre **Claude Code** en este repositorio y se lanza:

```
/orquestar-novela
```

La sesión te pide los cinco campos del brief —época y lugar, premisa, tono,
capítulos y palabras por capítulo— y a partir de ahí orquesta: un investigador
levanta el dossier de época, un arquitecto monta la escaleta y las fichas, y
luego, capítulo a capítulo, un escritor redacta, tres validadores puntúan a la
vez, el gate decide y un cronista vuelca lo aprobado en el canon. Al terminar,
un editor global propone los retoques finales.

También entiende «prepara la novela», «sigue escribiendo», «reanuda»,
«desbloquea el capítulo 4» o «ciérrala».

**Quien orquesta es la sesión, no un programa.** La máquina de estados, el
cálculo del gate y las once comprobaciones están escritos como instrucciones en
[`.claude/skills/orquestar-novela/`](.claude/skills/orquestar-novela/), en
Markdown y sin una línea de código. Los ocho subagentes están en
[`.claude/agents/`](.claude/agents/) y cada uno arranca leyendo su encargo de
`agentes/`, que es la única fuente de verdad de los prompts.

El canon queda en la carpeta de la novela, dentro de `biblioteca/`: los JSON del estado, el paquete de contexto con
el que se escribió cada capítulo, un Markdown por intento y `retoques.md`. Es
salida y no se versiona.

## Y para mirar lo que ha escrito

Ahí sí hay Python, y no escribe nada: mira.

### Requisitos

Python 3.11 o superior (aquí corre sobre 3.13). Todo sale de la biblioteca
estándar, así que **un repositorio recién clonado no necesita `pip install`**.
Las trazas necesitan `langfuse` y son opcionales.

### La interfaz web

```bash
python -m novela ui           # http://127.0.0.1:8787
```

Levanta un servidor local —`http.server`, nada que instalar— y abre el
navegador. Son tres salas:

- **Brief.** Los cinco campos del canon, en lectura. Una escena en three.js
  dibuja un cuadernillo por capítulo: el grosor son las palabras, el color el
  estado en el canon y la luz la pone el tono, con el candil parpadeando encima
  de la mesa.
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

**La página mira y no toca.** En el canon escribe la sesión de Claude Code que
orquesta y nadie más, así que en vez de botones la página da el comando exacto
que toca pegar. Lo que sí hace, y es lo que más justifica abrirla, es rehacer la
cuenta del gate con la fórmula del spec y avisar si no coincide con la que
escribió el orquestador: la suma la hace un modelo y eso es lo más frágil del
sistema.

Lo que el canon no guarda —la cuota diaria, las escenas, el focalizador, el
gancho final, el coste y las citas de las incidencias— aparece como «sin datos
todavía» y está listado con su motivo en un panel. Es aposta: preferimos el
hueco a un número inventado.

El puerto sale de `interfaz.puerto`, y `--puerto N` lo pisa para un arranque
suelto. La escena baja three.js de un CDN, y es lo único del repo que necesita
red. Si no llega, la interfaz funciona igual.

En Windows, `ui.bat` hace lo mismo buscando el intérprete por su cuenta, sin
fiarse del `PATH`.

### Ver qué hizo cada subagente

A [Langfuse](https://langfuse.com) va qué se le pidió a cada subagente, qué
contestó, con qué modelo y cuánto costó. Es la pregunta que el canon no
contesta: **por qué el modelo contestó lo que contestó**.

```bash
pip install "my-story-maker[trazas]"
cp .env.ejemplo .env          # y pon ahí tus claves de Langfuse
```

Con eso puesto, el hook de [`.claude/settings.json`](.claude/settings.json)
traza **cada llamada en el momento en que ocurre**, con su prompt, su modelo,
sus tokens y su latencia reales. No hay que lanzar nada: ocurre solo mientras la
novela se escribe. Y no puede romper nada — un hook que revienta ensuciaría la
sesión del orquestador, así que devuelve 0 siempre y deja además su línea en un
diario local.

El hook trae el gasto y ninguna nota. La otra mitad la trae esto:

```bash
python -m novela trazar   # del canon: las notas, el veredicto del gate y VD-08
```

Levanta el árbol entero desde el canon de la novela con **todas las puntuaciones** —las
tres notas de cada intento, la media, el veredicto y una extra que dice si la
suma del gate cuadra con la fórmula— y va marcado como reconstruido, porque no
trae tokens ni coste. Hace falta porque lo que el orquestador decide solo no es
una llamada a nadie: el hook no lo ve.

Una traza por unidad de trabajo —la preparación, **cada capítulo** y el cierre—,
agrupadas en una sesión por novela. Las tres notas del validador y la media
viajan como puntuaciones, así que la calidad del libro se mira en una gráfica en
lugar de releyendo capítulos.

Se apagan con `trazas.activas` a `false`. Y no hacen falta para nada: sin el
paquete, sin credencial o con Langfuse caído, la capa se calla y la novela se
escribe igual.

### En qué se fue el gasto

```bash
python -m novela informe-trazas --salida informe.md
```

Lee de vuelta las trazas de una novela y las agrega: gasto por rol, por capítulo
y por modelo, reparto de caché, llamadas más caras y más lentas, y el cruce del
coste de cada capítulo con sus notas y sus intentos. **El código cuenta y el
modelo juzga**: lo que se lee después se acumula en
[`docs/spec/TRAZAS.md`](docs/spec/TRAZAS.md), y la skill `analizar-trazas` lleva
el cuestionario para que todas las pasadas pregunten lo mismo.

## Comandos

| Comando | Qué hace |
|---|---|
| `ui [--puerto N]` | Abre la interfaz web. Mira y no escribe |
| `trazar [--modelo M]` | Manda a Langfuse las notas y los veredictos del canon |
| `informe-trazas [--sesion S] [--salida F] [--json]` | Agrega el gasto de una novela |
| `hook-traza` | Lo llama el hook, no una persona |
| `ui.bat` | `ui` en Windows, buscando el intérprete por su cuenta |

Opción global: `--config <ruta>`.

## Qué hay en cada sitio

| Carpeta | Qué contiene |
|---|---|
| `.claude/skills/orquestar-novela/` | La máquina de estados como instrucciones, y tres referencias |
| `.claude/agents/` | Los ocho subagentes: seis roles con el validador partido en tres |
| `agentes/` | Un `.md` por rol, con su encargo y sus modos de fallo. Única fuente de los prompts |
| `skills/` | Las skills de §10, que cada subagente carga al arrancar |
| `novela/` | El Python que mira: canon, interfaz, trazas e informe |
| `web/` | La interfaz: las tres salas, la escena three.js y la ambientación |
| `biblioteca/` | Las novelas, una carpeta cada una con su canon. Es salida y no se versiona |
| `tests/` | Tests del Python de `novela/`, sin red |
| `docs/spec/` | El spec, y el documento de análisis de trazas |

## Tests

```bash
python -m unittest discover -s tests -t .
```

Cincuenta y seis, sin red y sin coste. Cubren el lector del canon, la auditoría
del gate, la API de la interfaz, el árbol de trazas reconstruido y el hook.

**La orquestación en sí no tiene tests**, y no es un olvido: lo que hace es una
conversación. Es el precio de este diseño y está escrito en §21 del spec.
