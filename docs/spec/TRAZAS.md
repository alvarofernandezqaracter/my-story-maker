---
doc: spec-analisis-de-trazas
version: 0.1.0
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

## §5 Pasadas de análisis

Todavía ninguna. La primera irá aquí, como §6.
