# Tareas pendientes — del backend actual a la rúbrica del examen

Lista secuencial del trabajo que falta. **Cada tarea es una pasada completa del
ciclo de edición de `AGENTS.md`**: un interrogatorio, una enmienda a
`specs/SPEC1.md` con subida de versión, el código, la destilación en `docs/` y
la comprobación contra `docs/validators.md`. El prompt con el que se lanza cada
una está al final de este documento.

El orden no es caprichoso: cada tarea deja construido lo que la siguiente da por
hecho. Saltarse una obliga a rehacerla.

## Estado de partida

Ya está hecho y no se vuelve a tocar salvo que una tarea lo diga: el almacén
SQLite de las tres capas con su índice híbrido, el guion declarativo del
capítulo, el presupuesto de contexto con el techo de 100 000 tokens, las once
carpetas de tarea con su contrato y su prompt, el ejecutor que lanza subagentes
de Claude Code, la API de diez rutas y la batería de 274 pruebas.

## El orden de un vistazo

| # | Tarea | Bloque de la rúbrica |
| --- | --- | --- |
| T1 | El brief del destinatario | 1 |
| T2 | El entrevistador | 1 |
| T3 | Hechos con uso por capítulo y cronología | 1 y 4 |
| T4 | Checkpoint, reanudación y reintentos | 3 |
| T5 | Versiones de la obra | 3 y 2 |
| T6 | `CLAUDE.md`, skill, comandos y MCP de navegador | 3 |
| T7 | Los dos hooks | 3 |
| T8 | Palabras prohibidas y audit log | 7 |
| T9 | Validadores programáticos y puerta de publicación | 5a |
| T10 | Validador formal de la historia en Lean 4 | 5c |
| T11 | Validador formal del sistema en TLA+ | 5d |
| T12 | Juicio semántico, cinco briefs y tuning | 5b y evaluación |
| T13 | Langfuse | 6 · aplazado por decisión tuya |
| T14 | Lectura interactiva y cambio del lector | 2 · después del backend |
| T15 | Entregables del repositorio | — · al final |

---

## Fase A · El dominio del examen

Sin esto no hay examen que valga: hoy el sistema escribe novela histórica para
un editor profesional, y lo que se pide es novela personalizada de regalo.

### T1 · El brief del destinatario

**Qué entrega.** Un `Brief` que describe a una persona real y la ocasión del
regalo —nombre, edad, rasgos, recuerdos, género, tono, extensión, dedicatoria y
las palabras o temas vetados—, validado con esquema y rechazado por su nombre
cuando le falta algo. La capa Mundo pasa a admitir hechos que vienen de la vida
del destinatario y no de una fuente histórica.

**Qué hay que decidir antes.** La grande: si la novela histórica desaparece o si
conviven las dos. De la respuesta depende qué pasa con `epoca`,
`tesis_tematica`, el Documentalista, las `Fuente` y las diez dimensiones de
anacronismo que hoy sostienen medio `validators.md`. Segunda: si un recuerdo
aportado por el comprador es una `Fuente` de un tipo nuevo o una entidad
distinta, porque el invariante «solo el Documentalista escribe `Fuente`» lo
toca de lleno.

**Docs que se tocan.** `definitions.md` y el diagrama del árbol del mundo de
`domain-knowledge.md`; `architecture.md` si cambia el censo de agentes;
`validators.md` si se retiran o añaden dimensiones.

### T2 · El entrevistador

**Qué entrega.** Un rol nuevo que conversa con el comprador y devuelve el brief
de T1 ya completo: detecta los campos que faltan, detecta al menos un tipo de
contradicción —edad contra tono, por ejemplo— y admite texto libre pegado
(una carta, una anécdota) del que extrae hechos. Ese texto entra como dato
delimitado, nunca como instrucción, igual que ya hacen las fuentes.

**Depende de** T1: no se puede entrevistar para rellenar un formulario que aún
no existe.

**Qué hay que decidir antes.** Si la entrevista es una conversación de varios
turnos por la API o una sola pasada sobre lo que el comprador ya escribió. Y
si el entrevistador es el rol doce del censo o una tarea del Planificador —el
invariante «un rol, una tarea» dice que rol nuevo, pero conviene que lo digas
tú—.

### T3 · Hechos con uso por capítulo y cronología

**Qué entrega.** Dos cosas que la rúbrica pide por su nombre. Primera: cada
hecho de la story bible registra **en qué capítulos se ha usado**, y quien
escribe lo anota al cerrar el capítulo. Segunda: una tabla de cronología con
eventos, momento, personajes presentes, lugar y fechas de nacimiento.

**Depende de** T1.

**Por qué va aquí.** Es el cimiento de tres tareas posteriores: el validador que
comprueba que cada elemento personalizado aparece en algún capítulo (T9), el
fichero que se le pasa a Lean (T10) y la propagación de un cambio del lector a
los capítulos afectados (T14). Si se deja para después, esas tres se quedan sin
suelo.

