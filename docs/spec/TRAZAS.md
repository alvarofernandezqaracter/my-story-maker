---
doc: spec-analisis-de-trazas
version: 0.2.0
estado: borrador
actualizado: 2026-09-17
---

# Spec — Análisis de trazas

Segundo spec del repositorio. [`SPEC.md`](SPEC.md) describe **cómo se escribe
una novela**; este describe **qué se ha aprendido mirando cómo se escribió**.
Son dos documentos porque son dos cosas distintas: uno se lee para construir y
el otro para decidir qué construir después.

Tiene su propia versión, independiente de la de `SPEC.md` y de la del paquete.
Analizar una novela no cambia el sistema, así que no tiene por qué mover la
versión de nadie.

## §1 Qué es esto y qué no es

**Qué es.** El sitio donde se acumulan, pasada a pasada, los hallazgos de mirar
las trazas de una novela ya escrita: en qué se fue el gasto, qué funcionó, qué
no y qué se propone cambiar.

**Qué no es.** Un segundo diseño. **Este documento observa, no decide.** Cuando
un hallazgo se convierte en un cambio de diseño —bajar un umbral, partir el
paquete de contexto, cambiar el modelo de un rol— eso se muda a `SPEC.md` como
`DA-xx` o como cambio de sección, y aquí queda la referencia cruzada.

La regla importa más de lo que parece: sin ella, en tres pasadas hay dos
documentos que se contradicen y ninguno de los dos es la fuente de verdad. La
regla número uno del repositorio sigue siendo que manda `SPEC.md`.

**Los números no se escriben a mano.** Todo lo que se afirme aquí sale del
informe de §2 o del canon. Un hallazgo sin su número al lado no es un hallazgo,
es una impresión, y una impresión no se puede contrastar dentro de tres novelas
—que es exactamente para lo que existe este fichero—.

## §2 De dónde salen los números

```bash
python -m novela informe-trazas --salida informe.md
```

Lee de vuelta las trazas de una novela desde Langfuse y las agrega: gasto por
rol, por capítulo y por modelo, reparto de caché, llamadas más caras y más
lentas, y el cruce del coste de cada capítulo con sus notas y sus intentos. Vive
en [`novela/informe.py`](../../novela/informe.py).

**El código cuenta y el modelo juzga**, que es la misma división que ya hace el
gate de §8 de `SPEC.md`: la fórmula en código, la lectura fuera. Al analista no
se le pasa la traza cruda —son decenas de megas y casi todo es ruido—, se le
pasa el agregado y las muestras que el propio agregado señala.

Dos fuentes alimentan ese informe, y no se mezclan:

| Fuente | Qué aporta | Etiqueta |
|---|---|---|
| El hook de §20 de `SPEC.md` | Prompt, respuesta, modelo, tokens, caché y latencia reales | `directo` |
| La reconstrucción desde el canon | Árbol, notas, veredictos del gate y auditoría | `reconstruido` |

**Solo lo `directo` cuenta gasto.** Lo reconstruido no tiene tokens que contar, y
sumarlo sería inventárselos.

## §3 Cómo se hace una pasada

Con la skill [`analizar-trazas`](../../.claude/skills/analizar-trazas/SKILL.md),
que lleva el cuestionario fijo. No hay un subagente para esto a propósito: el
análisis es una conversación con repreguntas, y un subagente que devuelve su
informe y se muere obliga a empezar de cero en cada una. Lo que sí hace falta es
que todas las pasadas pregunten lo mismo, o no se podrán comparar entre ellas;
de eso se encarga la skill.

Una pasada no reescribe a la anterior. Se añade una sección nueva, numerada a
partir de §5, con su fecha, su novela y su sesión. Los números de sección son
estables y no se reutilizan, como en `SPEC.md`.

## §4 Historial de cambios

Formato Keep a Changelog.

### [0.1.0] — 2026-09-17

**Añadido**
- §1–§3. El documento, sus reglas y de dónde salen sus números. Nace junto con
  el hook de trazas del camino delegado y el comando `informe-trazas`, que son
  los que hacen que haya algo que analizar.

### [0.2.0] — 2026-09-17

**Añadido**
- §6. Primera pasada de análisis, sobre la sesión `novela-1abde479ff05`. Sale
  con una advertencia de método que condiciona todo lo demás: esa novela se
  escribió a caballo de un cambio de modelo, así que ningún número suyo compara
  roles, compara regímenes.

## §5 Pasadas de análisis

Una por sección, numeradas a partir de §6. No se reescribe una anterior.

