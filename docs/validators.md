# Verificación: con qué se comprueba cada cosa

2026-09-23

## Qué contiene este documento

Cómo se establece que esto funciona. Aquí se dice **qué se verifica, con qué
método, quién lo comprueba, qué recibe exactamente y qué sale cuando falla**, y
se dice para las cuatro cosas que hay que verificar por separado: el texto que
se produce, el sistema de agentes que lo produce, el código que reparte los
turnos y los documentos con los que se gobierna todo lo anterior.

`definitions.md` enumera las dimensiones de calidad y `architecture.md` §5
describe en abstracto qué es un contrato de verificación. Este documento no
define dimensiones nuevas ni roles nuevos: si una dimensión aparece aquí y no en
`definitions.md`, es un error de este documento. Los instrumentos concretos que
se nombran —una herramienta, una biblioteca— pueden cambiar sin que cambie nada
más; lo que no cambia es el método y lo que se afirma con él.

## 1. Los cuatro objetos que se verifican

No fallan igual, así que no se comprueban igual. Confundirlos es la causa de que
un sistema generativo parezca validado sin estarlo.

| Objeto | Pregunta | Cómo falla | Dónde se trata |
| --- | --- | --- | --- |
| La obra | ¿Es correcto el texto producido? | Una contradicción, un anacronismo, una promesa que nadie paga | §4 y §5 |
| El sistema de agentes | ¿Se comporta de forma fiable? | Un verificador que no ve nada, un bucle que gira sin cerrar, una crítica sin evidencia | §7 |
| El código | ¿Hace lo que se dijo que haría? | Una frontera rota, un pliegue mal hecho, un presupuesto mal contado | §6 |
| Los documentos | ¿Dicen lo mismo entre sí y lo mismo que el sistema? | Una dimensión que solo existe en un documento, un rol que se nombra y no está en el censo, un doc que va por detrás del código | §11 |

Y dependen en cadena: **la obra se apoya en el sistema, el sistema se apoya en
el código y los tres se apoyan en lo que dicen los documentos**. Un verificador
cuya tasa de acierto nadie ha medido no verifica, opina con formato de tabla; un
guion que reparte mal las tandas revienta el techo antes de que ninguna
dimensión llegue a comprobarse; y una dimensión que este documento nombra y
`definitions.md` no reconoce es una comprobación que nadie sabe hacer.

La diferencia de fondo es que el código es determinista —la misma entrada da la
misma salida, así que una pasada buena demuestra algo— y los agentes no lo son:
el mismo contrato puede dar dos respuestas distintas, y una pasada buena no
demuestra nada. Por eso, del código se verifica el resultado y de los agentes se
verifica el proceso: que la trayectoria quede registrada, acotada, comprobada y
recuperable.

## 2. Vocabulario controlado: `metodo_de_verificacion`

Cinco valores cerrados. Todo lo que se verifica lleva exactamente uno, sea
texto, agente o código. Son la adaptación al dominio del marco estándar
**T/A/I/D/U** —test, analysis, inspection, demonstration, unverifiable—, en ese
mismo orden, y la letra se anota aquí para que la correspondencia sea visible.

| Valor | Marco | Sobre la obra y los agentes | Sobre el código | Fiabilidad |
| --- | --- | --- | --- | --- |
| `prueba` | T | Se prepara un caso con defecto conocido y se mira si el sistema lo acierta | Prueba unitaria, de integración o de propiedades con resultado esperado | Alta, solo sobre los casos preparados |
| `analisis` | A | Se comparan datos ya escritos sin releer prosa: dos fechas, un estado plegado, una cuenta sobre un registro acumulado | Se razona sobre el código sin ejecutarlo: tipos, contratos de importación, reglas de análisis estático | Alta si el dato de partida es fiable |
| `inspeccion` | I | Un agente lee el texto y responde si un predicado se cumple, citando el fragmento | Alguien lee el código o el artefacto y lo juzga | Media: depende de la proyección que reciba |
| `demostracion` | D | Se deja correr el sistema entero y se comprueba el resultado agregado al final | Se recorre una obra de punta a punta y se mira lo que quedó | Baja para localizar la causa, alta para detectar que algo falla |
| `inverificable` | U | No hay predicado posible: se puntúa con rúbrica y se marca como ruido | No hay método que valga lo que cuesta; se declara en §9 | Ninguna; no dispara regeneración por sí sola |

