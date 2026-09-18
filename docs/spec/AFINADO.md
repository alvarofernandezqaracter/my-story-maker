---
doc: spec-afinado-de-prompts
version: 0.1.0
estado: borrador
actualizado: 2026-09-18
---

# Spec — Afinado de prompts

Tercer spec del repositorio. [`SPEC.md`](SPEC.md) describe **cómo se escribe una
novela**; [`TRAZAS.md`](TRAZAS.md), **qué se ha aprendido mirando cómo se
escribió**; este describe **cómo mejora solo el prompt de un agente**.

Tiene su propia versión, independiente de la de `SPEC.md` y de la del paquete.
Afinar un prompt sí cambia el sistema, pero lo cambia por su cuenta y con su
propio ritmo: una vuelta no mueve el diseño de nadie.

Nace con **un solo agente y una sola métrica**, a propósito. Crecerá añadiendo
loops para otros roles, cada uno con su sección; lo que no crecerá es el número
de mecanismos, que es uno y está en §5–§8.

## §1 Qué es esto y qué no es

**Qué es.** Un loop que mide el prompt de un rol con un número que calcula
código, propone una versión mejor, la vuelve a medir contra casos que no ha
visto, y la promueve solo si la mejora es más grande que el ruido de la propia
medida.

**Qué no es.** Un evaluador de calidad de novelas —eso es la evaluación de §20
de `SPEC.md`, y la ponen jueces de fuera—. Tampoco es un sitio donde se decida
nada del diseño: si una vuelta enseña que un umbral del gate está mal puesto,
eso se muda a `SPEC.md` y aquí queda la referencia cruzada, igual que hace
`TRAZAS.md`.

**Qué toca y qué no.** Toca exactamente un fichero del repositorio,
`agentes/<rol>.md`, y lo toca con un commit. **No toca el canon de ninguna
novela, ni `config.json`, ni las skills, ni el frontmatter de ningún
subagente.**

## §2 El orden, que no se negocia

Cinco pasos y siempre en este orden. Está escrito porque saltarse el primero
produce trabajo impecable sobre el problema equivocado, que es el fallo más caro
de detectar porque todo parece correcto.

| Paso | Qué se hace | Por qué antes que el siguiente |
|---|---|---|
| 1 | **Dónde está el dinero.** Gasto y llamadas por rol, de la observabilidad | Elegir rol sin esta cifra es elegir a ojo |
| 2 | **Qué métrica.** Una objetivo con su dirección, y las guardias | La métrica se elige con el reparto del gasto delante |
| 3 | **Medir el vigente**, varias pasadas, sin optimizar nada | De aquí salen la **línea base** y el **ruido** |
| 4 | **Los umbrales**, calibrados contra lo medido en el paso 3 | Un umbral inventado convierte el loop en un sorteo |
| 5 | **El loop** | Todo lo anterior es su entrada |

Dos reglas que salen de haberlo hecho mal antes:

- **Si el margen que se persigue no supera al ruido de la métrica, el loop no
  mide: sortea.** El ruido es la diferencia entre dos pasadas idénticas del
  mismo prompt sobre el mismo caso, y se mide, no se supone.
- **Una guardia que el prompt vigente no pasa no protege nada.** Toda guardia se
  fija en lo que el vigente cumple de verdad, medido en el paso 3, nunca en un
  ideal. Una guardia imposible no vuelve al loop prudente: lo vuelve incapaz de
  promover, y encima lo disimula.

## §3 El primer loop: el validador de anacronismos

**El rol es el validador**, y la cifra que lo sostiene son **24 de las 41
llamadas y el 73,7% del coste contado** de la única novela con validador trazado
(`TRAZAS.md` §6). En el régimen de hoy —los ocho subagentes en haiku— empata con
el cronista en coste por capítulo, 0,032 $ cada uno, y sigue siendo la mitad de
las llamadas.

Pero el coste no es la razón principal. **El validador es el único rol cuya
salida se puede puntuar con código sin que el sistema se examine a sí mismo.**
Para saber si un capítulo está mejor escrito o si un resumen es fiel hace falta
un juez; para saber si el validador ve un anacronismo basta con meterle uno a
propósito y mirar si le baja la nota. La respuesta correcta la pone quien
construye el caso, no el sistema.

Y hay una tercera razón, que viene de `SPEC.md` §23: la única palanca que baja
el coste y sube la calidad a la vez es reducir los intentos por capítulo
(OB-02), y los intentos los decide el gate con lo que los validadores le dicen.

**De las tres dimensiones se afina `anacronismos`** porque es la única con un
defecto que se puede sembrar sin ambigüedad: un objeto o una idea que no existía
en la fecha del brief. Sembrar una contradicción de canon o un fallo de ritmo
exige criterio para decidir si de verdad lo es, y un caso discutible no sirve
para medir.