---

## Fase B · El bucle, a prueba de fallos

### T4 · Checkpoint, reanudación y reintentos

**Qué entrega.** Un punto de guardado por capítulo: si la generación se cae, se
reanuda desde el último capítulo cerrado sin duplicar ni perder ninguno. Y un
límite de reintentos por tarea, con lo que pasa cuando se agota escrito en
alguna parte y no improvisado.

**Por qué antes que nada más.** A partir de aquí todas las tareas añaden pasos
al bucle. Cuanto más tarde se meta el checkpoint, más sitios hay que tocar.
Además es la mitad de lo que T11 tiene que especificar en TLA+.

### T5 · Versiones de la obra

**Qué entrega.** Una obra deja de tener un solo manuscrito y pasa a tener
versiones: al regenerar se conserva la anterior íntegra y se registra qué
capítulos cambiaron respecto de ella. Publicar una versión es un acto
explícito, no el efecto lateral de terminar de escribir.

**Depende de** T4.

**Por qué en el backend y no con la web.** La rúbrica lo pide como invariante
—la versión anterior se conserva siempre— y T11 tiene que demostrarlo con el
model checker. La web de T14 solo lo enseña.

### T6 · `CLAUDE.md`, skill, comandos y MCP de navegador

**Qué entrega.** El fichero de instrucciones de la raíz escrito como pieza de
examen que es, y no la línea suelta que hay hoy. Una skill reutilizable
declarada como tal. Los comandos y subagentes propios commiteados en `.claude/`.
Y `.claude/mcp.json` con un servidor MCP de navegador —Playwright o Chrome—
configurado, que T14 usará para mirar la lectura con sus propios ojos.

**Por qué aquí.** Es barato, no depende de nada y todo lo que venga después se
escribe mejor con el `CLAUDE.md` en condiciones.

### T7 · Los dos hooks

**Qué entrega.** Un hook de validación de capítulo y un hook de policy,
enganchados al ciclo real, no de adorno.

**Depende de** T4 y T6.

**Qué hay que decidir antes.** Qué hace exactamente el hook de policy antes de
que exista la lista de palabras prohibidas de T8: si nace vacío y T8 lo llena, o
si se pospone. Yo propondría lo primero, para no tocar dos veces el enganche.

---

## Fase C · Guardrails

### T8 · Palabras prohibidas y audit log

**Qué entrega.** Tres listas en SQLite: la global de insultos y términos
ofensivos, y la de cada novela con lo que el comprador vetó en la entrevista.
La comparación normaliza antes: mayúsculas, acentos, plurales y variantes
simples. Si hay coincidencia el capítulo vuelve a quien lo escribió, con límite
de intentos; si se agota, la generación se detiene y lo dice. Cada coincidencia
queda en un audit log de las decisiones del policy engine. Con pruebas de un
caso por nivel y un caso de variante con acento o plural.

**Depende de** T1 (los vetos llegan en el brief), T4 (el límite de intentos) y
T7 (el hook donde se engancha).

---

## Fase D · Validación

### T9 · Validadores programáticos y puerta de publicación

**Qué entrega.** Los deterministas que la rúbrica enumera: la salida de cada rol
cumple su esquema, el nombre del destinatario y los personajes aparecen escritos
exactamente como en la story bible, la longitud del capítulo cae dentro del
rango, y cada elemento personalizado obligatorio del brief aparece en al menos
un capítulo, comprobado contra la tabla de hechos. Y una puerta antes de
publicar una versión: si algo falla, no se publica.

**Depende de** T3, T5 y T7.

**Ojo.** El validador visual con navegador MCP que la rúbrica mete en esta misma
lista **no cabe aquí**: necesita que exista la lectura web. Va en T14.

### T10 · Validador formal de la historia en Lean 4

**Qué entrega.** Un generador que vuelca la cronología de SQLite a un fichero
Lean; al menos dos invariantes demostrados —orden temporal de los eventos, edad
coherente con la fecha de nacimiento, un personaje no está en dos sitios a la
vez, un personaje no reaparece después de un evento que lo excluye—; ejecución
automática con `lake build`; y la regla de que si falla, la versión no se
publica y el fallo vuelve al editor como crítica.

**Depende de** T3 y T9.

**Lo que hay que conseguir además.** Un caso real en el que Lean pilla una
incoherencia que los demás validadores no pillaron. Si no aparece solo, se
fabrica un brief que la provoque —la rúbrica pide justamente uno diseñado para
eso— y se documenta.

### T11 · Validador formal del sistema en TLA+

**Qué entrega.** La especificación del flujo completo como máquina de estados:
configuración, planificación, escritura, validación y publicación, con los
reintentos, la reanudación desde checkpoint y la regeneración por cambio del
lector. Tres invariantes de seguridad y una propiedad de liveness. Verificación
con TLC sobre un modelo pequeño, con la configuración en el repositorio. Y el
mapeo explícito de cada acción de la especificación al trozo de código que la
implementa.

