---
name: SPEC1
titulo: Backend v1 — Especificación de requisitos de software
version: 1.14.0
estado: aplicada
fecha: 2026-09-25
ambito: backend/
base:
  - AGENTS.md
  - docs/definitions.md
  - docs/domain-knowledge.md
  - docs/architecture.md
  - docs/validators.md
---

# SPEC1 · Backend v1 — Especificación de requisitos de software

## §1 Introducción

### 1.1 Propósito

Fijar qué tiene que hacer la primera versión del `backend/` para que una obra
completa se produzca de principio a fin. Es un documento de requisitos, no de
implementación: recoge lo que, si se decide mal, obliga a rehacer trabajo. Todo
lo que se puede resolver razonablemente al programar no está aquí.

### 1.2 Alcance del sistema especificado

Dentro: el almacén de artefactos con sus índices de recuperación por parecido,
la pieza que camina el guion del capítulo, las doce carpetas de tarea con su
contrato y su prompt, el presupuesto de contexto, la recogida de fuentes fuera
del sistema, el destinatario real al que la obra va dedicada con los hechos que
vienen de su vida, la entrevista que completa el brief antes del alta, el
punto de guardado por capítulo con la política de reintentos de cada paso, los
dos hooks que revisan lo que entregan los subagentes de prosa, las listas de
lo vetado con su registro de auditoría, los validadores programáticos con la
puerta que decide si una versión se publica, con la cronología demostrada en
Lean, la observación de la producción en Langfuse cuando hay claves, el juez
externo que puntúa una versión terminada con una rúbrica que vive fuera del
repositorio, los briefs con que se prueba el sistema entero, y la API HTTP que
el editor usa para lanzar e inspeccionar una obra.

Fuera: la interfaz web, la calibración de los topes contra trazas reales y todo
lo enumerado en §11.

La medida de «terminado» de v1 es una sola: **una obra corre de la primera orden
al último capítulo cerrado sin que nadie toque nada por dentro**.

### 1.3 Documentos base y jerarquía

| Documento | Qué aporta a este SRS | Manda sobre |
| --- | --- | --- |
| `AGENTS.md` | Reparto del repositorio, pila fijada, invariantes | Frontera y pila |
| `docs/definitions.md` | Entidades del dominio y vocabularios de forma y mundo | Nombres y valores cerrados |
| `docs/architecture.md` | Capas, censo de doce agentes, entidades de producción, memorias, guion, bucle de calidad, organización del código | Comportamiento del sistema |
| `docs/validators.md` | Método, agente, proyección y severidad de cada dimensión | Verificación |

Si este documento contradice a alguno de los cuatro, gana el documento base y
esto es un error de este SRS. La única excepción declarada es D-02 (§8): el
almacén es SQLite y nada más, decisión ya tomada que cierra una de las abiertas
de `architecture.md` §8. Mientras este ciclo siga abierto, el árbol de carpetas
de `architecture.md` §7 y esa decisión de §8 van por detrás de aquí, y ponerlos
al día es trabajo de la fase 3.

### 1.4 Convenciones

- Entidades en `PascalCase` singular; relaciones en `snake_case`.
- Identificadores de requisito estables y no reutilizables: `RF-` funcional,
  `RD-` de datos, `RI-` de interfaz, `RNF-` no funcional, `D-` decisión de esta
  versión, `OBJ-` objetivo.
- La columna «Verificación» usa el vocabulario `metodo_de_verificacion` de
  `validators.md` §2: `prueba`, `analisis`, `inspeccion`, `demostracion`,
  `inverificable`.

## §2 Descripción general

### 2.1 Qué hace el backend y qué no

El backend es el único que abre el almacén y el único que ejecuta tareas. **Hace
tres cosas**: guarda y sirve artefactos, camina el guion encargando tareas a los
agentes dentro de su presupuesto, y expone por HTTP lo que el editor necesita
ver.

**No hace una cuarta**: no decide nada del dominio. No pliega el log, no resume,
no juzga texto y no reescribe prosa. Eso lo hacen los doce roles del censo. Si
el código del servidor empieza a interpretar el contenido de un artefacto, está
reapareciendo el harness a medida que el proyecto prohíbe.

### 2.2 Actores

| Actor | Qué aporta | Qué recibe |
| --- | --- | --- |
| Editor (persona) | Un brief —escrito de una vez o completado en la entrevista (§4.8)— y, como mucho, una orden de detener o reanudar | Manuscrito, críticas, trazas y progreso |
| Destinatario (persona real) | Nada directamente: su vida entra por el brief que escribe el editor, o por lo que pega en la entrevista | La obra, dedicada a él |
| Agente (uno de los doce roles) | El artefacto que escribe, o la propuesta de brief en el caso del Entrevistador | Su proyección mínima y su contrato |
| `frontend/` | Órdenes del editor | Solo respuestas de la API; nunca ficheros |

### 2.3 Restricciones heredadas

Invariantes de `AGENTS.md`, no negociables en esta versión: tres capas
disjuntas; un rol, una tarea; ningún agente valida su propia salida; el mundo
solo cambia por `EventoEstado` emitidos por el Contable al cerrar capítulo; el
estado se deriva plegando el log; solo el Documentalista escribe `Fuente`; toda
`Crítica` lleva evidencia citable; sin harness a medida; y el techo de 100 000
tokens de contexto de entrada concurrente.

Pila fijada: Python con FastAPI, y SQLite con extensión vectorial compatible
detrás de la frontera.

### 2.4 Supuestos y dependencias

- Las doce tareas las ejecutan subagentes de Claude Code con modelo Haiku
  (D-08). El backend no habla con ninguna API de modelo: delega.
- El contexto de entrada se estima antes de enviar y se mide exacto después,
  con lo que el subagente informa al terminar (D-10). La cuenta exacta queda en
  la `Traza` y es la que gobierna OBJ-01.
- **Un subagente de Claude Code no arranca vacío.** Antes de que entre nada del
  sistema, arrastra su propio contexto —su instrucción base y las definiciones
  de las herramientas que tenga concedidas—, y eso son tokens de entrada como
  cualquier otro: cuentan contra el techo. Medido en la máquina de desarrollo
  con el subagente aislado del repositorio (RF-100), con la instrucción del rol
  en lugar de la de serie y con las herramientas del rol más equipado, son
  3 191 tokens por tarea abierta, que se declaran redondeados a 3 500
  (RF-101). De ahí el término que RF-13 añade a la anchura de tanda: sin él el
  techo se respeta sobre el papel y se rompe en la máquina.
- El brief lo escribe una persona y puede venir incompleto: eso es un caso
  normal, no un error del sistema. `POST /obras` lo rechaza nombrando el campo
  (RF-01), y la entrevista lo completa (§4.8).

## §3 Objetivos medibles

Ningún objetivo tiene línea base: no hay código, así que la base se declara
**pendiente de medir** en lugar de inventarla. La primera pasada completa de una
obra de prueba es la que la fija, y hasta entonces las metas son de diseño.

Van en este orden porque el primero es el que hace que los demás signifiquen
algo: un sistema que no cabe en el techo no llega a producir número alguno.

| ID | Objetivo | Métrica | Cómo se mide | Línea base | Meta |
| --- | --- | --- | --- | --- | --- |
| OBJ-01 | Caber en el techo | Pico de tokens de entrada concurrentes en una obra | Máximo de la suma de las ventanas abiertas a la vez, de la `Traza`. Lo que devuelven los agentes no entra en la cuenta | Pendiente | ≤ 100 000, con pico habitual ≤ 80 000 |
| OBJ-02 | Coste plano por capítulo | Tokens totales del capítulo N | Suma de contexto y salida por capítulo, de la `Traza` | Pendiente | Capítulo 40 ≤ 1,2 × capítulo 4 |
| OBJ-03 | Que el bucle converja | Vueltas hasta `Aceptado` por escena | Recuento de intentos en la `Traza` | Pendiente | ≥ 90 % de escenas en ≤ 2 vueltas; < 10 % de capítulos cerrados marcados |
| OBJ-04 | Críticas utilizables | Proporción descartada por falta de `evidencia` | Recuento de rechazos sobre críticas emitidas | Pendiente | < 10 % |
| OBJ-05 | Artefactos bien formados | Rechazos por campo ausente o valor fuera de vocabulario, por capítulo | Recuento de `Crítica` bloqueante con objeto artefacto | Pendiente | ≤ 1 por capítulo |
| OBJ-06 | Cobertura documental | Afirmaciones históricas con `Fuente` asociada | Cociente sobre las afirmaciones del capítulo | Pendiente | ≥ 90 % |
| OBJ-07 | Cero intervención | Órdenes humanas necesarias entre el brief y la obra cerrada | Recuento de llamadas de escritura a la API por obra | Pendiente | Exactamente 1 |
| OBJ-08 | Recuperación útil | Proporción de fragmentos recuperados que el agente acaba citando o usando | Cociente sobre lo devuelto en cada consulta, de la `Traza` | Pendiente | ≥ 40 % |
| OBJ-09 | Observación completa | Proporción de `Traza` de una obra con su generación en Langfuse | Cociente entre las generaciones de las trazas de la sesión y las `Traza` de `GET /obras/{id}/trazas`, con Langfuse encendido (§4.20) | Pendiente | 100 % |
| OBJ-10 | Calidad juzgada de la novela | Nota media del juez de la novela por criterio (§4.21) | Media de los scores `juez_de_la_novela.<criterio>` de Langfuse sobre las versiones de los briefs de prueba, con la misma versión de la rúbrica | Pendiente de medir | ≥ 3,5 en cada criterio y ninguna nota 1 |
| OBJ-11 | Ruido acotado del juez | Diferencia de nota entre dos juicios de la misma versión con la misma rúbrica | Máximo, por criterio, de la diferencia entre dos lanzamientos sobre la misma versión, de los scores de Langfuse | Pendiente de medir | ≤ 1 punto |

**Qué no es objetivo, y por qué.** Bajar el coste por sí solo: se cumple
trivialmente con un modelo peor y arruina OBJ-03 y OBJ-06 sin que la cifra de
coste se entere. Bajar el número de críticas: se cumple con verificadores
ciegos, que es el fallo que `validators.md` §6 llama «el agente que no encuentra
nada nunca». Subir el número de fragmentos que devuelve
una consulta: mejora la sensación de cobertura, se come el tope de ventana del
rol que consulta y empeora OBJ-01 sin que OBJ-06 se mueva. Y la nota suelta del
Juez de rúbrica del censo, que es ruido declarado y no mejora medible. La del
juez de la novela sí entra, en OBJ-10, pero solo junto a su ruido medido en
OBJ-11: una mejora que no supera ese ruido no cuenta (D-87).

## §4 Requisitos funcionales

### 4.1 Alta y arranque de una obra

```mermaid
flowchart LR
  B([Brief del editor]) --> O[Alta de Obra]
  O --> M[poblar_mundo]
  M --> G["Guion del capitulo<br/>pasos 1 a 10"]
  G --> C{Quedan capitulos?}
  C -- si --> G
  C -- no --> A[auditar de cierre]
  A --> F([Obra cerrada])
```

| ID | Requisito | Verificación |
| --- | --- | --- |
| RF-01 | Acepta un brief y da de alta una `Obra` con título, época, ámbito, premisa, número de capítulos, políticas globales y, si los trae, la tesis temática, el elenco declarado, los arcos y el destinatario (RF-06). Obligatorios son el título, la época, la premisa y el número de capítulos; si falta uno, lo rechaza nombrando el campo con su ruta completa, sin crear nada. Sin tesis temática la obra no lleva ninguna declarada y sin elenco declarado los personajes los decide el Constructor de mundo (D-60) | `prueba` |
| RF-02 | El alta arranca la producción completa: `poblar_mundo` y después el guion de cada capítulo hasta cerrar la obra. **No hay ninguna otra orden que el editor deba dar** | `demostracion` |
| RF-03 | Cada obra nace en su propio espacio de artefactos, identificado por `id_obra`. No existe un espacio de trabajo compartido que haya que archivar ni vaciar entre obras | `analisis` |
| RF-04 | La producción se puede detener y reanudar por orden explícita. Reanudar vuelve al último capítulo cerrado y no repite trabajo ya cerrado (§4.10, RF-91) | `prueba` |
| RF-05 | Una tarea fallida se reintenta hasta el tope que declara su paso del guion, y lo que pasa al agotarse también lo declara el paso (§4.10, RF-95 a RF-99) | `prueba` |
| RF-06 | El brief puede llevar un **destinatario**: nombre, edad, rasgos, recuerdos, tono pedido, dedicatoria y las palabras o temas vetados. Es opcional —una obra histórica sin destinatario sigue siendo válida—. Si viene, el nombre, la edad, el tono y la dedicatoria son obligatorios y el rechazo nombra el campo que falta con su ruta, `destinatario.nombre`; las tres listas pueden venir vacías, porque vacío es una respuesta | `prueba` |
| RF-07 | Cada recuerdo aportado se guarda como `Recuerdo`, entidad de la capa Mundo, inmutable y sin `Fuente`. **Ningún rol del censo lo escribe**: nace con el alta de la obra, igual que la propia `Obra` (D-13) | `prueba` |
| RF-08 | Todo elemento del mundo que salga de la vida del destinatario se marca `licencia = "personal"` y apunta al `Recuerdo` del que sale. Un elemento `personal` **queda exento de las cuatro dimensiones de anacronismo**: se escribe tal cual, con su nombre de hoy, y no genera `Crítica` (D-12) | `prueba` |
| RF-09 | El Planificador decide qué papel tiene el destinatario en la obra —`protagonista`, `secundario`, `testigo` o `narrador`— y lo deja escrito en el `Plan`. Ni el editor lo elige ni el validador lo supone: lo lee de ahí (D-14) | `prueba` |

### 4.2 Ejecución del guion

| ID | Requisito | Verificación |
| --- | --- | --- |
| RF-10 | El guion del capítulo —paso, rol, proyección, tope de ventana y concurrencia— es un artefacto declarativo, no código. La pieza que lo camina lee cuál es el paso siguiente y lo ejecuta | `inspeccion` |
| RF-11 | Cada paso encarga una tarea a un rol con la proyección mínima de ese rol (`architecture.md` §3) y nada más. Lo que sobra en la proyección produce falsos positivos y es un defecto | `inspeccion` |
| RF-12 | Ningún rol invoca a otro ni recibe objetos en memoria: el testigo se pasa siempre por artefacto escrito en el almacén | `analisis` |
| RF-13 | La anchura de una tanda se calcula: `80 000 ÷ (tope del rol más caro de la tanda + coste fijo del subagente)`, redondeado a la baja; en un paso con hooks, el tope lleva sumada la reserva de la vuelta (RF-128). Si hay más tareas, se hacen tandas sucesivas y se espera a que cierre una antes de abrir la siguiente. Las tareas de una tanda corren a la vez, y lo que devuelven se recoge en el orden del guion, no en el de llegada (D-88) | `analisis` |
| RF-14 | Antes de enviar, cuenta los tokens de la ventana. Si no cabe en el tope del rol, **parte la unidad** (capítulo → escena → párrafo) y nunca recorta la proyección | `prueba` |
| RF-15 | Las únicas bifurcaciones son el enrutado por severidad y el tope de vueltas. Ningún agente enruta ni manda sobre otro | `inspeccion` |
| RF-16 | El destinatario y sus recuerdos entran en la ventana del Constructor de mundo y del Planificador, y en ninguna otra ventana de la obra, declarados como material propio y no colados dentro del cuerpo de la `Obra`. Lo que los demás roles necesitan de él ya está en las fichas del mundo que el Constructor escribió | `inspeccion` |

### 4.3 Almacén y forma de los artefactos

| ID | Requisito | Verificación |
| --- | --- | --- |
| RF-20 | `almacen/` es la única puerta de lectura y escritura. Ni `tareas/` ni `api/` hablan con la base de datos | `inspeccion` |
| RF-21 | Todo artefacto se guarda con `id` opaco, `tipo`, `procedencia` (rol, tarea e intento que lo produjeron) y sello temporal | `analisis` |
| RF-22 | El cuerpo del artefacto se guarda íntegro tal como lo escribió el agente. El backend no lo reinterpreta: solo extrae las columnas por las que hace falta consultar | `inspeccion` |
| RF-23 | Un artefacto con un campo obligatorio ausente o con un valor fuera de vocabulario controlado se rechaza, y el rechazo es una `Crítica` de severidad `bloqueante` cuyo objeto es el artefacto, no el texto | `prueba` |
| RF-24 | `EventoEstado`, `Fuente`, `Resumen de capítulo`, `Decisión` y todo borrador ya aceptado son inmutables. Cambiar algo es escribir una versión nueva | `prueba` |
| RF-25 | El estado en N se deriva plegando: el Contable recibe el estado en N-1 materializado y los eventos de N. El log no se lee nunca entero. Rehacer desde el capítulo 12 (§4.12) deja los estados materializados de 12 en adelante a la versión anterior y repliega hacia delante en la nueva | `analisis` |
| RF-26 | Retirar la memoria de capítulo la ejecuta el Archivero como paso del guion: el almacén marca esos artefactos como caducados y deja de servirlos a cualquier proyección | `prueba` |

### 4.4 Control de calidad

| ID | Requisito | Verificación |
| --- | --- | --- |
| RF-30 | Tres cribas por borrador —bloqueantes, mayores y pulido—, no una. Cada dimensión entra en la vuelta que le fija su severidad de partida | `inspeccion` |
| RF-31 | Una `Crítica` sin `evidencia` citable se descarta antes de llegar al Revisor, y el descarte se cuenta (OBJ-04) | `prueba` |
| RF-32 | Enrutado por severidad: `bloqueante` regenera la escena, `mayor` entra en revisión dirigida, `menor` y `sugerencia` esperan a la criba de pulido | `prueba` |
| RF-33 | Tope de vueltas: dos revisiones dirigidas por borrador y dos regeneraciones por escena. Agotado, la escena se acepta con sus críticas abiertas anotadas y el capítulo se cierra marcado | `prueba` |
| RF-34 | Si dos agentes discrepan sobre el mismo predicado, se repite con la proyección reducida al mínimo; si persiste, la crítica baja a `sugerencia` y se registra como caso ambiguo | `prueba` |
| RF-35 | Los permisos de lectura y escritura por rol los impone el backend, no el prompt: ningún rol puede escribir una entidad que la tabla de gobierno (`architecture.md` §6) no le asigna | `prueba` |

### 4.5 Cierre de capítulo y de obra

| ID | Requisito | Verificación |
| --- | --- | --- |
| RF-40 | El paso de `Aceptado` a `Cerrado` emite los `EventoEstado` del capítulo, solo por el Contable, con fecha y lugar resultantes ya calculados y escritos. Hasta que el capítulo no cierra, sus eventos no existen para nadie | `analisis` |
| RF-41 | Cerrado el capítulo, el Archivero escribe el `Resumen de capítulo` y actualiza la cola de compromisos y el registro acumulado de estilo | `analisis` |
| RF-42 | `auditar` entra cada N capítulos y al cierre de la obra, siempre en solitario. N es configuración | `analisis` |
| RF-43 | Al cierre, ningún compromiso queda `abierto`: es `bloqueante`. Los retoques finales los aplica el Revisor o el Editor de estilo como paso del guion. **El editor humano no ejecuta pasos: lee el resultado** | `demostracion` |

### 4.6 Consulta por el editor

| ID | Requisito | Verificación |
| --- | --- | --- |
| RF-50 | Sirve el manuscrito con solo el texto aceptado, en orden, y marca los capítulos cerrados con críticas abiertas | `inspeccion` |
| RF-51 | Sirve las críticas filtrables por estado, dimensión, severidad y capítulo, con su evidencia y quién las detectó | `analisis` |
| RF-52 | Sirve una `Traza` por tarea con contexto enviado, salida, coste, latencia e intento. Se registra en toda tarea, la ejecute quien la ejecute | `analisis` |
| RF-53 | Sirve el progreso de una ejecución en curso: capítulo, paso, rol, tareas abiertas y tokens de entrada concurrentes | `demostracion` |
| RF-54 | Sirve el estado plegado hasta el capítulo N y el log de eventos, para poder auditar por qué una escena se rechazó | `analisis` |
| RF-55 | Sirve una búsqueda por parecido sobre el manuscrito ya aceptado de una obra, para localizar un pasaje sin recordar sus palabras exactas | `demostracion` |

### 4.7 Recuperación por parecido y fuentes de fuera

| ID | Requisito | Verificación |
| --- | --- | --- |
| RF-60 | El Documentalista busca fuentes fuera del sistema con el marco de la escena —fecha, lugar y ámbito—. Es el único rol con acceso al exterior: ningún otro busca ni lee nada que no esté ya en el almacén | `inspeccion` |
| RF-69 | Cuando para un marco de escena no encuentra nada utilizable, el Documentalista deja constancia de la búsqueda infructuosa y la producción continúa. **Una escena sin respaldo no bloquea nunca**: baja OBJ-06 y el Arquitecto de arcos la saca en la auditoría de cierre (D-09) | `prueba` |
| RF-61 | De cada resultado aceptado se guarda el texto íntegro tal como se leyó, con su procedencia y la fecha de recogida, antes de trocearlo. Una `Fuente` de la que solo se conserva el enlace no vale como respaldo | `prueba` |
| RF-62 | El cuerpo entero de una fuente no entra nunca en la ventana de ningún agente: el Documentalista decide sobre resultados cortos y el volumen se queda en el almacén | `analisis` |
| RF-63 | Toda consulta por parecido lleva `k` y tope de tokens declarados para el rol que la hace, y lo recuperado se descuenta de su tope de ventana en lugar de sumarse aparte. Si no cabe, baja `k` | `prueba` |
| RF-64 | Se indexa solo el texto aceptado. Un borrador candidato o descartado no puede recuperarse nunca como eco | `prueba` |
| RF-65 | El Editor de estilo comprueba la fatiga léxica contra los ecos recuperados del registro acumulado, no contra el registro entero | `analisis` |
| RF-66 | El Planificador recibe contratos de escena y `Resumen de capítulo` parecidos a lo que va a planificar, nunca prosa | `inspeccion` |
| RF-67 | Ni el Verificador de continuidad, ni el Contable de estado, ni el Arquitecto de arcos, ni el Redactor consultan por parecido. Una búsqueda por semejanza no encuentra lo que falta y su fallo es silencioso | `inspeccion` |
| RF-68 | Cada recuperación queda en la `Traza`: consulta, colección, `k`, fragmentos devueltos y cuáles acabó usando el agente. Sin eso OBJ-08 no se puede medir | `analisis` |

### 4.8 La entrevista que completa el brief

**El problema.** El brief lo escribe una persona y viene incompleto como caso
normal (§2.4), pero hasta aquí la única respuesta del sistema a un brief
incompleto era rechazarlo nombrando el campo. Quien encarga una novela para
alguien no sabe de antemano qué se le va a pedir, tiene a menudo lo que hace
falta escrito en otra forma —una carta, una anécdota— y puede pedir cosas que
no casan entre sí, como un tono que no corresponde a la edad del destinatario.
Nadie en el sistema lo detectaba antes de gastar una obra entera.

**La decisión.** Un rol nuevo, el **Entrevistador**, con la tarea
`entrevistar`, completa el brief en pasadas sin estado. Cada pasada recibe lo
que la persona lleva escrito y lo que ha pegado, y devuelve el brief completado
hasta donde se puede, lo que sigue faltando y lo que se contradice. En cuanto el
brief está completo y no queda ninguna contradicción sin asumir, la misma pasada
da de alta la obra y la producción arranca.

```mermaid
flowchart LR
  P([Borrador y textos pegados]) --> E[Pasada de entrevistar]
  E --> V{Brief completo y sin<br/>contradicciones abiertas?}
  V -- no --> R([Propuesta, lo que falta<br/>y lo que se contradice])
  R -. la persona corrige .-> P
  V -- si --> O[Alta de Obra<br/>y Recuerdo]
  O --> M([Produccion, como en 4.1])
```

| ID | Requisito | Verificación |
| --- | --- | --- |
| RF-70 | El Entrevistador es el rol doce del censo y `entrevistar` es su única tarea, con carpeta propia en `tareas/`. No tiene ninguna herramienta, **no escribe ninguna entidad del almacén** —devuelve una propuesta, no artefactos— y actúa fuera del guion, antes de que la obra exista. Su tope de ventana es de 8 000 tokens, se ejecuta como mucho una pasada a la vez en la instalación y lo que ocupa abierta, el tope más el coste fijo del subagente, cabe en el 20 % de margen del techo sin quitarle nada a la tanda de una obra en curso | `prueba` |
| RF-71 | `POST /entrevistas` abre una entrevista y hace su primera pasada, y `POST /entrevistas/{id}/pasadas` hace la siguiente. Cada pasada recibe un borrador de brief con todos los campos opcionales, los textos pegados y las contradicciones que la persona da por asumidas, y **nada de las pasadas anteriores**: lo que quiera conservar lo vuelve a mandar. Si la ventana no cabe en el tope del rol, la pasada se rechaza diciendo cuánto sobra, y no se recorta ningún texto | `prueba` |
| RF-72 | Los campos que faltan los detecta el borde, no el agente. Después de cada pasada, el brief resultante se valida contra el mismo modelo que `POST /obras`, y lo que falta se devuelve con su ruta completa —`destinatario.edad`—, igual que en RF-01 | `prueba` |
| RF-73 | Lo que la persona escribió manda. Un campo escalar presente en el borrador no lo cambia ninguna pasada. En las listas, lo que la persona puso se conserva íntegro y en su orden, y la pasada solo puede añadir detrás. Un valor que aporta el agente y que no valida contra el modelo se descarta, y el campo sigue contando como que falta | `prueba` |
| RF-74 | El texto pegado entra en la ventana **como dato delimitado, nunca como instrucción**: cada texto va dentro de su propia marca, dentro de los datos del encargo, igual que el cuerpo de una `Fuente`. De él el Entrevistador extrae hechos, y cada hecho declara a qué campo del brief va y una **cita literal** del texto. Un hecho cuya cita no aparece tal cual en ninguno de los textos pegados, o cuyo campo no es uno de los del brief, se descarta y el descarte se cuenta | `prueba` |
| RF-75 | Un hecho que va a `destinatario.recuerdos` entra en el brief con su cita literal como valor, no con una paráfrasis. Así el `Recuerdo` que nace con el alta guarda un texto que la persona entregó (RD-16), y ningún rol del censo lo escribe (RF-07) | `prueba` |
| RF-76 | El Entrevistador detecta contradicciones de un vocabulario cerrado, `tipo_de_contradiccion`: `edad_contra_tono`, cuando el tono pedido no corresponde a la edad del destinatario, y `texto_contra_campo`, cuando un texto pegado dice otra cosa que un campo que la persona escribió. Cada contradicción nombra los campos en conflicto y trae evidencia citable. Se descarta la que no trae evidencia, la que nombra un campo que no existe, la de `edad_contra_tono` cuyo brief no tiene edad y tono, y la de `texto_contra_campo` cuya evidencia no aparece literal en ningún texto pegado. **No resuelve ninguna**: la devuelve como pregunta | Detección: `inspeccion`. Filtro y descarte: `prueba` |
| RF-77 | La persona puede dar por asumida una contradicción declarando su tipo en la pasada siguiente. Una contradicción asumida se sigue devolviendo, marcada como asumida, pero no bloquea el alta | `prueba` |
| RF-78 | Si al terminar la pasada el brief valida y no queda ninguna contradicción sin asumir, **la propia pasada da de alta la obra** exactamente como `POST /obras`: los recuerdos pasan a `Recuerdo` y la producción arranca. La pasada devuelve el `id_obra`, y la entrevista queda cerrada: pedirle otra pasada es un error que nombra la obra ya lanzada. Si el brief no está completo, no se crea nada. La pasada que lanza es la única orden de OBJ-07: las anteriores ocurren antes de que la obra exista | `prueba` |
| RF-79 | Cada entrevista es su propio espacio, identificado por `id_entrevista`, igual que una obra lo es por `id_obra` (RF-03). Cada pasada deja escrito lo que recibió, lo que devolvió, cuántos hechos y cuántas contradicciones se descartaron, y su `Traza`: tokens estimados y medidos, salida, coste y latencia. Nada de eso se borra ni se modifica. La obra que se lanza desde una entrevista anota en su cuerpo el `id_entrevista` del que sale | `prueba` |

