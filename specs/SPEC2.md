---
name: SPEC2
titulo: Frontend v1 — Especificación de requisitos de software
version: 1.1.0
estado: aprobada
fecha: 2026-09-24
ambito: frontend/
base:
  - AGENTS.md
  - specs/SPEC1.md
  - backend/openapi.yaml
  - docs/definitions.md
  - docs/architecture.md
  - docs/validators.md
---

# SPEC2 · Frontend v1 — Especificación de requisitos de software

## §1 Introducción

### 1.1 Propósito

Fijar qué tiene que hacer la primera versión del `frontend/` para que una
persona encargue una novela y la lea sin tocar nunca el servidor por su cuenta.
Es un documento de requisitos, no de implementación: recoge lo que, si se decide
mal, obliga a rehacer trabajo.

SPEC1 dejó la interfaz web explícitamente fuera del alcance de v1 del backend
(SPEC1 §11). Este documento la mete dentro del suyo. No enmienda SPEC1: el
backend queda como está y la interfaz se construye contra el contrato que ya
publica.

### 1.2 Alcance del sistema especificado

Dentro: la conversación que completa el encargo hasta lanzar la obra, la
pantalla que enseña el avance mientras la obra se produce, la lista de las
tareas ya hechas, la lectura del manuscrito aceptado, un menú que salta entre
las tres pantallas de una obra, y el cliente HTTP generado desde el contrato.

Fuera: las pantallas de críticas, estado del mundo y búsqueda de pasajes; todo
lo enumerado en §11.

La medida de «terminado» de v1 es una sola: **una persona que no ha visto nunca
el sistema llega de la pantalla en blanco a la novela leída sin que nadie le
enseñe una orden de consola**.

### 1.3 Documentos base y jerarquía

| Documento | Qué aporta a este SRS | Manda sobre |
| --- | --- | --- |
| `AGENTS.md` | Frontera única, pila fijada, ciclo de edición | Frontera y pila |
| `specs/SPEC1.md` | Qué hace el backend, qué sirve y con qué forma | Comportamiento del servidor |
| `backend/openapi.yaml` | El contrato exacto del borde | Nombres de campo y formas |
| `docs/definitions.md` | Vocabularios cerrados del dominio | Palabras que aparecen en pantalla |

Si este documento contradice a alguno de los cuatro, gana el documento base y
esto es un error de este SRS. Donde SPEC1 y `openapi.yaml` discrepen, manda el
contrato: es el que se genera desde el código.

### 1.4 Convenciones

- Mismas familias de identificador que SPEC1: `RF-` funcional, `RD-` de datos,
  `RI-` de interfaz, `RNF-` no funcional, `D-` decisión, `OBJ-` objetivo. Son
  **locales a este documento** y se citan siempre con él delante: `SPEC2 RF-01`.
- La columna «Verificación» usa el vocabulario `metodo_de_verificacion` de
  `validators.md` §2.

## §2 Descripción general

### 2.1 Qué hace la interfaz y qué no

**Hace dos cosas**: recoge el encargo y enseña lo que el sistema ha producido.

**No hace una tercera**: no decide nada del dominio. No pliega el log, no juzga
si una crítica es bloqueante, no cuenta tokens, no completa el brief por su
cuenta ni detecta qué campo falta. Todo eso ya viene resuelto en la respuesta.
Una regla de dominio reimplementada aquí es una segunda verdad que divergirá de
la del backend.

### 2.2 Actores

| Actor | Qué aporta | Qué recibe |
| --- | --- | --- |
| Editor (persona) | Lo que sabe del encargo y los textos que tenga escritos | La propuesta de brief, el avance y la novela |
| `backend/` | Respuestas HTTP y el flujo de progreso | Las llamadas de la interfaz, y nada más |

### 2.3 Restricciones heredadas

De `AGENTS.md`, no negociables: la interfaz **nunca lee ficheros ni abre la base
de datos**; todo lo pide por HTTP. El contrato de la frontera es OpenAPI y se
genera, no se redacta. Pila fijada: Vite + React, aplicación de una sola página.
Español en la interfaz, y los nombres del dominio tal cual.

