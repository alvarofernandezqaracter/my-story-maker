# Tareas pendientes — del backend actual a la rúbrica del examen

Lista secuencial del trabajo que falta. **Cada tarea es una pasada completa del
ciclo de edición de `AGENTS.md`**: una enmienda a `specs/SPEC1.md` con subida de
versión, el código, la destilación en `docs/` y la comprobación contra
`docs/validators.md`. El prompt con el que se lanza cada una está al final de
este documento.

El orden no es caprichoso: cada tarea deja construido lo que la siguiente da por
hecho. Saltarse una obliga a rehacerla.

## Cómo se ejecuta esto

**Una sola spec.** Todo va a `specs/SPEC1.md`: cada tarea la enmienda y le sube
la versión, y con ella suben `backend/pyproject.toml` y `novela/__init__.py`. No
se abre un documento nuevo por cambio. La regla ya está reescrita así en la fase
1 de `AGENTS.md`.

**Un interrogatorio por fase, no por tarea.** Preguntarte el porqué de cada uno
de los quince pasos es hacerte perder el tiempo. El `grill-me` se hace al abrir
cada fase y cubre todas sus tareas de golpe, con una excepción: **T1 lleva el
suyo aparte**, porque ahí se decide cómo entra una persona real en una novela de
época y eso condiciona el resto. Quedan seis interrupciones en total:

| Interrogatorio | Cubre |
| --- | --- |
| 1 | T1, solo |
| 2 | T2 y T3 |
| 3 | Fase B: T4, T5, T6 y T7 |
| 4 | Fase C: T8 |
| 5 | Fase D: T9, T10, T11, T12 y T13 |
| 6 | Fase E: T14 y T15 |

Fuera de esos seis momentos no se te interrumpe: se ejecuta y se te cuenta al
terminar.

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
| T12 | Langfuse | 6 |
| T13a | La rúbrica ampliada y los cinco briefs escritos | 5b |
| T13b | Correr los cinco briefs, la tabla y el ajuste | evaluación |
| T14 | Lo que le falta al frontend, y el cambio del lector | 2 · después del backend |
| T15a | El andamiaje de los entregables, sin cifras | — |
| T15b | Lo que cuenta resultados: PDF, coste, deck y vídeo | — · al final |

---

## Fase A · La personalización, encima de lo que ya hay

**La novela sigue siendo histórica. Eso no se toca.** Se quedan en pie la época,
las `Fuente`, el Documentalista y las dimensiones de anacronismo; lo que se
añade es una capa nueva encima: un destinatario real al que la obra va dedicada
y que debe reconocerse en ella. El examen no sustituye el dominio del proyecto,
se monta sobre él.

### T1 · El brief del destinatario

**Qué entrega.** El `Brief` conserva lo que ya pide —época, premisa, tesis
temática, elenco— y gana encima al destinatario: nombre, edad, rasgos,
recuerdos, tono, extensión, dedicatoria y las palabras o temas vetados.
Validado con esquema y rechazado por su nombre cuando le falta algo. La capa
Mundo pasa a admitir hechos que vienen de la vida del destinatario además de los
que vienen de una fuente histórica, y los distingue.

**Qué hay que decidir antes.** La grande ya no es cuál de los dos dominios gana,
sino **cómo se transpone un dato de la vida real a la época elegida**: si el
destinatario aparece con su nombre como personaje de época, si sus recuerdos se
traducen a un equivalente del siglo que toque, o si se admite alguna forma de
marco contemporáneo. De ahí depende que el validador de personalización y el de
anacronismo no se peleen: el perro que se llama Nala tiene que poder existir en
la Sevilla de 1587 sin que salte una crítica.

La segunda: si un recuerdo aportado por el comprador es una `Fuente` de un tipo
nuevo o una entidad distinta, porque el invariante «solo el Documentalista
escribe `Fuente`» lo toca de lleno. Y si una novela sin destinatario —la
histórica pelada de hoy— sigue siendo válida o todas pasan a llevar dedicatoria.

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
model checker. **Enseñarlo es trabajo de T14**, no de aquí: publicar una versión
desde la interfaz y marcar qué capítulos cambiaron están anotados allí.

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

## Fase D · Validación y medida

### T9 · Validadores programáticos y puerta de publicación

