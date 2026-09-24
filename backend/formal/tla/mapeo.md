# El modelo TLA+ del flujo y el código que lo implementa

`Produccion.tla` es el flujo de producción de una obra como máquina de estados
(SPEC1 §4.17). Este documento dice **qué función del código implementa cada
acción** del modelo (RF-163), qué deja fuera el modelo y cómo se lanza TLC.

La correspondencia se sostiene por revisión, no se demuestra: si cambia una
función de la tabla, hay que revisar su acción y volver a pasar TLC.

## Cómo se lanza

TLC no es dependencia del paquete (D-69). Hace falta Java 11 o posterior y
`tla2tools.jar`, los dos fuera del repositorio. En la máquina de desarrollo:

| Pieza | Versión | De dónde |
| --- | --- | --- |
| JDK | Eclipse Temurin 21.0.12.1+1, zip portable | `https://api.adoptium.net/v3/binary/latest/21/ga/windows/x64/jdk/hotspot/normal/eclipse` |
| `tla2tools.jar` | Asset de la release `v1.8.0` de tlaplus; se anuncia como `TLC2 Version 2026.09.23.154203 (rev: 4260e47)` | `https://github.com/tlaplus/tlaplus/releases/download/v1.8.0/tla2tools.jar` |

Desde la batería, sin gastar (RF-168):

```sh
export NOVELA_TLA2TOOLS=/ruta/a/tla2tools.jar   # y JAVA_HOME, o java en el PATH
python -m pytest tests/test_flujo_formal.py
```

Si falta Java o el jar, la prueba se salta y dice qué falta. A mano, desde esta
carpeta, con los ficheros de trabajo de TLC fuera del repositorio (RD-08):

```sh
java -XX:+UseParallelGC -cp "$NOVELA_TLA2TOOLS" tlc2.TLC -workers auto \
     -noGenerateSpecTE -metadir "$(mktemp -d)" -config Produccion.cfg Produccion.tla
```

Lo que tiene que decir al final es `Model checking completed. No error has been
found.`

## Qué comprueba TLC

| Propiedad | Clase | Qué dice | De dónde sale |
| --- | --- | --- | --- |
| `PuertaRespetada` | Seguridad (una de las tres) | Toda versión del registro de publicaciones terminó y pasó la puerta | RF-116, RF-146 |
| `AnteriorIntacta` | Seguridad (una de las tres) | Lo que ve una versión terminada es lo mismo que veía al terminar | RF-114 |
| `UnaSolaProduccion` | Seguridad (una de las tres) | Toda versión salvo la última está terminada, y como mucho un caminante trabaja | D-40, RF-166 |
| `NiDuplica` | Seguridad, auxiliar | Lo vivo de un capítulo es de una sola producción | RF-92, RF-165 |
| `NiPierde` | Seguridad de acción, auxiliar | Un capítulo cerrado sigue cerrado salvo que una versión nueva lo releve | RF-92 |
| `NoEscribeEnTerminada` | Seguridad de acción, auxiliar | Ningún artefacto nuevo nace en una versión que ya terminó | RF-114 |
| `TypeOK` | Tipos, auxiliar | Cada variable en su dominio; el intento nunca pasa del tope `R` | RF-95 |
| `AcabaTerminadaODetenida` | Vivacidad | Toda versión en producción acaba terminada o la obra detenida | RF-162, RF-167 |

Hipótesis de la vivacidad, escritas en `Fairness`: equidad débil del paso del
caminante que trabaja y del arranque del backend tras una caída; caídas finitas
(`MaxCaidas`). El editor —detener, reanudar, rehacer, cambiar un hecho,
publicar— y los fallos no deben nada.

## Acción por acción

Rutas relativas a `backend/src/novela/`.

