# Verificar con un método declarado

**La idea.** Decir «está comprobado» no vale si no se dice cómo. Cada cosa que
se verifica necesita un método, un predicado —qué tiene que ser verdad—, lo
mínimo que hay que mirar y una evidencia que se pueda citar.

**Cómo se aplica aquí.** Hay cinco métodos, un vocabulario cerrado:

| Método | Cuándo |
| --- | --- |
| `prueba` | Un caso preparado con resultado conocido |
| `analisis` | Un cálculo sobre datos ya escritos |
| `inspeccion` | Alguien lee y cita |
| `demostracion` | Se enseña funcionando |
| `inverificable` | No admite predicado, y se dice |

Cada dimensión de calidad de la novela tiene asignado su método, su agente y su
severidad en `validators.md`. Declarar algo `inverificable` es una respuesta
válida; inventarse una comprobación, no.

**Ejemplo.** La coherencia de voz es la única dimensión `inverificable`: la
puntúa el Juez de rúbrica, pero su nota es ruido y no bloquea nada.

**El límite.** Los verificadores también se miden: con casos sembrados de un
solo defecto se cuenta lo que detectan y lo que se inventan.

*Más:* [`validators.md`](../validators.md) §2 y §3.
