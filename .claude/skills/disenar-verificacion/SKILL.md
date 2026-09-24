---
name: disenar-verificacion
description: "Decide cómo se verifica una dimensión de calidad, un requisito o una salida de agente, y escribe el contrato de verificación correspondiente. Úsala al añadir una dimensión de calidad, al asignarle validador a algo que aún no lo tiene, al revisar si una comprobación existente es fiable, o al escribir o modificar docs/validators.md. Se dispara con: validar, verificar, validador, contrato de verificación, predicado, criterio de aceptación, cómo compruebo esto, quién valida esto, eval, falso positivo, inverificable."
license: MIT
metadata:
  proyecto: my-story-maker
  fuente: hoja de referencia externa de metodologías de verificación
---

# Diseñar la verificación de algo

Esta skill existe para impedir el fallo más común al verificar un sistema
generativo: **tratar como comprobable lo que solo se puede opinar**. Un número
del 1 al 10 puesto por un modelo sobre «la calidad del ritmo» parece una
medida y no lo es; un «¿la fecha de salida es posterior a la de llegada?» sí lo
es. Confundirlos hace que el bucle de revisión gire sin converger y que nadie
se entere.

El catálogo completo de metodologías, con su definición y su referencia, está en
[references/metodologias.md](references/metodologias.md). Léelo cuando dudes de
qué método existe; esta página dice cómo elegir entre ellos.

## Los cinco métodos

Vocabulario controlado. Todo lo que se verifica lleva exactamente uno de estos
cinco valores en `metodo_de_verificacion`. Es la adaptación al dominio del marco
T/A/I/D/U (test, analysis, inspection, demonstration, unverifiable) de la hoja
de referencia.

| Valor | Qué significa aquí | Fiabilidad |
| --- | --- | --- |
| `prueba` | Se prepara un caso con resultado conocido y se comprueba si el sistema lo acierta. Es lo que se hace con los propios verificadores | Alta, pero solo sobre los casos preparados |
| `analisis` | Se comparan datos ya escritos sin releer el texto: dos fechas, un estado plegado contra otro, una cuenta sobre un registro acumulado | Alta si el dato de partida es fiable |
| `inspeccion` | Un agente lee el texto y responde si un predicado se cumple, citando el fragmento exacto | Media: depende de la proyección que reciba |
| `demostracion` | Se deja correr el sistema entero y se comprueba el resultado agregado al final, no paso a paso | Baja para localizar la causa, alta para detectar que algo va mal |
| `inverificable` | No hay predicado posible. Se puntúa con rúbrica y se marca como ruido, o se declara fuera de alcance | Ninguna: no se enruta por severidad como si fuera un defecto |

La regla que hace útil el vocabulario: **`inverificable` es una respuesta
legítima y frecuente**. Declararlo vale más que fabricar un predicado falso.

## El procedimiento

Cuatro pasos, en orden. No saltes el tercero: es donde se cae la mayoría de las
verificaciones que parecen bien diseñadas.

### 1 · Enuncia el predicado en una frase

Una frase que solo pueda ser cierta o falsa, sobre entidades de la ontología, no
sobre impresiones. «El ritmo es bueno» no es un predicado. «La proporción de
párrafos en modo `sumario` está dentro de la banda declarada para el capítulo»
sí lo es.

Si no consigues escribir la frase, el método es `inverificable`. Para ahí y
pasa al paso 4.

### 2 · Clasifica el método

Pregunta en este orden y quédate con la primera respuesta afirmativa:

1. ¿Se resuelve comparando datos ya escritos, sin leer prosa? → `analisis`.
2. ¿Hace falta leer el texto y señalar un fragmento? → `inspeccion`.
3. ¿Solo se ve al final, sobre la obra entera? → `demostracion`.
4. ¿Ninguna? → `inverificable`.

`prueba` no aparece en esta lista porque no verifica la obra: verifica a los
verificadores. Ver «Verificar al verificador», abajo.

### 3 · Comprueba que existe un agente que puede verlo

Este paso es el que se olvida. Busca en el censo de `architecture.md` un agente
cuya proyección **ya contenga** todo lo que el predicado necesita. Si el
predicado exige el canon y el único agente con esa tarea no ve el canon por
diseño, la verificación no es implementable tal como está enunciada.

Cuando eso pase, en este orden:

1. ¿Otro agente del censo tiene la proyección adecuada? Asígnasela a él, aunque
   el defecto sea de alcance local: el alcance describe dónde está el defecto, no
   quién lo encuentra.
2. ¿Ninguno? Entonces hay trabajo que ningún tipo de tarea cubre. **Propón un
   rol nuevo y para**; no ensanches la proyección de un agente existente para
   que le quepa, porque eso rompe el invariante de un rol, una tarea.

Recuerda también la regla de una dimensión por tarea: un agente al que se le
piden siete comprobaciones a la vez encuentra las dos primeras.

### 4 · Escribe el contrato, o declara el ruido

Si el método es `analisis`, `inspeccion` o `demostracion`, el resultado es un
contrato de verificación con exactamente tres partes:

- **Predicado** — la frase del paso 1.
- **Proyección mínima** — la lista cerrada de lo que el agente recibe. Mínima de
  verdad: lo que sobra en la proyección es lo que produce falsos positivos, y
  ver la prosa anterior ancla al verificador en los fallos que esa prosa ya
  contenía.
- **Forma de la `Crítica`** — qué entidad va en `objeto`, qué `dimension`, qué
  `severidad` por defecto y qué cuenta como `evidencia` citable. Sin evidencia
  la crítica se descarta antes de llegar al Revisor, así que el contrato tiene
  que decir qué evidencia es aceptable.

Si el método es `inverificable`, el resultado es otra cosa: la rúbrica que
usará el Juez, la nota de que su salida es ruidosa y se marca aparte, y la
prohibición de que dispare regeneración por sí sola.

## Verificar al verificador

Un verificador sin medida de acierto es una opinión con formato de tabla. Lo que
cierra el círculo es `prueba`: **casos sembrados**, un texto con un defecto
conocido de una sola dimensión, y la comprobación de si el agente responsable lo
señala. Un caso por dimensión y por severidad es suficiente para empezar.

Tres señales de que una verificación está mal diseñada, todas observables en la
`Traza`:

- **No encuentra nada nunca.** Casi siempre es una proyección que no contiene el
  dato necesario, no un texto impecable.
- **Encuentra algo siempre.** Predicado demasiado vago, o proyección con
  material de sobra que invita a opinar.
- **Dos agentes discrepan de forma sistemática en la misma dimensión.** No se
  arregla con un desempate: significa que el predicado no es uno solo.

## Qué no traer de la ingeniería de software

La hoja de referencia incluye métodos que verifican código y no se aplican al
texto de una novela: comprobación de tipos, análisis estático, ejecución
simbólica, verificación formal, comprobación de modelos, pruebas de mutación.
No los propongas como validadores de la obra. Sí valen —y valdrán— para el
código del servidor y de la interfaz cuando exista, que es otro nivel de
verificación y está descrito en la segunda mitad de `docs/validators.md`.

La frontera es fácil de recordar: **una novela no tiene especificación formal
contra la que probarse, y por eso el techo de lo comprobable está más bajo de lo
que la lista de métodos sugiere**. Diseñar la verificación consiste, en buena
parte, en decir dónde está ese techo.
