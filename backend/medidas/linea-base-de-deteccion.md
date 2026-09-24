# Linea base de deteccion por dimension

Casos sembrados con un defecto conocido de una sola dimension por caso, y
los mismos casos con esa dimension intacta. **Es la linea base, no un
umbral**: lo que mide es de donde se parte.

| Dimension | Rol | Detecta el defecto | Inventa sobre el intacto |
| --- | --- | --- | --- |
| `integridad_de_pov` | verificador_de_continuidad | si | no |
| `cumplimiento_del_contrato` | verificador_de_continuidad | si | **si** |
| `cambio_de_valor` | verificador_de_continuidad | si | no |
| `violacion_epistemica` | verificador_de_continuidad | si | no |
| `continuidad_de_estado` | verificador_de_continuidad | si | **si** |
| `coherencia_temporal` | verificador_de_continuidad | si | no |
| `anacronismo_material` | verificador_de_continuidad | si | no |
| `anacronismo_conceptual` | verificador_de_continuidad | si | no |
| `anacronismo_social_e_institucional` | verificador_de_continuidad | si | no |
| `ritmo` | verificador_de_continuidad | si | no |
| `anacronismo_lexico` | editor_de_estilo | si | **si** |
| `fatiga_lexica` | editor_de_estilo | si | **si** |
| `tics_de_modelo` | editor_de_estilo | si | no |
| `coherencia_de_voz` | juez_de_rubrica | si | **si** |

Deteccion: 14 de 14. Falsos positivos: 5 de 14.

## Como leer esto

Catorce de catorce detectadas y cinco falsos positivos de catorce. Es la
primera medida y por eso **fija la linea base, no exige umbral**.

Lo que se lee en la columna de la derecha es la senal que `validators.md` 7
llama «el que encuentra algo siempre»: cinco contratos senalan defecto sobre
una escena que cumple su contrato. En cuatro de los cinco el predicado admite
grado —cuanto cumple un objetivo, cuanto pesa una imagen repetida, cuanto suena
un personaje a si mismo— y ahi es donde un predicado vago invita a opinar. Es
donde toca apretar el enunciado del contrato antes que tocar nada del codigo.

`coherencia_temporal` merece nota aparte. En una primera pasada no detecto su
defecto, y no fue cosa del agente: la ficha del lugar no traia escrita la
distancia, asi que no habia dos valores que comparar y al agente le tocaba
calcular, que es exactamente lo que `architecture.md` 7 dice que peor hace y lo
que falla en silencio. Con la distancia escrita en la ficha, lo detecta. La
compensacion documentada funciona, y lo que la sostiene es que el dato este
escrito, no que el agente sea listo.
