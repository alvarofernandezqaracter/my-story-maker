# Desarrollo guiado por especificación

**La idea.** Cuando quien escribe el código es un agente, lo que decide si
acierta es lo bien que esté escrito lo que se le pide. Una spec fija el qué y
el porqué antes del cómo, y deja constancia de las alternativas descartadas.

**Cómo se aplica aquí.** El sistema se construyó en un ciclo de tres fases:
spec, código y documentación, en ese orden. Cada decisión lleva un
identificador (`D-nn`) con su porqué, y cada requisito su método de
verificación. `AGENTS.md` y `CLAUDE.md` le dicen al agente de desarrollo las
reglas que no se rompen, y un subagente `verificador` distinto comprueba lo
entregado: quien escribió no se valida a sí mismo, tampoco en el desarrollo.

**Ejemplo.** La primera spec fijó siete objetivos medibles con la línea base
«pendiente de medir» en vez de inventarla: no había código con qué medir.

**El límite.** Recorrer el ciclo entero en cada cambio es lento; para cambios
pequeños y ya decididos, pesa más de lo que aporta.

*Más:* [`spec-inicial.md`](../spec-inicial.md).
