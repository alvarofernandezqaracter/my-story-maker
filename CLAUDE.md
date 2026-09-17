# CLAUDE.md — my-story-maker

Sistema multiagente que escribe una novela histórica capítulo a capítulo a partir
de un brief de cinco campos. Versión 0.13.0.

**El camino principal es la orquestación delegada**: quien orquesta es una sesión
de Claude Code, no código. Hay un segundo camino, el harness de Python, que hace
lo mismo escrito en `novela/` y que vive también aquí.

| | Camino principal (§21) | Harness (§14, §18–§20) |
|---|---|---|
| Quién orquesta | Una sesión de Claude Code | `novela/flujo.py` |
| Dónde vive | `.claude/`, todo Markdown | `novela/`, 3.802 líneas de Python |
| Canon | JSON en `novela-cc/canon/` | SQLite en `canon.db` |
| Se lanza con | `/orquestar-novela` | `python -m novela ...` |
| Rama | `main` | `harness-python` |

**Los dos comparten los prompts** de `agentes/` y `skills/` y los umbrales de
`config.json`, y no los duplican: cada subagente lee su fichero de rol al
arrancar. Tocar un prompt cambia los dos caminos, y eso es deliberado.

## Regla número uno: el spec manda

[`docs/spec/SPEC.md`](docs/spec/SPEC.md) es la fuente de verdad. Si el código y el
spec cuentan cosas distintas, manda el spec y el código es el que está mal.

§1 dice qué secciones describen el diseño —que vale para los dos caminos— y
cuáles son de un camino concreto.

**El spec y el código nunca divergen.** Cuando un cambio introduce, cambia o
elimina algo que el spec describe (una clave de `config.json`, un campo del
canon, un validador `VD-xx`, un comando, un estado, una instrucción de la skill),
el spec se actualiza en el mismo momento, no después. Eso implica además:

- Subir la versión en la cabecera del spec (`version:` y `actualizado:`), y con
  ella la de `pyproject.toml` y `novela/__init__.py`.
- Añadir su entrada en §16 con **sección tocada y motivo**, formato Keep a Changelog.
- Regenerar la tabla de §17 con el `git log` que la propia §17 documenta al final.
- Los números de sección son estables y **no se reutilizan**; si una sección
  desaparece, su número queda muerto (pasó con DA-01).

## Cómo se trabaja este repo

- **Documentos de spec**: cortos, centrados en decisiones y en el porqué, no en el
  cómo. Una sección por commit.
- **Commits**: uno por sección o por unidad de cambio, mensaje en minúsculas y en
  español, con el ámbito entre paréntesis y la sección tocada:
  `docs(spec): §12 la credencial del modo real va en el entorno`,
  `feat(harness): capa unica de llamada a agentes, simulada y real`.
- **Push**: automático. Se commitea en local y se publica en el remoto sin pedir
  confirmación cada vez. Quedan fuera y siguen exigiendo permiso expreso las
  operaciones no reversibles: push --force, borrar ramas remotas y reescribir
  historia ya publicada.
- **Idioma y acentos**: todo en español. El código `.py` y los prompts de
  `agentes/`, `skills/` y `.claude/` van **sin acentos** (ASCII); los documentos
  Markdown (`SPEC.md`, `README.md`, este fichero) sí llevan acentos.

# El camino principal: orquestación delegada (§21)

Tú eres el orquestador. Tu trabajo **no es escribir la novela**: es decidir a
quién se llama, con qué delante, y qué se hace con lo que devuelve. La prosa, el
criterio histórico y el juicio literario son de los subagentes.

Se arranca con `/orquestar-novela`, o pidiendo preparar, escribir, reanudar o
cerrar una novela.

## Qué hay en `.claude/`

| Fichero | Qué es |
|---|---|
| [.claude/skills/orquestar-novela/SKILL.md](.claude/skills/orquestar-novela/SKILL.md) | La máquina de estados escrita como instrucciones: los tres tramos, el loop de intentos y el bloqueo |
| [references/canon-en-ficheros.md](.claude/skills/orquestar-novela/references/canon-en-ficheros.md) | Dónde vive cada cosa del canon y quién la escribe |
| [references/paquete-de-contexto.md](.claude/skills/orquestar-novela/references/paquete-de-contexto.md) | Los nueve bloques, el cruce de etiquetas y el orden de recorte |
| [references/comprobaciones.md](.claude/skills/orquestar-novela/references/comprobaciones.md) | Los once `VD-xx` y el gate, con sus números |
| `.claude/agents/novela-*.md` | Los ocho subagentes |

Los ocho subagentes son los seis roles de §5, **con el validador partido en
tres**. Cada uno arranca leyendo su fichero de `agentes/` y sus skills de
`skills/`: los prompts tienen una sola fuente de verdad y la comparten los dos
caminos.

