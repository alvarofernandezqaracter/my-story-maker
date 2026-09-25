# Salidas estructuradas

**La idea.** Si lo que devuelve un agente es texto libre, el siguiente tiene que
interpretarlo. Si es un objeto con una forma declarada, se puede comprobar sin
leerlo.

**Cómo se aplica aquí.** Cada tarea tiene un `esquema.json` con ejemplos de lo
que debe devolver: un objeto JSON con su lista de artefactos, cada uno con su
tipo y su cuerpo. Los valores cerrados —estados, severidades, dimensiones— son
vocabularios controlados, y la propia base de datos rechaza uno que no exista.
El backend no interpreta el cuerpo: solo comprueba la forma.

**Ejemplo.** Un campo es obligatorio si aparece en todos los ejemplos que el
esquema da de su tipo. Un `EventoEstado` de tipo `muere` no lleva `objeto`, así
que el esquema del Contable enseña dos formas de evento, una con objeto y otra
sin él.

**El límite.** Los modelos no siempre respetan la forma: ponen el JSON entre
vallas de código, con texto alrededor, o escriben `Crítica` con tilde. El
ejecutor lo lee igual; lo que no es JSON sigue siendo un intento fallido.

*Más:* [`architecture.md`](../architecture.md) §4, «Cómo se lee lo entregado».