**La letra se queda en esta tabla y no viaja al resto del documento.** El valor
que se escribe en un artefacto, y por el que después se filtra y se cuenta, es
siempre el español: dos nombres para la misma cosa son dos vocabularios, y en
español las iniciales ni siquiera distinguirían `inspeccion` de
`inverificable`.

`inverificable` es una respuesta legítima y frecuente. Declararla vale más que
fabricar un predicado falso, que es lo que convierte el bucle de revisión en un
generador de impresiones con número. **Lo que no lleva método es un
`inverificable` sin declarar, y eso es un defecto de este documento, no del
sistema.**

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
  decir qué evidencia acepta. Y cuando el predicado se cumple, el agente deja
  constancia de ello: **una comprobación que no deja rastro no se distingue de
  una que no se hizo**, y sin ese rastro no hay forma de saber si una dimensión
  se quedó sin comprobar.

**La proyección mínima no se rellena por parecido.** Cuando una dimensión se
comprueba comparando hechos —continuidad de estado, violación epistémica,
coherencia temporal— su proyección se trae entera y por identificador. Una
búsqueda por semejanza devuelve una muestra, y el verificador que no recupera la
contradicción escribe que no la hay: el falso negativo sale con el mismo formato
que la comprobación correcta y nadie lo distingue. La recuperación por parecido
solo alimenta comprobaciones cuyo fallo es dejar de encontrar algo, nunca las
que afirman que algo no existe. En el reparto de §4 eso es una sola dimensión:
la fatiga léxica.

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

**Las cuatro dimensiones de anacronismo tienen una exención declarada.** Lo que
lleva licencia `personal` viene de la vida del destinatario al que va dedicada
la obra y se escribe con su nombre de hoy: no es un defecto, es el encargo. Los
tres del Verificador la reconocen por el grado de licencia de la ficha, que ven
en el canon; el Editor de estilo no ve el canon, así que recibe el destinatario
en su proyección y reconoce por ahí los nombres que no debe señalar. Sin esta
exención el nombre real saldría como defecto en cada capítulo y la obra se
atascaría corrigiendo el regalo.

| Dimensión | Método | Agente | Proyección mínima | Severidad |
| --- | --- | --- | --- | --- |
| Anacronismo material | `inspeccion` | Verificador de continuidad | Fecha y lugar de la escena, fichas de los `Objeto` mencionados con su disponibilidad temporal y su licencia | `mayor` |
| Anacronismo conceptual | `inspeccion` | Verificador de continuidad | `Concepto` disponibles en esa fecha y ese ámbito con su licencia, texto | `mayor` |
| Anacronismo social e institucional | `inspeccion` | Verificador de continuidad | `Práctica` y cargos vigentes en el marco con su licencia, texto | `mayor` |
| Anacronismo léxico | `inspeccion` | Editor de estilo | Texto, lista vetada corta del capítulo derivada del `Registro lingüístico` de las escenas en juego, y el destinatario | `menor` |
| Fatiga léxica | `analisis` | Editor de estilo | Ecos recuperados por parecido del registro acumulado de imágenes y muletillas, texto nuevo | `menor` |
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

## 6. Verificación del código

El código no escribe la novela: guarda artefactos, ensambla proyecciones,
reparte turnos y sirve lo producido. Por eso lo que hay que verificar de él no
es literario. Son cuatro cosas —la frontera, el guion, el pliegue y el
presupuesto— y las cuatro son deterministas, así que aquí sí se puede demostrar
algo y no solo comprobarlo por muestras.

### Lo que sostiene el corte se comprueba sin ejecutar

Las reglas de organización de `architecture.md` §7 no son preferencias de
estilo: son lo que impide que el sistema se convierta en el harness a medida que
el proyecto prohíbe. Todas son decidibles leyendo el código, así que son
`analisis` y corren en cada commit. Es la verificación más barata del proyecto y
la que más protege.

| Afirmación | Con qué se comprueba |
| --- | --- |
| Ninguna carpeta de `tareas/` importa a otra: se comunican por artefactos | Contrato de importación entre módulos |
| `almacen/` es la única puerta de lectura y escritura de la persistencia | Contrato de importación, más una regla que prohíbe abrir la base de datos fuera de ahí |
| `nucleo/` no importa ninguna tarea ni decide nada del dominio | Contrato de capas, y vigilar que `nucleo/` no engorde |
| En `frontend/`, solo `compartido/` llama a la API, y las funcionalidades no se importan entre sí | Regla de fronteras del linter |
| El único sitio con tipos declarados es el borde HTTP | Comprobación de tipos sobre `api/` |

