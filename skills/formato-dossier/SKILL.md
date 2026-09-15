---
name: formato-dossier
description: Que es un dato de epoca bien escrito y como marcar fuente y estado
usa: investigador
---

# Formato del dossier

Un dato de epoca es la unidad minima del dossier: una afirmacion sobre la
epoca, con categoria, fuente y estado. Si no se puede meter en una escena, no
es un dato: es una generalidad.

## Que hace bueno a un dato

Concreto y comprobable. «La gente era religiosa» no vale. «Se oye misa antes
del amanecer y el gremio multa al que falta tres domingos seguidos» vale, porque
un escritor puede construir una escena con eso y un validador puede contrastar
un texto contra eso.

Una sola afirmacion por dato. Si tienes que usar «y ademas», son dos datos.

Escrito en presente y sin hedging. Nada de «es posible que», «probablemente» o
«segun algunas fuentes»: esa incertidumbre se expresa en el campo `estado`, no
en la prosa del dato. Un dato que se contradice a si mismo no sirve ni al
escritor ni al validador.

## Categorias

`vestimenta`, `politica`, `comida`, `lenguaje` y `otro`. Usa `otro` poco: si la
mitad del dossier cae ahi, el generador de contexto pierde capacidad de filtrar.

## Fuente y estado, que es lo que mas importa

| Estado | Cuando | Que va en `fuente` |
|---|---|---|
| `verificado` | Hay una fuente concreta que lo respalda | La URL o la referencia. Nunca `modelo` |
| `sin_verificar` | Lo recuerdas pero no puedes senalar de donde | `modelo` |
| `inventado` | Lo rellenas tu para tapar un hueco | `modelo` |

La distincion no es burocratica. El escritor decide cuanto peso narrativo pone
sobre cada dato segun su estado, y el validador solo considera grave romper un
dato `verificado`. Marcar `verificado` algo que solo recuerdas hace dos danos a
la vez: el escritor lo convierte en punto de trama y el validador bloquea
capitulos por contradecir algo que nunca fue cierto.

## Etiquetas

Son los terminos con los que el generador de contexto cruza este dato contra las
etiquetas de cada ficha de capitulo. Tres o cuatro por dato.

Piensa en escenas, no en taxonomia. Un dato sobre el precio del pan se etiqueta
`mercado`, `pobreza`, `comida`, no solo `comida`. Etiquetas demasiado genericas
hacen que el bloque de epoca del escritor se llene de ruido; demasiado
especificas hacen que no se seleccione nunca.