## §6 Pasada 1 — 2026-09-17, sesión `novela-1abde479ff05`

Seis capítulos, 11.341 palabras. **41 llamadas** a subagentes, 1.697.054 tokens,
103,8 minutos de modelo y 0,86 $ contados.

### Lo primero, porque invalida medio informe

**Esta novela se escribió con tres modelos distintos, y no a propósito.** Los
capítulos 1–5 y la preparación corrieron con `claude-opus-5[1m]` (investigador,
arquitecto, escritor) y `claude-sonnet-5` (validador, cronista). El capítulo 6 y
el cierre corrieron enteros con `claude-haiku-4-5`. El cambio es el commit
`1dc7cc0`, que fijó `model: haiku` en los ocho ficheros de `.claude/agents/`
mientras la novela estaba a medias.

**Consecuencia para quien lea esto dentro de tres novelas: ninguna comparación
entre roles de esta pasada es válida sin separar por modelo**, porque cada rol
corrió mayoritariamente con un modelo distinto. La tabla «gasto por rol» del
informe dice que el validador se lleva el 60% de los tokens, y eso mezcla 18
llamadas en sonnet con 6 en haiku.

Y un segundo aviso: **`claude-opus-5[1m]` no tiene precio en la lista de modelos
de Langfuse**, así que sus 8 llamadas y 289.765 tokens cuentan como 0,00 $. El
total de 0,86 $ está subestimado y no se sabe en cuánto. El informe lo avisa
solo, que es lo que hay que exigirle.

### En qué se va el gasto

| Modelo | Llamadas | Tokens | Coste |
|---|---:|---:|---:|
| `claude-sonnet-5` | 23 | 936.238 | 0,7558 $ |
| `claude-haiku-4-5` | 10 | 471.051 | 0,0993 $ |
| `claude-opus-5[1m]` | 8 | 289.765 | sin precio |

Por rol, y separando el modelo, que es la única forma en que estos números
significan algo:

| Rol | Modelo | Llamadas | Tokens/llamada | Segundos/llamada |
|---|---|---:|---:|---:|
| validador | sonnet-5 | 18 | 39.812 | 130 |
| validador | haiku-4.5 | 6 | 49.817 | 197 |
| escritor | opus-5[1m] | 6 | 38.715 | 197 |
| cronista | sonnet-5 | 5 | 43.923 | 118 |
| escritor | haiku-4.5 | 2 | 44.625 | 189 |
| cronista | haiku-4.5 | 1 | 47.254 | 199 |
| editor_global | haiku-4.5 | 1 | 35.642 | 104 |
| arquitecto | opus-5[1m] | 1 | 33.343 | 163 |
| investigador | opus-5[1m] | 1 | 24.130 | 94 |

**El validador es la mitad del libro**: 24 de las 41 llamadas. Es lo esperable y
no es un problema: son tres por intento por diseño, y esa independencia es lo que
permite que un texto brillante caiga por continuidad. Pero fija dónde está la
palanca si algún día hay que abaratar.

### Lo que ya funciona bien

- **La caché es perfecta y no es casualidad.** De 1.412.329 tokens de entrada,
  1.412.171 salieron de caché: **el 100,0%**, con 158 tokens frescos en toda la
  novela. El paquete de contexto de §7 se reenvía entero en cada intento y no se
  está pagando dos veces. Este es el número que más se habría notado si estuviera
  mal, y está bien.
- **El gate no está rozando sus umbrales.** Las seis medias aprobadas fueron 5,0,
  5,0, 4,0, 4,67, 4,67 y 4,33 contra una `media_minima` de 3,7. El margen más
  estrecho es de 0,30 sobre 5. No hay ningún capítulo que entrara raspando.
- **El contexto está muy lejos del tope.** Crece de 1.848 tokens en el capítulo 1
  a 5.915 en el 6 —unos 800 por capítulo— contra un `tope_contexto` de 40.000.
  Al ritmo observado, el orden de recorte de §7 no se ejercitaría hasta el
  capítulo 43. **En esta novela no se recortó nada.**
- **Los dos rechazos del gate fueron rechazos de verdad.** Capítulo 2 intento 1 y
  capítulo 6 intento 1, los dos con una nota mínima de 1 y una incidencia grave.
  No fueron capítulos aprobables tumbados por un decimal.

### Lo que no termina de funcionar

