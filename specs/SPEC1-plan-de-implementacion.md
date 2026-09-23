---
name: SPEC1-plan-de-implementacion
titulo: Plan de implementación de SPEC1 — Backend v1
version: 1.0.0
estado: aplicado
fecha: 2026-09-22
ambito: backend/
base:
  - specs/SPEC1.md
  - docs/architecture.md
  - docs/validators.md
---

# Plan de implementación de SPEC1 — Backend v1

## Cómo se lee este plan

Diez etapas en orden, de la 0 a la 9. Cada una dice **qué queda construido**,
**qué requisitos de SPEC1 cubre** y **con qué método de `validators.md` se da por
cerrada**, con su evidencia citable. Ninguna etapa empieza hasta que la anterior
cierra.

Este plan **no decide nada que SPEC1 no haya decidido ya**. Fija detalles de
implementación —qué biblioteca, qué orden, qué fichero— y nada más. Si al
programar aparece una decisión de fondo, se para y se vuelve a la fase 1 del
ciclo de edición para ampliar la spec; no se improvisa sobre la marcha.

La medida de «terminado» sigue siendo la de SPEC1 §1.2: **una obra corre de la
primera orden al último capítulo cerrado sin que nadie toque nada por dentro**.

## El orden, y por qué es ese

```mermaid
flowchart LR
  E0[0 · Andamio] --> E1[1 · Almacen]
  E1 --> E2[2 · Nucleo]
  E2 --> E3[3 · Recorrido en seco]
  E3 --> E4[4 · Indice hibrido]
  E4 --> E5[5 · Ejecutor real]
  E5 --> E6[6 · Las once tareas]
  E6 --> E7[7 · API]
  E7 --> E8[8 · Obra de tres capitulos]
  E8 --> E9[9 · Cierre del ciclo]
```

Tres razones sostienen este orden y no otro:

- **No se llama a ningún agente real antes del recorrido en seco.** Mientras no
  exista, cualquier fallo del guion se descubre gastando (`validators.md` §6).
  La etapa 3 es la puerta.
- **La frontera se comprueba antes de que haya código que la rompa.** Los
  contratos de importación son el paso 1 del orden de adopción de
  `validators.md` §10: cuestan poco al principio y mucho al final.
- **El índice va antes que las tareas que lo consultan.** Documentalista,
  Planificador y Editor de estilo lo necesitan montado; montarlo después obliga
  a rehacer sus proyecciones.

| Etapa | Hito con el que se cierra |
| --- | --- |
| 0 · Andamio | Los contratos de importación fallan cuando deben |
| 1 · Almacén | Cada tipo de artefacto se escribe, se lee y no se puede corromper |
| 2 · Núcleo | Los diez pasos, el enrutado y la anchura de tanda, enumerados en pruebas |
| 3 · Recorrido en seco | Un capítulo entero recorrido sin gastar ni producir novela |
| 4 · Índice híbrido | Borrarlo y reconstruirlo devuelve los mismos fragmentos |
| 5 · Ejecutor real | Una tarea real ejecutada, con su `Traza` completa |
| 6 · Las once tareas | Casos sembrados, con la línea base de detección por dimensión |
| 7 · API | Brief incompleto rechazado por su nombre; detener y reanudar sin perder trabajo |
| 8 · Obra de tres capítulos | Obra cerrada con **una sola** llamada de escritura |
| 9 · Cierre del ciclo | `docs/` describe el sistema tal como quedó |

## Etapa 0 · Andamio y fronteras

**Qué queda construido.** `backend/pyproject.toml` con el paquete `novela` y el
árbol de `architecture.md` §7: `tareas/`, `nucleo/`, `almacen/` y `api/`, vacías
salvo su `__init__.py`. Las herramientas: `pytest`, `ruff`, comprobación de tipos
**solo sobre `api/`** —el único sitio con tipos declarados— e `import-linter` con
los cuatro contratos de `validators.md` §6. Y un único fichero de ajustes con lo
que hoy es configuración: ruta de la base, cada cuántos capítulos entra `auditar`
(valor de partida: solo al cierre de la obra), topes de vueltas, `k` por rol y los
topes de ventana de `architecture.md` §3, que se copian tal cual:

| Rol | Tope de ventana |
| --- | --- |
| Arquitecto de arcos | 25 000 |
| Planificador · Revisor | 20 000 |
| Constructor de mundo | 15 000 |
| Contable de estado · Archivero · Redactor | 12 000 |
| Documentalista · Verificador · Editor de estilo | 8 000 |
| Juez de rúbrica | 6 000 |

