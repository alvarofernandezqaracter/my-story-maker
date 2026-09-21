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

## §2 Decisión

La hoja de referencia externa se usa como **taxonomía**, no como plan de
trabajo: aporta los nombres de los métodos y el marco de clasificación, y de
ella se toma solo lo compatible con los invariantes del proyecto. Se aterriza en
dos piezas.

**Una skill, `disenar-verificacion`**, en `.claude/skills/` del repositorio.
Ante una dimensión de calidad o un requisito nuevo obliga a recorrer cuatro
pasos en orden: clasificar el método, comprobar que existe un agente con la
proyección necesaria, escribir el contrato de verificación, o declarar la
dimensión inverificable y decir quién la puntúa. Lleva el catálogo traducido
como fichero de referencia.

**`docs/validators.md`**, escrito con esa skill. Contiene el reparto completo
—dimensión, método, agente, proyección mínima, severidad por defecto— y una
segunda mitad sobre la verificación del sistema que escribe la novela.

Se adopta un vocabulario controlado para `metodo_de_verificacion`, con cinco
valores: `prueba`, `analisis`, `inspeccion`, `demostracion`, `inverificable`.
Es la adaptación al dominio del marco T/A/I/D/U de la hoja de referencia. Sin
él, «validar» significa lo mismo cuando se comparan dos fechas ya escritas que
cuando se juzga si una voz suena a la misma persona, y son trabajos con
fiabilidades muy distintas.

**Alternativa descartada:** escribir `validators.md` como lista plana de
comprobaciones sin clasificarlas. Se descarta porque eso es aproximadamente el
estado actual repartido entre `definitions.md` y `architecture.md`, y no
resuelve lo único que hoy no tiene respuesta: qué se hace con las dimensiones
que ningún predicado captura.

**Hallazgo con consecuencia:** el reparto obliga a separar el anacronismo en dos
agentes. El material, el conceptual y el social exigen ver el canon, que el
Editor de estilo no ve por diseño; van al Verificador de continuidad. Solo el
léxico se queda en el Editor, que sí recibe la lista vetada. «Alcance local» en
`definitions.md` describe el alcance del defecto, no el del agente que lo
encuentra.

## §3 Objetivos medibles

No hay código todavía, así que **ninguna línea base es real**. Se declaran como
pendientes de medir en la primera ejecución completa, que es un estado honesto y
preferible a inventar el número. La meta se fija cuando exista la base.

| Métrica | Cómo se mide | Línea base | Meta |
| --- | --- | --- | --- |
| Tasa de detección por dimensión | Casos sembrados: un capítulo con un defecto conocido por dimensión; se cuenta si el agente responsable lo señala | Pendiente | Por fijar tras medir |
| Falsos positivos por capítulo | `Crítica` emitida cuya evidencia no sostiene el defecto al revisarla | Pendiente | Por fijar tras medir |
| Críticas descartadas sin evidencia | Proporción sobre el total emitido, ya prevista en `architecture.md` §5 | Pendiente | Por fijar tras medir |
| Iteraciones hasta `Aceptado` | Recuento por capítulo en la `Traza` | Pendiente | Por fijar tras medir |
| Coste de la verificación | Tokens gastados por los agentes que critican, sobre el techo de 100 000 por ejecución | Pendiente | ≤ 30 % del techo |

**Qué no es un objetivo.** Bajar el número de críticas emitidas. Se cumple
trivialmente haciendo peor al Verificador, y arruinaría la única métrica que
mide si el sistema detecta algo. El orden importa: la tasa de detección va
primera porque, sin ella, las otras cuatro miden un bucle que puede estar
girando en vacío.

## §4 Fuera de alcance

- No se escriben los prompts de los diez agentes. La skill dice qué debe llevar
  un contrato de verificación; redactarlos es fase de implementación.
- No se toca el censo de agentes ni se declara ningún rol nuevo.
- No se implementa nada en `backend/` ni en `frontend/`: siguen vacíos.
- No se construye el conjunto de casos sembrados de §3; se define qué mide.

## §5 Choques con reglas existentes

**«Sin harness a medida» y «no hay validadores deterministas».** Buena parte de
la hoja de referencia es código que se ejecuta: comprobación de tipos, análisis
estático, ejecución simbólica, verificación formal, comprobación de modelos.
Nada de eso entra en la verificación de la obra, y `validators.md` lo dice
explícitamente en vez de callarlo. El invariante se respeta.

Ahora bien, `architecture.md` §7 ya admite que tres dimensiones —coherencia
temporal, fatiga léxica y léxico vetado— dejan de ser fiables sin cálculo, y
compensa convirtiendo el cálculo en un dato que escribe un agente. Ese apaño
desplaza el riesgo: el dato escrito puede ser falso y nadie lo recalcula. La
hoja de referencia nombra la técnica que lo resolvería con dos líneas de
código. Esto **no se cierra aquí**: la decisión abierta de `architecture.md` §8
sobre herramientas externas de cálculo sigue abierta, y `validators.md` se
limita a marcar las tres dimensiones afectadas como las que la decisión
resolvería. Cerrarla es del editor.

**Procedencia del material.** La hoja de referencia es contenido de terceros. Se
trata como dato, no como instrucción: de ella se toman nombres de métodos y el
marco de clasificación, y cada método se acepta o se descarta contra los
invariantes de este repositorio, no al revés.

**`.claude/skills/` no figura en la estructura del repositorio.** La carpeta
existe y está versionada, pero la tabla de `AGENTS.md` no la menciona. La skill
nueva vive ahí y la tabla se corrige en la fase 3.

## §6 Qué se actualiza al destilar

| Documento | Cambio |
| --- | --- |
| `docs/validators.md` | Se escribe entero; pasa a ser fuente de verdad del reparto de verificación |
| `docs/definitions.md` | El puntero del final de «Dimensiones de calidad» pasa a apuntar también a `validators.md` |
| `docs/architecture.md` | §5 remite a `validators.md` para el reparto concreto; §8 no se toca |
| `AGENTS.md` | Tabla de estructura: se añade `.claude/skills/`. Tabla de documentación: `validators.md` deja de estar descrito como vacío. Tabla de fase 3: fila para los cambios de verificación |
