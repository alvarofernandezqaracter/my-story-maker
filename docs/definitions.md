# Ontología del dominio: generación de novela histórica — Definiciones

2026-09-21 · [NOMBRE_ANONIMIZADO]

## Propósito, alcance y convenciones

Esta ontología define el vocabulario del dominio sobre el que opera un sistema multiagente de escritura de novela histórica por capítulos. Es operativa, no descriptiva: cada entidad definida aquí debe corresponder a un registro tipado en el estado del sistema, a una porción identificable del contexto que recibe algún agente, y a al menos un predicado de validación. Lo que no cumple las tres condiciones sobra.

**T-Box y A-Box.** La ontología (T-Box) define tipos, atributos y relaciones válidos para cualquier novela histórica. La biblia de una obra concreta (A-Box) es la instanciación: esta condesa, este asedio, esta carta. El harness manipula instancias; el diseño se justifica sobre tipos. Separarlos permite reutilizar el sistema con otra obra sin tocar código.

**Alcance.** Cubre el dominio narrativo y el histórico. Queda fuera la infraestructura (modelos, proveedores, almacenamiento) y la interfaz. El dominio de producción —agentes, tareas, críticas, contexto, gobierno— está en `architecture.md`.

**Convenciones**

- Entidades en PascalCase singular: `Escena`, `Personaje`, `EventoEstado`.
- Relaciones en snake\_case con verbo orientado: `ocurre_en`, `sabe_que`, `paga_setup`.
- Toda entidad lleva `id` estable y opaco, `tipo` y `procedencia` (agente que la creó, revisión en que apareció).
- Los atributos de valor cerrado remiten a un vocabulario controlado; nunca texto libre.
- Cardinalidades anotadas como `1`, `0..1`, `1..*`, `*`.

Regla de corte: si un atributo no lo lee ningún agente ni lo comprueba ningún validador, no se modela.

## Organización del vocabulario

Las entidades del dominio se reparten en dos capas disjuntas, que este documento define en ese orden:

- **Capa 1 — Obra:** unidades textuales (obra, parte, capítulo, escena, beat, párrafo). Responde a cómo está hecho el texto.
- **Capa 2 — Mundo:** referentes (personajes, lugares, eventos, objetos, instituciones, cronología). Responde a de qué habla el texto.

La capa 2 se desdobla además en **mundo documentado** (lo que la evidencia histórica sostiene) y **mundo ficcional** (lo inventado sobre él). Son el mismo tipo de entidad con distinto grado de licencia, no dos ontologías.

Existe una tercera capa, la de producción, que observa a estas dos y está definida en `architecture.md` junto con las reglas de acoplamiento entre capas.

## Capa 1 — La obra

La unidad operativa del sistema es la **escena**, no el capítulo: es el nivel más pequeño en el que se puede declarar un contrato completo y verificable.

**Obra.** Raíz. Atributos: título, época y ámbito geográfico, premisa, tesis temática, elenco principal, políticas globales (POV dominante, tiempo verbal, nivel de arcaísmo, extensión objetivo). Relación: `se_compone_de` 1..\* `Parte`.

**Parte / Acto.** Agrupación estructural con función dramática (planteamiento, complicación, crisis, resolución). Atributos: función, arco global que cubre, capítulos que contiene. Opcional en obras cortas.

**Capítulo.** Unidad de entrega y de generación. Atributos: número, título, POV dominante, ventana temporal cubierta, extensión objetivo, función en el ritmo global, estado de producción. Relaciones: `se_compone_de` 1..\* `Escena`, `sigue_a` 0..1 `Capítulo`.

**Escena.** Bloque continuo de espacio, tiempo y punto de vista. Es donde se enganchan las validaciones. Sus atributos forman el contrato de escena (abajo).

**Beat.** Unidad mínima de cambio dentro de la escena: acción, reacción, decisión o revelación. Sirve para planificar sin escribir y para localizar fallos de ritmo. Atributos: tipo, agente, contenido en una frase.

**Párrafo.** Unidad textual generada. Atributos: texto, escena a la que pertenece, modo (escena dramatizada, sumario, descripción, digresión, diálogo). Portador de los defectos de alcance local.

### El contrato de escena

Toda `Escena` declara, antes de escribirse, estos campos. Si alguno falta, la escena no es generable; si el texto producido no los satisface, la escena se rechaza.