De SPEC1, dos que gobiernan el diseño de la pantalla del encargo: la entrevista
es **sin estado** —cada pasada recibe todo lo que la persona quiera conservar y
nada de las anteriores (SPEC1 D-20)— y la obra **se lanza sola** en cuanto el
brief está completo, sin confirmación (SPEC1 D-22).

### 2.4 Supuestos y dependencias

- El backend corre en la misma máquina y no hay autenticación: v1 del servidor
  no la tiene y esta no la inventa.
- Una obra tarda horas y cientos de tareas. Todo lo que espera lo dice en
  pantalla; nada se queda en blanco.
- El servidor no guarda el borrador del encargo entre pasadas. Si el navegador
  pierde lo escrito, la persona pierde su trabajo: de ahí RF-06 y D-03.

## §3 Objetivos medibles

Ningún objetivo tiene línea base: no hay interfaz, así que la base se declara
**pendiente de medir** en lugar de inventarla. La primera sesión completa con
una persona real es la que la fija.

Van en este orden porque el primero es el que hace que los demás signifiquen
algo: una interfaz de la que hay que salirse para encargar no es la interfaz.

| ID | Objetivo | Métrica | Cómo se mide | Línea base | Meta |
| --- | --- | --- | --- | --- | --- |
| OBJ-01 | Cero salidas de la web | Acciones que la persona tiene que hacer fuera de la interfaz para llegar de la idea a la obra leída | Recuento en un recorrido observado de principio a fin | Pendiente | Exactamente 0 |
| OBJ-02 | El encargo converge | Pasadas de entrevista hasta `estado = "lanzada"` | Campo `numero` de la pasada que lanza | Pendiente | Mediana ≤ 3; ninguna sesión por encima de 6 |
| OBJ-03 | Nada se pierde al recargar | Proporción de recargas de la pantalla del encargo que conservan lo escrito y lo pegado | Prueba automática: escribir, recargar, comparar | Pendiente | 100 % |
| OBJ-04 | Nada en blanco sin explicación | Estados de espera o de fallo que la pantalla muestra sin decir qué pasa | Recorrido por cada pantalla con el servidor lento y con el servidor caído | Pendiente | Exactamente 0 |
| OBJ-05 | El contrato no se desfasa en silencio | Cambios del borde HTTP que llegan a la rama principal sin que el cliente se regenere | La comprobación de RI-02 sobre el histórico | Pendiente | Exactamente 0 |
| OBJ-06 | El avance se nota | Segundos entre que el servidor emite un suceso y la pantalla lo muestra | Sello del evento contra el repintado, en el recorrido de aceptación | Pendiente | ≤ 2 s |

**Qué no es objetivo, y por qué.** El peso de lo que se descarga: es una
aplicación local de una sola persona, optimizarlo no mejora nada de lo que
importa y empuja a partir el código sin motivo. El número de clics para lanzar:
se cumple trivialmente quitando lo que evita que el encargo salga mal, y arruina
OBJ-02 sin que la cifra de clics se entere. Y la nota de una prueba de
usabilidad puntuada a ojo, que es ruido y no medida.

## §4 Requisitos funcionales

### 4.1 El encargo

```mermaid
flowchart LR
  B([Pantalla en blanco]) --> E[La persona escribe o pega]
  E --> P[Pasada contra el servidor]
  P --> V{Estado de la pasada}
  V -- pendiente --> R[Se muestra lo entendido,<br/>lo que falta y lo que choca]
  R --> E
  V -- lanzada --> A([Se salta al avance<br/>con el id_obra])
```

