# El paquete de contexto

El paquete es **todo lo que el escritor va a ver del canon**. No tiene acceso a
nada mas, y esa restriccion es el motor de calidad del sistema entero: obliga a
que lo que el capitulo sabe sea exactamente lo que el canon guarda, y no lo que
se quedo flotando en una conversacion.

Lo armas tu, leyendo `<novela>/canon/`, y lo escribes en
`<novela>/contexto/cap-NN.md` antes de llamar al escritor.

## La regla que sostiene todo lo demas

**El texto completo de los capitulos anteriores no entra nunca en el paquete.**
Para eso estan los resumenes del cronista. La unica excepcion es el enganche: las
ultimas `contexto.palabras_enganche` palabras literales del capitulo anterior
aprobado, y nada mas.

Si metes el capitulo anterior entero «para que tenga contexto», has roto el
diseno: el paquete crece sin techo, el escritor imita en vez de continuar, y
dejas de saber si el resumen del cronista servia para algo.

## Determinismo

Mismo capitulo y mismo canon tienen que dar el mismo paquete. **No elijas tu que
es relevante.** Los filtros son mecanicos y estan escritos abajo: cruces de
etiquetas y rangos de fechas, no criterio literario. Si te pones a seleccionar a
ojo lo que crees que le hace falta al escritor, dos pasadas iguales dan paquetes
distintos y ya no se puede comparar nada.

El paquete **no se guarda como canon**: se reconstruye. Si cambia el canon,
cambia el paquete, y eso es correcto.

## Los nueve bloques, en este orden

Escribelos con estas cabeceras exactas, porque es lo que la skill
`skills/formato-paquete-contexto/SKILL.md` le dice al escritor que espere. **Un
bloque vacio se omite entero**, cabecera incluida.

### 1. `# Encargo del capitulo N`

La ficha entera del capitulo, de `escaleta.json`, en lista:

```
- Titulo: ...
- Acto: ...
- Fecha: ...
- Objetivo: ...
- Palabras objetivo: ...
- Sinopsis: ...
```

Nunca se recorta.

### 2. `# Personajes en escena`

Ficha completa de cada id que aparece en `personajes` de la ficha del capitulo.
Una subseccion por personaje:

```
## Nombre (id, rol)
- Voz: ...
- Motivacion: ...
- Arco: ...
- Donde esta: ...
- Que sabe: cosa | otra cosa
```

Si `sabe` esta vacio, pon `(sin anotar)`. Nunca se recorta.

### 3. `# Reparto de fondo`

Quien **no** sale en el capitulo pero cuyo nombre aparece mencionado en la
sinopsis. Una linea por cabeza, con la primera frase de su motivacion:

```
- Nombre (id): primera frase de su motivacion.
```

El criterio es literal: el nombre del personaje aparece en el texto de la
sinopsis. No lo amplies por parecido ni por parentesco.

### 4. `# Memoria reciente`

Los resumenes **completos** de los ultimos `contexto.ventana_resumenes`
capitulos aprobados anteriores a N. Con el valor por defecto de 3 y estando en el
capitulo 7, son el 4, el 5 y el 6.

```
## Capitulo 4
El resumen entero, tal cual lo escribio el cronista.
```

### 5. `# Memoria larga`

Todos los capitulos aprobados **anteriores** a esa ventana, recortados a la
**primera frase** de su resumen. Estando en el 7, son del 1 al 3.

```
- Cap. 1: Primera frase del resumen.
```

Primera frase significa hasta el primer punto, interrogacion o exclamacion
incluidos. No la reescribas ni la resumas tu: cortala.

### 6. `# Hilos vivos`

Los hilos de `hilos.json` con `cerrado_en: null`, todos.

```
- (abierto en cap. 3) el aval del gremio sigue sin firmarse
```

Nunca se recorta. Es la deuda de la novela y es lo que el escritor necesita para
no dejar promesas colgando.

### 7. `# Epoca`

Los datos de `dossier.json` que compartan **al menos una etiqueta** con las
`etiquetas` de la ficha del capitulo, comparando en minusculas.

Ordenados por estado —primero `verificado`, luego `sin_verificar`, luego
`inventado`— y dentro de cada grupo por `id` alfabetico.

```
- [verificado] (politica) La afirmacion concreta. — fuente: nombre de la fuente
```

El estado viaja siempre. El escritor decide que arriesga en la pagina segun lo
que este marcado como firme, asi que un dato sin su estado es peor que no darlo.

### 8. `# Cronologia`

Los eventos de `timeline.json` cuya fecha caiga **entre la fecha de la ficha del
capitulo anterior y la de este**, ambas incluidas. Para el capitulo 1 es todo lo
anterior a su fecha.

```
- 1587-04 (trama) Descripcion del evento.
```

Compara fechas normalizadas por texto (`1587`, `1587-04`, `1587-04-12`), que
ordenan bien alfabeticamente porque el formato es fijo.

### 9. `# Enganche con el capitulo anterior`

Las ultimas `contexto.palabras_enganche` palabras literales del capitulo anterior
**aprobado**. Sacalas con el comando, no a ojo:

```bash
tr -s '[:space:]' '\n' < <novela>/capitulos/cap-06-intento-2.md | tail -400 | tr '\n' ' '
```

Cambia el `400` por el valor real de `config.json`. Va citado:

```
> ...las ultimas cuatrocientas palabras tal cual.
```

Si no hay capitulo anterior aprobado, el bloque no existe.

## El recorte, si el paquete se pasa del tope

El tope es `contexto.tope_contexto` **tokens**, estimados como el numero de
caracteres del paquete dividido entre 4, redondeando hacia arriba. Cuentalos con:

```bash
wc -c < <novela>/contexto/cap-07.md
```

Si te pasas, recorta quitando elementos **por el final** de cada bloque, y en
este orden estricto:

1. `memoria_larga`
2. `cronologia`
3. `reparto_fondo`
4. `epoca`

Vacia uno entero antes de pasar al siguiente, y para en cuanto quepa.

**El encargo, los personajes en escena y los hilos vivos no se recortan nunca.**
Si con los cuatro bloques recortables vacios el paquete sigue sin caber, **no
escribas el capitulo con el contexto mutilado**: marca el capitulo y el proyecto
como `bloqueado` y para. Un capitulo escrito sin sus personajes o sin su encargo
no es un capitulo mediocre, es basura que ademas envenena a los siguientes.

Anota en `estado.json` que bloques se recortaron. Un capitulo que sale raro se
explica casi siempre ahi.
