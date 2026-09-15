---
doc: spec-sistema-novelas-historicas
version: 0.1.0
estado: borrador        # borrador | en revisión | aprobado
actualizado: 2026-09-15
basado_en: docs/diagrama/sistema-novelas-historicas-v2.drawio
---

# Especificación del sistema multiagente de novelas históricas

> Estado del documento: borrador en construcción. Cada sección lleva su propia marca de estado bajo el título hasta que se cierre.

## Tabla de contenidos

- [§1 Visión y alcance](#1-visión-y-alcance)
- [§2 Glosario](#2-glosario)
- [§3 Modelo de datos del canon](#3-modelo-de-datos-del-canon)
- [§4 Arquitectura del harness](#4-arquitectura-del-harness)
- [§5 Catálogo de agentes](#5-catálogo-de-agentes)
- [§6 Generador de contexto](#6-generador-de-contexto)
- [§7 Loop de capítulo y gate de calidad](#7-loop-de-capítulo-y-gate-de-calidad)
- [§8 Editor global](#8-editor-global)
- [§9 Contratos de I/O y validación](#9-contratos-de-io-y-validación)
- [§10 Persistencia y versionado del canon](#10-persistencia-y-versionado-del-canon)
- [§11 Errores, reintentos y reanudación](#11-errores-reintentos-y-reanudación)
- [§12 Observabilidad y costes](#12-observabilidad-y-costes)
- [§13 Configuración](#13-configuración)
- [§14 Estructura del repo](#14-estructura-del-repo)
- [§15 Plan de evaluación y tests](#15-plan-de-evaluación-y-tests)
- [§16 Roadmap por fases](#16-roadmap-por-fases)
- [§17 Riesgos y decisiones abiertas](#17-riesgos-y-decisiones-abiertas)
- [§18 Decisiones de arquitectura (ADRs)](#18-decisiones-de-arquitectura-adrs)
  - [§18.1 ADR-0001 — Formato del canon](#181-adr-0001--formato-del-canon)
  - [§18.2 ADR-0002 — Framework de orquestación](#182-adr-0002--framework-de-orquestación)
  - [§18.3 ADR-0003 — Revisores en paralelo vs. secuencial](#183-adr-0003--revisores-en-paralelo-vs-secuencial)
  - [§18.4 ADR-0004 — Criterio del gate](#184-adr-0004--criterio-del-gate)
  - [§18.5 ADR-0005 — Política de selección de contexto](#185-adr-0005--política-de-selección-de-contexto)
- [§19 Trazabilidad diagrama → spec](#19-trazabilidad-diagrama--spec)
- [§20 Historial de cambios del spec](#20-historial-de-cambios-del-spec)

---

## §1 Visión y alcance

> Estado: completa

### §1.1 Problema que se resuelve

Escribir una novela histórica larga con un LLM en una sola pasada falla por tres motivos que se refuerzan entre sí:

| Problema | Síntoma en el texto | Causa raíz |
|---|---|---|
| Pérdida de continuidad | Un personaje muerto en el capítulo 4 habla en el 9; una carta que se quemó reaparece. | El modelo no tiene memoria fiable del libro; el contexto no cabe o se degrada. |
| Anacronismos | Patatas en la Castilla de 1450, relojes de bolsillo en Roma. | El modelo mezcla épocas y no distingue lo que sabe de lo que rellena. |
| Deriva narrativa | Arcos que no cierran, promesas al lector sin pago, ritmo plano. | Nadie sostiene la estructura global mientras se genera lo local. |

El sistema descrito aquí ataca los tres problemas separando responsabilidades: una fase de preparación fija los hechos y la estructura antes de escribir; un **canon** persistente actúa como única fuente de verdad; cada capítulo pasa por tres revisores independientes y un gate determinista antes de entrar en el canon; y un editor global comprueba la estructura al final. El diagrama `docs/diagrama/sistema-novelas-historicas-v2.drawio` es la fuente de verdad del flujo; este documento lo hace implementable.

### §1.2 Qué especifica este documento

Este spec cubre dos cosas distintas que conviven en el mismo proceso:

1. **El harness**: el código determinista que orquesta el flujo, genera el contexto, aplica el gate, persiste el canon, gestiona errores, reanuda ejecuciones y registra costes. Todo lo que puede decidirse con una regla se decide en el harness (§4, §6, §7, §9, §10, §11, §12, §13).
2. **La solución agéntica**: los siete agentes LLM (investigador, arquitecto, escritor, tres revisores, editor global), con sus prompts, contratos de salida, modelos sugeridos y modos de fallo (§5, §8).

La regla de separación es estricta y se repite en todo el documento: **lo determinista va en código, lo generativo va en agentes**. Un agente nunca decide si un capítulo se aprueba; un trozo de código nunca redacta prosa.

### §1.3 Usuario y entorno de ejecución

| Aspecto | Valor |
|---|---|
| Usuario | Una sola persona, autor del proyecto. No hay multiusuario ni permisos. |
| Entorno | Máquina local (Windows 11 en el desarrollo actual; el diseño no depende del SO). |
| Interfaz | Línea de comandos. Una interfaz web o de escritorio queda fuera de esta versión (§1.5). |
| Lenguaje de implementación | Python 3.12 o superior. Motivo: ecosistema LLM maduro, `asyncio` para el paralelismo de revisores, y es la elección del autor. |
| Proveedores LLM | Abstracción multiproveedor desde la fase 1 (§4.6, §13). El harness no depende de ningún proveedor concreto; cada agente puede apuntar a un modelo distinto. |
| Conectividad | Se asume acceso a internet para las APIs de los proveedores. La búsqueda web del investigador es una herramienta opcional (§5.1). |
| Intervención humana | Ninguna dentro del flujo normal. El proceso solo se detiene y escala al usuario cuando un capítulo agota los reintentos o ante un fallo irrecuperable (§7.7, §11). El usuario puede parar el proceso, editar el canon a mano y reanudar (§10.6, §11.5). |

### §1.4 Criterios de éxito

Éxito funcional: dado un brief válido, el sistema produce sin intervención humana un libro completo con todos los capítulos aprobados por el gate, el canon actualizado y el informe del editor global, o bien se detiene con una escalada clara y reanudable.

Métricas de éxito medibles (los valores objetivo son iniciales y se recalibran con el set de evaluación de §15.6):

| Métrica | Definición | Objetivo inicial | Dónde se mide |
|---|---|---|---|
| Tasa de aprobación a la primera | Capítulos aprobados en el intento 1 / capítulos totales | ≥ 60 % | §12.4 |
| Reintentos medios por capítulo | Suma de intentos adicionales / capítulos | ≤ 0,8 | §12.4 |
| Capítulos escalados | Capítulos que agotan `max_reintentos` | ≤ 1 por libro de 20 capítulos | §12.4 |
| Contradicciones detectables por código | Fallos de las comprobaciones deterministas de §7.3 en capítulos aprobados | 0 | §15.3 |
| Coste por capítulo | Coste total de un run de capítulo, incluidos reintentos | Dentro del límite de §13 (por defecto 3 USD) | §12.4 |
| Reanudación | Tras matar el proceso en cualquier punto, relanzar continúa sin repetir trabajo aprobado ni duplicar gasto | 100 % de los casos de §15.4 | §11.5 |

Lo que **no** es criterio de éxito de esta versión: la calidad literaria absoluta del texto. Se mide indirectamente a través de los revisores y del editor global, pero no hay juez humano en el bucle.

### §1.5 Fuera de alcance

| Fuera | Motivo |
|---|---|
| Interfaz web o gráfica | El usuario trabaja en local por CLI. Se retoma en una versión posterior si hace falta. |
| Multiusuario, permisos, autenticación | Un solo usuario en su máquina. |
| Generación de imágenes, portadas, maquetación editorial | No aparece en el diagrama. |
| Traducción del libro terminado | El idioma se fija en el brief y todo se genera en él. |
| Edición humana interactiva capítulo a capítulo | Decidido por el usuario en la Fase 0: sin aprobación humana en el flujo. |
| Reescritura automática tras el editor global | El editor global devuelve una lista de retoques; ejecutarlos automáticamente queda como opción definida en §8 pero no implementada en la fase 1 (§16). |
| Fine-tuning o entrenamiento de modelos | Solo se usan modelos vía API. |
| Publicación o exportación a EPUB/PDF | Se entrega Markdown; la conversión es trivial con herramientas externas. |

### §1.6 Supuestos explícitos

Cada supuesto está marcado y recogido también en §17. Si alguno resulta falso, hay que revisar las secciones indicadas.

| Id | Supuesto | Secciones afectadas si falla |
|---|---|---|
| S-01 | Un capítulo tiene entre 1.500 y 6.000 palabras, con 3.000 como valor por defecto. El usuario no ha fijado tamaño objetivo; estos valores son configurables (§13). | §5.3, §6 |
| S-02 | Un libro tiene entre 8 y 40 capítulos. Por encima de 40 el presupuesto de contexto de §6 necesita recalibrarse. | §6, §12 |
| S-03 | El canon completo de un libro cabe en pocos megabytes de texto. Esto justifica ficheros planos y snapshots por copia completa (§3.2, §10). | §3, §10 |
| S-04 | Los modelos usados admiten salida estructurada en JSON y ventanas de contexto de al menos 128k tokens para el escritor. | §5, §6, §9 |
| S-05 | El coste de tokens de los proveedores es conocido y se puede tabular en la configuración (§13) para calcular costes sin llamar a APIs de facturación. | §12 |
| S-06 | Un capítulo se genera de una pieza en una sola llamada al escritor, dividido internamente en escenas. No se generan escenas en llamadas separadas. | §5.3, §7 |
| S-07 | El usuario acepta que los datos marcados como inventados aparezcan en la novela sin marca en la prosa, siempre que queden registrados en los metadatos del capítulo. Decidido en Fase 0 con valores por defecto. | §3.6, §5.3, §5.5 |
| S-08 | La búsqueda web del investigador es opcional y está desactivada por defecto en la fase 1. | §5.1, §16 |

### §1.7 Principios de diseño

Estos principios se citan por número en el resto del documento.

| Id | Principio | Consecuencia práctica |
|---|---|---|
| P-01 | Determinista en código, generativo en agentes. | Gate, selección de contexto, persistencia, reintentos y métricas no llaman a ningún LLM. |
| P-02 | El canon es la única fuente de verdad. | Ningún agente recibe información del libro que no venga del canon a través del generador de contexto (§6). |
| P-03 | El canon solo se escribe al aprobar. | Todo lo que produce un run va a staging; solo el gate aprobado dispara un commit atómico (§10.4). |
| P-04 | Toda salida de LLM es JSON validado contra schema. | Sin excepción, ni para la prosa del escritor (§9). |
| P-05 | Todo run es idempotente y reanudable. | La clave es `run_id` + `capitulo_id`; relanzar nunca repite trabajo aprobado (§11). |
| P-06 | Todo se mide. | Cada llamada LLM deja una fila de log con tokens, coste, latencia y resultado (§12). |
| P-07 | Los reintentos son incrementales. | El escritor recibe su texto anterior y las incidencias, nunca una orden de empezar de cero (§7.6). |
| P-08 | Nada se decide en silencio. | Cada decisión técnica lleva justificación; cada supuesto está en §17; cada cambio del spec, en §20. |

## §2 Glosario

> Estado: completa

Un término tiene una sola definición y un solo nombre en el código. Convención de nombres en código: identificadores en español, sin tildes ni eñes, `snake_case` para funciones, variables, campos JSON y ficheros; `PascalCase` para clases y tipos. Los prefijos de identificador (`per_`, `evt_`, ...) se definen en §3.1.2.

### §2.1 Términos del dominio narrativo

| Término | Definición | Nombre en código |
|---|---|---|
| Brief | Entrada del usuario que arranca un proyecto: época, premisa, tono, idioma y número de capítulos. Es inmutable una vez creado el proyecto. | `Brief` / `brief.json` |
| Proyecto | Un libro en producción: brief, canon, runs, estado y configuración. Vive en un directorio propio. | `Proyecto` / `proyecto_id` |
| Canon | Base de datos del libro. Única fuente de verdad: personajes, línea de tiempo, dossier histórico, escaleta, resúmenes y capítulos aprobados. Se lee antes de escribir y se escribe solo al aprobar (P-02, P-03). | `Canon` |
| Dossier histórico | Colección de datos históricos de la época del libro, cada uno con fuente y estado. Parte del canon; buscable (§3.14). | `Dossier` / `canon/dossier/` |
| Dato histórico | Unidad del dossier: un hecho concreto de época (vestimenta, política, comida, lenguaje, ...), con fuente y estado ∈ {verificado, inventado}. | `DatoHistorico` |
| Ficha | Registro estructurado de una entidad del canon. Hay fichas de personaje, de capítulo y de dato histórico. "Ficha" a solas no se usa en código; siempre se especializa. | `Personaje`, `FichaCapitulo`, `DatoHistorico` |
| Personaje | Ficha de un actor de la novela: voz, motivación, arco, dónde está y qué sabe. | `Personaje` |
| Línea de tiempo | Lista ordenada de eventos de la trama cruzados con hechos históricos reales. | `Timeline` / `canon/timeline.json` |
| Evento | Elemento de la línea de tiempo. Tipo `trama` (ocurre en la novela) o `historico` (ocurrió en la realidad y ancla la trama). | `Evento` |
| Escaleta | Plan del libro producido por el arquitecto: arco en tres actos, promesas narrativas y una ficha por capítulo. | `Escaleta` / `canon/escaleta/` |
| Arco | Estructura global del libro en tres actos, con la función de cada acto y los puntos de giro. | `Arco` / `canon/escaleta/arco.json` |
| Acto | Cada una de las tres partes del arco. Un capítulo pertenece exactamente a un acto. | `acto` ∈ {1, 2, 3} |
| Ficha de capítulo | Plan de un capítulo dentro de la escaleta: qué pasa, quién sale, dónde, cuándo y qué beats lo componen. Existe antes de escribir el capítulo. | `FichaCapitulo` |
| Capítulo | Unidad de generación y aprobación del libro. Tiene una ficha (plan), cero o más borradores (intentos) y, al aprobarse, un texto y un resumen en el canon. | `Capitulo` / `capitulo_id` |
| Capítulo redactado | Salida del escritor para un intento: la prosa dividida en escenas más sus metadatos. Solo entra al canon si el gate aprueba. | `CapituloRedactado` |
| Escena | Subdivisión del capítulo redactado con unidad de lugar, tiempo y personajes. Es la unidad de localización de las incidencias. | `Escena` |
| Beat | Unidad mínima de la ficha de capítulo: un suceso o giro que el capítulo debe contener. Un beat se realiza en una o varias escenas. | `Beat` |
| Promesa | Compromiso narrativo con el lector (setup) que debe pagarse más adelante (payoff). Se registra en el arco y se sigue capítulo a capítulo. | `Promesa` |
| Resumen de capítulo | Un párrafo por capítulo aprobado, más los hechos clave y el estado final de personajes. Fuente principal del contexto para capítulos posteriores y del editor global. | `Resumen` / `canon/resumenes/` |
| Resumen global | Composición determinista de los hechos clave de todos los capítulos aprobados, usada como memoria comprimida del libro (§6.3). | `ResumenGlobal` |
| Retoque | Elemento de la lista que devuelve el editor global: un problema estructural con capítulos afectados y acción sugerida. | `Retoque` |

### §2.2 Términos del harness y del flujo

| Término | Definición | Nombre en código |
|---|---|---|
| Harness | El código determinista que orquesta agentes, canon, gate y persistencia (P-01). | paquete `harness/` |
| Agente | Componente que hace una llamada LLM con un prompt fijo y devuelve JSON validado. Dos clases: generador (produce contenido) y revisor (evalúa contenido). | `Agente`, `AgenteGenerador`, `AgenteRevisor` |
| Revisor | Agente que evalúa un capítulo redactado y devuelve una nota y una lista de incidencias. Hay tres: continuidad, anacronismos, lógica y ritmo. | `RevisorContinuidad`, `RevisorAnacronismos`, `RevisorLogicaRitmo` |
| Generador de contexto | Módulo del harness que lee el canon y construye el paquete de contexto de un capítulo bajo un presupuesto de tokens (§6). No es un agente. | `GeneradorContexto` |
| Paquete de contexto | Salida del generador de contexto: los fragmentos del canon seleccionados para un capítulo, ya serializados, con su recuento de tokens. | `PaqueteContexto` |
| Run | Una ejecución de una etapa del flujo sobre un proyecto: investigación, arquitectura, un capítulo o el editor global. Identificado por `run_id`. Un run de capítulo contiene de 1 a `max_reintentos` intentos. | `Run` / `run_id` |
| Intento | Una iteración del loop de capítulo dentro de un run: una llamada al escritor, tres revisiones y una evaluación del gate. Numerado desde 1. | `Intento` / `intento` |
| Reintento | Todo intento con número mayor que 1. El límite `max_reintentos` cuenta reintentos, no intentos: con `max_reintentos = 3` hay como máximo 4 intentos (1 inicial + 3 reintentos). | `max_reintentos` |
| Nota | Puntuación entera de 1 a 10 que un revisor asigna al capítulo en su dimensión. Es la única escala usada en el spec (§7.4). | `nota` |
| Incidencia | Problema concreto detectado por un revisor: severidad, localización en el texto, descripción, evidencia en el canon y sugerencia. | `Incidencia` |
| Severidad | Gravedad de una incidencia ∈ {bloqueante, mayor, menor, sugerencia}. `bloqueante` impide la aprobación por sí sola (§7.5). | `severidad` |
| Revisión | Salida completa de un revisor sobre un intento: nota, incidencias y resumen. | `Revision` |
| Gate | Función determinista del harness que, a partir de las tres revisiones, decide aprobar, reintentar o escalar (§7.5). | `GateCalidad` / `evaluar_gate()` |
| Veredicto del gate | Resultado del gate ∈ {aprobado, reintentar, escalado}. | `VeredictoGate` |
| Escalada | Parada del flujo con entrega de artefactos al usuario, porque un capítulo agotó los reintentos o hubo un fallo irrecuperable (§7.7, §11). | `Escalada` |
| Staging | Área de trabajo donde un run escribe sus salidas antes de que el gate las apruebe. Nunca se lee como canon. | `staging/` |
| Commit del canon | Aplicación atómica de las salidas en staging al canon tras la aprobación del gate (§10.4). No confundir con un commit de git. | `commit_canon()` |
| Snapshot | Copia íntegra del canon tomada justo después de cada commit del canon, que permite volver al estado tras el capítulo N (§10.3). | `Snapshot` / `snapshots/` |
| Estado del proyecto | Fichero que registra en qué etapa está el proyecto, qué capítulos están aprobados y qué run está en curso. Es lo que lee la reanudación (§11.5). | `EstadoProyecto` / `estado.json` |
| Proveedor | Implementación concreta de la interfaz de llamada a un LLM (Anthropic, OpenAI, local, mock). El harness solo conoce la interfaz. | `ProveedorLLM` |
| Llamada LLM | Una petición a un proveedor y su respuesta, con tokens, coste y latencia registrados (§12.1). | `LlamadaLLM` |
| Comprobación determinista | Verificación en código sobre el capítulo redactado que se ejecuta antes de los revisores (personaje muerto que aparece, dato no registrado, etc.) (§7.3). | `ComprobacionDeterminista` |
| Presupuesto de tokens | Máximo de tokens de entrada que el generador de contexto puede gastar en un paquete; se reparte por bloques con prioridades de recorte (§6.4). | `presupuesto_tokens` |

### §2.3 Términos de versionado

| Término | Definición | Dónde |
|---|---|---|
| Versión del spec | SemVer de este documento, en la cabecera YAML. Independiente del versionado del canon. | Cabecera, §20 |
| Versión del canon | Número entero que se incrementa con cada commit del canon; identifica un snapshot. | §10.2 |
| ADR | Registro de una decisión de arquitectura, con contexto, opciones, decisión, consecuencias y estado. | §18 |

## §3 Modelo de datos del canon

> Estado: pendiente

## §4 Arquitectura del harness

> Estado: pendiente

## §5 Catálogo de agentes

> Estado: pendiente

## §6 Generador de contexto

> Estado: pendiente

## §7 Loop de capítulo y gate de calidad

> Estado: pendiente

## §8 Editor global

> Estado: pendiente

## §9 Contratos de I/O y validación

> Estado: pendiente

## §10 Persistencia y versionado del canon

> Estado: pendiente

## §11 Errores, reintentos y reanudación

> Estado: pendiente

## §12 Observabilidad y costes

> Estado: pendiente

## §13 Configuración

> Estado: pendiente

## §14 Estructura del repo

> Estado: pendiente

## §15 Plan de evaluación y tests

> Estado: pendiente

## §16 Roadmap por fases

> Estado: pendiente

## §17 Riesgos y decisiones abiertas

> Estado: pendiente

## §18 Decisiones de arquitectura (ADRs)

> Estado: pendiente

### §18.1 ADR-0001 — Formato del canon

> Estado: pendiente

### §18.2 ADR-0002 — Framework de orquestación

> Estado: pendiente

### §18.3 ADR-0003 — Revisores en paralelo vs. secuencial

> Estado: pendiente

### §18.4 ADR-0004 — Criterio del gate

> Estado: pendiente

### §18.5 ADR-0005 — Política de selección de contexto

> Estado: pendiente

## §19 Trazabilidad diagrama → spec

> Estado: pendiente

## §20 Historial de cambios del spec

> Estado: pendiente
