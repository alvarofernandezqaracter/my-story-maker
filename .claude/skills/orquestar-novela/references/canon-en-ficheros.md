# El canon en ficheros

En el camino de Python el canon es una base SQLite con siete tablas. Aqui no hay
Python, asi que el canon son ficheros JSON bajo `novela-cc/canon/`. Cambia el
soporte, no el papel: **sigue siendo la unica fuente de verdad del proyecto**, y
sigue sin poder escribirlo nadie mas que el orquestador.

Todo va bajo `novela-cc/` a proposito. El camino de Python usa `canon.db`,
`capitulos/` y `retoques.md` en la raiz, asi que los dos pueden correr sobre el
mismo repositorio sin pisarse y se pueden comparar despues.

## El arbol

```
novela-cc/
  canon/
    estado.json         el estado del proyecto y de cada capitulo
    brief.json          los cinco campos, se escribe una vez y no se toca
    dossier.json        { "datos": [...] }              <- investigador
    personajes.json     { "personajes": [...] }         <- arquitecto, luego cronista
    escaleta.json       { "capitulos": [...] }          <- arquitecto
    hilos.json          { "hilos": [...] }              <- cronista
    timeline.json       { "eventos": [...] }            <- cronista
    resumenes/
      cap-01.json       la propuesta del cronista, entera
  contexto/
    cap-01.md           el paquete con el que se escribio, para poder auditarlo
  capitulos/
    cap-01-intento-1.md borradores, aprobados y descartados
  retoques.md           salida final del editor global
```

La columna de la derecha dice **de que rol sale** el contenido, no quien escribe
el fichero. Escribes tu, siempre.

## estado.json

Es el fichero que hace que esto sea reanudable. Escribelo en cuanto algo cambie,
no al final de la pasada.

```json
{
  "estado": "escribiendo",
  "actualizado": "2026-09-16T17:20:00",
  "capitulos": {
    "1": {
      "estado": "aprobado",
      "intento_aprobado": 2,
      "intentos": [
        { "intento": 1, "estado": "descartado", "palabras": 1740,
          "notas": { "continuidad": 3, "anacronismos": 4, "logica_ritmo": 3 },
          "media": 3.33, "aprueba": false,
          "motivos": ["media 3.33 por debajo de 3.7"] },
        { "intento": 2, "estado": "aprobado", "palabras": 1812,
          "notas": { "continuidad": 4, "anacronismos": 4, "logica_ritmo": 4 },
          "media": 4.0, "aprueba": true, "motivos": [] }
      ]
    },
    "2": { "estado": "pendiente", "intento_aprobado": null, "intentos": [] }
  }
}
```

`estado` del proyecto: `borrador`, `investigado`, `estructurado`, `escribiendo`,
`bloqueado`, `escrito`, `editado`.

`estado` de cada capitulo: `pendiente`, `en_curso`, `aprobado`, `bloqueado`.

`estado` de cada intento: `propuesto`, `aprobado`, `descartado`.

Guarda las notas y los motivos de **todos** los intentos, tambien de los que
fracasaron. Es lo unico que permite despues saber si el gate esta bien calibrado,
y si solo guardas el que aprobo te quedas sin la mitad de los datos.

## hilos.json

Un hilo es una promesa que la novela abre y tiene que saldar.

```json
{ "hilos": [
  { "hilo": "el aval del gremio sigue sin firmarse", "capitulo": 3, "cerrado_en": null },
  { "hilo": "quien falsifico el registro", "capitulo": 1, "cerrado_en": 6 }
] }
```

Cuando el cronista cierra un hilo, **casa la cadena literalmente** con la de
`hilos_abiertos` que hay guardada. Si el cronista parafrasea, no casa, y en vez
de arreglarselo tu por aproximacion, devuelvele la propuesta: un hilo cerrado a
ojo es un hilo que el editor global dara por saldado sin estarlo.

Los **hilos vivos** son los que tienen `cerrado_en: null`. Son la deuda de la
novela y entran enteros en cada paquete de contexto.

## personajes.json y los cambios de ficha

El arquitecto lo escribe una vez. Despues, **solo el cronista lo modifica**, y
solo en dos campos: `ubicacion` y `sabe`. El resto de la ficha (`id`, `nombre`,
`rol`, `voz`, `motivacion`, `arco`) es del arquitecto y no se toca en el loop.

`sabe` es acumulativo: lo que el cronista devuelve se anade a lo que ya habia, no
lo sustituye. Un personaje no desaprende.

El `id` no cambia jamas. Si cambiara, todas las fichas de capitulo que apuntaban
a el quedarian huerfanas.

## Como se escribe, en la practica

Escribe JSON con sangrado de dos espacios y con los acentos tal cual, no
escapados: estos ficheros se leen a mano para depurar y `é` no se lee.

Y antes de sobrescribir cualquier fichero del canon, **leelo**. Nunca lo
reconstruyas de memoria a partir de lo que creas recordar de la conversacion: el
fichero es la verdad y tu contexto es una copia que puede estar vieja o haberse
compactado.
