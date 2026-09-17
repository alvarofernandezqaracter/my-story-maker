---
name: analizar-trazas
description: Analiza las trazas de una novela ya escrita y saca en que se va el gasto, que funciona, que no y que se podria mejorar. Usala cuando se pida analizar trazas, mirar el coste o el rendimiento de una novela, o revisar Langfuse de este repositorio.
---

# Analizar las trazas de una novela

Esto no escribe novela: mira como se escribio. La pregunta no es por que un
capitulo salio asi -para eso esta la traza suelta- sino en que se va el gasto de
una novela entera, que roles cuestan, que capitulos se atascan y si lo caro es
ademas lo bueno.

**No hace falta ningun subagente.** El analisis es una conversacion: quien lo
pide va a repreguntar, y un subagente que devuelve su informe y se muere obliga
a empezar de cero en cada repregunta. Lo que si hace falta es que la pasada de
la novela 5 pregunte lo mismo que la de la novela 1, o las secciones de
`docs/spec/TRAZAS.md` no se podran comparar entre si. Ese guion es este fichero.

## 1. Los numeros los saca el codigo

```bash
python -m novela informe-trazas --salida informe.md      # o --json para el crudo
python -m novela informe-trazas --sesion novela-xxxxxxxx # otra novela
```

**No cuentes tu.** El informe agrega gasto por rol, por capitulo y por modelo,
el reparto de cache, las llamadas mas caras y mas lentas, y cruza el coste de
cada capitulo con sus notas y sus intentos. Tu trabajo empieza donde acaba esa
tabla. Si el informe no trae un numero, no te lo inventes: dilo y sigue.

Si una columna sale a cero, casi nunca es que no se mando, sino que no se pidio;
antes de concluir nada, mira `novela/informe.py`.

## 2. Las preguntas que se hacen siempre

En este orden, y todas, aunque alguna no de nada:

1. **Reparto del gasto.** Que rol se lleva la mayor parte y si eso es lo
   esperable por su trabajo. Tres validadores por intento pesan tres veces.
2. **Cache.** Que porcentaje de la entrada se leyo de cache. El paquete de
   contexto de §7 se reenvia entero en cada intento: si no se esta leyendo de
   cache, se esta pagando dos veces lo mismo.
3. **Modelos.** Que modelo resolvio cada rol de verdad, y si coincide con
   el frontmatter de cada subagente. El modelo lo decide el
   fichero del subagente, no `config.json`, y conviene mirar si divergen.
4. **Reintentos.** Cuanto costaron los capitulos que necesitaron dos intentos
   frente a los que salieron a la primera, y si el reintento quirurgico salio
   mas barato que el de cero.
5. **Crecimiento del contexto.** Como crece `contexto.tokens` capitulo a
   capitulo y a que ritmo se acerca a `contexto.tope_contexto`.
6. **Coste contra calidad.** Si los capitulos mas caros son los de mejor nota.
   Si no lo son, eso es un hallazgo.
7. **Los umbrales del gate.** Que margen real hubo entre las medias y
   `media_minima`. Es el dato que pide DA-06 para calibrar.
8. **Lo lento.** Que llamadas tardaron mas y si su duracion se explica por lo
   que tenian que hacer.

## 3. Los cuatro cubos

Todo hallazgo cae en uno de estos cuatro, y solo en uno:

- **En que se va el gasto.** Descriptivo, sin juicio.
- **Lo que ya funciona bien.** Se escribe siempre. Un informe que solo trae
  problemas no se puede usar para decidir que no tocar.
- **Lo que no termina de funcionar.**
- **Propuestas de mejora.** Cada una con lo que costaria y lo que ahorraria.

**Cada hallazgo cita su numero y de donde sale.** Un hallazgo sin evidencia no
se puede contrastar dentro de tres novelas, y este documento existe justamente
para leerse dentro de tres novelas. Si algo es una sospecha y no un dato, se
escribe como sospecha y se dice que haria falta para confirmarla.

## 4. Donde se escribe

En [`docs/spec/TRAZAS.md`](../../../docs/spec/TRAZAS.md), una seccion nueva por
pasada, con su fecha, su novela y su sesion. **No se reescribe una pasada
anterior**: la gracia es ver como evoluciona el sistema, y para eso hacen falta
las dos.

Y la regla que separa los dos documentos: **TRAZAS.md observa, no decide.**
Cuando un hallazgo se convierte en un cambio de diseno -bajar un umbral, partir
el paquete de contexto, cambiar el modelo de un rol- eso se muda a `SPEC.md`
como DA-xx o como cambio de seccion, y aqui queda la referencia cruzada. Si no
se respeta, en tres pasadas hay dos disenos que se contradicen.