| ID | Requisito | Verificación |
| --- | --- | --- |
| RF-01 | El encargo se presenta como una conversación: la persona escribe en lenguaje corriente o pega un texto entero, y cada envío es una pasada contra el servidor. La primera abre la entrevista; las siguientes cuelgan de su `id_entrevista` | `demostracion` |
| RF-02 | Cada pasada manda **todo** lo acumulado en el navegador —el borrador entero, todos los textos pegados y las contradicciones asumidas—, porque el servidor no recuerda nada de las anteriores | `prueba` |
| RF-03 | Tras cada pasada se muestran, sin interpretarlos, los tres resultados que devuelve: lo que ha entendido del encargo, los campos que siguen faltando con su ruta, y las contradicciones con su evidencia. La interfaz **no decide** cuáles faltan ni cuáles chocan: los pinta | `inspeccion` |
| RF-04 | Una contradicción se puede dar por asumida con un gesto. Asumirla añade su tipo a las pasadas siguientes; la contradicción se sigue mostrando, marcada | `prueba` |
| RF-05 | Cuando una pasada vuelve con `estado = "lanzada"`, la interfaz pasa sola al avance con el `id_obra` que trae, sin pedir confirmación. La entrevista queda cerrada y no se puede seguir escribiendo en ella | `prueba` |
| RF-06 | Lo que la persona lleva escrito y pegado **sobrevive a recargar la página y a cerrar el navegador**, hasta que la obra se lanza. Al lanzarse se descarta | `prueba` |
| RF-07 | Un texto pegado se muestra siempre como lo que es —material de la persona—, identificable y separado de lo que dice el sistema. Nunca se mezcla con la conversación como si lo hubiera dicho alguien | `inspeccion` |
| RF-08 | Si el servidor rechaza la pasada por tamaño, la interfaz dice cuánto sobra y no recorta nada por su cuenta | `prueba` |
| RF-09 | La ficha distingue lo obligatorio de lo opcional según lo que el servidor exige (SPEC1 RF-01, D-50): la tesis, los personajes y los arcos se pueden dejar sin tocar, y dejarlos así no los manda. La interfaz no los pide ni los marca como pendientes | `prueba` |

### 4.2 El avance

| ID | Requisito | Verificación |
| --- | --- | --- |
| RF-20 | Mientras la obra corre, la pantalla muestra lo que el servidor va empujando por el flujo abierto: capítulo en curso, tareas abiertas y tokens de entrada concurrentes frente al techo | `demostracion` |
| RF-21 | Al entrar, la pantalla se pinta con la foto de una sola consulta y solo después se engancha al flujo. Nunca se ve vacía esperando al primer suceso | `prueba` |
| RF-22 | Si el flujo se corta, la interfaz se reengancha sola y lo dice mientras tanto. Una obra que sigue corriendo no puede parecer parada porque se haya caído la conexión | `prueba` |
| RF-23 | La obra se puede detener y reanudar desde aquí. Son las dos únicas órdenes de la interfaz además de lanzar, y son control, no mantenimiento | `prueba` |
| RF-24 | Al cerrarse la obra, la pantalla lo dice y ofrece la lectura. No hace falta estar mirando para enterarse: al volver a entrar, el estado es el mismo | `demostracion` |
| RF-25 | La interfaz no calcula nada del avance: los tokens, el techo y el capítulo en curso se muestran tal como vienen | `inspeccion` |
| RF-26 | Las tareas ya hechas de la obra se ven en una pantalla propia, agrupadas por capítulo y en el orden en que las sirve el servidor: qué rol, qué tarea, capítulo y escena, cuánto tardó y si pasó los hooks de su paso. Solo lo esencial: tokens, coste e intentos no se enseñan (D-09). Se puede volver a pedir la lista sin salir de la pantalla | `prueba` |
| RF-27 | «Pasó los hooks» se lee del veredicto `final` que la `Traza` ya trae (SPEC1 RI-15): pasa si todos los hooks dicen que pasa, no pasa si alguno no, y una tarea sin hooks no dice nada. La interfaz no revisa el texto por su cuenta | `inspeccion` |

### 4.2 bis Moverse por una obra

| ID | Requisito | Verificación |
| --- | --- | --- |
| RF-30 | Las pantallas de una obra —Avance, Tareas y Lectura— llevan arriba el mismo menú, que salta de una a otra con un clic y marca en cuál se está. Cada pantalla conserva su propia dirección, así que también se pueden abrir en pestañas del navegador | `prueba` |

### 4.3 La lectura