| | Métrica | Dirección |
|---|---|---|
| **Objetivo** | `deteccion`: de los casos con un anacronismo sembrado, fracción en los que la nota de `anacronismos` queda por debajo de `gate.nota_minima` —es decir, con la que el gate bloquea— | **sube** |
| Guardia | `falsos_positivos`: de los casos limpios, fracción con la nota por debajo de `gate.nota_minima` | no sube |
| Guardia | `notas_hermanas`: media de `continuidad` y `logica_ritmo` sobre los casos limpios | no baja |
| Guardia | `forma`: fracción de respuestas que cumplen lo que VD-10 exige —un bloque, de la dimensión pedida, con nota entera de 1 a 5— | no baja |
| Guardia | `coste_llamada`: coste medio de una llamada al validador | no sube |

Las dos guardias del medio existen por un motivo concreto: las tres dimensiones
comparten `agentes/validador.md`, así que un prompt que mejora los anacronismos
puede estropear las otras dos, y un validador más suspicaz tumba capítulos
buenos, que es más coste por el camino de los reintentos. **Los valores que cada
guardia tiene que respetar no se escriben aquí a mano**: salen de la medición
del paso 3 y quedan en la sección de la vuelta.

## §4 Los cinco campos

Un loop son cinco campos rellenados con valores concretos. Sin los cinco no se
arranca.

| Campo | Valor |
|---|---|
| **TRIGGER** | `/afinar-validador` en una sesión de Claude Code abierta en el repositorio, y automáticamente cuando la skill de orquestación pasa una novela a `editado`, que es cuando hay capítulos nuevos de los que sacar casos |
| **GOAL** | Una vuelta está hecha cuando dice un número sobre la partición de reserva: o promueve un candidato porque su `deteccion` supera a la del vigente por más que el ruido, con las cinco guardias intactas; o lo rechaza y deja escrito por cuánto se quedó corto. **Rechazar es terminar bien** |
| **VERIFY** | Código sobre la salida, sin juez y sin ojo: `nota < gate.nota_minima`, con el umbral leído de `config.json`. El texto de las incidencias se guarda y no se puntúa |
| **STOP** | Cualquiera de cuatro: se agotan `afinado.max_candidatos`; `afinado.fallos_seguidos` candidatos seguidos no baten el ruido; una guardia empeora; o el gasto de la vuelta pasa de `afinado.tope_gasto` |
| **MEMORY** | Tres sitios: el prompt promovido en `agentes/validador.md`, en un commit propio; las medidas en Langfuse, como una ejecución de dataset con una puntuación por caso; y lo aprendido, en una sección nueva de este documento, con los números generados y sin una palabra de los casos |

## §5 Los casos, y por qué no están aquí

Un caso es lo que el validador recibe en una novela: el capítulo, el dossier de
época y el encargo del capítulo. Vienen en pares construidos sobre capítulos ya
aprobados:

| Variante | Qué es | Qué se espera |
|---|---|---|
| `limpio` | El capítulo tal como se aprobó | Que la nota **no** baje del suelo del gate |
| `sembrado` | El mismo capítulo con **un** anacronismo metido a mano en una frase | Que la nota **sí** baje del suelo del gate |

**Los casos no viven en este repositorio y no van a vivir aquí.** Viven en dos
datasets de Langfuse, `afinado-anacronismos-taller` y
`afinado-anacronismos-reserva`. El motivo es el mismo por el que las rúbricas de
los jueces tampoco están versionadas (`SPEC.md` §20): el validador es un
subagente con herramienta `Read` sobre el proyecto, y un examinado que puede
leer el examen escribe para el examen. Quien propone prompts nuevos ve **solo el
taller**; la decisión de promover se toma **solo contra la reserva**, que no se
le enseña nunca.

Mientras una vuelta corre, los casos se escriben en una carpeta temporal fuera
del repositorio y se borran al cerrarla.

**Crecer no cuesta lo mismo en las dos variantes**: cada capítulo nuevo aprobado
es un caso limpio sin trabajo ninguno, y cada caso sembrado hay que escribirlo.
Es trabajo de autoría, se hace una vez y no se repite; no es mantenimiento.

## §6 Cómo se puntúa

El validador se llama **como se llama en producción**: el subagente
`novela-validador-anacronismos`, con su frontmatter, sus herramientas y el
system prompt de Claude Code. No hay réplica por API, porque una mejora medida
en otro arnés puede no aparecer donde el prompt corre de verdad.

De su respuesta se toman dos cosas y solo dos: que la forma pase VD-10, y la
nota entera. El resto —las incidencias— se guarda para leerlo y **no entra en
ningún número**.