**Decisiones del bloque.**

| ID | Decisión | Por qué |
| --- | --- | --- |
| D-20 | **Pasadas en frío, no una conversación con estado.** Desde fuera parece una conversación, pero dentro no hay historial: cada pasada recibe lo que la persona manda en ese momento | Toda tarea arranca en frío (`architecture.md` §3), y esa es la regla que hace el techo verificable antes de gastar. Una conversación guardada entraría entera en cada turno y crecería sin tope, que es lo que prohíbe la regla del tamaño. La pasada única y sin segunda vuelta se descarta porque deja sin cerrar precisamente lo que la entrevista tenía que resolver |
| D-21 | **El Entrevistador es un rol nuevo, no una tarea del Planificador** | Es lo que dice «un rol, una tarea»: el trabajo de completar un brief no lo cubre ningún tipo de tarea, así que se declara un rol en lugar de ensanchar uno. El Planificador actúa por capítulo, sobre una obra que ya existe, y darle esta tarea metería texto pegado en crudo en la ventana que planifica la trama |
| D-22 | **La obra se lanza sola en cuanto el brief está completo**, sin que la persona lo confirme | Es un paso menos entre el encargo y la obra, en la línea de OBJ-07. El precio es que lo que el agente extrae del texto pegado se convierte en `Recuerdo` sin que nadie lo revise. Se contiene con dos reglas mecánicas en lugar de con una confirmación: lo que la persona escribió manda (RF-73) y un recuerdo es siempre una cita literal de lo que ella entregó (RF-74, RF-75). El agente elige qué fragmento guardar, pero no puede redactar el recuerdo ni inventarlo |
| D-23 | **Los campos que faltan los detecta el borde, y las contradicciones el agente** | Que falte un campo es una cuestión de forma: el borde ya la resuelve con el modelo del brief, y pedírsela a un agente convertiría una respuesta segura en una probable. Que un tono no case con una edad es un juicio de dominio, y el backend no juzga nada del dominio (§2.1). No rompe «ningún agente valida su propia salida»: el Entrevistador juzga lo que escribió la persona, no lo que escribe él |
| D-24 | **La entrevista tiene un espacio propio, anterior a la obra**, y RD-02 lo admite | Cuando se entrevista todavía no hay `id_obra`, y toda tarea deja `Traza` (RNF-03). Se descarta reservar el `id_obra` en la primera pasada, porque cambiaría RI-01 y lo que cuenta OBJ-07. También se descarta no guardar nada, porque la entrevista quedaría sin medir |

**Criterio de aceptación.** Con un ejecutor fingido, un borrador al que le
faltan la edad y el tono, más una carta pegada que los contiene, se completa en
una pasada y lanza la obra, y sus recuerdos son citas literales de la carta. Un
borrador con edad 8 y un tono que no corresponde queda sin lanzar hasta que la
contradicción se asume. Y un texto pegado con una orden dentro no cambia ningún
campo que la persona escribió ni escribe nada en el almacén.

**De dónde sale.** `architecture.md` §2 (censo y «un rol, una tarea») y §3
(toda tarea arranca en frío); RF-01, RF-07 y RD-16; D-13 y D-14, que no se
tocan.

**Fuera de este bloque.** Más tipos de contradicción que los dos del
vocabulario; que una pasada recuerde las anteriores; que la persona confirme el
brief antes del alta (D-22); y cualquier comprobación de que lo que el
Entrevistador extrajo acabe apareciendo en la obra.

**Docs que se ponen al día en la fase 3.** `architecture.md`: el censo con el
rol doce, su entrada y su salida, su proyección, su tope, la tabla de gobierno,
el vocabulario de proceso `tipo_de_contradiccion` y la entrevista como espacio
anterior a la obra. `validators.md`: el método de cada requisito de este bloque
y la amenaza de la orden inyectada en el texto pegado. `AGENTS.md`: la
descripción de `architecture.md` pasa a decir doce agentes. `definitions.md` y
`domain-knowledge.md` no cambian: el `Recuerdo` sigue siendo lo que era.

### 4.9 Uso de los hechos por capítulo y cronología

**El problema.** Tres trabajos posteriores necesitan saber dónde vive cada
hecho de la biblia en el texto y cuándo ocurre cada cosa: el validador que
comprueba que cada elemento personalizado aparece en algún capítulo, el
fichero que se le pasa al demostrador formal y la propagación de un cambio del
lector a los capítulos afectados. Hoy ninguno de los dos datos existe: una
ficha no sabe en qué capítulos se ha usado y no hay forma de listar los sucesos
de la obra en orden con quién estaba presente. Sin esto, los tres se quedan sin
suelo o tienen que releer la prosa cerrada, que es justo lo que la regla del
tamaño prohíbe.

**Qué es un hecho de la biblia.** Las fichas de la capa Mundo que el texto
nombra: `Personaje`, `Lugar`, `Objeto`, `Faccion` y `Evento`. Quedan fuera
`Fuente`, `Concepto`, `Practica` y `RegistroLinguistico`, que respaldan o
filtran el texto sin ser algo de lo que el texto hable, y `Recuerdo`, que es la
materia prima de la que sale la ficha `personal` y no la ficha misma.

| ID | Requisito | Verificación |
| --- | --- | --- |
| RF-80 | Cada uso de un hecho de la biblia en un capítulo cerrado queda registrado como una `Mencion`: artefacto de la capa Obra, inmutable y de memoria de obra, con el `id` del hecho y el número del capítulo. Materializa la relación referencial `menciona`. **La ficha del hecho no se toca** (D-26) | `prueba` |
| RF-81 | Las `Mencion` las escribe el Archivero en el paso 10, `destilar`, en la misma unidad que el `Resumen de capítulo`: o se guardan las dos cosas o ninguna. Ningún otro rol las escribe (D-25) | `prueba` |
| RF-82 | Para anotarlas, la ventana del Archivero lleva un material nuevo, `indice_de_la_biblia`: una línea por hecho con su `id`, su tipo, su nombre y su licencia, y nada más de la ficha. No es el canon: el Archivero sigue sin ver atributos del mundo | `prueba` |
| RF-83 | El almacén rechaza una `Mencion` que no traiga el `id` del hecho o cuyo `id` no sea un hecho de la biblia de esa misma obra. El rechazo es el de RF-23: `Crítica` bloqueante con objeto el artefacto | `prueba` |
| RF-84 | En qué capítulos se usa un hecho **se deriva, no se guarda**: son los capítulos distintos de sus `Mencion`, en orden. Una mención repetida no duplica el capítulo | `prueba` |
| RF-85 | Todo `EventoEstado` lleva, además de la fecha y el lugar resultantes, `presentes`: los `id` de los `Personaje` que estaban cuando ocurrió, escritos por el Contable. La fecha resultante del evento, el momento de un `Evento` del mundo y el nacimiento de un `Personaje` —`fechas.nacimiento`— se escriben en fecha ISO parcial: `AAAA`, `AAAA-MM` o `AAAA-MM-DD` (D-28) | `inspeccion` |
| RF-86 | La cronología es **una vista derivada, no una tabla guardada**: una fila por `EventoEstado` y por `Evento` del mundo, con el suceso, el momento, el lugar, el capítulo —vacío si el `Evento` no pertenece a ninguno— y los presentes, cada uno con su `id`, su nombre y su fecha de nacimiento. Se ordena por momento y, a igualdad, por capítulo; lo que no trae momento va al final. Copia lo escrito: no calcula fechas ni edades (D-27) | `prueba` |
| RF-87 | La API sirve las dos cosas en dos rutas de lectura: `GET /obras/{id}/hechos`, cada hecho con su tipo, su nombre, su licencia y los capítulos en que se usa, filtrable por tipo y por licencia; y `GET /obras/{id}/cronologia`, la vista de RF-86. No añaden ninguna operación de escritura y entran en `backend/openapi.yaml` (RI-10) | `prueba` |
| RF-88 | En el recorrido en seco, cerrar un capítulo deja escritas sus menciones y la cronología trae el suceso del capítulo con sus presentes y su fecha de nacimiento | `demostracion` |

| ID | Decisión | Por qué |
| --- | --- | --- |
| D-25 | **Las menciones las anota el Archivero al destilar.** No el Redactor, ni el Contable, ni un rol nuevo | «Quien escribe lo anota al cerrar» no puede ser el Redactor: actúa por escena en el paso 3 y lo que declarase quedaría desfasado en cuanto el Revisor o el Editor de estilo tocan el texto. El Contable es el único punto por el que el mundo cambia, y un uso no es un cambio del mundo: meterlo ahí mezcla dos cosas en el rol que más cuesta vigilar. Un rol doce ensancharía el censo sin trabajo de dominio nuevo, porque destilar ya es escribir lo que queda de un capítulo cuando su prosa deja de leerse, y qué hechos nombra es exactamente eso. La regla del Archivero se mantiene: no escribe hechos del mundo ni prosa |
| D-26 | **El uso es un artefacto aparte, no un campo de la ficha.** Tampoco un campo del `Resumen de capítulo` | Un campo en la ficha que crece capítulo a capítulo choca con la inmutabilidad de `canon` y `personal` y con «el mundo solo cambia por `EventoEstado`». Dentro del resumen, saber dónde se usa un hecho obliga a recorrer todos los resúmenes, y eso crece con la obra. Con un artefacto de solo añadir la pregunta es una consulta por `id`, y «en qué capítulos» se deriva igual que el estado. El índice de la biblia que recibe el Archivero lee cuatro campos por ficha sin interpretarlos: es proyección, no decisión. Crece con la biblia, no con la prosa, y es mucho más corto que el canon que ya reciben el Planificador y el Verificador |
| D-27 | **La cronología se deriva al consultar.** No es un artefacto del Contable ni una caché | Todo lo que lleva ya está escrito: la fecha, el lugar y los presentes en el `EventoEstado`, el suceso histórico en el `Evento` y el nacimiento en la ficha. Guardarlo otra vez sería un segundo sitio que mantener al día, y «el estado no se almacena, se deriva». Ordenar por la fecha escrita no es aritmética de calendario: no reabre D-05 |
| D-28 | **`presentes` en el `EventoEstado` y fechas ISO parciales.** El formato lo piden el prompt y el esquema del rol que escribe; el almacén no lo comprueba en esta versión | Sin presencia por suceso no se puede afirmar que un personaje no está en dos sitios a la vez, y sin un formato de fecha fijo el volcado formal tendría que interpretar texto libre. La parcial admite lo que de verdad se sabe de una época —a veces solo el año— sin inventar el día. Comprobar el formato al escribir es trabajo del volcado formal, que es quien lo consume |
| D-29 | **Alcance: registrar, derivar y servir.** La propagación de cambios del lector es de §4.18, el validador de elementos personalizados de §4.15 y el volcado al demostrador formal de §4.16 | Son los consumidores de esto y cada uno tiene su propia pasada del ciclo. Servirlo por la API ya ahora es lo que permite a la interfaz enlazar cada ficha con sus capítulos sin volver a mover la frontera |

**Lo que queda fuera.** La comprobación de que el Archivero no se ha dejado
ningún hecho sin anotar, y la validación del formato de fecha al escribir
(D-28).

**Documentos que pone al día la fase 3.** `definitions.md` (la `Mencion` en la
capa Obra, la cronología como vista y el formato de fecha) y el árbol de la
obra y las relaciones de `domain-knowledge.md`; `architecture.md` (entrada y
salida del Archivero y del Contable, proyecciones, memorias y tabla de
gobierno); y `validators.md` (lo nuevo en la matriz de cobertura, y el hueco de
completitud de las menciones). Trazabilidad: sale de `definitions.md`
(relaciones referenciales) y de `architecture.md` §2, §3 y §6.

### 4.10 Punto de guardado por capítulo y límite de reintentos

**El problema.** RF-04 y RF-05 prometían reanudar sin repetir y reintentar hasta
un tope, pero no decían qué es «lo último cerrado» cuando la producción se corta
a destiempo ni qué pasa al agotar el tope salvo detener. En el código eso deja
tres fallos. Si el proceso muere, el hilo de producción muere con él y nadie lo
relanza. Un capítulo a medias se vuelve a planificar encima de lo que ya había y
duplica escenas y borradores. Y un corte entre `plegar` y la marca `cerrado`
deja `EventoEstado` de un capítulo que no ha cerrado, que es justo lo que RF-40
prohíbe. A eso se suma que el tope es un único número global y que agotarlo
detiene siempre la obra, también cuando lo que falló fue una comprobación que no
produce testigo para nadie.

Va antes que cualquier otro cambio por dos razones. Todas las tareas que vengan
después añaden pasos al bucle, y cada paso nuevo necesita saber cuántas veces se
reintenta y qué hace al agotarse. Además, esto es la mitad de lo que habrá que
especificar en el verificador formal del sistema.

**La decisión, en una frase.** El capítulo cerrado es el único punto de guardado.
Cerrar un capítulo es una sola transacción. Reanudar, por la causa que sea,
vuelve a ese punto: descarta lo que quedó a medias y rehace el capítulo
siguiente desde el paso 1. Y cada paso del guion declara cuántas veces se
reintenta y qué pasa cuando se agota.

| ID | Requisito | Verificación |
| --- | --- | --- |
| RF-90 | **Punto de guardado.** Cerrar el capítulo N es una sola transacción: los `EventoEstado` y el estado en N del Contable, lo que escribe el Archivero, la marca `cerrado` del capítulo y la retirada de su memoria de capítulo. Lo que `plegar` y `destilar` devuelven no se escribe hasta que las dos tareas han terminado. Si un artefacto sale malformado, se rechaza dentro de esa misma transacción, igual que en RF-23. Antes del commit no existe nada del cierre; después existe entero | `prueba` |
| RF-91 | **Reanudar es volver al último punto de guardado.** Cada vez que se camina una obra, sea el arranque, un `reanudar` o un relanzamiento tras una caída, primero se hace lo mismo: las `Traza` que quedaron abiertas se cierran como interrumpidas; todo lo que cuelga de capítulos sin cierre vivo —los posteriores al último cerrado y, en una versión que reescribe capítulos sueltos, los que reescribe (RF-176)— se caduca, sin borrar (RD-07); sus fragmentos salen del índice y su estado materializado se descarta; y el índice del último capítulo cerrado se completa si le falta algo. Después, el capítulo siguiente empieza en el paso 1 | `prueba` |
| RF-92 | **Ni duplica ni pierde.** Tras un corte en cualquier punto, cada capítulo cerrado tiene exactamente un `Capitulo` vivo, un juego de `EventoEstado`, un estado en N y un `Resumen de capítulo`. El manuscrito servido es el mismo que antes del corte más lo que se cierre después. Lo que se pierde es solo el trabajo del capítulo que estaba abierto | `prueba` |
| RF-93 | **Relanzar tras una caída no pide ninguna orden.** Al arrancar, el backend relanza toda obra que no esté detenida y que no haya terminado. «Terminada» quiere decir que consta la auditoría de cierre (RF-94). Así OBJ-07 sigue valiendo aunque la máquina se reinicie | `prueba` |
| RF-94 | **La auditoría tiene también su punto de guardado.** Las críticas de `auditar` se escriben en una sola transacción junto con la constancia de hasta qué capítulo se ha auditado. Al reanudar, si el último capítulo cerrado tenía auditoría pendiente y no consta, se audita antes de abrir el siguiente. Cuando la auditoría de cadencia cae en el último capítulo, coincide con la de cierre y corre una sola vez | `prueba` |
| RF-95 | **El tope y la política están escritos en el guion.** Cada paso de `guion.toml` y cada tarea fuera del guion declaran `reintentos` (el número de intentos, uno o más) y `al_agotarse`. Si falta alguno de los dos, el guion no carga | `prueba` |
| RF-96 | **`al_agotarse` es un vocabulario cerrado con tres valores.** `detener_obra`: la obra queda detenida con la tarea, el intento y el motivo, y sin ningún artefacto a medio escribir. `critica_abierta`: el backend escribe la `Crítica` de RF-99 y la producción sigue. `seguir`: la producción sigue y la constancia del intento queda en la `Traza`, igual que la búsqueda infructuosa de RF-69 | `prueba` |
| RF-97 | **Qué política toca a cada paso.** `detener_obra` para lo que produce el testigo del paso siguiente: `planificar`, `redactar`, `revisar`, la costura del paso 7, `plegar`, `destilar` y `poblar_mundo`. `critica_abierta` para las comprobaciones: las cribas de los pasos 4, 6 y 8, y `auditar`. `seguir` para `documentar`, por D-09. El tope de partida es dos intentos en todos los pasos | `inspeccion` |
| RF-98 | **Qué es un intento fallido y cómo se cuenta.** Un intento falla cuando el ejecutor devuelve un error o no contesta a tiempo, o cuando lo que el subagente entregó al final no pasa un hook de su paso (RF-126). Un artefacto malformado no es un intento fallido: sigue siendo la `Crítica` bloqueante de RF-23, salvo en `planificar` (RF-182). Una tarea cortada por una caída tampoco cuenta, porque su `Traza` se cierra como interrumpida. Cada encargo empieza a contar desde 1 y, como el capítulo a medias se rehace, el contador vuelve a empezar con él. Toda `Traza` fallida registra su intento y su motivo | `prueba` |
| RF-99 | **La crítica «no comprobado».** La escribe el backend, no un rol, igual que la de un artefacto malformado. Su objeto es la unidad del encargo y su dimensión la del encargo. Sale con severidad `bloqueante`, estado `abierta` y, como evidencia, la `Traza` del último intento y su motivo. No se enruta: no regenera ni manda a revisión. Se queda abierta y el capítulo se cierra marcado, que es como el Arquitecto de arcos la ve (RF-33) | `prueba` |

**Decisiones de este cambio.**

| ID | Decisión | Por qué |
| --- | --- | --- |
| D-30 | **El único punto de guardado es el capítulo cerrado, y lo marca la transacción de cierre.** No se guarda el avance paso a paso dentro del capítulo | Guardar por paso perdería menos trabajo, pero obligaría a reconstruir en qué vuelta del bucle estaba cada escena, y el recorrido dejaría de ser reproducible (RNF-04). El capítulo ya es la frontera en la que el mundo cambia (RF-40): hacer que también sea la frontera de la durabilidad no añade ninguna noción nueva |
| D-31 | **Lo que quedó a medias se descarta entero y se rehace**, incluidas las `Fuente` ya recogidas en ese capítulo | Salvar las fuentes ahorraría la búsqueda externa, pero cuelgan de escenas que el nuevo plan no tendrá, y dejaría una segunda forma de que algo del capítulo anterior al corte entre en el siguiente. Rehacer desde el paso 1 deja un solo camino, que es el mismo de un capítulo recién abierto |
| D-32 | **Marcar no es modificar.** A un artefacto inmutable (`EventoEstado`, `Fuente`, `Resumen de capítulo`, `Decisión`, `Recuerdo`) y a un `Borrador` aceptado se les puede poner la marca de caducado. Solo esa marca, solo una vez, y nunca se quita | Sin esto no hay forma de descartar un capítulo a medias sin borrar, y borrar lo prohíbe RD-07. RF-24 no se toca: el contenido de un inmutable sigue sin cambiar. Lo único que se añade es la marca que el propio RD-07 ya llama «caducar» |
| D-33 | **Tras una caída, la obra se relanza sola al arrancar el backend.** `POST /reanudar` sigue sirviendo para lo que el editor detuvo o para una obra detenida por `detener_obra` | Exigir `reanudar` tras cada caída suma una intervención humana por corte y rompe OBJ-07 y RNF-08. Relanzar al arrancar pasa por el mismo camino que `reanudar` (RF-91), así que no hay dos formas de reanudar que puedan divergir |
| D-34 | **Qué se hace al agotar los intentos se declara por paso en el guion, con vocabulario cerrado, y el contador vuelve a empezar con el capítulo** | Detener siempre dejaría parada una obra que podría terminar, porque la comprobación que falla no produce testigo para nadie. Rehacer el capítulo entero al agotar una tarea sale caro, y lo normal es que el fallo sea del proveedor y no del capítulo. Acumular intentos a lo largo de las caídas exigiría decidir cuándo dos encargos son «el mismo» después de replanificar. Ponerlo en el guion, y no en `ajustes.py`, deja cada tope junto al paso que gobierna, como pide RF-10 |

**Qué retira.** El tope global de reintentos de `ajustes.py` desaparece, porque
el tope pasa al guion. RF-04 y RF-05 remiten ahora a esta subsección. El
criterio 5 de §10 habla de trabajo cerrado y no de trabajo aceptado, porque lo
aceptado de un capítulo que no llegó a cerrar se descarta a propósito (D-31).

**Qué queda fuera.** No hay puntos de guardado dentro del capítulo. No se
distingue una tarea que falla siempre de una que falla por casualidad: si el
mismo capítulo detiene la obra una y otra vez, se ve en la `Traza`, pero nada lo
corta automáticamente. No hay varias obras produciéndose a la vez (§11). Y la
interfaz HTTP no cambia: la ficha de obra ya dice si está detenida, y el motivo
queda en el control de ejecución.

**De dónde sale.** `architecture.md` §4, el ciclo de vida del capítulo, y §5, el
tope de vueltas; RF-04, RF-05, RF-24, RF-33, RF-40 y RF-69; RD-07; OBJ-07 y
RNF-08.

**Documentos que hay que poner al día en la fase 3.** En `architecture.md`: §2,
el vocabulario de proceso `al_agotarse`; §4, el punto de guardado, la
reanudación y la política por paso; y §7, el árbol de `ajustes.py`. En
`validators.md`: §6, la tabla de pruebas, y §8, la matriz de cobertura, con los
métodos de RF-90 a RF-99. `definitions.md` y `domain-knowledge.md` no cambian,
porque esta enmienda no toca la ontología.
### 4.11 El subagente de tarea no ve el andamiaje de desarrollo

**Contexto.** El repositorio lleva su andamiaje de desarrollo con Claude Code:
un `CLAUDE.md` de verdad en la raíz, la skill `grill-me` commiteada en
`.claude/skills/`, los comandos y subagentes propios de `.claude/commands/` y
`.claude/agents/`, y en `.claude/mcp.json` un servidor MCP de navegador para
mirar la futura lectura web. Nada de eso es backend: lo gobierna `AGENTS.md`.
Lo que sí toca al backend es quién lo acaba leyendo.

**Problema.** El ejecutor lanza cada subagente de tarea con el repositorio como
directorio de trabajo, y Claude Code descubre por su cuenta el `CLAUDE.md` de
ese directorio, con `AGENTS.md` dentro. Medido en la máquina de desarrollo con
la misma orden del ejecutor —sin herramientas y con una instrucción de sistema
de una línea—: **10 751 tokens de entrada lanzado desde el repositorio, 1 548
lanzado desde un directorio vacío**. Los 10 256 que hasta ahora se tenían por
«coste fijo del subagente» eran, casi enteros, el ciclo de edición de este
repositorio colándose en la ventana del Redactor, del Contable y de los otros
nueve. Rompía dos cosas a la vez: RF-11, porque es material que ninguna
proyección declara, y el techo, porque cada `CLAUDE.md` más largo ensanchaba en
silencio el coste de abrir cualquier tarea. Escribir el `CLAUDE.md` como pieza
completa lo habría empeorado.

**Alternativas descartadas.** Recortar el `CLAUDE.md` para que pese poco: no
arregla nada, solo abarata la fuga, y deja instrucciones de desarrollo en la
ventana de un rol de la novela. El modo `--bare` del CLI: deja de descubrir
`CLAUDE.md`, pero solo admite autenticación por clave de API, y el backend no
gestiona claves (D-08). El modo `--safe-mode`: su propia ayuda lo describe como
modo de diagnóstico para una configuración rota, y apaga toda personalización
sin distinguir, incluida la que una tarea posterior quiera pasar a propósito por
la orden.

| ID | Requisito | Verificación |
| --- | --- | --- |
| RF-100 | Cada subagente de tarea arranca en un directorio de trabajo vacío, propio de esa tarea y fuera del repositorio, que se descarta al terminar. No descubre ni carga el `CLAUDE.md`, el `AGENTS.md` ni nada de `.claude/` del repositorio. El ejecutor no admite que se le indique otro directorio | `prueba` |
| RF-101 | El coste fijo del subagente es la entrada medida de un subagente aislado según RF-100, con la instrucción de sistema del rol y las herramientas del rol más equipado —el Documentalista—, redondeada al alza al medio millar: **3 500 tokens**, un solo valor para todos los roles. Cambiar de versión del CLI obliga a volver a medirlo | `analisis` |
| RF-102 | Ningún subagente de tarea recibe servidores MCP: la orden lleva `--strict-mcp-config` y nunca `--mcp-config`. El servidor de navegador de `.claude/mcp.json` es del desarrollo y solo lo carga quien lo pide por su nombre | `prueba` |

