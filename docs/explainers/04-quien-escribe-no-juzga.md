# Quien escribe no juzga

**La idea.** Un modelo que revisa su propio texto tiende a darlo por bueno:
comparte los puntos ciegos que tenía al escribirlo. Separar al que genera del
que verifica es la forma más barata de fiabilidad.

**Cómo se aplica aquí.** Ningún agente valida su propia salida. El Redactor no
escribe críticas; el Verificador y el Juez de rúbrica no escriben borradores;
el Revisor aplica críticas ajenas y no puede crear las suyas. El único rol que
escribe y comprueba, el Editor de estilo, lo hace en dos pasos distintos del
guion. Y el juez de la novela entera corre con otro modelo, Sonnet, que el que
escribió, Haiku.

**Ejemplo.** Toda `Crítica` tiene que traer evidencia citable del texto; sin
ella se descarta. El Verificador no puede opinar: tiene que señalar.

**El límite.** Dos agentes pueden discrepar siempre en lo mismo. Quién arbitra
entonces sigue abierto ([`architecture.md`](../architecture.md) §8).

*Más:* [`validators.md`](../validators.md) §7.