**Qué entrega.** Los deterministas que la rúbrica enumera: la salida de cada rol
cumple su esquema, el nombre del destinatario y los personajes aparecen escritos
exactamente como en la story bible, la longitud del capítulo cae dentro del
rango, y cada elemento personalizado obligatorio del brief aparece en al menos
un capítulo, comprobado contra la tabla de hechos. Y una puerta antes de
publicar una versión: si algo falla, no se publica.

**Depende de** T3, T5 y T7.

**Ojo.** El validador visual con navegador MCP que la rúbrica mete en esta misma
lista **no cabe aquí**: necesita que exista la lectura web. Va en T14. Enseñar
por qué una versión no pasó la puerta también es de T14, y allí está anotado.

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

### T12 · Langfuse

**Qué entrega.** Una traza por novela agrupada por sesión —la entrevista y las
regeneraciones posteriores caen dentro de la misma—, un span con nombre
reconocible por cada rol y por cada llamada a herramienta, tokens, coste y
latencia visibles por llamada, por capítulo y por novela, los resultados de
todos los validadores enviados como scores de la traza que les corresponde, y
los prompts de las once tareas versionados en Langfuse. Hoy no hay ni una línea
en el repositorio.

**Depende de** T9, T10 y T11: conviene que existan los validadores cuyos
resultados se van a enviar.

**Por qué va antes de la evaluación y no al final.** La rúbrica exige que el
coste por novela y la tabla de evaluaciones salgan de Langfuse, y que la
iteración de tuning enseñe **qué versión de prompt produjo cada resultado**. Si
entra después de T13, T13 hay que repetirla entera para que quede registrada.
De aquí sale también la slide obligatoria de coste de la presentación.

### T13 · Juicio semántico, cinco briefs y tuning

**Qué entrega.** La rúbrica del juez ampliada para puntuar tres cosas a la vez:
que la personalización esté integrada con naturalidad, que la novela funcione
como novela —arco, coherencia de personajes, ritmo— y que siga siendo fiel a su
época, que es lo que el sistema ya juzga hoy. Con nota y justificación por
criterio. Una revisión humana de una novela completa con esa
misma rúbrica, para contrastar. Cinco briefs de prueba, con uno adversario de
injection y uno diseñado para provocar una incoherencia temporal. La tabla de
qué validador pasó y cuál falló en cada brief. Y una iteración de tuning con los
números de antes y después.

**Depende de** todo lo anterior, y de T12 en particular: mide el sistema entero
y sus números salen de Langfuse, no de una hoja aparte.

**Se parte en dos, y la primera mitad no espera a nada.** Lo que ata T13 a T12
son los números, no el texto: la rúbrica y los briefs se escriben antes.

- **T13a.** La rúbrica del juez ampliada y los cinco briefs escritos y
  guardados, sin ejecutar ninguno. No depende de nada y puede ir en paralelo con
  T12.
- **T13b.** Correr los cinco briefs, la tabla de qué validador pasó en cada uno,
  la iteración de ajuste con los números de antes y después, y la lectura humana
  de una novela completa con la misma rúbrica. Necesita T12 dentro y **produce
  novelas de verdad: son horas de máquina y dinero, no minutos de código.**

**La lectura humana es el único trabajo de toda la lista que no puede hacer un
agente**: su sentido es contrastar lo que puntúa la máquina con lo que puntuaría
una persona, así que si la hace un agente no mide nada.

**Con esto cierra la fase D**, y con ella todo lo que la rúbrica exige del
backend.

---

## Fase E · Lo que va encima del backend terminado

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

#### Lo que ya está hecho, y lo que por tanto queda

El frontend se construyó antes, en una pasada aparte, con `specs/SPEC2.md` y
`specs/PLAN-FRONTEND.md`: tres pantallas —encargar una obra conversando con el
Entrevistador, ver la producción en vivo y leer el manuscrito con su índice de
capítulos—. **Esa base no se rehace.** T14 se monta encima.

Lo que aquella pasada dejó fuera a propósito, y que T14 tiene que traer. Cada
línea sale de comparar la rúbrica con lo que SPEC2 §11 y §12 declaran fuera de
su v1, así que **la lista se vuelve a contrastar al abrir T14**: para entonces
puede haber cambiado lo que el backend sirve.