**Cubre.** RF-20, RD-09, RNF-05, RNF-07.

**Se cierra con** `analisis`: los contratos fallan si una carpeta de `tareas/`
importa otra, si algo fuera de `almacen/` importa `sqlite3`, si `nucleo/` importa
una tarea o si aparecen tipos declarados fuera de `api/`. Evidencia: la salida de
`import-linter` en verde, y en rojo sobre un fichero sembrado que rompa cada
contrato a propósito.

## Etapa 1 · El almacén

**Qué queda construido.** El esquema SQLite de las tres capas de
`architecture.md` §1 —Obra, Mundo y Producción— más la `Traza`, con toda fila
colgando de un `id_obra`. La capa Obra **referencia la capa Mundo por `id` y
nunca la duplica**, y la de Producción referencia a las dos sin que ninguna la
referencie a ella: es la regla de acoplamiento, y aquí se impone con claves
foráneas, no con buena voluntad.

Una tabla por tipo de artefacto con el cuerpo íntegro en una columna y, al lado,
solo las columnas por las que se consulta: obra, capítulo, escena, estado,
severidad, dimensión y rol, más `id` opaco, `tipo`, procedencia —rol, tarea e
intento— y sello temporal. Los tipos están todos declarados y no hay más: las
entidades de producción de `architecture.md` §2 —`Agente` y `Tarea`, de las que
sale la procedencia de todo lo demás, más `Plan`, `Borrador`, `Crítica`,
`Revisión`, `Decisión`, `EventoEstado`, `Resumen de capítulo` y `Traza`— y las de
las otras dos capas, que define `definitions.md`: `Obra`,
`Parte`, `Capítulo`, `Escena`, `Beat`, `Párrafo` y `Compromiso` en la capa Obra;
`Personaje`, `Lugar`, `Evento`, `Objeto`, `Facción`, `Práctica`, `Concepto`,
`Registro lingüístico` y `Fuente` en la capa Mundo.

Reglas que se imponen en el esquema y no en el código: tablas `STRICT`, un
`CHECK` por cada vocabulario controlado, `foreign_keys` activas, e inmutabilidad
por disparador para `EventoEstado`, `Fuente`, `Resumen de capítulo`, `Decisión` y
todo borrador ya aceptado. Los vocabularios de proceso son tres y están cerrados
en `architecture.md` §2 —cuatro severidades, cinco estados de producción y diez
tipos de `EventoEstado`—; los de forma y de mundo salen de `definitions.md`.

**No se borra nada**: caducar y descartar son marcas. Cada artefacto lleva a qué
memoria pertenece —de tarea, de capítulo o de obra (`architecture.md` §3)—,
porque es lo que permite al Archivero retirar la memoria de capítulo sin que
nadie tenga que decidirlo sobre la marcha. El estado materializado se declara
como caché descartable; regenerar el capítulo N descarta los estados de N en
adelante y repliega hacia delante.

Conexión: `WAL`, `busy_timeout` explícito, `synchronous = NORMAL`, escrituras en
`BEGIN IMMEDIATE`, un solo escritor serializado y lecturas aparte que no lo
bloquean. `almacen/` se expone como interfaz estrecha con nombres de dominio
—guardar borrador, leer capítulo, añadir eventos, listar críticas abiertas—, no
como pasamanos de SQL ni como ORM. Migraciones numeradas desde el primer día.

**Cubre.** RD-01 a RD-04, RD-06, RD-07, RD-08, RF-21 a RF-26, RNF-05, RNF-06.

**Se cierra con** `prueba` y `analisis`: escritura y lectura de cada tipo de
artefacto; un `UPDATE` sobre un inmutable falla; un valor fuera de vocabulario se
rechaza; un artefacto caducado deja de servirse a cualquier proyección; descartar
los estados materializados de N en adelante y replegar da el mismo resultado que
plegar desde cero; y ningún cuerpo de escena contiene una ficha de mundo, solo su
identificador. Evidencia: la suite del almacén, el `EXPLAIN QUERY PLAN` de cada
consulta nueva y el recuento de referencias al mundo que no son `id`. La
propiedad *semántica* del pliegue —que la ejecuta el Contable, no el almacén— se
comprueba en la etapa 6.

