---
spec: 001
titulo: Verificación — qué método le toca a cada dimensión de calidad
version: 0.1.0
estado: aprobada
fecha: 2026-09-21
fuente: hoja de referencia externa de metodologías de verificación
  (https://claude.ai/artifact/Rass3RVfaN5KSJDdG2FQhR), aportada por el editor
---

# 001 · Verificación

## §1 Problema

`docs/validators.md` está vacío desde el arranque de la rama `v2`. Mientras
tanto, `definitions.md` enumera veinte dimensiones de calidad y
`architecture.md` §5 describe el contrato de verificación en abstracto, pero
**ningún documento dice qué método le toca a cada dimensión, qué agente la
comprueba, con qué proyección ni qué se hace con las que no admiten
comprobación**. Quien implemente el bucle de calidad tiene que reinventar ese
reparto, y «coherencia de voz» acabaría tratada igual que «continuidad de
estado» cuando no son la misma clase de problema: una se puntúa, la otra se
comprueba.

Falta además el eslabón de arriba. Nada dice **cómo se comprueba que los
verificadores funcionan**. Un sistema que se valida a sí mismo sin medir su
propia tasa de acierto no es verificable: es optimista.

El interrogatorio previo lo delegó el editor: «lo que tú consideres a partir del
artifact». Las decisiones de §2 son, por tanto, propuesta del agente, y el
choque de §5 es el punto donde conviene que las mire.