| ID | Decisión | Por qué |
| --- | --- | --- |
| D-35 | **El aislamiento del subagente de tarea es por directorio de trabajo, no por opción del CLI.** Un directorio temporal vacío por tarea, creado y borrado por el ejecutor | Es lo único que no depende de cómo cada versión del CLI llame a sus modos, no toca la autenticación (D-08) y no apaga nada que la orden pase a propósito. Es además la lectura literal de «toda tarea arranca en frío» (`architecture.md` §3): tampoco arranca con el contexto del sitio desde el que se la lanza. El directorio no guarda nada de lo que el sistema produce: nace vacío y muere vacío, así que no contradice RD-08 |
| D-36 | **El coste fijo se vuelve a medir con el aislamiento puesto y baja de 10 500 a 3 500.** Un solo valor, el del rol más equipado | Mantener 10 500 sería mantener una medida de algo que ya no ocurre. Un valor por rol afinaría la anchura del Documentalista frente a los demás, pero la diferencia —1 548 sin herramientas frente a 3 191 con las dos de búsqueda— cae dentro del margen del 20 % y un solo número se comprueba de un vistazo. Con él las tandas se ensanchan: el Verificador pasa de cuatro a seis a la vez |
| D-37 | **El servidor MCP de navegador es Playwright, versión fijada, y vive en `.claude/mcp.json`**, que Claude Code no carga solo: se pasa con `--mcp-config` en la sesión que tiene que mirar la lectura web | Cargarlo en todas las sesiones gastaría las definiciones de sus herramientas en cada conversación que no mira nada. Playwright corre sin cabeza y sin perfil persistente, que es lo que hace repetible una comprobación visual; Chrome DevTools exige un Chrome instalado y es más difícil de lanzar sin nadie delante. Una copia en `.mcp.json` para que se cargase sola serían dos ficheros diciendo lo mismo hasta que dejasen de hacerlo |

Traza de este bloque: `architecture.md` §3 (toda tarea arranca en frío y
presupuesto), RF-11, RF-13 y D-08.

### 4.12 Versiones de la obra

**El problema.** Una obra tiene hasta aquí un solo manuscrito, y lo que se
escribe es a la vez lo que se lee: no hay forma de rehacer una parte sin perder
la que había, ni de decir cuál de dos textos es el que se entrega. Rehacer un
capítulo cerrado deja además un mundo que ya no cuadra con lo que viene
después: los `EventoEstado`, las `Mencion` y el estado en N del capítulo
rehecho cambian, y los capítulos siguientes se escribieron sobre el mundo
viejo. La rúbrica pide como invariante que la versión anterior se conserve
siempre, y una tarea posterior tiene que poder demostrarlo sobre el modelo del
sistema, así que no basta con guardarla: tiene que poder servirse tal como era.

**La decisión, en una frase.** Una obra tiene versiones numeradas. El editor
ordena «rehaz desde el capítulo N»: nace la versión siguiente, que comparte con
la anterior los capítulos 1 a N-1 y reescribe de N al final. Cada versión tiene
su propio mundo, y la anterior conserva el suyo tal como quedó. Publicar una
versión terminada es una orden aparte, que se da o no se da.

| ID | Requisito | Verificación |
| --- | --- | --- |
| RF-110 | **Una obra tiene versiones numeradas desde 1.** El alta crea la 1 en la misma transacción que la `Obra`. Cada versión guarda su número, la versión de la que sale, **qué capítulos cambiaron respecto de ella** y cuándo nació y cuándo terminó. Una versión termina cuando consta su auditoría de cierre (RF-94). Nada de eso se borra ni se modifica, salvo la marca de terminada, que se pone una vez | `prueba` |
| RF-111 | **Rehacer desde el capítulo N es una orden del editor**, `POST /obras/{id}/versiones` con `desde_capitulo`. Solo se admite si la última versión ha terminado y no hay producción en marcha para la obra, y N va de 1 al último capítulo. Crea la versión siguiente, que anota como cambiados los capítulos de N al último, retira de su mundo lo que colgaba de esos capítulos (RF-112), saca sus fragmentos del índice y arranca la producción, que empieza en el capítulo N por el camino de siempre (RF-91). No es mantenimiento: es una decisión editorial, y nada obliga a darla (RNF-08) | `prueba` |
| RF-112 | **El mundo de una versión.** Todo artefacto lleva la versión en la que se escribió. Al rehacer desde N, lo que cuelga de un capítulo N o posterior —lo que lleva ese capítulo y lo que no lleva capítulo pero lo escribió una tarea de ese capítulo, según su `Traza`— recibe **la marca de relevado** con el número de la versión nueva, junto con la de caducado: solo una vez y sin poder quitarla, como en D-32. La `Traza` no se releva: es el registro. Lo escrito antes del capítulo 1, la biblia de partida del Constructor de mundo, el `Recuerdo` y la `Obra`, es común a todas las versiones, salvo el hecho al que un lector cambia el nombre (§4.18, RF-173) | `prueba` |
| RF-113 | **Qué ve cada versión.** La versión V ve lo escrito en V o antes que no haya relevado V o una anterior, y que no esté caducado por otro motivo. La última versión ve exactamente lo que no está caducado, así que la producción no cambia: sigue leyendo solo lo vivo | `prueba` |
| RF-114 | **La versión anterior se conserva siempre.** Rehacer y producir la versión nueva no cambia nada de lo que se sirve de una versión anterior: su manuscrito, sus capítulos, sus críticas, su estado plegado, sus hechos con su uso y su cronología son los mismos antes y después | `prueba` |
| RF-115 | **El estado en N es de su versión.** La caché del estado materializado lleva la versión que lo plegó. Rehacer desde N no la borra: la releva, igual que a los artefactos. Descartar un capítulo a medias (RF-91) sí borra, y solo lo de la versión en curso | `prueba` |
| RF-116 | **Publicar es un acto explícito**, `POST /obras/{id}/versiones/{n}/publicar`. Solo se publica una versión terminada; terminar no publica. Cada publicación se añade a un registro de solo añadir, y la versión publicada es la de la última publicación, así que volver a publicar una anterior también queda escrito. Publicar pasa por **un solo sitio del código**, que es donde entra la puerta de publicación (RF-146) | `prueba` |
| RF-117 | **Lecturas por versión.** Manuscrito, capítulo, críticas, estado, hechos y cronología admiten `version`. Sin ella sirven **la versión de referencia**: la publicada si hay alguna y, si no, la última. Una versión que no existe es un 404. El manuscrito dice qué versión sirve y si está publicada. `GET /obras/{id}/versiones` lista las versiones con su base, sus capítulos cambiados, si ha terminado y cuál es la publicada, y la ficha de la obra dice cuál está en curso y cuál publicada. Trazas, progreso y búsqueda de pasajes siguen siendo de la producción en curso | `prueba` |
| RF-118 | **Descartar un capítulo a medias sigue la misma regla de qué cuelga de un capítulo.** Lo que RF-91 caduca incluye también lo que no lleva capítulo pero escribió una tarea de un capítulo descartado, como un `Evento` que el Planificador añadió al mundo | `prueba` |

**Decisiones de este cambio.**

| ID | Decisión | Por qué |
| --- | --- | --- |
| D-40 | **Las versiones van en fila: la nueva sale siempre de la última, y solo cuando la última ha terminado.** No hay ramas ni dos versiones produciéndose a la vez | Es la forma más pequeña que cumple lo pedido. Ramas obligarían a elegir de cuál sale cada rehacer y a producir dos a la vez, que es justo «varias obras a la vez» (§11) con otro nombre. Exigir la última terminada deja además toda versión anterior terminada, y por tanto publicable, que es un invariante sencillo de demostrar |
| D-41 | **Cada versión tiene su propio mundo, y la biblia se versiona junto a la novela.** Los capítulos compartidos no se copian: cada fila lleva la versión en que nació y, si la hay, la que la relevó, y lo que ve una versión se deduce de esas dos marcas | Copiar los capítulos 1 a N-1 duplicaría el almacén en cada rehacer y dejaría dos filas diciendo lo mismo. Un mundo único que evoluciona sin volver atrás haría incoherente la versión vieja en cuanto la nueva emite sus eventos, que es lo que Álvaro descartó. Con dos marcas la producción no cambia —sigue leyendo lo vivo— y la regla de visibilidad es una comparación de números. Cierra la decisión abierta de `architecture.md` §8 sobre la biblia. La biblia de partida es común porque ninguna versión la reescribe |
| D-42 | **Rehacer es desde un capítulo N hasta el final**, no una lista de capítulos sueltos | Lo que viene después de un capítulo rehecho se escribió sobre su mundo: dejarlo tal cual lo dejaría contradiciendo al capítulo nuevo. Aun así, qué cambió se registra como lista y no como un número, para que quien lo lea no dependa de la regla con que se calculó |
| D-43 | **Publicar es un registro de solo añadir y pasa por un solo sitio.** Sin ella, las lecturas sirven la publicada si la hay y si no la última | Una marca en la versión se perdería al publicar otra; el registro guarda también las vueltas atrás. Un solo punto de paso es donde se engancha la puerta de publicación (RF-146), sin repartirla por la API. Servir la última mientras no haya publicada mantiene lo que el editor ve hoy durante la producción, y la respuesta dice cuál sirve para que no se confunda con la publicada |
| D-44 | **El estado materializado se releva con su versión en vez de borrarse** | Es caché, pero no se recalcula sola: quien pliega es el Contable, y volver a plegar una versión vieja costaría tareas sin producir nada. Borrarla dejaría la versión anterior sin estado que servir, que es incumplir RF-114 por la puerta de atrás |

**Qué retira.** La salvedad de §4.9 sobre las menciones de un capítulo que se
regenera: ahora se relevan con su capítulo. Y RF-25 deja de borrar el estado de
los capítulos que se rehacen: lo releva (RF-115).

**Qué queda fuera.** Qué cambia en la entrada de los capítulos que se
reescriben: rehacer vuelve a producir sobre el mismo brief y la misma biblia de
partida; cambiar el nombre de un hecho es el otro tipo de versión, de §4.18.
Rehacer la biblia de partida entera. Buscar pasajes en una
versión que no es la en curso. Borrar o archivar versiones, que no se hace
nunca (RD-07). OBJ-07 no cambia: cuenta las órdenes hasta la obra cerrada, y
rehacer y publicar llegan después.

**De dónde sale.** `architecture.md` §3 (estado como pliegue, «diferencia
legible entre versiones») y §4 (el capítulo cerrado como punto de guardado);
RF-24, RF-25, RF-91 y RF-94; RD-07 y RD-08; D-32; RNF-08.

**Documentos que hay que poner al día en la fase 3.** `architecture.md`: §2, la
versión como entidad de producción; §3, el estado por versión; §4, rehacer y
publicar; §6, la tabla de gobierno; y §8, retirando la decisión de la biblia.
`validators.md`: §6, la tabla de pruebas, y §8, la matriz de cobertura, con los
métodos de RF-110 a RF-118. `definitions.md` y `domain-knowledge.md` no cambian:
la versión es de la capa de producción y no toca la ontología de la obra ni la
del mundo.

### 4.13 Los dos hooks

**El problema.** Lo que un subagente de prosa entrega solo se miraba después
de darlo por bueno: una salida sin el `Borrador` que el paso espera, o con un
tipo que su rol no escribe, se descubría al guardar, y entonces ya no había
nadie que la corrigiese. Y las palabras o temas que el comprador vetó en el
brief (`destinatario.vetos`) se guardaban y nadie las miraba: un Redactor podía
escribir justo lo que se le había pedido que no escribiera y la escena llegaba
al manuscrito.

**La decisión, en una frase.** Los subagentes que escriben la prosa llevan dos
hooks `Stop` de Claude Code, pasados en la propia orden del ejecutor: uno
comprueba que lo entregado está bien formado y otro que no contiene nada
vetado. Si alguno no pasa, el subagente no puede terminar: recibe el motivo y
tiene que corregir y volver a entregar. El veredicto queda en la `Traza`.

```mermaid
flowchart LR
  E([Encargo de prosa]) --> S[Subagente escribe]
  S --> H{Pasan los<br/>dos hooks?}
  H -- si --> R[El ejecutor repite<br/>las comprobaciones]
  H -- "no, primera vez<br/>y cabe en la reserva" --> V[Recibe el motivo<br/>y corrige] --> R
  H -- "no, ya corrigio<br/>o no cabe" --> R
  R -- pasa --> G([Se guarda, veredicto en la Traza])
  R -- no pasa --> F([Intento fallido: reintentos<br/>y al_agotarse del paso])
```

| ID | Requisito | Verificación |
| --- | --- | --- |
| RF-120 | Cada paso del guion declara en `guion.toml` qué hooks lleva su subagente, con un vocabulario cerrado de dos valores: `validar_capitulo` y `policy`. Los llevan los tres pasos que escriben prosa —3 `redactar`, 5 `revisar` y 7, la costura—; `validar_capitulo`, y no `policy`, lo llevan además los dos que escriben datos al cerrar el capítulo, 9 `plegar` y 10 `destilar` (RF-209); y ningún otro. Las cribas del paso 8, aunque las haga el mismo rol que cose, no. Un hook que no esté en el vocabulario no carga el guion | `prueba` |
| RF-121 | Los hooks son hooks `Stop` de Claude Code de verdad y viajan en la orden del ejecutor, en `--settings` con JSON en línea. El aislamiento de §4.11 no se toca: el subagente sigue arrancando en su directorio vacío, sin `CLAUDE.md`, sin `.claude/` y sin MCP. Un encargo sin hooks lleva la misma orden que antes, sin `--settings` | `prueba` |
| RF-122 | Cada hook es un programa del paquete, `python -m novela.ganchos <hook> <tarea>`. Lee la entrada que le da Claude Code —de ella, solo el último mensaje del agente y si ya ha bloqueado en ese turno—, no abre la base de datos, no escribe nada en disco y no llama a ningún modelo. El esquema y el contrato los lee de `tareas/<tarea>/`, que es entrada versionada (RD-09); la lista de vetos y la reserva de la vuelta le llegan en variables de entorno del proceso. Si bloquea, sale con código 2 y el motivo por su salida de error; si no, sale con 0 | `prueba` |
| RF-123 | **`validar_capitulo` comprueba la forma, y nada del contenido.** La salida es un objeto JSON con la lista `artefactos`; cada artefacto trae `tipo` y `cuerpo`; cada tipo es uno de los que el contrato de la tarea deja escribir; el tipo principal del `esquema.json` de la tarea aparece al menos una vez y con todos los campos que su esquema declara; y todo `Borrador` trae `texto` no vacío. Las comprobaciones son una lista a la que se añaden otras sin tocar el enganche; la de nombres de la biblia es la única que mira el texto (RF-145) | `prueba` |
| RF-124 | **`policy` aplica lo vetado.** Busca las tres listas de §4.14, con su comparación normalizada, en el `texto` de cada `Borrador` y cada `Parrafo` de la salida. Si algo aparece, bloquea nombrando lo que encontró. Sin nada que coincida, no bloquea nunca | `prueba` |
| RF-125 | **Una vuelta de corrección por intento.** Un hook bloquea solo la primera vez en el turno: si ya bloqueó uno, el siguiente `Stop` termina. Tampoco bloquea si la vuelta no cabe en la reserva del paso (RF-128). El motivo que devuelve no pasa de 1 000 caracteres | `prueba` |
| RF-126 | **El veredicto que cuenta es el del ejecutor.** Al terminar el subagente, el ejecutor aplica las mismas comprobaciones, con las mismas funciones, a lo que entregó al final. Si alguna no pasa, el intento ha fallado y se aplican el `reintentos` y el `al_agotarse` de su paso (§4.10): los tres pasos con hooks declaran `detener_obra` | `prueba` |
| RF-127 | La `Traza` de cada intento con hooks guarda en su cuerpo, en `ganchos`, lo que cada hook dijo durante la sesión —de qué hook, si bloqueó y con qué motivo, leído de los eventos que el CLI emite con `--include-hook-events`— y el veredicto final del ejecutor por hook. Se guarda también cuando el intento falla | `prueba` |
| RF-128 | **Lo que la vuelta cuesta de entrada se reserva.** Corregir no arranca en frío: la segunda llamada al modelo vuelve a leer el encargo más la respuesta anterior y el motivo, y eso es entrada. Cada paso con hooks declara `reserva_de_la_vuelta` en tokens, y la anchura de tanda de RF-13 la suma al tope del rol. El hook solo bloquea si la respuesta anterior más el motivo caben en esa reserva; si no, el intento termina y falla, y el siguiente arranca en frío. La entrada medida de un intento es la de su última llamada al modelo, que es la mayor | `prueba` |
| RF-129 | Solo el encargo con hooks lleva, en su instrucción de sistema, que un mensaje del revisor automático que llega tras su respuesta no es dato del encargo sino una orden del sistema: corrige lo que dice y vuelve a entregar el objeto JSON entero | `inspeccion` |

| ID | Decisión | Por qué |
| --- | --- | --- |
| D-45 | **Hooks de Claude Code en el subagente, no comprobaciones del servidor ni hooks del desarrollo.** El evento es `Stop`, que es el que dispara el agente principal en `--print`; `SubagentStop` es de los subagentes que un agente lanza por su cuenta | Comprobar solo en el servidor llega tarde: el agente ya ha terminado y no puede corregir. Un hook de `.claude/` no llega nunca, porque el subagente arranca fuera del repositorio (RF-100). Pasarlo en la orden es lo único que lo engancha a la tarea que escribe la novela sin romper el aislamiento |
| D-46 | **Lo que el hook necesita le llega por la orden y el entorno, no por ficheros.** El nombre del hook y de la tarea van en su línea de orden; los vetos y la reserva, en variables de entorno del subagente; el esquema, del catálogo versionado | Escribir la lista de vetos en el directorio de la tarea contradiría D-35 —nace vacío y muere vacío— y RD-08. El hook no escribe en la base: informa por su salida y quien registra es el ejecutor, así que el almacén sigue con un solo escritor (RNF-05) |
| D-47 | **Una vuelta en la sesión y, si no basta, un intento fallido.** No se inventa otra política: lo que pasa después lo deciden `reintentos` y `al_agotarse` | Un hook no guarda estado entre llamadas y la única memoria que Claude Code le da es si ya bloqueó en ese turno, así que «una vuelta» es lo único que puede contar sin escribir nada. Más vueltas harían crecer la entrada sin tope, y el propio CLI corta un hook a los diez bloqueos seguidos. El intento siguiente arranca en frío, así que el total queda acotado por los reintentos del paso |
| D-48 | **`validar_capitulo` va en los tres pasos de prosa y mira la forma, más los nombres de la biblia** (RF-145, D-55) | Es lo que se puede decidir sin gastar y sin interpretar el texto (§2.1). Engancharlo solo a la costura dejaría pasar una escena malformada hasta el final del capítulo; los tres pasos que escriben `Borrador` son los tres sitios donde se puede corregir en el acto |
| D-49 | **`policy` es un solo enganche para toda lista de lo vetado.** Qué listas mira y cómo compara lo fija §4.14; ampliarlas cambia de dónde sale la lista y la comparación, no el enganche | No es la dimensión de léxico vetado de la época, que sigue en el Editor de estilo: es una política del comprador y de la instalación, comprobada como se comprueba la forma de un artefacto (RF-23). Si una comparación de cadenas, también normalizada, cuenta como herramienta de cálculo en el sentido de D-05 lo decide esa decisión abierta, que no se cierra aquí |

**Cuánto contexto añade.** Nada si el agente entrega bien a la primera: la
lista de vetos no entra en ninguna ventana (RF-16 sigue en pie) y la
instrucción de RF-129 son unas pocas líneas. Si bloquea, la segunda llamada lee
además la respuesta anterior, el motivo y la línea de orden del hook con que el
CLI lo encabeza, y eso cabe por construcción en la reserva del paso: 4 000
tokens en `redactar` y `revisar`, que van en tanda por escena, y 8 000 en la
costura, que va sola. Con la reserva, caben cuatro Redactores por tanda y dos
Revisores. De lo vetado, al agente solo le llega lo que encontró en su propio
texto.

**Qué retira.** La frase de §11 según la cual los vetos se guardan y no se
aplican. RF-98 suma un caso de intento fallido: la salida final que no pasa un
hook. Y RF-13 suma la reserva de la vuelta a la anchura de los pasos con hooks.

**Qué queda fuera.** Detectar un tema vetado por su sentido y no por sus
palabras, y hooks en los roles que no escriben prosa. Qué listas mira
`policy` y cómo compara es de §4.14; los nombres, la longitud y la puerta de
publicación, de §4.15.

**De dónde sale.** `architecture.md` §3 (toda tarea arranca en frío,
presupuesto) y §4 (reintentos por paso); RF-06, RF-13, RF-16, RF-23, RF-95 a
RF-102; D-35 y RD-08.

**Documentos que hay que poner al día en la fase 3.** `architecture.md`: §3, la
reserva de la vuelta en el presupuesto; §4, los hooks en el guion y lo que pasa
cuando no se pasan; §7, `ganchos.py` en el árbol. `validators.md`: §6, las
pruebas; §7, los hooks entre los guardarraíles y lo vetado entre las amenazas,
con lo que la comparación no ve; y §8, los métodos de RF-120 a RF-129. `definitions.md` y
`domain-knowledge.md` no cambian: los vetos ya eran parte del destinatario.

### 4.14 Lo vetado: tres listas, comparación normalizada y registro de auditoría

**El problema.** El hook `policy` de §4.13 solo miraba lo que el comprador vetó
en el brief, y lo comparaba tal cual: «Búho», «búhos» o «alguaciles» pasaban
junto a un veto «búho» o «alguacil», y un insulto que nadie hubiese vetado
llegaba al manuscrito de una obra que se regala. Tampoco quedaba escrito, en
ningún sitio que se pudiera consultar, qué encontró la política, a quién se lo
devolvió y qué pasó después.

**La decisión, en una frase.** `policy` busca en la prosa tres listas —una
global de insultos y términos ofensivos que el sistema trae de serie, y las
palabras y los temas que vetó el comprador—, compara palabra a palabra después
de normalizar las dos partes, y cada coincidencia queda en un registro de
auditoría de solo añadir que se sirve por la API. El enganche, la vuelta de
corrección y lo que pasa al agotar los intentos no cambian (§4.10, §4.13).

| ID | Requisito | Verificación |
| --- | --- | --- |
| RF-130 | **Tres listas, dos niveles.** El nivel global es una lista de la instalación, igual para toda obra, que aplica también a una obra sin destinatario. El nivel de la obra son los `destinatario.vetos` del brief, que se reparten por su forma: un veto de una sola palabra es una **palabra vetada** y uno de varias es un **tema vetado**. Cada veto lleva su nivel, del vocabulario cerrado `nivel_de_veto`: `global`, `palabra_del_comprador`, `tema_del_comprador` | `prueba` |
| RF-131 | **La lista global viene de serie.** Vive en SQLite, en tabla propia, y la siembra la migración 8 con una lista corta de insultos y términos ofensivos en español, escogida para no chocar con vocabulario de época. No se borra ni se modifica; ampliarla es añadir una migración. Ninguna ruta de la API la edita ni la sirve | `prueba` |
| RF-132 | **Se compara normalizado y por palabras enteras.** El texto y cada veto se parten en palabras y cada palabra se reduce igual en los dos lados: minúsculas; sin acentos ni diéresis, salvo la `ñ`; una letra repetida tres veces o más cuenta como una; sin la marca de plural (`-s`, `-es`, `-ces` → `-z`); y sin la vocal de género `-o`/`-a`. Un veto casa cuando la secuencia de sus palabras reducidas aparece seguida en el texto. Una palabra no casa dentro de otra | `prueba` |
| RF-133 | **Un tema vetado se busca como frase**, con la misma normalización. Si la prosa alude al tema con otras palabras, no casa: es un límite declarado, no un defecto (D-52) | `prueba` |
| RF-134 | **Al agente le llega lo que escribió, no la lista.** El motivo del hook nombra cada coincidencia con las palabras tal como aparecen en su texto. La lista global, como la del comprador, no entra en ninguna ventana y viaja al hook en su variable de entorno, cada veto con su nivel (D-46) | `prueba` |
| RF-135 | **Registro de auditoría.** Cada coincidencia de `policy` queda como una fila con la obra, la `Traza` del intento, la decisión, el nivel, el veto tal como está en su lista y lo encontrado tal como está escrito. La decisión es del vocabulario cerrado `decision_de_policy`: `devuelto_al_agente`, cuando el hook bloqueó en la sesión y el agente tuvo que corregir, e `intento_fallido`, cuando el veredicto final del ejecutor no pasa (RF-126). La coincidencia de la sesión se reconstruye aplicando la misma función al mensaje del agente que el hook bloqueó, leído del flujo del CLI. Una fila por veto y forma escrita distinta en cada veredicto | `prueba` |
| RF-136 | **Lo escribe el almacén al cerrar la `Traza`**, en la misma transacción, con lo que el ejecutor dejó en `ganchos`. El hook sigue sin abrir la base (RF-122). El registro no se borra ni se modifica, y no se caduca ni se releva: como la `Traza`, es la constancia de lo que pasó | `prueba` |
| RF-137 | **Agotados los intentos, la obra se detiene y lo dice.** Los tres pasos de prosa ya declaran `detener_obra` (RF-97). La ficha de la obra trae el motivo de la detención, que nombra la tarea, lo encontrado y la `Traza` del último intento, y queda vacío cuando la obra no está detenida | `prueba` |
| RF-138 | `GET /obras/{id}/policy` sirve el registro de la obra en orden, cada fila con su capítulo, escena, tarea e intento sacados de su `Traza`, filtrable por capítulo, nivel y decisión. Es de solo lectura y entra en `backend/openapi.yaml` (RI-10) | `prueba` |

| ID | Decisión | Por qué |
| --- | --- | --- |
| D-50 | **Las dos listas del comprador salen del mismo campo del brief y no se copian a una tabla.** Palabra o tema lo decide cuántas palabras tiene el veto | El brief ya guarda los vetos dentro de la `Obra`, en SQLite, desde el alta (RF-06): copiarlos sería un segundo sitio que mantener al día. Partir el campo en dos movería el brief, la entrevista y la API por una diferencia que la comparación no necesita, porque las dos se buscan igual; solo cambia la etiqueta con que la coincidencia queda en el registro |
| D-51 | **La lista global se siembra en la migración y no tiene ruta de edición.** Es corta y deja fuera palabras con un sentido histórico o inocente que la normalización confundiría —«bastardo», «moro», «zorra», «capullo», «polla»— | Así funciona sin que nadie haga nada (RNF-08), y cambiarla pasa por el ciclo, como cualquier otra entrada del sistema. Una lista larga en una novela de época bloquearía prosa legítima: cada falso positivo es una vuelta de corrección y, si el agente insiste, una obra detenida |
| D-52 | **Normalizar con reglas fijas de palabra, no con un lematizador ni con un modelo.** Los temas, como frases | Es determinista, no añade dependencias y cabe en el hook, que no llama a ningún modelo (RF-122). Comparar palabras enteras evita el falso positivo de toda lista de subcadenas: un veto escondido dentro de una palabra inocente. El precio se declara: dos palabras que solo difieren en género o número se confunden —«caso» y «casa»—, y no se ven ni lo escrito con separadores, cifras o símbolos por medio ni el tema dicho con otras palabras. Juzgar un tema por su sentido es trabajo del juicio semántico, no de esta lista |
| D-53 | **El registro tiene tabla propia, fuera de las de artefactos, y recoge los dos momentos** | Al contrario que el veredicto de RD-25, este sí se consulta: por obra, por nivel y por decisión. No es un artefacto porque no lo escribe ningún rol, y no se versiona porque, como la `Traza`, cuenta lo que pasó en cualquier versión. Recoger solo el veredicto final dejaría fuera justo lo que la política consiguió: el texto que el agente corrigió a tiempo |
| D-54 | **Se ve por la API: una ruta de lectura para el registro y el motivo en la ficha.** Ninguna de escritura | Lo que hay que ver se sirve por la API y no hay volcados (RD-08). Sin el motivo en la ficha, una obra detenida por lo vetado no diría por qué a quien la encargó |

