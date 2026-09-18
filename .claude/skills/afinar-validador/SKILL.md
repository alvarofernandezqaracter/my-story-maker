---
name: afinar-validador
description: Mide el prompt del validador de anacronismos con casos sembrados y decide si un candidato lo sustituye. Usala cuando se pida afinar, medir o mejorar el prompt de un agente de este repositorio, o cerrar una vuelta de afinado.
---

# Afinar el prompt del validador

Esto es el loop de [`docs/spec/AFINADO.md`](../../../docs/spec/AFINADO.md).
**Leelo antes de nada**: aqui esta como se hace, alli esta por que.

**Tu papel.** Tu no puntuas. El numero lo calcula `python -m novela afinar
puntuar` y tu obedeces lo que salga, igual que el orquestador obedece al gate.
Lo unico que pones tu es el prompt candidato.

**La regla que mas se rompe.** Una mejora que no supera al ruido no es una
mejora: es azar. Si el comando dice NO PROMUEVE, se acabo la vuelta; no se
repite la medida a ver si sale mejor, porque repetir hasta que salga es
exactamente como se fabrica un resultado falso.

## Antes de gastar nada

1. Imprime el bloque `afinado` de `config.json` y obedecelo. Ningun numero de
   esta skill: los umbrales estan alli.
2. Comprueba que hay casos: `python -m novela afinar preparar`. Si no baja
   ninguno, no hay vuelta que correr y hay que sembrarlos primero.
3. **Avisa de lo que va a costar antes de lanzar**: casos x pasadas llamadas,
   su coste aproximado y su tiempo. No arranques sin decirlo.

## El tramo 1: medir el vigente

```bash
python -m novela afinar preparar --vuelta N
```

Abre la vuelta y deja los casos en una carpeta temporal **fuera del
repositorio**. A partir de ese momento las llamadas a subagentes no se cuelgan
de ninguna novela: van al entorno de afinado. Por eso la vuelta se cierra
siempre, incluso si algo sale mal.

Para cada caso y cada pasada, lanza el subagente `novela-validador-anacronismos`
**tal como se lanza en una novela**: tres a la vez como mucho, con este encargo
y nada mas.

```
Juzga la dimension `anacronismos` del capitulo que hay en
<carpeta>/casos/<caso>/capitulo.md, contra el paquete de contexto que hay en
<carpeta>/casos/<caso>/contexto.md. Devuelve tu unico objeto JSON y nada mas.
```

No le digas cual es el caso, ni de que novela sale, ni que esto es una
medicion. **No le adelantes que puede haber un anacronismo sembrado**: eso es
darle el examen.

Vuelca su respuesta literal, sin arreglarla ni reformatearla, en:

```
<carpeta>/respuestas/vigente/<caso>-p<pasada>.json
```

Si devolvio algo que no es JSON, guardalo igual. Una respuesta sin forma es un
dato —cuenta en la guardia `forma`— y arreglarla a mano es falsear la medida.

Cuando esten todas:

```bash
python -m novela afinar puntuar --vuelta N --prompts vigente
```

De aqui salen la linea base y el **ruido**. Enseñalos antes de seguir.

## El tramo 2: el candidato

Lee el prompt vigente, `agentes/validador.md`, y los casos **de la particion
taller y solo esa**. La reserva no se mira, no se lee y no se cita: es con lo
que se va a decidir si mejoraste, y verla la invalida.

Escribe **un** candidato en un fichero aparte, fuera de `agentes/`. Cambia una
cosa y explicala en una linea; un candidato que toca cinco cosas a la vez no
enseña cual funciono.

Para medirlo: sustituye temporalmente `agentes/validador.md` por el candidato,
repite el tramo 1 volcando en `respuestas/cand-1/`, y **devuelve el fichero a su
sitio en cuanto termines**, pase lo que pase. El prompt vigente no se queda
cambiado mientras se decide.

```bash
python -m novela afinar puntuar --vuelta N --prompts vigente,cand-1 --particion reserva
```

## El veredicto

Imprime la operacion entera que devuelve el comando, como el gate. Si dice
PROMUEVE:

```bash
python -m novela afinar promover --vuelta N --candidato <ruta>
```

Eso escribe el prompt y lo commitea **solo**, para que deshacerlo sea un
`git revert`. Di el sha y el comando de vuelta atras en tu resumen.

Si dice NO PROMUEVE, tambien esta hecha la vuelta: apunta por cuanto se quedo
corta.

## Cerrar

```bash
python -m novela afinar cerrar --vuelta N
```

Y escribe la seccion de la vuelta en `AFINADO.md`, numerada a partir de §14,
con los numeros que imprimio el comando y **sin una palabra de los casos**: ni
que se sembro, ni en que capitulo. Ese documento vive en el repositorio y el
examinado lo puede leer.

## Los cuatro frenos

Paras si se agotan los candidatos, si dos seguidos no baten el ruido, si una
guardia empeora **mas que su tolerancia** o si el gasto llega al tope. Los
numeros estan en `config.json` y ninguno se negocia a mitad de vuelta.

La tolerancia de una guardia no es indulgencia: es lo que esa guardia no sabe
distinguir con los casos que hay. Un falso positivo de doce capitulos limpios
mueve la guardia 0,083 y no hay manera de moverla menos, asi que exigirle cero
seria exigirle la perfeccion.
