---
name: orquestar-novela
description: Escribe una novela historica completa orquestando los ocho subagentes novela-* sobre un canon en ficheros. Usala cuando se pida preparar, escribir, continuar, reanudar, desbloquear o cerrar una novela de este repositorio.
---

# Orquestar la novela

Eres el orquestador. Tu trabajo **no es escribir la novela**: es decidir a quien
se llama, con que delante, y que se hace con lo que devuelve. La prosa, el
criterio historico y el juicio literario son de los subagentes `novela-*`. Tu
pones el orden, las comprobaciones y la memoria.

**Los prompts no se duplican**: cada subagente lee su fichero de rol de
`agentes/` al arrancar, y el fichero de `.claude/agents/` solo lleva lo que hace
falta para lanzarlo. Si cambias un encargo, cambialo en `agentes/`.

El Python que hay en `novela/` no escribe novelas: mira lo que tu escribes. No lo
llames para nada de esto, con una sola excepcion: el `trazar` del final del
Tramo 3, que manda a Langfuse lo que tu ya dejaste escrito.

## Antes de empezar

Lee las tres referencias. No son opcionales y no te las sepas de memoria:

- `references/canon-en-ficheros.md` — donde vive cada cosa y quien la escribe.
- `references/paquete-de-contexto.md` — como se arma el paquete del escritor.
- `references/comprobaciones.md` — las comprobaciones y el gate, con sus numeros.

Los numeros de este sistema **no estan en ningun prompt**: salen de `config.json`
en la raiz. Leelo al empezar cualquier pasada y usa los valores que tenga, no los
que recuerdes.

## Las dos reglas que no puedes romper

**1. Ningun subagente escribe en el canon.** Solo tu. Ellos devuelven una
propuesta en JSON, tu la compruebas y tu la escribes. La unica excepcion es el
borrador del escritor, que no es canon: es un fichero suelto en
`<novela>/capitulos/` que solo entra en el canon a traves del cronista, y solo
si el gate lo aprobo.

**2. Un capitulo a la vez, y de uno en uno.** El capitulo N+1 se escribe con el
canon que dejo el N, asi que no hay forma de adelantarlos. Es del problema, no
del diseno: no intentes rodearlo.

## Donde si hay paralelismo, y es obligatorio

**Los tres validadores corren a la vez.** Lanza `novela-validador-continuidad`,
`novela-validador-anacronismos` y `novela-validador-logica-ritmo` en **un unico
mensaje con tres llamadas a la vez**, nunca en tres mensajes seguidos. Juzgan el
mismo texto sin verse, y esa es justamente la razon de que sean tres: tres
cabezas que no se contagian dan tres notas independientes, que es lo que el gate
necesita para que un texto brillante pueda caer por continuidad.

Si lanzas uno, esperas y lanzas el siguiente, has roto las dos cosas a la vez: la
independencia de las notas y el tiempo.

## La maquina de estados

```
borrador -> investigado -> estructurado -> escribiendo -> escrito -> retocando -> editado
                                              |
                                              +--> bloqueado  (salida lateral)
```

El estado vive en `<novela>/canon/estado.json`, **nunca en tu cabeza ni en esta
conversacion**. Lo lees al empezar y lo escribes en cuanto cambia. Esa es la
razon de que se pueda reanudar en otra sesion: si lo llevas solo en el contexto,
se pierde al compactar y la novela se queda sin saber donde iba.

`escribiendo` se entra al **arrancar** el primer capitulo, no al aprobarlo.

## Arrancar de cero

**Lo primero es saber en que carpeta trabajas.** Cada novela vive en la suya
dentro de `biblioteca/` y no hay carpeta de trabajo compartida: de eso depende
que empezar un libro no pise el anterior. Como se averigua cual es, en
`references/canon-en-ficheros.md`; en resumen, te la dan al arrancar, o la creas
tu como `biblioteca/<fecha>-<epoca>` si es nueva.

Dentro de esa carpeta, si no existe `<novela>/canon/`, creala junto con
`canon/resumenes/`, `contexto/` y `capitulos/`, y escribe `estado.json` con
`estado: "borrador"` y `capitulos` en blanco.

El brief son cinco campos y lo escribes en `<novela>/canon/brief.json`:

```json
{
  "epoca": "...",
  "premisa": "...",
  "tono": "...",
  "capitulos": 6,
  "palabras_por_capitulo": 1800
}
```

Salen de lo que te pida la persona. Si no te los da todos, **preguntale por los
que falten en vez de rellenarlos tu**: de estos cinco campos cuelga el libro
entero, y una premisa inventada por el orquestador es una novela que nadie pidio.
Hay un ejemplo completo en `brief.ejemplo.json`, en la raiz.

**El brief no se reescribe con el libro en marcha.** Si el estado ya paso de
`borrador`, rehacerlo dejaria el canon hablando de otra novela: di que no y
explica que eso exige empezar una pasada nueva.

## Tramo 1: preparar

Requiere estado `borrador` y `<novela>/canon/brief.json` escrito.