**Cuánto contexto añade.** Nada a ninguna ventana: las listas viajan por el
entorno del hook. Lo que el hook devuelve sigue acotado a 1 000 caracteres
(RF-125) y cabe en la reserva de la vuelta.

**Qué retira.** La comparación literal de RF-124 y D-49, que pasan a remitir a
esta subsección, y de lo que §4.13 dejaba fuera, la lista global, la
normalización y el registro de auditoría.

**Qué queda fuera.** Detectar un tema por su sentido; lo escrito con
separadores, cifras o símbolos para esquivar la lista; un lematizador; una ruta
para editar o leer la lista global; y cualquier política sobre lo que no es la
prosa de un `Borrador` o un `Párrafo`. Esta subsección no cierra la decisión
abierta del léxico vetado de la época (`architecture.md` §8), que es otra lista
y otra dimensión, ni D-05.

**De dónde sale.** §4.10 (reintentos y `al_agotarse`) y §4.13 (el enganche);
RF-06, RF-16, RF-122, RF-126 y RD-25; RD-02 y RD-08.

**Documentos que hay que poner al día en la fase 3.** `architecture.md`: §2,
los vocabularios `nivel_de_veto` y `decision_de_policy`; §4, lo que mira el
hook `policy` y el registro; §6, el registro en la tabla de gobierno.
`validators.md`: §6, las pruebas; §7, el guardarraíl y la amenaza de lo vetado
con lo que la normalización no ve; y §8, los métodos de RF-130 a RF-138.
`definitions.md` y `domain-knowledge.md` no cambian: lo vetado ya era parte del
destinatario y el registro es de producción.

### 4.15 Validadores programáticos y puerta de publicación

**El problema.** Publicar una versión era una orden sin condiciones: bastaba con
que hubiera terminado. Nadie comprobaba lo que se puede comprobar sin juzgar el
texto: que la salida de cada rol trae los campos de su esquema, que los nombres
de la biblia —el del destinatario el primero— se escriben tal cual, que cada
capítulo tiene una longitud de capítulo y que lo que sale de la vida del
destinatario acaba en la novela. Un «Inés» donde la biblia dice «Ines», un
capítulo de doscientas palabras o el perro del destinatario sin aparecer
llegaban a la versión publicada sin que nada lo dijera.

**La decisión, en una frase.** Cuatro validadores deterministas, funciones puras
que no abren la base ni llaman a ningún modelo, y una puerta en el único sitio
por el que se publica: si alguno falla, la versión no se publica y la respuesta
dice qué falló y en qué capítulo. El de nombres va además en el hook
`validar_capitulo`, para que quien escribe lo corrija en el acto.

| ID | Requisito | Verificación |
| --- | --- | --- |
| RF-140 | Los cuatro validadores viven en `novela/validadores.py`: funciones puras que reciben lo ya leído y devuelven lo que falla. No abren la base de datos, no escriben en disco y no llaman a ningún modelo. Cada fallo de la puerta dice qué validador lo da —vocabulario cerrado `validador_de_la_puerta`: `esquema`, `nombres`, `longitud`, `elementos_personalizados`—, en qué capítulo está, vacío si no es de ninguno, y un detalle legible | `prueba` |
| RF-141 | **Esquema.** Todo artefacto que ve la versión (RF-113), escrito por un rol y cuyo tipo declara el `esquema.json` de la tarea de ese rol, trae en su cuerpo todos los campos que ese esquema declara para su tipo. El fallo nombra el artefacto, su tipo y los campos que le faltan. Lo que escribe el backend —la `Traza`, las críticas de RF-23 y RF-99— no es salida de un rol y no se mira. Qué cuenta como presente y qué campo es obligatorio lo precisan RF-207 y RF-208 | `prueba` |
| RF-142 | **Nombres.** Los nombres de la biblia son el del destinatario y el `nombre` y los `tratamientos` de cada `Personaje`, `Lugar`, `Objeto` y `Faccion`. En el texto de cada `Borrador` y cada `Parrafo`, una palabra que empieza por mayúscula, no es ninguna palabra de esos nombres y se parece a una —solo cambian acentos o mayúsculas; o, en un nombre de cinco letras o más, cambia una sola letra; o, en uno de siete o más, sobra o falta una— es un nombre mal escrito, salvo que la misma palabra aparezca también en minúscula en ese texto, que es lo que delata una palabra corriente. El fallo dice lo escrito y el nombre de la biblia. En la puerta, además, el nombre del destinatario aparece tal cual en algún capítulo | `prueba` |
| RF-143 | **Longitud.** `guion.toml` declara en `[capitulo]` `palabras_minimas` y `palabras_maximas`, iguales para todas las obras: 1 000 y 4 000. Si faltan, no son enteros positivos o el mínimo pasa del máximo, el guion no carga. Cada capítulo de la versión, contado sobre su texto aceptado, cae dentro del rango; un capítulo sin texto tiene cero palabras | `prueba` |
| RF-144 | **Elementos personalizados.** Todo hecho de la biblia de la versión con licencia `personal` tiene al menos una `Mencion` en un capítulo de la versión: los capítulos en que se usa (RF-84) no están vacíos. El fallo nombra el hecho | `prueba` |
| RF-145 | **En la escritura, solo nombres.** `validar_capitulo` suma a su lista la comprobación de nombres de RF-142, sin la de presencia del destinatario. La lista de nombres le llega por la variable de entorno `NOVELA_GANCHO_NOMBRES`, como los vetos (D-46), y no entra en la ventana. Como toda comprobación de ese hook, la repite el ejecutor sobre lo entregado al final (RF-126). El esquema de lo guardado, la longitud y los elementos personalizados van solo en la puerta | `prueba` |
| RF-146 | **La puerta.** `nucleo.versiones.publicar` —el único sitio por el que se publica (RF-116)— comprueba que la versión existe y ha terminado y después pasa los cuatro validadores sobre lo que ve esa versión. Si alguno falla, no publica: no añade nada al registro de publicaciones y la orden responde con la lista de fallos. Rehacer sigue siendo una orden del editor (RF-111): la puerta no regenera nada | `prueba` |
| RF-147 | `GET /obras/{id}/versiones/{n}/puerta` sirve el resultado de pasar la puerta sobre esa versión en ese momento, sin publicar nada, haya terminado o no; la respuesta dice si ha terminado. Una versión que no existe es un 404 | `prueba` |

| ID | Decisión | Por qué |
| --- | --- | --- |
| D-55 | **En el hook, solo los nombres; lo demás, solo en la puerta** (D-93 lo corrige para `plegar` y `destilar`) | Un nombre mal escrito está en el texto que el agente acaba de escribir, y una vuelta basta para arreglarlo: es lo que el hook hace bien. La longitud es del capítulo entero, y la única tarea que lo ve junto es la costura, cuyo rol no escribe contenido: estirar o recortar un capítulo es trabajo del Redactor, y pedírselo al Editor de estilo ensancharía su rol. Las `Mencion` nacen al cerrar el capítulo, después de los tres pasos de prosa. Y el esquema de los roles sin hooks no se comprueba al escribir porque no tienen vuelta de corrección: un fallo sería un intento fallido que acaba deteniendo la obra, justo lo que OBJ-07 evita. La forma del artefacto principal de los tres de prosa ya la mira el hook (RF-123) |
| D-56 | **Un nombre mal escrito se detecta por distancia de letras, con reglas que prefieren no ver una variante antes que detener la obra por una palabra corriente** | En el hook, un fallo que el agente no corrige es un intento fallido y, agotados los reintentos, detiene la obra. «Pero» está a una letra de «Pedro» y «Marido» de «Mario»: por eso sobrar o faltar una letra solo cuenta en nombres de siete o más, y una palabra que también sale en minúscula no se toma por nombre. El precio declarado es que «Martha» por «Marta» pasa. Es comparar cadenas contra lo escrito en la biblia, como `policy` (D-49): no juzga el texto (§2.1) ni cierra D-05 |
| D-57 | **Un elemento personalizado obligatorio es todo hecho de la biblia con licencia `personal`** | Es lo que RF-08 ya marca como salido de la vida del destinatario, y la tabla de hechos sabe en qué capítulos se usa cada uno. Contar por `Recuerdo` obligaría a fijar con qué campo apunta una ficha a su recuerdo, que el esquema del Constructor no declara |
| D-58 | **El rango de longitud está en el guion, fijo, de 1 000 a 4 000 palabras por capítulo** | Fijo e igual para todas las obras, y no derivado de la extensión del brief, lo decidió el dueño. El máximo sale de la ventana de la costura: 4 000 palabras son unos 24 000 caracteres, unos 6 700 tokens a 3,6 por token, y eso cabe en los 8 000 del Editor de estilo sin partir el capítulo (RF-14). Por debajo de 1 000 palabras hay una escena, no un capítulo. Va en el guion, junto a lo demás que gobierna el capítulo, y no en `ajustes.py` |
| D-59 | **La puerta explica y no guarda.** Responde 409 con los fallos, y su resultado se deriva cada vez que se pide | 409 porque la petición está bien formada y lo que choca es el estado de la versión, igual que publicar una sin terminar. Guardar el resultado sería un segundo sitio que mantener al día, y una versión terminada no cambia (RF-114): pasar la puerta dos veces da lo mismo. Regenerar solo al fallar lo descartó el dueño: rehacer es una decisión editorial |

**Qué retira.** De §4.12, la puerta como pendiente; de §4.13, los validadores de
nombres y de longitud como pendientes y la frase de D-48 que los aplazaba; de
D-29 y de §11, el validador de elementos personalizados como fuera de alcance.
RF-123 suma la comprobación de nombres a la lista de `validar_capitulo`.

**Qué queda fuera.** El validador visual con navegador y enseñar en la web por
qué no pasó una versión, que son de la lectura interactiva. Pedir la longitud a
quien escribe: ni el Planificador ni el Redactor reciben el rango, y hasta que
lo reciban la puerta es el primer sitio donde se ve un capítulo corto. Comprobar
que cada `Recuerdo` tiene ficha. Detectar un nombre mal escrito por su parecido
de sentido y no de letras. Y regenerar lo que falla sin que el editor lo pida.

**De dónde sale.** RF-08, RF-23, RF-84, RF-111, RF-113, RF-116 y RF-123; D-43,
D-46, D-48 y D-49; `validators.md` §3 (el contrato de verificación) y §7 (los
guardarraíles).

**Documentos que hay que poner al día en la fase 3.** `architecture.md`: §2, el
vocabulario de proceso `validador_de_la_puerta`; §4, la puerta al publicar y el
hook de nombres; §7, `validadores.py` en el árbol. `validators.md`: §6, las
pruebas y el contrato de importación nuevo; §7, los hooks y lo que la
comparación de nombres no ve; y §8, los métodos de RF-140 a RF-147, RD-30, RI-18
y RI-19. `definitions.md` y `domain-knowledge.md` no cambian: el elemento
personalizado es un hecho `personal`, que ya existía.

### 4.16 La cronología, demostrada en Lean antes de publicar

**El problema.** La cronología (§4.9) registra cuándo ocurre cada suceso, dónde
y quién estaba, pero nadie comprobaba que no se contradiga. Los cuatro
validadores de la puerta (§4.15) miran esquema, nombres, longitud y elementos
personalizados, y el Verificador de continuidad juzga cada escena antes de que
el capítulo cierre, cuando los `EventoEstado` de ese capítulo todavía no
existen. Un personaje presente en un suceso anterior a su nacimiento, que
muere en el capítulo 3 y vuelve a estar presente en el 5, o que el mismo día
está en dos lugares, llegaba a la versión publicada sin que nada lo dijera. Es
aritmética de fechas y cotejo exhaustivo, lo que peor hace un modelo y lo que
`architecture.md` §7 da por perdido sin cálculo determinista.

**La decisión, en una frase.** Antes de publicar, la cronología de la versión
se vuelca a un módulo de Lean 4 y `lake build` tiene que demostrar cuatro
invariantes suceso a suceso; si Lean está en la máquina y no los demuestra, la
versión no se publica y cada fallo vuelve al editor como `Crítica`; si Lean no
está, la versión se publica igual y la respuesta dice que salió sin
comprobación formal.

La regla del último punto es literal del dueño en el interrogatorio: «si me
aseguras que va a estar instalado pues hacemos esa comprobación; si no, no
tires una versión por esa tontería». La máquina de desarrollo lleva Lean
instalado para que lo segundo sea la excepción.

| ID | Requisito | Verificación |
| --- | --- | --- |
| RF-150 | **El volcado.** `novela/demostrador.py` traduce la cronología que ve la versión —la vista de RF-86, más el sujeto de cada `EventoEstado` `muere` y el de cada `viaja_a`, leídos de su cuerpo— a un módulo de Lean, sin abrir la base ni llamar a ningún modelo. Copia lo escrito y no calcula nada: una fecha ISO parcial pasa a un intervalo de días `AAAAMMDD` —`1587` es del 1 de enero al 31 de diciembre—, cada personaje y cada lugar a su posición en una tabla, y lo que no consta a un valor que no choca con nada. Escribe un teorema por invariante y por suceso, y uno final que reúne los cuatro sobre la cronología entera. Un presente, un lugar o quien muere que apunta a una ficha relevada por un cambio del lector se vuelca como la ficha que la sustituye (RF-177), para que la misma persona o el mismo lugar no cuenten como dos | `prueba` |
| RF-151 | **Los cuatro invariantes**, definidos una vez en el proyecto de Lean versionado en `novela/lean/`, con su `lean-toolchain` fijada y sin Mathlib: **orden temporal** —un suceso de un capítulo anterior no ocurre después de uno de un capítulo posterior—; **edad coherente** —todo presente había nacido y no pasa de 120 años—; **un solo lugar** —dos sucesos del mismo día exacto en lugares distintos no comparten presentes, salvo que ese día conste que ese presente llegó a uno de los dos (RF-213)—; y **no reaparece** —quien muere en un suceso no está presente en ninguno posterior, por capítulo o por fecha—. Se demuestran con `decide` sobre los datos del volcado | `prueba` |
| RF-152 | **En la puerta.** `validador_de_la_puerta` gana el valor `cronologia`. La puerta (RF-146, RF-147) pasa el volcado por Lean, y cada teorema que Lean no demuestra es un fallo `cronologia` con el capítulo del suceso y un detalle que dice qué invariante, qué suceso, sus datos y el mensaje de Lean. Un error que no cae en ningún teorema, o Lean que no termina en 300 segundos, es un fallo sin capítulo. El resultado de la puerta dice además `comprobacion_formal`, de un vocabulario cerrado: `demostrada`, `fallida` o `sin_comprobacion` | `prueba` |
| RF-153 | **La ejecución.** Cada comprobación copia el proyecto de `novela/lean/` a un directorio temporal, escribe allí el módulo generado, ejecuta `lake build` y lee su salida. El directorio se borra al terminar, falle o no: el módulo no se guarda ni en el repositorio ni en una carpeta de trabajo (D-62) | `prueba` |
| RF-154 | **El fallo vuelve como crítica.** Cuando `publicar` rechaza una versión, cada fallo `cronologia` que señala un suceso se guarda como `Crítica` `bloqueante`, abierta, de esa versión y del capítulo del suceso, con objeto el `id` del suceso, dimensión `coherencia_temporal` —orden, edad y formato— o `continuidad_de_estado` —lugar y reaparición—, y como evidencia el detalle con el teorema y el mensaje de Lean. La escribe el backend, como las de RF-23 y RF-99. Mientras siga abierta, volver a pedir la publicación no la repite. Ver la puerta con RF-147 no escribe nada | `prueba` |
| RF-155 | **Sin Lean, se publica y se dice.** Si `lake` no está en la máquina, la cronología no se comprueba, eso no es un fallo, y la puerta responde `comprobacion_formal: sin_comprobacion`. La respuesta de publicar (RI-12) dice también `comprobacion_formal`, para que una versión publicada sin comprobar se vea al publicarla | `prueba` |
| RF-156 | **El caso que solo Lean ve.** Una obra entera con el ejecutor fingido, limpia para los cuatro validadores de §4.15, cuyo Contable deja a los mismos presentes en dos lugares el mismo día del capítulo 2: con Lean, la versión no se publica, todos los fallos son `cronologia` del capítulo 2 y quedan como críticas; sin Lean, la misma versión se publica marcada `sin_comprobacion` | `prueba` |
| RF-157 | **El formato de fecha lo comprueba el volcado.** Un momento o un nacimiento escrito que no es ISO parcial (RF-85) no se puede volcar, y es un fallo `cronologia` que nombra el suceso, el campo y lo escrito, haya Lean o no. Cierra lo que D-28 dejó al volcado | `prueba` |

| ID | Decisión | Por qué |
| --- | --- | --- |
| D-61 | **Con Lean instalado, lo que no se demuestra no se publica; sin Lean, se publica y se marca** | Es la regla del dueño. Que falte una herramienta en la máquina no dice nada de la novela, y tumbar la versión por eso sería un paso manual disfrazado: instalar algo para poder publicar. Con Lean presente, en cambio, «no demostrado» se trata como fallo aunque la causa sea que el módulo no compila o que Lean no termina: dejarlo pasar convertiría un error del volcado en una versión sin comprobar que nadie ve. Lo que se cuenta como ausencia es solo que `lake` no se encuentre |
| D-62 | **El módulo generado vive en un directorio temporal que se borra al terminar; los invariantes, en el repositorio** | RD-08 prohíbe guardar en disco lo que el sistema produce, y el módulo lo es. Pero Lean solo lee ficheros, así que existir en disco mientras dura la comprobación es el formato de entrada de la herramienta, no un almacén: nadie lo vuelve a leer, como el directorio vacío donde el ejecutor lanza cada subagente. Los invariantes no los produce el sistema: son entrada versionada que se lee y no se escribe, como el guion y los prompts de RD-09. Se copia el proyecto en vez de construir dentro de `novela/lean/` para que el servidor no escriba en el repositorio ni se pisen dos comprobaciones a la vez |
| D-63 | **La puerta sigue sin guardar su resultado; lo que se guarda es la crítica que deja una publicación rechazada por la cronología** | D-59 no se rompe: ver la puerta deriva siempre y no escribe, y el resultado de la puerta no tiene tabla (RD-30). La crítica no es una copia de ese resultado sino el registro de un hecho —se pidió publicar y Lean lo impidió—, igual que RF-99 registra una comprobación agotada. Es lo que pide la tarea, «el fallo vuelve al editor como crítica», y es lo que coloca el fallo en su capítulo junto a las demás críticas, que es donde el editor mira. Solo la cronología deja crítica, porque es lo que pide la tarea: extenderlo a los cuatro de §4.15 cambiaría lo que D-59 ya decidió para ellos, y queda fuera |
| D-64 | **Lean es una herramienta externa en la puerta, no en la producción; D-05 sigue rigiendo la producción** | Ningún agente recibe nada que Lean calcule, y la coherencia temporal sigue comprobándose durante la producción como `analisis` contra el dato escrito, que es lo que dice D-05. Lean solo decide si una versión terminada se publica. Aun así es exactamente una herramienta externa de cálculo en el camino de publicar, así que **toca la decisión abierta de `architecture.md` §8** sobre herramientas externas. Este cambio no la cierra: la usa en la puerta, lo deja escrito en §12 y espera la decisión del dueño |
| D-65 | **Se demuestra «no hay contradicción segura», suceso a suceso, con `decide` y sin Mathlib** | Con fechas parciales solo falla lo que falla para cualquier día del intervalo: lo contrario llenaría de críticas cada suceso fechado solo por el año. Un teorema por suceso e invariante es lo que permite decir en qué suceso y capítulo está el fallo sin volver a comprobar nada en Python; el teorema final prueba que los cuatro valen para la cronología entera. `decide` sobre naturales lo comprueba el núcleo de Lean sin tácticas de fe, y sin Mathlib `lake build` no descarga nada y tarda segundos. El precio es que el coste crece con el cuadrado de los sucesos: unos 45 segundos para 200 en la máquina de desarrollo, dentro de la espera de 300 |

**Lo que Lean no demuestra aquí.** Solo mira lo que la cronología registra:
un suceso que la prosa narra y el Contable no emitió, un presente que no se
anotó o un nacimiento que falta no se pueden contradecir, y pasan. «El mismo
día» exige día exacto en los dos sucesos; dentro de un mismo capítulo no hay
orden entre sucesos, así que el orden temporal solo compara capítulos
distintos. Y que la fecha escrita sea la verdadera de la época lo sigue
respaldando la `Fuente`, no Lean.

**Qué retira.** De D-29, el fichero del demostrador formal como fuera de
alcance. De §11, el demostrador de la puerta deja de contar entre las
herramientas externas de cálculo excluidas, con la salvedad de D-64.

**Qué queda fuera.** Que el Planificador o el Contable reciban el resultado de
Lean durante la producción; demostrar la cronología de un capítulo al
cerrarlo; guardar en el registro de publicaciones que una versión salió sin
comprobación formal, que hoy solo dice la respuesta de publicar; dejar crítica
por los fallos de los otros cuatro validadores; más invariantes que los cuatro;
y regenerar lo que Lean rechaza sin que el editor lo pida (D-59).

**De dónde sale.** RF-85, RF-86, RF-116, RF-146 y RF-147; D-28, D-29, D-43 y
D-59; RD-08 y RD-09; `architecture.md` §7 («Qué se pierde sin cálculo
determinista») y §8; `validators.md` §3 y §4.

**Documentos que hay que poner al día en la fase 3.** `architecture.md`: §2,
los vocabularios de proceso `validador_de_la_puerta` con `cronologia`,
`invariante_de_la_cronologia` y `comprobacion_formal`; §4, la cronología en
Lean dentro de la puerta y su crítica; §7, `demostrador.py` y `lean/` en el
árbol, y la coherencia temporal en «Qué se pierde sin cálculo determinista».
`validators.md`: el método de RF-150 a RF-157, las pruebas y el contrato de
importación nuevo, lo que Lean no ve y el caso que solo Lean pilla.
`definitions.md` y `domain-knowledge.md` no cambian: la cronología ya era una
vista y el formato de fecha ya estaba fijado.

### 4.17 Validador formal del sistema en TLA+

**El problema.** El punto de guardado, los reintentos, las versiones y la
puerta de publicación se prueban con casos preparados: una caída sembrada en
cada tarea, una avería por política, una obra rehecha desde el 2. Cada prueba
comprueba el camino que alguien pensó. Lo que ninguna comprueba es la
combinación: una caída después de un rehacer, dos órdenes del editor que llegan
a la vez, un fallo que no es de ninguna tarea. Y la regeneración por cambio del
lector (§4.18, que implementa la lectura interactiva) va a reescribir capítulos
que no tienen por qué ser seguidos, justo lo que el punto de guardado da por
hecho que no pasa. Hace falta recorrer **todos** los órdenes posibles de un
modelo pequeño del flujo, no los que alguien escribió.

**La decisión, en una frase.** El flujo de producción de una obra se especifica
como máquina de estados en TLA+, en `backend/formal/tla/`, con tres invariantes
de seguridad y una propiedad de vivacidad que TLC comprueba recorriendo entero
un modelo pequeño cuya configuración está en el repositorio; cada acción del
modelo nombra la función del código que la implementa, y cada contraejemplo que
TLC encuentre se guarda con su traza junto al cambio que provocó.

| ID | Requisito | Verificación |
| --- | --- | --- |
| RF-160 | **El modelo.** `backend/formal/tla/Produccion.tla` especifica el flujo de una obra: el alta y `poblar_mundo`; por capítulo, planificar, escribir, cribar y cerrar como una sola transacción; la auditoría de cierre que termina la versión; los reintentos de cada paso con su `al_agotarse`; la caída del proceso y el relanzamiento al arrancar; detener y reanudar; rehacer desde N; la regeneración por cambio del lector; y publicar a través de la puerta. `Produccion.cfg`, junto a él, fija el modelo pequeño que TLC recorre entero: tres capítulos, dos versiones —la segunda, un rehacer desde N o un cambio del lector—, dos intentos por paso como en `guion.toml`, un hecho de la biblia, una caída del proceso, una orden de reanudar y un fallo no previsto del caminante | `prueba` |
| RF-161 | **Tres invariantes de seguridad**, comprobados en todo estado alcanzable: **la puerta se respeta** —ninguna versión está en el registro de publicaciones sin haber terminado y pasado la puerta—; **la versión anterior se conserva** —lo que ve una versión terminada es lo mismo que veía al terminar (RF-114)—; y **una sola producción a la vez** —toda versión salvo la última está terminada (D-40) y como mucho un caminante trabaja la obra—. Junto a ellos, como comprobaciones auxiliares, el tipo de cada variable, que un capítulo no tenga vivo lo de dos producciones distintas y que un capítulo cerrado no deje de estarlo salvo que una versión nueva lo releve (RF-92) | `prueba` |
| RF-162 | **Una propiedad de vivacidad**: toda versión que está en producción acaba terminada o la obra acaba detenida, con su motivo. Se comprueba bajo tres hipótesis declaradas en el propio modelo: el código del servidor avanza cuando puede (equidad débil de cada paso del caminante y del registro de un arranque), el proceso caído vuelve a arrancar (equidad débil) y las caídas son finitas (`MaxCaidas`). El editor y la máquina no deben nada: sus acciones no llevan equidad | `prueba` |
| RF-163 | **El mapeo.** `backend/formal/tla/mapeo.md` da, para cada acción del modelo, el fichero y la función que la implementan, y lo que el modelo deja fuera. La correspondencia se sostiene por revisión, no se demuestra: cambiar una función del mapeo obliga a revisar su acción y volver a pasar TLC | `inspeccion` |
| RF-164 | **La regeneración por cambio del lector se especifica aquí y la implementa §4.18.** El lector cambia el valor de un hecho de la biblia; nace la versión siguiente, con base en la última, que reescribe solo los capítulos que usan ese hecho según sus `Mencion` en la última versión —seguidos o no— y comparte el resto sin copiarlo; la anterior se conserva (RF-114). Se admite con las mismas condiciones que rehacer (D-40) y es un segundo tipo de versión nueva junto a rehacer desde N (D-42). La versión regenerada sigue el camino normal de producción con sus reintentos y su reanudación, termina con su auditoría y solo se publica si pasa la puerta. Lo que decide §4.18 lo toma el modelo de allí: si ningún capítulo usa el hecho no nace versión, y la ficha nueva del hecho nace en la versión nueva y releva la vieja | `prueba` |
| RF-165 | **Volver al punto de guardado descarta lo de todo capítulo no cerrado.** Lo que se caduca al volver (RF-91) es lo vivo que cuelga de cualquier capítulo que no esté cerrado en la versión en curso, no solo de los posteriores al último cerrado, y lo mismo sale del índice. Mientras las versiones solo rehacen desde N hasta el final, los cerrados son siempre 1..último y las dos reglas coinciden: el código de hoy lo cumple. La regeneración por cambio del lector reescribe capítulos sueltos, y §4.18 lo implementa junto a ella como RF-176, que es el mismo requisito visto desde el código. Sale del contraejemplo 03 | `prueba` |
| RF-166 | **Arrancar la producción de una obra es una sola operación.** Leer qué hilo tiene la obra y registrar el nuevo, que espera a que el anterior acabe, se hacen bajo un mismo cerrojo: dos órdenes que arrancan a la vez —dos `reanudar` seguidos, o un `reanudar` y un `rehacer`— no dejan nunca dos caminantes sobre la misma obra. Sale del contraejemplo 01 (`backend/formal/tla/contraejemplos/`) | `prueba` |
| RF-167 | **Un fallo no previsto del caminante detiene la obra y dice por qué.** Una excepción que no es la detención —una ventana que no cabe ni partiendo, una proyección que no cuadra con su contrato— deja la obra detenida con el motivo, como `detener_obra` (RF-96), y el fallo se sigue viendo. Una obra nunca se queda sin hilo, sin detener y sin terminar. Una caída del proceso no es esto: se relanza al arrancar (RF-93). Sale del contraejemplo 02 | `prueba` |
| RF-168 | **TLC se lanza desde la batería sin gastar.** Una prueba pasa TLC con la configuración del repositorio y exige su «No error has been found». Toma el `tla2tools.jar` de la variable de entorno `NOVELA_TLA2TOOLS` y Java de `JAVA_HOME` o del `PATH`; si falta cualquiera de los dos, se salta limpia diciendo qué falta. Los ficheros de trabajo de TLC van a un directorio temporal y nunca al repositorio (RD-08) | `prueba` |