## Etapa 2 · El núcleo

**Qué queda construido.** El guion del capítulo como **artefacto declarativo
versionado con el repositorio**, no como código, y la pieza que lo camina, que
lee cuál es el paso siguiente y lo ejecuta sin criterio propio. Los pasos son los
diez de `architecture.md` §4, en ese orden y con esa concurrencia:

| Paso | Tarea | Rol | Concurrencia |
| --- | --- | --- | --- |
| 1 | `planificar` | Planificador | Solo |
| 2 | `documentar` | Documentalista | Uno por escena, en tanda |
| 3 | `redactar` | Redactor | Uno por escena, en tanda |
| 4 | `verificar` — criba de bloqueantes | Verificador de continuidad | Uno por dimensión y escena, en tandas |
| 5 | `revisar` | Revisor | Solo, por escena; vuelve al 4 |
| 6 | `verificar` — criba de mayores | Verificador de continuidad | Uno por dimensión y escena, en tandas |
| 7 | `editar_estilo` — costura del capítulo | Editor de estilo | Solo, sobre el capítulo entero |
| 8 | `juzgar` y `editar_estilo` — criba de pulido | Juez de rúbrica, Editor de estilo | En tanda |
| 9 | `plegar` | Contable de estado | Solo |
| 10 | `destilar` | Archivero | Solo |

Cada paso lleva declarados además su proyección y su tope de ventana. Las dos
tareas que no tienen la cadencia del capítulo —`poblar_mundo` al arrancar la obra
y cuando haga falta ampliar el elenco, y `auditar` cada N capítulos y al cierre—
van fuera del guion y **siempre solas**.

Dentro de `nucleo/` va esto y nada más:

- **El presupuesto.** El techo son 100 000 tokens de entrada **simultáneos** y
  **cuenta solo lo que entra**: lo que los agentes devuelven se paga en coste y
  no ocupa techo, así que en el reparto de una tanda no se reserva nada para las
  respuestas. Anchura de tanda = `80 000 ÷ tope del rol más caro`, redondeado a
  la baja. Conteo de la ventana antes de enviar y, si no cabe, **partición de la
  unidad** —capítulo → escena → párrafo—; la proyección no se recorta nunca.
- **El reparto de concurrencia.** Paralelo donde no se pisan —documentar varias
  escenas, comprobar varias dimensiones sobre un mismo borrador— y secuencial
  donde hay testigo: planificar, redactar, revisar y cerrar van en fila porque
  cada una consume lo que dejó la anterior. Nunca en abanico libre.
- **El ensamblado de proyecciones** por rol, según la tabla de `architecture.md`
  §3: lo que ve y lo que no ve cada uno. Los materiales que se ensamblan son los
  seis de esa sección —canon, estado en N, compromisos abiertos, continuidad
  local, documentación y ecos de la obra—, cada uno con su política de
  residencia.
- **La regla del tamaño.** Nada cuyo tamaño crezca con la longitud de la obra
  entra en la ventana de ningún agente: el log no se lee nunca entero, la prosa
  cerrada no se relee salvo la cola de continuidad local, y los dos únicos
  materiales que crecen llevan tope declarado y un solo lector. De ellos, los
  `Resumen de capítulo` siguen entrando enteros: v1 declara su tope y avisa al
  alcanzarlo, pero no compacta (SPEC1 §11).
- **El enrutado por severidad y los topes de vueltas**, que son **las dos únicas
  bifurcaciones del guion**: ningún agente enruta ni manda sobre otro.
  `bloqueante` regenera la escena, `mayor` entra en revisión dirigida, `menor` y
  `sugerencia` esperan al pulido; dos revisiones por borrador y dos
  regeneraciones por escena, y agotado el tope la escena se acepta con sus
  críticas abiertas anotadas y el capítulo se cierra marcado.
- **El ciclo de vida del capítulo** de `architecture.md` §4, que es lo que el
  caminante recorre: `Planificado` → `Redactado` → `Validado`, con vuelta a
  `Redactado` por crítica bloqueante y a `EnRevision` por críticas mayores, y de
  `Validado` a `Aceptado` cuando no quedan bloqueantes; de `Aceptado` a
  `Cerrado`, que es el paso que publica los hechos y olvida el andamio. Un plan
  rechazado va a `Descartado`.
