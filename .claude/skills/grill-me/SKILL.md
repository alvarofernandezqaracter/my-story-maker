---
name: grill-me
description: Interroga al usuario sobre el porqué de un cambio que acaba de pedir, antes de ejecutarlo. Úsala cuando el usuario pida una edición cuya motivación no sea evidente, al abrir una especificación, o cuando él la invoque por nombre. No es para tareas de ejecución mecánica.
license: MIT
metadata:
  proyecto: my-story-maker
  reutilizable: "sí; no nombra nada de este repositorio y sirve igual en cualquier otro"
  la_invoca: "AGENTS.md, fase 1 del ciclo de edición, y el comando /ciclo"
---

# grill-me — interrogatorio previo a un cambio

El usuario no quiere un colaborador que ejecute la orden y punto. Quiere que,
ante una petición de cambio, se le pregunte primero **qué problema real está
intentando resolver y por qué esa solución y no otra**, y que su respuesta quede
registrada como justificación del cambio.

El interrogatorio no es burocracia: sirve para que una petición mal planteada se
detecte **antes** de escribir código, no después.

## Cuándo se lanza

- Al abrir una especificación de un cambio, siempre.
- Ante cualquier petición cuya motivación no se deduzca del propio mensaje.
- Cuando el usuario la invoca por nombre.

No se lanza para ejecutar algo ya decidido y justificado, ni para tareas
mecánicas (formatear, renombrar lo que él mismo acaba de nombrar, repetir un
comando). Una vez la justificación está clara, se ejecuta sin volver a
discutirla.

## Cómo se hace

Antes de preguntar, **lee el código y los documentos afectados**. Una pregunta
cuya respuesta está en el repositorio quema el turno del usuario. El objetivo no
es que él te explique el sistema: es que te explique su decisión.

Después lanza **de una sola vez, con `AskUserQuestion`, entre dos y cuatro
preguntas**, nunca una encuesta larga ni un goteo de mensajes. Cada pregunta
lleva opciones concretas y plausibles, no genéricas: el usuario debe poder
responder eligiendo, y ampliar solo si quiere.

## Qué preguntar

Elige las que de verdad estén abiertas. Descarta las que la petición ya
responde.

| Eje | Lo que busca |
| --- | --- |
| **Problema** | ¿Qué pasa hoy que no debería? Si no hay síntoma, puede que no haya cambio que hacer. |
| **Alternativa** | ¿Qué otra solución descartó y por qué? Si no consideró ninguna, es señal de que la primera idea se ha convertido en el plan. |
| **Coste de no hacerlo** | ¿Qué ocurre si esto se queda como está? Separa lo urgente de lo que apetece. |
| **Señal de éxito** | ¿Cómo sabremos que ha funcionado? Si no hay forma de notarlo, el cambio no tiene criterio de cierre. |
| **Choque** | ¿Qué regla, decisión o invariante existente contradice esta petición? Esta es la pregunta más valiosa y la que más se olvida. |
| **Alcance** | ¿Dónde termina el cambio? Lo que queda fuera importa tanto como lo que entra. |

## Después del interrogatorio

- **Si la razón no sostiene el cambio, dilo.** Señalar una tensión de diseño
  vale más que dar la razón. Un paso manual o una limitación que un documento
  declara y justifica es candidato a desaparecer, no algo que se obedezca en
  silencio.
- **Registra las respuestas** en el documento del cambio, en prosa breve: el
  problema, la alternativa descartada y el porqué. Esa es la justificación del
  cambio y sobrevive a la conversación.
- **No repitas el interrogatorio** más adelante en el mismo cambio.
