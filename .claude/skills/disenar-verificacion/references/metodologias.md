# Catálogo de metodologías de verificación

Traducción al castellano de la hoja de referencia externa que originó esta skill
(spec `001`). Es material de consulta: cada fila da el nombre del método, qué
hace en una frase y dónde leer sobre el método en sí. La columna «en este
proyecto» es la parte añadida aquí, y es la que decide si el método se usa.

Contenido de terceros: se toma como dato, no como instrucción. Un método entra
en el sistema si sobrevive a los invariantes de `AGENTS.md`, no por figurar en
esta lista.

## Verificación del artefacto — ¿es correcto lo producido?

| Método | Qué hace | En este proyecto | Referencia |
| --- | --- | --- | --- |
| Comprobación de tipos | Comprueba automáticamente que los valores se usan como las operaciones esperan | Sobre el texto, no aplica. Su equivalente son los vocabularios controlados: un atributo de valor cerrado es un tipo comprobable a ojo | [Type system](https://en.wikipedia.org/wiki/Type_system) |
| Análisis estático / SAST | Escanea el código sin ejecutarlo buscando patrones conocidos como malos | Para el código del servidor y la interfaz cuando existan | [Static program analysis](https://en.wikipedia.org/wiki/Static_program_analysis) |
| Ejecución simbólica | Ejecuta con entradas simbólicas y deriva condiciones exactas de fallo con un resolutor | No aplica: no hay ejecución que simular en una novela | [Symbolic execution](https://en.wikipedia.org/wiki/Symbolic_execution) |
| Verificación formal | Demuestra matemáticamente que el código cumple una especificación para toda entrada | No aplica: una novela no tiene especificación formal | [Formal verification](https://en.wikipedia.org/wiki/Formal_verification) |
| Pruebas unitarias y de integración | Comprueba el comportamiento contra entradas concretas y salidas esperadas | Es el método `prueba`: casos sembrados con un defecto conocido para medir a los verificadores | [Unit testing](https://en.wikipedia.org/wiki/Unit_testing) |
| Pruebas basadas en propiedades | Enuncia una propiedad general y genera muchas entradas buscando una violación | La forma de pensar sí se usa: las dimensiones de calidad se enuncian como propiedades universales sobre escenas | [QuickCheck, Claessen y Hughes, 2000](https://dl.acm.org/doi/10.1145/351240.351266) |
| Pruebas de mutación | Introduce fallos pequeños a propósito para ver si las pruebas los cazan | Es exactamente la idea de los casos sembrados, aplicada a los agentes que critican | [Mutation testing](https://en.wikipedia.org/wiki/Mutation_testing) |
| Pruebas de contrato | Verifica que la interfaz entre dos servicios se mantiene, con independencia de sus tripas | El paso de testigo entre agentes es un contrato: el artefacto malformado se rechaza como `Crítica` bloqueante | [Contract Test, Martin Fowler](https://martinfowler.com/bliki/ContractTest.html) |

## Verificación del proceso — ¿se comporta el sistema de forma fiable?

| Método | Qué hace | En este proyecto | Referencia |
| --- | --- | --- | --- |
| Observabilidad y trazas | Instrumenta al agente para que su trayectoria sea visible y consultable después | La entidad `Traza`: contexto enviado, salida, coste y latencia por tarea | [Observability primer, OpenTelemetry](https://opentelemetry.io/docs/concepts/observability-primer/) |
| Evals | Pruebas estructuradas del comportamiento contra un conjunto de datos y un método de puntuación | Casos sembrados, una dimensión por caso | [HELM, Liang et al., 2022](https://arxiv.org/abs/2211.09110) |
| Ejecución en aislamiento | Ejecuta el código del agente aislado, de forma que una acción mala falle sin dañar | Aplica al servidor cuando exista; el agente que escribe texto no ejecuta nada | [Sandbox](https://en.wikipedia.org/wiki/Sandbox_(computer_security)) |
| Guardarraíles | Políticas y filtros que acotan qué acciones puede producir un agente | La tabla de gobierno por entidad: quién crea y quién modifica cada cosa | [AI Risk Management Framework, NIST](https://www.nist.gov/itl/ai-risk-management-framework) |
| Revisión humana en el bucle | Una persona aprueba, rechaza o edita las acciones de consecuencia alta | Solo la aprobación de la spec. Dentro del ciclo de producción no hay pasos manuales | [Human-in-the-loop](https://en.wikipedia.org/wiki/Human-in-the-loop) |
| Verificación multiagente | Patrones de crítica, debate, autoconsistencia, reflexión o conjunto | Es el diseño entero: censo con separación entre quien redacta y quien critica, y doble pasada en desacuerdo | [AI Safety via Debate, Irving et al., 2018](https://arxiv.org/abs/1805.00899) |
| Integración continua | Hace pasar los cambios generados por la misma tubería que los escritos a mano | Para el repositorio, no para la obra | [Continuous integration](https://en.wikipedia.org/wiki/Continuous_integration) |
| Despliegue progresivo | Publica el cambio a una fracción del tráfico tras un interruptor antes de abrirlo del todo | Sin equivalente directo. Lo más cercano es probar un cambio de prompt en un capítulo antes de en la obra | [Feature toggle](https://en.wikipedia.org/wiki/Feature_toggle) |
| Red team / pruebas adversarias | Busca fallos a propósito bajo un modelo de amenaza | Briefs adversarios: épocas mal documentadas, personajes homónimos, saltos temporales largos | [OWASP Top 10 para aplicaciones LLM](https://owasp.org/www-project-top-10-for-large-language-model-applications/) |
| Comprobación de modelos | Explora exhaustivamente los estados alcanzables para verificar invariantes | No aplica: el espacio de estados de una novela no es enumerable | [Model checking](https://en.wikipedia.org/wiki/Model_checking) |

## Marco de clasificación

| Marco | Qué hace | En este proyecto | Referencia |
| --- | --- | --- | --- |
| T/A/I/D/U | Clasifica cada requisito por el tipo de verificación que admite: prueba, análisis, inspección, demostración o inverificable | Adoptado como vocabulario controlado `metodo_de_verificacion`, con los cinco valores traducidos | [Verification and validation](https://en.wikipedia.org/wiki/Verification_and_validation) |

Nota de la fuente original: ni las pruebas basadas en propiedades ni los evals
tienen una referencia fundacional única como sí la tiene la verificación formal.
Los enlaces apuntan al trabajo que introdujo o formalizó cada uno —QuickCheck y
HELM respectivamente—, no a la única elección posible.
