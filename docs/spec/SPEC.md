---
doc: spec-sistema-novelas-historicas
version: 0.1.0
estado: borrador
actualizado: 2026-09-15
---

# Spec — Sistema multiagente de novelas históricas

## §1 Visión y alcance

Sistema que escribe una novela histórica capítulo a capítulo a partir de un brief corto. Un agente investiga la época, otro diseña la estructura, un escritor redacta cada capítulo y tres revisores lo puntúan antes de que entre en el canon. Al terminar, un editor global propone retoques sobre el conjunto.

**Principio rector.** Lo determinista vive en código del harness: selección de contexto, cálculo del gate, control de reintentos, escritura en el canon y máquina de estados. Lo generativo vive en agentes: investigar, estructurar, redactar, revisar y editar. Ningún agente escribe en el canon; propone, y el harness decide.

**Qué produce.** Un canon consultable, un fichero por capítulo aprobado y una lista final de retoques. No maqueta el libro ni aplica esos retoques por sí mismo.

**Fuera de alcance en 0.1.0.** Interfaz gráfica, exportación a EPUB, ilustraciones, varios proyectos a la vez, traducción y reescritura automática a partir del editor global.

**Criterio de éxito.** Una novela completa sin contradicciones de canon detectables ni anacronismos groseros, con intervención humana solo en los dos puntos que fija §4.

## §2 Glosario

| Término | Significado en este sistema |
|---|---|
| Brief | Entrada del usuario: época, premisa, tono y nº de capítulos. Única cosa que se escribe a mano al arrancar. |
| Canon | Base de datos del libro. Única fuente de verdad. Se lee antes de escribir y se actualiza solo al aprobar. |
| Dossier | Conjunto de datos históricos del canon, cada uno con su fuente y su estado de verificación. |
| Dato histórico | Unidad mínima del dossier: una afirmación sobre la época, con categoría, fuente y estado. |
| Escaleta | Plan de la novela: arco en tres actos y una ficha por capítulo. |
| Ficha de capítulo | Qué pasa en un capítulo y quién sale. Es el encargo que recibe el escritor. |
| Capítulo redactado | Texto que produce el escritor en un intento concreto. Puede no llegar a aprobarse. |
| Resumen | Un párrafo por capítulo aprobado, con hilos abiertos y cerrados. Es lo que lee el editor global. |
| Generador de contexto | Código que selecciona del canon lo que hace falta para un capítulo y arma el paquete de contexto. |
| Paquete de contexto | Salida del generador: el subconjunto del canon que ve el escritor. |
| Revisor | Agente que puntúa un capítulo en una dimensión y devuelve incidencias. Hay tres. |
| Nota | Puntuación de 1 a 5 que da un revisor en su dimensión. |
| Gate | Código que decide, con las tres notas, si el capítulo se aprueba o se reescribe. |
| Intento | Cada pasada del escritor sobre el mismo capítulo. Máximo tres. |
| Editor global | Agente de pasada única al final, fuera del loop. Lee resúmenes, no texto. |
| Harness | Todo el código determinista que orquesta el proceso. No genera prosa. |
