# Spec inicial

Qué se decidió construir y por qué, **antes de escribir una línea de código**.
Es el resumen de la primera versión de la spec del backend, escrita el
21 de septiembre de 2026 sobre la ontología, la arquitectura y el reparto de la
verificación que ya estaban en `docs/`. El texto entero sigue en el historial:

```sh
git show 6c9dc20:specs/SPEC1.md
```

La spec viva, que dice cómo tiene que ser el sistema ahora, es otra cosa: está
en `specs/` y ha crecido con cada cambio. Esta página no la sigue: fija el
punto de partida para que se pueda comparar con él.

## El problema

Una persona encarga una novela histórica con un brief: época, premisa y, si es
un regalo, quién la recibe y qué recuerdos suyos tienen que aparecer. Escribir
eso con un solo modelo de lenguaje falla de tres maneras conocidas: la novela
no cabe en su contexto, el modelo se contradice entre capítulos sin darse
cuenta y, si él mismo revisa lo que escribe, da por bueno su propio error.

## Lo que se decidió construir

Un backend que hace **tres cosas y ninguna más**: guarda y sirve artefactos,
camina un guion encargando tareas a agentes dentro de un presupuesto de
contexto, y expone por HTTP lo que el editor necesita ver. **No decide nada del
dominio**: no resume, no juzga texto, no pliega el estado. Eso lo hacen los
roles del censo, entonces once. Si el servidor empieza a interpretar el
contenido de un artefacto, está reapareciendo el *harness* a medida que el
proyecto prohíbe.

La medida de «terminado» era una sola: **una obra corre de la primera orden al
último capítulo cerrado sin que nadie toque nada por dentro**.

## Las restricciones de partida

Heredadas de `AGENTS.md` y no negociables: tres capas disjuntas (Obra, Mundo,
Producción); un rol, una tarea; ningún agente valida su propia salida; el mundo
solo cambia por `EventoEstado` del Contable al cerrar capítulo; el estado se
deriva plegando el log; solo el Documentalista escribe `Fuente`; toda `Crítica`
lleva evidencia; y el techo de 100 000 tokens de contexto concurrente. Pila:
Python con FastAPI y SQLite con extensión vectorial.

## Los objetivos, con la línea base declarada pendiente

No había código, así que ninguna línea base se inventó: todas quedaron
«pendiente de medir» hasta la primera obra completa.

| ID | Objetivo | Meta de diseño |
| --- | --- | --- |
| OBJ-01 | Caber en el techo | Pico ≤ 100 000 tokens, habitual ≤ 80 000 |
| OBJ-02 | Coste plano por capítulo | Capítulo 40 ≤ 1,2 × capítulo 4 |
| OBJ-03 | Que el bucle converja | ≥ 90 % de escenas aceptadas en ≤ 2 vueltas |
| OBJ-04 | Críticas utilizables | < 10 % descartadas por falta de evidencia |
| OBJ-05 | Artefactos bien formados | ≤ 1 rechazo por capítulo |
| OBJ-06 | Cobertura documental | ≥ 90 % de afirmaciones históricas con `Fuente` |
| OBJ-07 | Cero intervención | Exactamente 1 orden humana por obra |

Y lo que **no** era objetivo, a propósito: bajar el coste por sí solo (se
cumple con un modelo peor), bajar el número de críticas (se cumple con
verificadores ciegos) y la nota de un juez de rúbrica (ruido, no mejora).

## Las cinco decisiones de la primera versión

| ID | Decisión | Por qué |
| --- | --- | --- |
| D-01 | El artefacto es un documento declarativo; el backend no lo tipa por dentro | Quien impone la forma es el esquema que ve el agente, no una clase de Python |
| D-02 | Todo se guarda en SQLite y en ningún otro sitio | Un segundo sitio sería un segundo escritor y rompería la frontera única |
| D-03 | El prompt y el contrato de cada rol viven juntos, en `tareas/<tipo>/` | Declarar un rol es añadir una carpeta: la regla «un rol, una tarea» se ve en el árbol |
| D-04 | Una sola orden por obra, y cada obra en su propio espacio | No hay nada que archivar ni vaciar entre obras |
| D-05 | Sin herramientas externas de cálculo | Decisión abierta; mientras tanto, la coherencia temporal se comprueba contra el dato ya escrito |

## Qué quedó fuera

La interfaz web, varios usuarios, varias obras a la vez, calibrar los topes de
ventana contra trazas reales —no existían— y compactar los materiales que
crecen con la obra.

## Los criterios de aceptación

1. Una obra de tres capítulos corre de `POST /obras` a obra cerrada con una
   sola llamada de escritura.
2. La `Traza` permite calcular OBJ-01 a OBJ-06.
3. Casos sembrados con un defecto de una sola dimensión miden detección y
   falsos positivos.
4. Un artefacto malformado a propósito produce una `Crítica` bloqueante.
5. Detener y reanudar a mitad de capítulo no duplica ni pierde trabajo.
6. Regenerar un capítulo intermedio deja los siguientes consistentes.

## Lo que la spec dejó abierto

Si los prompts viven en el backend o aparte (propuesta D-03), qué severidad
dispara regeneración frente a revisión, si se acepta alguna herramienta
externa de cálculo, con qué contador se miden los tokens, cada cuántos
capítulos se audita la obra y qué modelo de embeddings indexa las fuentes.
Cómo se cerró cada una está en [`trade-offs.md`](trade-offs.md) y, lo que
sigue abierto, en [`architecture.md`](architecture.md) §8.
