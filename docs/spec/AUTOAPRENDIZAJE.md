---
doc: spec-autoaprendizaje
version: 0.1.0
estado: borrador
actualizado: 2026-09-18
---

# Spec — Autoaprendizaje

Tercer spec del repositorio. [`SPEC.md`](SPEC.md) describe **cómo se escribe una
novela** y [`TRAZAS.md`](TRAZAS.md) **qué se ha aprendido mirando cómo se
escribió**. Este describe **cómo se mejora solo el prompt de un agente**, con un
dataset delante y una métrica que decide.

Tiene su propia versión. Mientras el banco no toque el diseño de la novela, sus
cambios no mueven la versión de nadie más; el día que la toque, se muda a
`SPEC.md` como manda la regla número uno.

## §1 Qué es esto y qué no es

**Qué es.** Un banco de pruebas. Coge el prompt vigente de un rol, deja que un
agente proponga variantes, las corre todas contra el mismo conjunto de casos,
mide con números y se queda con la que gana. Si ninguna gana, no cambia nada.

**Qué no es.** No escribe novelas, no lee ni toca el canon de ninguna
biblioteca, y no mejora «la calidad» en abstracto. Un loop que no puede decir de
antemano qué número tiene que bajar no es un loop de mejora, es una reescritura
con buena intención.

**Tampoco es un segundo motor.** El banco no reimplementa nada: para medir un
rol arranca el mismo camino delegado de §21 de `SPEC.md`, con el mismo subagente,
las mismas herramientas y el mismo modelo. Lo único que cambia entre dos
corridas es el texto del prompt. El Python del banco cuenta y compara; no
escribe prosa ni decide nada que requiera criterio.

**Relación con los otros dos documentos.** `TRAZAS.md` observa y no decide; este
sí decide, pero solo sobre el texto de un prompt. Cuando una ronda demuestre que
hay que mover un umbral, partir un rol o cambiar un campo del canon, eso es un
cambio de diseño y se muda a `SPEC.md` como `DA-xx` o como cambio de sección.
Aquí queda la referencia cruzada y el número que lo provocó.

## §2 Monotraza: cuál es la unidad que se mide

**Un loop, un rol, una llamada.** Cada caso del dataset es una entrada de un solo
agente —un brief para el investigador, un paquete de contexto para el escritor—
y produce una sola llamada, que es una sola traza. De ahí el nombre.

**Por qué así.** Porque la culpa de un número tiene dueño. En una traza de novela
entera, que el capítulo 4 salga caro puede ser del escritor, del paquete que le
armaron o de un dossier hinchado tres pasos antes, y no hay forma de separarlo.
Y porque una iteración cuesta una llamada en vez de un libro: se pueden hacer
veinte en una tarde.

**Lo que se pierde, y hay que tenerlo escrito.** El banco no ve los efectos
aguas abajo. Un investigador que gasta un 40% menos puede estar devolviendo un
dossier más pobre que empeora al escritor dos etapas después, y **ninguna
métrica monotraza lo detecta**. Contra eso hay dos defensas, las dos parciales:
las guardias de §3, que vigilan la salida del propio rol, y la costumbre de
escribir una novela entera después de una promoción y mirarla con `TRAZAS.md`.

## §3 El objetivo: una métrica que baja y varias que no pueden caer

Un **objetivo** es lo que se optimiza, y es la pieza central: sin él no hay loop.
Lleva siempre dos cosas.

- **La métrica objetivo.** Una sola, y con dirección: los tokens de la llamada
  bajan, el desvío sobre las palabras pedidas baja, la nota sube. Dos métricas
  objetivo a la vez no es un objetivo, es un empate esperando a pasar.
- **Las guardias.** Las métricas que no pueden empeorar. Son las que convierten
  «gasta menos» en «gasta menos **manteniendo** el rendimiento», que es lo único
  que se quiere de verdad. Cada guardia lleva su suelo.

**Ninguna métrica se puntúa a ojo.** O la calcula código sobre la salida del
rol, o la pone un juez de Langfuse (§6). Un número que depende de que alguien lo
mire no se puede correr veinte veces.

**Los once `VD-xx` de §9 de `SPEC.md` ya son métricas, y son gratis.** Son
comprobaciones deterministas sobre la salida de un rol, que es exactamente la
forma de una guardia. VD-04 vigila al investigador, VD-08 al escritor, VD-09 y
VD-10 al cronista y al validador. El banco los reutiliza tal cual en vez de
inventarse comprobaciones paralelas que dirían otra cosa.

Tres objetivos de ejemplo, que son los que dan forma al resto del documento:

| Objetivo | Rol | Métrica objetivo | Guardias |
|---|---|---|---|
| `investigador-barato` | investigador | Tokens de la llamada | VD-04 sin fallos; nº de datos usables sobre su suelo; las cuatro categorías representadas; nota del juez de dossier no peor que la del vigente |
| `escritor-longitud` | escritor | Desvío relativo sobre `palabras_objetivo` | VD-08 sin bloqueo; párrafos sobre `margenes.parrafos_min`; las tres notas del validador no peores que las del vigente |
| `validador-estable` | validador | Dispersión de la nota entre dos corridas del mismo capítulo | VD-10 sin fallos; las notas no se desplazan en bloque hacia arriba |

El tercero es el que explica por qué la métrica objetivo no siempre es dinero:
un validador que puntúa distinto el mismo texto dos veces seguidas rompe el gate
sin que ninguna traza lo delate.

## §4 El dataset: taller y reserva

**Los casos viven en Langfuse**, como dataset, y no en el repositorio. Es donde
ya están las corridas, las puntuaciones y la comparación entre versiones, y
duplicarlos aquí sería tener dos verdades. De cada ronda queda en disco un
espejo de solo lectura (§8) para poder mirar qué pasó sin abrir el navegador.

**El dataset se parte en dos y la partición no se mueve.**

| Partición | Quién la ve | Para qué |
|---|---|---|
| **Taller** | El optimizador, con los fallos de cada caso delante | Proponer la siguiente variante |
| **Reserva** | Nadie, nunca | Decidir si se promueve |

**El optimizador no ve la reserva jamás**, ni sus casos ni sus resultados. Sin
esa separación el loop aprende el dataset en vez del trabajo, y la mejora que
enseña la tabla no aparece luego en ninguna novela.

**Un dataset que no distingue no promueve.** Si todas las variantes sacan el
mismo número, el problema es del dataset y no de los prompts, y el banco lo dice
y para. Por eso hay un mínimo de casos en la reserva por debajo del cual ninguna
promoción es válida, por mucho que gane.

**Los casos son entradas de un rol, no novelas.** Se sacan de novelas ya
escritas —el brief de una, el paquete de contexto de un capítulo de otra— porque
así el banco mide sobre lo que el sistema produce de verdad y no sobre ejemplos
cómodos escritos para la ocasión.

## §5 El corredor: se mide donde se usa

**El candidato se corre con el mismo arnés que producción.** Una sesión de
Claude Code sin interactivo, con el subagente definido al vuelo
(`claude -p --agents`) llevando el prompt candidato y **las mismas herramientas
y el mismo modelo** que el subagente real. Lo único distinto es el texto.

**Por qué no se llama a la API directamente**, que sería más barato y más
determinista: porque entonces se mediría otro sistema. El prompt en producción
corre dentro de Claude Code, con su system prompt, sus herramientas y sus
ficheros leídos al arrancar. Una mejora medida fuera de ese arnés puede no
aparecer dentro, y lo único que se sabría es que el banco miente.

**Las métricas de coste salen gratis del hook de §22.** El `PostToolUse` sobre
`Agent` ya traza cada llamada a un subagente con su modelo, su duración y su
reparto de tokens y caché. El banco no cuenta tokens por su cuenta: usa el mismo
contador que cuenta los de las novelas, o los dos números acabarían sin cuadrar.

**Las corridas del banco no se mezclan con las novelas.** Corren con su propio
perfil —un `config.banco.json`, que es lo que §12 de `SPEC.md` llama perfil y
nada más— con su `trazas.entorno` propio. Así ni el informe de gasto de una
novela cuenta llamadas de banco ni al revés.

**Una ronda corre entera con un solo modelo, y lo escribe.** La primera pasada
de `TRAZAS.md` se quedó a medias justamente por esto: media novela en un modelo y
media en otro no comparan prompts, comparan regímenes.

**Y por qué esto sí es código.** El loop no tiene juicio dentro: contar tokens,
comparar dos números contra un margen y parar a la quinta ronda es aritmética.
Lo generativo —proponer la variante, juzgar la calidad— sigue fuera, en un
agente y en Langfuse. Es el mismo reparto de §1 de `SPEC.md`, aplicado a otra
máquina.

```bash
python -m novela objetivos                      # los objetivos definidos y su estado
python -m novela aprender --objetivo investigador-barato
python -m novela aprender --objetivo escritor-longitud --rondas 1 --seco
```

`--seco` corre la ronda entera y no promueve nada, pase lo que pase. Es el modo
en el que se estrena un objetivo nuevo.

