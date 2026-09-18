# Las comprobaciones y el gate

Aqui no hay criterio literario. Son reglas que se cumplen o no se cumplen, y tu
las aplicas igual esten como esten las notas o lo bien que te haya parecido el
capitulo.

Dos severidades. **Bloqueante**: el artefacto no se usa y se reintenta. **Aviso**:
se registra, viaja al reintento como incidencia y el proceso sigue.

Todos los numeros salen de `config.json`. Los de los ejemplos son los que trae el
fichero por defecto; **lee el tuyo** antes de aplicar nada.

## La politica de reintento, que es comun a todo

Un artefacto que falla una comprobacion bloqueante se pide **una segunda vez**,
diciendole al subagente exactamente que fallo. Si falla la segunda, **para el
proceso** y deja escrito el motivo en `estado.json`.

No hay tercera, no hay espera creciente y no hay «una mas por si acaso». Si dos
intentos con el fallo delante no lo arreglan, el problema no es de suerte y
seguir pidiendo solo gasta dinero.

## VD-01 y VD-02 — forma y obligatorios

La salida parsea como un unico objeto JSON, y trae todos sus campos obligatorios
no vacios. Los contratos de cada rol estan en los propios ficheros de
`.claude/agents/novela-*.md`.

Los enumerados son cerrados y no admiten sinonimos:

| Campo | Valores |
|---|---|
| `categoria` (dato) | `vestimenta`, `politica`, `comida`, `lenguaje`, `otro` |
| `estado` (dato) | `verificado`, `sin_verificar`, `inventado` |
| `rol` (personaje) | `protagonista`, `secundario`, `figurante` |
| `dimension` | `continuidad`, `anacronismos`, `logica_ritmo` |
| `severidad` | `grave`, `aviso` |
| `tipo` (evento) | `trama`, `historico` |
| `tipo` (retoque) | `arco`, `promesa`, `ritmo`, `personaje` |

Bloqueante las dos.

## VD-03 — los ids existen

Todo id referenciado existe ya en el canon.

En el **arquitecto**, cada id de `capitulos[].personajes` tiene que estar en los
`personajes[]` que el mismo propone. En el **cronista**, cada id de
`personajes_presentes`, de `cambios_personaje` y de `eventos[].personajes` tiene
que estar ya en `personajes.json`, y cada `dato_id` en `dossier.json`.

Bloqueante.

## VD-04 — el dossier lleva fuente y estado

Cada dato tiene `fuente` no vacia y un `estado` de los tres validos. Y la regla
que mas se incumple:

**Un dato con `estado: "verificado"` no puede tener `fuente: "modelo"`.**

Es la unica defensa del sistema contra la fuente inventada con aspecto creible.
Un modelo recordando algo no es una fuente, por seguro que suene. Bloqueante.

## VD-05 — eventos

Un evento de tipo `trama` **lleva** `capitulo`. Uno de tipo `historico` **no lo
lleva**. Excluyente en los dos sentidos. Bloqueante.

## VD-06 — resumen solo si hay aprobado

No entra ningun resumen en el canon si el capitulo no tiene un intento aprobado.
Esto te protege de ti mismo: si alguna vez te ves llamando al cronista antes del
gate, para. Bloqueante.

## VD-07 — numero de capitulos

La escaleta trae un numero de capitulos dentro del margen del brief:

```
minimo = floor(pedidos * margenes.capitulos_min)     0.8 por defecto
maximo = ceil (pedidos * margenes.capitulos_max)     1.2 por defecto
```

Para 6 capitulos pedidos: entre 4 y 8. Bloqueante.

## VD-08 — extension del capitulo, la unica de dos escalones

Corre **antes** que los validadores. Esa es toda su razon de ser: si el capitulo
no cumple lo basico, se reintenta sin gastar las tres llamadas.

Cuenta con comandos, nunca a ojo:

```bash
wc -w < <novela>/capitulos/cap-01-intento-1.md
awk 'BEGIN { RS = ""; n = 0 } !/^#{1,6}[ \t]/ { n++ } END { print n }' <novela>/capitulos/cap-01-intento-1.md
```

El primero da las palabras. El segundo da los parrafos, contando bloques
separados por linea en blanco y sin contar los encabezados.

Despues:

```
desvio = |palabras - palabras_objetivo| / palabras_objetivo
```

| Condicion | Escalon |
|---|---|
| parrafos < `margenes.parrafos_min` (3) | **bloqueo** |
| desvio > `margenes.palabras_bloqueo` (0.4) | **bloqueo** |
| desvio > `margenes.palabras_aviso` (0.15) | aviso |

**Bloqueo**: marca el intento `descartado` y vuelve al escritor **desde cero**.
No llames a los validadores.

**Aviso**: el texto vale. Sigue a los validadores y arrastra el aviso a las
incidencias del reintento si el gate acaba rechazando.