### Dónde no se comprueban tipos, y por qué

El cuerpo del artefacto no se tipa por dentro: se guarda íntegro tal como lo
escribió el agente, y el backend solo extrae las columnas por las que hace falta
consultar (SPEC1, D-01). La consecuencia para la verificación es concreta y
conviene no olvidarla: **la comprobación de tipos no dice nada sobre la forma de
un artefacto**. Lo que impone esa forma es el esquema en el contexto del agente
que lo escribe y el rechazo del agente siguiente, y eso se verifica rompiendo un
artefacto a propósito y mirando que salga la `Crítica` bloqueante. Es `prueba`,
no `analisis`.

### La proyección se comprueba antes de mandarla

Un contrato declara su proyección mínima, pero hasta aquí nadie miraba si la
ventana que sale se parece a la que se declaró. Y esa es la avería más cara que
puede tener el sistema: si la proyección llega incompleta —el estado en N-1 no
se materializó, la ficha del objeto no se trajo—, el verificador **no falla,
contesta que el predicado se cumple**, porque no ha visto lo que lo rompía. El
falso negativo sale con el mismo formato que la comprobación buena y ya no hay
forma de distinguirlos.

Por eso el ensamblador compara cada ventana con el contrato antes de mandarla,
en las dos direcciones:

- **Completa.** Si falta una pieza declarada, la tarea no sale. Parar cuesta una
  vuelta; mandar un verificador ciego cuesta el resto de la obra.
- **Mínima.** Lo que va en la ventana sin estar declarado también es defecto: el
  material de sobra es lo que invita a opinar en vez de comprobar.

Es `analisis`, vive en `nucleo/` y es de lo más barato del documento, porque la
proyección ya está escrita en el contrato: solo hay que cotejarla con lo que se
manda.

### Pruebas

| Qué se prueba | Cómo |
| --- | --- |
| El guion, el enrutado por severidad, el tope de vueltas y la anchura de tanda | Se recorren enteros: el guion son diez pasos declarados, así que se enumera en lugar de razonar sobre él |
| El almacén | Escritura y lectura de cada tipo de artefacto, inmutabilidad de los que no cambian —que admiten la marca de caducado una vez y nada más—, rechazo por valor fuera de vocabulario, caducidad de la memoria de capítulo |
| El punto de guardado | Caídas sembradas: un ejecutor que tumba el proceso a mitad de cada tarea del capítulo y de la auditoría, y otro proceso que reanuda. Lo cerrado antes del corte sigue igual y la obra reanudada deja lo mismo que una sin cortes: un `Capitulo`, un juego de `EventoEstado`, un estado en N y un `Resumen de capítulo` por capítulo, el mismo manuscrito y ninguna traza abierta. Una caída entre `plegar` y el cierre no deja ningún evento. Lo del capítulo descartado sale del índice. Al arrancar se relanza la obra caída y ni la detenida ni la terminada |
| La política de reintentos | Averías sembradas en una tarea de cada política: la que produce testigo detiene la obra con tarea, intento y motivo y sin nada a medio escribir; la comprobación deja su `Crítica` «no comprobado» abierta y la obra cierra; `documentar` sigue sin crítica. Un paso del guion sin tope o sin política no carga, y la tarea cortada por una caída no cuenta como intento |
| El pliegue | Propiedad: plegar el estado en N-1 más los eventos de N da lo mismo que plegar el log entero. Regenerar el capítulo 12 y replegar hacia delante da lo mismo que plegar desde cero |
| El índice de parecido | Propiedad: borrarlo y reconstruirlo desde los artefactos devuelve los mismos fragmentos. El índice es derivado; los artefactos no |
| La persistencia | Cada migración sobre una copia de una obra de prueba; el bloqueo por escrituras concurrentes se ejercita con una tanda de verdad, no se supone |
| La frontera con la interfaz | El contrato OpenAPI versionado frente al que genera el código: si el borde cambia, la prueba lo vuelve a volcar y falla una vez, para que el movimiento pase por el diff. Comprueba además que toda operación declare la forma de lo que devuelve, porque un contrato con respuestas sin tipar no sirve para generar cliente. La mitad del cliente espera a que `frontend/` exista |
| Que las pruebas afirmen algo | Pruebas de mutación sobre `nucleo/` y sobre los permisos por rol, en periodo y no en cada commit, porque son lentas |

### El recorrido en seco