| Acción del modelo | Qué es | Código |
| --- | --- | --- |
| `Init` | Alta: la obra, su versión 1 y el primer caminante | `api/aplicacion.py:crear_aplicacion.lanzar_obra` → `almacen/artefactos.py:Almacen.crear_obra` (con `_dar_de_alta`) y `api/aplicacion.py:Produccion.arrancar` |
| `Arrancar` | Arrancar: leer el hilo anterior y registrar el nuevo, que hace `join` del anterior, bajo cerrojo. Los hilos forman una cola: `cam` es el que trabaja y `esperan` cuenta los demás | `api/aplicacion.py:Produccion.arrancar` (`_turno_de_arranque`) |
| `Acabar` | El hilo que trabaja acaba y el siguiente de la cola empieza | Fin de `caminar` dentro de `Produccion.arrancar` (`Thread.join`) |
| `Volver` | Volver al punto de guardado. Lo descartado se olvida en vez de guardarse caducado, porque ninguna versión lo ve | `nucleo/caminante.py:Caminante.volver_al_punto_de_guardado` → `almacen/artefactos.py:Almacen.cerrar_trazas_interrumpidas`, `ultimo_capitulo_cerrado`, `descartar_desde` (`_marcar_desde`) e `indice.py:Indice.retirar_desde`. El modelo descarta lo de todo capítulo no cerrado (RF-165). En esta rama el código descarta lo posterior al último cerrado, que es lo mismo mientras no haya regeneración del lector. **Llega con T14 al fusionar** (su RF-176): `volver_al_punto_de_guardado` con `Almacen.capitulos_cerrados` y `Almacen.descartar_sin_cerrar` en lugar de `descartar_desde`, que es lo que el modelo describe |
| `Intento` con `tarea = "poblar"` | `poblar_mundo` si no hay biblia: nacen las fichas de los hechos | `nucleo/caminante.py:Caminante.caminar_obra` → `_fuera_del_guion("poblar_mundo")` |
| `Elegir` | Lo cerrado no se repite | `nucleo/caminante.py:Caminante.caminar_obra` (bucle) y `_ya_cerrado` |
| `Intento` | Un intento de la tarea en curso, y lo que manda su `al_agotarse` | `nucleo/caminante.py:Caminante._mandar` (bucle de intentos) y `_agotado`; tope y política de `nucleo/guion.toml` leídos por `nucleo/guion.py:_politica` |
| `Intento`, rama `detenida` | La orden de detener se nota antes de mandar | `nucleo/caminante.py:Caminante._parar_si_detenida` y `ProduccionDetenida` recogida en `caminar_obra` |
| `Intento`, `tarea = "planificar"` | Paso 1: nace el trabajo del capítulo | `nucleo/caminante.py:Caminante.caminar_capitulo` (paso 1) |
| `Intento`, `tarea = "cribar"` | Pasos 2 a 8 que no producen testigo nuevo: `documentar` (`seguir`) y las cribas (`critica_abierta`) | `nucleo/caminante.py:Caminante.caminar_capitulo` (pasos 2 a 8), `_criba`, `_critica_no_comprobado` |
| `Intento`, `tarea = "plegar"` | Pasos 9 y 10, aplazados hasta el cierre | `nucleo/caminante.py:Caminante.caminar_capitulo` (pasos 9 y 10, con `aplazados`) |
| `Cerrar` | El punto de guardado: una sola transacción | `almacen/artefactos.py:Almacen.cerrar_capitulo` |
| `AudCheck` | ¿Toca auditar? | `nucleo/caminante.py:Caminante._auditar_si_toca` |
| `Intento`, `tarea = "auditar"` | `auditar`, fuera del guion | `nucleo/caminante.py:Caminante._fuera_del_guion("auditar")` |
| `GuardarAud` | Críticas, constancia y marca de terminada juntas; la puerta queda fijada | `almacen/artefactos.py:Almacen.guardar_auditoria(de_cierre=True)` |
| `Fin` | El caminante acaba | Salida normal de `Caminante.caminar_obra` |
| `FalloNoPrevisto` | Una excepción que no es de ninguna tarea detiene la obra con su motivo | `nucleo/caminante.py:Caminante.caminar_obra` (`except Exception`) → `Almacen.detener` |
| `Caida` | El proceso muere: todos los hilos con él | No es código: es la máquina |
| `ArrancarBackend` | Relanzar lo no detenido ni terminado, antes de servir peticiones | `api/aplicacion.py:crear_aplicacion.ciclo` → `Produccion.relanzar_las_caidas` y `Produccion.terminada` |
| `Detener` | Orden del editor | `api/aplicacion.py:crear_aplicacion.detener` → `Almacen.detener` |
| `Reanudar` | Orden del editor | `api/aplicacion.py:crear_aplicacion.reanudar` → `Almacen.reanudar` y `Produccion.arrancar` |
| `AbrirVersion(S)` | Versión nueva que reescribe `S`, relevando lo que colgaba de `S` | `almacen/artefactos.py:Almacen.abrir_version` (`_marcar_desde` con `relevo`) |
| `Rehacer(n)` | Rehacer desde N | `api/aplicacion.py:crear_aplicacion.rehacer` → `nucleo/versiones.py:rehacer_desde` → `Almacen.abrir_version`; después `Produccion.arrancar` |
| `CambioLector(h)` | Regeneración por cambio del lector: `S` son los capítulos de las `Mencion` del hecho en la última versión; se relevan lo de `S` y la ficha vieja, nace la ficha nueva en la versión nueva, la constancia de auditoría baja por debajo del primer capítulo de `S` y arranca la producción | **Llega con T14 al fusionar** (SPEC1 §4.18): `POST /obras/{id}/cambios` → `nucleo/versiones.py:cambiar_hecho` → `almacen/artefactos.py:Almacen.abrir_version_por_cambio`; `S` sale de `Almacen.capitulos_de_uso`. La ficha nueva lleva `sustituye` y la escribe el backend en la misma transacción (D-72 de T14). Si ningún capítulo usa el hecho responde 409 y no nace versión (D-73 de T14): en el modelo la acción no está habilitada con `S` vacío. El 404 de un hecho que no existe y el 422 de un nombre vacío o igual no cambian el estado y no se modelan |
| `Publicar(v)` | Publicar pasando por la puerta | `api/aplicacion.py:crear_aplicacion.publicar` → `nucleo/versiones.py:publicar` → `nucleo/versiones.py:puerta` → `Almacen.publicar_version`. **Llega con T10 al fusionar**: `puerta(..., demostrador=None)` suma el validador `cronologia` con Lean y `publicar` devuelve `(publicada_en, comprobacion)`. Para el modelo, `comprobada` y `sin_comprobacion` (Lean no instalado) son «pasa», y `fallida` es «no pasa»: no se publica y se escriben las críticas de `_criticas_de_la_cronologia`, que el modelo no distingue |
| `Visible(v)`, `Vivas` | Lo que ve cada versión; lo vivo es lo que lee la producción | `almacen/artefactos.py:_visible` |
| `Usos(v, h)` | En qué capítulos se usa un hecho | `almacen/artefactos.py:Almacen.capitulos_de_uso` |
| `Produciendo` | ¿Hay producción en marcha? (el último hilo registrado vive) | `hilo.is_alive()` en `api/aplicacion.py:crear_aplicacion.rehacer` |
| `Terminada` | Obra terminada: consta la auditoría de cierre | `api/aplicacion.py:Produccion.terminada` y `Almacen.auditada_hasta` |