| Campo | Significado | Validación asociada |
| --- | --- | --- |
| `pov` | Personaje foco y tipo de focalización | Nada narrado fuera del acceso de ese personaje |
| `marco` | Lugar + instante/duración en la cronología | Coherencia con desplazamientos previos |
| `elenco_presente` | Personajes en escena | Todos vivos, disponibles y en ese lugar |
| `objetivo` | Qué quiere el foco en esta escena | Debe ser legible en el texto |
| `obstaculo` | Qué lo impide | Sin obstáculo no hay escena, hay sumario |
| `cambio_de_valor` | Estado emocional o situacional al entrar y al salir | Entrada ≠ salida |
| `informacion_revelada` | Qué pasa a saber cada personaje y el lector | Alimenta el estado epistémico |
| `funcion_estructural` | Setup, escalada, giro, respiro, pago, resolución | Contribuye a la curva de tensión |
| `compromisos_abiertos` | Pistas plantadas que exigen pago posterior | Entra en la cola de compromisos |
| `compromisos_pagados` | Pistas previas que esta escena salda | Cierra elementos de la cola |

## Capa 2 — El mundo

**Personaje.** Agente del mundo narrado. Atributos: nombre y variantes de tratamiento, estatus ontológico (histórico, ficticio, compuesto), edad y fechas, extracción social, oficio, rasgos físicos estables, voz (léxico, cadencia, muletillas, temas recurrentes), motivación dominante, herida o carencia, arco declarado. Relaciones: `pertenece_a` `Facción`, `reside_en` `Lugar`, `vinculado_a` `Personaje` (con tipo de vínculo y signo), `sabe_que` `Proposición`.

**Lugar.** Espacio con extensión y propiedades sensoriales. Atributos: nombre histórico y actual, jerarquía (reino, ciudad, edificio, estancia), distancias y tiempos de viaje a otros lugares, rasgos materiales de época. La distancia no es decorativa: es la restricción que valida la cronología.

**Evento.** Suceso datable. Atributos: descripción, intervalo temporal, participantes, lugar, estatus (histórico documentado, histórico reinterpretado, ficticio), visibilidad (público, privado, secreto). Relaciones: `precede_a`, `causa`, `posibilita`, `impide`.

**Objeto.** Cosa con historia propia. Atributos: descripción material, disponibilidad temporal (desde cuándo existe ese objeto en ese lugar), poseedor actual, valor simbólico. Los objetos son los reincidentes en fallos de continuidad porque cambian de manos.

**Facción / Institución.** Cuerpo colectivo: familia, gremio, orden religiosa, ejército, corte. Atributos: naturaleza, intereses, jerarquía interna, relación con otras facciones. Da motivación a personajes secundarios sin necesidad de modelarlos uno a uno.

**Práctica / Costumbre.** Forma de hacer propia de la época: comer, viajar, cortejar, litigar, rezar, morir. Es la fuente principal de textura histórica y de anacronismo social.

**Concepto.** Categoría mental disponible en la época. Modela lo que un personaje *puede pensar*: nociones de intimidad, nación, infancia, tiempo, enfermedad. Es la capa que impide el anacronismo más difícil de detectar, el conceptual.

**Registro lingüístico.** Repertorio permitido y prohibido: léxico disponible, fórmulas de tratamiento, tics a evitar, términos vetados por modernos. Se aplica como filtro sobre el texto generado.

**Fuente.** Documento o referencia que respalda un elemento. Atributos: cita, tipo (primaria, secundaria, divulgativa), fiabilidad, qué afirma exactamente. Sin `Fuente` no hay forma de distinguir un dato de una alucinación plausible.

### Grado de licencia

Todo elemento de esta capa lleva un campo `licencia` con uno de tres valores. Sin él, el validador de anacronismos no puede distinguir un error de una decisión artística.

| Valor | Significado | Tratamiento |
| --- | --- | --- |
| `canon` | Documentado por una `Fuente`; inmutable | Contradecirlo es defecto grave |
| `plausible` | Inventado, compatible con la evidencia | Debe respetar el marco material y conceptual |
| `licencia` | Contradice la evidencia a sabiendas | Exige justificación registrada y, si procede, nota final |

## Relaciones transversales

Las entidades son el inventario; las relaciones son donde vive la coherencia. Seis familias, cada una con su propio validador.

**Mereológicas** (`se_compone_de`, `parte_de`). Estructuran la capa 1. Validan integridad: ninguna escena huérfana, ningún capítulo vacío.

**Temporales** (`precede_a`, `simultaneo_a`, `dura`, `dista_de`). No basta con una fecha: hace falta orden parcial, duración y distancia, porque la mayoría de los fallos de continuidad son aritmética de calendario (un viaje imposible, una gestación de once meses, un personaje que envejece mal).

**Causales** (`causa`, `posibilita`, `impide`). Distintas de las temporales y necesarias para que la trama no sea una lista de sucesos. Permiten preguntar si un giro estaba preparado o llegó de la nada.