La única comprobación que ejercita el sistema entero sin gastar ni producir
novela: con un ejecutor fingido que devuelve artefactos preparados en vez de
llamar a un agente, el guion recorre los diez pasos de un capítulo, cada paso
encarga su tarea al rol que le toca, ningún rol escribe una entidad que no le
corresponde, las tandas respetan la anchura calculada y todo lo producido se
puede volver a servir. Es `demostracion`, y es lo primero que debe existir:
mientras no exista, cualquier fallo del guion se descubre gastando.

## 7. Verificación del sistema de agentes

El nivel de obra mide la novela. Este mide el sistema, y es lo que permite
afirmar que el bucle converge en lugar de suponerlo.

### La traza es la condición de todo lo demás

Toda tarea deja `Traza`. No decide nada por sí sola —por eso es `demostracion` y
no `prueba`—, pero sin ella los casos sembrados, la medida de reincidencia y la
comparación entre dos versiones de un prompt trabajan a ciegas. Las preguntas
que tiene que poder contestar son cuatro:

- Qué rol escribió qué artefacto, en qué capítulo y en qué intento.
- Qué había exactamente en la ventana cuando se produjo el borrador que falló.
- Cuál fue el pico de tokens de entrada concurrentes, y en qué paso.
- Qué fragmentos devolvió cada consulta por parecido y cuáles acabó usando el
  agente.

### Los guardarraíles no son un filtro añadido: son el diseño

Lo que impide que un rol haga lo que no le toca no es una instrucción en su
prompt, que es una petición y no una garantía. Es la tabla de gobierno de
`architecture.md` §6 impuesta por el backend, más el hecho de que cada tarea
arranque sin más herramientas que las que su contrato le concede (SPEC1, D-08).

| Guardarraíl | Método | Cómo se comprueba |
| --- | --- | --- |
| Cada rol escribe solo lo que la tabla de gobierno le asigna | `prueba` | Se enumeran, rol por rol, las escrituras posibles y se intenta la prohibida |
| Los vocabularios controlados | `analisis` | Un valor fuera de vocabulario se rechaza, y el rechazo se cuenta por capítulo |
| Los topes de ventana por rol | `analisis` | La tarea que no cabe se parte en unidades menores; recortar la proyección a ojo fabrica falsos negativos |
| Solo el Documentalista sale del sistema | `prueba` | Ningún otro rol tiene herramienta con la que salir; se comprueba enumerándolas |

### Medir a los verificadores

| Qué se verifica | Método | Cómo | Qué delata |
| --- | --- | --- | --- |
| Que los verificadores detectan | `prueba` | Casos sembrados: un texto con un defecto conocido de una sola dimensión por caso | Tasa de detección por dimensión |
| Que no inventan defectos | `prueba` | Los mismos casos, con esa dimensión intacta | Falsos positivos por capítulo |
| Que toda dimensión llegó a comprobarse | `analisis` | Recuento de constancias por unidad aceptada, contra las dimensiones que le tocaban por su alcance | Un paso del guion que se saltó, o una tanda que murió sin que nadie se enterase |
| Que ninguna comprobación se agota en silencio | `analisis` | Recuento de críticas «no comprobado» por dimensión y de trazas fallidas por paso, en la `Traza` | Un proveedor que falla siempre en el mismo rol, o una dimensión que se da por cerrada sin haberse comprobado nunca |
| Que la cuenta previa no engaña | `analisis` | Contexto estimado antes de mandar frente al medido al terminar, tarea por tarea. La cuenta previa incluye lo que el subagente arrastra de su parte: si solo cuenta la proyección, mide otra cosa | Un techo que se respeta sobre el papel y se rompe en la máquina |
| Que el bucle converge | `analisis` | Recuento de vueltas hasta `Aceptado` en la `Traza` | Escenas y capítulos que giran sin cerrar |
| Que las críticas son utilizables | `analisis` | Proporción descartada por falta de `evidencia` | Agentes que opinan en vez de comprobar |
| Que los artefactos están bien formados | `analisis` | Recuento de rechazos por campo ausente, por capítulo | Un rol con demasiado alcance o con pocos ejemplos |
| Que lo recuperado sirve | `analisis` | Proporción de fragmentos devueltos que el agente acaba usando | Consultas que llenan la ventana sin aportar nada |
| Que el sistema aguanta lo difícil | `prueba` | Briefs adversarios: época mal documentada, personajes homónimos, saltos temporales largos | Dimensiones que solo fallan bajo presión |
| Que cabe en el presupuesto | `analisis` | Pico de contexto de entrada concurrente frente al techo de 100 000 | Verificación que se come la generación |