| ID | Requisito | Verificación |
| --- | --- | --- |
| RF-40 | El manuscrito se lee en orden, agrupado por capítulo y escena, con solo el texto aceptado. Se puede leer una obra a medio producir: lo que hay es lo que se ve | `demostracion` |
| RF-41 | Un capítulo que el servidor marca se muestra marcado, con el aviso de que tiene defectos sin resolver. v1 **no enseña cuáles**: el contrato del manuscrito solo trae la marca, y la pantalla de críticas está fuera de alcance (§11) | `inspeccion` |
| RF-42 | La ficha de la obra —título, capítulos cerrados, capítulos marcados y críticas abiertas— acompaña a la lectura como recuento, sin detalle | `prueba` |
| RF-43 | La lectura es cómoda para leer seguido: texto a ancho de lectura y navegación por capítulos. Es el entregable de todo el sistema, no un volcado de depuración | `inspeccion` |

### 4.4 Esperas y fallos

| ID | Requisito | Verificación |
| --- | --- | --- |
| RF-60 | Toda petición en curso tiene estado visible, y todo fallo dice qué ha pasado y qué se puede hacer. Ninguna pantalla se queda en blanco ni girando sin fin | `inspeccion` |
| RF-61 | Un rechazo del servidor se muestra con el mensaje que manda el servidor, en español, sin traducirlo ni adornarlo. Los campos que faltan se señalan por su ruta, como los nombra él | `prueba` |
| RF-62 | Un fallo de red se distingue de un rechazo del servidor, y el primero se puede reintentar sin volver a escribir nada | `prueba` |

## §5 Requisitos de datos

| ID | Requisito | Verificación |
| --- | --- | --- |
| RD-01 | **La interfaz no tiene almacén de dominio.** Lo que muestra son respuestas del servidor, consultadas y cacheadas contra él. No hay copia local de capítulos, críticas ni estado | `inspeccion` |
| RD-02 | Lo único que la interfaz guarda por su cuenta es el borrador del encargo en curso —campos, textos pegados, contradicciones asumidas e `id_entrevista`—, en el navegador y hasta que la obra se lanza (RF-06) | `inspeccion` |
| RD-03 | Todo valor de vocabulario cerrado —severidad, estado, tipo de contradicción— se muestra tal cual o traducido a una etiqueta legible, nunca ampliado ni agrupado con otro «porque se ve mejor» | `analisis` |
| RD-04 | Las palabras del dominio que aparecen en pantalla están definidas: las de la obra y el mundo en `definitions.md`, y las del proceso —`Entrevista`, `Crítica`, `Traza`— en `architecture.md`, que es donde `definitions.md` las remite. Una palabra en pantalla que no está en ninguno de los dos, o sobra o falta una definición | `analisis` |

## §6 Requisitos de interfaz

| ID | Operación | Requisito | Verificación |
| --- | --- | --- | --- |
| RI-01 | Todas | Toda llamada pasa por un único cliente en `compartido/`. Ninguna pantalla habla con el servidor por su cuenta: es lo que hace que la frontera se revise leyendo una carpeta | `analisis` |
| RI-02 | Todas | Las funciones y los tipos de ese cliente se **generan desde `backend/openapi.yaml`** y no se editan a mano. Una comprobación regenera y falla si lo generado no coincide con lo commiteado, igual que RNF-09 hace en el backend. No hay orden de mantenimiento que recordar | `prueba` |
| RI-03 | `POST /entrevistas` · `/entrevistas/{id_entrevista}/pasadas` | §4.1 | `demostracion` |
| RI-04 | `GET /obras/{id_obra}/progreso` | Flujo de sucesos, con reenganche (RF-22) | `prueba` |
| RI-05 | `GET /obras/{id_obra}/progreso/ahora` | La foto con la que se pinta antes de engancharse (RF-21) | `prueba` |
| RI-06 | `GET /obras/{id_obra}` · `/obras/{id_obra}/manuscrito` | §4.3 | `demostracion` |
| RI-07 | `POST /obras/{id_obra}/detener` · `/obras/{id_obra}/reanudar` | RF-23 | `prueba` |
| RI-08 | `GET /obras/{id_obra}/trazas` | RF-26 y RF-27, sin filtros | `prueba` |

Los demás endpoints del contrato existen y v1 no los llama. Que estén servidos
no obliga a pintarlos.

