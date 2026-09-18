# CLAUDE.md — my-story-maker

Sistema multiagente que escribe una novela histórica capítulo a capítulo a partir
de un brief de cinco campos. Versión 1.16.0.

**Tú eres el orquestador.** Tu trabajo **no es escribir la novela**: es decidir a
quién se llama, con qué delante, y qué se hace con lo que devuelve. La prosa, el
criterio histórico y el juicio literario son de los subagentes.

Se arranca con `/orquestar-novela`, o pidiendo preparar, escribir, reanudar o
cerrar una novela.

## Regla número uno: el spec manda

[`docs/spec/SPEC.md`](docs/spec/SPEC.md) es la fuente de verdad. Si el código y el
spec cuentan cosas distintas, manda el spec y el código es el que está mal.

**El spec y el código nunca divergen.** Cuando un cambio introduce, cambia o
elimina algo que el spec describe (una clave de `config.json`, un campo del
canon, un validador `VD-xx`, un comando, un estado, una instrucción de la skill),
el spec se actualiza en el mismo momento, no después. Eso implica además:

- Subir la versión en la cabecera del spec (`version:` y `actualizado:`), y con
  ella la de `pyproject.toml` y `novela/__init__.py`.
- Añadir su entrada en §16 con **sección tocada y motivo**, formato Keep a Changelog.
- Regenerar la tabla de §17 con el `git log` que la propia §17 documenta al final.
- Los números de sección son estables y **no se reutilizan**; si una sección
  desaparece, su número queda muerto (pasó con DA-01, DA-11 y §14).

Hay un segundo spec, [`docs/spec/TRAZAS.md`](docs/spec/TRAZAS.md), con su propia
versión. `SPEC.md` describe cómo se escribe una novela; aquel describe qué se ha
aprendido mirando cómo se escribió. **Aquel observa y no decide**: cuando un
hallazgo se convierte en un cambio de diseño, se muda a `SPEC.md`.

## Cómo se trabaja este repo

- **Documentos de spec**: cortos, centrados en decisiones y en el porqué, no en el
  cómo. Una sección por commit.
- **Commits**: uno por sección o por unidad de cambio, mensaje en minúsculas y en
  español, con el ámbito entre paréntesis y la sección tocada:
  `docs(spec): §12 la credencial del modo real va en el entorno`.
- **Push**: automático. Se commitea en local y se publica en el remoto sin pedir
  confirmación cada vez. Quedan fuera y siguen exigiendo permiso expreso las
  operaciones no reversibles: push --force, borrar ramas remotas y reescribir
  historia ya publicada.
- **Idioma y acentos**: todo en español. El código `.py` y los prompts de
  `agentes/`, `skills/` y `.claude/` van **sin acentos** (ASCII); los documentos
  Markdown (`SPEC.md`, `README.md`, este fichero) sí llevan acentos.

# Cómo está montado

## Qué hay en `.claude/`

| Fichero | Qué es |
|---|---|
| [.claude/skills/orquestar-novela/SKILL.md](.claude/skills/orquestar-novela/SKILL.md) | La máquina de estados escrita como instrucciones: los tres tramos, el loop de intentos y el bloqueo |
| [references/canon-en-ficheros.md](.claude/skills/orquestar-novela/references/canon-en-ficheros.md) | Dónde vive cada cosa del canon y quién la escribe |
| [references/paquete-de-contexto.md](.claude/skills/orquestar-novela/references/paquete-de-contexto.md) | Los nueve bloques, el cruce de etiquetas y el orden de recorte |
| [references/comprobaciones.md](.claude/skills/orquestar-novela/references/comprobaciones.md) | Los once `VD-xx` y el gate, con sus números |
| `.claude/agents/novela-*.md` | Los ocho subagentes |
| `.claude/settings.json` | El hook `PostToolUse` sobre `Agent`, que traza cada llamada (§22) |

Los ocho subagentes son los seis roles de §5, **con el validador partido en
tres**. Cada uno arranca leyendo su fichero de `agentes/` y sus skills de
`skills/`: los prompts tienen una sola fuente de verdad y no se duplican en el
fichero del subagente, que solo lleva nombre, descripción, herramientas y modelo.

**El modelo de cada rol vive en el frontmatter de su subagente**, no en
`config.json`. Las llamadas las hace Claude Code y solo lee el frontmatter, así
que un modelo escrito también en `config.json` sería un número que no gobierna
nada.