## Lo que el modelo deja fuera (D-66)

- **El contenido.** Un artefacto es un registro con su capítulo, su tipo, la
  producción que lo escribió, sus marcas de versión y caducidad y los hechos
  que menciona. No hay texto, escenas ni fichas.
- **El bucle de calidad dentro del capítulo.** Las regeneraciones y revisiones
  de los pasos 4 a 6 tienen sus topes probados aparte (RF-33); aquí la criba es
  una tarea que sale bien o se agota.
- **Las tandas, el presupuesto y el índice de parecido.** El índice es derivado
  y se rehace al volver al punto de guardado.
- **La memoria de capítulo.** Retirarla al cerrar no cambia lo que ve ninguna
  versión de lo que el modelo distingue.
- **La puerta por dentro.** Un veredicto que pasa o no pasa, fijado al terminar
  la versión (D-67): cubre los cuatro validadores de hoy y el formal de la
  historia de T10 —también cuando Lean no está y la versión se publica marcada
  «sin comprobación formal», que para el flujo es «pasa»—.
- **Varias obras.** El modelo es de una (§11).
- **La ficha por dentro.** Una ficha es un registro sin capítulo con el hecho
  que describe; su valor no se modela, solo que la de la versión nueva
  sustituye a la vieja sin que la vieja deje de verse en su versión.
- **La identidad de cada producción.** Un artefacto `trabajo` lleva en `n`
  cuántas producciones vivas de su capítulo había al escribirlo; `n = 2` es
  justo el duplicado que `NiDuplica` prohíbe.

## El tamaño del modelo

`Produccion.cfg` es el modelo que TLC recorre entero y el que lanza la prueba:
tres capítulos, dos versiones, `R = 2`, un hecho, una caída, un reanudar y un
fallo no previsto. En la máquina de desarrollo, con cuatro núcleos, son
1 596 100 estados generados, 437 197 distintos y una profundidad de 59, en unos
tres minutos.

Que el modelo no pase por no llegar a nada se comprobó aparte, con invariantes
testigo que tienen que fallar: TLC encuentra una versión del lector que se
produce, sufre una caída y termina, y otra que se publica, las dos a
profundidad 39.

Con tres versiones el modelo pasa de varios millones de estados distintos y
TLC tarda más de lo que una batería aguanta: no se da por comprobado.

## Contraejemplos

Cada uno, con su traza literal y su explicación, en `contraejemplos/`:

| # | Propiedad que rompió | Qué cambió |
| --- | --- | --- |
| 01 | `UnaSolaProduccion`: dos `reanudar` a la vez dejaban dos caminantes | Cerrojo en `Produccion.arrancar` (RF-166) |
| 02 | `AcabaTerminadaODetenida`: un fallo no previsto dejaba la obra sin hilo, sin detener y sin terminar | `caminar_obra` detiene la obra con su motivo (RF-167) |
| 03 | `NiDuplica`: con la regeneración del lector, una caída duplicaba el capítulo reescrito | Requisito para §4.18: descartar lo de todo capítulo no cerrado (RF-165), que T14 implementa como su RF-176 |