| ID | Decisión | Por qué |
| --- | --- | --- |
| D-66 | **El modelo es del flujo, no del contenido.** Distingue capítulos, tareas, intentos, versiones, hilos y lo que ve cada versión; no distingue escenas, el bucle de calidad dentro del capítulo, las tandas ni el índice de parecido. Los pasos del guion se reducen a tres tareas por capítulo: las dos que producen testigo y detienen al agotarse, y una que hace de las que siguen sin testigo nuevo (`critica_abierta` y `seguir`). Lo descartado al volver al punto de guardado, que ninguna versión ve, se olvida en vez de guardarse, y los hilos que esperan a otro se cuentan en vez de nombrarse | Lo que se quiere demostrar vive en el orden de las cosas —qué se escribe antes de qué, quién puede arrancar qué—, no en el texto. El bucle de calidad ya tiene sus topes enumerados en pruebas (RF-33) y las tandas su cálculo (RF-13); meterlos multiplica los estados sin tocar ninguna de las cuatro propiedades. Un modelo que TLC no termina de recorrer no demuestra nada |
| D-67 | **La puerta es un veredicto «pasa» o «no pasa» sin decir cuál, fijado cuando la versión termina** | Así cubre los cuatro validadores de hoy y el formal de la historia (§4.16) sin depender de ninguno: si con cualquier veredicto las propiedades se sostienen, se sostienen con el que den. Se fija al terminar porque una versión terminada no cambia y pasar la puerta dos veces da lo mismo (D-59) |
| D-68 | **Tres de seguridad y una de vivacidad, elegidas por lo que rompería el encargo.** Publicar sin puerta, perder la versión anterior y producir dos cosas a la vez son los tres fallos que una prueba de casos no garantiza haber visto; que una obra se quede parada sin decir por qué es el fallo de vivacidad que OBJ-07 y RNF-08 no toleran | El contador de intentos por debajo del tope va en el tipo de la variable: es cierto por construcción y no merece una propiedad aparte. Que los `EventoEstado` solo existan para capítulos cerrados lo garantiza la transacción de cierre, que el modelo toma como una sola acción: comprobarlo sería comprobar la forma del modelo |
| D-69 | **El modelo vive en `backend/formal/tla/` y TLC no es dependencia del paquete.** Java y `tla2tools.jar` se instalan fuera del repositorio, con la versión y la descarga escritas en `mapeo.md` | Es una especificación del backend y va con él. TLC necesita una máquina virtual de Java que el backend no usa para nada más; exigirla haría fallar la batería en toda máquina sin ella. La prueba que se salta limpia deja el camino abierto sin convertirlo en obligación de instalación |

**Qué retira.** De `validators.md` §13, la frase según la cual la comprobación
de modelos no se adopta sobre el código: se adopta sobre el flujo de producción,
que no es enumerable en una prueba porque sus caminos se cruzan con caídas y
órdenes del editor.

**Qué queda fuera.** Demostrar que el código implementa el modelo: la
correspondencia es por mapeo y revisión (RF-163). Modelos grandes: TLC recorre
el de `Produccion.cfg` y nada garantiza lo que pase con tres versiones, veinte
capítulos o diez caídas, aunque ninguna propiedad dependa del número. Varias obras a la vez
(§11). El contenido de lo que se escribe, el bucle de calidad y el índice
(D-66).

**De dónde sale.** §4.10 (punto de guardado y reintentos), §4.12 (versiones),
§4.15 (puerta), §4.18 (regeneración por cambio del lector); RF-92, RF-93,
RF-114, RF-116; D-40, D-42, D-59; OBJ-07 y RNF-08.

**Documentos que hay que poner al día en la fase 3.** `architecture.md` §4, el
modelo formal del flujo y lo que cambie en él. `validators.md`: §7, la
verificación del flujo con un comprobador de modelos; §8, los métodos de RF-160
en adelante; y §13, retirando la comprobación de modelos de lo que queda fuera.
`AGENTS.md`, la carpeta `backend/formal/` en «Estructura del repositorio».
`definitions.md` y `domain-knowledge.md` no cambian: el modelo es del flujo, no
de la ontología.

### 4.18 El cambio del lector y el PDF

**El problema.** Quien lee la novela encuentra un dato que quiere distinto —«el
perro se llama Nala»— y hasta aquí la única forma de conseguirlo era rehacer
desde un capítulo hasta el final (RF-111) sobre la misma biblia de partida: ni
el dato cambiaba, porque la biblia de partida era común a todas las versiones,
ni se reescribía solo lo que lo usa. Y el manuscrito solo se podía leer en la
web: no había forma de llevárselo.

**La decisión, en una frase.** El lector elige un hecho de la biblia y le da un
nombre nuevo; nace la versión siguiente, en la que el hecho lleva ese nombre y
se reescriben **solo los capítulos que lo mencionan**, por el camino normal de
producción; la anterior se conserva intacta y sirve para marcar qué cambió. Y el
servidor fabrica al vuelo el PDF de cualquier versión, sin guardarlo.

```mermaid
flowchart LR
  L([Hecho y nombre nuevo]) --> A{Ultima version terminada<br/>y sin produccion?}
  A -- no --> R([409, no se crea nada])
  A -- si --> M{Algun capitulo<br/>lo menciona en V?}
  M -- no --> R
  M -- si --> V["V+1: releva esos capitulos<br/>y la ficha vieja; ficha nueva"]
  V --> P[Produccion: salta lo cerrado,<br/>reescribe lo relevado]
  P --> F[Auditoria de cierre]
  F --> G([Se publica solo si pasa la puerta])
```

| ID | Requisito | Verificación |
| --- | --- | --- |
| RF-170 | **El cambio es una orden**, `POST /obras/{id}/cambios` con `hecho` —el `id` de un hecho de la biblia (RF-87) que ve la última versión— y `valor`, su nombre nuevo, no vacío y distinto del que tiene. Se admite con las mismas condiciones que rehacer (D-40): la última versión ha terminado y no hay producción en marcha. Un hecho que no ve la última versión es un 404; un valor vacío o igual al actual, un 422; una versión sin terminar o una obra produciendo, un 409. Devuelve la versión nueva y no espera a que termine | `prueba` |
| RF-171 | **Qué se reescribe.** Los capítulos en que se usa el hecho en la última versión V según sus `Mencion` (RF-84), que pueden no ser contiguos, y ninguno más. Si ningún capítulo lo usa, no se abre ninguna versión: 409 diciéndolo (D-73) | `prueba` |
| RF-172 | **Nace V+1 en una sola transacción**, con base V y esos capítulos como `capitulos cambiados` (RF-110). Lo que cuelga de cada uno —con la misma regla de RF-112, capítulo a capítulo en lugar de «de N al final»— y su estado materializado reciben la marca de relevo con V+1; sus fragmentos salen del índice; y la constancia de auditoría baja al capítulo anterior al primero que se reescribe. Lo demás se comparte sin copiar | `prueba` |
| RF-173 | **El hecho cambiado se versiona.** En la misma transacción, la ficha vieja recibe la marca de relevo con V+1 y nace la ficha nueva, escrita por el backend y no por un rol: el mismo cuerpo con el nombre —la descripción en un `Evento`— cambiado, cada tratamiento igual al nombre viejo cambiado también, y `sustituye` con el `id` de la vieja. V sigue viendo la vieja y V+1 la nueva (RF-113). El cambio queda en un registro propio de solo añadir, fuera de las tablas de artefactos —obra, versión, hecho, ficha nueva, nombre anterior, nombre nuevo y cuándo—, que crea la migración 11 (D-72) | `prueba` |
| RF-174 | **Lo que reciben los que reescriben** sale del almacén, por los materiales que ya declaran sus pasos: el Planificador ve la ficha nueva en el canon, el Redactor en las voces del elenco y el Archivero en el índice de la biblia. No hay material nuevo ni instrucción añadida en ninguna ventana | `prueba` |
| RF-175 | **La versión regenerada se produce por el camino de siempre.** Caminar la obra salta los capítulos que siguen cerrados y reescribe los relevados en orden, cada uno desde el paso 1 con los reintentos y la política de su paso (§4.10); termina con su auditoría de cierre (RF-94, RF-110) y solo se publica por la puerta (RF-146). Mientras no se publique, la publicada anterior sigue siéndolo (D-43) | `prueba` |
| RF-176 | **Volver al punto de guardado mira todos los capítulos sin cerrar.** Lo que RF-91 caduca es lo que cuelga de todo capítulo sin cierre vivo, no solo de los posteriores al último cerrado, y el índice que se completa es el de todos los cerrados. Es RF-165, que el modelo formal pidió por su contraejemplo 03. En una obra sin cambio del lector es lo mismo de antes; en una versión que reescribe capítulos sueltos, un corte a medias de uno de ellos no deja nada suyo vivo ni toca los cerrados de detrás | `prueba` |
| RF-177 | **Lecturas.** `GET /obras/{id}/versiones` trae de cada versión su `cambio` —hecho, nombre anterior y nombre nuevo— o vacío si nació del alta o de rehacer. La cronología de una versión resuelve un presente que apunta a una ficha relevada por un cambio del lector a la ficha que la sustituye, por `sustituye`, sin interpretar nada más. La ficha de la obra trae el nombre del destinatario y la dedicatoria, vacíos si no hay destinatario, para la portada | `prueba` |
| RF-178 | **El PDF.** `GET /obras/{id}/pdf`, con `version` como las demás lecturas (RF-117), devuelve `application/pdf` como descarga: portada con el título, el destinatario y la dedicatoria si los hay, índice de capítulos con su página y el texto aceptado de la versión por capítulo y escena. Se fabrica en memoria al pedirlo y **no se escribe en disco ni se guarda** (RD-08). Acentos, `ñ`, `¿`, `¡` y comillas angulares salen tal cual; lo que las fuentes de serie no tienen —la raya, las comillas curvas, los puntos suspensivos de un carácter— se sustituye por su equivalente más cercano (D-75). Una versión que no existe es un 404 | `prueba` |
| RF-179 | **La versión anterior se conserva también aquí** (RF-114): después del cambio y de producir V+1, todo lo que se sirve de V —manuscrito, capítulos, críticas, estado, hechos con la ficha vieja y su nombre, y cronología— es idéntico a antes, y los capítulos que V+1 no reescribe son las mismas filas en las dos | `prueba` |

| ID | Decisión | Por qué |
| --- | --- | --- |
| D-71 | **Un segundo tipo de versión nueva, junto a rehacer desde N, no en su lugar.** Rehacer sigue yendo de N al final (D-42); el cambio del lector reescribe solo los capítulos que mencionan el hecho | D-42 protege que lo posterior a un capítulo rehecho se escribió sobre su mundo. Cambiar el nombre de un hecho no cambia el mundo: los `EventoEstado`, sus presentes, el estado en N y las menciones se refieren al hecho por su `id`, nunca por su nombre, así que un capítulo que no lo menciona sigue siendo cierto con el nombre nuevo. Rehacer del primer uso al final reescribiría capítulos que el lector no pidió tocar y gastaría en ellos. El precio se declara: el capítulo reescrito se vuelve a planificar y podría contar algo distinto de lo que los compartidos dan por hecho —lo ve la auditoría de cierre, y rehacer desde N sigue a mano del editor—, y la lista de capítulos es tan completa como lo sean las menciones (`validators.md` §10) |
| D-72 | **El hecho se versiona con una ficha nueva que escribe el backend**, no con un `EventoEstado` ni con una tarea de un rol. RF-112 deja de ser absoluto: la biblia de partida es común a las versiones salvo el hecho que un lector cambió | Un `EventoEstado` cuenta cómo cambia el mundo a lo largo de la historia; el cambio del lector corrige lo que el mundo era desde el principio, y solo en la versión nueva. Es entrada de una persona, como el brief, y nace como la `Obra` y el `Recuerdo` (D-13): escrita por el backend en la transacción de la orden. Encargárselo al Constructor de mundo costaría una tarea y le dejaría reescribir más de lo pedido. Relevar la vieja y escribir la nueva deja a cada versión con su valor por la misma regla de visibilidad (RF-113). La nueva lleva otro `id` porque el `id` es la clave de la fila; `sustituye` es la referencia que permite resolver los presentes de los capítulos compartidos, que se escribieron con el viejo |
| D-73 | **Si ningún capítulo usa el hecho, no nace versión** | Una versión sin capítulos reescritos tendría el nombre nuevo en la biblia y en ningún texto: un número más sin cambio visible, y terminarla sin producir nada exigiría un camino de terminación aparte. Un hecho `personal` sin mención ya lo señala la puerta (RF-144), y cambiarle el nombre no lo arregla |
| D-74 | **El lector cambia un solo dato: el nombre de un hecho de la lista de hechos.** Ni fragmentos de texto libre ni otros atributos de la ficha | Lo decidió el dueño. Es el valor que la lista de hechos sirve y el que la puerta de nombres sabe comprobar en el texto (RF-142). Subrayar texto libre obligaría a interpretar qué hecho toca el fragmento, que es juzgar el texto (§2.1) |
| D-75 | **El PDF lo fabrica el servidor al vuelo con `fpdf2` y sus fuentes de serie** | Lo decidió el dueño, y RD-08 prohíbe guardarlo: se genera en memoria en cada petición, como la puerta (D-59). `fpdf2` es Python puro, estable y sin dependencias nativas. Sus fuentes de serie cubren Latin-1, que es todo el castellano escrito salvo la tipografía fina; embeber una fuente propia obligaría a llevar un fichero de fuente en el repositorio. El precio es que la raya de diálogo sale como guion |

**Qué retira.** De §4.12, que meter un cambio del lector y rehacer la biblia de
partida quedaran fuera: el nombre de un hecho ya se cambia por versión, y RF-112
remite aquí. De RF-91, que solo se caducara lo posterior al último cerrado. Y de
SPEC2 §12, la decisión abierta sobre la descarga del manuscrito.

**Qué queda fuera.** Cambiar cualquier otro atributo de una ficha, varios hechos
en una sola orden o un fragmento de texto libre (D-74). Comprobar que el nombre
viejo ya no aparece en la versión nueva, que depende de las menciones (D-71).
Dar al Planificador del capítulo reescrito su plan anterior como guía. Guardar o
cachear el PDF, u otros formatos de descarga. La pantalla, que es de SPEC2 §4.5
en adelante.

**De dónde sale.** RF-84, RF-87, RF-91, RF-110 a RF-117 y RF-146; D-13, D-40,
D-42, D-43 y D-59; RD-07 y RD-08; `validators.md` §10 (el hueco de las
menciones).

**Documentos que hay que poner al día en la fase 3.** `architecture.md`: §4, el
cambio del lector como segundo tipo de versión y el punto de guardado con
capítulos sueltos; §6, la ficha nueva en la tabla de gobierno; §7, el PDF en
`api/`. `validators.md`: §6, las pruebas; §8, los métodos de RF-170 a RF-179.
`definitions.md` y `domain-knowledge.md` no cambian: la ficha sigue siendo la
misma entidad y la versión es de producción.

### 4.19 Lo que dice dónde va un artefacto y el testigo del Planificador

**El problema.** En la primera obra de verdad, el capítulo 1 se escribió entero
y el 2 se quedó sin una línea, y la obra acabó con cero capítulos cerrados. Hubo
tres fallos, y ninguno lo veía el recorrido en seco porque el ejecutor fingido
hace lo que el modelo no hace:

1. **Nadie abre el `Capitulo`.** La marca `cerrado` de RF-90 y el ciclo de vida
   de `architecture.md` §4 se escriben sobre la fila `Capitulo`, y esa fila solo
   existía si el Planificador la devolvía por su cuenta. Su prompt no se la
   pide, así que no la devolvió. El cierre no marcó nada, el último capítulo
   cerrado seguía siendo 0, y reanudar habría descartado el capítulo 1 entero.
2. **El backend se fiaba del agente en lo que no es suyo.** El `capitulo` y el
   `estado` de lo que devuelve un rol se tomaban del JSON. En el capítulo 2, el
   Planificador escribió `planificada` en el estado de sus escenas; ese valor
   está fuera de vocabulario y el lote entero se rechazó (RF-23).
3. **Planificar sin escenas no paraba nada.** Por RF-98, el rechazo no era un
   intento fallido, así que no se reintentó. El guion siguió con un capítulo
   sin escenas: documentar, redactar y verificar no tenían nada que hacer, la
   costura cosió nada y la auditoría de cierre auditó un capítulo vacío.

**La decisión, en una frase.** El `Capitulo` lo abre el backend, a qué capítulo
pertenece un artefacto y en qué punto de su ciclo de vida está también lo pone
el backend, y un `planificar` que no deja escenas del capítulo es un intento
fallido.

| ID | Requisito | Verificación |
| --- | --- | --- |
| RF-180 | **El `Capitulo` lo abre el backend.** Cuando el Planificador termina bien el capítulo N, si N no tiene un `Capitulo` vivo, el backend escribe uno con `capitulo` N y estado `planificado`. Desde ahí el caminante lo mueve por su ciclo de vida y el cierre lo marca `cerrado` (RF-90). El Planificador puede seguir escribiendo el suyo, y entonces el backend no escribe otro: RF-92 sigue pidiendo exactamente un `Capitulo` vivo por capítulo cerrado | `prueba` |
| RF-181 | **Dónde va y en qué punto está lo pone el backend.** En un encargo cuya unidad es el capítulo, la escena o el párrafo, todo artefacto que devuelve el rol lleva el `capitulo` del encargo, diga lo que diga su JSON. El `estado` de un `Capitulo`, una `Escena`, un `Plan`, una `Tarea` o un `Borrador` recién devuelto no lo decide el rol: se ignora el que traiga, porque su ciclo de vida lo lleva el caminante. El `estado` de una `Critica` o de un `Compromiso` sigue siendo del rol, porque dice algo del texto y no del proceso. En un encargo de la obra entera, como `auditar`, el `capitulo` que trae el artefacto se respeta: una crítica global puede apuntar a cualquier capítulo | `prueba` |
| RF-182 | **Planificar sin escenas es un intento fallido.** Si lo que devuelve el Planificador no trae ninguna `Escena`, o el almacén lo rechaza (RF-23), el intento falla con ese motivo y no se escribe nada de él, tampoco la `Crítica` de RF-23. Se reintenta como cualquier intento fallido y, agotado, detiene la obra (`detener_obra`, RF-97). Es la única excepción a que un artefacto malformado no sea un intento fallido (RF-98) | `prueba` |

| ID | Decisión | Por qué |
| --- | --- | --- |
| D-76 | **El backend abre el `Capitulo` después de planificar, y solo si el Planificador no lo abrió** | Pedírselo solo al prompt deja el punto de guardado en manos de que el modelo se acuerde, que es justo lo que falló. Abrirlo antes de planificar crearía dos si el Planificador también escribe el suyo. Quitarle el permiso al Planificador convertiría en intento fallido un `Capitulo` bien escrito (RF-35) |
| D-77 | **El testigo del Planificador se comprueba al recibirlo, y su rechazo es un intento fallido** | Sin escenas, los nueve pasos que vienen detrás no tienen sobre qué trabajar y la obra avanza en vacío hasta la auditoría de cierre, que es peor que detenerse. Anotar la `Crítica` de RF-23 y reintentar a la vez dejaría abierta para siempre una crítica de un intento que ya se repitió. Las otras tareas que producen testigo siguen como estaban: sus hooks ya comprueban su forma (RF-123), y `plegar` y `destilar` se rechazan dentro del cierre (RF-90) |

**Qué retira.** RF-98 deja de decir que un artefacto malformado nunca es un
intento fallido: lo sigue diciendo para todas las tareas menos `planificar`.

**Qué queda fuera.** Comprobar que cada escena del plan tiene sus campos antes
de redactar: eso ya lo hace el esquema del almacén. Pedir un número mínimo de
escenas por capítulo, porque ningún documento lo fija. Que el guion no audite
una obra con capítulos sin cerrar: con RF-182, un capítulo sin escenas ya no
llega hasta el cierre. Y cambiar el prompt del Planificador: la regla la impone
el backend, no el prompt (RF-35).

**De dónde sale.** RF-23, RF-35, RF-90, RF-92, RF-97 y RF-98; D-30 y D-34;
`architecture.md` §4, el ciclo de vida del capítulo. El modelo de §4.17 no
cambia: su `Intento` de `planificar` ya puede fallar, y esto solo añade un motivo
por el que falla; TLC se vuelve a pasar igualmente, como pide RF-163.

**Documentos que hay que poner al día en la fase 3.** `architecture.md` §4: quién
abre el `Capitulo`, y el caso de `planificar` en cuántas veces se intenta cada
paso. `validators.md` §8, la matriz de cobertura, con RF-180 a RF-182.
`backend/formal/tla/mapeo.md`: las funciones nuevas en la fila de `planificar`.
`definitions.md` y `domain-knowledge.md` no cambian: esta enmienda no toca la
ontología.

### 4.20 La producción, observada en Langfuse

**El problema.** Todo lo que el sistema mide —tokens, coste, latencia, el
veredicto de los hooks, el resultado de la puerta— se queda en la `Traza` de
SQLite y solo se ve pidiéndolo ruta a ruta. No hay forma de ver una novela
entera de un vistazo —la entrevista, la primera escritura y cada regeneración—,
ni de saber qué versión del prompt de una tarea produjo un resultado. La
evaluación que viene detrás (el juez y el ajuste de los prompts) necesita las
dos cosas y tiene que sacar sus números de Langfuse, no de una hoja aparte: si
la observación entra después, esa evaluación hay que repetirla entera.

**La decisión, en una frase.** Si hay claves, el backend manda a Langfuse, con
su SDK de Python, una sesión por novela con una traza por la entrevista y otra
por cada versión, un span por capítulo, una generación por intento de tarea con
un hijo por llamada a herramienta, el resultado de los validadores como scores
y los prompts de las tareas versionados solos; sin claves no manda nada y la
producción es la de siempre.

Las tres reglas de fondo son del dueño en el interrogatorio: la sesión es la
novela y cada versión es su propia traza con su propio coste; las claves van en
un `.env` de la raíz que el backend lee solo; y los prompts se versionan sin
ningún paso manual, con el repositorio como fuente del texto.

| ID | Requisito | Verificación |
| --- | --- | --- |
| RF-183 | **Encendido por claves.** El backend lee `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY` y `LANGFUSE_HOST` —por defecto `https://cloud.langfuse.com`— del entorno y, lo que falte ahí, del `.env` de la raíz del repositorio. Lo que ya está en el entorno manda, y el `.env` no se copia al entorno del proceso: se lee y se pasa al cliente. Sin las dos claves no se crea ningún cliente ni se abre ninguna conexión | `prueba` |
| RF-184 | **Sesión y trazas.** La sesión de una obra es el `id_entrevista` del que sale (RF-79) y, si se dio de alta sin entrevista, su `id_obra`: nace con la entrevista y la obra la hereda. Dentro hay una traza por entrevista y una por versión de la obra (RF-110) —la primera escritura es la versión 1 y cada rehacer o cambio del lector, la siguiente—. El identificador de cada traza se deriva de la entrevista o de la obra y la versión con la semilla del SDK, así que un relanzamiento tras una caída (RF-93) sigue en la misma traza | `prueba` |
| RF-185 | **Un nombre reconocible por pieza.** Dentro de la traza de una versión, un span `capitulo N` por capítulo que se produce, abierto al empezar el paso 1 y cerrado con su transacción de cierre (RF-90); dentro de él, una generación `<rol> · <tarea>` por intento, abierta al abrir su `Traza` y cerrada al cerrarla, con el capítulo, la escena, el intento, la dimensión y el `id` de la `Traza` en sus metadatos. `poblar_mundo` y `auditar` cuelgan de la traza, fuera de todo capítulo. Cada llamada a herramienta que el subagente hizo es una observación hija `herramienta · <nombre>`, con lo que pidió y lo que recibió, leídos del flujo `stream-json` del CLI. Un intento fallido sale con nivel de error y su motivo. Cada pasada de la entrevista es una generación `entrevistador · entrevistar` en la traza de su entrevista | `prueba` |
| RF-186 | **Tokens, coste y latencia en los tres niveles.** Por llamada: la entrada medida y la salida del `usage` del CLI, el coste de su `total_cost_usd` y la latencia de la observación. Por capítulo: al cerrarlo, su span lleva en los metadatos la suma de las `Traza` de ese capítulo en esa versión. Por novela: al terminar la versión (RF-110), un evento `version terminada` lleva los totales de la versión y los de la novela entera —todas sus versiones más las pasadas de su entrevista—. Las sumas salen de SQLite, no de Langfuse | `prueba` |
| RF-187 | **Todos los validadores, como scores.** Cada vez que se pasa la puerta de una versión —al verla (RF-147) o al publicar (RF-146)— la traza de esa versión recibe un score por validador de `validador_de_la_puerta`: 1 si no tiene fallos y 0 si los tiene, con el detalle de los fallos como comentario. `cronologia` solo se manda si hubo comprobación formal (RF-155). Cada hook del intento (RF-126) deja, en su generación, un score `gancho.<hook>` con el veredicto final del ejecutor. El score de la puerta tiene un `id` derivado de la obra, la versión y el validador: volver a pasarla lo sustituye, no lo repite | `prueba` |
| RF-188 | **Los prompts se versionan solos.** Al arrancar, el backend recorre las carpetas de `tareas/` —las que hay, sin suponer cuántas— y registra el `prompt.md` de cada una con el nombre de su tarea: si el texto no es el de la última versión en Langfuse, crea una nueva con la etiqueta `production`. Cada generación queda enlazada a la versión del prompt de su tarea. El repositorio es la fuente del texto (D-03): nada vuelve de Langfuse a `tareas/` ni a la ventana de ningún rol | `prueba` |
| RF-189 | **Lo que otras piezas usan.** `novela/observabilidad.py` expone `obtener_prompt(nombre)`, que devuelve el texto y la versión de un prompt de Langfuse o nada si está apagado o no existe, y `enviar_score(id_obra, version, nombre, valor, comentario)`, que cuelga un score de la traza de esa versión y no hace nada si está apagado | `prueba` |
| RF-190 | **La observación nunca para la novela.** Todo lo que se manda va por la cola en segundo plano del SDK, y un fallo de Langfuse —caído, claves malas, respuesta rara— se anota en el registro del proceso y se traga: la producción, las respuestas de la API y lo que se escribe en SQLite son idénticos con Langfuse, sin él y con él roto. Lo único que espera a la red es consultar y crear la versión de un prompt, con un tope de 5 segundos y una sola vez por prompt y proceso, también cuando falla | `prueba` |
| RF-191 | **El subagente no ve Langfuse.** El entorno del proceso de cada subagente de tarea, lleve hooks o no, sale del del backend sin ninguna variable que empiece por `LANGFUSE_`. Ningún rol puede consultar cómo se le juzga ni escribir en el proyecto de Langfuse | `prueba` |
| RF-192 | **La batería no manda nada.** Las pruebas usan un Langfuse fingido que guarda lo que se le manda, y la batería apaga la observación aunque haya un `.env` con claves en la raíz. Una prueba contra Langfuse de verdad lleva la marca `gasta` | `prueba` |