## Las dos reglas que no se rompen

1. **Ningún subagente escribe en el canon.** Devuelven JSON y escribe el
   orquestador, con la propuesta ya comprobada delante. La única excepción es el
   borrador del escritor, que no es canon hasta que pasa el gate y lo resume el
   cronista.
2. **Un capítulo a la vez.** El capítulo N+1 se escribe con el canon que dejó el
   N. Es del problema, no del diseño.

## Dónde sí hay paralelismo

**Los tres validadores corren a la vez**, lanzados en un único mensaje. No es una
opción de configuración: es la forma del sistema. Tres cabezas que no se ven dan
tres notas que no se contagian, que es lo que el gate necesita para que un texto
brillante pueda caer por continuidad.

## El canon en ficheros

```
biblioteca/2026-09-18-sevilla-1587/
  canon/estado.json  brief.json  dossier.json  personajes.json
        escaleta.json  hilos.json  timeline.json  resumenes/cap-NN.json
  contexto/cap-NN.md     el paquete con el que se escribió, para auditarlo
  capitulos/cap-NN-intento-K.md
  retoques.md
```

No se versiona: es salida, no fuente. **No hay carpeta de trabajo**: cada novela
nace en la suya, así que empezar una nunca pisa otra y no hay nada que archivar a
mano. La novela en curso es aquella cuyo `estado.json` se tocó más tarde.

## Lo que este diseño no tiene

Y conviene no olvidarlo, porque es el precio:

- **El gate no es código.** La fórmula está escrita y hay que imprimir la
  operación entera, pero la suma la hace un modelo. La interfaz la rehace y avisa
  si no cuadra (§19), pero avisar es todo lo que hace: DA-15.
- **El paquete de contexto no es determinista.** Los filtros son mecánicos y el
  conteo va por `wc`, pero el ensamblado lo hace un modelo: el invariante de que
  mismo capítulo y mismo canon dan el mismo paquete pasa de garantizado a
  instruido.
- **La orquestación no tiene tests.** Lo que hace es una conversación. Los 89
  tests que hay cubren el Python de `novela/`, que mira el canon y arranca al
  orquestador, pero no escribe novelas.

# El diseño

Esto es lo que especifican §2–§13 y §15, y lo obedece la skill.

## Los seis agentes (§5)

| Rol | Entrada | Salida | Skills que carga |
|---|---|---|---|
| `investigador` | brief | `{ datos: [...] }` | `formato-dossier` |
| `arquitecto` | brief + dossier | `{ personajes, capitulos }` | `formato-fichas` |
| `escritor` | paquete de contexto | `{ texto, faltantes? }` | `formato-paquete-contexto`, `estilo-prosa` |
| `validador` | capítulo + paquete + encargo | `{ revisiones: [3 bloques] }` | `rubricas-validador` |
| `cronista` | capítulo aprobado + fichas | resumen, hilos, `cambios_personaje`, `eventos` | `formato-fichas` |
| `editor_global` | resúmenes + escaleta + personajes | `{ retoques: [...] }` | — |

Una skill es texto que lee un modelo, **nunca fuente de verdad para el código**:
los números y umbrales viven en `config.json`.

## Los once validadores (§9)

VD-01 forma, VD-02 obligatorios, VD-03 ids existentes, VD-04 dossier con fuente y
estado (un `verificado` con fuente `modelo` es inválido), VD-05 evento de trama con
capítulo e histórico sin él, VD-06 resumen solo si hay intento aprobado, VD-07 número
de capítulos dentro de márgenes, **VD-08 la única de dos escalones** (aviso y bloqueo,
de ahí sus dos márgenes), VD-09 personajes presentes ⊆ ficha, VD-10 tres dimensiones
una vez cada una con nota entera 1-5, VD-11 nada bloqueante pendiente al confirmar.

Las tres dimensiones del validador son siempre `continuidad`, `anacronismos` y
`logica_ritmo`, en ese orden.

## El gate (§8)

```
aprueba = min(notas) >= nota_minima y media >= media_minima y ninguna incidencia grave
```

La incidencia grave veta por sí sola. Siempre tres notas; **nota global no existe**.

## Máquina de estados (§4)

`borrador` → `investigado` → `estructurado` → `escribiendo` → `escrito` → `editado`,
con `bloqueado` como salida lateral que exige mano humana. `escribiendo` se entra al
**arrancar** el primer capítulo, no al aprobarlo.

