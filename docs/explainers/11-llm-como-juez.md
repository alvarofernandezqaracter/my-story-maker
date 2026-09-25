# Un modelo como juez

**La idea.** Hay cosas de la calidad de una novela que ninguna regla captura:
si funciona como novela, si lo personal está integrado. Se le puede pedir a un
modelo que las puntúe con una rúbrica, sabiendo que su nota es ruidosa.

**Cómo se aplica aquí.** Dos jueces distintos:

- **El Juez de rúbrica**, dentro del censo, puntúa la coherencia de voz de cada
  escena y capítulo. No bloquea nada.
- **El juez de la novela**, fuera del sistema: se lanza a mano sobre una
  versión terminada, con Sonnet, y puntúa tres criterios de 1 a 5 con
  justificación y citas literales. Lee todos los resúmenes y los capítulos
  enteros que quepan en 60 000 tokens.

**Ejemplo.** En el brief de ejemplo, el recuerdo de la destinataria es haber
encontrado unas llaves dentro de la nevera. Si en la novela aparece como un
pegote, `personalizacion_integrada` lo tiene que penalizar citando el pasaje.

**El límite.** La rúbrica vive solo en Langfuse y la nota no dispara nada: si el
sistema pudiera leerla o reaccionar a ella, acabaría escribiendo para complacer
al juez.

*Más:* [`trade-offs.md`](../trade-offs.md) §5 y §11.
