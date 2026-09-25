# Trade-offs

Las decisiones de diseño que más pesan, contadas como decisiones: qué problema
había, qué opciones se pusieron sobre la mesa, con qué criterios se compararon,
qué se eligió y qué se paga por ello. El detalle de cada una vive en la spec
con su identificador (`D-nn`), que se cita al final de cada apartado como
puntero; esta página no lo sustituye, lo ordena.

Lo que sigue sin decidir no está aquí: está en
[`architecture.md`](architecture.md) §8.

## Índice

1. [Un agente o muchos](#1-un-agente-o-muchos)
2. [Quién decide el siguiente paso](#2-quién-decide-el-siguiente-paso)
3. [Un harness propio o subagentes que ya son agentes](#3-un-harness-propio-o-subagentes-que-ya-son-agentes)
4. [El formato de la story bible](#4-el-formato-de-la-story-bible)
5. [Qué modelo escribe, cuál juzga y cómo lee el juez](#5-qué-modelo-escribe-cuál-juzga-y-cómo-lee-el-juez)
6. [Cómo se encuentra lo parecido](#6-cómo-se-encuentra-lo-parecido)
7. [Guardarraíles: en el prompt, en el servidor o en un hook](#7-guardarraíles-en-el-prompt-en-el-servidor-o-en-un-hook)
8. [Dónde se guarda el avance](#8-dónde-se-guarda-el-avance)
9. [Cómo se integra TLA+ con el flujo real](#9-cómo-se-integra-tla-con-el-flujo-real)
10. [Qué invariantes demuestra Lean, y en qué orden](#10-qué-invariantes-demuestra-lean-y-en-qué-orden)
11. [Cómo se juzga el sistema sin que aprenda el examen](#11-cómo-se-juzga-el-sistema-sin-que-aprenda-el-examen)
12. [Cómo se compara lo vetado](#12-cómo-se-compara-lo-vetado)

---

## 1. Un agente o muchos

**El problema.** Una novela de diez capítulos no cabe en el contexto de un
modelo a la vez que su mundo, sus fuentes y sus críticas, y un modelo que
revisa lo que él mismo escribió tiende a darlo por bueno.

| Opción | A favor | En contra |
| --- | --- | --- |
| Un solo agente con toda la obra en contexto | Sin coordinación; una sola voz | No cabe; se autoevalúa; no se puede saber qué parte falló |
| Un agente que escribe y otro que critica | Ya separa escribir de juzgar | El escritor sigue cargando mundo, fuentes y estado: el contexto crece con la obra |
| **Un censo de roles, cada uno con una sola tarea** | Cada rol ve solo lo que necesita; quien escribe no juzga; cada fallo tiene un responsable | Más piezas y más encargos; hay que decidir quién manda en el orden |

**Criterios.** Caber en el techo de 100 000 tokens de entrada concurrentes; que
ningún agente valide su propia salida; que un defecto se pueda atribuir a un
rol, un capítulo y un intento.

**Elección.** Doce roles, **un rol por tipo de tarea y un tipo de tarea por
rol**. Si aparece trabajo que ninguno cubre se declara un rol nuevo en vez de
ensanchar uno: así nació el Entrevistador, en lugar de dárselo al Planificador.

**El precio.** Cientos de encargos por obra y un coste fijo por encargo. Se paga
con un modelo pequeño en los roles (§5) y con proyecciones mínimas.

*En la spec: `architecture.md` §2, D-21.*

## 2. Quién decide el siguiente paso

**El problema.** Con doce roles, alguien tiene que decir a quién le toca.

| Opción | En contra |
| --- | --- |
| Un agente coordinador que enruta | Es un rol que manda sobre otros; su gasto y el número de frentes abiertos no se conocen de antemano |
| Cada agente dice al terminar a quién le toca | El gasto queda sin acotar y el techo deja de ser una garantía |
| **Un guion declarativo que una pieza sin criterio recorre** | Menos flexible: las únicas bifurcaciones son la severidad y el tope de vueltas |

**Criterios.** Que el techo sea una garantía y no una esperanza; que el
recorrido sea reproducible (misma obra, mismos pasos); que ningún agente mande
sobre otro.

**Elección.** El guion de diez pasos por capítulo, en `nucleo/guion.toml`, y el
caminante, que lo lee y lo ejecuta sin conocer el dominio.

**El precio.** Lo que el guion no prevé no ocurre: un tipo de trabajo nuevo es
un paso nuevo en el guion, no una improvisación del agente.

*En la spec: `architecture.md` §4.*

## 3. Un harness propio o subagentes que ya son agentes

**El problema.** Cada tarea necesita un modelo, herramientas, permisos y un
bucle de llamadas.

| Opción | En contra |
| --- | --- |
| Llamar a la API del modelo desde Python y escribir el bucle de herramientas | Es el *harness* a medida que el proyecto prohíbe: permisos, reintentos y herramientas reimplementados, y el estado en objetos en memoria |
| **Lanzar cada tarea como un subagente de Claude Code** | Depende del CLI y de su forma de contar tokens |

**Criterios.** Sin harness a medida; permisos de verdad, que no dependan de que
el prompt los pida; ninguna clave de modelo que gestionar.

**Elección.** Cada tarea es un subagente de Claude Code que arranca **en un
directorio vacío fuera del repositorio**, sin más herramientas que las de su
contrato y sin servidores MCP. El backend solo reparte turnos: entrega la
ventana y recoge lo que vuelve.

**El precio.** Un coste fijo por encargo, medido en unos 1 500–3 200 tokens de
entrada (ver [`registro-de-iteraciones.md`](registro-de-iteraciones.md), T6), y
atarse a cómo el CLI escribe su salida.

*En la spec: D-08, D-35, D-36.*

## 4. El formato de la story bible

**El problema.** La biblia —personajes, lugares, objetos, facciones, eventos—
la leen casi todos los roles, cambia al avanzar la novela y tiene que poder
volver atrás cuando se rehace un capítulo.

**Qué forma tiene cada ficha.**

| Opción | En contra |
| --- | --- |
| Ficheros Markdown o YAML en carpetas | Un segundo sitio donde escribir, y el sistema tendría dos escritores |
| Una tabla con una columna por atributo | El backend tendría que conocer el dominio: cada atributo nuevo sería una migración |
| **Un documento JSON declarativo por artefacto, en SQLite, con un envoltorio fijo** | Nadie comprueba el cuerpo al guardarlo: la forma la impone el esquema de quien lo escribe y la rechaza quien lo lee |

**Cómo cambia.**

| Opción | En contra |
| --- | --- |
| Fichas que se editan al avanzar | Se pierde lo que era cierto en el capítulo 3; nadie sabe quién cambió qué |
| **Fichas inmutables más un log de `EventoEstado`, y el estado en N se deriva plegando el log** | Plegar cuesta una tarea al cerrar cada capítulo |

**Cómo se versiona.**

| Opción | En contra |
| --- | --- |
| Un mundo único que solo avanza | La versión anterior queda incoherente en cuanto la nueva emite eventos |
| Copiar el mundo en cada versión | Duplica el almacén en cada rehacer |
| **Cada fila con la versión en que nació y la que la relevó** | Toda consulta filtra por versión |

**Criterios.** Un solo escritor; que el backend no interprete el contenido; que
el mundo cambie solo por `EventoEstado`; que cada versión se pueda leer tal como
terminó.

**Elección.** Las tres opciones marcadas. Lo que un capítulo usa de la biblia
no se guarda en la ficha: es una `Mención` aparte que anota el Archivero, y la
cronología no se guarda, se deriva al consultarla.

*En la spec: D-01, D-02, D-25, D-26, D-27, D-41, D-44.*

## 5. Qué modelo escribe, cuál juzga y cómo lee el juez

**El problema.** Hay tres lectores con necesidades distintas: los roles, que
leen una escena o un capítulo; el juez de la novela, que tiene que leer la obra
entera; y quien desarrolla el código.

| Quién | Opciones | Elegido | Por qué |
| --- | --- | --- | --- |
| Los doce roles | Haiku, Sonnet, Opus | **Haiku** | Cientos de tareas por obra, ninguna razona sobre la obra entera |
| El juez de la novela | El mismo modelo que escribió, uno mayor | **Sonnet** | Juzgar con el modelo que escribió invita a preferir lo que él habría escrito; es una llamada por versión, así que el coste queda acotado. Opus, descartado por coste en algo que se repite en cada brief y cada vuelta de ajuste |
| El código del sistema | — | **Opus** | Quien escribe el código no es parte de la novela |

**Cómo lee el juez.** Una novela larga no cabe en su ventana de 60 000 tokens.

| Opción | En contra |
| --- | --- |
| La novela entera | No cabe |
| Trocearla y juzgar cada trozo | Da tres notas por trozo que nadie sabe sumar en una nota de la obra |
| Recortar capítulos a medias | Fabrica el defecto de ritmo que se quiere medir |
| **Todos los resúmenes de capítulo, y capítulos enteros por prioridad mientras quepan** | Lo que no cabe solo se ve por su resumen; la ventana lo dice |

La prioridad es el primero y el último capítulo y los que mencionan lo personal,
que es justo donde se mide la personalización.

*En la spec: D-08, D-84, D-85.*

## 6. Cómo se encuentra lo parecido

**El problema.** El Planificador y el Documentalista necesitan escenas y
fuentes parecidas a la que tienen entre manos, y la mitad de lo que se busca son
nombres propios y fechas.

| Opción | En contra |
| --- | --- |
| Embeddings de un proveedor externo | Cuenta, clave y coste por capítulo; reindexar una obra cuesta dinero |
| Solo búsqueda por palabra (FTS5) | No encuentra lo que se dice con otras palabras |
| Solo parecido de sentido | Es lo peor que hay para un nombre propio o una fecha exacta |
| **Híbrida: palabra exacta y parecido de sentido, fundidos en un solo orden, con un modelo local multilingüe** | Un modelo más en la máquina |

**Elección.** `fastembed` con `paraphrase-multilingual-MiniLM-L12-v2`, de 384
dimensiones, en `sqlite-vec` junto a FTS5. Multilingüe porque la obra es en
español; el único multilingüe de 384 dimensiones del catálogo. Recuperar lo hace
el almacén, no un rol nuevo: elegir qué mirar no decide qué es cierto.

*En la spec: D-07, D-10.*

## 7. Guardarraíles: en el prompt, en el servidor o en un hook

**El problema.** Que la prosa escriba los nombres de la biblia tal cual y no
traiga nada vetado.

| Opción | En contra |
| --- | --- |
| Pedirlo en el prompt | Es una petición, no una garantía |
| Comprobarlo en el servidor al recibir | Un fallo es un intento entero perdido: el agente no puede corregir en el acto |
| **Un hook `Stop` en el subagente que no le deja terminar sin corregir, y la misma comprobación repetida por el ejecutor al final** | Una vuelta más de conversación, que ocupa techo y se reserva en la tanda |

**Elección.** Dos hooks: `validar_capitulo` (forma y nombres) y `policy` (lo
vetado). Una vuelta de corrección en la sesión; si no basta, el intento falla y
manda la política del paso.

*En la spec: D-45, D-47, D-48, D-55, D-93.*

## 8. Dónde se guarda el avance

**El problema.** Una obra se puede cortar a mitad: el editor la detiene, una
tarea agota sus intentos o el proceso se cae.

| Opción | En contra |
| --- | --- |
| Guardar tras cada paso | Hay que reconstruir en qué vuelta del bucle estaba cada escena, y el recorrido deja de ser reproducible |
| **El capítulo cerrado es el único punto de guardado; lo que queda a medias se descarta entero** | Se repite el trabajo del capítulo cortado, fuentes incluidas |

**Elección.** El cierre del capítulo es una sola transacción; al volver, se
descarta todo capítulo que no esté cerrado. Tras una caída, la obra se relanza
sola al arrancar el backend, sin que nadie pulse nada.

*En la spec: D-30, D-31, D-33, RF-165.*

## 9. Cómo se integra TLA+ con el flujo real

**El problema.** Las pruebas recorren los caminos que alguien preparó. Lo que
no recorren es la combinación: una caída después de rehacer, dos órdenes del
editor a la vez.

**Qué se modela.**

| Opción | En contra |
| --- | --- |
| Todo: escenas, bucle de calidad, tandas | TLC no termina de recorrerlo, y un modelo sin recorrer no demuestra nada |
| **Solo el flujo: capítulos, tareas, intentos, versiones, hilos y qué ve cada versión** | El contenido y el bucle de calidad quedan fuera; tienen sus pruebas aparte |

**Cómo se une al código.**

| Opción | En contra |
| --- | --- |
| Generar el código desde el modelo, o el modelo desde el código | Mantener ese generador sería otro proyecto; y el código ya existía cuando se escribió el modelo |
| **Una tabla que dice qué función implementa cada acción, y una prueba que lanza TLC** | La correspondencia se sostiene por revisión, no se demuestra |

**Qué propiedades.** Las que romperían el encargo y una prueba de casos no
garantiza haber visto: publicar sin pasar la puerta, perder la versión
anterior, dos producciones a la vez (seguridad) y una obra parada sin decir por
qué (vivacidad).

**Elección.** `backend/formal/tla/`, con `mapeo.md` acción por acción. TLC no es
dependencia del paquete: si falta Java, la prueba se salta y lo dice. Cada
contraejemplo se guarda con su traza y vuelve al código como arreglo con su
prueba —ver [`registro-de-iteraciones.md`](registro-de-iteraciones.md)—.

**El precio.** El modelo es pequeño —tres capítulos, dos versiones— y con tres
versiones ya no cabe en una batería.

*En la spec: D-66, D-67, D-68, D-69.*

## 10. Qué invariantes demuestra Lean, y en qué orden

**El problema.** La coherencia temporal es lo que un lector nota antes y lo que
un agente ve peor: un Verificador juzga una escena antes de que existan los
eventos del capítulo.

**Cómo se priorizó.** De todo lo que se podría comprobar sobre el tiempo de
una novela, entraron primero los invariantes que cumplen dos condiciones: se
deciden **solo con lo que la cronología ya registra** —fecha, lugar, presentes,
nacimientos y muertes—, sin interpretar texto; y son contradicciones que ningún
rol del censo está en posición de ver, porque cruzan capítulos.

| Invariante | Qué dato basta | Qué rol no lo ve, y por qué |
| --- | --- | --- |
| `orden_temporal` | Fecha y capítulo de cada suceso | El Verificador juzga una escena, no el orden entre capítulos |
| `edad_coherente` | Fecha del suceso y nacimiento de cada presente | El nacimiento está en la ficha, no en la escena que se verifica |
| `un_solo_lugar` | Fecha, lugar, presentes y quién llega con un `viaja_a` | Los eventos se emiten al cerrar el capítulo, después de verificarlo |
| `no_reaparece` | Quién muere en cada `EventoEstado` `muere` | La muerte puede estar muchos capítulos antes |

Quedaron para después, por no cumplir la primera condición: las distancias
entre lugares —la ficha guarda la ubicación en texto libre, y calcular
distancias es lo que D-05 deja fuera—, el orden dentro de un mismo capítulo,
que no está registrado, y todo lo que la prosa cuenta y el Contable no emitió.

**Cómo se demuestra.**

| Opción | En contra |
| --- | --- |
| Comprobarlo en Python | Es otra función que puede tener el mismo error que el volcado |
| Lean con Mathlib y tácticas automáticas | Descarga pesada, minutos por comprobación |
| **Un teorema por suceso e invariante, con `decide` sobre naturales, sin Mathlib** | El coste crece con el cuadrado de los sucesos: unos 45 s para 200 |

Con fechas parciales («1587», «1587-04») se demuestra «no hay contradicción
segura»: solo falla lo que falla para cualquier día del intervalo.

**Dónde corre.** En la puerta de publicación, no en la producción: ningún agente
recibe nada que Lean calcule. Con Lean instalado, lo que no se demuestra no se
publica; sin Lean, se publica marcado «sin comprobación formal», porque que falte
una herramienta no dice nada de la novela.

*En la spec: D-61, D-62, D-64, D-65, D-96.*

## 11. Cómo se juzga el sistema sin que aprenda el examen

**El problema.** Hace falta una nota de calidad de la novela entera, pero si el
sistema puede leer la rúbrica, acaba escribiendo para complacerla.

| Opción | En contra |
| --- | --- |
| Un rol más del censo | Su prompt viviría en `tareas/`, legible por quien lo sufre |
| Que la nota dispare revisiones | La producción aprendería a complacer al juez por otro camino |
| **Un evaluador externo, lanzado a mano, con la rúbrica solo en Langfuse** | No hay nota automática en cada obra |

**Elección.** El juez de la novela no está en el censo, ni en el guion, ni en la
API; su módulo no puede importar `tareas/` ni la API, y sin rúbrica no se
lanza. Langfuse es un espejo de salida: la producción no lee nada de él.

*En la spec: D-82, D-83, D-86, D-87.*

## 12. Cómo se compara lo vetado

**El problema.** El comprador veta palabras y temas, y hay una lista global de
insultos. Hay que pararlos también con otra mayúscula, sin acento o en plural.

| Opción | En contra |
| --- | --- |
| Buscar la subcadena tal cual | «película minúscula» caería por «culo» |
| Un lematizador o un modelo | Dependencias, no determinista, no cabe en un hook que no llama a ningún modelo |
| **Normalizar con reglas fijas y comparar palabras enteras; los temas como frases** | El mismo tema dicho con otras palabras, o «m i e r d a», pasa |

**Elección.** La tercera, con el límite declarado en
[`red-team-log.md`](red-team-log.md) en vez de escondido.

*En la spec: D-49, D-50, D-51, D-52.*
