---
name: backend-sqlite
description: "El almacén de artefactos de my-story-maker sobre SQLite: qué se guarda, quién lo abre y cómo se consulta. Úsala antes de tocar nada que persista. Dispara con: sqlite, base de datos, almacén, persistencia, esquema, tabla, índice, consulta lenta, migración, WAL, SQLITE_BUSY, EXPLAIN QUERY PLAN, aiosqlite, PRAGMA, STRICT, foreign keys, FTS5, JSON, artefacto, log de eventos, EventoEstado, estado en N."
license: MIT
compatibility: "SQLite 3.x desde Python (sqlite3 / aiosqlite). La búsqueda vectorial va aparte, en la skill sqlite-vec."
allowed-tools: "Read Write Bash"
metadata:
  proyecto: my-story-maker
  related-skills: "sqlite-vec, fastapi"
---

# El almacén de my-story-maker

Esta skill tiene dos mitades. Primero, **las reglas de este proyecto**: son las
que deciden si un cambio entra o no, y salen de `AGENTS.md` y de
`docs/architecture.md`. Detrás, en `references/`, un **manual general de SQLite**
heredado, en inglés y sin relación con el dominio: se consulta, no se obedece.
Cuando las dos mitades discrepan, mandan las reglas del proyecto.

## 1. Quién abre la base de datos

Una sola puerta: `backend/src/novela/almacen/`. Nadie más la abre.

- Las tareas de `tareas/` **no importan `sqlite3` ni escriben SQL**. Piden y
  entregan artefactos a `almacen/`, y se comunican entre ellas por artefactos,
  nunca por llamadas directas.
- El `frontend/` **no ve la base de datos ni el disco**. Todo lo que muestra lo
  pide por HTTP al backend. Si le falta un dato, se añade un endpoint; no hay
  atajo posible por debajo.
- `almacen/` se declara como **interfaz estrecha**: unas pocas operaciones con
  nombre de dominio (guardar borrador, leer capítulo, añadir eventos, listar
  críticas abiertas), no un ORM ni un pasamanos de SQL. La forma física del
  almacén sigue siendo una decisión abierta, y una interfaz estrecha es lo que
  permite cambiarla sin tocar diez carpetas.

## 2. Qué se guarda

El principio es «artefactos, no objetos»: el estado vive en documentos
declarativos que los agentes puedan leer tal cual, no en un modelo relacional
del dominio.

- **El artefacto se guarda entero y legible.** Las columnas están para
  *encontrarlo* —obra, capítulo, escena, tipo, versión, quién lo escribió,
  cuándo— no para desmenuzar su contenido. Si aparece la tentación de una
  columna por atributo narrativo, es que se está construyendo el harness a
  medida que el proyecto prohíbe.
- **El log de `EventoEstado` es de solo añadir.** Nunca `UPDATE` ni `DELETE`
  sobre él. Regenerar el capítulo 12 no corrige eventos: descarta los del 12 en
  adelante y vuelve a plegar hacia delante.
- **El estado en N no se almacena, se deriva** plegando el log. Si por
  velocidad se guarda el estado materializado en N, es **caché descartable**:
  tiene que poder borrarse entera y recomputarse, y el esquema debe dejar claro
  que lo es.
- **Las capas no se mezclan.** Obra referencia Mundo por `id` y nunca lo
  duplica; Producción referencia a las dos y ninguna la referencia a ella. Con
  `PRAGMA foreign_keys = ON` en cada conexión —en SQLite viene apagado— esa
  regla deja de depender de la buena voluntad del que escribe.
- **Donde hay vocabulario controlado no hay texto libre.** Tablas `STRICT` y
  `CHECK (severidad IN (...))`. Los valores cerrados son lo que hace computables
  los predicados de calidad; una columna de texto libre los desactiva en
  silencio.
- **Los nombres del dominio se respetan.** Una tabla que guarda `EventoEstado`
  se llama por ese concepto, no por un sinónimo inventado al escribir el
  `CREATE TABLE`. Si hace falta un concepto que la ontología no tiene, eso es
  una decisión de dominio: vuelve a la spec, no lo resuelvas en el esquema.