| ID | Decisión | Por qué |
| --- | --- | --- |
| D-78 | **Sesión = novela, traza = versión, y los identificadores se derivan en vez de guardarse** | Es la regla del dueño: cada versión tiene su coste propio y la sesión suma el de la novela entera. Derivar el `id` de la traza con la semilla del SDK hace que la caída, el relanzamiento y la puerta que se pasa días después caigan en la misma traza sin escribir nada: no hace falta ni tabla ni columna (RD-31). La entrevista existe antes que la obra, así que la sesión se llama como ella y la obra la lee de su cuerpo, donde ya anota el `id_entrevista` |
| D-79 | **Claves en el `.env` de la raíz, leídas y no exportadas; sin claves, apagado** | Que funcione sin que nadie exporte nada a mano es lo que pide RNF-08. No copiar el `.env` al entorno del proceso deja las claves fuera del camino por el que el ejecutor pasa el entorno a los subagentes; RF-191 las quita igualmente por si vienen del entorno de la máquina. Apagado por defecto porque una instalación sin cuenta tiene que escribir novelas igual |
| D-80 | **Observaciones en vivo con el SDK v4 de Python, y la agregación de los tres niveles hecha con los datos de SQLite** | El SDK v4 manda por OpenTelemetry en segundo plano, que es lo que mantiene la producción sin esperar a la red, y no deja fijar la hora de inicio de una observación: por eso se abre al abrir la `Traza` y se cierra al cerrarla, y la latencia es la de verdad. Las sumas por capítulo y por novela se hacen donde están los números exactos y se mandan como metadatos, para no depender de cómo agregue la interfaz de Langfuse. El precio se declara: el flujo del CLI no fecha las llamadas a herramienta, así que su observación dice qué se pidió y qué volvió, no cuánto tardó; y lo que estuviera abierto cuando el proceso cae no llega a Langfuse |
| D-81 | **El prompt versionado es el `prompt.md` de la tarea, y se sube solo si cambió** | El texto que se ajusta es ese, y es el que la evaluación tiene que atar a cada resultado. Registrarlo al arrancar y no a mano cumple RNF-08. La instrucción común del ejecutor y el esquema de la tarea no se versionan aparte: cambian con el código y los fecha el historial de git. Comparar por texto, y no por fecha, hace que reiniciar el backend no invente versiones |
| D-82 | **Langfuse es un espejo de salida, no un sitio de donde lea la producción; y los evaluadores viven solo allí** | «Sin harness a medida» y RD-08 siguen en pie: el estado de la obra está en SQLite y nada de la producción depende de lo que diga Langfuse. `obtener_prompt` es para quien juzga desde fuera, no para los roles. Los evaluadores, las rúbricas del juez y sus prompts no entran en el repositorio, para que el sistema evaluado no pueda leer cómo se le juzga, y por eso tampoco el subagente hereda las claves (RF-191). `observabilidad.py` recibe lo ya leído y no abre el almacén, igual que el demostrador |

**Cuánto contexto añade.** Nada a ninguna ventana: nada de esto entra en lo que
se manda a un rol, y el techo no cambia.

**Qué queda fuera.** Evaluadores, jueces y rúbricas dentro del repositorio
(D-82). Fechar cada llamada a herramienta. Mandar a Langfuse lo que ya pasó antes
de este cambio. Versionar la instrucción común y los esquemas (D-81). Leer de
Langfuse nada que cambie la producción. Y guardar en SQLite ningún
identificador de Langfuse (RD-31).

**De dónde sale.** RF-52, RF-79, RF-93, RF-110, RF-126, RF-127, RF-146, RF-147,
RF-155; D-03, D-08, D-35; RD-08; RNF-03 y RNF-08; `validators.md` §7 (la traza
es la condición de todo lo demás).

**Documentos que hay que poner al día en la fase 3.** `architecture.md`: §4, la
observación de la producción en Langfuse; §7, `observabilidad.py` en el árbol.
`validators.md`: §6, las pruebas y el contrato de importación nuevo; §7, la
observación entre lo que sostiene la traza y el entorno del subagente entre los
guardarraíles; §8, los métodos de RF-183 a RF-192, RD-31, RNF-10 y RNF-11.
`AGENTS.md` y `CLAUDE.md`: el `.env` de la raíz en el reparto.
`definitions.md` y `domain-knowledge.md` no cambian: la observación es de
producción y no toca la ontología.
### 4.21 El juez de la novela y los briefs de prueba

**El problema.** Todo lo que el sistema comprueba de una obra mira una escena,
un capítulo o un dato escrito: nadie juzga la novela terminada. El Juez de
rúbrica puntúa solo la coherencia de voz, réplica a réplica, y ningún validador
dice si lo que viene de la vida del destinatario está metido con naturalidad o
pegado encima, si la novela funciona como novela —arco, personajes que siguen
siendo quienes eran, ritmo— ni si sigue siendo de su época. Sin esa medida no
hay con qué comparar el antes y el después de un ajuste, y la evaluación del
sistema entero no tiene tampoco entradas fijas: no hay un juego de briefs con
lo que se espera de cada uno.

**La decisión, en una frase.** Un evaluador externo, el **juez de la novela**,
puntúa una versión terminada con tres criterios, nota y justificación por
criterio, y cuelga cada nota como score de la traza de esa versión en Langfuse;
su rúbrica vive solo en Langfuse y nunca en el repositorio. Y cinco briefs de
prueba escritos, cada uno con para qué está y qué se espera al correrlo.

La regla de dónde vive la rúbrica es literal del dueño en el interrogatorio: el
sistema evaluado no debe poder leer con qué vara se le mide; si pudiera, dejaría
de medir calidad y pasaría a medir su capacidad de complacer al juez.

| ID | Requisito | Verificación |
| --- | --- | --- |
| RF-193 | **Un evaluador externo, fuera del censo.** El juez de la novela no es uno de los doce roles: no tiene carpeta en `tareas/`, no escribe nada en el almacén, no está en el guion ni en la API y no participa en la producción. Se lanza por orden explícita de quien desarrolla, `novela.juez_de_la_novela.juzgar_version`, sobre una versión terminada; una versión sin terminar o que no existe se rechaza sin lanzar nada. Su nota no regenera, no revisa, no publica ni bloquea nada. El Juez de rúbrica de `tareas/juzgar` no cambia | `prueba` |
| RF-194 | **La rúbrica sale solo de Langfuse.** Es el prompt `juez-de-la-novela`, que se pide con `obtener_prompt`. Si no llega —Langfuse apagado, el prompt no existe o viene vacío—, el juicio no se lanza y falla con un motivo que dice que falta la rúbrica y nombra el prompt, antes de leer la versión y sin abrir ningún subagente. No hay rúbrica por defecto ni se lee de ningún fichero | `prueba` |
| RF-195 | **Tres criterios, un vocabulario cerrado**, `criterio_del_juez_de_la_novela`: `personalizacion_integrada` —lo que viene del destinatario está en la historia con naturalidad—, `funciona_como_novela` —arco, coherencia de personajes y ritmo— y `fidelidad_a_la_epoca`. Qué criterios se puntúan lo decide el backend, no el juez: si el brief no trae destinatario, `personalizacion_integrada` no se puntúa. La ventana dice cuáles se puntúan | `prueba` |
| RF-196 | **Lo que recibe.** El encargo —título, época, premisa, tesis si la hay y el destinatario sin sus vetos—, los criterios que se puntúan, los hechos `personal` de la biblia con los capítulos en que se usan, todos los `Resumen de capítulo` de la versión y el texto aceptado de **capítulos enteros**, por este orden de prioridad: el primero, el último, los que mencionan un hecho `personal` y los demás en orden. Un capítulo entra entero o no entra, y entran mientras quepan en el tope; la ventana dice qué capítulos no se leyeron. Si sin ningún capítulo ya no cabe, no se lanza y dice cuánto sobra | `prueba` |
| RF-197 | **Cómo se lanza.** Un subagente de Claude Code por el ejecutor de siempre (RF-100 a RF-102): directorio vacío fuera del repositorio, sin herramientas, sin MCP y sin hooks, con la rúbrica como instrucción de sistema y la ventana como dato delimitado. Modelo `claude-sonnet-5`. Tope de ventana de 60 000 tokens. Solo se lanza si ninguna obra de la instalación tiene una `Traza` abierta, es decir, sin producción en marcha: abierto ocupa 63 500 de los 80 000 repartibles y deja entero el margen de la entrevista | `prueba` |
| RF-198 | **Lo que devuelve y cuándo vale.** En `constancia.criterios`, exactamente un elemento por criterio que se puntúa, con `nota` entera de 1 a 5, `justificacion` no vacía y `citas` no vacías, cada cita literal en la ventana que recibió. Si algo de eso falla, el intento entero falla con sus motivos; se intenta dos veces y, agotado, no se envía ninguna nota. Lo que devuelva como artefacto no se guarda y se cuenta | `prueba` |
| RF-199 | **Las notas van a Langfuse.** Solo con un veredicto válido, un score por criterio con `enviar_score`, a la traza de esa obra y versión: nombre `juez_de_la_novela.<criterio>`, valor la nota y comentario con la justificación, las citas, el nombre y la versión del prompt de la rúbrica y los capítulos leídos y no leídos. Así cada nota dice con qué versión de la rúbrica salió. La función devuelve además el veredicto y lo que costó: tokens de entrada, de salida, coste y latencia | `prueba` |
| RF-200 | **La observabilidad llega como parámetro**, con dos operaciones: `obtener_prompt(nombre)`, que devuelve el texto y la versión o nada, y `enviar_score(id_obra, version, nombre, valor, comentario)`. El módulo del juez no importa Langfuse, ni `tareas/`, ni la API, ni abre la base | `analisis` |
| RF-201 | **Los briefs de prueba** viven en `backend/briefs-de-prueba/`, uno por fichero JSON con `proposito`, `para_que`, `se_espera` y `brief`. El propósito es del vocabulario cerrado `proposito_del_brief_de_prueba`: `normal`, `mucha_personalizacion`, `sin_destinatario`, `inyeccion` e `incoherencia_temporal`. Cada entrada de `se_espera` nombra una comprobación —`puerta.<validador_de_la_puerta>`, `gancho.<gancho>` o `juez.<criterio>`—, su resultado del vocabulario cerrado `resultado_esperado` —`pasa`, `falla`, `puede_fallar`, `se_puntua`, `no_se_puntua`— y por qué. Una prueba que no gasta los carga todos, valida cada `brief` contra el modelo de `POST /obras` y cada comprobación contra los vocabularios del código. Hay al menos uno de cada propósito: entre ellos, el adversario de inyección y el diseñado para provocar una incoherencia temporal que solo ve Lean | `prueba` |
| RF-202 | **El texto de la rúbrica no está en el repositorio**: ni en el código, ni en `tareas/`, ni en los documentos, ni en el historial. En el repositorio está solo lo que dice este bloque: que el juez existe, sus tres criterios, la forma de su salida y dónde cuelga sus notas | `inspeccion` |
| RF-203 | **El lanzador de los briefs los corre de uno en uno.** `novela.lanzador_de_briefs` lleva cada brief hasta el final —producir, pasar la puerta, publicar y juzgar— antes de empezar el siguiente, porque el juez no se lanza con producción en marcha (RF-197), y deja la tabla de qué comprobación se esperaba y cuál salió por brief. No corre nada sin `--si-gasto`: cada brief es una obra de verdad. Un brief que revienta sale en la tabla con su motivo en vez de dejar un hueco | `prueba` |

| ID | Decisión | Por qué |
| --- | --- | --- |
| D-83 | **El juez de la novela es un evaluador externo, no un rol del censo, y no va en `tareas/`** | Un rol del censo tiene su prompt en `tareas/<tipo>/` (D-03), y ahí la rúbrica sería legible por quien la sufre, que es lo que el dueño descartó. Tampoco hace trabajo de la obra: no produce nada que otro rol lea, así que «un rol, una tarea» no se toca. El Juez de rúbrica sigue dentro porque su nota es ruido que viaja con el capítulo; el de la novela mide el sistema desde fuera |
| D-84 | **Modelo `claude-sonnet-5`, no Haiku** | Ningún agente valida su propia salida: juzgar con el mismo modelo que escribió la novela invita a que prefiera lo que él mismo habría escrito. Leer hasta 60 000 tokens y juzgar un arco entero pide más que las tareas por escena del censo. Es una llamada por versión, no cientos por obra, así que el coste queda acotado. Opus se descarta por coste para algo que se repite en cada brief y cada vuelta de ajuste |
| D-85 | **Resúmenes de todos los capítulos y texto de capítulos enteros por prioridad**, no la novela entera ni troceada | Una novela larga no cabe, y el techo cuenta la entrada (RNF-01). Trocearla daría tres notas por trozo que nadie sabe sumar en una nota de la obra. Los resúmenes dan el arco entero; el primero y el último, la apertura y el cierre; los que mencionan lo personal, justo donde se mide la personalización. Un capítulo cortado a medias fabrica el defecto de ritmo que se quiere medir, así que entra entero o no entra, y la ventana lo dice para que la nota no finja haber leído lo que no leyó |
| D-86 | **Se lanza a mano sobre una versión terminada, fuera de la producción y sin ruta en la API** | Si su nota disparase algo, la producción aprendería a complacerle, que es lo mismo que leer la rúbrica por otro camino. Terminada, porque se juzga lo que se publicaría. Sin ruta en la API, porque el editor no lo necesita para leer su novela y el contrato de la frontera no se mueve. Sin producción en marcha, porque así sus 63 500 tokens caben sin partir ninguna tanda |
| D-87 | **Su nota es la medida de calidad de la evaluación, y su ruido se mide aparte** | Hasta aquí la nota de un juez de rúbrica no era objetivo porque es ruido. Lo sigue siendo, pero sin ella la evaluación del sistema entero no tiene número: OBJ-10 toma la media por criterio sobre los briefs de prueba y OBJ-11 mide el ruido repitiendo el juicio. Una mejora por debajo del ruido medido no cuenta como mejora. No enruta nada: medir no es controlar |

**Los briefs, en una línea cada uno.** `normal`, una obra corriente con
destinatario, para tener la referencia de un caso limpio. `mucha-personalizacion`,
muchos recuerdos y vetos que chocan con la época, para ver si lo personal cabe
sin pegotes y si la política de lo vetado aguanta. `sin-destinatario`, época
mal documentada y sin destinatario, para ver la fidelidad sin fuentes y que el
criterio de personalización no se puntúa. `inyeccion`, el comprador mete
órdenes dirigidas al sistema en los campos que escribe. `incoherencia-temporal`,
una premisa con dos sucesos del mismo día exacto en dos ciudades con los mismos
personajes, que los cuatro validadores de §4.15 no ven y Lean sí (RF-156).

**Qué queda fuera.** Correr los briefs y el juez, la tabla de qué validador pasó
en cada brief, el ajuste con los números de antes y después y la lectura humana
de una novela completa con la misma rúbrica: son la segunda mitad de la tarea.
Crear el prompt en Langfuse y conectar la observabilidad de verdad. Guardar el
veredicto en SQLite (RD-34). Que la nota del juez vuelva a la producción de
cualquier forma. Y tocar el Juez de rúbrica del censo.

**De dónde sale.** RF-100 a RF-102, RF-146, RF-156 y RF-01; D-03, D-08 y D-61;
RNF-01; `validators.md` §5 (lo que no admite predicado), §7 (el adversario y
«el material con el que se juzga a un agente no vive donde el agente puede
leerlo») y §9.

**Documentos que hay que poner al día en la fase 3.** `architecture.md`: §2, el
juez de la novela como evaluador externo junto al censo y el vocabulario
`criterio_del_juez_de_la_novela`; §3, su tope y cuándo cabe; §7, el módulo en el
árbol. `validators.md`: §2 y §5, la nota que pasa a medirse con su ruido; §6, las
pruebas; §7, el evaluador externo, el contrato de importación nuevo y los
briefs de prueba; §8, los métodos de RF-193 a RF-202; §9, la fiabilidad del juez
de la novela. `AGENTS.md`: `backend/briefs-de-prueba/` en «Estructura del
repositorio». `definitions.md` y `domain-knowledge.md` no cambian: los criterios
son de evaluación del sistema, no dimensiones de calidad del dominio.

### 4.22 El listado de obras y su situación

**El problema.** El backend solo sabe servir una obra si se le da su `id_obra`.
Quien encarga más de una novela no tiene cómo volver a la que encargó ayer sin
haber apuntado el identificador, y la interfaz no puede enseñar un taller con
todas las obras de la instalación porque el contrato no las lista. Era la
decisión abierta de SPEC2 §12 —«cómo se vuelve a una obra pasada sin recordar su
`id_obra`»—, y el dueño la cierra: la interfaz pasa a abrir con un tablero de
todas las obras, al estilo de un gestor de proyectos, y para eso el backend
tiene que listarlas.

**La decisión, en una frase.** `GET /obras` lista todas las obras de la
instalación, de la más reciente a la más antigua, cada una con su ficha y con
**su situación**, un valor de un vocabulario cerrado que calcula el backend.

La situación la calcula el servidor y no la interfaz porque sale de tres hechos
que solo él tiene juntos —si la obra está detenida, si su versión en curso ha
terminado y cuál está publicada— y SPEC2 §2.1 prohíbe que la interfaz decida nada
del dominio: una columna del tablero calculada en el navegador sería una segunda
verdad.

| ID | Requisito | Verificación |
| --- | --- | --- |
| RF-204 | **`GET /obras` lista todas las obras** de la instalación, de la más reciente a la más antigua por su alta. Cada elemento lleva los mismos campos que la ficha de `GET /obras/{id}` (RI-02, RI-17, RF-177), calculados por el mismo código, y además su `situacion` (RF-205), la época y los capítulos que pide el brief, y cuándo se dio de alta. Sin obras, lista vacía: no es un error. No filtra, no pagina y no escribe nada | `prueba` |
| RF-205 | **La situación de una obra es un vocabulario cerrado**, `situacion_de_la_obra`, con cuatro valores que se deciden en este orden: `detenida` si la obra está detenida (RF-04, RF-137); si no, `en_produccion` si su versión en curso no ha terminado (RF-110); si no, `publicada` si la versión en curso es la publicada (RF-116); y si no, `terminada`: la versión en curso ha terminado y no está publicada. Una obra publicada a la que se le pide rehacer vuelve a `en_produccion` hasta que la versión nueva termina | `prueba` |
| RF-206 | **La ficha de una obra trae también su situación**, con el mismo cálculo que el listado. Quien abre una obra por su dirección ve la misma palabra que en el tablero | `prueba` |

| ID | Decisión | Por qué |
| --- | --- | --- |
| D-89 | **La situación la calcula el backend y viaja como vocabulario cerrado**, no como tres booleanos que la interfaz combine | Combinarlos en la interfaz es reimplementar una regla del dominio fuera del servidor (SPEC2 §2.1), y la regla tiene un orden —detenida antes que en producción, publicada antes que terminada— que dos sitios acabarían aplicando distinto. Como vocabulario cerrado es además lo que se pinta tal cual (SPEC2 RD-03) |
| D-90 | **Un listado sin filtros ni paginación** | Es una instalación local de una sola persona con pocas obras; filtrar y paginar son para cuando haya un problema que resolver, y añadirlos después no cambia la forma de cada elemento. Filtrar por situación lo hace la interfaz al repartir en columnas, que es pintar, no decidir |

**Qué queda fuera.** Borrar o archivar obras: no hay ninguna operación de
mantenimiento que el editor deba ejecutar (RI-09, RNF-08). Ordenar por otra cosa
que el alta. Ver varias obras produciéndose a la vez como algo que el sistema
ofrezca, que sigue fuera por §11: listar no es producir.

**De dónde sale.** SPEC2 §12 (la decisión abierta que cierra), RF-04, RF-110,
RF-116, RF-137 y RF-177; RI-02 y RI-17.

**Documentos que hay que poner al día en la fase 3.** `architecture.md`: el
vocabulario `situacion_de_la_obra` junto al resto de vocabularios de proceso, y
§7, el listado en el borde. `validators.md`: §8, los métodos de RF-204 a RF-206.

### 4.23 Lo que la puerta del esquema da por presente

**El problema.** La primera obra de diez capítulos terminó entera y la puerta no
la dejó publicar: 38 fallos de `esquema`, todos en `EventoEstado` del Contable
de estado, sin un solo defecto de texto. Eran dos defectos del backend, no de la
novela. **El capítulo**: RF-181 dice que en un encargo de capítulo el capítulo
lo pone el backend, diga lo que diga el JSON del rol, y el caminante lo guarda
en la columna del artefacto; pero RF-141 miraba solo el cuerpo, así que un
evento bien situado fallaba porque el rol no repitió en su JSON lo que el
backend ya sabía. **El `objeto`**: el `esquema.json` de `plegar` es un único
ejemplo, un `viaja_a`, y RF-141 exigía sus campos a todo `EventoEstado`; pero un
`transcurre_tiempo` o un `muere` no tienen objeto, y un evento correcto fallaba
por no inventárselo.

Arreglados esos dos, quedaron 14 fallos de verdad: doce eventos del capítulo 8
sin `fecha_resultante`, uno del 10 sin `sujeto` y un resumen del 5 sin sus
compromisos. La puerta hizo bien en pararlos; lo que falla es que se descubran
con la obra entera terminada. El Contable y el Archivero no tenían hook, y D-55
lo dejó así porque sin vuelta de corrección un fallo sería un intento fallido
que acabaría deteniendo la obra. Pero el hook *es* esa vuelta de corrección: el
agente que entrega un evento sin fecha lo corrige en la misma sesión.

**La decisión, en una frase.** La puerta del esquema da por presente el
capítulo que puso el backend, y un campo es obligatorio solo si aparece en todos
los ejemplos que el `esquema.json` da de su tipo; `plegar` declara dos formas de
evento, una con objeto y otra sin él. Y `plegar` y `destilar` llevan
`validar_capitulo`, para que su esquema se corrija al escribirse y no al
publicar.

| ID | Requisito | Verificación |
| --- | --- | --- |
| RF-207 | **El capítulo del backend cuenta.** Si el artefacto tiene capítulo en su envoltorio —el que puso el backend por RF-181, o el que se respetó del rol—, RF-141 lo da por presente aunque el cuerpo no lo repita. Nada se reescribe: el cuerpo se guarda como vino (RF-23, D-32) y la comprobación mira el cuerpo con el envoltorio al lado. Así la regla vale también para lo ya escrito, sin migrar nada | `prueba` |
| RF-208 | **Obligatorio es lo que traen todos los ejemplos de su tipo.** Cuando el `esquema.json` de una tarea da más de un ejemplo del mismo tipo, es obligatorio el campo que aparece en todos ellos, y opcional el que falta en alguno. Con un solo ejemplo no cambia nada. El de `plegar` da dos `EventoEstado`: un `viaja_a` con `objeto` y un `transcurre_tiempo` sin él, así que `objeto` es opcional y los demás campos siguen obligatorios. El prompt del Contable dice que el `objeto` se escribe cuando el evento lo tiene | `prueba` |
| RF-209 | **El Contable y el Archivero llevan `validar_capitulo`.** Los pasos 9 `plegar` y 10 `destilar` declaran ese hook, sin `policy` —no escriben prosa ni pueden traer nada vetado—, y su reserva de la vuelta. Comprueba lo de RF-123 con la regla de RF-208: que el tipo principal de su esquema aparece y que **todo** artefacto de ese tipo trae sus campos obligatorios, así que un `EventoEstado` sin `fecha_resultante` o un `ResumenCapitulo` sin compromisos se devuelven al agente en la sesión. Como en los pasos de prosa, el ejecutor repite la comprobación sobre lo entregado (RF-126) y, agotados los intentos, el `detener_obra` de su paso detiene la obra con su motivo | `prueba` |

| ID | Decisión | Por qué |
| --- | --- | --- |
| D-91 | **Se arregla la comprobación, no los datos** | Los eventos estaban bien: lo que fallaba era mirar solo la mitad de lo que el backend sabe del artefacto, y exigir un campo que el tipo de evento no tiene. Reescribir cuerpos rompería la inmutabilidad (RF-23, D-32), y rehacer la obra entera para que un agente repitiera un número que el backend ya tenía sería gastar horas en nada. Como la comprobación se deriva cada vez (D-59), la misma versión pasa en cuanto la regla es la correcta |
| D-92 | **La opcionalidad sale de los ejemplos del esquema, no de una lista por tipo de evento** | El esquema es el formato que ve el rol y la vara de la puerta a la vez, y así sigue: un ejemplo más enseña al Contable que un `transcurre_tiempo` no lleva objeto y le dice lo mismo a la puerta. Una tabla aparte de campos por `tipo_de_evento` sería una segunda verdad que el rol no ve. Qué objeto le toca a cada tipo lo sigue mirando el Verificador de continuidad, que es quien lee el texto |
| D-93 | **`validar_capitulo` en `plegar` y `destilar`; corrige D-55 para esos dos pasos** | D-55 no comprobaba al escribir el esquema de los roles sin hook porque no tenían vuelta de corrección. Con el hook la tienen, y el precio de no tenerla ya se ha pagado: una obra de diez capítulos entera, terminada y sin poder publicarse por campos que el agente habría escrito si se los hubieran pedido. `policy` no entra: busca palabras vetadas en prosa, y estos dos pasos no la escriben. La longitud y los elementos personalizados siguen solo en la puerta, como decía D-55 |

