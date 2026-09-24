# Contraejemplo 01 · Dos caminantes sobre la misma obra

**Qué rompe.** El invariante `UnaSolaProduccion` (SPEC1 RF-161): como mucho un
caminante trabaja la obra.

**Contra qué modelo salió.** El del commit `845faf6` («formal: modelo TLA+ del
flujo tal como esta el codigo»), que modela `Produccion.arrancar` tal como
estaba: leer el hilo anterior (`self.hilos.get(id_obra)`) y registrar el nuevo
(`self.hilos[id_obra] = hilo`) eran dos pasos sin cerrojo. En el modelo, la
lectura queda en `pets` y el registro es la acción `Registrar`.

**La traza, en llano** (salida literal de TLC en
[`01-dos-caminantes.txt`](01-dos-caminantes.txt), seis estados):

1. La obra se da de alta y su caminante, el hilo 1, arranca.
2. El editor pulsa «reanudar». La petición lee que el hilo anterior es el 1.
3. El editor vuelve a pulsar «reanudar» antes de que la primera termine —un
   doble clic—. La segunda petición también lee que el anterior es el 1.
4. La primera registra su hilo, el 2, que espera a que acabe el 1.
5. La segunda registra el suyo, el 3, que **también** espera al 1, no al 2.
6. El hilo 1 acaba —en la traza por un fallo no previsto; da igual cómo: la
   detención o el final valen lo mismo— y los hilos 2 y 3 arrancan a la vez.
   Dos caminantes vuelven al punto de guardado y producen el mismo capítulo, y
   cada uno descarta lo que el otro escribe.

**Por qué pasa en el código de verdad.** Las rutas de FastAPI son funciones
síncronas y corren en un grupo de hilos: dos `POST /reanudar` seguidos se
atienden a la vez. `reanudar` y `rehacer` llaman a `arrancar`.

**Qué cambió.** El commit que guarda esta traza:

- En el código: `Produccion.arrancar` lee el anterior y registra el nuevo bajo
  un cerrojo, `Produccion._turno_de_arranque` (`backend/src/novela/api/aplicacion.py`).
- En la spec: SPEC1 RF-166.
- En el modelo: `CrearHilo(ultimo)` es una sola acción; desaparecen `pets` y
  `Registrar`.
- En las pruebas: `test_dos_arranques_a_la_vez_no_dejan_dos_caminantes`
  (`backend/tests/test_flujo_formal.py`), que ensancha a propósito la ventana
  entre leer y registrar: sin el cerrojo ve dos caminantes a la vez y falla;
  con él, uno.
