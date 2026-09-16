# CLAUDE.md — my-story-maker

Sistema multiagente que escribe una novela histórica capítulo a capítulo a partir
de un brief de cinco campos. Versión 0.5.1, F0–F5 del roadmap funcionando de punta
a punta en modo `simulado`.

## Regla número uno: el spec manda

[`docs/spec/SPEC.md`](docs/spec/SPEC.md) es la fuente de verdad. Si el código y el
spec cuentan cosas distintas, manda el spec y el código es el que está mal.

**El spec y el código nunca divergen.** Cuando un cambio de código introduce,
cambia o elimina algo que el spec describe (una clave de `config.json`, un campo
del canon, un validador `VD-xx`, un comando de la CLI, un estado), el spec se
actualiza en el mismo momento, no después. Eso implica además:

- Subir la versión en la cabecera del spec (`version:` y `actualizado:`).
- Añadir su entrada en §16 con **sección tocada y motivo**, formato Keep a Changelog.
- Regenerar la tabla de §17 con el `git log` que la propia §17 documenta al final.
- Los números de sección son estables y **no se reutilizan**; si una sección
  desaparece, su número queda muerto (pasó con DA-01).

## Cómo se trabaja este repo

- **Documentos de spec**: cortos, centrados en decisiones y en el porqué, no en el
  cómo. Una sección por commit.
- **Commits**: uno por sección o por unidad de cambio, mensaje en minúsculas y en
  español, con el ámbito entre paréntesis y la sección tocada:
  `docs(spec): §12 la credencial del modo real va en el entorno`,
  `feat(harness): capa unica de llamada a agentes, simulada y real`.
- **Push**: Álvaro hace el push y trata con el remoto. Commitear en local y parar ahí.
- **Idioma y acentos**: todo en español. El código `.mjs` y los prompts de
  `agentes/` y `skills/` van **sin acentos** (ASCII); los documentos Markdown
  (`SPEC.md`, `README.md`, este fichero) sí llevan acentos.

## Stack y comandos

Node 24 (mínimo 22.5) con `node:sqlite` y `node:test`, los dos de la biblioteca
estándar. El modo `simulado` —el de por defecto— no necesita instalar nada. La
única dependencia es `@anthropic-ai/sdk`, importada de forma perezosa y solo en
modo `real`.

```bash
node bin/novela.mjs init
node bin/novela.mjs brief brief.ejemplo.json
node bin/novela.mjs preparar     # investigador y arquitecto
node bin/novela.mjs escribir     # loop: escritor, VD-08, validador, gate, cronista
node bin/novela.mjs cerrar       # editor global y retoques.md
npm test                         # 36 tests, sin red
```

Otros comandos: `reanudar`, `estado`,
`ver <dossier|personajes|escaleta|resumenes|timeline|hilos|contexto N|capitulo N>`,
`poner <personaje|capitulo|dato> <fichero.json>`,
`desbloquear --capitulo N [--aprobar-intento K | --reiniciar]`, `skills`.
Opciones globales `--config` y `--canon`.

## Principio rector

Lo determinista vive en **código** (`src/`): selección de contexto, gate, control
de reintentos, escritura en el canon y máquina de estados. Lo generativo vive en
**agentes** (`agentes/`, `skills/`): investigar, estructurar, redactar, revisar,
resumir y editar.

**Ningún agente escribe en el canon.** Todos devuelven una propuesta estructurada
que el harness valida (§9) y persiste. Los agentes nunca se pasan datos entre sí
por fuera del canon o del paquete de contexto.

## Mapa del código