**Las llamadas de medición no son de ninguna novela.** Mientras hay una vuelta
abierta, el hook de `SPEC.md` §22 las manda al entorno `afinado.entorno` y a una
sesión propia de la vuelta, en lugar de colgarlas de la novela en curso. No es
una precaución teórica: el trabajo anterior metió 21 observaciones de prueba
dentro de la sesión de una novela real, y cualquiera que la consultara después
contaba el doble de llamadas de las que hubo.

## §7 El ruido, y de dónde sale el umbral

Antes de optimizar nada, el prompt vigente corre `afinado.pasadas` veces sobre
los mismos casos. De ahí salen dos números, y los dos hacen falta:

- **La línea base**: la `deteccion` media del vigente.
- **El ruido**: cuánto se mueve esa cifra entre dos pasadas idénticas.

Un candidato se promueve solo si su mejora sobre la reserva supera
`ruido × afinado.factor_margen`. Con `factor_margen` en 1 basta con salir del
ruido; subirlo exige más evidencia y promueve menos veces. **El umbral no se
elige antes de medir el ruido**, que es el orden de §2.

## §8 Promover, y deshacerlo

Promover es escribir `agentes/<rol>.md` y commitearlo, **solo eso y en un commit
propio**, con el asunto en una forma fija: `feat(afinado): vuelta NN promueve el
prompt de <rol>`.

**Deshacer una promoción mala es `git revert` de ese commit.** Un comando, sin
carpetas de copias ni ficheros `.bak`: el prompt anterior está entero en el
historial y el commit no lleva nada más dentro. Por eso la promoción no comparte
commit con el spec ni con la sección de la vuelta, que van en los suyos.

## §9 Configuración

Seis claves nuevas en el `config.json` de `SPEC.md` §12, que pasa de diecisiete
a veintitrés. Ningún número de este documento vive en el código ni en un prompt.

| Clave | Por defecto | Para qué |
|---|---|---|
| `afinado.pasadas` | 3 | Veces que se corre cada caso con el mismo prompt (§7) |
| `afinado.factor_margen` | 1.0 | Cuántas veces el ruido tiene que superar la mejora para promover |
| `afinado.max_candidatos` | 3 | Candidatos que se prueban en una vuelta antes de parar |
| `afinado.fallos_seguidos` | 2 | Candidatos seguidos que no baten el ruido antes de parar |
| `afinado.tope_gasto` | 1.0 | Dólares que puede gastar una vuelta |
| `afinado.entorno` | `afinado` | Entorno de Langfuse al que van las llamadas de medición (§6) |

`pasadas` no puede bajar de 2: con una sola pasada no hay ruido que medir y el
loop se queda ciego. Y hay una regla cruzada, `afinado.entorno` distinto de
`trazas.entorno`: si las llamadas de medición cayeran en el entorno de las
novelas, el gasto de una vuelta se sumaría al de un libro y nadie lo notaría.

## §10 Lo que este diseño no tiene

Conviene tenerlo escrito, porque es el precio:

- **No propone prompts solo.** Quien escribe el candidato es el modelo de la
  sesión, con el taller delante. Lo que es determinista es la medida y la
  decisión, no la idea.
- **Los casos sembrados los escribe una persona.** Nada comprueba que el
  anacronismo sembrado sea de verdad un anacronismo; si está mal sembrado, el
  caso mide otra cosa y no avisa.
- **Nueve capítulos aprobados no son un corpus.** El tamaño del conjunto es hoy
  el límite duro de lo que el loop puede distinguir, y crece a razón de un
  capítulo por capítulo escrito.
- **Una vuelta no es barata en tiempo.** Son decenas de llamadas a subagentes en
  serie y en paralelo, y el reloj lo marcan ellas.

## §11 Decisiones abiertas

Los ids no se reutilizan.

| Id | Decisión pendiente | Cuándo decidirla |
|---|---|---|
| AF-01 | Si el disparo automático al cerrar una novela debe pedir permiso o correr solo | Con el gasto de dos o tres vueltas medido |
| AF-02 | Si la métrica objetivo debe ser `deteccion` o la caída emparejada de la nota entre el caso limpio y el sembrado | Con el ruido de la vuelta 1 delante |
| AF-03 | Qué rol entra en el segundo loop. El cronista es el candidato: empata en coste por capítulo y emite 3.995 tokens de salida por resumen | Cuando el primero haya cerrado dos vueltas |
| AF-04 | Si las guardias deben poder vetar por sí solas o sumar en un único veredicto | Cuando una guardia impida una promoción que la métrica objetivo pedía |

## §12 Historial de cambios

Formato Keep a Changelog.

### [0.1.0] — 2026-09-18

**Añadido**
- §1–§11. El documento y el primer loop: el validador de anacronismos, sus cinco
  campos, los casos fuera del repositorio, el ruido como umbral y la promoción
  reversible con un commit.

## §13 Vueltas

Una por sección, numeradas a partir de §14. No se reescribe una anterior, por la
misma regla que las pasadas de `TRAZAS.md`.