## §6 El optimizador y el juez

**El optimizador** es un agente que recibe tres cosas: el prompt vigente, la
definición del objetivo con sus guardias, y los peores casos del **taller** con
lo que falló en cada uno. Devuelve un número fijo de variantes completas del
prompt, no parches ni instrucciones de edición: lo que se mide es un fichero
entero, y un prompt ensamblado a trozos no es reproducible.

Vive fuera de `agentes/`, en `autoaprendizaje/optimizador.md` con su subagente en
`.claude/agents/banco-optimizador.md`. La carpeta `agentes/` es el reparto de la
novela, y este no escribe libros.

**El juez** es lo que mide lo que el código no sabe medir: si un dossier sigue
sirviendo, si la prosa sigue teniendo pulso. Es un evaluador de Langfuse, como
los de §20 de `SPEC.md`, y hereda su regla entera: **su rúbrica no entra en este
repositorio**. Aquí pesa todavía más que allí. El optimizador escribe prompts
para maximizar una nota; si puede leer con qué vara se la ponen, escribirá para
la vara y el número subirá sin que nada mejore. Es el modo de fallo clásico de
esta clase de loops y la única defensa barata es que el examinado no vea el
examen.

**El optimizador tampoco ve el histórico de rondas anteriores**, por lo mismo:
con las diez variantes descartadas delante y sus notas, lo que aprende es la
forma de la métrica.

## §7 La regla de promoción

Se mide sobre la **reserva**, nunca sobre el taller.

```
promueve = objetivo_candidato mejora al vigente en >= margen_mejora
           y ninguna guardia cae por debajo de su suelo
           y la reserva tiene >= casos_minimos
```

**El vigente se vuelve a medir en cada ronda.** No se compara contra un número
guardado de la semana pasada, porque entre medias puede haber cambiado el modelo
de debajo y entonces la comparación es con otro sistema. Cuesta una tanda de
llamadas más por ronda y no es negociable.

**Empate es no promover.** Una guardia que empata vale; una objetivo que empata,
no. Cambiar el prompt tiene un coste que no está en la tabla —lo que se deja de
entender del sistema— y una mejora que no se distingue del ruido no lo paga.

**La promoción es automática.** El fichero se escribe y se commitea sin
preguntar, porque un loop que se para a pedir permiso en cada vuelta no es un
loop. Lo que la hace aceptable es que sea trivial de deshacer:

- Toca **un solo fichero**, `agentes/<rol>.md`, en un commit propio que no lleva
  ninguna otra cosa.
- El mensaje del commit lleva el objetivo, el número que ganó y el id de la
  ronda, así que `git revert` de esa línea devuelve el prompt anterior.
- **El banco no arranca con el árbol de trabajo sucio** en `agentes/`. Si hay
  cambios sin commitear, para antes de correr nada: no se puede prometer que
  revertir un commit deja el repositorio como estaba si había trabajo a medias
  dentro.

**Qué para el loop**, además de promover: agotar `rondas_max`, pasarse de
`gasto_max`, o encadenar `paciencia` rondas sin ninguna mejora. No hay reintento
infinito, igual que en §13 de `SPEC.md`: parar y mirar sale más barato.

## §8 Qué se escribe y dónde

**Lo único que el banco pisa es `agentes/<rol>.md`.** No toca `.claude/agents/`,
porque las herramientas y el modelo de un rol no se optimizan aquí: son
decisiones de diseño y viven donde dice §12 de `SPEC.md`. Y no toca `skills/`,
porque una skill la comparten varios roles y moverla dentro de un loop cambiaría
en silencio las métricas de otro.

```
autoaprendizaje/
  optimizador.md                      el encargo del optimizador (§6)
  objetivos/<objetivo>.json           métrica, guardias, dataset y suelos
  rondas/<fecha>-<objetivo>-<n>/
    candidatos/NN.md                  las variantes tal y como se corrieron
    medidas.json                      taller y reserva, por caso y por métrica
    veredicto.md                      qué ganó, por cuánto y contra qué vigente
```

Las rondas son **salida y no se versionan**, igual que la biblioteca: lo que hay
que conservar de una ronda promovida ya está en el commit del prompt y en
Langfuse. Lo que queda en disco es para poder mirarlo al día siguiente sin
reconstruir nada.

## §9 Estados de una ronda

`propuesta` → `medida` → `promovida` | `descartada` | `agotada` | `parada`

`descartada` es el resultado normal y sano: el candidato no ganó por el margen.
`agotada` es que se acabaron las rondas sin promover nada, y dice algo del
objetivo, no del prompt. `parada` es el tope de gasto, y deja la ronda a medias a
propósito en vez de terminarla a medio medir.

