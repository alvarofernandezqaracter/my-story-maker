# Ingeniería de contexto

**La idea.** Lo que un modelo hace depende de lo que tiene delante. Darle de
más no es gratis: ocupa sitio, cuesta dinero y le invita a opinar de lo que no
le toca. Diseñar qué entra en cada ventana pesa tanto como el prompt.

**Cómo se aplica aquí.**

- **Arranque en frío.** Ningún agente recuerda nada: cada tarea recibe todo lo
  que necesita y nada más, y muere al terminar.
- **Proyecciones por rol.** Cada rol tiene declarado qué materiales entran en
  su ventana. El caminante comprueba antes de mandar que no falte ninguno ni
  sobre ninguno.
- **Un techo de concurrencia.** En ningún instante la suma de lo que se manda a
  los agentes abiertos a la vez pasa de 100 000 tokens. Cuenta solo la entrada,
  y el que termina libera su parte: una cadena larga no lo agota; muchos frentes
  a la vez, sí.

**Ejemplo.** El Contable de estado no ve el plan del capítulo, para que anote lo
que pasó y no lo que se planeó. Pero sin fechas se inventaba los años, así que
ahora recibe el marco temporal de cada escena y nada más del plan.

**El límite.** La cuenta previa de tokens es una estimación calibrada, no la del
proveedor; por eso se deja un 20 % de margen.

*Más:* [`architecture.md`](../architecture.md) §3.
