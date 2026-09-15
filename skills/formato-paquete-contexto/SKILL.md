---
name: formato-paquete-contexto
description: Como se serializa y en que orden se presenta el paquete de contexto
usa: escritor
---

# Formato del paquete de contexto

El paquete es todo lo que vas a ver del canon. Lo arma codigo, siempre en el
mismo orden y con las mismas cabeceras. No pidas mas contexto y no supongas que
existe algo que no esta aqui: no hay canal de vuelta.

## Orden de los bloques

1. `# Encargo del capitulo N` — la ficha entera: titulo, acto, fecha, objetivo,
   palabras objetivo y sinopsis. Nunca se recorta.
2. `# Personajes en escena` — ficha completa de quien sale. Nunca se recorta.
3. `# Reparto de fondo` — nombre y una linea de quien se menciona pero no sale.
4. `# Memoria reciente` — resumenes completos de los ultimos capitulos.
5. `# Memoria larga` — el resto de capitulos, recortados a una frase.
6. `# Hilos vivos` — promesas abiertas y aun no cerradas. Nunca se recorta.
7. `# Epoca` — datos del dossier que casan con las etiquetas del capitulo.
8. `# Cronologia` — eventos entre la fecha del capitulo anterior y la de este.
9. `# Enganche con el capitulo anterior` — la cola literal del capitulo previo.

Si falta un bloque es que esta vacio, no que se haya perdido. Un `# Epoca`
ausente significa que no hay datos etiquetados para este capitulo, y entonces
apoyas la epoca en lo que ya sepas sin inventar hechos concretos, y anotas en
`faltantes` lo que te habria hecho falta.

## Como leer cada bloque

**Encargo.** El `objetivo` es el contrato. Un capitulo que cumple la sinopsis
pero no el objetivo se suspende en logica y ritmo.

**Personajes.** El campo `Que sabe` manda sobre lo que un personaje puede decir
o deducir en esta escena. Si alguien sabe algo que segun su ficha ignora, eso es
un fallo de continuidad y es de los graves.

**Hilos vivos.** Son promesas hechas al lector que siguen sin saldar. No tienes
que cerrarlos todos, pero no los contradigas ni los olvides: si tu capitulo
cierra uno, que se note en el texto.

**Epoca.** Cada dato lleva su estado delante, entre corchetes. `[verificado]`
es firme y puedes apoyar trama en ello. `[sin_verificar]` sostiene una escena
pero no la protagoniza. `[inventado]` es relleno de fondo: usalo como textura y
no lo conviertas en punto de giro.

**Enganche.** Son las ultimas palabras literales del capitulo anterior, y estan
para continuidad de tono y de escena. No las repitas ni las parafrasees al
abrir: arranca despues de ellas.

## Recortes

Cuando el paquete no cabe, el codigo recorta en este orden: memoria larga,
cronologia, reparto de fondo, epoca. El encargo, los personajes y los hilos
vivos no se recortan nunca. Asi que un paquete escueto no significa que la
novela sea escueta; significa que el capitulo es tardio y hay mucho detras.