Dos puntos fijos de intervención humana: capítulo bloqueado (tres salidas manuales)
y los retoques finales, que se aplican a mano.

## Invariantes del diseño

1. **Una sola escritura en el canon por capítulo**, la del cronista, después del
   gate, y de una vez (VD-11): o entran resumen, cambios de ficha y eventos
   juntos, o no entra nada.
2. **El texto completo de capítulos anteriores no entra nunca** en el paquete,
   salvo el enganche (`contexto.palabras_enganche` palabras literales del anterior
   aprobado). Para eso están los resúmenes.
3. **Orden de recorte del paquete**, si se pasa de `tope_contexto`: memoria larga,
   cronología, reparto de fondo, época. Encargo, personajes y hilos vivos no se
   recortan; si aun así no cabe, el capítulo se marca `bloqueado`.
4. **VD-08 antes del validador**: si el capítulo redactado no cumple lo básico se
   reintenta la generación sin gastar las tres llamadas al validador.
5. **El reintento del último intento va de cero**, y el que descarta VD-08 también.
   Los demás reciben su propio texto para arreglo quirúrgico.
6. **Un bloqueante que falla dos veces seguidas para el proceso** y deja el estado
   escrito. No hay reintento infinito ni backoff.
7. **El estado vive en el canon, nunca en memoria del proceso.** Por eso reanudar
   no necesita argumentos. Y **reanudar no desbloquea**.

## Configuración (§12)

Un único `config.json` en la raíz. **Si un número aparece escrito en el código o
en un prompt sin pasar por este fichero, es un bug.** Las claves:
`gate.{nota_minima,media_minima,max_intentos}`,
`contexto.{tope_contexto,ventana_resumenes,palabras_enganche}`,
`interfaz.puerto`, `lanzador.{comando,permisos}`, `trazas.{activas,entorno,texto}`,
`margenes.{capitulos_min,capitulos_max,palabras_aviso,palabras_bloqueo,parrafos_min}`.
Diecisiete. Reglas cruzadas: `palabras_bloqueo > palabras_aviso` y
`capitulos_max >= capitulos_min`.

Las credenciales van en un `.env` de la raíz que no se versiona. Un **perfil** es
un `config*.json` de la raíz, nada más.

# El Python que queda (§18–§20, §22)

No escribe novelas: mira lo que escribió el orquestador.

```bash
python -m novela ui                          # interfaz web, solo lectura (§19)
python -m novela trazar                      # manda a Langfuse el canon reconstruido (§20)
python -m novela biblioteca                  # las novelas, y cuál está en curso (§21)
python -m novela informe-trazas --salida informe.md   # agrega el gasto (§22)
                                             # sin Langfuse tira del diario local
python -m unittest discover -s tests -t .    # 89 tests, sin red
```

`hook-traza` existe pero no se llama a mano: lo llama el hook de
`.claude/settings.json` una vez por cada llamada a un subagente.

## Mapa del código

| Fichero | Qué es | Spec |
|---|---|---|
| [novela/config.py](novela/config.py) | Carga y **valida entero** `config.json` | §12 |
| [novela/canon_cc.py](novela/canon_cc.py) | Lector **de solo lectura** del canon en ficheros, y la auditoría del gate | §21 |
| [novela/servidor.py](novela/servidor.py) | Interfaz web: sirve `web/` y una API que solo lee | §19 |
| [novela/lanzador.py](novela/lanzador.py) | Arranca `claude -p` con el brief. **No escribe en el canon** | §19 |
| [novela/trazas.py](novela/trazas.py) | Capa única de observabilidad; la única que sabe que Langfuse existe | §20 |
| [novela/trazas_cc.py](novela/trazas_cc.py) | Reconstruye el árbol de §20 desde el canon | §20 |
| [novela/trazas_hook.py](novela/trazas_hook.py) | El hook `PostToolUse`: traza cada llamada en vivo, con su gasto | §22 |
| [novela/informe.py](novela/informe.py) | Lee las trazas de vuelta y agrega el gasto; sin Langfuse, del diario local | §22 |
| [novela/biblioteca.py](novela/biblioteca.py) | Dónde vive cada novela y cuál es la de ahora. **No escribe canon** | §21 |
| [novela/entorno.py](novela/entorno.py) | Lector del `.env` | §12, §20 |
| [novela/\_\_main\_\_.py](novela/__main__.py) | CLI. **No decide nada** | §18 |

