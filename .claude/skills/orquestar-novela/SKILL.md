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
llames para nada de esto.

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
`novela-cc/capitulos/` que solo entra en el canon a traves del cronista, y solo
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
borrador -> investigado -> estructurado -> escribiendo -> escrito -> editado
                                              |
                                              +--> bloqueado  (salida lateral)
```

El estado vive en `novela-cc/canon/estado.json`, **nunca en tu cabeza ni en esta
conversacion**. Lo lees al empezar y lo escribes en cuanto cambia. Esa es la
razon de que se pueda reanudar en otra sesion: si lo llevas solo en el contexto,
se pierde al compactar y la novela se queda sin saber donde iba.

`escribiendo` se entra al **arrancar** el primer capitulo, no al aprobarlo.

## Arrancar de cero

Si no existe `novela-cc/canon/`, creala junto con `canon/resumenes/`, `contexto/`
y `capitulos/`, y escribe `estado.json` con `estado: "borrador"` y `capitulos` en
blanco.

El brief son cinco campos y lo escribes en `novela-cc/canon/brief.json`:

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

Requiere estado `borrador` y `novela-cc/canon/brief.json` escrito.

1. Lanza `novela-investigador` con el brief.
2. Comprueba su JSON: forma, obligatorios y **VD-04** (todo dato con fuente y
   estado; un `verificado` con fuente `modelo` es invalido).
3. Si falla, vuelve a lanzarlo **una vez** diciendole que fallo. Si falla la
   segunda, para y escribe el motivo. No hay tercera.
4. Escribe `novela-cc/canon/dossier.json`. Estado a `investigado`.
5. Lanza `novela-arquitecto`.
6. Comprueba: forma, obligatorios, **VD-03** (ids existentes) y **VD-07**
   (numero de capitulos dentro del margen). Misma politica de un reintento.
7. Escribe `personajes.json` y `escaleta.json`. Estado a `estructurado`.

## Tramo 2: escribir un capitulo

Este es el loop, y es donde esta casi todo el diseno. Para el capitulo N:

1. **Arma el paquete de contexto** siguiendo `references/paquete-de-contexto.md`
   y escribelo en `novela-cc/contexto/cap-NN.md`. Lo escribes en disco aunque
   parezca un rodeo: es lo unico que explica despues por que el escritor escribio
   lo que escribio, y es lo que leen los validadores para juzgar con su misma
   informacion.
2. Si es el capitulo 1, pon el estado en `escribiendo`.
3. Para cada intento K desde 1 hasta `gate.max_intentos`:
   - **Escritor.** Lanza `novela-escritor` con la ruta del paquete y la ruta de
     salida. En el intento 1 va limpio. En los reintentos, mira el punto 7.
   - **VD-08, antes de los validadores.** Cuenta palabras y parrafos del borrador
     **con el comando de `references/comprobaciones.md`**, no a ojo. Si cae en el
     escalon de bloqueo, descarta el intento y vuelve al escritor **desde cero**,
     sin gastar las tres llamadas a los validadores. Si solo es aviso, sigue y
     arrastra el aviso a las incidencias.
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
5. Comprueba su JSON: forma, obligatorios, **VD-03**, **VD-05**, **VD-06** y
   **VD-09**.
6. **Escribe el canon de una sola vez**: el resumen, los cambios de ficha en
   `personajes.json`, los hilos en `hilos.json` y los eventos en `timeline.json`.
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
obligatorios, y vuelca los retoques en `novela-cc/retoques.md` ordenados por
severidad. Estado a `editado`.

Los retoques **se aplican a mano**. No los apliques tu y no ofrezcas aplicarlos:
son el segundo punto fijo de intervencion humana del sistema.

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