- **La doble pasada en desacuerdo.** Si dos agentes discrepan sobre el mismo
  predicado, se repite la comprobación con la proyección reducida al mínimo; si
  persiste, la crítica baja a `sugerencia` y se registra como caso ambiguo.
- **El descarte de críticas sin evidencia**, contado, porque es lo que mide
  OBJ-04.
- **Los permisos por rol**, derivados de la tabla de gobierno de
  `architecture.md` §6 e impuestos aquí, no en el prompt. Son los que hacen
  cumplir las reglas de integridad del censo sin depender de que nadie las
  recuerde: el Redactor no emite `Crítica` y ni el Verificador ni el Editor de
  estilo ni el Juez escriben `Borrador` —ningún agente valida su propia salida—,
  y el Revisor aplica críticas ajenas pero no puede crear las suyas.
- **Los reintentos** hasta el tope declarado, con la unidad escrita entera o
  nada.

**Cubre.** RF-05, RF-10 a RF-15, RF-30 a RF-35, RNF-01, RNF-04, RNF-06.

**Se cierra con** `prueba` y `analisis`: el guion son diez pasos declarados, así
que se enumera entero en lugar de razonar sobre él, y lo mismo con las cuatro
severidades, los dos topes de vueltas y las transiciones del ciclo de vida del
capítulo. Evidencia: la suite del guion y una tabla de anchura de tanda calculada
rol por rol contra los topes de `architecture.md` §3.

**Riesgo declarado.** Si `nucleo/` engorda, está reapareciendo el harness a
medida. Se vigila su tamaño en cada etapa posterior.

## Etapa 3 · Recorrido en seco

**Qué queda construido.** Un ejecutor fingido que devuelve artefactos preparados
en vez de llamar a un agente, y con él el recorrido completo de los diez pasos de
un capítulo de tres escenas.

**Qué demuestra.** Cada paso encarga su tarea al rol que le toca; ningún rol
escribe una entidad que la tabla de gobierno no le asigna; las tandas respetan la
anchura calculada; todo lo producido queda guardado y se puede volver a servir; y
repetido dos veces da exactamente la misma secuencia de pasos, tandas y
proyecciones.

**Cubre.** El criterio 0 de SPEC1 §10, RNF-04, y los pasos 2 y 4 del orden de
adopción de `validators.md` §10.

**Se cierra con** `demostracion`, más una `prueba` por rol que intenta la
escritura prohibida y falla. Evidencia: la secuencia de pasos registrada en las
dos pasadas y el registro del intento de escritura prohibida.

**Esta etapa es la puerta.** Mientras no esté en verde no se invoca a ningún
agente real.

## Etapa 4 · Índice híbrido y recuperación

**Qué queda construido.** Las tres colecciones de `architecture.md` §3 y ninguna
más, cada una particionada por `id_obra`:

| Colección | Cuándo se escribe | Quién la consulta |
| --- | --- | --- |
| Documental | Al recoger la `Fuente` | Documentalista |
| Obra · prosa | Al aceptar la unidad, nunca antes | Editor de estilo y la API de consulta del editor |
| Obra · estructura | Al cerrar el capítulo | Planificador |

Igual de importante es quién **no** consulta: ni el Verificador de continuidad,
ni el Contable de estado, ni el Arquitecto de arcos, ni el Redactor. Una búsqueda
por semejanza no encuentra lo que falta y su fallo es silencioso, así que solo
alimenta comprobaciones cuyo fallo es dejar de encontrar algo —en el reparto de
`validators.md` §4, una sola dimensión: la fatiga léxica—.

La búsqueda es **híbrida**: `sqlite-vec` para el parecido de sentido y FTS5 para
la palabra exacta sobre la misma colección, con los dos órdenes fundidos en uno
solo antes de recortar a `k`. Ninguna de las dos vías se consulta a solas.

Las huellas se calculan en la propia máquina con `fastembed` y el modelo
`sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`, de 384
dimensiones. El modelo queda registrado
junto a cada fragmento: dos modelos conviviendo en el índice de una obra son un
defecto. Solo se indexa texto aceptado, y el fragmento apunta a su artefacto sin
duplicar el cuerpo. `k` y el tope de tokens van declarados por rol y **se
descuentan del tope de ventana del que consulta**; si no cabe, baja `k`. Cada
recuperación deja en la `Traza` la consulta, la colección, `k`, los fragmentos
devueltos y cuáles acabó usando el agente.