Tres señales de verificación mal diseñada, todas visibles en la `Traza`: el
agente que no encuentra nada nunca —casi siempre es una proyección incompleta,
no un texto impecable—, el que encuentra algo siempre —predicado vago, o
proyección con material de sobra que invita a opinar— y dos agentes que
discrepan de forma sistemática en la misma dimensión, lo que significa que ese
predicado no era uno solo.

### Lo que ya es verificación cruzada, y lo que no se añade

El sistema no necesita un aparato de comprobación entre modelos por encima del
que ya tiene: **el censo es ese aparato**. Quien redacta no critica y quien
critica no redacta, así que el Verificador ya es el crítico del Redactor; y la
doble pasada con la proyección reducida cuando dos agentes discrepan ya es la
repetición que da consistencia, sin necesidad de un rol más.

Dos cosas quedan deliberadamente fuera. La primera, que un agente revise su
propia salida: no cuenta como verificación, lo prohíbe el invariante y no se
adopta ni como primera pasada. La segunda, un árbitro que resuelva la
discrepancia sistemática entre el Verificador y el Juez: quién arbitra es una
decisión abierta de `architecture.md` §8 y aquí no se cierra. Lo que sí existe
mientras tanto es la señal que la haría necesaria, que es la reincidencia por
dimensión de la tabla anterior.

### El adversario

No todo fallo es un descuido. Cuatro amenazas con nombre, cada una con la
comprobación que la vigila.

| Amenaza | Por dónde entra | Qué la para y cómo se comprueba |
| --- | --- | --- |
| Instrucción inyectada en una fuente | El Documentalista trae texto de fuera y sus fragmentos acaban en la ventana de otros roles | Lo traído entra como dato delimitado, nunca como instrucción. Se siembra una fuente con una orden dentro y se mira en la `Traza` si el Redactor se desvía |
| Deriva de objetivo | Tras varias vueltas, el texto se optimiza para pasar la criba en vez de para contar la escena | Reincidencia por dimensión y la auditoría del Arquitecto de arcos, que mira la obra y no el borrador |
| Contaminación del mundo | Un dato falso entra en el canon y envenena el contexto de todos los capítulos siguientes | El mundo solo cambia por `EventoEstado` del Contable y solo al cerrar capítulo. Se comprueba intentando escribir el mundo desde cualquier otro rol |
| Fuga de material | Un rol manda fuera lo que el sistema tiene dentro | Ningún rol salvo el Documentalista tiene herramienta con la que salir |

Lo que se encuentra en una de estas comprobaciones se queda como caso sembrado
para siempre: un ataque descubierto y no reincorporado al conjunto de casos es
un ataque que volverá.

### Cambiar un prompt es un cambio que se mide

El prompt y el contrato de cada rol viven junto a su tarea (SPEC1, D-03), así
que cambiarlos es un cambio de código y se trata como tal: la versión nueva
corre sobre la misma obra de prueba que la vigente y se comparan tasa de
detección, falsos positivos, vueltas hasta aceptar y coste. Se cambia una cosa
cada vez; volver atrás es recuperar el prompt anterior, que está en el
repositorio.

Con una condición: **el material con el que se juzga a un agente no vive donde
el agente puede leerlo**. Los casos sembrados y sus respuestas esperadas se
quedan fuera de `tareas/`, para que ninguna proyección los arrastre y ningún rol
aprenda a aprobar el examen en vez de a hacer el trabajo.

## 8. Matriz de cobertura

Qué afirma este sistema sobre sí mismo y con qué se sostiene cada afirmación.
Esta tabla es el entregable del documento; todo lo anterior la justifica.