**Depende de** T4, T5 y T9, porque son los estados que tiene que describir.
Describe también la regeneración de T14, que aún no existirá: eso se especifica
igual, y T14 se implementa después contra lo especificado.

**Lo que hay que guardar por el camino.** Si TLC saca un contraejemplo, se anota
junto al cambio que provocó en el código. Es una evidencia que la rúbrica pide.

### T12 · Juicio semántico, cinco briefs y tuning

**Qué entrega.** La rúbrica del juez ampliada para puntuar las dos cosas a la
vez: que la personalización esté integrada con naturalidad y que la novela
funcione como novela —arco, coherencia de personajes, ritmo—, con nota y
justificación por criterio. Una revisión humana de una novela completa con esa
misma rúbrica, para contrastar. Cinco briefs de prueba, con uno adversario de
injection y uno diseñado para provocar una incoherencia temporal. La tabla de
qué validador pasó y cuál falló en cada brief. Y una iteración de tuning con los
números de antes y después.

**Depende de** todo lo anterior: mide el sistema entero.

**Aviso de orden.** Esta tarea produce las evidencias que hay que enseñar en la
presentación, y la rúbrica dice que salgan de Langfuse: el coste por novela, los
scores y **qué versión de prompt produjo cada resultado**. Si T13 sigue
aplazada, T12 hay que rehacerla entera después. Recomendación: mover T13 justo
antes de T12.

---

## Fase E · Lo que aplazaste

### T13 · Langfuse

Una traza por novela agrupada por sesión, un span por rol y por herramienta,
tokens, coste y latencia por llamada, por capítulo y por novela, los resultados
de todos los validadores enviados como scores, y los prompts versionados. Hoy no
hay ni una línea en el repositorio.

Lo dejas para luego y es tu decisión, pero arrastra tres cosas: la tabla de
evals de T12, la slide obligatoria de coste por novela y la mitad de las
evidencias de la presentación. Cuanto más tarde entre, más trabajo ya hecho hay
que repetir para que quede registrado.

### T14 · Lectura interactiva y cambio del lector

Web con índice de capítulos navegable, ficha de personajes y lugares sacada de
la story bible con enlace al capítulo donde aparece cada uno, y portada con la
dedicatoria. El lector selecciona un fragmento o un hecho y pide un cambio —«el
perro se llama Nala»—; el sistema localiza los capítulos que usan ese hecho,
regenera solo esos y marca cuáles cambiaron respecto de la versión anterior.
Más el PDF exportado, que hace falta igual aunque la lectura sea web.

Aquí entra también el validador visual con navegador MCP: el agente abre la
novela, navega y comprueba que el índice, la ficha y la portada se ven bien; si
no, lo registra como fallo y lo devuelve a quien corresponda.

**Depende de** T3 —los hechos saben en qué capítulos viven—, T5 —las versiones—
y T6 —el MCP de navegador configurado—.

### T15 · Entregables del repositorio

`README.md` con el brief de ejemplo reproducible, `.env.example`, la novela de
ejemplo en PDF en `/ejemplos/`, la documentación de proceso en `/docs`
—spec inicial, trade-offs, explainers, diagramas, registro de iteraciones y
red-team log—, la carpeta `/presentacion/` con el deck y sus anexos, y el vídeo
de demo.

Va al final porque cuenta lo que se hizo, y para contarlo hay que haberlo hecho.
Lo único que conviene ir escribiendo por el camino es el registro de iteraciones
y el red-team log: reconstruirlos de memoria al final sale mal.

---

## El prompt con el que se lanza cada tarea

```
Quiero añadir esto al sistema:

- <lo que entrega la tarea, copiado de su apartado>

Hazlo recorriendo el ciclo de edición completo de AGENTS.md, sin saltarte
ninguna fase y sin parar entre fases:

1. Interrógame primero con la skill grill-me sobre el porqué de cada cosa.
   Es el único momento en que me puedes interrumpir; a partir de ahí ejecuta
   todo seguido y me lo cuentas al final.
2. Actualiza specs/SPEC1.md con lo que se decida, subiendo su version y la de
   backend/pyproject.toml y novela/__init__.py en el mismo movimiento.
3. Implementa exactamente lo que diga la spec y nada más.
4. Destila los cambios en docs/: definitions.md y el diagrama de
   domain-knowledge.md si toca la ontología, architecture.md si toca capas,
   agentes o flujo, validators.md si hay algo nuevo que verificar, y la
   sección «Estructura del repositorio» de AGENTS.md si cambia el reparto.
   Lo que se retire desaparece del documento, no se narra como pasado.
5. Antes de darlo por cerrado, comprueba cada cosa entregada contra
   docs/validators.md y dime con qué método la has verificado.

Al terminar, cuéntame en lenguaje llano qué has cambiado y en qué ficheros,
y si algo que has tocado deja abierta o cerrada una decisión de
architecture.md §8, dímelo en vez de cerrarla tú.
```
