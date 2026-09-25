# Comprobar el flujo con TLA+

**La idea.** Las pruebas recorren los caminos que alguien preparó. Un
comprobador de modelos recorre **todos** los estados posibles de una versión
pequeña del sistema y, si alguno rompe una regla, devuelve la secuencia exacta
de pasos que lleva a él.

**Cómo se aplica aquí.** `backend/formal/tla/Produccion.tla` describe el flujo
de una obra —capítulos, intentos, versiones, hilos, caídas y órdenes del
editor—, no su contenido. TLC lo recorre y comprueba que nunca se publica sin
pasar la puerta, que una versión terminada no cambia, que no hay dos
producciones a la vez y que toda obra acaba terminada o detenida con su motivo.
`mapeo.md` dice qué función del código implementa cada acción.

**Ejemplo.** TLC encontró que un doble clic en «reanudar» dejaba dos caminantes
escribiendo el mismo capítulo. Se arregló con un cerrojo y una prueba que lo
reproduce.

**El límite.** Que el código haga lo que el modelo dice se sostiene por
revisión, no se demuestra; y el modelo es pequeño: tres capítulos y dos
versiones.

*Más:* [`trade-offs.md`](../trade-offs.md) §9 y los contraejemplos en
[`backend/formal/tla/contraejemplos/`](../../backend/formal/tla/contraejemplos/).