| Fichero | Qué es | Spec |
|---|---|---|
| [src/config.mjs](src/config.mjs) | Carga y **valida entero** `config.json`; para al arrancar si algo falta o cae fuera de rango | §12 |
| [src/canon.mjs](src/canon.mjs) | SQLite: las 7 tablas, y `escrituraDelCronista` como transacción única | §3, §6 |
| [src/esquemas.mjs](src/esquemas.mjs) | Contratos de I/O de los seis roles y `comprobarForma` (VD-01/VD-02) | §5 |
| [src/validadores.mjs](src/validadores.mjs) | Los once `VD-xx` deterministas | §9 |
| [src/gate.mjs](src/gate.mjs) | Fórmula del gate, `mejorIntento`, `incidenciasOrdenadas` | §8 |
| [src/contexto.mjs](src/contexto.mjs) | Generador de contexto: nueve bloques, serialización y recorte | §7 |
| [src/skills.mjs](src/skills.mjs) | Carga `agentes/<rol>.md` + sus skills y compone las instrucciones | §10 |
| [src/agentes.mjs](src/agentes.mjs) | Capa única de llamada; oculta simulado/real; `ParadaDelProceso` | §5, §12 |
| [src/proveedor.mjs](src/proveedor.mjs) | Modo `real`: SDK de Anthropic, streaming, extracción de JSON | §12 |
| [src/simulado.mjs](src/simulado.mjs) | Respuestas fijas con el formato correcto + inyección de fallos | §12 |
| [src/flujo.mjs](src/flujo.mjs) | `preparar`, `escribirCapitulo`, `cerrar`, `reanudar` | §4, §8, §11 |
| [bin/novela.mjs](bin/novela.mjs) | CLI. **No decide nada**: carga config, abre el canon y llama al flujo | §18 |

`canon.db`, `capitulos/*.md` y `retoques.md` son salida y no se versionan.

## Los seis agentes (§5)

| Rol | Entrada | Salida | Skills que carga |
|---|---|---|---|
| `investigador` | brief | `{ datos: [...] }` | `formato-dossier` |
| `arquitecto` | brief + dossier | `{ personajes, capitulos }` | `formato-fichas` |
| `escritor` | paquete de contexto | `{ texto, faltantes? }` | `formato-paquete-contexto`, `estilo-prosa` |
| `validador` | capítulo + paquete + encargo | `{ revisiones: [3 bloques] }` | `rubricas-validador` |
| `cronista` | capítulo aprobado + fichas | resumen, hilos, `cambios_personaje`, `eventos` | `formato-fichas` |
| `editor_global` | resúmenes + escaleta + personajes | `{ retoques: [...] }` | — |