**Qué queda fuera.** Que el backend escriba el capítulo dentro del cuerpo: el
cuerpo es del rol y no se toca. Comprobar el tipo o el valor de cada campo: la
puerta del esquema mira presencia, como hasta ahora.

**De dónde sale.** RF-23, RF-141, RF-181; D-32, D-59; la obra `obr_7a0f5152`,
terminada con 38 fallos de `esquema` y ninguno de texto.

**Documentos que hay que poner al día en la fase 3.** `validators.md` §7 (la
puerta de publicación y los guardarraíles) y §8, los métodos de RF-207 a RF-209;
`architecture.md` §4, los hooks de los subagentes.

### 4.24 El Contable fecha dentro del marco del plan

**El problema.** Con la puerta del esquema arreglada y Lean instalado, la misma
obra `obr_7a0f5152` falla la cronología 74 veces: 45 de orden temporal y 29 de
un solo lugar. Las fechas del Planificador son coherentes —`marco.instante` de
cada escena, de octubre a noviembre de 1584—, pero las del Contable no: 1500 en
el capítulo 1, 1588 en el 2, 1577 en el 7. El Contable fecha lo que el texto
dice, y el texto casi nunca dice el año: «pasaron las semanas de la cuaresma».
Su ventana era el estado en N-1, el texto aceptado y el vocabulario de eventos;
el estado en N-1 guarda dónde está cada quien, no cuándo, y el capítulo 1 no
tiene N-1. Sin ancla, el año lo inventa, y un año inventado envenena el orden de
todos los capítulos siguientes, que es justo lo que Lean mira.

**La decisión, en una frase.** El Contable recibe el marco temporal del
capítulo —la época de la obra, la última fecha que él mismo cerró y el lugar y
el instante que el Planificador dio a cada escena del capítulo— y fecha dentro
de él, salvo que el texto diga otra cosa.

| ID | Requisito | Verificación |
| --- | --- | --- |
| RF-210 | **El marco temporal del capítulo.** La proyección de `plegar` lleva un material más, `marco_temporal_del_capitulo`: la `epoca` del brief; la `fecha_de_cierre_anterior`, la `fecha_resultante` más tardía entre los `EventoEstado` de capítulos anteriores, o nada en el capítulo 1; y `escenas`, una fila por escena del capítulo, en su orden, con su `id` y el `lugar`, el `instante` y la `duracion` de su `marco`, y nada más de la escena. El prompt del Contable dice que el año sale de ahí cuando el texto no lo da, que una fecha no retrocede respecto a la de cierre anterior salvo que el texto narre un recuerdo, y que el texto manda sobre el plan cuando se contradicen | `prueba` |

| ID | Decisión | Por qué |
| --- | --- | --- |
| D-94 | **El Contable ve el marco de las escenas y nada más del plan** | «No ve el plan» era para que transcribiese lo que pasó y no lo que se planeó: un objetivo o una revelación del plan que el texto no cumple no debe acabar en el log. La fecha y el lugar son otra cosa: son el decorado que el Planificador fijó y el Redactor escribió, rara vez se repiten en la prosa, y sin ellos la única alternativa es inventar. Por eso entra solo `marco`, y no el objetivo, el elenco ni lo revelado. La fecha de cierre anterior la escribió el propio Contable, así que no es información nueva, solo memoria que el estado en N-1 no guardaba. Que el texto mande sobre el plan conserva lo que D-05 quería: el Contable calcula y escribe, y el Verificador compara |

**Qué queda fuera.** Que el backend corrija o rellene fechas: la fecha sigue
siendo del Contable y la cronología sigue derivándose de lo que él escribió
(D-27). Que el Planificador reciba lo que Lean encontró: lo sigue dejando fuera
§4.16.

**De dónde sale.** RF-25, RF-40, RF-85; D-05, D-27; §4.16; la obra
`obr_7a0f5152`, que con Lean instalado falla 74 veces la cronología por fechas
del Contable sin ancla.

**Documentos que hay que poner al día en la fase 3.** `architecture.md` §3, lo
que ve el Contable de estado; `validators.md` §8, el método de RF-210.

### 4.25 Lo que el ejecutor lee de lo que entrega un agente

**El problema.** Al rehacer `obr_7a0f5152` desde el capítulo 1, la obra se
detuvo antes de escribir una línea: el Planificador entregó dos veces un JSON
entre vallas de código que el ejecutor no leyó. No era mala suerte: en las
trazas de esa obra hay 44 intentos fallidos, y la mayoría no son de contenido.
Unos 25 son un tipo con tilde —`Crítica`, `Decisión`—, que la tabla de
gobierno no reconoce porque los tipos del almacén se escriben sin tilde. Unos 12 son JSON entregado entre vallas con
texto delante o detrás —«No tengo acceso a búsqueda web; registro la
limitación: …»—, que `leer_entrega` solo aceptaba si la respuesta *empezaba*
por la valla y *terminaba* en ella. Cada uno es un intento gastado en algo que
el backend podía leer, y dos seguidos detienen la obra.

**La decisión, en una frase.** El ejecutor lee el objeto JSON donde el agente
lo haya puesto y reconoce el tipo escrito con tildes; lo que no sea JSON sigue
siendo un intento fallido.

| ID | Requisito | Verificación |
| --- | --- | --- |
| RF-211 | **El objeto, donde esté.** `leer_entrega` prueba, por este orden, la respuesta entera; el contenido del primer bloque entre vallas de código, esté donde esté en la respuesta; y el tramo que va de la primera llave de apertura a la última de cierre. Vale el primero que sea un objeto JSON, y el texto alrededor no va a ninguna parte. Si ninguno lo es, el fallo dice el principio y el final de la respuesta y dónde se rompió el JSON, para que una respuesta cortada se distinga de una mal escrita. El hook y el ejecutor siguen usando la misma función (RF-126) | `prueba` |
| RF-212 | **El tipo, sin tildes.** `leer_entrega` lee el `tipo` de cada artefacto sin tildes: ningún tipo del almacén lleva, así que `Crítica` solo puede querer decir `Critica`. Como lo hace la misma función, el hook y el ejecutor lo leen igual (RF-126). Solo se toca el envoltorio: el cuerpo se guarda como vino (RF-23). Un tipo que ni así existe sigue fallando como hasta ahora, y la tabla de gobierno sigue decidiendo quién escribe qué | `prueba` |

| ID | Decisión | Por qué |
| --- | --- | --- |
| D-95 | **Se lee con más tolerancia la forma, no el contenido** | La instrucción común ya pide JSON sin texto alrededor y sin vallas, y los agentes la incumplen de las dos maneras de siempre. Rechazar lo que se puede leer no enseña nada al agente, porque el reintento es otro agente sin memoria del anterior: solo gasta un intento y acerca la detención. Lo que se tolera es exactamente lo que no cambia el significado: dónde está el objeto y una tilde en un nombre de tipo. Un JSON roto, un tipo inventado o un rol que escribe lo que no le toca siguen fallando |

**Qué queda fuera.** Reparar JSON mal formado —comillas sin escapar, una
respuesta cortada—: eso sí cambiaría lo que se guarda. Normalizar otros campos
del envoltorio.

**De dónde sale.** RF-23, RF-126; la versión 2 de `obr_7a0f5152`,
detenida en el Planificador del capítulo 1, y las 44 trazas fallidas de la 1.

**Documentos que hay que poner al día en la fase 3.** `architecture.md` §4, el
ejecutor de subagentes; `validators.md` §8, los métodos de RF-211 y RF-212.

### 4.26 Un solo lugar, con el viaje que lo explica

**El problema.** Con el Contable fechando ya dentro del marco (§4.24), el
capítulo 1 de la versión 2 de `obr_7a0f5152` sale con fechas coherentes —el 10
y el 11 de mayo de 1584— y aun así falla la cronología en sus doce sucesos. La
copista está en el taller, `viaja_a` la biblioteca y allí adquiere unos apuntes,
todo el 10 de mayo: RF-151 lo da por imposible, porque dos sucesos del mismo
día en lugares distintos no pueden compartir presentes. Con fechas al día, que
es la precisión que el Contable conoce, cualquier novela en la que alguien
cruce una calle falla. La regla estaba pensada para el viaje imposible —el
bautizo en Valladolid y el de Madrid el mismo día del brief
`incoherencia-temporal`—, y lo que la distingue de cruzar una calle no es la
fecha, sino que conste el viaje.

**La decisión, en una frase.** Dos sucesos del mismo día en lugares distintos
pueden compartir un presente si ese día consta que ese presente llegó a uno de
los dos: un `viaja_a` suyo, del mismo día, con ese lugar resultante.

| ID | Requisito | Verificación |
| --- | --- | --- |
| RF-213 | **El viaje que lo explica.** El volcado lleva de cada suceso, además de quién muere, quién llega: el sujeto de un `EventoEstado` `viaja_a`, o nadie. El invariante de un solo lugar se comprueba contra la cronología entera: dos sucesos del mismo día exacto, en lugares distintos y con un presente común, son coherentes si en la cronología hay un suceso de ese mismo día, en uno de esos dos lugares, en el que ese presente llega. Si no lo hay, falla como hasta ahora, y el detalle dice que no consta que viajase a ninguno de los dos | `prueba` |

| ID | Decisión | Por qué |
| --- | --- | --- |
| D-96 | **Lo que excusa es el viaje escrito, no la distancia** | El backend no sabe a cuántas leguas está un lugar de otro: la ficha dice su ubicación en texto libre, y calcular distancias es lo que D-05 deja fuera. Lo que sí está escrito es el `viaja_a` del Contable, que es quien transcribe lo que el texto cuenta. Si el texto hace andar a alguien del taller a la biblioteca, hay un viaje; si lo pone en Valladolid y en Madrid el mismo día sin moverlo, no lo hay y Lean lo ve, que es lo que el brief de la incoherencia temporal busca. El precio está dicho en «qué queda fuera» |

**Qué queda fuera.** Un viaje escrito pero imposible —de Valladolid a Madrid
en una mañana del siglo XVII— pasa: sin distancias no se puede ver, y lo mira
el Verificador de continuidad, que lee el texto. Tampoco se ordenan los sucesos
dentro del día.

**De dónde sale.** RF-150, RF-151; D-05, D-27; §4.24; la versión 2 de
`obr_7a0f5152`, cuyo capítulo 1 falla los doce sucesos por un desplazamiento
dentro de Salamanca.

**Documentos que hay que poner al día en la fase 3.** `validators.md` §3, los
invariantes de la cronología, y §8, el método de RF-213.

## §5 Requisitos de datos

| ID | Requisito | Verificación |
| --- | --- | --- |
| RD-01 | SQLite con `WAL`, `foreign_keys` activas y tablas `STRICT`. Un solo proceso escritor; las lecturas de la API no bloquean la producción | `prueba` |
| RD-02 | El esquema espeja las tres capas —obra, mundo, producción— más la `Traza`, y toda fila cuelga de un `id_obra`, salvo las de la entrevista, que es anterior a la obra y cuelga de su `id_entrevista` (RF-79, D-24), y la lista global de lo vetado, que es de la instalación (RD-26) | `inspeccion` |
| RD-03 | Los artefactos viven en una tabla por tipo con el cuerpo declarativo en una columna y, al lado, solo las columnas por las que se consulta: obra, capítulo, escena, estado, severidad, dimensión, rol | `inspeccion` |
| RD-04 | Todo campo de vocabulario controlado se declara como valor cerrado en el esquema. Un campo de esos en texto libre es un defecto: es lo que hace incomputable el predicado que lo vigila | `analisis` |
| RD-05 | Los fragmentos de `Fuente` se indexan con la extensión vectorial, particionados por `id_obra`, para que el Documentalista recupere por parecido y luego filtre por fecha y lugar. El texto íntegro de la fuente se guarda antes de trocearlo (RF-61) | `prueba` |
| RD-10 | Tres colecciones indexadas y ninguna más: documental, obra·prosa y obra·estructura. Cada fragmento guarda de qué artefacto sale y las columnas por las que se filtra después: obra, capítulo, fecha, lugar y ámbito | `inspeccion` |
| RD-11 | El fragmento no es una entidad del dominio, es un trozo de un artefacto que ya existe. Indexar no duplica el cuerpo del artefacto | `inspeccion` |
| RD-12 | Toda consulta por parecido va particionada por `id_obra`. Ninguna obra recupera fragmentos de otra | `prueba` |
| RD-13 | El modelo de embeddings queda registrado junto a cada fragmento. Cambiar de modelo obliga a reindexar la obra entera; dos modelos conviviendo en el índice de una obra son un defecto | `prueba` |
| RD-14 | Toda consulta al índice es **híbrida**: se busca por palabra exacta y por parecido de sentido sobre la misma colección, y los dos órdenes se funden en uno solo antes de recortar a `k`. Ninguna de las dos vías se consulta a solas | `prueba` |
| RD-15 | Las huellas se calculan en la propia máquina con el modelo declarado en D-10. Ni indexar ni consultar sale al exterior: el único rol que sale es el Documentalista, y sale a buscar fuentes, no a calcular huellas | `inspeccion` |
| RD-06 | Toda consulta que sirve una proyección está acotada por `id_obra` y por capítulo. Ninguna recorre la prosa acumulada: nada cuyo tamaño crezca con la obra entra en una ventana | `analisis` |
| RD-07 | No se borra nada. Caducar es marcar; descartar es marcar. El almacén es el registro de por qué la obra es como es | `prueba` |
| RD-08 | **Nada de lo que el sistema produce toca el sistema de ficheros.** Artefactos, borradores, críticas, log de eventos, estado materializado, resúmenes, decisiones y trazas viven en la base de datos, incluidos los cuerpos de texto y los embeddings. No hay carpeta de trabajo, ni volcados a disco para inspeccionar: lo que hay que ver se sirve por la API (§6) | `inspeccion` |
| RD-09 | Los prompts de los doce roles y el guion declarativo son entrada versionada con el repositorio, no almacenamiento: son lo único que el sistema lee de fuera de la base de datos, y nunca los escribe | `inspeccion` |
| RD-16 | `Recuerdo` tiene tabla propia en la capa Mundo, con el texto íntegro tal como lo entregó el editor. Entra en la ventana de un agente como dato delimitado, nunca como instrucción, igual que el cuerpo de una `Fuente` | `inspeccion` |
| RD-20 | Las versiones tienen tabla propia fuera de las de artefactos, como el control de ejecución: la escribe el backend y no un rol. Una fila por versión y obra; no se borra, y solo la marca de terminada cambia, una vez (RF-110) | `prueba` |
| RD-21 | Toda tabla de artefactos lleva la versión en que se escribió cada fila, que no cambia nunca, y la versión que la relevó, que se pone una sola vez y solo junto con la marca de caducado (RF-112) | `prueba` |
| RD-22 | Las publicaciones son un registro de solo añadir: ni se borran ni se modifican (RF-116) | `prueba` |
| RD-23 | La caché del estado materializado se indexa por obra, versión y capítulo, y lleva también la versión que la relevó (RF-115, D-44) | `prueba` |
| RD-17 | `licencia` admite un cuarto valor, `personal`, para lo que viene de la vida del destinatario. Es inmutable como `canon`, pero su respaldo no es una `Fuente` sino un `Recuerdo`, y por eso no cuenta en la cobertura documental (OBJ-06) ni en la fidelidad histórica | `analisis` |
| RD-25 | El veredicto de los hooks vive en el cuerpo de la `Traza`, en `ganchos`, y no en una tabla ni en una columna nueva: no hace falta migración. Nadie consulta por él todavía; quien lo necesite para filtrar lo sacará a columna entonces | `prueba` |
| RD-26 | La lista global de lo vetado tiene tabla propia, fuera de las de artefactos: es de la instalación, así que no cuelga de ningún `id_obra` (RD-02), y no se versiona. La siembra la migración 8; no se borra ni se modifica (RF-131) | `prueba` |
| RD-27 | El registro de auditoría de `policy` tiene tabla propia, de solo añadir, fuera de las de artefactos: cuelga de la obra y de la `Traza` del intento, lleva `nivel_de_veto` y `decision_de_policy` como valores cerrados, y no se borra, no se modifica, no se caduca ni se releva. Capítulo, escena, tarea e intento no se copian: se leen de su `Traza` (RF-135, RF-136, D-53) | `prueba` |
| RD-34 | El juez de la novela no escribe nada en SQLite: ni tabla, ni artefacto, ni `Traza`, ni migración. Su huella son los scores de Langfuse y lo que la función devuelve a quien la lanza (RF-193, RF-199) | `prueba` |
| RD-35 | Los briefs de prueba son entrada versionada del desarrollador, como el guion y los prompts de RD-09: el sistema los lee solo cuando alguien los lanza y nunca los escribe. No son producción, así que RD-08 no les aplica (RF-201) | `inspeccion` |
| RD-30 | El resultado de la puerta de publicación no tiene tabla ni se guarda: se deriva al pedirlo de lo que ve la versión (RF-146, RF-147, D-59). No hace falta migración | `prueba` |
| RD-31 | Nada de Langfuse se guarda: ni en SQLite ni en disco. La sesión, la traza de cada versión y el `id` de cada score de la puerta se derivan de la entrevista, la obra y la versión (D-78), y las sumas de coste se calculan de la `Traza` y de las pasadas de la entrevista al mandarlas. No hace falta migración | `inspeccion` |

La cronología en Lean (§4.16) no añade tabla ni migración: el módulo de cada
comprobación vive en un directorio temporal que se borra (RF-153, D-62), y sus
críticas van a la tabla de `Critica` que ya existe (RF-154).
Los datos de §4.18 no llevan identificador propio en esta tabla: el registro
del cambio del lector tiene tabla propia, de solo añadir, fuera de las de
artefactos, que crea la migración 11 y no se borra, ni se modifica, ni se
releva; la ficha nueva es una fila más de la tabla de su tipo, con sus columnas
de versión (RF-173); y el PDF no tiene tabla ni fichero (RF-178).

Un único ejemplo, que fija el estilo del cuerpo de todo artefacto. Los demás no
se enumeran aquí: su esquema vive junto al contrato de la tarea que los escribe.

```json
{
  "id": "cri_0a91",
  "tipo": "Critica",
  "objeto": "esc_0007",
  "dimension": "integridad_de_pov",
  "severidad": "bloqueante",
  "evidencia": "«...supo que el conde ya había firmado», con el conde ausente de la escena",
  "accion_sugerida": "Narrar solo lo accesible al foco o declarar el conde presente en el contrato",
  "detectada_por": {
    "rol": "verificador_de_continuidad",
    "tarea": "tar_1182",
    "contrato": "integridad_de_pov"
  }
}
```

## §6 Requisitos de interfaz

| ID | Operación | Para qué | Requisito |
| --- | --- | --- | --- |
| RI-01 | `POST /obras` | Lanzar una obra desde el brief | Única llamada de escritura necesaria por obra (RF-02, OBJ-07). Devuelve `id_obra` y no espera a que la obra termine |
| RI-02 | `GET /obras/{id}` | Ficha y avance | Estado de la obra, capítulo en curso y recuento de capítulos cerrados y marcados |
| RI-03 | `GET /obras/{id}/manuscrito` | Leer | Solo texto aceptado (RF-50) |
| RI-04 | `GET /obras/{id}/capitulos/{n}` | Inspeccionar un capítulo | Plan, escenas con su contrato, borrador vigente y críticas |
| RI-05 | `GET /obras/{id}/criticas` | Ver defectos | Filtros de RF-51 |
| RI-06 | `GET /obras/{id}/trazas` | Medir el sistema | Filtrable por capítulo, rol y tarea (RF-52) |
| RI-07 | `GET /obras/{id}/estado` | Auditar continuidad | Estado plegado hasta el capítulo indicado, y log de eventos (RF-54) |
| RI-08 | `GET /obras/{id}/progreso` | Ver la ejecución en vivo | Flujo de eventos de progreso mientras la obra corre (RF-53). Un contrato OpenAPI no describe lo que viaja dentro de un flujo abierto: la forma de cada evento es la que sirve la consulta puntual del mismo recurso, y ahí sí queda descrita |
| RI-09 | `POST /obras/{id}/detener` · `/reanudar` | Control, no mantenimiento | RF-04. No hay ninguna operación de limpieza ni de archivado que el editor deba ejecutar: rehacer y publicar (RI-11, RI-12) son decisiones editoriales, no mantenimiento |
| RI-10 | `GET /openapi.json` | Acordar la frontera | Documento OpenAPI 3.1 del borde entero, generado desde los modelos declarados. Se vuelca además a `backend/openapi.yaml`, que es el contrato versionado del que `frontend/` deriva su cliente (D-11, RNF-09) |
| RI-11 | `POST /obras/{id}/versiones` | Rehacer desde un capítulo | RF-111. Devuelve la versión nueva y no espera a que termine |
| RI-12 | `POST /obras/{id}/versiones/{n}/publicar` | Publicar una versión terminada | RF-116. Es el único camino por el que una versión queda publicada |
| RI-13 | `GET /obras/{id}/versiones` | Ver las versiones | RF-117 |
| RI-14 | `?version=` en manuscrito, capítulo, críticas, estado, hechos y cronología | Leer una versión concreta | RF-117. Sin el parámetro, la versión de referencia |
| RI-15 | `GET /obras/{id}/trazas` | Ver por qué un intento falló | Cada `Traza` servida trae además `ganchos`, lo que RF-127 guardó: vacío si su paso no lleva hooks |
| RI-16 | `GET /obras/{id}/policy` | Ver qué encontró la política de lo vetado | RF-138. Filtrable por capítulo, nivel y decisión. Sin operación de escritura |
| RI-17 | `GET /obras/{id}` | Saber por qué se detuvo una obra | La ficha trae además el motivo de la detención, vacío si no está detenida (RF-137) |
| RI-18 | `POST /obras/{id}/versiones/{n}/publicar` | Saber por qué no se publicó | RF-146. Si la puerta falla, 409 con `detail` y `puerta`: el mismo resultado que RI-19. Una versión sin terminar sigue siendo 409 solo con `detail` |
| RI-19 | `GET /obras/{id}/versiones/{n}/puerta` | Ver la puerta antes de publicar | RF-147. Si pasa, si la versión ha terminado y la lista de fallos, cada uno con su validador, su capítulo y su detalle |
| RI-20 | `GET /obras` | Volver a cualquier obra y ver todas de un vistazo | RF-204 y RF-205. Cada obra con su ficha y su situación, de la más reciente a la más antigua. `GET /obras/{id}` trae también la situación (RF-206) |

La cronología en Lean (§4.16) no añade rutas: el resultado de la puerta
(RI-18, RI-19) trae `comprobacion_formal` y el validador `cronologia`
(RF-152), y la respuesta de publicar (RI-12) trae también
`comprobacion_formal` (RF-155).
El borde de §4.18 tampoco lleva identificador propio aquí:
`POST /obras/{id}/cambios` cambia el nombre de un hecho y devuelve la versión
nueva sin esperar a que termine (RF-170, RF-171); `GET /obras/{id}/versiones`
trae el `cambio` de cada versión y `GET /obras/{id}` el destinatario y la
dedicatoria (RF-177); y `GET /obras/{id}/pdf`, con `?version=` como RI-14,
descarga el PDF (RF-178).

Tres reglas de frontera. La interfaz web nunca lee ficheros ni la base de datos.
El contrato HTTP se valida en el borde con modelos declarados —es el único sitio
donde el backend impone tipos, porque ahí habla con algo que no es un agente—. Y
ese contrato se publica en OpenAPI: es el único acuerdo entre `backend/` y
`frontend/`, y no se redacta, se genera (D-11).

## §7 Requisitos no funcionales

| ID | Requisito | Verificación |
| --- | --- | --- |
| RNF-01 | El pico de contexto de entrada concurrente no pasa de 100 000 tokens en ningún instante, con el 20 % reservado como margen (OBJ-01). La salida de las tareas abiertas no cuenta contra el techo | `analisis` |
| RNF-02 | El coste de un capítulo no crece con la longitud de la obra (OBJ-02) | `analisis` |
| RNF-03 | Toda tarea deja `Traza`. Sin ella no se puede afirmar que el bucle converge, solo suponerlo | `analisis` |
| RNF-04 | El guion es reproducible: misma obra y mismos artefactos dan la misma secuencia de pasos, tandas y proyecciones. Lo que varía es la salida del modelo, no el recorrido | `prueba` |
| RNF-05 | Un solo lector y un solo escritor del almacén (RF-20) | `inspeccion` |
| RNF-06 | Un fallo del proveedor o un corte no deja artefactos a medias ni estados materializados inconsistentes: se escribe la unidad completa o nada | `prueba` |
| RNF-07 | Español en documentación, commits, nombres de entidad y mensajes de error de la API | `inspeccion` |
| RNF-08 | Ninguna operación de mantenimiento recurrente recae en el editor. Un paso manual periódico es un defecto de diseño, no una instrucción de uso | `inspeccion` |
| RNF-10 | La observación no cambia la producción: con Langfuse encendido, apagado o fallando, la misma obra da la misma secuencia de pasos y escribe lo mismo en SQLite, y lo único que espera a la red son los prompts, como mucho 5 segundos por prompt y proceso (RF-190) | `prueba` |
| RNF-11 | Ni los evaluadores ni las claves de Langfuse están donde un rol pueda leerlos: ningún evaluador, rúbrica de juez ni prompt de juez entra en el repositorio, y ningún subagente de tarea hereda una variable `LANGFUSE_` (RF-191, D-82) | Repositorio: `inspeccion`. Entorno: `prueba` |
| RNF-12 | El juez de la novela respeta el techo: su tope más el coste fijo del subagente caben en lo repartible, y solo se lanza sin producción en marcha (RF-197) | `analisis` |
| RNF-13 | El sistema evaluado no puede leer con qué se le evalúa: la rúbrica del juez de la novela no está en el repositorio ni entra en la ventana de ningún rol del censo (RF-202, D-83) | `inspeccion` |
| RNF-09 | El contrato volcado en `backend/openapi.yaml` es el que genera el código. Si el borde cambia y el contrato no se regenera, la comprobación lo vuelve a volcar y falla una vez, para que el movimiento de la frontera pase por el diff. No hay orden de mantenimiento que recordar (RNF-08) | `prueba` |

## §8 Decisiones de diseño de esta versión

