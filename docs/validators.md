# Verificación: qué método le toca a cada dimensión

2026-09-21

## Qué contiene este documento

El reparto concreto de la verificación. `definitions.md` enumera las dimensiones
de calidad y `architecture.md` §5 describe en abstracto qué es un contrato de
verificación; aquí se dice, para cada dimensión, **con qué método se comprueba,
qué agente la comprueba, qué recibe exactamente y con qué severidad sale la
`Crítica`**. La segunda mitad trata el otro nivel: cómo se comprueba que el
sistema que escribe la novela funciona.

Este documento no define dimensiones nuevas ni roles nuevos. Si una dimensión
aparece aquí y no en `definitions.md`, es un error de este documento.

## 1. Los dos niveles

La verificación se parte en dos, y confundirlos es la causa de que un sistema
generativo parezca validado sin estarlo.

| Nivel | Pregunta | Objeto | Dónde se trata |
| --- | --- | --- | --- |
| Obra | ¿Es correcto el texto producido? | Párrafos, escenas, capítulos, la obra entera | §4 y §5 |
| Sistema | ¿Se comporta de forma fiable el conjunto de agentes? | Agentes, tareas, críticas, trazas | §6 |

El nivel de obra se apoya en el de sistema: un verificador cuya tasa de acierto
nadie ha medido no verifica, opina con formato de tabla.

## 2. Vocabulario controlado: `metodo_de_verificacion`

Cinco valores cerrados. Todo lo que se verifica lleva exactamente uno.

| Valor | Qué significa | Fiabilidad |
| --- | --- | --- |
| `prueba` | Se prepara un caso con resultado conocido y se mira si el sistema lo acierta | Alta, solo sobre los casos preparados |
| `analisis` | Se comparan datos ya escritos sin releer prosa: dos fechas, un estado plegado, una cuenta sobre un registro acumulado | Alta si el dato de partida es fiable |
| `inspeccion` | Un agente lee el texto y responde si un predicado se cumple, citando el fragmento | Media: depende de la proyección que reciba |
| `demostracion` | Se deja correr el sistema entero y se comprueba el resultado agregado al final | Baja para localizar la causa, alta para detectar que algo falla |
| `inverificable` | No hay predicado posible: se puntúa con rúbrica y se marca como ruido | Ninguna; no dispara regeneración por sí sola |

`inverificable` es una respuesta legítima y frecuente. Declararla vale más que
fabricar un predicado falso, que es lo que convierte el bucle de revisión en un
generador de impresiones con número.

## 3. El contrato de verificación

Toda dimensión con método `analisis`, `inspeccion` o `demostracion` se entrega a
un agente como un contrato de tres partes, y de ninguna otra forma.

- **Predicado.** Una frase que solo puede ser cierta o falsa, sobre entidades de
  la ontología. «El ritmo es bueno» no vale; «la proporción de párrafos en modo
  `sumario` cae dentro de la banda declarada para el capítulo» sí.
- **Proyección mínima.** La lista cerrada de lo que el agente recibe. Lo que
  sobra en la proyección es lo que produce falsos positivos.
- **Forma de la `Crítica`.** Qué va en `objeto`, qué `dimension`, qué
  `severidad` por defecto y qué cuenta como `evidencia` citable. Una `Crítica`
  sin evidencia se descarta antes de llegar al Revisor, así que el contrato debe
  decir qué evidencia acepta.

Una dimensión por tarea: al agente al que se le piden siete comprobaciones a la
vez solo le salen las dos primeras.

## 4. Reparto de las dimensiones de la obra

La severidad de la tabla es la de partida; el enrutado por severidad es el de
`architecture.md` §5.

### Alcance local — párrafo y página

El anacronismo se reparte entre dos agentes, y no por capricho: el material, el
conceptual y el social exigen ver el canon, que el Editor de estilo no recibe
por diseño. El alcance local describe dónde está el defecto, no quién lo
encuentra.

| Dimensión | Método | Agente | Proyección mínima | Severidad |
| --- | --- | --- | --- | --- |
| Anacronismo material | `inspeccion` | Verificador de continuidad | Fecha y lugar de la escena, fichas de los `Objeto` mencionados con su disponibilidad temporal | `mayor` |
| Anacronismo conceptual | `inspeccion` | Verificador de continuidad | `Concepto` disponibles en esa fecha y ese ámbito, texto | `mayor` |
| Anacronismo social e institucional | `inspeccion` | Verificador de continuidad | `Práctica` y cargos vigentes en el marco, texto | `mayor` |
| Anacronismo léxico | `inspeccion` | Editor de estilo | Texto y lista vetada corta del capítulo, derivada del `Registro lingüístico` de las escenas en juego | `menor` |
| Fatiga léxica | `analisis` | Editor de estilo | Registro acumulado de imágenes y muletillas ya usadas, texto nuevo | `menor` |
| Tics de modelo | `inspeccion` | Editor de estilo | Lista de patrones recurrentes de superficie, texto | `sugerencia` |
| Coherencia de voz | `inverificable` | Juez de rúbrica | Réplicas del mismo personaje en dos capítulos, rúbrica de voz | `menor`, ruidosa |

### Alcance de escena y capítulo

| Dimensión | Método | Agente | Proyección mínima | Severidad |
| --- | --- | --- | --- | --- |
| Cumplimiento del contrato | `inspeccion` | Verificador de continuidad | Contrato de la escena, texto de la escena | `bloqueante` |
| Cambio de valor | `inspeccion` | Verificador de continuidad | Campo `cambio_de_valor` declarado, texto | `mayor` |
| Integridad de POV | `inspeccion` | Verificador de continuidad | `pov` declarado, texto | `bloqueante` |
| Violación epistémica | `analisis` | Verificador de continuidad | Estado epistémico derivado del elenco presente, acciones y réplicas del texto | `bloqueante` |
| Continuidad de estado | `analisis` | Verificador de continuidad | Estado en N-1: presencias, posesiones y ubicaciones; hechos afirmados por el texto | `bloqueante` |
| Coherencia temporal | `analisis` | Verificador de continuidad | Fecha y lugar resultantes ya calculados y escritos por el Contable en cada `EventoEstado` | `bloqueante` |
| Ritmo | `analisis` | Verificador de continuidad | Modo declarado de cada párrafo, banda objetivo del capítulo | `menor` |