El reparto rol→skill vive en `SKILLS_POR_ROL` ([src/skills.mjs:12](src/skills.mjs#L12)).
Una skill es texto que lee un modelo, **nunca fuente de verdad para el código**: los
números y umbrales viven en `config.json`.

## Invariantes que no se tocan

1. **Una sola escritura en el canon por capítulo**, la del cronista, después del
   gate, y en una transacción (VD-11): o entran resumen, cambios de ficha y eventos
   juntos, o no entra nada.
2. **El gate es código puro**: `aprueba = min(notas) >= nota_minima y media >= media_minima
   y ninguna incidencia grave`. La incidencia grave veta por sí sola. Siempre tres
   notas; **nota global no existe**.
3. **El generador de contexto es determinista**: mismo capítulo y mismo canon dan el
   mismo paquete. El paquete no se persiste, se reconstruye.
4. **El texto completo de capítulos anteriores no entra nunca** en el paquete, salvo
   el enganche (`contexto.palabras_enganche` palabras literales del anterior aprobado).
   Para eso están los resúmenes.
5. **Orden de recorte del paquete**, si se pasa de `tope_contexto`: memoria larga,
   cronología, reparto de fondo, época. Encargo, personajes y hilos vivos no se
   recortan; si aun así no cabe, el capítulo se marca `bloqueado`.
6. **VD-08 antes del validador**: si el capítulo redactado no cumple lo básico se
   reintenta la generación sin gastar la llamada al agente validador.
7. **El reintento del último intento va de cero**, y el que descarta VD-08 también.
   Los demás reciben su propio texto para arreglo quirúrgico.
8. **Nada corre en paralelo** con la configuración por defecto. El único paralelismo
   posible es `validador.modo: "separado"`, que hace tres llamadas sobre el mismo
   capítulo. Nunca dos capítulos a la vez: el N+1 depende del canon que dejó el N.
9. **Un bloqueante que falla dos veces seguidas para el proceso** y deja el estado
   escrito (`ParadaDelProceso`). No hay reintento infinito ni backoff.
10. **El estado vive en el canon, nunca en memoria del proceso.** Por eso `reanudar`
    no necesita argumentos. Y **reanudar no desbloquea**.

## Los once validadores (§9)

VD-01 forma, VD-02 obligatorios, VD-03 ids existentes, VD-04 dossier con fuente y
estado (un `verificado` con fuente `modelo` es inválido), VD-05 evento de trama con
capítulo e histórico sin él, VD-06 resumen solo si hay intento aprobado, VD-07 número
de capítulos dentro de márgenes, **VD-08 la única de dos escalones** (aviso y bloqueo,
de ahí sus dos márgenes), VD-09 personajes presentes ⊆ ficha, VD-10 tres dimensiones
una vez cada una con nota entera 1-5, VD-11 nada bloqueante pendiente al confirmar.

Las tres dimensiones del validador son siempre `continuidad`, `anacronismos` y
`logica_ritmo`, en ese orden.

## Máquina de estados (§4)

`borrador` → `investigado` → `estructurado` → `escribiendo` → `escrito` → `editado`,
con `bloqueado` como salida lateral que exige mano humana. `escribiendo` se entra al
**arrancar** el primer capítulo, no al aprobarlo.

Dos puntos fijos de intervención humana: capítulo bloqueado (tres salidas manuales
vía `desbloquear`) y los retoques finales, que se aplican a mano.

## Configuración (§12)

Un único `config.json` en la raíz, validado entero al arrancar. **Si un número
aparece escrito en el código sin pasar por este fichero, es un bug.** La credencial
de la API no vive aquí: va en el entorno, porque el fichero se versiona.

Quince claves: `ejecucion.modo`, `gate.{nota_minima,media_minima,max_intentos}`,
`contexto.{tope_contexto,ventana_resumenes,palabras_enganche}`, `validador.modo`,
`margenes.{capitulos_min,capitulos_max,palabras_aviso,palabras_bloqueo,parrafos_min}`,
`modelo_por_rol`, `busqueda_web`. Reglas cruzadas: `palabras_bloqueo > palabras_aviso`
y `capitulos_max >= capitulos_min`.

## Modo simulado e inyección de fallos

Todas las llamadas pasan por [src/agentes.mjs](src/agentes.mjs), así que el resto del
harness no sabe qué modo está activo. Los tests y las demostraciones corren por el
mismo camino que la ejecución real.

Dos variables de entorno, **solo con efecto en modo simulado**, toman una lista de
`capitulo:intento`:

```bash
NOVELA_SIM_FALLOS="2:1"  # el validador suspende ese intento (nota 2 + incidencia grave)
NOVELA_SIM_CORTOS="3:1"  # el escritor devuelve un capitulo que VD-08 bloquea
```

Existen porque el camino interesante —rechazo, reintento, bloqueo— no se ve nunca si
todas las respuestas simuladas son buenas.

## Tests

`npm test` corre 36 tests en dos ficheros, sin red y sin coste:
[test/deterministas.test.mjs](test/deterministas.test.mjs) para config, gate y
validadores, y [test/flujo.test.mjs](test/flujo.test.mjs) para el canon, el generador
de contexto y el flujo entero contra la capa simulada. Cada test del flujo corre en su
propio directorio temporal porque el harness escribe en el `cwd`.

## Estado actual y cosas abiertas

- `margenes.parrafos_min` vale **3** desde 0.5.1, alineado en `config.json`, en la
  tabla de §12 y en la copia del test. Cinco párrafos descartaba capítulos cortos
  legítimos antes de llegar al validador.
- El `.drawio` de [docs/diagrama/](docs/diagrama/) va por detrás del Mermaid: le falta
  el cronista y se regenera a mano. El Mermaid de §4 es el bueno.
- Decisiones abiertas vivas en §15: DA-02 (modelos), DA-03 (parada tras preparación),
  DA-04 (proveedor de búsqueda), DA-05 (`faltantes` que nadie mira), DA-06
  (calibración del gate, sin capítulos reales), DA-07, DA-08, DA-09, DA-10.
- F6 (búsqueda web real del investigador) no está implementado: `busqueda_web` está a
  `true` para no tocar el esquema más tarde, pero el investigador la ignora.