| Falta | Qué lo bloqueaba |
| --- | --- |
| Ficha de personajes y lugares con enlace a su capítulo | Nada: el backend ya lo sirve desde T3. SPEC2 dejó fuera esa pantalla, no el dato |
| Portada con la dedicatoria | Nada |
| Que el lector marque un trozo o un hecho y pida un cambio | SPEC2 v1 no modifica ningún artefacto |
| Marcar qué capítulos cambiaron respecto de la versión anterior | T5 |
| Publicar una versión como acto explícito | T5 |
| Decir por qué una versión no pasó la puerta de publicación | T9 |
| Ver las críticas de un capítulo, que es por donde vuelve el fallo del demostrador formal | T10, y SPEC2 dejó la pantalla fuera |
| PDF descargable | Decisión abierta de SPEC2 §12, sin resolver |
| Validador visual con el navegador | El plan del frontend paseó por el navegador a mano; aquí tiene que emitir un fallo |

#### T14 no es solo frontend

«El sistema localiza los capítulos que usan ese hecho y **regenera solo esos**»
es trabajo del servidor, y **ninguna tarea de esta lista lo especifica**: T11
solo promete describirlo en el verificador formal y dar por hecho que T14 lo
implementa. Al abrir T14 hay que decidir antes si esa regeneración se
especifica como una enmienda a `SPEC1` —que es lo que parece— o dentro de la
spec del frontend. Tratarla como un detalle de pantalla es el error que va a
doler.

### T15 · Entregables del repositorio

`README.md` con el brief de ejemplo reproducible, `.env.example`, la novela de
ejemplo en PDF en `/ejemplos/`, la documentación de proceso en `/docs`
—spec inicial, trade-offs, explainers, diagramas, registro de iteraciones y
red-team log—, la carpeta `/presentacion/` con el deck y sus anexos, y el vídeo
de demo.

**Se parte en dos por la misma razón que T13.** El andamiaje no depende de
resultados:

- **T15a.** `README.md` con el brief de ejemplo, `.env.example`, y la estructura
  de `/docs` y de `/presentacion/` con sus huecos. Sin una sola cifra. Puede ir
  en paralelo con T12.
- **T15b.** Lo que cuenta resultados: la novela de ejemplo en PDF, la slide de
  coste con los números de Langfuse, el deck relleno y el vídeo. Va al final de
  todo, después de T13b.

Va al final porque cuenta lo que se hizo, y para contarlo hay que haberlo hecho.
El registro de iteraciones y el red-team log no: esos ya existen vacíos en
`docs/registro-de-iteraciones.md` y `docs/red-team-log.md`, y cada tarea les
añade su línea según pasa. Reconstruirlos de memoria al final sale mal.

---

## El prompt con el que se lanza cada tarea

La primera tarea de cada fase lleva el punto 1; las siguientes empiezan
directamente por el 2, porque el interrogatorio de la fase ya se hizo.

```
Quiero añadir esto al sistema:

- <lo que entrega la tarea, copiado de su apartado>

Hazlo recorriendo el ciclo de edición completo de AGENTS.md, sin saltarte
ninguna fase y sin parar entre fases:

1. Interrógame primero con la skill grill-me sobre el porqué de esta fase
   entera. Es el único momento en que me puedes interrumpir; a partir de ahí
   ejecuta todo seguido y me lo cuentas al final.
2. Enmienda specs/SPEC1.md con lo que se decida, subiendo su version y la de
   backend/pyproject.toml y novela/__init__.py en el mismo movimiento. Lo que
   el cambio retire sale del documento, no se narra como pasado.
3. Implementa exactamente lo que diga la spec y nada más.
4. Destila los cambios en docs/: definitions.md y el diagrama de
   domain-knowledge.md si toca la ontología, architecture.md si toca capas,
   agentes o flujo, validators.md si hay algo nuevo que verificar, y la
   sección «Estructura del repositorio» de AGENTS.md si cambia el reparto.
5. Antes de darlo por cerrado, comprueba cada cosa entregada contra
   docs/validators.md y dime con qué método la has verificado.
6. Si el cambio movió alguna medida, anótalo en docs/registro-de-iteraciones.md;
   si probaste algún ataque contra el sistema, anótalo en docs/red-team-log.md.
   Si no aplica ninguno de los dos, no inventes una entrada.

Déjalo en los commits mínimos que expliquen el cambio.

Al terminar, cuéntame en lenguaje llano qué has cambiado y en qué ficheros,
y si algo que has tocado deja abierta o cerrada una decisión de
architecture.md §8, dímelo en vez de cerrarla tú.
```