## Interfaz web (§19) y observabilidad (§20)

`python -m novela ui` levanta un servidor local de la biblioteca estándar.
Cuatro salas: **brief** qué libro es, **escritorio** por dónde va, **arquitectura**
el pipeline de §4, §7, §8 y §9 como grafo por capas en **SVG inline**, y
**lectura** el capítulo. Solo la tercera sigue diciendo algo con el canon vacío,
y cada una tiene su enlace (`#arquitectura`).
**En el canon escribe el orquestador y nadie más**, así que cualquier método que
no sea `GET` contra la API responde 409 y da el comando que sí escribe. Las dos
excepciones no tocan el canon: `POST /api/trazas`, que manda a Langfuse lo que el
canon ya dice, y `POST /api/lanzar`, que **arranca** una sesión de Claude Code con
el brief de la sala del brief y se aparta. Esa segunda deroga el «solo GET» en una
ruta; la primera regla de §21 no se toca, porque quien escribe la novela sigue
siendo esa sesión.

**Ningún dato de la pantalla es propio de la interfaz**: o se lee del canon o se
recalcula con las reglas del spec. Lo que el canon no guarda se pinta «sin datos
todavía», **no se rellena**, y además se declara junto en un panel con el motivo.

La paleta es la de Qaracter (`#FF7932` y `#233441`) y manda. La ambientación
histórica de [web/ambientacion.css](web/ambientacion.css) va **por debajo**: ocupa
los neutros, las texturas y los adornos, y el naranja hace de lacre sin cambiar de
valor. El cuarto tiene luz de día y va en gris roto; lo único cálido es el
capítulo, que se lee sobre vitela. Cada color de marca tiene dos variantes,
relleno y tinta, porque el naranja del logotipo no pasa AA como texto sobre claro.
La escena WebGL es el fondo del **brief** y de ninguna otra sala: three.js viaja
por CDN —lo único del repo que necesita red— y degrada.

**Una traza es una unidad de trabajo cerrada, no el libro.** Ningún fallo de
observabilidad para una novela, y el hook menos que ninguno: devuelve 0 siempre,
porque un hook que revienta ensucia la sesión del orquestador.

**Los evaluadores de calidad de §20 no entran en este repositorio.** Viven solo en
Langfuse, y no por descuido: el escritor tiene `Read` sobre el proyecto, así que
una rúbrica guardada aquí la puede leer justo quien está siendo evaluado. No los
versiones, no los copies a un fichero de trabajo dentro del repo y no escribas su
texto en el spec. Lo que sí va al spec es la decisión: que existen, a qué
observación apuntan y por qué están fuera.

## Los objetivos medibles (§23)

Siete, con línea base y meta. El orden importa: **OB-01**, el acuerdo entre el
validador y el juez externo de §20, va primero porque todas las demás notas se
las pone el propio sistema y sin él no miden calidad sino autoestima. **OB-02**
(1,33 intentos por capítulo) y **OB-03** (25% de intentos incumplen un «Ignora»)
son el mismo problema por los dos lados y bajan el coste sin tocar umbrales.
**OB-04** (el gate cuadra) y **OB-05** (caché al 100%) son de guardia: están
perfectos y lo que se pide es que no bajen.

No son objetivos, y está escrito por qué: bajar el coste por sí solo, subir las
notas del validador, y bajar `media_minima`.

# Estado actual y cosas abiertas

- El `.drawio` de [docs/diagrama/](docs/diagrama/) va por detrás del Mermaid: le
  falta el cronista y se regenera a mano. El Mermaid de §4 es el bueno.
- Decisiones abiertas vivas en §15: DA-02, DA-03, DA-04, DA-05, DA-06, DA-07,
  DA-08, DA-09, DA-10, DA-12, DA-13, DA-14, DA-15.
- La búsqueda web del investigador no existe: su subagente tiene `tools: Read`.
  Para que entre hay que cambiarle las herramientas, no una clave de config.
- **Dos huecos del modelo de datos**, que salieron en la primera pasada completa:
  ningún `VD-xx` comprueba que el cronista respete un «Ignora» de una ficha, así
  que un conocimiento que el gate acaba de vetar puede entrar por la puerta de al
  lado; y `sabe` solo acumula, sin forma de retractar un «Ignora», de modo que una
  ficha termina afirmando y negando lo mismo.
