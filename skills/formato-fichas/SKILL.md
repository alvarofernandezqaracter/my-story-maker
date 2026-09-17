---
name: formato-fichas
description: Estructura de la escaleta, la ficha de capitulo y la ficha de personaje
usa: arquitecto, cronista
---

# Formato de fichas

La escaleta es el plan de la novela: un arco en tres actos y una ficha por
capitulo. Las fichas de personaje van al lado. Todo esto entra en el canon una
vez y el loop solo lo lee.

## Ficha de personaje

| Campo | Que va |
|---|---|
| `id` | Slug estable en minusculas. Se usa en referencias cruzadas de todo el sistema |
| `nombre` | |
| `rol` | `protagonista`, `secundario` o `figurante` |
| `voz` | Como habla: registro, muletillas, y que no diria nunca |
| `motivacion` | Que quiere y por que |
| `arco` | De donde parte y adonde llega |
| `ubicacion` | Donde esta ahora mismo en la trama |
| `sabe` | Lista de lo que conoce y lo que ignora |

El `id` no cambia jamas. Si cambia, todas las fichas de capitulo que apuntaban
al personaje quedan huerfanas y el orquestador rechaza la escaleta entera.

`voz` es el campo que mas trabaja. «Habla poco» no basta. Lo util es el
registro, dos o tres tics concretos y sobre todo el limite: que no diria nunca
ese personaje. Sin ese limite, todas las voces derivan al mismo neutro en cuanto
la novela avanza.

`sabe` se escribe en positivo y en negativo, porque la mitad de los fallos de
continuidad son de ignorancia: «Sabe que el contador falsifico el registro»,
«Ignora que su hermano lo sabia». Lo que un personaje ignora es informacion tan
dura como lo que sabe.

## Ficha de capitulo

| Campo | Que va |
|---|---|
| `numero` | Clave, correlativo desde 1 |
| `titulo` | |
| `acto` | 1, 2 o 3 |
| `sinopsis` | Que pasa, en tres o cuatro frases |
| `fecha` | ISO parcial: `1587`, `1587-04` o `1587-04-12` |
| `personajes` | Ids de quien sale |
| `etiquetas` | Terminos de epoca para cruzar con el dossier |
| `objetivo` | Que tiene que haber cambiado al acabar |
| `palabras_objetivo` | Heredado del brief salvo ajuste |

`fecha` y `etiquetas` son las dos que el generador de contexto necesita y las
dos que mas se olvidan. La `fecha`, junto con la del capitulo anterior, define
la ventana de la linea de tiempo que vera el escritor. Las `etiquetas` son lo
unico contra lo que se filtra el dossier. Sin ellas esos dos bloques del paquete
llegan vacios y el escritor escribe a ciegas sobre la epoca.

Las fechas avanzan con los capitulos. Si el capitulo 5 es anterior al 4, la
ventana de cronologia sale vacia y nadie avisa.

`objetivo` no es la sinopsis otra vez. La sinopsis dice que pasa; el objetivo
dice que ha cambiado cuando acaba. Es contra el objetivo contra lo que se juzga
la dimension de logica y ritmo.

## Cuando el cronista propone cambios

El cronista usa este mismo formato, pero solo puede tocar tres campos del
personaje: `ubicacion`, `sabe` y, de forma automatica, `actualizado_en`. La voz,
la motivacion y el arco son identidad y pertenecen a la parte inmutable del
canon: si el arco cambia, es que la escaleta cambio, y eso es una decision
humana, no una consecuencia de un capitulo.
