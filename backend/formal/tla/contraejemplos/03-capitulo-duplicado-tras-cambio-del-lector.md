# Contraejemplo 03 · El capítulo reescrito por un cambio del lector se duplica tras una caída

**Qué rompe.** El invariante auxiliar `NiDuplica` (SPEC1 RF-161, RF-92): lo
vivo de un capítulo es de una sola producción.

**Contra qué modelo salió.** El del commit `16636a5` (contraejemplos 01 y 02 ya
arreglados), con el modelo de estados reducido —las tareas `documentar` y las
cribas en una sola, un solo `reanudar`— y con `Volver` modelando lo que hace
`Caminante.volver_al_punto_de_guardado`: descartar lo que cuelga de los
capítulos **posteriores al último cerrado** (`descartar_desde(ultimo + 1)`).

**La traza, en llano** (salida literal de TLC en
[`03-capitulo-duplicado-tras-cambio-del-lector.txt`](03-capitulo-duplicado-tras-cambio-del-lector.txt),
33 estados):

1. Estados 1 a 24: la versión 1 se produce entera. Al cerrar el capítulo 1 el
   Archivero anota que menciona el hecho `h1`; los capítulos 2 y 3 no lo
   mencionan. La auditoría de cierre termina la versión.
2. Estado 25: el lector cambia `h1`. Nace la versión 2, que reescribe solo el
   capítulo 1 —el único que usa el hecho—; el 2 y el 3 se comparten.
3. Estados 26 a 28: el caminante vuelve al punto de guardado, elige el capítulo
   1 y lo planifica: nace trabajo de la producción 4.
4. Estado 29: el proceso se cae.
5. Estados 30 a 33: el backend vuelve y relanza la obra. Al volver al punto de
   guardado, el último capítulo cerrado es **el 3**, así que descarta lo
   posterior al 3, que es nada. El trabajo a medias del capítulo 1 sigue vivo,
   el caminante lo vuelve a planificar encima y el capítulo 1 queda con lo de
   dos producciones: escenas y borradores duplicados.

**Por qué no se ve hoy.** Rehacer desde N reescribe de N al final, así que los
capítulos cerrados de la versión en curso son siempre 1..último y «posterior al
último cerrado» es lo mismo que «no cerrado». La regeneración por cambio del
lector (RF-164) reescribe capítulos sueltos y rompe esa igualdad: basta un
capítulo que no sea el último.

**Qué cambió.** El commit que guarda esta traza:

- En la spec: SPEC1 RF-165. Lo que se descarta al volver al punto de guardado
  es lo que cuelga de todo capítulo que no está cerrado en la versión en curso,
  y los fragmentos del índice igual.
- En el modelo: `Descartar` marca lo vivo de todo capítulo no cerrado.
- En el código: nada todavía. Mientras no exista la regeneración del lector,
  los dos criterios coinciden en todo estado alcanzable y el código de hoy
  cumple RF-165. Implementarlo va con la regeneración, en §4.18 (**pendiente
  de T14**), que además tiene que relevar por conjunto de capítulos y no por
  «desde N».