- **Un dato histórico sin `Fuente` es una alucinación.** Todo lo que guarde un
  dato documental guarda al lado el `id` de su `Fuente`, y la `Fuente` es
  inmutable.

## 3. Cómo se consulta

- **Un solo escritor.** SQLite admite muchos lectores y un escritor. Baseline de
  conexión: `journal_mode = WAL`, `busy_timeout` explícito (nunca cero),
  `foreign_keys = ON`, `synchronous = NORMAL` con WAL. Detalle y trampas, en
  `references/concurrency-durability.md`.
- **Transacciones de escritura, `BEGIN IMMEDIATE`.** Empezar en modo diferido y
  ascender a escritura a mitad es la receta del `SQLITE_BUSY` que no se reproduce
  en local.
- **Toda consulta nueva pasa por `EXPLAIN QUERY PLAN` antes de darse por buena**,
  y `scripts/eqp-triage.py` clasifica el plan y sugiere el arreglo:

  ```bash
  python .claude/skills/backend-sqlite/scripts/eqp-triage.py \
      --db novela.db --sql "SELECT ... FROM ... WHERE ..."
  ```

  `SCAN` sobre una tabla que crece con la obra es un fallo, no un aviso.
- **El almacén no devuelve «todo».** Cada consulta sirve a la proyección de un
  rol concreto: el redactor no recibe la trama futura, el editor de estilo no
  recibe el canon. El recorte se hace en la consulta, no después en Python, y va
  siempre acotado, porque una ejecución completa no puede pasar de 100 000
  tokens entre todos los agentes.
- **Async solo si el endpoint es async.** Con FastAPI, `aiosqlite`; y si una
  ruta usa el `sqlite3` síncrono, va en un hilo aparte para no bloquear el bucle
  de eventos (`references/async-patterns.md`).

## 4. Búsqueda vectorial

La parte vectorial —embeddings, tablas `vec0`, consultas KNN, recuperación de
documentación por escena— **no está en esta skill**: está en la skill
`sqlite-vec`, que se abre además de esta. Aquí solo la regla que las une: lo que
se indexa para recuperar documentación guarda el `id` de la `Fuente` de la que
sale, y se filtra por fecha y lugar de la escena antes que por parecido.

## 5. Manual general (`references/`)

Material heredado, en inglés y genérico. Se ha retirado lo que no aplica aquí
—Cloudflare D1, los hosts de Node y el recorrido por motores—, porque el backend
es Python sobre un fichero local.

| Fichero | Para qué |
| --- | --- |
| `query-performance.md` | Leer `EXPLAIN QUERY PLAN`, índices que cubren, por qué no se usa un índice |
| `concurrency-durability.md` | WAL, `SQLITE_BUSY`, `busy_timeout`, modos de transacción, durabilidad |
| `schema-design.md` | Afinidad de tipos, `STRICT`, claves foráneas, columnas generadas, fechas |
| `schema-patterns.md` | Plantillas de tabla: configuración, caché, log de eventos, cola, búsqueda |
| `migration-patterns.md` | Qué puede y qué no puede `ALTER TABLE`, recreación en 12 pasos, `user_version` |
| `feature-modules.md` | FTS5, tokenizador de trigramas, funciones JSON, `UPSERT`, `RETURNING` |
| `async-patterns.md` | `aiosqlite`: conexión, CRUD, lotes, resultados en streaming |
| `operations.md` | Integridad, corrupción, copias, `VACUUM`, carga masiva |
| `testing.md` | Bases en memoria contra fichero, fixtures, sembrado determinista |

## 6. Lo que no decides tú

Dos cosas siguen abiertas en `docs/architecture.md` §8 y **no se cierran dentro
de un cambio de código**: dónde vive exactamente el almacén de artefactos dentro
del reparto del repositorio, y quién lo escribe. Si el trabajo se topa con una
de ellas, se propone el cierre y se espera la decisión; no se elige por
conveniencia y se sigue adelante.