## §7 Requisitos no funcionales

| ID | Requisito | Verificación |
| --- | --- | --- |
| RNF-01 | La interfaz no lee ficheros ni abre la base de datos. Si falta un dato se añade un endpoint; no existe el atajo | `analisis` |
| RNF-02 | Una carpeta por funcionalidad, sin importaciones entre ellas. Lo común sube a `compartido/`; entre dos pantallas se duplica antes que acoplarse | `analisis` |
| RNF-03 | No hay capa de dominio en el cliente: ni `services/`, ni `models/`, ni `domain/` | `inspeccion` |
| RNF-04 | Cómo llega el avance está encapsulado en el cliente de API. Cambiar de flujo empujado a sondeo no toca ninguna pantalla | `inspeccion` |
| RNF-05 | Español en toda la interfaz y en los mensajes de error | `inspeccion` |
| RNF-06 | La interfaz arranca en desarrollo y se construye para usarla, cada cosa con una sola orden. Ponerla en pie no es un procedimiento | `demostracion` |

## §8 Decisiones de diseño de esta versión

| ID | Decisión | Por qué |
| --- | --- | --- |
| D-01 | **v1 es encargar, ver avanzar, ver lo hecho y leer.** Críticas, estado del mundo y búsqueda de pasajes quedan fuera | Encargar, ver avanzar y leer son las tres cosas sin las cuales la web no sirve para nada. Lo hecho entra porque quien mira una obra de horas quiere saber qué ha pasado además de qué pasa ahora; las otras tres son instrumentos de depuración que hoy se miran mejor por el contrato |
| D-02 | **El encargo se presenta como una conversación**, aunque por dentro sean pasadas sin estado | Quien encarga una novela no sabe de antemano qué se le va a pedir, que es justo el problema que SPEC1 §4.8 identificó. Un formulario obliga a saberlo antes de empezar. El precio es que la web carga con la memoria que el servidor no tiene, y se paga en D-03 |
| D-03 | **El borrador del encargo vive en el navegador**, y se manda entero en cada pasada | Es la consecuencia directa de que la entrevista sea sin estado (SPEC1 D-20). Guardarlo en el servidor sería pedirle que recuerde, que es lo que hace el techo de contexto verificable antes de gastar. Guardarlo solo en memoria convierte una recarga accidental en la pérdida de la carta que la persona pegó |
| D-04 | **El avance llega por el flujo que el servidor empuja**, con una foto inicial y reenganche automático | El servidor ya lo sirve y es lo que hace que una obra de horas no parezca colgada. El sondeo es más simple pero repite trabajo y se nota lento. La foto inicial y el reenganche son el precio, y son dos requisitos, no una arquitectura |
| D-05 | **El cliente se genera desde el contrato y hay una comprobación que falla si se desfasa** | Es el mismo trato que el backend ya se da a sí mismo (SPEC1 RNF-09 y D-11). Sin la comprobación, regenerar es un paso manual que se olvida, y un paso manual periódico es un defecto de diseño. Con ella, mover la frontera pasa por el diff en los dos lados |
| D-06 | **TypeScript**, no JavaScript | No es una preferencia de estilo: es lo que hace que D-05 sirva de algo. Con tipos generados, un campo que el servidor renombra rompe al construir; sin ellos, rompe en la pantalla de alguien |
| D-08 | **Un menú dentro de la obra, no pantallas a la vez** | Saltar con un clic basta para seguir una obra, y cada pantalla sigue teniendo su dirección para quien quiera varias pestañas. Poner dos pantallas juntas en la misma vista obliga a rehacer las tres para que quepan. El menú no llega al encargo ni a otras obras: no hay listado de obras (§12) |
| D-09 | **La lista de tareas enseña lo esencial** | Se lee de un vistazo quién hizo qué y si salió bien. Los tokens y el coste siguen en el contrato para quien mida el gasto, y añadirlos más adelante no cambia nada de lo de arriba |
| D-07 | **Un capítulo marcado se avisa sin detalle** | Enseñar la marca sin poder abrirla es un callejón, pero ocultarla sería peor: la persona leería como definitivo un capítulo que el sistema sabe defectuoso. El detalle llega cuando llegue la pantalla de críticas |