| Afirmación | Con qué se comprueba | Método |
| --- | --- | --- |
| Las tres capas no se mezclan: la obra referencia el mundo por `id` y no lo duplica | Ningún cuerpo de escena contiene ficha de mundo; la referencia es el identificador | `analisis` |
| Un rol, una tarea | Enumeración de las carpetas de tarea contra el censo de `architecture.md` §2 | `analisis` |
| Ningún agente valida su propia salida | Enumeración por rol de lo que puede escribir, contra la tabla de gobierno | `prueba` |
| El mundo solo cambia por `EventoEstado` del Contable | Intento de escritura del mundo desde otro rol | `prueba` |
| El estado no se almacena, se deriva | El pliegue incremental da lo mismo que plegar el log entero | `prueba` |
| El contrato de la frontera dice lo que el servidor hace | El documento OpenAPI versionado se coteja con el que generan los modelos del borde | `prueba` |
| Solo el Documentalista escribe `Fuente` y es el único con salida al exterior | Permisos por rol y enumeración de las herramientas de cada tarea | `prueba` |
| Toda `Crítica` lleva evidencia citable | Recuento de descartes por falta de evidencia sobre las críticas emitidas | `analisis` |
| Sin harness a medida: `nucleo/` no decide nada del dominio | Contrato de importación, más vigilar su tamaño | `analisis` |
| `almacen/` es el único lector y el único escritor de la persistencia | Contrato de importación | `analisis` |
| El pico de contexto de entrada concurrente no pasa de 100 000 | Máximo de la suma de ventanas abiertas a la vez, en la `Traza` | `analisis` |
| El capítulo 40 cuesta lo que el capítulo 4 | Coste por capítulo de una obra de prueba larga | `demostracion` |
| El guion es reproducible: misma obra y mismos artefactos, misma secuencia | Recorrido en seco repetido | `prueba` |
| Una obra corre del brief al último capítulo con una sola orden | Obra de tres capítulos de punta a punta | `demostracion` |
| Ninguna operación de mantenimiento recae en el editor | Enumeración de las operaciones de escritura que ofrece la API | `analisis` |
| El índice de parecido se puede borrar y reconstruir sin pérdida | Reconstruir y comparar | `prueba` |
| Un artefacto malformado no llega al Revisor | Artefacto roto a propósito | `prueba` |
| Solo se indexa texto aceptado | Intento de recuperar como eco un borrador descartado | `prueba` |
| Los verificadores detectan lo que deben | Casos sembrados, uno por dimensión y severidad | `prueba` |
| Los verificadores no inventan defectos | Los mismos casos con la dimensión intacta | `prueba` |
| El bucle converge o se declara no convergido | Vueltas hasta `Aceptado` y capítulos cerrados marcados | `analisis` |
| Una fuente con una orden dentro no redirige al Redactor | Fuente sembrada con instrucción | `prueba` |
| Ninguna ventana sale incompleta ni con material de sobra | La proyección enviada se coteja con la declarada en el contrato | `analisis` |
| El techo estimado es el techo real | Estimación previa frente a medida posterior, tarea por tarea | `analisis` |
| Toda dimensión del alcance dejó constancia en cada unidad aceptada | Recuento de constancias contra las dimensiones que tocaban | `analisis` |
| El guion y los contratos de tarea dicen lo mismo | Cotejo de la criba y el rol de cada dimensión en los dos sitios donde están escritos | `analisis` |
| Toda proyección mínima la sabe traer el ensamblador | Cotejo de los materiales que cada contrato pide contra los que el ensamblador sabe construir | `analisis` |
| Lo que cada rol declara escribir es lo que la tabla de gobierno le asigna | Cotejo del contrato de cada tarea contra la tabla | `analisis` |
| Detener, o cortar la producción en cualquier punto, y reanudar no duplica ni pierde trabajo cerrado | Caída sembrada en cada tarea y reanudación desde otro proceso | `prueba` |
| Cerrar un capítulo es una sola transacción | Caída sembrada entre `plegar` y el cierre, y recuento de lo que quedó escrito | `prueba` |
| Tras una caída la obra se relanza sin ninguna orden | Arranque del backend sobre una base con una obra caída, una detenida y una terminada | `prueba` |
| Todo paso del guion declara su tope y lo que pasa al agotarse | Carga de un paso sin ellos | `prueba` |
| La política de cada paso es la que fija la spec | Lectura de `guion.toml` contra la tabla de SPEC1 RF-97, además enumerada en una prueba | `inspeccion` |
| Cada política de agotamiento hace lo que declara | Avería sembrada en una tarea de cada política | `prueba` |
| Los cuatro documentos dicen lo mismo entre sí | Los cotejos de §11 | `analisis` |
| La fecha y el lugar que el Contable escribe son correctos | — | `inverificable` |
| La novela merece leerse | — | `inverificable` |

Las dos últimas filas son deliberadas y están explicadas en §9. La última, sobre
todo: ningún método de este documento verifica que la novela sea buena. Es el
riesgo que todo este aparato existe para hacer más pequeño, y se nombra para que
nadie confunda una criba en verde con un libro.

**Y falta una distinción que conviene no perder.** Una afirmación sin método
puede serlo por dos motivos muy distintos: porque no hay método posible, y eso
es un `inverificable` y va en §9; o porque lo hay de sobra y nadie lo tiene
asignado todavía, y eso no es un `inverificable`, es un hueco, y va en §10. El
segundo caso es el peligroso, porque desde fuera las dos cosas se parecen a una
casilla vacía.

