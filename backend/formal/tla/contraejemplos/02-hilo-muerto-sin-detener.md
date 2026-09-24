# Contraejemplo 02 · Una obra ni detenida ni terminada, y sin nadie que la mueva

**Qué rompe.** La propiedad de vivacidad `AcabaTerminadaODetenida` (SPEC1
RF-162): toda versión en producción acaba terminada o la obra acaba detenida.

**Contra qué modelo salió.** El del commit `d6d61dc` (contraejemplo 01 ya
arreglado), en el que `FalloNoPrevisto` modela lo que hacía
`Caminante.caminar_obra`: solo recogía `ProduccionDetenida`, así que cualquier
otra excepción subía hasta el hilo y lo mataba sin tocar nada del almacén.

**La traza, en llano** (salida literal de TLC en
[`02-hilo-muerto-sin-detener.txt`](02-hilo-muerto-sin-detener.txt)):

1. La obra se da de alta y su caminante arranca.
2. Al caminante le salta una excepción que no es de ninguna tarea. En el código
   hay varias que no pasan por los reintentos: `NoCabeNiPartiendo` cuando una
   ventana no cabe ni partiendo la unidad, `ProyeccionIncompleta` y
   `ProyeccionConMaterialDeSobra` cuando la ventana no cuadra con su contrato.
   El hilo muere.
3. «Stuttering»: no pasa nada más, para siempre. La obra no está detenida —la
   ficha no dice nada, `motivo` vacío—, no está terminada y no tiene hilo. Solo
   la movería que el editor pulsase «reanudar» o que el backend se reiniciase,
   y ninguna de las dos cosas está garantizada: es exactamente el paso manual
   que OBJ-07 y RNF-08 prohíben. Y si se reinicia, el relanzamiento vuelve a
   chocar con lo mismo.

**Qué cambió.** El commit que guarda esta traza:

- En el código: `Caminante.caminar_obra` recoge cualquier otra excepción,
  detiene la obra con el motivo «fallo no previsto del caminante: …» y la
  deja subir para que el fallo se siga viendo
  (`backend/src/novela/nucleo/caminante.py`). Una caída del proceso no es una
  `Exception` y no pasa por aquí: sigue relanzándose al arrancar.
- En la spec: SPEC1 RF-167.
- En el modelo: `FalloNoPrevisto` pone `detenida` a verdadero.
- En las pruebas: `test_un_fallo_no_previsto_detiene_la_obra_y_dice_por_que`
  (`backend/tests/test_flujo_formal.py`): sin el arreglo, la obra queda sin
  detener y la prueba falla.
