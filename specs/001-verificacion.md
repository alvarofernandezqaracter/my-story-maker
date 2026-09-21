---
spec: 001
titulo: Verificación — qué método le toca a cada dimensión de calidad
version: 0.1.0
estado: aprobada
fecha: 2026-09-21
fuente: hoja de referencia externa de metodologías de verificación
  (https://claude.ai/artifact/Rass3RVfaN5KSJDdG2FQhR), aportada por el editor
---

# 001 · Verificación

## §1 Problema

`docs/validators.md` está vacío desde el arranque de la rama `v2`. Mientras
tanto, `definitions.md` enumera veinte dimensiones de calidad y
`architecture.md` §5 describe el contrato de verificación en abstracto, pero
**ningún documento dice qué método le toca a cada dimensión, qué agente la
comprueba, con qué proyección ni qué se hace con las que no admiten
comprobación**. Quien implemente el bucle de calidad tiene que reinventar ese
reparto, y «coherencia de voz» acabaría tratada igual que «continuidad de
estado» cuando no son la misma clase de problema: una se puntúa, la otra se
comprueba.

Falta además el eslabón de arriba. Nada dice **cómo se comprueba que los
verificadores funcionan**. Un sistema que se valida a sí mismo sin medir su
propia tasa de acierto no es verificable: es optimista.

El interrogatorio previo lo delegó el editor: «lo que tú consideres a partir del
artifact». Las decisiones de §2 son, por tanto, propuesta del agente, y el
choque de §5 es el punto donde conviene que las mire.

## §2 Decisión

La hoja de referencia externa se usa como **taxonomía**, no como plan de
trabajo: aporta los nombres de los métodos y el marco de clasificación, y de
ella se toma solo lo compatible con los invariantes del proyecto. Se aterriza en
dos piezas.

**Una skill, `disenar-verificacion`**, en `.claude/skills/` del repositorio.
Ante una dimensión de calidad o un requisito nuevo obliga a recorrer cuatro
pasos en orden: clasificar el método, comprobar que existe un agente con la
proyección necesaria, escribir el contrato de verificación, o declarar la
dimensión inverificable y decir quién la puntúa. Lleva el catálogo traducido
como fichero de referencia.

**`docs/validators.md`**, escrito con esa skill. Contiene el reparto completo
—dimensión, método, agente, proyección mínima, severidad por defecto— y una
segunda mitad sobre la verificación del sistema que escribe la novela.

Se adopta un vocabulario controlado para `metodo_de_verificacion`, con cinco
valores: `prueba`, `analisis`, `inspeccion`, `demostracion`, `inverificable`.
Es la adaptación al dominio del marco T/A/I/D/U de la hoja de referencia. Sin
él, «validar» significa lo mismo cuando se comparan dos fechas ya escritas que
cuando se juzga si una voz suena a la misma persona, y son trabajos con
fiabilidades muy distintas.

**Alternativa descartada:** escribir `validators.md` como lista plana de
comprobaciones sin clasificarlas. Se descarta porque eso es aproximadamente el
estado actual repartido entre `definitions.md` y `architecture.md`, y no
resuelve lo único que hoy no tiene respuesta: qué se hace con las dimensiones
que ningún predicado captura.

**Hallazgo con consecuencia:** el reparto obliga a separar el anacronismo en dos
agentes. El material, el conceptual y el social exigen ver el canon, que el
Editor de estilo no ve por diseño; van al Verificador de continuidad. Solo el
léxico se queda en el Editor, que sí recibe la lista vetada. «Alcance local» en
`definitions.md` describe el alcance del defecto, no el del agente que lo
encuentra.

## §3 Objetivos medibles

No hay código todavía, así que **ninguna línea base es real**. Se declaran como
pendientes de medir en la primera ejecución completa, que es un estado honesto y
preferible a inventar el número. La meta se fija cuando exista la base.

| Métrica | Cómo se mide | Línea base | Meta |
| --- | --- | --- | --- |
| Tasa de detección por dimensión | Casos sembrados: un capítulo con un defecto conocido por dimensión; se cuenta si el agente responsable lo señala | Pendiente | Por fijar tras medir |
| Falsos positivos por capítulo | `Crítica` emitida cuya evidencia no sostiene el defecto al revisarla | Pendiente | Por fijar tras medir |
| Críticas descartadas sin evidencia | Proporción sobre el total emitido, ya prevista en `architecture.md` §5 | Pendiente | Por fijar tras medir |
| Iteraciones hasta `Aceptado` | Recuento por capítulo en la `Traza` | Pendiente | Por fijar tras medir |
| Coste de la verificación | Tokens gastados por los agentes que critican, sobre el techo de 100 000 por ejecución | Pendiente | ≤ 30 % del techo |

**Qué no es un objetivo.** Bajar el número de críticas emitidas. Se cumple
trivialmente haciendo peor al Verificador, y arruinaría la única métrica que
mide si el sistema detecta algo. El orden importa: la tasa de detección va
primera porque, sin ella, las otras cuatro miden un bucle que puede estar
girando en vacío.

## §4 Fuera de alcance

- No se escriben los prompts de los diez agentes. La skill dice qué debe llevar
  un contrato de verificación; redactarlos es fase de implementación.
- No se toca el censo de agentes ni se declara ningún rol nuevo.
- No se implementa nada en `backend/` ni en `frontend/`: siguen vacíos.
- No se construye el conjunto de casos sembrados de §3; se define qué mide.
