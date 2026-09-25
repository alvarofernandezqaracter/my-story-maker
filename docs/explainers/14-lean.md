# Demostrar la cronología con Lean

**La idea.** Un asistente de demostraciones no prueba casos: demuestra que una
afirmación es verdad para los datos que se le dan, y su núcleo lo comprueba sin
fiarse de nadie.

**Cómo se aplica aquí.** Antes de publicar una versión, el backend vuelca su
cronología —fecha, lugar y presentes de cada suceso, nacimientos y muertes— a un
módulo de Lean y le pide que demuestre cuatro invariantes: los capítulos van
hacia delante en el tiempo, nadie está presente antes de nacer ni con más de
120 años, nadie está en dos lugares el mismo día sin que conste el viaje, y
quien muere no reaparece. Hay un teorema por suceso e invariante, así que un
fallo dice en qué capítulo está.

**Ejemplo.** Una obra de prueba falló 74 veces: el Contable se inventaba el año
cuando el texto no lo decía. Ningún otro validador lo vio. Se arregló dándole
al Contable el marco temporal del capítulo.

**El límite.** Lean solo ve lo que la cronología registra: un suceso que la
prosa cuenta y el Contable no anotó no se puede contradecir. Sin Lean en la
máquina, la versión se publica marcada «sin comprobación formal».

*Más:* [`trade-offs.md`](../trade-offs.md) §10.