## 9. Registro de lo inverificable

Todo `inverificable` se lista aquí con su motivo. Uno que no esté en esta tabla
es un defecto del documento.

| Riesgo | Por qué no se verifica | Con qué se vigila |
| --- | --- | --- |
| Calidad literaria | No hay predicado posible, y el gusto del editor es el suelo, no un método | Rúbrica ruidosa marcada aparte; el editor lee el resultado |
| Fiabilidad del Juez de rúbrica | El juez es él mismo un modelo estocástico | Su salida no dispara regeneración; lo que vale es la reincidencia, no la nota suelta |
| Que el dato calculado sea falso | Coherencia temporal, fatiga léxica y léxico vetado se comprueban contra un dato que escribió el propio sistema, y nadie lo recalcula porque no se usan herramientas externas de cálculo | Reincidencia por dimensión. Las tres cambiarían de método si se cierra a favor la decisión abierta de `architecture.md` §8 |
| Forma interna del artefacto | No se tipa por decisión de diseño | El rechazo del agente siguiente, contado por capítulo |
| Reproducibilidad de la recuperación por parecido | Dos consultas pueden ordenar distinto entre versiones del modelo de huellas | Queda en la `Traza` qué se recuperó y qué se usó; el modelo de huellas se fija |
| Cambio de comportamiento del modelo | Fuera de control | Versión fijada, y los casos sembrados se repiten enteros al subirla |
| Que una fuente admitida sea mala | Con qué criterio se admite una fuente de fuera es una decisión abierta | Cobertura documental y la auditoría de cierre del Arquitecto de arcos |

Las tres dimensiones de la tercera fila son el mismo apaño visto tres veces:
convertir un cálculo en un dato escrito por el agente que tiene el contexto para
producirlo. Funciona, pero desplaza el riesgo de «el código puede tener un
fallo» a «el dato escrito puede ser falso y nadie lo recalcula».

## 10. Huecos: lo que nadie comprueba todavía

La tabla de gobierno de `architecture.md` §6 dice, entidad por entidad, quién la
vigila. Cotejada contra el reparto de §4, en cinco sitios ese vigilante **no
existe**: hay una entidad que alguien escribe, una columna que dice que está
vigilada y ninguna dimensión, ningún agente y ningún método detrás. Se listan
aquí en vez de inventarles una comprobación, porque taparlos exige una dimensión
nueva en `definitions.md` o un rol nuevo en el censo, y este documento no crea ni
lo uno ni lo otro.

| Hueco | Qué no comprueba nadie | Qué haría falta |
| --- | --- | --- |
| El pliegue | Que los `EventoEstado` del capítulo recojan **todo** lo que el texto aceptado dice que cambió. Un evento que falta no da error: envenena el estado de todos los capítulos siguientes, y el fallo aparece lejos de donde está la causa | Una dimensión de completitud del pliegue. La proyección que necesitaría —estado y texto aceptado— ya la tiene el Verificador de continuidad, así que el hueco es de dimensión, no de rol |
| El resumen | Que el `Resumen de capítulo` sea fiel al capítulo que resume. A partir de ahí es lo único que el Arquitecto de arcos verá nunca de ese capítulo: lo que el resumen se deje fuera desaparece de la obra | Una dimensión, y un agente que vea a la vez la prosa y el resumen. Hoy ninguno la tiene: el Arquitecto no ve prosa por diseño y el Archivero no puede validar lo que él mismo escribe |
| El canon inicial | Que las fichas del Constructor de mundo sean coherentes entre sí: distancias que cuadren, fechas que no se contradigan, vínculos recíprocos. Toda la continuidad posterior se mide contra ellas, de modo que un error de partida no se detecta jamás, se propaga | Un cotejo de consistencia entre fichas antes de planificar el primer capítulo. Es `analisis` y es barato; lo que falta es a quién se le encarga |
| La pasada de pulido | Lo que el Revisor toca en la última criba ya no vuelve a comprobarse. Es el único punto del ciclo donde arreglar algo `menor` puede meter un defecto `bloqueante` y salir con el capítulo cerrado | Volver a pasar la criba de bloqueantes sobre lo que la revisión de pulido tocó. Eso es un cambio del bucle de `architecture.md` §5, no un reparto de este documento |
| El plan | Que el contrato de una escena sea bueno, no solo que esté completo. Que no le falten campos lo caza el rechazo por artefacto malformado; que el `cambio_de_valor` declarado sea de verdad un cambio, o que el obstáculo se oponga al objetivo, no lo mira nadie antes de escribir | Una dimensión que se evalúe sobre el `Plan` y no sobre el texto, para gastar la regeneración antes de redactar y no después |