Ejemplo con objetivo 1800: 1500 palabras es desvio 0.17, aviso. 1000 palabras es
desvio 0.44, bloqueo.

## VD-09 — personajes presentes

`personajes_presentes` del cronista tiene que ser un **subconjunto** de los
`personajes` de la ficha del capitulo. Si alguien sale en el texto y no estaba en
la ficha, es un personaje colado y se rechaza la propuesta entera. Bloqueante.

## VD-10 — las tres dimensiones

Vuelven las tres dimensiones, **una vez cada una**, con nota **entera** de 1 a 5.
Ni falta ninguna, ni se repite ninguna, ni hay medias notas.

Si falla, relanza **al validador** que falte. No reintentes al escritor: el texto
no tiene la culpa de que una revision viniera mal. Bloqueante.

## VD-11 — nada pendiente al confirmar

Antes de escribir la propuesta del cronista en el canon, comprueba que ninguna
comprobacion bloqueante quedo sin resolver. Si queda alguna, **no escribas nada**.

## VD-12 — la retractacion casa literal

Cada cadena de `olvida`, dentro de un `cambios_personaje`, tiene que estar escrita
**tal cual** en el `sabe` que ese personaje tiene ahora mismo en
`personajes.json`. Comparas caracter a caracter, igual que al cerrar un hilo.

Si una no casa, **rechaza la propuesta entera** y devuelvesela al cronista con la
lista de las que no casan y el `sabe` actual delante. No busques el parecido mas
cercano: retirar del canon la linea equivocada es peor que no retirar ninguna,
porque nadie vuelve a mirarlo. Bloqueante.

`olvida` puede venir vacia o no venir. Lo que no puede es traer una linea que la
ficha no tiene.

## VD-13 — el retoque no cambia el canon

Solo en el tramo de cierre (§11), despues del gate del capitulo retocado. El
cronista vuelve a emitir el canon de ese capitulo sobre el texto nuevo, y tiene
que salir **igual** al que ya estaba guardado en:

- `resumenes/cap-NN.json`: los mismos `hilos_abiertos`, `hilos_cerrados` y
  `personajes_presentes`, como conjuntos.
- `timeline.json`: los mismos eventos de ese capitulo, por `id` y por `tipo`.
- `personajes.json`: los mismos `cambios_personaje`, por `id`, `ubicacion`, y las
  mismas lineas en `sabe` y en `olvida`.

El resumen en prosa **si puede cambiar**: es la redaccion de lo mismo. Lo que no
puede cambiar es ninguna de las listas de arriba.

Si cuadra, el texto retocado sustituye al intento aprobado y el resumen nuevo
sustituye al viejo. Si no cuadra, **descarta el texto retocado**, deja el capitulo
como estaba y devuelve el retoque al editor global. Bloqueante.

## El gate

Entra despues de VD-10 y solo con las tres revisiones validas delante.

```
notas   = [continuidad, anacronismos, logica_ritmo]
minima  = min(notas)
media   = sum(notas) / 3
graves  = numero de incidencias con severidad "grave", en cualquier dimension

aprueba = minima >= gate.nota_minima        (3 por defecto)
          y media >= gate.media_minima      (3.7 por defecto)
          y graves == 0
```

**Una sola incidencia grave veta el capitulo por si misma.** Un capitulo puede
sacar tres cuatros y caer por una contradiccion de canon, porque eso no se
arregla puntuando mas alto.

**No existe la nota global.** Siempre son tres numeros. Si un validador te
devuelve una nota global, ignorala.

Escribe la operacion entera en tu respuesta, asi:

```
notas 4 / 3 / 4 -> minima 3 (>= 3 OK), media 3.67 (< 3.7 FALLA), graves 0
veredicto: rechazado
```

Tres numeros y dos comparaciones. Hazlas explicitas siempre, tambien cuando el
resultado parezca obvio: es la unica parte de este sistema donde una decision
importante depende de que sumes bien, y escribirla es lo que hace que se pueda
revisar despues.

## Al agotar los intentos

Se conserva el intento de **mejor media** en estado `propuesto`, los demas pasan
a `descartado`, y el capitulo y el proyecto quedan `bloqueado`.

Si ningun intento llego a tener revisiones —porque todos cayeron por VD-08—, se
conserva el ultimo.

Y entonces paras. **No bajes el liston, no repuntues y no apruebes tu.** El
bloqueo es una de las dos intervenciones humanas previstas del sistema, no un
obstaculo que tengas que salvar.

## El orden de las incidencias en el reintento

Primero las `grave`, luego las `aviso`. Dentro de cada grupo, por el orden de las
dimensiones: `continuidad`, `anacronismos`, `logica_ritmo`.

El escritor arregla de arriba abajo y puede quedarse sin sitio, asi que lo que va
primero importa.