## §9 Trazabilidad

| Bloque | De dónde sale |
| --- | --- |
| §4.1 El encargo | SPEC1 §4.8 (RF-70 a RF-79; D-20 a D-24) |
| §4.2 El avance | SPEC1 RF-53, RF-04, RI-08, RI-09; las tareas hechas, SPEC1 RI-06 y RI-15 |
| §4.2 bis Moverse por una obra | D-08 |
| §4.3 La lectura | SPEC1 RF-50, RI-02, RI-03 |
| §5 Datos | `AGENTS.md` (frontera única); SPEC1 RD-08 |
| §6 Interfaz | SPEC1 D-11, RNF-09, RI-10 |
| §7 No funcionales | `AGENTS.md` (frontera y pila); skill `frontend-react` §2 y §3 |

## §10 Verificación y criterios de aceptación

La verificación del código es la de `validators.md` §6 y no se duplica aquí. Lo
que fija este SRS es cuándo v1 está terminada:

1. Un borrador al que le faltan la edad y el tono, más una carta pegada que los
   contiene, se completa y lanza la obra **sin salir de la web** (OBJ-01), y la
   pantalla salta sola al avance.
2. Recargar la página a media conversación conserva todo lo escrito y lo pegado
   (OBJ-03).
3. Un brief con una contradicción queda sin lanzar hasta que se asume desde la
   pantalla, y entonces lanza.
4. Con el flujo cortado a mitad, la pantalla del avance lo dice, se reengancha
   sola y no pierde el estado (RF-22).
5. Con el servidor caído del todo, ninguna de las cuatro pantallas queda en
   blanco ni girando: las cuatro dicen qué pasa (OBJ-04).
6. El manuscrito de una obra a medio producir se lee, y un capítulo marcado sale
   marcado.
7. Se cambia un campo del borde HTTP en el backend, se regenera el contrato y la
   comprobación del cliente falla (OBJ-05).
8. Un encargo con título, época, premisa y número de capítulos, sin tesis, sin
   personajes y sin arcos, se lanza sin que nadie los pida.
9. Desde cualquiera de las tres pantallas de una obra se llega a las otras dos
   con un clic, y la de tareas enseña cada tarea hecha con su veredicto.

## §11 Fuera del alcance de v1

Las pantallas de críticas, estado plegado y cronología, y la búsqueda de
pasajes por parecido: el servidor las sirve y v1 no las pinta. Autenticación y
varios usuarios, porque el backend tampoco los tiene. Ver varias obras a la vez
o un listado de obras producidas: v1 trabaja sobre la obra que se acaba de
lanzar o sobre un `id_obra` que se conoce. Edición de nada: la interfaz no
modifica ningún artefacto. Instalación fuera de la máquina de desarrollo. Y
cualquier vista del detalle de una crítica, por D-07.

## §12 Decisiones abiertas

Ninguna bloquea la fase 2.

- [ ] Con qué biblioteca se consulta y se cachea el estado del servidor.
      TanStack Query es el candidato obvio, pero la primera pantalla no lo
      necesita para escribirse y decidirlo antes de tener tres pantallas es
      decidirlo a ciegas.
- [ ] Cómo se vuelve a una obra pasada sin recordar su `id_obra`. Hoy no hay
      listado de obras en el contrato; añadirlo es tocar el backend, así que
      queda para cuando haya más de una obra que mirar.
- [ ] Si el manuscrito terminado se puede descargar, y en qué formato. Es lo
      primero que se va a pedir después de leerlo, y no cambia nada de lo de
      arriba.

## §13 Docs que se ponen al día en la fase 3

`architecture.md` §7: el árbol de `features/` gana `tareas` y el párrafo del
frontend dice que las pantallas de una obra comparten menú. La skill
`.claude/skills/frontend-react/`: su §2 nombra la carpeta `tareas`.
`validators.md`: el método de RF-09, RF-26, RF-27, RF-30 y RI-08 en la matriz de
§8. `AGENTS.md`: la fila de `frontend/` nombra la pantalla de tareas.
