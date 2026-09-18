# El canon en ficheros

## Que es `<novela>`

Cada novela vive en su propia carpeta dentro de `biblioteca/`, con un nombre
como `biblioteca/2026-09-18-sevilla-1587`. **No hay carpeta de trabajo fija.**
En estas paginas, `<novela>/` significa la carpeta de la novela que tienes entre
manos, y la sacas asi:

1. Si quien te arranco te dijo cual es -el mensaje de arranque la nombra antes
   que el brief-, esa y ninguna otra.
2. Si te piden reanudar, continuar o cerrar sin decirte cual, es la de
   `biblioteca/` cuyo `canon/estado.json` se escribio mas recientemente. Si hay
   varias a medias, **pregunta** en vez de elegir tu.
3. Si te piden una novela nueva y nadie te dio carpeta, creala tu:
   `biblioteca/<fecha de hoy>-<epoca en minusculas y con guiones>`, por ejemplo
   `biblioteca/2026-09-18-cadiz-1812`. Si ese nombre ya existe, no escribas
   dentro: anade `-2`.

**Nunca escribas en la carpeta de otra novela.** Es la unica forma de que
empezar un libro no se lleve por delante el anterior.

El canon son ficheros JSON bajo `<novela>/canon/`, uno por cada entidad de la
seccion 3 del spec. **Es la unica fuente de verdad del proyecto** y no puede
escribirlo nadie mas que tu.

Todo va bajo `<novela>/`, incluidos los borradores y los retoques. Es salida y
no se versiona: lo que se versiona es lo que la produce.

## El arbol

```
<novela>/
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
        { "intento": 1, "estado": "descartado",
          "ruta": "biblioteca/2026-09-18-cadiz-1812/capitulos/cap-01-intento-1.md",
          "palabras": 1740, "parrafos": 22, "vd08": "aviso",
          "notas": { "continuidad": 3, "anacronismos": 4, "logica_ritmo": 3 },
          "media": 3.33, "minima": 3, "graves": 0, "aprueba": false,
          "motivos": ["media 3.33 por debajo de 3.7"],
          "avisos": ["1740 palabras, por debajo del objetivo"],
          "tipo_reintento": null },
        { "intento": 2, "estado": "aprobado",
          "ruta": "biblioteca/2026-09-18-cadiz-1812/capitulos/cap-01-intento-2.md",
          "palabras": 1812, "parrafos": 24, "vd08": "ok",
          "notas": { "continuidad": 4, "anacronismos": 4, "logica_ritmo": 4 },
          "media": 4.0, "minima": 4, "graves": 0, "aprueba": true,
          "motivos": [], "avisos": [], "tipo_reintento": "quirurgico" }
      ]
    },
    "2": { "estado": "pendiente", "intento_aprobado": null, "intentos": [] }
  }
}
```

### Los campos de un intento, y ninguno sobra

**Escribelos todos, tambien en los intentos que fracasaron.** Cada uno lo lee
alguien despues, y el que falta no se nota hasta que se busca:

| Campo | Que es | Quien se queda sin nada si falta |
|---|---|---|
| `intento` | El numero de vuelta, desde 1 | Todo |
| `estado` | `propuesto`, `aprobado` o `descartado` | La interfaz y el cierre |
| `ruta` | **Donde dejo el fichero el escritor**, desde la raiz del repositorio | El juez externo: sin ella el capitulo no viaja a las trazas y no hay nada que puntuar |
| `palabras`, `parrafos` | Lo que conto VD-08 | VD-08 en la interfaz, y el aviso de extension |
| `vd08` | El escalon: `ok`, `aviso` o `bloqueo` | La puntuacion `vd-08` de las trazas |
| `notas` | Las tres dimensiones, en su orden | El gate y todas las metricas |
| `media`, `minima`, `graves` | Los tres numeros con los que salio la cuenta | La auditoria del gate: sin ellos no se puede rehacer la operacion |
| `aprueba` | El veredicto que escribiste | La auditoria, que compara tu veredicto con el suyo |
| `motivos` | Por que cayo, en frases cortas | Saber que hay que arreglar |
| `avisos` | Lo que no bloqueo pero se arrastro | El contexto del reintento |
| `tipo_reintento` | `quirurgico`, `desde_cero` o `null` en el primero | Medir si el reintento desde cero sirve de algo |

`ruta` es la que mas cuesta echar de menos y la mas facil de olvidar, porque el
fichero esta en disco y parece que con eso basta. No basta: quien lee el canon
despues no adivina el nombre, busca esta clave. **Escribela en cuanto el escritor
te devuelva su ruta**, en el mismo momento, y no al aprobar el capitulo: un
intento descartado tambien tiene que llevarla.

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