Valor de partida a declarar en el código, pendiente de calibrar: cuánto mide un
fragmento y cuánto se solapa con el siguiente (SPEC1 §12).

**Cubre.** RF-55, RF-63 a RF-68, RD-05, RD-10 a RD-15.

**Se cierra con** `prueba`: borrar el índice y reconstruirlo desde los artefactos
devuelve los mismos fragmentos; un borrador descartado no se recupera nunca como
eco; y ninguna consulta cruza de una obra a otra. Evidencia: la comparación de
los dos índices y el intento de recuperar un descartado.

## Etapa 5 · Ejecutor real y `Traza`

**Qué queda construido.** El lanzamiento de un subagente de Claude Code con
modelo Haiku por tarea: se le entrega la proyección ya ensamblada y se recoge el
artefacto que devuelve. **El backend no llama a ninguna API de modelo ni gestiona
claves.** Cada tarea arranca sin ninguna herramienta salvo las que su contrato le
concede, y solo el Documentalista tiene salida al exterior. Lo que viene de fuera
entra como dato delimitado, nunca como instrucción.

**Toda tarea arranca en frío.** No hay historial de conversación en ninguna
parte: cada tarea abre una ventana construida desde cero a partir de los
artefactos escritos y la cierra al escribir el suyo. Entre dos tareas no viaja
nada más que un artefacto en el almacén, y es eso lo que permite medir una
ventana antes de mandarla.

La `Traza` se registra en toda tarea: contexto enviado, salida, coste, latencia,
intento y la cuenta exacta de tokens que el subagente devuelve al terminar. La
estimación previa se calibra contra esa cuenta exacta.

**Cubre.** D-08, RF-35, RF-52, RNF-03, y hace medible OBJ-01.

**Se cierra con** `prueba` y `analisis`: se enumeran rol por rol las herramientas
concedidas y se intenta la salida al exterior desde uno que no la tiene; y la
`Traza` contesta las cuatro preguntas de `validators.md` §7. Evidencia: la tabla
de herramientas por rol y una `Traza` completa de una tarea real.

## Etapa 6 · Las once carpetas de tarea

**Qué queda construido.** Una carpeta por tipo de tarea del censo, con todo lo
suyo dentro: contrato, prompt, esquema del artefacto que escribe y rechazo del
artefacto que recibe. Declarar un rol es añadir una carpeta. Se implementan en el
orden en que el guion las necesita:

| Tanda | Tareas | Por qué van juntas |
| --- | --- | --- |
| 1 | `planificar`, `documentar`, `redactar` | Producen el primer borrador: sin ellas no hay nada que criticar |
| 2 | `verificar`, `revisar` | Cierran el bucle de calidad, que es donde vive el riesgo |
| 3 | `editar_estilo`, `juzgar`, `plegar`, `destilar` | Cosen y cierran el capítulo |
| 4 | `poblar_mundo`, `auditar` | Van solas y fuera de la cadencia del capítulo |

**El Redactor recibe un encargo por escena, no por capítulo**, y el capítulo se
cose después en el paso 7 con `editar_estilo`. Es lo que hace barato regenerar y
lo que respeta que al Verificador no le quepa un capítulo entero.

Las dimensiones de calidad de `validators.md` §4 son **veintiuna**, y ninguna
inaugura una tarea: cada una se entrega como un **contrato de verificación** al
rol al que ya le corresponde —diez van en `verificar`, tres en `editar_estilo`,
una en `juzgar` y siete en `auditar`—, con su predicado en una frase, su
proyección mínima cerrada y la forma exacta de la `Crítica`, cuyos seis campos
son `objeto`, `dimension`, `severidad`, `evidencia`, `accion_sugerida` y
`detectada_por`. **Una dimensión por invocación**, sin excepción: al agente al
que se le piden siete comprobaciones a la vez solo le salen las dos primeras.

Dentro del capítulo entran en tres cribas: cinco dimensiones en la de
bloqueantes, cuatro en la de mayores y cinco en la de pulido. Las siete del
Arquitecto de arcos son de alcance de obra y entran por `auditar`.

**Qué escribe cada tarea**, copiado de la tabla de entrada y salida de
`architecture.md` §2, porque es lo que el permiso de escritura tiene que
permitir y lo que el agente siguiente va a rechazar si falta:

| Tarea | Deja escrito |
| --- | --- |
| `poblar_mundo` | Fichas de `Personaje`, `Lugar`, `Objeto` y `Facción` |
| `documentar` | `Fuente`, `Concepto`, `Práctica` y `Registro lingüístico`, filtrados por fecha y lugar |
| `planificar` | `Plan`: esqueleto de `Capítulo`, contrato de cada `Escena` y `Compromiso` asignados |
| `redactar` | `Borrador` candidato de una escena, con sus `Párrafo` |
| `verificar` | `Crítica` con evidencia citable, o la constancia de que el predicado se cumple |
| `editar_estilo` | `Crítica` local, `Borrador` de superficie y el registro acumulado actualizado |
| `juzgar` | `Crítica` ruidosa, marcada aparte, que por sí sola no dispara regeneración |
| `revisar` | `Revisión` —críticas atendidas y rechazadas con motivo— y el `Borrador` siguiente |
| `plegar` | `EventoEstado` del capítulo N, con fecha y lugar resultantes, y el estado en N |
| `destilar` | `Resumen de capítulo`, las dos colas actualizadas y la memoria de capítulo retirada |
| `auditar` | `Crítica` de alcance global |

La `Traza` no está en la tabla porque no es salida de ningún rol: se registra en
toda tarea, la ejecute quien la ejecute. Y la tabla de gobierno de
`architecture.md` §6 añade tres escrituras que la de entrada y salida no nombra,
y que los permisos tienen que contemplar: `Evento`, que escriben el Planificador
y el Documentalista; `Compromiso`, que escriben el Planificador y el Redactor; y
`Decisión`, que puede registrar cualquier rol y es inmutable.

Aquí se cierran también el paso de `Aceptado` a `Cerrado` —solo el Contable emite
`EventoEstado`— y la retirada de la memoria de capítulo por el Archivero.

**Tres contratos cargan con lo que se pierde al no calcular** (`architecture.md`
§7), y por eso se escriben con especial cuidado: el Contable emite en cada
`EventoEstado` la fecha y el lugar resultantes **ya calculados y explícitos**,
para que el Verificador compare dos valores escritos en vez de calcularlos; el
Editor de estilo mantiene el registro acumulado de imágenes y muletillas,
actualizado al cerrar cada capítulo, y comprueba la fatiga contra los ecos
recuperados de ese registro, no contra el texto; y la lista de léxico vetado es
corta y del capítulo, derivada del `Registro lingüístico` de las escenas en
juego, nunca la lista global.

**Cubre.** RF-11, RF-23, RF-30, RF-40 a RF-43, RF-60 a RF-62, RF-69, D-03, D-09.

**Se cierra con** `prueba` y `analisis`: se enumeran las carpetas de tarea contra
el censo de `architecture.md` §2 y son once, una por rol; casos sembrados con un
defecto conocido de una sola dimensión por caso, y los mismos casos con esa
dimensión intacta para contar falsos positivos; un artefacto roto a propósito
produce `Crítica` bloqueante con objeto el artefacto y no llega al Revisor; y la
propiedad del pliegue —estado en N-1 más los eventos de N da lo mismo que plegar
el log entero—. La primera medida **fija la línea base, no exige umbral**.
Evidencia: la tabla de detección y falsos positivos por dimensión.

## Etapa 7 · La API

**Qué queda construido.** Las nueve operaciones de SPEC1 §6 —diez rutas, porque
detener y reanudar comparten fila—, cada una como un procedimiento de principio a
fin, sin capa de servicios intermedia. Es el único sitio donde el
backend declara tipos, porque es donde habla con algo que no es un agente. Los
mensajes de error, en español.

`POST /obras` da de alta la obra, arranca la producción en segundo plano y
devuelve el `id_obra` sin esperar a que termine. Es la **única** llamada de
escritura por obra, junto a detener y reanudar, que son control y no
mantenimiento: la API no ofrece ninguna operación de limpieza ni de archivado.
`GET /obras/{id}/progreso` sirve el avance mientras la obra corre.

**Cubre.** RF-01 a RF-04, RF-50 a RF-55, RI-01 a RI-09, RNF-07, RNF-08, OBJ-07.

**Se cierra con** `prueba`, `analisis` y `demostracion`: un brief al que le falta
un campo obligatorio se rechaza nombrando el campo y sin crear nada; se enumeran
las operaciones de escritura que ofrece la API y son exactamente tres; y detener
y reanudar a mitad de capítulo no duplica ni pierde trabajo aceptado. Evidencia:
el esquema HTTP publicado y la lista de sus operaciones de escritura.