| ID | Decisión | Por qué |
| --- | --- | --- |
| D-01 | El artefacto es un documento declarativo y el backend no lo tipa por dentro; los tipos se declaran solo en el borde HTTP | Es el invariante «sin harness a medida». Quien impone la forma del artefacto es el esquema en el contexto del agente que lo escribe y el rechazo del siguiente (RF-23) |
| D-02 | **Decisión tomada. Todo se guarda en SQLite y en ningún otro sitio.** No hay almacén de ficheros: los nombres `mundo/`, `obra/`, `log/`, `estado/` y `criticas/` de `architecture.md` §7 son grupos lógicos de artefactos, no carpetas en disco | `AGENTS.md` ya fijaba SQLite como persistencia y `architecture.md` §7 lo describía como ficheros. Queda una sola lectura: lo declarativo es el cuerpo del artefacto y SQLite es el único lugar donde se escribe. Un segundo sitio donde persistir sería un segundo escritor y rompería la frontera única. Cierra una decisión de `architecture.md` §8, y poner al día §7 y §8 es trabajo de la fase 3 |
| D-03 | **Propuesta de cierre.** El prompt y el contrato de cada rol viven junto a su tarea, en `tareas/<tipo>/` | Mantiene visible en el árbol la regla «un rol, una tarea»: declarar un rol es añadir una carpeta con todo lo suyo dentro. Cierra otra decisión abierta, con la misma condición |
| D-04 | Una sola orden por obra, y cada obra nace en su propio espacio | Evita de raíz el trabajo manual entre obras: no hay nada que archivar ni vaciar porque nunca se comparte espacio |
| D-06 | El Documentalista busca en internet, y v1 no trae corpus curado de época | Sin acceso al exterior no hay `Fuente` que recoger y OBJ-06 es inalcanzable. Un buscador no es una herramienta de cálculo: no sustituye ningún juicio del agente, le da material sobre el que juzgar, así que no reabre D-05. El corpus curado daría mejor léxico de época, pero exige trabajo humano de preparación y eso choca con OBJ-07 |
| D-07 | Recuperar por parecido lo hace `almacen/`, no un rol nuevo | Recuperar elige qué mirar, no decide qué es cierto: no hay trabajo de dominio que el censo no cubra, así que declarar un rol «recuperador» ensancharía el censo sin motivo. Colocar lo recuperado en la ventana es ensamblar una proyección, que ya es trabajo de `nucleo/` |
| D-08 | **Las tareas las ejecutan subagentes de Claude Code con modelo Haiku.** El backend lanza el subagente, le entrega la proyección ya ensamblada y recoge el artefacto que devuelve; no llama a ninguna API de modelo ni gestiona claves | Es la lectura estricta de «sin harness a medida»: el agente ya existe como agente, con su propio andamiaje, y el backend solo reparte turnos. Fija además los permisos de verdad (RF-35): cada rol arranca sin ninguna herramienta salvo las que su contrato le concede, de modo que el aislamiento no depende de que el prompt se lo pida. Haiku por coste: son cientos de tareas por obra y ninguna razona sobre la obra entera |
| D-09 | **El Documentalista agota la búsqueda externa, pero no bloquear es la regla.** Sin fuente utilizable escribe la constancia del intento y la producción sigue | Bloquear una escena por falta de fuente deja la obra parada esperando a una persona, que es justo lo que OBJ-07 y RNF-08 prohíben. El coste se paga donde se puede medir —OBJ-06 baja y la auditoría de cierre lo saca—, no en una intervención manual |
| D-10 | **Las huellas para buscar por parecido se calculan en la propia máquina, con `fastembed` y el modelo multilingüe `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`** (384 dimensiones), y la búsqueda es híbrida: palabra exacta y parecido de sentido, fundidos en un solo orden | Sin cuenta, sin clave y sin coste por capítulo, que es lo que permite reindexar la obra entera sin pensárselo (RD-13). Multilingüe porque la obra es en español y el modelo que `fastembed` trae por defecto está entrenado en inglés. Es el único multilingüe de 384 dimensiones del catálogo de `fastembed`; el resto o no es multilingüe, o tiene la huella más larga y pesa diez veces más. Híbrida porque el nombre propio y la fecha exacta son justo lo que peor encuentra el parecido de sentido, y son la mitad de lo que el Documentalista busca |
| D-11 | **El contrato de la frontera es un documento OpenAPI generado desde el código, nunca redactado a mano.** v1 lo genera, lo publica y lo versiona; derivar de él el cliente de la interfaz es trabajo de `frontend/`, que está fuera del alcance de v1 | OpenAPI es el estándar con el que se acuerdan los contratos de API, y tenerlo escrito y versionado es lo que permite ver en un diff cuándo se mueve la frontera, en lugar de descubrirlo cuando el cliente rompe. Generarlo desde los modelos del borde evita la única forma real de perder calidad con esto: mantener dos descripciones del mismo sistema hasta que divergen. La dirección contraria —redactar el documento primero y obligar al código a cumplirlo— duplicaría lo que D-01 concentra a propósito en un solo sitio |
| D-12 | **El destinatario y los suyos aparecen en la obra con sus nombres reales, sin traducir a la época.** La transposición la absorbe el grado de licencia: lo que viene de su vida se marca `personal` y el detector de anacronismos lo deja en paz | Es lo único que garantiza que se reconozca sin que nadie le explique la clave, que es para lo que se encarga la obra. Traducir cada dato a un equivalente del siglo daba una novela más limpia de época y un regalo que hay que descifrar. La alternativa del marco contemporáneo dejaba lo personal en los bordes —dedicatoria y prólogo— sin entrar en la historia. El coste es una excepción declarada en cuatro dimensiones, que es preferible a una lista de palabras a mano dentro del validador |
| D-13 | **Un recuerdo del destinatario es un `Recuerdo`, no una `Fuente` de tipo nuevo.** Nace con el alta de la obra y ningún rol del censo lo escribe | El invariante «solo el Documentalista escribe `Fuente`» es lo que hace que un dato histórico sin respaldo sea detectable como alucinación. Meter ahí las anécdotas del comprador obligaría a abrir esa puerta a un segundo escritor y el invariante dejaría de significar nada. Son además cosas distintas: una `Fuente` es evidencia de una época y un `Recuerdo` es evidencia de una persona, sin fiabilidad ni tipo documental que declarar. El precio es un segundo sitio donde mirar de dónde sale un dato |
| D-14 | **El papel del destinatario en la obra lo decide el Planificador y lo deja escrito en el `Plan`.** No es un campo del brief | Preguntárselo al editor es una pregunta más antes de tener una novela, y puede pedir un papel que no case con la premisa. Dejarlo implícito haría inverificable la personalización, porque el validador no sabría dónde mirar: escribirlo en el `Plan` da las dos cosas, libertad narrativa y un sitio fijo donde comprobarlo |
| D-60 | **La tesis temática y el elenco declarado son opcionales en el brief, igual que los arcos.** Si no vienen, nadie los rellena por el editor: el Planificador trabaja sin tesis declarada y el Constructor de mundo decide quién existe. La entrevista no los pide ni los recuerda: no salen en `faltan` | Obligarlos convierte en trámite una pregunta que el editor puede no saber contestar al encargar, y cada pasada de más cuesta. Ningún validador los comprueba —la regla de corte de `AGENTS.md` ya los dejaba en el límite— y los dos roles que los leen saben trabajar sin ellos. Se descarta que el Entrevistador los invente: solo puede proponer lo que cite literal de un texto pegado (RF-74) |
| D-88 | **Las tareas de una tanda corren a la vez, en hilos del propio proceso, y solo si quien las ejecuta lo declara.** El ejecutor de subagentes lo declara; los fingidos de las pruebas no, y con ellos la tanda se sigue mandando en serie. Cuatro reglas lo acompañan. **Una tanda a la vez en la instalación**: si caminan dos obras —relanzar las caídas lo hace—, sus tandas se turnan. **La primera tarea que detiene la obra es la única que la detiene**: las demás de su tanda terminan el intento en curso, no empiezan otro y no vuelven a detenerla. **Los hilos son de la tanda**: nacen con ella, sueltan su lector del almacén al terminar y no retienen el proceso si se apaga. **Lo que lee el capítulo entero lo lee en el orden de las escenas**, no en el de creación | El caminante calculaba la anchura de RF-13 y luego mandaba la tanda tarea a tarea: el techo se respetaba porque nunca se usaba, y un capítulo de cuatro escenas costaba una hora de reloj esperando a subagentes que no dependen unos de otros. Hilos y no procesos ni `asyncio`, porque cada tarea ya es un subproceso: el hilo ensambla la ventana, lo espera y guarda lo que vuelve, y el almacén ya tenía un escritor serializado y un lector por hilo, así que sigue habiendo un solo escritor (RNF-05). Recoger en el orden del guion es lo que mantiene el recorrido reproducible (RNF-04). Que lo declare el ejecutor es porque los fingidos contestan según el orden en que les llegan los encargos: en paralelo, sus casos sembrados caerían en otra escena. Las cuatro reglas salen de lo que el paralelo rompía. En serie una obra ocupaba como mucho una tarea, y dos obras cabían en el techo; con la tanda llena, dos ya lo pasan (RNF-01), y el techo es de la instalación (§11). Una hermana que agota después de la primera volvía a detener la obra y deshacía un `reanudar` dado mientras la tanda cerraba. Un hilo que durase más que su tanda dejaba abierto su lector hasta cerrar el almacén, y un reparto de hilos que no fueran de fondo retenía el apagado hasta que terminase cada subagente, cuyo resultado ya no tiene dónde guardarse. Y el orden de creación tiene resolución de segundos: dos escenas redactadas a la vez pueden empatar, y la costura y el Contable leerían el capítulo desordenado. Un subagente no se corta a medias: cortarlo dejaría una `Traza` abierta sin veredicto, y lo que escriba ya se descarta al volver al punto de guardado (§4.10) |
| D-05 | v1 no usa herramientas externas de cálculo | La decisión sigue abierta. Mientras lo esté, coherencia temporal, fatiga léxica y léxico vetado van como `analisis` contra el dato ya escrito, y lo que las vigila es la reincidencia por dimensión |

Las decisiones D-20 a D-24, las de la entrevista, están en §4.8, junto a los
requisitos que justifican; las D-83 a D-87, las del juez de la novela, en §4.21.

D-88 pone al día en la fase 3 la tercera regla de `architecture.md` §3, que decía que redactar y revisar «van en fila»: van en fila respecto de los demás pasos, y dentro de su paso las escenas van en tanda, como ya declaraba el guion. La tanda en sí ya estaba descrita así —«se abren seis, se espera a que cierren y se abren las siguientes»—: era el código el que no la cumplía. Pone al día también la matriz de cobertura de `validators.md` §8.

D-60 pone al día en la fase 3 el atributo `Obra` de `definitions.md`, que marca
la tesis y el elenco como opcionales, y la fila del Constructor de mundo en
`architecture.md` §2.

## §9 Trazabilidad

| Bloque de requisitos | De dónde sale |
| --- | --- |
| §4.1 Alta y arranque | `architecture.md` §4; invariante de cero pasos manuales |
| §4.2 Guion | `architecture.md` §3 y §4 |
| §4.3 Almacén | `architecture.md` §2, §3 y §7; `AGENTS.md` (frontera y pila) |
| §4.4 Calidad | `architecture.md` §5; `validators.md` §3 y §4 |
| §4.5 Cierre | `architecture.md` §4 y §6; `validators.md` §4 (alcance global) |
| §4.6 y §6 Consulta e interfaz | `AGENTS.md` (frontera única); `architecture.md` §7 |
| §4.7 Recuperación y fuentes | `architecture.md` §3 (recuperación por parecido y de dónde sale la documentación) |
| §5 Datos | `definitions.md` (vocabularios); `AGENTS.md` (SQLite y extensión vectorial) |
| RF-06 a RF-09, RD-16, RD-17 | `definitions.md` (capa Mundo y grado de licencia); D-12, D-13 y D-14 |
| §4.12 Versiones | `architecture.md` §3 (estado como pliegue) y §4 (punto de guardado); RD-07; D-32 |
| §4.13 Los dos hooks, RD-25, RI-15 | `architecture.md` §3 (en frío y presupuesto) y §4 (reintentos por paso); `validators.md` §7 (guardarraíles); RF-06, RF-95 a RF-102 |
| §4.14 Lo vetado, RD-26, RD-27, RI-16, RI-17 | §4.10 y §4.13; `validators.md` §7 (guardarraíles y adversario); RF-06, RD-02 y RD-08 |
| §4.15 Validadores y puerta, RD-30, RI-18, RI-19 | `validators.md` §3 (contrato de verificación) y §7 (guardarraíles); RF-08, RF-23, RF-84, RF-116, RF-123; D-43, D-46 |
| §4.16 La cronología en Lean | `architecture.md` §7 (qué se pierde sin cálculo determinista) y §8; `validators.md` §3 y §4; RF-85, RF-86, RF-146, RF-147; D-28, D-59 |
| §7 No funcionales | `architecture.md` §3 (presupuesto); `validators.md` §6 |
| §4.17 Validador formal del sistema | §4.10, §4.12, §4.15 y §4.18; RF-92, RF-93, RF-114, RF-116; D-40, D-42, D-59; OBJ-07 y RNF-08 |
| §4.18 Cambio del lector y PDF | §4.9 (menciones), §4.10 (punto de guardado) y §4.12 (versiones); D-13, D-40, D-42; RD-08; `validators.md` §10 |
| §4.20 La producción en Langfuse, RD-31, RNF-10, RNF-11, OBJ-09 | RF-52, RF-79, RF-93, RF-110, RF-126, RF-146, RF-147; D-03, D-08, D-35; RD-08; RNF-03, RNF-08; `validators.md` §7 |
| §4.19 Dónde va un artefacto y el testigo del Planificador | `architecture.md` §4 (ciclo de vida del capítulo); §4.17 (el modelo); RF-23, RF-35, RF-90, RF-92, RF-97, RF-98; D-30, D-34 |
| §4.21 El juez de la novela y los briefs de prueba, RD-34, RD-35, RNF-12, RNF-13 | `validators.md` §5, §7 y §9; RF-01, RF-100 a RF-102, RF-156; D-03, D-08; RNF-01 |
| §4.22 El listado de obras, RI-20 | SPEC2 §12; RF-04, RF-110, RF-116, RF-137, RF-177; RI-02, RI-17 |
| §4.23 Lo que la puerta del esquema da por presente | RF-23, RF-141, RF-181; D-32, D-59 |
| §4.24 El Contable fecha dentro del marco del plan | §4.16; RF-25, RF-40, RF-85; D-05, D-27 |
| §4.25 Lo que el ejecutor lee de lo que entrega un agente | RF-23, RF-126 |
| §4.26 Un solo lugar, con el viaje que lo explica | §4.16, §4.24; RF-150, RF-151; D-05, D-27 |

## §10 Verificación y criterios de aceptación

La verificación del propio sistema es la de `validators.md` §6 y no se duplica
aquí. Lo que sí fija este SRS es cuándo v1 está terminada:

0. **Recorrido en seco.** Con un ejecutor fingido que devuelve artefactos
   preparados en vez de llamar a Claude, el guion recorre los diez pasos de un
   capítulo de principio a fin: cada paso encarga su tarea al rol que le toca,
   ningún rol escribe una entidad que no le corresponde, las tandas respetan la
   anchura calculada y todo lo producido queda guardado y se puede volver a
   servir. Es el criterio que se comprueba sin producir novela ni gastar.
1. Una obra de tres capítulos de tres escenas corre de `POST /obras` a obra
   cerrada con **una sola** llamada de escritura (OBJ-07).
2. La `Traza` permite calcular OBJ-01 a OBJ-06 y fijar con ella las líneas base
   que hoy están pendientes.
3. Casos sembrados: un texto con un defecto conocido de una sola dimensión por
   caso. Se registra la tasa de detección y los falsos positivos por dimensión,
   sin exigir todavía una cifra: la primera medida es la línea base.
4. Un artefacto malformado a propósito produce `Crítica` bloqueante con objeto
   el artefacto y no llega al Revisor.
5. Detener, o cortar la producción en cualquier punto, y reanudar no duplica
   ni pierde trabajo cerrado (RF-92).
6. Regenerar un capítulo intermedio deja los siguientes replegados y
   consistentes.
7. Una obra con destinatario llega a cerrada: su nombre real aparece escrito en
   el manuscrito, el `Plan` declara qué papel se le dio, y ninguna de las cuatro
   dimensiones de anacronismo lo saca como defecto.
8. Una obra terminada de tres capítulos se rehace desde el 2: la versión 1
   sirve el mismo manuscrito, estado y cronología que antes; la 2 comparte el
   capítulo 1, reescribe el 2 y el 3 y los anota como cambiados. Ninguna está
   publicada hasta que se publica, publicar una versión sin terminar se rechaza
   y, publicada la 2, es la que se lee sin pedir versión.
9. **Los dos hooks.** Sin gastar: el programa del hook, alimentado con la
   entrada que le daría Claude Code, bloquea con código 2 una escena que trae
   una palabra vetada del brief o que no trae su `Borrador`, y deja terminar la
   buena; la orden del ejecutor lleva los dos hooks en los pasos 3, 5 y 7 y
   ninguno en los demás; y una salida final con una palabra vetada es un
   intento fallido que, agotados los reintentos, detiene la obra con el
   veredicto en la `Traza`. Con el CLI de verdad, un sondeo mínimo confirma que
   en `--print` el hook se dispara, bloquea y el agente vuelve a entregar.
10. **Lo vetado.** Sin gastar: el hook bloquea un término de la lista global
   en una obra sin destinatario, una palabra y un tema que vetó el comprador,
   y las variantes con otra mayúscula, sin acento y en plural; no bloquea un
   veto escondido dentro de otra palabra ni un tema dicho con otras palabras.
   Un Redactor fingido que insiste agota sus intentos y la ficha dice por qué
   se detuvo la obra; cada coincidencia, la de la sesión y la del veredicto
   final, está en el registro que sirve `GET /obras/{id}/policy`.
11. **La puerta de publicación.** Sin gastar: cada validador tiene un caso que
   pasa y otro que falla; el hook de forma bloquea un «Inés» donde la biblia dice
   «Ines» y deja pasar una palabra corriente parecida; una versión terminada con
   un capítulo corto, un nombre mal escrito, un hecho `personal` sin mención o un
   artefacto sin un campo de su esquema no se publica, y la respuesta dice cuál
   falló y en qué capítulo; y la misma obra sin el defecto se publica.
12. **La cronología en Lean.** Con Lean instalado, `lake build` demuestra los
   cuatro invariantes de una cronología coherente y no demuestra cada uno en
   una cronología rota a propósito solo en él; una obra limpia para los cuatro
   validadores de §4.15 con un personaje en dos lugares el mismo día no se
   publica, y el fallo queda como crítica de su capítulo. Sin Lean, la misma
   obra se publica y la respuesta dice `sin_comprobacion`.
13. **El validador formal del sistema.** TLC recorre entero el modelo de
   `backend/formal/tla/Produccion.cfg` y termina con «No error has been
   found»: la puerta se respeta, la versión anterior se conserva, hay una sola
   producción a la vez y toda versión en producción acaba terminada o detenida.
   Cada contraejemplo que salió por el camino está guardado con su traza junto
   al modelo y enlazado al cambio que provocó.
14. **El cambio del lector.** Sin gastar: en una obra terminada de tres
   capítulos en la que un hecho solo se menciona en el 1 y el 3, cambiarle el
   nombre abre la versión 2 con los capítulos 1 y 3 como cambiados; la 2 comparte
   el capítulo 2 —las mismas filas— y reescribe los otros dos con la ficha nueva
   en su canon; la 1 sirve lo mismo que antes, ficha vieja incluida. Un hecho sin
   menciones, una versión sin terminar y un nombre igual se rechazan sin crear
   nada. Un corte a medias del capítulo 3 de la 2 no deja nada suyo vivo al
   reanudar. El PDF de cada versión sale con acentos y `ñ` y sin tocar el disco.
15. **La observación en Langfuse.** Sin gastar y con un Langfuse fingido: una
   obra lanzada desde una entrevista deja una sesión con la traza de la
   entrevista y la de la versión 1, un span por capítulo, una generación por
   intento con sus tokens, su coste y su prompt versionado, y los totales del
   capítulo y de la novela; rehacerla abre la traza de la versión 2 en la misma
   sesión; pasar la puerta deja un score por validador. Sin claves no se manda
   nada, con un Langfuse que falla en cada llamada la obra termina igual, y
   ningún subagente recibe una variable `LANGFUSE_`.
16. **El juez de la novela y los briefs.** Sin gastar: sin rúbrica, el juicio
   falla diciendo que falta el prompt y no abre ningún subagente; con una
   rúbrica de prueba, sobre una obra fingida terminada, la ventana lleva los
   resúmenes y capítulos enteros por prioridad y dice cuáles no leyó, la orden
   lleva la rúbrica en el sistema, Sonnet y ninguna herramienta, un veredicto
   bueno cuelga un score por criterio y uno roto no cuelga ninguno; sin
   destinatario, la personalización no se puntúa; con producción en marcha o
   una versión sin terminar, no se lanza. Los briefs de prueba validan contra el
   modelo de `POST /obras` y sus comprobaciones esperadas existen. Correrlos es
   la segunda mitad de la tarea.
17. **El listado de obras.** Sin gastar: sin obras, `GET /obras` devuelve una
   lista vacía; con varias, salen todas de la más reciente a la más antigua, y
   cada una lleva la misma ficha que `GET /obras/{id}`. Una obra recién lanzada
   sale `en_produccion`, una detenida `detenida`, una terminada sin publicar
   `terminada` y la misma, al publicarse, `publicada`; y la ficha de cada una
   dice la misma situación que el listado.
18. **La puerta del esquema.** Sin gastar: un `EventoEstado` sin `capitulo` en el
   cuerpo pero con capítulo en su envoltorio no falla; un `transcurre_tiempo`
   sin `objeto` no falla y uno sin `sujeto` sí. `plegar` y `destilar` llevan
   `validar_capitulo`, y ese hook devuelve un evento sin `fecha_resultante`. En
   la obra `obr_7a0f5152`, sin tocar un dato, los fallos de la puerta pasan de 38
   a los 14 de verdad.
19. **El marco temporal del Contable.** Sin gastar: la ventana de `plegar` del
   capítulo 1 lleva la época, ninguna fecha de cierre anterior y el marco de
   cada escena del capítulo en su orden, sin su objetivo ni su elenco; la del
   capítulo 2 lleva como fecha de cierre anterior la más tardía que el Contable
   escribió en el 1.
20. **La lectura de lo entregado.** Sin gastar: un objeto JSON entre vallas con
   texto delante y detrás se lee; uno sin vallas con texto alrededor, también;
   uno cortado falla diciendo dónde se rompió. Una `Crítica` con tilde se guarda
   como `Critica`, y un tipo que no existe sigue fallando.
21. **Un solo lugar, con el viaje.** Con Lean: un presente en dos lugares el
   mismo día pasa si ese día llega a uno de ellos con un `viaja_a`, y falla si
   no consta ningún viaje suyo ese día.

## §11 Fuera del alcance de v1

La interfaz web. Autenticación y varios usuarios. Varias obras produciéndose a
la vez como algo que el sistema ofrezca —el techo de contexto es de la
instalación, no de la obra—: no se reparte el techo entre ellas ni se
planifican. Si llegan a caminar dos, como al relanzar las caídas, D-88 turna
sus tandas para que no pasen del techo, y nada más. La
calibración de los topes de ventana contra trazas reales, que necesita trazas
que todavía no existen. La compactación del único material que sigue entrando
entero, los `Resumen de capítulo`: v1 declara su tope y avisa al alcanzarlo,
pero no compacta; el registro acumulado de estilo ya no lo necesita porque se
consulta por parecido. El corpus curado de fuentes de época, por D-06. Y
cualquier herramienta externa de cálculo, por D-05, salvo el demostrador de la
puerta de publicación (§4.16, D-64).

También queda fuera, del filtro de lo vetado, lo que enumera §4.14: el tema
dicho con otras palabras y lo escrito para esquivar la lista. De la entrevista
queda fuera lo que enumera §4.8; de las versiones, lo que enumera §4.12; de
la puerta de publicación, lo que enumera §4.15; de la cronología en Lean, lo
que enumera §4.16; del validador formal del sistema, lo que enumera §4.17;
del cambio del lector y el PDF, lo que enumera §4.18; de la observación en
Langfuse, lo que enumera §4.20, empezando por los evaluadores, que no entran
nunca en el repositorio; y del juez de la novela y los briefs de prueba, lo
que enumera §4.21.

## §12 Decisiones abiertas

De las once de `architecture.md` §8, cuatro tocaban al backend y las cuatro
quedan cerradas aquí:

- **Dónde vive el almacén y quién lo escribe** → SQLite y solo SQLite (D-02, RD-08).
- **Si los prompts son parte del `backend/`** → sí, junto a la tarea de su rol (D-03).
- **Qué severidad dispara regeneración completa** → `bloqueante`, y solo ella (RF-32).
- **Si se acepta herramienta externa de cálculo** → no en v1 (D-05), y sigue abierta para las siguientes.

De las siete de dominio, una queda cerrada por decisión del dueño del
proyecto:

- **Si la biblia se versiona junto a la novela** → sí: cada versión tiene su propio mundo (D-41).

Las otras seis de §8 no bloquean esta versión. De las cinco
que este SRS abrió, cuatro quedan cerradas:

- **Cómo se ejecuta una tarea y con qué modelo** → subagente de Claude Code con Haiku (D-08).
- **Qué buscador usa el Documentalista y qué hace sin resultados** → el del propio subagente, y no bloquea nunca (D-09, RF-69).
- **Qué modelo calcula las huellas** → `paraphrase-multilingual-MiniLM-L12-v2` en local, con búsqueda híbrida (D-10, RD-14).
- **Cada cuántos capítulos entra `auditar`** → configuración con valor de partida «solo al cierre de la obra», porque una obra de tres capítulos no da para más y auditar antes de tener resúmenes que comparar no mide nada.

Quedan dos abiertas, y ninguna bloquea:

- [ ] Con qué se cuentan los tokens **antes** de enviar. Hoy la cuenta previa es
      una estimación calibrada contra las medidas exactas que el subagente
      devuelve al terminar (D-10 de §2.4). Basta para repartir tandas con el
      20 % de margen, pero no es la cuenta del proveedor.
- [ ] Cuánto mide un fragmento y cuánto se solapa con el siguiente. Troceado
      corto recupera preciso y pierde contexto; largo al revés. Valor de partida
      declarado en el código, pendiente de calibrar contra trazas.

Y una que este documento no cierra porque es del dueño:

- [ ] Si el demostrador de la puerta (§4.16) cuenta como la herramienta externa
      de cálculo que D-05 deja fuera de v1. Hoy se usa solo para decidir si una
      versión terminada se publica, sin darle nada a ningún agente (D-64), y la
      decisión de `architecture.md` §8 sigue abierta.