## Las dos reglas que no se rompen

1. **Ningún subagente escribe en el canon.** Devuelven JSON y escribe el
   orquestador, con la propuesta ya comprobada delante. La única excepción es el
   borrador del escritor, que no es canon hasta que pasa el gate y lo resume el
   cronista.
2. **Un capítulo a la vez.** El capítulo N+1 se escribe con el canon que dejó el
   N. Es del problema, no del diseño.

## Dónde sí hay paralelismo

**Los tres validadores corren a la vez**, lanzados en un único mensaje. No es una
opción de configuración como `validador.modo` en el harness: es la forma del
camino. Tres cabezas que no se ven dan tres notas que no se contagian, que es lo
que el gate necesita para que un texto brillante pueda caer por continuidad.

## El canon en ficheros

```
novela-cc/
  canon/estado.json  brief.json  dossier.json  personajes.json
        escaleta.json  hilos.json  timeline.json  resumenes/cap-NN.json
  contexto/cap-NN.md     el paquete con el que se escribió, para auditarlo
  capitulos/cap-NN-intento-K.md
  retoques.md
```

No se versiona. Vive aparte de `canon.db` a propósito: los dos caminos corren
sobre el mismo repositorio sin pisarse y se comparan después.

## Lo que este camino no tiene

Y conviene no olvidarlo, porque es el precio:

- **El gate deja de ser código.** La fórmula está escrita y hay que imprimir la
  operación entera, pero la suma la hace un modelo.
- **El paquete de contexto deja de ser determinista.** Los filtros son mecánicos
  y el conteo va por `wc`, pero el ensamblado lo hace un modelo: el invariante de
  que mismo capítulo y mismo canon dan el mismo paquete pasa de garantizado a
  instruido.
- **Ni tests sin red ni trazas.** §20 cuelga de `novela/agentes.py` y aquí no se
  pasa por ahí.

# El diseño, que vale para los dos caminos

Esto es lo que especifican §2–§13 y §15, y lo obedecen igual el harness y la
skill.

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
en un prompt sin pasar por este fichero, es un bug.** Dieciocho claves:
`ejecucion.modo`, `gate.{nota_minima,media_minima,max_intentos}`,
`contexto.{tope_contexto,ventana_resumenes,palabras_enganche}`, `validador.modo`,
`interfaz.puerto`, `trazas.{activas,entorno}`,
`margenes.{capitulos_min,capitulos_max,palabras_aviso,palabras_bloqueo,parrafos_min}`,
`modelo_por_rol`, `busqueda_web`. Reglas cruzadas: `palabras_bloqueo > palabras_aviso`
y `capitulos_max >= capitulos_min`.

`ejecucion.modo` y `validador.modo` son del harness: el camino delegado no los usa.

Las credenciales van en un `.env` de la raíz que no se versiona. Un **perfil** es
un `config*.json` de la raíz, nada más: eso es lo que elige el selector de §19.

# El harness de Python (§14, §18–§20)

Segundo camino. Vive en `novela/` y tiene su rama, `harness-python`, que es este
repositorio sin `.claude/agents/` ni la skill.

## Stack y comandos

Python 3.13 (mínimo 3.11) con `sqlite3` y `unittest`, los dos de la biblioteca
estándar. El modo `simulado` —el de por defecto— no necesita instalar nada.

```bash
python -m novela init
python -m novela brief brief.ejemplo.json
python -m novela preparar     # investigador y arquitecto
python -m novela escribir     # loop: escritor, VD-08, validador, gate, cronista
python -m novela cerrar       # editor global y retoques.md
python -m novela ui           # ciclo entero desde el navegador (§19)
python -m unittest discover -s tests -t .    # 74 tests, sin red
```

Otros comandos: `reanudar`, `estado`,
`ver <dossier|personajes|escaleta|resumenes|timeline|hilos|contexto N|capitulo N>`,
`poner <personaje|capitulo|dato> <fichero.json>`,
`desbloquear --capitulo N [--aprobar-intento K | --reiniciar]`, `skills`.

## Mapa del código