## Etapa 8 · La obra de tres capítulos

**Qué queda construido.** Nada nuevo: es la pasada que convierte el sistema en
algo medido. Una obra de tres capítulos de tres escenas corre de `POST /obras` a
obra cerrada con una sola llamada de escritura, y de su `Traza` salen las líneas
base de OBJ-01 a OBJ-08, hoy declaradas pendientes.

Se ejercitan además los criterios que faltan de SPEC1 §10: regenerar un capítulo
intermedio y comprobar que los siguientes quedan replegados y consistentes;
briefs adversarios —época mal documentada, personajes homónimos, saltos
temporales largos—; y una fuente sembrada con una instrucción dentro, para mirar
en la `Traza` si el Redactor se desvía.

De la misma pasada sale la **métrica del sistema** de `architecture.md` §5:
cuántas vueltas necesita cada capítulo, **qué dimensiones reinciden** y cuántas
críticas se descartan por falta de evidencia. La reincidencia por dimensión es lo
único que vigila las tres dimensiones que se comprueban contra un dato que
escribió el propio sistema y que nadie recalcula.

**Se cierra con** `demostracion`. Evidencia: la `Traza` completa de la obra, la
tabla de líneas base que sustituye a los ocho «pendiente» de SPEC1 §3, y el
recuento de reincidencia por dimensión.

## Etapa 9 · Cierre del ciclo

La fase 3 del ciclo de edición, que es trabajo del agente y no un recordatorio
para el editor:

| Qué se actualiza | Por qué |
| --- | --- |
| `architecture.md` §7 | El árbol de artefactos deja de describirse como carpetas en disco: `mundo/`, `obra/`, `log/`, `estado/` y `criticas/` son grupos lógicos y todo vive en SQLite (D-02). El árbol del código pasa a ser el de la etapa 0 |
| `architecture.md` §8 | Se retiran las **tres** decisiones que SPEC1 cierra del todo —dónde vive el almacén, si los prompts son del `backend/`, y qué severidad dispara regeneración—, sin narrarlas como pasado. La de la herramienta externa de cálculo **no se retira**: queda anotada como «no en v1» y sigue abierta para las siguientes. Las siete de dominio siguen abiertas tal cual |
| `architecture.md` §4 | El diagrama del ciclo de vida etiqueta el paso de `Redactado` a `Validado` como «validadores deterministas», y §5 dice que no los hay: el paso lo dan las cribas de agentes. Se corrige la etiqueta |
| `validators.md` | Se registra el método de lo entregado que hoy no tenga uno asignado |
| `AGENTS.md` | Solo si el reparto del repositorio cambia |

Al terminar, SPEC1 queda marcada como aplicada.

## Lo que este plan no decide

Las dos decisiones abiertas de SPEC1 §12 siguen abiertas y ninguna bloquea: con
qué se cuentan los tokens antes de enviar —hoy, una estimación calibrada contra
la medida exacta que devuelve el subagente— y cuánto mide un fragmento con cuánto
solape. Las dos llevan valor de partida declarado en el código y se calibran en
la etapa 8. Todo lo de SPEC1 §11 queda fuera, empezando por la interfaz web.

## Riesgos que se aceptan, y con qué se contienen

| Riesgo | Con qué se contiene |
| --- | --- |
| Las once carpetas de tarea divergen en cómo escriben sus artefactos | No hay capa común: lo contiene que `almacen/` sea la única puerta de escritura y que el agente siguiente rechace lo malformado |
| El conteo previo de tokens es una estimación, no la cuenta del proveedor | El 20 % de margen del techo. Si en la etapa 8 el pico real se acerca a 100 000, se ajustan los topes por rol antes que tocar el techo. La calibración fina contra trazas reales queda fuera de v1 (SPEC1 §11): lo que da la etapa 8 es la línea base |
| Los topes de ventana por rol son una asignación de diseño, no una medida | Se declaran en configuración y la `Traza` existe en parte para revisarlos. Cambiarlos no es un cambio de código |
| `sqlite-vec` o `fastembed` no cargan en la máquina de desarrollo | Se comprueba al abrir la etapa 4, antes de construir nada encima. Si no hay forma, es una decisión de fondo y se vuelve a la fase 1 |
| `nucleo/` engorda y reaparece el harness a medida | Contrato de importación, más vigilar su tamaño en cada etapa |