- **Haiku no salió más barato por llamada, y salió más lento.** El validador en
  haiku gastó 49.817 tokens por llamada frente a 39.812 en sonnet (+25%) y tardó
  197 segundos frente a 130 (+52%). **No lo tomes como una conclusión sobre
  haiku**: sus 6 llamadas son todas del capítulo 6, que es el de mayor contexto
  (5.915 tokens de paquete, +38% sobre el capítulo 5). El aumento de tokens se
  explica por ahí. El de tiempo, no del todo. Para confirmarlo hace falta una
  novela entera en haiku, que es justo lo que va a pasar en la siguiente pasada.
- **El diario local duplica llamadas.** `novela-cc/trazas/llamadas.jsonl` tenía
  **83 líneas para 41 llamadas reales**: el rescate desde el transcript
  reprocesó lo que el hook ya había anotado. Langfuse no se contaminó, porque el
  id de traza se siembra del contenido y allí se consolidaron en 41, pero
  **cualquiera que cuente líneas del diario se equivoca por el doble**. El
  módulo que lo provocaba se retiró en 1.1.0 de `SPEC.md`; el diario de esta
  pasada se queda como está, con su duplicado dentro.
- **El informe no separa por modelo dentro de un rol.** La tabla «gasto por rol»
  suma los dos regímenes. Que hiciera falta calcularlo a mano para escribir esta
  sección es un hueco del informe, no del análisis.

### Coste contra calidad

| Cap | Intentos | Notas | Media | Contexto | Tokens | Coste |
|---:|---:|---|---:|---:|---:|---:|
| 1 | 1 | 5/5/5 | 5,00 | 1.848 | 170.657 | 0,0934 $ |
| 2 | 2 | 5/5/5 | 5,00 | 2.729 | 355.070 | 0,2116 $ |
| 3 | 1 | 5/3/4 | 4,00 | 3.500 | 203.792 | 0,1352 $ |
| 4 | 1 | 4/5/5 | 4,67 | 3.938 | 218.559 | 0,1670 $ |
| 5 | 1 | 5/5/4 | 4,67 | 4.272 | 220.452 | 0,1486 $ |
| 6 | 2 | 5/4/4 | 4,33 | 5.915 | 435.409 | 0,0925 $ |

**Lo caro no es lo bueno.** El capítulo más barato de los medidos en el mismo
régimen es el 1, y es el de mejor nota (5,00). El 4 es el más caro de los de un
solo intento (0,1670 $) y saca 4,67. La correlación, si existe, va en contra.

**Un reintento cuesta lo que cuesta el capítulo.** Los dos capítulos de dos
intentos, el 2 y el 6, son los dos más caros en tokens de su régimen: 355.070 y
435.409, frente a una horquilla de 170.657–220.452 en los de un intento. Es
coherente con el diseño —el reintento del último intento va de cero— y pone
precio a la decisión: **cada rechazo del gate cuesta aproximadamente un capítulo
entero**.

### Lo lento

Las cinco llamadas más lentas son cuatro `redactar-capitulo` y un
`revisar-capitulo`, entre 247 y 303 segundos. La del escritor se explica por lo
que tiene que hacer: 1.800 palabras de prosa. La del validador de continuidad
del capítulo 6 tardó 274 segundos con 62.195 tokens, que es el paquete más
grande de la novela contra el canon más lleno. Ninguna duración pide
explicación.

### Propuestas

Ninguna toca el diseño todavía, y eso es deliberado: **una sola pasada, y
contaminada por el cambio de modelo, no basta para mover un umbral.**

| Propuesta | Qué costaría | Qué daría |
|---|---|---|
| Escribir la siguiente novela entera en haiku sin tocar nada más | Nada: ya está puesto | La comparación limpia que esta pasada no puede dar. Es el prerrequisito de todo lo demás |
| Dar precio a `claude-opus-5[1m]` en la lista de modelos de Langfuse | Un formulario | Que el total deje de estar subestimado en una cantidad desconocida |
| Que el informe cruce rol × modelo | Unas 20 líneas en `novela/informe.py` | Que la próxima pasada no tenga que calcularlo a mano, como ha tenido que hacer esta |
| Bajar `media_minima` de 3,7 | — | **No.** El margen más estrecho fue 0,30 y los dos rechazos tenían incidencia grave con nota 1. No hay evidencia de que el umbral esté apretando |

**Para DA-06**, que es quien pedía estos datos: con seis capítulos y un solo
régimen de modelo comparable, la distribución de medias (5,0 / 5,0 / 4,0 / 4,67 /
4,67 / 4,33) está muy por encima de 3,7 y no dice si el umbral está bien puesto o
si simplemente el sistema no produce capítulos mediocres. **Sigue abierta y hace
falta al menos otra novela.**
