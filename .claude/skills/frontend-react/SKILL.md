---
name: frontend-react
description: "La interfaz de my-story-maker: qué le toca hacer, cómo se organiza y qué tiene prohibido. Úsala antes de tocar nada de frontend/. Dispara con: react, frontend, interfaz, componente, jsx, tsx, vite, hook, useState, useEffect, estado del cliente, TanStack Query, Zustand, formulario, pantalla, lanzar obra, manuscrito, críticas, trazas, testing de componentes."
license: MIT
compatibility: "React 19 sobre Vite. No hay Next.js ni Server Components en este proyecto. Ecosistema verificado en 2026-07."
allowed-tools: "Read Write Bash"
metadata:
  proyecto: my-story-maker
  related-skills: "fastapi"
---

# La interfaz de my-story-maker

Esta skill tiene dos mitades. Primero, **las reglas de este proyecto**, que
salen de `AGENTS.md` y de `docs/architecture.md` §7 y deciden si un cambio entra
o no. Detrás, en `references/`, un **manual general de React** heredado, en
inglés y sin relación con el dominio: se consulta, no se obedece. Cuando las dos
mitades discrepan, mandan las reglas del proyecto.

## 1. Qué es esta interfaz y qué no

La interfaz **lanza ejecuciones y muestra artefactos**. Nada más. El editor
escribe un brief, arranca una obra y mira lo que los agentes han producido: el
manuscrito, las críticas abiertas, la traza de cómo se llegó hasta ahí.

Lo que tiene prohibido:

- **No lee ficheros del disco ni abre la base de datos.** Todo lo que muestra lo
  pide por HTTP al backend. Es la frontera única del proyecto: el almacén de
  artefactos tiene un solo lector y un solo escritor. Si falta un dato, se añade
  un endpoint; no existe el atajo de leer el fichero.
- **No calcula dominio.** No pliega el log de `EventoEstado` para reconstruir el
  estado en N, no decide si una crítica es bloqueante, no cuenta tokens ni juzga
  texto. Todo eso ya lo hizo un agente y viene resuelto en el artefacto. Una
  regla de negocio reimplementada en el cliente es una segunda verdad que
  divergirá de la del backend.
- **No inventa vocabulario.** Las severidades, los estados del capítulo y los
  tipos de evento son vocabularios cerrados del dominio. La interfaz puede
  traducirlos a una etiqueta legible, nunca ampliarlos ni agrupar dos valores en
  uno «porque se ve mejor».

## 2. Cómo se organiza

Una carpeta por funcionalidad, con sus componentes y sus llamadas dentro:

```
frontend/src/
  features/
    lanzar/       el brief del editor y el arranque de una obra
    manuscrito/   leer lo redactado, por capítulo y escena
    criticas/     críticas abiertas y resueltas, con su evidencia
    trazas/       por qué el capítulo 12 quedó así
  compartido/     cliente de API y componentes comunes
```

- **Nada de capas de dominio en el cliente.** No hay `services/`, `models/` ni
  `domain/`: eso es el backend.
- **Las funcionalidades no se importan entre sí.** Lo común sube a
  `compartido/`; entre dos pantallas se duplica antes que acoplarse.
- **Un solo cliente de API**, en `compartido/`, y todas las llamadas pasan por
  él. Es lo que hace que la frontera se pueda revisar leyendo una carpeta.

## 3. El estado

**Casi todo lo que la interfaz muestra es estado del servidor.** No es suyo: son
artefactos que el backend ya tiene.

- El estado del servidor **se consulta y se cachea contra la API**, con la
  biblioteca que se elija para ello —TanStack Query es el candidato obvio, pero
  no está decidido y no hace falta decidirlo para la primera pantalla—.
- El estado propio de una pantalla —un filtro, una pestaña, un formulario a
  medio escribir— **se queda en esa pantalla**, en `useState` o en un formulario
  (React Hook Form si el formulario crece, con Zod para validar).
- **No hay almacén global.** Un Zustand, un Jotai o un Redux Toolkit con los
  capítulos dentro sería una copia desactualizada de lo que ya tiene el backend.
  Si alguna vez hiciera falta uno, sería para preferencias de la propia interfaz
  —tema, panel plegado—, nunca para el dominio.
- **Cómo llega el avance de una ejecución en curso está sin decidir** (sondeo,
  SSE, websocket). Es detalle de implementación: encapsúlalo en el cliente de
  API para que cambiarlo no toque las pantallas.

## 4. React en este proyecto

- **React 19 sobre Vite, aplicación de una sola página.** No hay Next.js ni
  Server Components: todo componente se ejecuta en el navegador. Si una
  referencia del manual habla de RSC, no aplica aquí.
- Las novedades de React 19 que sí se usan: `use(` para leer una promesa o un
  contexto, Actions con `useActionState` para enviar el brief, `useFormStatus`
  para el estado del envío y `useOptimistic` cuando la respuesta tarda. El
  React Compiler hace innecesaria casi toda la memoización manual: no siembres
  `useMemo` por si acaso.
- **Español en la interfaz**, y los nombres del dominio tal cual: `Escena`,
  `Crítica`, `EventoEstado`. Si en la pantalla aparece una palabra que no está
  en `docs/definitions.md`, o sobra o falta una definición.
- Las ejecuciones son lentas por naturaleza: **todo lo que espera tiene estado
  visible** —en curso, fallido, terminado— y nada se queda en blanco sin decir
  por qué.

## 5. Manual general (`references/`)

Material heredado, en inglés y genérico. Se ha retirado la referencia de Server
Components, que describe un entorno —Next.js y el App Router— que este proyecto
no tiene.

| Fichero | Para qué |
| --- | --- |
| `hooks-patterns.md` | Qué hook resuelve cada problema, y las trampas de cada uno |
| `component-architecture.md` | Composición, props, límites de error, componentes compuestos |
| `state-management.md` | Estado de servidor contra estado de cliente, y el catálogo de bibliotecas |
| `performance.md` | Re-renderizados, listas largas, carga diferida, medición |
| `testing.md` | `@testing-library/react` y `vitest`: qué probar y cómo |

`scripts/check-react-facts.py` comprueba que lo que la skill afirma del
ecosistema sigue siendo cierto: en modo `--offline` que el catálogo de
`assets/react-facts.json` y la prosa no se hayan separado, y en `--live` que
ningún paquete haya sacado una versión mayor por detrás.

```bash
python .claude/skills/frontend-react/scripts/check-react-facts.py --offline
```