## §10 Configuración

Misma regla que todo el repositorio: **si un número del banco aparece escrito en
el código o en un prompt sin pasar por `config.json`, es un bug**. Seis claves
nuevas, que llevarán la tabla de §12 de `SPEC.md` de diecisiete a veintitrés el
día que entre el código.

| Clave | Propuesta | Para qué |
|---|---|---|
| `autoaprendizaje.rondas_max` | 5 | Vueltas antes de rendirse |
| `autoaprendizaje.candidatos_por_ronda` | 3 | Variantes que propone el optimizador cada vez |
| `autoaprendizaje.margen_mejora` | 0,10 | Mejora relativa mínima en la objetivo para promover |
| `autoaprendizaje.casos_minimos` | 12 | Suelo de casos en la reserva para que una promoción valga |
| `autoaprendizaje.gasto_max` | 5,0 | Tope en dólares de un loop entero |
| `autoaprendizaje.paciencia` | 2 | Rondas seguidas sin mejora antes de parar |

Reglas cruzadas: `paciencia <= rondas_max` y `margen_mejora > 0`. Un margen de
cero convierte el ruido en promociones.

**Esto obliga a tocar `SPEC.md`** en el mismo commit que traiga el código, no
después: §12 tiene la tabla de claves y dice cuántas son, y §18 la lista de
comandos. Es la regla número uno del repositorio y aquí se aplica igual.

## §11 Lo que este diseño no tiene

El precio, que conviene tenerlo escrito antes de fiarse de la primera tabla que
salga verde:

- **El banco se puede sobreajustar a su dataset.** La reserva lo hace caro, no
  imposible: veinte rondas contra la misma reserva la convierten poco a poco en
  taller. Los casos hay que renovarlos con cada novela nueva.
- **Monotraza no ve aguas abajo** (§2). Un rol más barato puede salir caro dos
  etapas después y el banco dará por buena la promoción.
- **El juez cuesta y no se ve.** Lo corre Langfuse con su propia conexión, así
  que su gasto no entra en `gasto_max` ni en el informe de §22, igual que pasa
  con los jueces de §20. El tope de gasto es del banco, no del total.
- **Una promoción automática puede meter una regresión.** La reserva reduce la
  probabilidad; no la anula. La red de abajo es `git revert`, y por eso la forma
  del commit es parte del diseño y no una costumbre.
- **No hay test que pruebe que el banco mejora nada.** Se puede probar la
  aritmética de la comparación y la regla de parada; que el loop produzca
  prompts mejores solo lo dice la siguiente novela.

## §12 Decisiones abiertas

Ids propios, `AA-xx`, que no se reutilizan. Nada de esto impide estrenar el
banco; todo impide dar por buena una promoción sin mirarla.

| Id | Decisión pendiente | Por qué importa | Cuándo decidirla |
|---|---|---|---|
| AA-01 | Si el banco puede optimizar también las `skills/` | Hoy quedan fuera por compartirse entre roles, pero `estilo-prosa` es donde de verdad vive la prosa del escritor | Cuando un objetivo del escritor se atasque en el prompt del rol |
| AA-02 | Cuántos casos y de cuántas novelas distintas | Un dataset sacado de un solo libro mide ese libro | Con dos novelas cerradas |
| AA-03 | Si la promoción exige además una novela entera de control | Es la única defensa real contra el límite de §2, y cuesta un libro por promoción | La primera vez que una promoción salga cara aguas abajo |
| AA-04 | Qué hacer cuando dos objetivos del mismo rol tiran en direcciones opuestas | Abaratar al investigador y ampliar su cobertura no caben en el mismo prompt | Cuando haya dos objetivos vivos sobre un mismo rol |
| AA-05 | Si el modelo del rol entra alguna vez en el loop | Hoy es fijo a propósito, pero DA-02 de `SPEC.md` pregunta lo mismo y el banco es quien tiene los números | Después de la primera promoción limpia |

## §13 Historial de cambios

Formato Keep a Changelog. Una entrada por versión; cada línea dice la sección
tocada y el motivo.

### [0.1.0] — 2026-09-18

**Añadido**
- §1–§12. Nace el documento con el diseño del banco monotraza: objetivo y
  guardias, dataset partido en taller y reserva, corredor sobre el mismo arnés
  que producción, promoción automática por margen y sus topes. Motivo: el
  autoaprendizaje cambia prompts que están bajo `SPEC.md`, así que necesita sus
  reglas escritas antes de la primera línea de código, no después de la primera
  promoción.