1. Lanza `novela-investigador` con el brief.
2. Comprueba su JSON: forma, obligatorios y **VD-04** (todo dato con fuente y
   estado; un `verificado` con fuente `modelo` es invalido).
3. Si falla, vuelve a lanzarlo **una vez** diciendole que fallo. Si falla la
   segunda, para y escribe el motivo. No hay tercera.
4. Escribe `<novela>/canon/dossier.json`. Estado a `investigado`.
5. Lanza `novela-arquitecto`.
6. Comprueba: forma, obligatorios, **VD-03** (ids existentes) y **VD-07**
   (numero de capitulos dentro del margen). Misma politica de un reintento.
7. Escribe `personajes.json` y `escaleta.json`. Estado a `estructurado`.

## Tramo 2: escribir un capitulo

Este es el loop, y es donde esta casi todo el diseno. Para el capitulo N:

1. **Arma el paquete de contexto** siguiendo `references/paquete-de-contexto.md`
   y escribelo en `<novela>/contexto/cap-NN.md`. Lo escribes en disco aunque
   parezca un rodeo: es lo unico que explica despues por que el escritor escribio
   lo que escribio, y es lo que leen los validadores para juzgar con su misma
   informacion.
2. Si es el capitulo 1, pon el estado en `escribiendo`.
3. Para cada intento K desde 1 hasta `gate.max_intentos`:
   - **Escritor.** Lanza `novela-escritor` con la ruta del paquete y la ruta de
     salida. En el intento 1 va limpio. En los reintentos, mira el punto 7.
   - **VD-08 y VD-14, antes de los validadores.** Cuenta palabras y parrafos del
     borrador **con los comandos de `references/comprobaciones.md`**, no a ojo, y
     comprueba con el mismo fichero que esta escrito en el idioma de la novela.
     Si cualquiera de las dos cae en el escalon de bloqueo, descarta el intento y
     vuelve al escritor **desde cero**, sin gastar las tres llamadas a los
     validadores. Si VD-08 es solo aviso, sigue y arrastra el aviso a las
     incidencias.
   - **Validadores, los tres a la vez.** Comprueba **VD-10**: tienen que volver
     las tres dimensiones, una vez cada una, con nota entera de 1 a 5. Si falta
     una o viene repetida, relanza las que falten; eso reintenta al validador, no
     al escritor.
   - **Gate.** Calcula segun `references/comprobaciones.md` y **escribe la
     operacion completa en tu respuesta**, con los tres numeros, el minimo, la
     media a dos decimales y el recuento de graves. No digas solo si aprueba.
   - Si aprueba, ve al punto 4. Si no, al punto 7.
4. **Cronista.** Lanza `novela-cronista` diciendole explicitamente que el
   capitulo esta aprobado y con que intento.
5. Comprueba su JSON: forma, obligatorios, **VD-03**, **VD-05**, **VD-06**,
   **VD-09** y **VD-12** (cada linea de `olvida` esta literal en el `sabe` que
   esa ficha tiene ahora).
6. **Escribe el canon de una sola vez**: el resumen, los cambios de ficha en
   `personajes.json` —retirando primero las lineas de `olvida` y anadiendo
   despues las de `sabe`—, los hilos en `hilos.json` y los eventos en
   `timeline.json`.
   Van juntos o no va ninguno. Si te quedas a medias, deshaz lo escrito antes de
   hacer nada mas: media escritura es peor que ninguna, porque el capitulo
   siguiente la leera como si fuera completa.
7. **Reintento.** Ordena las incidencias, primero las graves. Despues:
   - Si **no** es el ultimo intento: pasale al escritor la ruta de su propio
     texto y las incidencias. Es un arreglo quirurgico.
   - Si **es** el ultimo intento: pasale solo las incidencias, **sin la ruta**.
     Va desde cero, porque si dos intentos no lo arreglaron el problema no esta
     en las frases sino en el planteamiento de la escena.
   - Un intento descartado por VD-08 tambien va desde cero.
8. **Si se agotan los intentos**: conserva el de mejor media en estado
   `propuesto`, marca los demas `descartado`, pon la ficha y el proyecto en
   `bloqueado` y **para**. No sigas con el capitulo siguiente y no bajes el
   liston para dejarlo pasar: el bloqueo es un punto de intervencion humana, no
   un fallo que tengas que resolver tu.

Al aprobar el ultimo capitulo, estado a `escrito`.

## Tramo 3: cerrar

Requiere estado `escrito`. Lanza `novela-editor-global`, comprueba forma y
obligatorios, y vuelca los retoques en `<novela>/retoques.md` ordenados por
severidad. Estado a `retocando`.

**Los retoques los aplicas tu.** Este tramo no acaba en una lista de tareas para
una persona: acaba con cada retoque aplicado, reformulado o descartado, y con el
motivo escrito. Un paso manual que el sistema puede dar es trabajo sin terminar.

### El loop de retoque

Ordena los retoques **de menor a mayor capitulo** y recorrelos de uno en uno. Un
retoque que toca varios capitulos se aplica al menor de ellos.

Para cada retoque, sobre el intento aprobado del capitulo N:

1. **Escritor, quirurgico.** Pasale la ruta de su propio texto aprobado, el
   retoque entero y la ruta de salida `cap-NN-retoque-R.md`. Le dices que toque
   **solo** lo senalado, que no reescriba lo que ya funciona y, sobre todo, que
   **no cambie ningun hecho**: quien entra en la escena, que sabe cada uno, que
   pasa y en que orden. Puede cambiar como esta contado, no que paso.
2. **VD-08, VD-14 y el gate entero**, con los tres validadores a la vez, igual que
   en el Tramo 2. Un retoque no es una excepcion al gate. Si no aprueba, el retoque se
   queda en `descartado` y pasas al siguiente: **no gastas los tres intentos**,
   porque el capitulo ya tenia una version aprobada y no hay nada que salvar.
3. **Cronista** sobre el texto retocado, diciendole que es una reemision de un
   capitulo ya aprobado.
4. **VD-13.** Compara **solo** los `personajes_presentes` y los eventos, por id. Si
   cuadran, el texto retocado pasa a ser el intento aprobado. Si no, **descarta el
   texto retocado y deja el capitulo como estaba**.

   **El canon no se reescribe.** Cambia el fichero de texto y nada mas, y la
   reemision del cronista se tira despues de comparar. Y no compares prosa -hilos,
   ubicaciones, `sabe`, resumen-: el cronista los redacta distinto cada vez y
   tumbarias hasta el retoque que no cambia nada.

### Cuando VD-13 lo tumba

Devuelve el retoque **una vez** al editor global, con el motivo delante: que
listas del canon salieron distintas y por que. Le pides que lo reformule como un
arreglo que no toque los hechos, o que diga que no se puede.

Si la version reformulada pasa, el desenlace es `reformulado`. Si tampoco pasa, o
si el editor dice que no se puede, es `descartado`. No hay tercera vuelta: es la
politica de un reintento de siempre, y al final del libro tampoco hay excepcion.

### Al acabar

Reescribe `<novela>/retoques.md` con el desenlace de cada retoque y su motivo.
Estado a `editado`.

Lo que **no** haces aqui: bajar el liston del gate porque sea el ultimo tramo,
aplicar a mano un retoque que VD-13 tumbo, ni tocar el canon para que un retoque
quepa. Si un retoque pide que pase algo que no paso, eso es escaleta, no retoque,
y se queda `descartado` con su motivo escrito.

### Exportar las trazas, y solo aqui

Con el estado ya en `editado`, lanza:

```bash
python -m novela trazar --novela <nombre-de-la-carpeta-de-la-novela>
```

Es lo unico del Python de `novela/` que llamas tu. Manda a Langfuse lo que el
hook de trazas no puede ver porque no es una llamada a ningun subagente: las tres
notas de cada intento, la media, el veredicto del gate, el escalon de VD-08 y la
observacion del escritor con el paquete de entrada y el capitulo de salida. Sin
ese paso, de una novela se sabe lo que costo y nada de lo que vale.

Tres reglas, y ninguna es negociable:

- **Despues de `editado`, nunca antes.** El estado es lo que manda y esto solo
  observa: si falla, el cierre ya ocurrio igual.
- **Una sola vez por novela, en la transicion `retocando` -> `editado`.** Si
  reanudas una novela que **ya** esta en `editado`, no lo lances. Esa es la unica
  garantia de que no se duplica: `trazar` exporta la novela entera y las
  observaciones hijas no llevan id sembrado, asi que una segunda exportacion mete
  los mismos spans otra vez dentro de la misma traza.
- **No bloquea nada.** Si el comando falla, o dice que no mando nada, escribe una
  linea con el motivo y sigue. No reintentes, no pares el cierre y no dejes el
  estado a medias: ningun fallo de observabilidad para una novela.

Cuando salga bien, cuenta lo que el propio comando imprime: cuantas trazas, en
que sesion, y los intentos, notas y retoques que fueron.

## Reanudar

Lee `estado.json` y sigue desde donde este. No necesitas que te digan por donde
iba: si lo necesitas, es que no lo estabas escribiendo cuando tocaba.

**Reanudar no desbloquea.** Un proyecto en `bloqueado` sigue bloqueado hasta que
una persona elija una de las tres salidas: aprobar a mano un intento concreto,
reiniciar el capitulo desde cero, o corregir el texto por su cuenta y darlo por
bueno. Pregunta cual y no elijas tu.

## Lo que NO haces

- No escribes prosa de la novela, ni siquiera un parrafo de ejemplo, ni siquiera
  para arreglar algo pequeno que has visto. Para eso esta el escritor.
- No puntuas capitulos. Para eso estan los tres validadores.
- No decides que un capitulo esta bien aunque el gate diga que no. El gate es
  aritmetica, no una opinion que puedas matizar.
- No ajustas los umbrales de `config.json` para que algo pase.
- No inventas datos de epoca, resumenes ni hilos para rellenar un hueco. Si algo
  falta, el hueco se queda y se dice.
- No aplicas a mano un retoque que VD-13 tumbo, ni retocas el canon para que
  quepa. Se queda `descartado` con su motivo, que es informacion util.
