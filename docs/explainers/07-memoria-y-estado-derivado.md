# Memoria y estado derivado

**La idea.** Un agente sin memoria entre llamadas necesita que alguien le diga
cómo está el mundo. Si ese «cómo está» se guarda en una ficha que se va
editando, se pierde lo que era cierto antes y nadie sabe quién lo cambió.

**Cómo se aplica aquí.** El mundo solo cambia por `EventoEstado` —alguien viaja,
adquiere algo, se entera de algo, muere—, que solo escribe el Contable al cerrar
un capítulo. El estado en el capítulo N no se guarda: **se deriva plegando el
log** de eventos hasta N. Es la idea del *event sourcing*. Además hay tres
memorias con distinta vida: la de la tarea, la del capítulo —que se retira al
cerrarlo— y la de la obra.

**Ejemplo.** Rehacer desde el capítulo 4 no tiene que deshacer nada: basta con
plegar el log hasta el 3 y seguir desde ahí.

**El límite.** Plegar cuesta una tarea al cerrar cada capítulo; el resultado se
guarda como caché para no repetirlo.

*Más:* [`architecture.md`](../architecture.md) §3, «Estado como pliegue».