Los cinco se cierran por el ciclo de edición: son dimensiones o son roles, y eso
se abre con una spec. Mientras sigan aquí, lo que hay es la constancia de que se
conocen, que es bastante más de lo que hay cuando un hueco no está escrito.

## 11. Los entregables del ciclo también se verifican

Nada se da por bueno sin comprobarlo, y eso alcanza a lo que se entrega en las
tres fases del ciclo: la spec, el código y los docs. El código tiene su método
en §6. Los otros dos son documentos, y un documento se comprueba mirando si dice
lo mismo que los demás y lo mismo que el sistema.

| Qué se comprueba | Método | Cómo |
| --- | --- | --- |
| Toda dimensión que este documento nombra existe en `definitions.md` | `analisis` | Cotejo de las dos listas; una dimensión que solo está aquí es un error de aquí |
| Todo agente que este documento nombra existe en el censo | `analisis` | Lo mismo, contra `architecture.md` §2 |
| Cada proyección mínima cabe en el tope de ventana de su rol | `analisis` | Cotejo contra la tabla de topes. La que no cabe parte la tarea en unidades menores; recortar la proyección es fabricar falsos negativos |
| Ninguna decisión abierta se ha cerrado por el camino | `inspeccion` | Las de `architecture.md` §8 siguen en la lista, o hay una spec que las cierra y lo dice |
| La ventana de divergencia está cerrada | `analisis` | No hay una spec aprobada sin destilar cuando se abre la siguiente |
| Lo retirado no queda narrado como historia | `inspeccion` | Los docs describen el estado actual; lo que se quita, se quita, no se cuenta en pasado |

La spec, además, se comprueba contra sí misma: que cada objetivo tenga métrica,
línea base y meta, y que todo lo que declara verificable tenga aquí un método
asignado. Una spec que dice «se comprobará que funciona» no ha declarado nada.

## 12. Orden de adopción

No existe todo a la vez. Este orden es el que da más protección por unidad de
esfuerzo, y los cuatro primeros pasos valen más que todo el resto junto porque
son los que sostienen la frontera.

1. Contratos de importación y tipos en el borde HTTP. `analisis`
2. Cotejo de cada ventana contra la proyección declarada en su contrato, en las
   dos direcciones. `analisis`
3. El recorrido en seco con ejecutor fingido. `demostracion`
4. Pruebas de `nucleo/` y `almacen/`, incluidas las migraciones y la
   reconstrucción del índice. `prueba`
5. Permisos por rol enumerados y probados, incluida la escritura prohibida.
   `prueba`
6. `Traza` completa, capaz de contestar las cuatro preguntas de §7, y con ella
   la constancia de cada comprobación y la estimación frente a la medida.
   `demostracion`
7. Casos sembrados por dimensión: primero para fijar la línea base, después para
   exigir un umbral. `prueba`
8. Propiedades sobre el pliegue y sobre el índice. `prueba`
9. Briefs adversarios y fuente sembrada con instrucción. `prueba`
10. Pruebas de mutación sobre `nucleo/` y sobre los permisos. `prueba`

El segundo puesto no es un capricho: cuesta poco y es lo único que impide que
todo lo que viene después mida comprobaciones hechas a ciegas. Nada de esta
lista necesita la interfaz web y nada bloquea producir una obra.

## 13. Qué queda fuera, y por qué

**Sobre la obra:** verificación formal, comprobación de modelos y ejecución
simbólica. La razón es la misma para las tres: una novela no tiene
especificación formal contra la que probarse y su espacio de estados no es
enumerable.

**Sobre el código:** la comprobación de modelos sí tendría sentido sobre el
guion del capítulo y la tabla de gobierno, que son pequeños y son justamente
donde viven los invariantes. No se adopta porque el guion ya es un artefacto
declarativo de diez pasos y la tabla es finita: recorrerlos enteros en una
prueba da lo mismo por mucho menos. Si el guion dejara de ser enumerable, la
decisión se reabre.

**Revisión humana dentro del ciclo:** no hay. El editor lee el resultado; no
ejecuta pasos intermedios ni aprueba nada por el camino. Un paso manual
periódico sería un defecto de diseño, no un control de calidad.