| Fichero | Qué es | Spec |
|---|---|---|
| [novela/config.py](novela/config.py) | Carga y **valida entero** `config.json` | §12 |
| [novela/canon.py](novela/canon.py) | SQLite: las 7 tablas, y `escritura_del_cronista` como transacción única | §3, §6 |
| [novela/esquemas.py](novela/esquemas.py) | Contratos de I/O de los seis roles y `comprobar_forma` (VD-01/VD-02) | §5 |
| [novela/validadores.py](novela/validadores.py) | Los once `VD-xx` deterministas | §9 |
| [novela/gate.py](novela/gate.py) | Fórmula del gate, `mejor_intento`, `incidencias_ordenadas` | §8 |
| [novela/contexto.py](novela/contexto.py) | Generador de contexto: nueve bloques, serialización y recorte | §7 |
| [novela/skills.py](novela/skills.py) | Carga `agentes/<rol>.md` + sus skills | §10 |
| [novela/agentes.py](novela/agentes.py) | Capa única de llamada; oculta simulado/real; `ParadaDelProceso` | §5, §12 |
| [novela/proveedor.py](novela/proveedor.py) | Modo `real`: SDK de Anthropic | §12 |
| [novela/claude_code.py](novela/claude_code.py) | Modo `claude_code`: `claude --print` sin herramientas | §12 |
| [novela/simulado.py](novela/simulado.py) | Respuestas fijas + inyección de fallos | §12 |
| [novela/flujo.py](novela/flujo.py) | `preparar`, `escribir_capitulo`, `cerrar`, `reanudar` | §4, §8, §11 |
| [novela/servidor.py](novela/servidor.py) | Interfaz web: sirve `web/`, la API y el hilo único del flujo | §19 |
| [novela/trazas.py](novela/trazas.py) | Capa única de observabilidad; la única que sabe que Langfuse existe | §20 |
| [novela/entorno.py](novela/entorno.py) | Lector del `.env` | §12, §20 |
| [novela/\_\_main\_\_.py](novela/__main__.py) | CLI. **No decide nada** | §18 |

**Nada corre en paralelo** con la configuración por defecto. El único paralelismo
es `validador.modo: "separado"`, que hace tres llamadas sobre el mismo capítulo.
La interfaz no es excepción: su flujo vive en **un solo hilo** y arrancar otro
mientras hay uno vivo devuelve 409.

## Modo simulado e inyección de fallos

Dos variables de entorno, **solo con efecto en modo simulado**, toman una lista de
`capitulo:intento`:

```bash
NOVELA_SIM_FALLOS="2:1"  # el validador suspende ese intento
NOVELA_SIM_CORTOS="3:1"  # el escritor devuelve un capitulo que VD-08 bloquea
```

Existen porque el camino interesante —rechazo, reintento, bloqueo— no se ve nunca
si todas las respuestas simuladas son buenas.

## Interfaz web (§19) y observabilidad (§20)

`python -m novela ui` levanta un servidor local de la biblioteca estándar: brief,
lanzar a los agentes, ver el proceso y leer los capítulos. Las tres salas son
[web/brief.js](web/brief.js), [web/taller.js](web/taller.js) y
[web/lectura.js](web/lectura.js). **Ningún dato de la pantalla es propio de la
interfaz**: o se lee del canon o se recalcula con las reglas del harness. Lo que
el canon no guarda se pinta «sin datos todavía» y **no se rellena**.

Cada llamada a un agente deja traza en Langfuse, instrumentada en un solo sitio,
[novela/trazas.py](novela/trazas.py). **Una traza es una unidad de trabajo
cerrada, no el libro.** Ningún fallo de observabilidad para una novela.

La paleta es la de Qaracter (`#FF7932` y `#233441`). three.js viaja por CDN —lo
único del repo que necesita red— y degrada.

## Tests

`python -m unittest discover -s tests -t .` corre 74 tests en tres ficheros, sin
red y sin coste. Cada test del flujo corre en su propio directorio temporal porque
el harness escribe en el `cwd`. Los tests **apagan las trazas a mano** en lugar de
fiarse de que el entorno esté limpio.

Cubren el harness. **El camino delegado no tiene tests**, y esa es una de sus
diferencias de fondo.

# Estado actual y cosas abiertas

- El `.drawio` de [docs/diagrama/](docs/diagrama/) va por detrás del Mermaid: le
  falta el cronista y se regenera a mano. El Mermaid de §4 es el bueno.
- Decisiones abiertas vivas en §15: DA-02, DA-03, DA-04, DA-05, DA-06, DA-07,
  DA-08, DA-09, DA-10, DA-12.
- F6 (búsqueda web real del investigador) no está implementado: `busqueda_web`
  está a `true` para no tocar el esquema más tarde, pero el investigador la ignora.
- El modo `real` no se ha ejercitado contra la API desde la migración.
- **Dos huecos del modelo de datos que tienen los dos caminos**, y que salieron en
  la primera pasada completa del camino delegado: ningún `VD-xx` comprueba que el
  cronista respete un «Ignora» de una ficha, así que un conocimiento que el gate
  acaba de vetar puede entrar por la puerta de al lado; y `sabe` solo acumula, sin
  forma de retractar un «Ignora», de modo que una ficha termina afirmando y
  negando lo mismo.