### Alcance global — obra

| Dimensión | Método | Agente | Proyección mínima | Severidad |
| --- | --- | --- | --- | --- |
| Progresión de arcos | `inspeccion` | Arquitecto de arcos | Arcos declarados, resúmenes de todos los capítulos | `mayor` |
| Economía narrativa | `analisis` | Arquitecto de arcos | Cola de compromisos con su estado | `bloqueante` al cierre de la obra |
| Curva de tensión | `analisis` | Arquitecto de arcos | `funcion_estructural` de todas las escenas en orden | `menor` |
| Distribución de revelaciones | `analisis` | Arquitecto de arcos | Eventos `aprende` y `revela_a` del log, con su capítulo | `menor` |
| Fidelidad histórica | `analisis` | Arquitecto de arcos | Recuento de elementos por `licencia` y justificaciones registradas | `mayor` |
| Cobertura documental | `analisis` | Arquitecto de arcos | Afirmaciones históricas del capítulo y sus `Fuente` asociadas | `mayor` |
| Obra cerrada sin defectos abiertos | `demostracion` | Arquitecto de arcos | Obra entera cerrada y el registro de sus críticas | `bloqueante` |

## 5. Lo que no admite predicado

Una sola dimensión sale `inverificable` del reparto: **coherencia de voz**.
Medir si dos réplicas suenan a la misma persona exige una distancia estilística
que nadie puede calcular leyendo, y la impresión de que «suena parecido» no es
una medida.

Tratamiento: la juzga el Juez de rúbrica contra una rúbrica escrita, su salida
se marca aparte como ruidosa y **no dispara regeneración por sí sola**. Si
reincide en el mismo personaje a lo largo de varios capítulos, eso sí es señal,
y la señal es la reincidencia, no la puntuación de un capítulo suelto.

## 6. Verificación del sistema que escribe

El nivel de obra mide la novela. Este mide el sistema, y es lo que permite
afirmar que el bucle converge en lugar de suponerlo.

| Qué se verifica | Método | Cómo | Qué delata |
| --- | --- | --- | --- |
| Que los verificadores detectan | `prueba` | Casos sembrados: un texto con un defecto conocido de una sola dimensión por caso | Tasa de detección por dimensión |
| Que no inventan defectos | `prueba` | Los mismos casos, con esa dimensión intacta | Falsos positivos por capítulo |
| Que el bucle converge | `analisis` | Recuento de iteraciones hasta `Aceptado` en la `Traza` | Capítulos que giran sin cerrar |
| Que las críticas son utilizables | `analisis` | Proporción descartada por falta de `evidencia` | Agentes que opinan en vez de comprobar |
| Que los artefactos están bien formados | `analisis` | Recuento de rechazos por campo ausente, por capítulo | Un rol con demasiado alcance o con pocos ejemplos |
| Que el sistema aguanta lo difícil | `prueba` | Briefs adversarios: época mal documentada, personajes homónimos, saltos temporales largos | Dimensiones que solo fallan bajo presión |
| Que cabe en el presupuesto | `analisis` | Tokens por ejecución frente al techo de 100 000 | Verificación que se come la generación |

Tres señales de verificación mal diseñada, todas visibles en la `Traza`: el
agente que no encuentra nada nunca —casi siempre es una proyección incompleta,
no un texto impecable—, el que encuentra algo siempre —predicado vago, o
proyección con material de sobra que invita a opinar— y dos agentes que
discrepan de forma sistemática en la misma dimensión, lo que significa que ese
predicado no era uno solo.

Los guardarraíles del sistema no son un filtro añadido: son la tabla de gobierno
de `architecture.md` §6 y los vocabularios controlados. Un atributo en texto
libre es un atributo que nadie puede verificar.

## 7. Qué queda fuera, y por qué

Del catálogo de metodologías de la ingeniería de software, tres no se aplican a
la obra: verificación formal, comprobación de modelos y ejecución simbólica. La
razón es la misma para las tres: **una novela no tiene especificación formal
contra la que probarse, y su espacio de estados no es enumerable**. Comprobación
de tipos, análisis estático, pruebas de mutación y pruebas de contrato sí
tendrán sentido sobre el código del servidor y de la interfaz cuando exista, que
es verificación del repositorio y no de la obra.

No hay revisión humana dentro del ciclo de producción. El editor lee el
resultado; no ejecuta pasos intermedios.

## 8. Las tres dimensiones que dependen de una decisión abierta

`architecture.md` §7 ya reconoce que coherencia temporal, fatiga léxica y léxico
vetado dejan de ser fiables sin cálculo, y lo compensa convirtiendo el cálculo
en un dato que escribe el agente que tiene el contexto para producirlo. Por eso
en §4 las tres aparecen como `analisis`: el agente compara datos ya escritos en
lugar de calcularlos.

El apaño funciona, pero desplaza el riesgo de «el código puede tener un fallo» a
«el dato escrito puede ser falso y nadie lo recalcula». Son, por tanto, las tres
dimensiones que cambiarían de método si se cerrase a favor del sí la decisión
abierta de `architecture.md` §8 sobre admitir herramientas externas de cálculo.
Mientras siga abierta, lo que las vigila es la reincidencia por dimensión de §6.
