---
name: rubricas-validador
description: Las tres rubricas ancladas y el formato de los tres bloques
usa: validador
---

# Rubricas del validador

Tres rubricas, una por dimension, escala de 1 a 5 entera. Las anclas estan para
que la nota no derive a lo largo del libro: el capitulo 30 se puntua con la
misma vara que el 3.

## Continuidad

Coherencia con el canon: donde esta cada uno, que sabe cada uno, cuando pasa.

| Nota | Ancla |
|---|---|
| 1 | Contradice un hecho del canon |
| 2 | Varios detalles sin respaldo, o uno que empuja la trama |
| 3 | Detalle menor sin respaldo |
| 4 | Todo cuadra, pero el canon se usa de forma generica |
| 5 | Todo cuadra y usa el canon con precision |

Una elipsis no es un hueco. Si el capitulo salta tres dias y no cuenta que paso,
eso es una decision narrativa. El hueco de continuidad es que alguien sepa,
tenga o este donde su ficha dice que no.

## Anacronismos

Objetos, costumbres, instituciones y lexico frente al dossier.

| Nota | Ancla |
|---|---|
| 1 | Rompe un dato `verificado` |
| 2 | Varios choques con `sin_verificar`, o un concepto claramente fuera de epoca |
| 3 | Choca con un `sin_verificar` |
| 4 | Sin choques, pero la epoca se sostiene sobre decorado |
| 5 | Epoca sostenida sin adorno de folleto |

El anacronismo caro es el conceptual: una forma de pensar sobre el trabajo, la
familia o el mercado que pertenece a otro siglo. Salta menos que una palabra
moderna y hace mas dano. Al reves, no penalices un termino solo porque suene
actual: comprueba contra el dossier antes de llamarlo anacronismo.

## Logica y ritmo

Causa y efecto, cumplimiento del objetivo del capitulo, tension.

| Nota | Ancla |
|---|---|
| 1 | La escena no lleva a ninguna parte |
| 2 | Avanza por casualidad, o no toca el objetivo del encargo |
| 3 | Avanza pero se atasca o se salta un paso |
| 4 | Cumple el objetivo con algun tramo muerto |
| 5 | Cada escena empuja la siguiente |

El objetivo del encargo es el contrato: un capitulo bien escrito que no lo
cumple no pasa de 2 en esta dimension, por bien que este escrito.

## Formato de salida

```json
{
  "revisiones": [
    {
      "dimension": "continuidad",
      "nota": 4,
      "incidencias": [
        {
          "cita": "fragmento literal del capitulo",
          "severidad": "grave",
          "sugerencia": "Una linea sobre como arreglarlo."
        }
      ]
    }
  ]
}
```

Las tres dimensiones, una vez cada una, con `continuidad`, `anacronismos` y
`logica_ritmo` escritos asi. Nota entera de 1 a 5. Sin nota global. Un bloque
sin incidencias lleva la lista vacia, no se omite.

`grave` significa contradecir el canon o un dato `verificado`, y veta el
capitulo por si sola aunque las tres notas sean altas. Todo lo demas es `aviso`.
La cita es literal del capitulo: sin ella, el escritor no sabe donde tocar en el
reintento.
