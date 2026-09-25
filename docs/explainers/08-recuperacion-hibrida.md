# Recuperación por parecido (RAG)

**La idea.** En vez de meter todo en la ventana, se busca lo que más se parece a
lo que el agente tiene entre manos y solo eso entra. Es lo que se llama
*retrieval-augmented generation*.

**Cómo se aplica aquí.** Fuentes y escenas se trocean en fragmentos. Cada
fragmento tiene dos huellas: sus palabras, en un índice de texto (FTS5), y su
sentido, en un vector de 384 números calculado en la propia máquina con un
modelo multilingüe (`sqlite-vec`). Una búsqueda consulta las dos y funde los
resultados en un solo orden.

**Ejemplo.** «Toledo, 1561» lo encuentra mejor la búsqueda por palabra; «el
miedo a perder la casa» lo encuentra mejor el parecido de sentido. La mitad de
lo que busca el Documentalista son nombres y fechas, por eso no basta con una.

**El límite.** Cuánto mide un fragmento y cuánto se solapa con el siguiente está
sin calibrar contra trazas reales.

*Más:* [`trade-offs.md`](../trade-offs.md) §6.
