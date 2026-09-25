# Guardarraíles y hooks

**La idea.** Un guardarraíl es una regla que el agente no puede saltarse,
aunque quiera. Una instrucción en el prompt no lo es: es una petición.

**Cómo se aplica aquí.** Tres capas, de fuera a dentro:

- **Permisos.** Cada subagente arranca solo con las herramientas de su
  contrato, y la tabla de gobierno decide qué puede guardar cada rol.
- **Hooks `Stop`.** Un pequeño programa que Claude Code lanza cuando el agente
  va a dar su trabajo por terminado. `validar_capitulo` mira la forma y los
  nombres de la biblia; `policy`, que no haya nada vetado. Si falla, el agente
  no puede terminar: recibe el motivo y corrige en la misma sesión.
- **La puerta de publicación.** Cinco validadores deterministas antes de
  publicar una versión.

**Ejemplo.** Un Redactor real escribió «alguacil», vetado en el brief; el hook
no le dejó terminar, reescribió con «soldado» y pasó.

**El límite.** Se compara por palabras normalizadas: el mismo tema dicho con
otras palabras, o una palabra con espacios entre las letras, pasa. Está
declarado en el [`red-team-log.md`](../red-team-log.md).

*Más:* [`trade-offs.md`](../trade-offs.md) §7 y §12.