**Epistémicas** (`sabe_que`, `cree_que`, `sospecha_que`, `ignora_que`). Modelan quién sabe qué, desde cuándo y con qué certeza, **incluyendo al lector como sujeto epistémico**. Es la relación que casi ningún sistema modela y la que decide si una revelación funciona o se deshincha: un personaje que actúa sobre información que aún no ha recibido es el fallo más frecuente y más invisible de la generación por capítulos.

**De compromiso** (`planta_setup`, `paga_setup`, `promete_a_lector`). Forman una cola con vencimientos. Un setup sin pago es una promesa rota; un pago sin setup es un *deus ex machina*.

**Referenciales** (`menciona`, `documentado_por`, `deriva_de`). Conectan la capa 1 con la 2 y la 2 con las fuentes. Sostienen la trazabilidad histórica y permiten saber qué párrafos hay que revisar cuando una entidad del mundo cambia.

## Vocabularios controlados

Valores cerrados. Cualquier atributo que los use rechaza texto libre; así los predicados de validación son computables. Los vocabularios de proceso (severidad, estado de producción, tipos de `EventoEstado`) están en `architecture.md`.

**POV / focalización:** `primera`, `tercera_limitada`, `tercera_omnisciente`, `epistolar`, `mixta`.

**Modo del párrafo:** `escena`, `sumario`, `descripcion`, `dialogo`, `monologo_interior`, `digresion`.

**Función estructural de escena:** `setup`, `escalada`, `giro`, `revelacion`, `respiro`, `pago`, `resolucion`.

**Tipo de beat:** `accion`, `reaccion`, `decision`, `revelacion`, `transicion`.

**Estatus ontológico:** `historico`, `ficticio`, `compuesto` (personaje ficticio armado con rasgos de varios reales).

**Grado de licencia:** `canon`, `plausible`, `licencia`.

**Tipo de fuente:** `primaria`, `secundaria`, `divulgativa`, `sin_respaldo`.

**Tipo de anacronismo:** `material` (objetos y técnicas), `lexico` (palabras no disponibles), `conceptual` (categorías mentales imposibles), `social` (comportamientos y cortesías), `institucional` (cargos, leyes, procedimientos).

**Estado de compromiso:** `abierto`, `reforzado`, `pagado`, `abandonado`.

## Dimensiones de calidad

Las dimensiones tienen alcances distintos y solo son observables en el suyo. Meterlo todo en un juez global produce el "8/10, buen ritmo" que no significa nada. El mecanismo que aplica estas dimensiones —estrategia de validación y bucle de control— está en `architecture.md`.

### Alcance local (párrafo y página)

Dimensiones formulables como regla estrecha sobre un fragmento corto.

| Dimensión | Predicado o método |
| --- | --- |
| Anacronismo material | Objeto mencionado con disponibilidad temporal compatible con la fecha de la escena |
| Anacronismo léxico | Ninguna palabra de la lista vetada; términos fuera del registro señalados |
| Anacronismo conceptual | Ningún `Concepto` invocado fuera de su disponibilidad de época |
| Anacronismo social e institucional | Prácticas y cargos coherentes con el marco |
| Fatiga léxica | Frecuencia de lemas y de imágenes por encima de umbral respecto al corpus previo |
| Tics de modelo | Lista de patrones recurrentes de superficie |
| Coherencia de voz | Distancia estilística entre réplicas del mismo personaje en capítulos distintos |

### Alcance de escena y capítulo

| Dimensión | Predicado |
| --- | --- |
| Cumplimiento del contrato | Cada campo declarado tiene realización en el texto |
| Cambio de valor | Estado de entrada ≠ estado de salida del foco |
| Integridad de POV | Nada narrado fuera del acceso perceptivo y cognitivo del foco |
| Violación epistémica | Ningún personaje actúa sobre proposiciones que no `sabe_que` en ese instante |
| Continuidad de estado | Presencias, posesiones y ubicaciones compatibles con el estado derivado |
| Coherencia temporal | Desplazamientos posibles dadas distancias y duraciones |
| Ritmo | Proporción escena/sumario y diálogo/narración dentro de la banda objetivo |

### Alcance global (obra)

| Dimensión | Predicado |
| --- | --- |
| Progresión de arcos | Cada personaje con arco declarado muestra cambios medibles distribuidos |
| Economía narrativa | Ningún compromiso `abierto` al final; ningún pago sin setup previo |
| Curva de tensión | Distribución de escenas de escalada y giro sin mesetas largas |
| Distribución de revelaciones | Espaciado de los cambios epistémicos del lector |
| Fidelidad histórica | Ratio `canon` / `plausible` / `licencia`; toda `licencia` con justificación registrada |
| Cobertura documental | Proporción de afirmaciones históricas con `Fuente` asociada |
