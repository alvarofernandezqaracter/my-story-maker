# Plan de implementación del frontend v1

Plan para construir de una sola pasada la interfaz que describe
`specs/SPEC2.md`. Está pensado para dárselo a un agente y que termine con una
web que funciona: de la pantalla en blanco a la novela leída.

**Este plan no es la spec.** Qué tiene que hacer la interfaz y por qué lo dice
SPEC2; aquí solo está el *cómo*: qué ficheros, en qué orden, con qué
bibliotecas y cómo se comprueba cada cosa. Si algo de aquí contradice a SPEC2,
manda SPEC2 y esto es un error del plan.

## 0. Cómo se lanza

Prompt para el agente que ejecuta:

> Implementa `specs/PLAN-FRONTEND.md` de principio a fin, sin parar entre pasos.
> Antes de escribir código abre la skill `frontend-react`. Sigue los pasos en
> orden y no des uno por cerrado sin su comprobación. No toques `backend/`. Al
> terminar, cuéntame en lenguaje llano qué se ha hecho, qué se ha comprobado y
> qué ha quedado fuera.

Condiciones de partida, que el agente comprueba antes del paso 1:

- Node 24 y npm 11 están instalados (`node --version`).
- `backend/.venv` existe y el backend arranca (ver `CLAUDE.md`).
- SPEC2 es la fase 1 del ciclo ya escrita: **no hay interrogatorio**. Lanzar este
  plan es aprobarla, así que el primer cambio es poner `estado: aprobada` en su
  cabecera.

Lo que no se hace en ningún paso:

- **No se toca `backend/`.** Ni CORS, ni endpoints, ni `openapi.yaml`. Todo lo
  que hace falta ya está servido (§1). Si aparece algo que exige tocarlo, se
  para y se dice: es volver a la fase 1 de SPEC1, no un detalle.
- **No se lanza una obra de verdad sin avisar.** Cada pasada de entrevista
  arranca un subagente real y una obra lanzada produce durante horas: las dos
  cosas cuestan dinero. Todas las pruebas del plan simulan el servidor.
- **No se cierra ninguna decisión abierta de SPEC2 §12.** Ni TanStack Query, ni
  listado de obras, ni descarga del manuscrito.

## 1. Lo que el backend ya da (comprobado en el código)

Se leyó `backend/src/novela/api/aplicacion.py` y `backend/openapi.yaml`. Esto es
lo que condiciona la interfaz y no está escrito en SPEC2:

| Hecho | Consecuencia para la interfaz |
| --- | --- |
| El backend **no tiene CORS** | El navegador no puede llamarlo desde otro puerto. La interfaz se sirve con un **proxy de Vite**: el navegador pide `/api/...` a Vite y Vite lo reenvía a `http://127.0.0.1:8000`, quitando el `/api`. Mismo origen, sin tocar el backend |
| Un rechazo normal trae `{"detail": "<mensaje en español>"}` | Es el mensaje que se enseña tal cual (SPEC2 RF-61) |
| Un cuerpo mal formado trae `{"detalle": "...", "campos": ["ruta", ...]}` con 422 | Se enseña `detalle` y se señalan los `campos` por su ruta |
| La pasada que no cabe devuelve 422 con `detail` = «…ocupa N tokens, el tope es T y sobran S…» | RF-08 sale gratis: se enseña el mensaje. No se recorta nada |
| Pasada contra una entrevista inexistente: 404. Contra una que ya lanzó su obra: 409 que nombra la obra | Mensajes propios con salida (§4.1) |
| Si el subagente falla: 502 con `detail` | Rechazo del servidor con opción de reintentar |
| Una pasada tarda lo que tarde un subagente: **de segundos a un par de minutos** | Sin tiempo límite en el cliente; la espera enseña los segundos que lleva |
| `GET /obras/{id}/progreso` es SSE con **eventos con nombre**: `progreso` (lleva un `Progreso` en JSON) cada segundo, y `terminada` cuando el hilo de producción ha acabado, tras el cual el servidor cierra | Se escucha con `addEventListener("progreso")`, no con `onmessage`. Al llegar `terminada` **hay que cerrar el `EventSource`**: si no, el navegador se reconecta solo y vuelve a empezar |
| `terminada` también llega cuando la obra **se ha detenido** (el hilo acaba igual) | Se distingue con el campo `detenida` del último progreso, no calculando nada |
| El primer evento de cada conexión es un `progreso` inmediato | Al reengancharse, la pantalla se pone al día con el primer mensaje |
| `POST /obras/{id}/detener` exige cuerpo `{"motivo": "..."}`; `reanudar` no lleva cuerpo | El diálogo de detener pide un motivo opcional |
| `tareas_abiertas` es una lista de objetos con `rol`, `tarea`, `capitulo`, `escena`, `tokens` | Se pintan esas cinco columnas, tal cual |
| Cuando Vite no alcanza el backend responde 500 **sin JSON** | Una respuesta sin `detail` ni `detalle` es «no hay servidor», no un rechazo (RF-62) |

### Dos huecos que el plan no resuelve

Se dicen aquí para que nadie los tape en el código:

1. **Una obra terminada, vista después de reiniciar el servidor, parece seguir en
   marcha.** El evento `terminada` solo sale si el servidor tiene el hilo de esa
   obra en memoria. Tras reiniciar, el flujo manda `progreso` sin fin y nunca
   `terminada`. Deducirlo en el cliente («no hay tareas y no hay capítulo en
   curso, luego ha terminado») es calcular dominio, y SPEC2 RF-25 lo prohíbe. La
   solución es un campo `terminada` en `Progreso` o en `FichaDeObra`, que es una
   enmienda a SPEC1. Mientras no exista, la pantalla dice lo que sabe: «sin
   tareas abiertas ahora mismo».
2. **Volver a una obra después de cerrar el navegador** exige conocer su
   dirección. Es la decisión abierta 2 de SPEC2 §12. La pantalla del avance
   enseña su dirección con un botón de copiar; no se guarda el `id_obra` en el
   navegador, porque RD-02 solo permite guardar el borrador.

## 2. Decisiones de implementación

Son detalle de implementación, no de spec: cada una se puede cambiar sin tocar
SPEC2.

| Qué | Elección | Por qué |
| --- | --- | --- |
| Lenguaje | TypeScript en modo estricto | SPEC2 D-06 |
| Base | Vite (última estable) + React 19 + `@vitejs/plugin-react` con el React Compiler (`babel-plugin-react-compiler`) | Pila fijada; la skill pide el compilador en lugar de `useMemo` a mano |
| Tipos del contrato | `openapi-typescript` | Genera tipos desde `openapi.yaml` sin escribir nada a mano (RI-02) |
| Llamadas | `openapi-fetch` | Cliente de 6 kB que usa esos tipos: una ruta o un campo renombrado rompe al compilar |
| Rutas | `react-router` (modo declarativo) | Tres pantallas con dirección propia; recargar el avance o la lectura tiene que volver al mismo sitio |
| Estado del servidor | **Hooks propios mínimos**, sin biblioteca | SPEC2 §12 deja abierta la biblioteca. Tres pantallas con dos o tres consultas cada una no la necesitan, y escogerla ahora sería cerrar la decisión a ciegas |
| Estado global | Ninguno | Skill `frontend-react` §3 |
| Formularios | `useState` y los `<input>` nativos. Sin React Hook Form ni Zod | Un formulario de trece campos sin validación de dominio no lo justifica. La validación la hace el servidor |
| Estilos | CSS plano con variables, un fichero por pantalla más `compartido/estilos/` | Sin dependencias; se lee sin conocer ningún framework |
| Pruebas | `vitest` + `@testing-library/react` + `jsdom` + `msw` | La skill las nombra; `msw` simula el backend sin gastar |
| Reglas de fronteras | ESLint 9 con `typescript-eslint`, `eslint-plugin-react-hooks` y `no-restricted-imports` / `no-restricted-globals` | Es la «regla de fronteras del linter» que ya pide `validators.md` §6 |
| Versión del paquete | `frontend/package.json` lleva la de SPEC2, `1.0.0` | Mismo criterio que el backend con SPEC1 |
| Identidad visual | Colores corporativos: naranja `#FF7932` como acento y azul pizarra `#233441` como texto y base de los neutros, que tiran a azul en lugar de a gris. Logotipo en su versión oscura en la cabecera | Preferencia fijada para todo lo visual del proyecto |

El logotipo se descarga **una vez**, en el paso 1, a `frontend/public/logo.svg`
desde
`https://cdn.prod.website-files.com/6470655226e5e315462367b3/6479d296b3c5b295da00df57_Logo_Color_Dark.svg`.
Si la descarga falla, la cabecera lleva solo texto y se dice al terminar; no se
dibuja un logotipo a mano.

## 3. Árbol de ficheros

```
frontend/
  package.json            scripts de §5; version 1.0.0
  package-lock.json
  tsconfig.json           strict, noUncheckedIndexedAccess
  vite.config.ts          proxy /api (dev y preview) + React Compiler
  vitest.config.ts        jsdom, url http://localhost:5173, setup de msw
  eslint.config.js        reglas de fronteras (§6)
  index.html              lang="es"
  public/logo.svg
  scripts/
    generar-contrato.mjs  openapi.yaml -> src/compartido/api/esquema.d.ts
    arrancar.mjs          levanta backend + Vite con una sola orden
  src/
    main.tsx              monta el router
    rutas.tsx             las tres rutas y la de «no existe»
    compartido/
      api/
        esquema.d.ts      GENERADO. No se edita
        cliente.ts        único punto de salida HTTP; devuelve Resultado<T>
        fallos.ts         convierte cualquier respuesta fallida en un Fallo
        avance.ts         el flujo de progreso con reenganche (RNF-04)
        tipos.ts          alias legibles de components["schemas"][...]
      almacen-local.ts    leer/escribir JSON en localStorage con try/catch
      usar-consulta.ts    hook genérico: cargando / datos / fallo / reintentar
      componentes/
        Cabecera.tsx      logotipo + nombre de la pantalla
        AvisoDeFallo.tsx  mensaje del Fallo + botón de reintentar si procede
        Espera.tsx        «qué se está esperando» + segundos transcurridos
      estilos/
        tokens.css        colores, tipografía, espaciado; claro y oscuro
        base.css
    features/
      encargo/
        PantallaDelEncargo.tsx
        Conversacion.tsx       mensajes escritos y textos pegados
        FichaDelEncargo.tsx    el borrador por campos + lo entendido
        Resultado.tsx          faltan, no válidos, contradicciones, hechos
        usar-borrador.ts       estado persistido del encargo (RD-02)
        peticion.ts            borrador + textos + asumidas -> PeticionDeEntrevista
        campos.ts              etiqueta legible de cada ruta del brief
        encargo.css
      avance/
        PantallaDelAvance.tsx
        usar-avance.ts         foto inicial + flujo
        TareasAbiertas.tsx
        avance.css
      manuscrito/
        PantallaDelManuscrito.tsx
        agrupar.ts             unidades -> capítulos -> escenas (solo orden)
        manuscrito.css
  pruebas/
    servidor.ts               manejadores msw y respuestas de ejemplo
    EventSourceFalso.ts
    *.test.tsx                ver §7
```

No existe ninguna carpeta `services/`, `models/` ni `domain/` (RNF-03), y una
prueba lo vigila (§6).

## 4. Pasos, en orden

Cada paso tiene su comprobación. No se pasa al siguiente sin ella.

### Paso 1 — Andamiaje

- `estado: aprobada` en la cabecera de SPEC2.
- `npm create vite@latest` con la plantilla `react-ts` dentro de `frontend/`,
  y se quita lo de ejemplo (logo de Vite, contador, `App.css`).
- Dependencias de §2; `package-lock.json` commiteado.
- `vite.config.ts`:

  ```ts
  const proxy = {
    "/api": {
      target: "http://127.0.0.1:8000",
      changeOrigin: true,
      rewrite: (ruta: string) => ruta.replace(/^\/api/, ""),
    },
  };
  export default defineConfig({
    plugins: [react({ babel: { plugins: ["babel-plugin-react-compiler"] } })],
    server: { port: 5173, proxy },
    preview: { port: 4173, proxy },
  });
  ```

- Descargar el logotipo (§2).

**Comprobación:** `npm run build` termina sin errores.

### Paso 2 — Contrato y cliente (RI-01, RI-02, OBJ-05)

`scripts/generar-contrato.mjs` exporta una función y se ejecuta también como
orden. Es **la única** forma de producir `esquema.d.ts`, para que la orden y la
prueba den exactamente lo mismo:

```js
import openapiTS, { astToString } from "openapi-typescript";
const CONTRATO = new URL("../../backend/openapi.yaml", import.meta.url);
const DESTINO = new URL("../src/compartido/api/esquema.d.ts", import.meta.url);
const CABECERA =
  "// GENERADO desde backend/openapi.yaml por scripts/generar-contrato.mjs.\n" +
  "// No se edita a mano: si el borde cambia, se regenera (SPEC2 RI-02).\n";

export async function generar() {
  return CABECERA + astToString(await openapiTS(CONTRATO));
}
// Si se ejecuta como orden, escribe DESTINO.
```

Nadie tiene que acordarse de regenerar: `predev` y `prebuild` llaman al script,
así que arrancar o construir siempre usa el contrato vigente. Las pruebas **no**
regeneran antes: `pruebas/contrato.test.ts` hace lo mismo que el backend con
RNF-09 —genera, compara con el fichero commiteado y, **si difiere, lo reescribe
y falla una vez**—, para que el movimiento de la frontera aparezca en el diff y
se commitee junto al cambio que lo movió.

`compartido/api/cliente.ts`:

```ts
import createClient from "openapi-fetch";
import type { paths } from "./esquema";
import { falloDesde, falloDeRed, type Fallo } from "./fallos";

const base = new URL("/api", window.location.origin).href.replace(/\/$/, "");
const http = createClient<paths>({ baseUrl: base });

export type Resultado<T> = { ok: true; datos: T } | { ok: false; fallo: Fallo };

async function llamar<T>(peticion: () => Promise<{ data?: T; error?: unknown; response: Response }>)
  : Promise<Resultado<T>> {
  try {
    const { data, error, response } = await peticion();
    if (response.ok && data !== undefined) return { ok: true, datos: data };
    return { ok: false, fallo: falloDesde(response.status, error) };
  } catch {
    return { ok: false, fallo: falloDeRed() };
  }
}

// Una función por operación que usa v1 (RI-03 a RI-07), y ninguna más:
export const abrirEntrevista   = (cuerpo: PeticionDeEntrevista) => llamar(() => http.POST("/entrevistas", { body: cuerpo }));
export const pasarEntrevista   = (id: string, cuerpo: PeticionDeEntrevista) => llamar(() => http.POST("/entrevistas/{id_entrevista}/pasadas", { params: { path: { id_entrevista: id } }, body: cuerpo }));
export const verObra           = (id: string) => llamar(() => http.GET("/obras/{id_obra}", { params: { path: { id_obra: id } } }));
export const verProgresoAhora  = (id: string) => llamar(() => http.GET("/obras/{id_obra}/progreso/ahora", { params: { path: { id_obra: id } } }));
export const leerManuscrito    = (id: string) => llamar(() => http.GET("/obras/{id_obra}/manuscrito", { params: { path: { id_obra: id } } }));
export const detenerObra       = (id: string, motivo: string) => llamar(() => http.POST("/obras/{id_obra}/detener", { params: { path: { id_obra: id } }, body: { motivo } }));
export const reanudarObra      = (id: string) => llamar(() => http.POST("/obras/{id_obra}/reanudar", { params: { path: { id_obra: id } } }));
```

`compartido/api/fallos.ts` — el único sitio que sabe cómo viene un error:

```ts
export type Fallo =
  | { tipo: "sin_servidor"; mensaje: string }                    // red caída o Vite sin backend
  | { tipo: "rechazo"; estado: number; mensaje: string; campos: string[] };

// {"detail": "texto"}                -> rechazo con ese texto, sin tocarlo
// {"detalle": "texto", "campos": []} -> rechazo con texto y rutas
// {"detail": [ValidationError...]}   -> rechazo; mensaje = msg de cada uno, campos = loc sin el primer tramo
// cualquier otra cosa (sin JSON)     -> sin_servidor
```

El mensaje de `sin_servidor` es fijo: «No hay conexión con el servidor. Lo que
llevas hecho no se ha perdido.» Es el único texto de error que redacta la
interfaz; todos los demás son del servidor (RF-61).

`compartido/api/tipos.ts` solo da nombres cortos a los tipos generados
(`export type Progreso = components["schemas"]["Progreso"]`, etc.).

**Comprobación:** `npm run contrato` genera el fichero; `tsc --noEmit` pasa;
renombrar a mano un campo en una copia de `openapi.yaml` y regenerar hace
fallar la compilación de `cliente.ts` o de una pantalla (criterio 7 de §10).

### Paso 3 — Lo común

- `almacen-local.ts`: `leer<T>(clave, validar)` y `escribir(clave, valor)`,
  cada acceso en `try/catch`. Si lo guardado no se puede leer, se devuelve
  `null` y la pantalla lo dice («no se ha podido recuperar el borrador
  anterior»); nunca revienta.
- `usar-consulta.ts`: `usarConsulta(fn, deps)` → `{ estado: "cargando" |
  "listo" | "fallo", datos, fallo, reintentar }`. Sin caché compartida: cada
  pantalla pide lo suyo al entrar. Si el fallo es `sin_servidor`, reintenta sola
  cada 5 s y lo dice.
- `Espera.tsx`: recibe qué se espera («El Entrevistador está leyendo tu
  encargo») y cuenta los segundos. Con `aria-live="polite"`.
- `AvisoDeFallo.tsx`: pinta `fallo.mensaje` tal cual, los `campos` en una lista
  de rutas en monoespaciado, y el botón «Reintentar» cuando se le pasa una
  acción. Distingue visualmente `sin_servidor` (aviso) de `rechazo` (error).
- `tokens.css`: `--acento: #FF7932`, `--tinta: #233441`, neutros derivados de la
  pizarra, tipografía de interfaz del sistema y tipografía de lectura serif del
  sistema (`Iowan Old Style, Palatino, Georgia, serif`), sin fuentes externas:
  es una aplicación local. Tema oscuro con `prefers-color-scheme`.
- `rutas.tsx`:

  | Dirección | Pantalla |
  | --- | --- |
  | `/` | Encargo |
  | `/obras/:idObra` | Avance |
  | `/obras/:idObra/manuscrito` | Lectura |
  | cualquier otra | «Esta dirección no existe» con enlace al encargo |

**Comprobación:** pruebas unitarias de `fallos.ts` con los cuatro formatos, y de
`almacen-local.ts` con un `localStorage` que lanza excepción.

### Paso 4 — El encargo (RF-01 a RF-08)

**Lo que la persona ve.** Dos columnas en escritorio, una debajo de otra en
móvil:

- **Izquierda, la conversación.** Arriba, lo que la persona ha ido aportando, en
  orden: sus mensajes como burbujas («Tú») y cada texto pegado como una tarjeta
  aparte con la etiqueta «Texto pegado · N» y el texto plegado a unas líneas
  (RF-07). Cada tarjeta y cada mensaje se puede quitar antes del próximo envío.
  Debajo, el cuadro para escribir y dos botones: «Enviar» y «Pegar un texto»,
  que abre un área grande para pegar una carta o una anécdota. Al pie de la
  conversación, lo que ha contestado el sistema en la última pasada (`Resultado`),
  claramente separado de lo de la persona.
- **Derecha, la ficha del encargo.** Los campos del brief con etiqueta legible
  y, en pequeño, su ruta (`destinatario.edad`). Lo que la persona escribe aquí es
  el **borrador**. Si la última pasada trae un valor para un campo que el
  borrador tiene vacío, se enseña debajo como «Entendido: …» con un botón
  «Quedármelo» que lo copia al borrador. Los campos que la pasada dice que
  faltan se resaltan, buscándolos por su ruta tal como la manda el servidor.

**Qué va en cada pasada (RF-02).** Todo, siempre:

| Campo de `PeticionDeEntrevista` | De dónde sale |
| --- | --- |
| `borrador` | Solo lo que la persona ha escrito o se ha quedado en la ficha. Nunca el `brief_propuesto` entero: si se devolviera, lo que adivinó el agente pasaría a contar como escrito por la persona y ninguna pasada podría corregirlo (SPEC1 RF-73) |
| `textos` | Todos los mensajes y todos los textos pegados, en orden, como cadenas; los vacíos no se mandan |
| `contradicciones_asumidas` | Los tipos que la persona ha dado por buenos |

`peticion.ts` construye ese cuerpo y es una función pura con su prueba. Reglas
de limpieza, todas de forma, ninguna de dominio: una cadena vacía no se manda;
una lista solo se manda si la persona ha tocado ese campo (una lista presente,
aunque vacía, cuenta como escrita); `capitulos_objetivo` y `destinatario.edad` se
mandan como número; `destinatario` solo va si tiene algún campo.
`politicas_globales` no está en la ficha de v1: es opcional y no se pregunta.

**Lo que se guarda en el navegador (RF-06, RD-02).** `usar-borrador.ts` guarda
en `localStorage`, clave `my-story-maker.encargo`, versión 1, en cada cambio:

```ts
type BorradorGuardado = {
  version: 1;
  idEntrevista: string | null;
  borrador: BorradorDeBrief;
  camposTocados: string[];                               // rutas de lista tocadas
  aportaciones: { id: string; clase: "mensaje" | "pegado"; texto: string }[];
  asumidas: ("edad_contra_tono" | "texto_contra_campo")[];
};
```

La respuesta de la pasada **no se guarda**: es del servidor (RD-01). Tras
recargar, la pantalla conserva todo lo de la persona y dice «Tu encargo está
guardado. Envía para ver qué entiende el sistema».

**El envío.** Sin `idEntrevista`, `POST /entrevistas`; con él,
`POST /entrevistas/{id}/pasadas`. Mientras dura, la pantalla enseña `Espera`
con «El Entrevistador está leyendo tu encargo. Puede tardar un par de minutos»
y los segundos, y bloquea el envío doble. Al volver:

- Se guarda `id_entrevista`.
- `estado = "pendiente"`: se pinta el `Resultado`.
- `estado = "lanzada"`: se borra lo guardado y se navega a `/obras/{id_obra}`
  con `replace`, sin pedir confirmación (RF-05). Volver atrás no reabre la
  entrevista.

**El `Resultado` (RF-03, RF-04).** Se pinta lo que llega, sin decidir nada:

- «Te falta decirme»: la lista `faltan`, cada ruta con su etiqueta legible.
- «No puedo usar»: la lista `no_validos`.
- «Cosas que no casan»: una tarjeta por contradicción con su tipo en palabras
  (`edad_contra_tono` → «La edad no casa con el tono»; `texto_contra_campo` →
  «Un texto pegado dice otra cosa que un campo»), los campos por su ruta, la
  `evidencia` citada y el botón «Darla por buena». Al pulsarlo, su tipo entra en
  `asumidas` y la tarjeta se marca «La das por buena» con opción de deshacer. Si
  hay varias del mismo tipo, el botón avisa de que las da por buenas todas: el
  contrato asume por tipo.
- «Lo que he sacado de tus textos»: cada hecho con su campo y su cita literal.
- Los descartes (`hechos_descartados`, `contradicciones_descartadas`) como un
  recuento plegado, sin más.

**Fallos del envío (RF-08, RF-60 a RF-62).** Siempre con `AvisoDeFallo`, y
nada de lo escrito se pierde en ninguno:

| Qué vuelve | Qué dice y qué ofrece |
| --- | --- |
| `sin_servidor` | El mensaje fijo y «Reintentar», que reenvía el mismo cuerpo |
| 422 por tamaño | El mensaje del servidor, que ya dice cuánto sobra. Se sugiere quitar un texto pegado; no se quita ninguno |
| 422 de validación | `detalle` y sus `campos` resaltados en la ficha |
| 404 (entrevista que no existe) | El mensaje y «Empezar de nuevo con lo que llevo», que pone `idEntrevista` a `null` y conserva lo demás |
| 409 (la entrevista ya lanzó una obra) | El mensaje, que nombra la obra, y «Empezar un encargo nuevo», que descarta el borrador tras confirmarlo |
| 502 | El mensaje y «Reintentar» |

Siempre visible, abajo: «Descartar este encargo», con confirmación.

**Comprobación:** las pruebas del encargo de §7 pasan.

### Paso 5 — El avance (RF-20 a RF-25)

**`compartido/api/avance.ts`** es el único sitio que sabe que el avance llega
por SSE (RNF-04). Pasarlo a sondeo es reescribir este fichero y nada más:

```ts
export type EstadoDelFlujo = "conectando" | "en_directo" | "reconectando";
type Oyentes = {
  alProgreso: (p: Progreso) => void;
  alTerminar: () => void;              // llegó `terminada`; el flujo ya está cerrado
  alEstado: (e: EstadoDelFlujo, intentos: number) => void;
};
export function seguirElAvance(idObra: string, oyentes: Oyentes,
  fabrica: (url: string) => EventSource = (u) => new EventSource(u)): () => void
```

Por dentro: abre `EventSource` sobre `/api/obras/{id}/progreso` (la ruta se
comprueba contra `keyof paths` para que un cambio de contrato rompa aquí);
escucha `progreso` y `terminada` con `addEventListener`; en `open` pasa a
`en_directo` y pone a cero los intentos; en `error` **cierra** la conexión,
pasa a `reconectando` y la reabre él mismo tras 1, 2, 4, 8 y luego 15 s como
máximo, indefinidamente. El reenganche es propio y no el automático del
navegador porque el automático no se reintenta tras una respuesta de error y no
avisa de cuántas veces lleva. En `terminada`, cierra y avisa. Devuelve la
función que lo apaga todo, que la pantalla llama al desmontarse.

**`features/avance/usar-avance.ts`**:

1. Pide a la vez `verObra` y `verProgresoAhora` y pinta con eso (RF-21). Hasta
   que llegan, `Espera` con «Cargando la obra».
2. Solo después llama a `seguirElAvance`. Cada `progreso` reemplaza el
   anterior.
3. Vuelve a pedir la ficha cuando cambia `capitulo_en_curso` o `detenida`, y al
   terminar, porque los recuentos de capítulos cerrados solo vienen en ella.
4. En `terminada`, pide otra vez `verProgresoAhora`: si `detenida` es `true`, la
   obra está detenida; si no, ha terminado.

**Lo que se ve:**

- Cabecera con el título de la obra y un estado en palabras: «En marcha»,
  «Detenida», «Terminada», y al lado el estado de la conexión: «En directo»,
  «Conectando…», «Se ha cortado la conexión. Reconectando (intento N)…»
  (RF-22). Mientras reconecta se sigue viendo el último progreso, marcado como
  «última noticia hace N s».
- Capítulo en curso tal como viene, o «Ningún capítulo abierto ahora mismo» si
  es `null`. Capítulos cerrados, de la ficha.
- Tokens: «12 340 de 100 000 tokens de entrada a la vez», con las dos cifras tal
  cual y una barra cuyo ancho es su cociente (RF-25: se pintan, no se cuentan).
- Tabla `TareasAbiertas` con rol, tarea, capítulo, escena y tokens; vacía, dice
  «Sin tareas abiertas ahora mismo».
- Botones (RF-23): «Detener», con un diálogo que pide el motivo (opcional), y
  «Reanudar» cuando `detenida` es `true`. Tras cualquiera de los dos, se pide la
  foto otra vez y, si el flujo estaba cerrado, se vuelve a abrir. Mientras la
  orden viaja, el botón dice «Deteniendo…» o «Reanudando…».
- Siempre, «Leer lo que hay» → `/obras/{id}/manuscrito`. Al terminar se
  convierte en el botón principal: «Leer la novela» (RF-24).
- Al pie: «Para volver a esta obra, guarda esta dirección», con la dirección y
  un botón de copiar (hueco 2 de §1).

Fallos: `sin_servidor` al entrar → aviso con reintento automático; 404 → el
mensaje del servidor («No hay ninguna obra …») con enlace al encargo.

**Comprobación:** las pruebas del avance de §7 pasan.

### Paso 6 — La lectura (RF-40 a RF-43)

- Pide a la vez `verObra` y `leerManuscrito`.
- `agrupar.ts` convierte `unidades` en capítulos con sus escenas **respetando
  el orden en que llegan**: es presentación, no dominio. Un capítulo va marcado
  si alguna de sus unidades trae `capitulo_marcado`.
- Arriba, la ficha como recuento (RF-42): título, capítulos cerrados, capítulos
  marcados, críticas abiertas.
- A la izquierda, en escritorio, un índice fijo de capítulos con enlaces a
  `#capitulo-N` y su marca si la tienen; en móvil, un desplegable.
- El texto a ancho de lectura (unos 66 caracteres, `max-width: 38rem`),
  tipografía serif, interlineado amplio. Cada escena se parte en párrafos por
  las líneas en blanco y se pinta como texto: **nunca**
  `dangerouslySetInnerHTML`. Entre escenas, un separador `⁂`. Al final de cada
  capítulo, «Capítulo anterior» y «Capítulo siguiente».
- Capítulo marcado (RF-41, D-07): antes de su texto, un aviso en el color de
  acento: «Este capítulo tiene defectos sin resolver. Todavía no se puede ver
  cuáles.»
- Sin texto aceptado todavía: «Aún no hay ningún capítulo aceptado. Aparecerá
  aquí en cuanto se cierre el primero», con enlace al avance.
- Botón «Buscar texto nuevo» que vuelve a pedir las dos cosas: la obra puede
  estar a medio producir (RF-40).

**Comprobación:** las pruebas de la lectura de §7 pasan.

### Paso 7 — Reglas de fronteras (RI-01, RNF-01 a RNF-03)

`eslint.config.js`, además de las reglas recomendadas:

- En `src/features/**`: `no-restricted-globals` para `fetch`, `EventSource`,
  `XMLHttpRequest` y `WebSocket`; `no-restricted-imports` para `openapi-fetch`.
  Solo `src/compartido/api/**` habla con el servidor.
- En cada `src/features/<x>/**`: `no-restricted-imports` de las otras dos
  carpetas de `features/`.
- En todo `src/`: prohibido importar `node:fs`, `fs`, `path` o cualquier cosa
  de `../backend` (RNF-01). Los scripts de `scripts/` quedan fuera: son
  utillaje, no interfaz.

`pruebas/estructura.test.ts` comprueba lo que ESLint no ve: que no existe
ninguna carpeta `services`, `models` ni `domain` bajo `src/`, y que el único
fichero que importa `openapi-fetch` es `compartido/api/cliente.ts`.

**Comprobación:** `npm run lint` pasa, y añadir un `fetch` en una pantalla lo
hace fallar (se prueba y se deshace).

### Paso 8 — Pruebas y recorrido

Las pruebas de §7, todas contra `msw` y un `EventSource` falso. Después, un
recorrido en el navegador con el servidor de desarrollo:

- Con el backend **apagado**: las tres pantallas dicen que no hay servidor y
  ninguna se queda en blanco ni girando (criterio 5 de §10).
- Con el backend **encendido**: se abre `/obras/no-existe` y
  `/obras/no-existe/manuscrito` y se ve el 404 del servidor. Esto no gasta.
- **Lanzar una entrevista de verdad gasta**: se pregunta antes de hacerlo y, si
  no hay permiso, se deja dicho como pendiente.

Si la sesión tiene el navegador de `.claude/mcp.json`, el recorrido se hace con
él y se guardan capturas como evidencia; si no, se dice.

### Paso 9 — Docs (fase 3, SPEC2 §13)

Solo lo que dice SPEC2 §13, sin narrar historia:

- `AGENTS.md`: la fila de `frontend/` deja de decir que está vacía, y la
  introducción de «Alcance de esta rama» también.
- `docs/architecture.md` §7: el árbol pasa a `features/  encargo, avance,
  manuscrito` y el párrafo del avance dice que llega por SSE con foto inicial y
  reenganche.
- `.claude/skills/frontend-react/SKILL.md`: §2 nombra `encargo`, `avance` y
  `manuscrito`; §3 deja de decir que el avance está sin decidir. Después,
  `python .claude/skills/frontend-react/scripts/check-react-facts.py --offline`
  tiene que seguir pasando.
- `docs/validators.md`: el método de cada requisito de SPEC2 en la matriz de §8
  (sale de la tabla de §7 de este plan), y en §6 la frase «La mitad del cliente
  espera a que `frontend/` exista» pasa a describir la comprobación de RI-02.

Al cerrar cada fase —código y docs— se lanza el subagente `verificador` sobre
lo entregado. Quien escribió no se valida a sí mismo.

## 5. Órdenes

Todas desde `frontend/`. Ninguna es de mantenimiento: la regeneración del
contrato va colgada de las demás.

| Orden | Qué hace |
| --- | --- |
| `npm install` | Una vez por máquina |
| `npm run dev` | `scripts/arrancar.mjs`: arranca el backend (`backend/.venv` + `uvicorn novela.api.principal:app --port 8000`, con `backend/` como carpeta de trabajo para que use su base de siempre) si el puerto 8000 no responde ya, y después Vite. Al cerrar, apaga lo que haya arrancado. Resuelve la ruta del Python del entorno en Windows (`Scripts/python.exe`) y en Linux o macOS (`bin/python`) |
| `npm run build` | Construye `dist/` |
| `npm start` | Igual que `dev` pero sirviendo `dist/` con `vite preview` |
| `npm run comprobar` | `tsc --noEmit`, `eslint .` y `vitest run`: lo que se pasa antes de cada commit |
| `npm run contrato` | Regenera `esquema.d.ts` a mano, por si se quiere ver el diff antes de probar |

Hay que saberlo: arrancar el backend **relanza sola cualquier obra que se
quedara a medias** (SPEC1 D-33), y eso gasta. `arrancar.mjs` lo avisa en la
consola al arrancar.

## 6. Palabras en pantalla (RD-03, RD-04)

Solo se usan palabras que estén definidas en `docs/definitions.md` o en
`docs/architecture.md`: Obra, Capítulo, Escena, Brief, Destinatario, Recuerdo,
Entrevista, Entrevistador, Crítica, tokens de entrada, techo. Los valores de
vocabulario cerrado se pintan tal cual o con la etiqueta de `campos.ts` y del
tipo de contradicción, uno a uno, sin juntar dos en uno. Los roles de las tareas
abiertas se pintan como los manda el servidor. Al terminar el paso 9 se hace la
comprobación de RD-04: sacar las cadenas visibles de `src/` y buscar cada
palabra de dominio en los dos documentos.

## 7. Requisito por requisito

| Requisito | Dónde se cumple | Cómo se comprueba |
| --- | --- | --- |
| RF-01 | `PantallaDelEncargo`, `cliente.ts` | Prueba: la primera pasada va a `/entrevistas` y la segunda a `/entrevistas/{id}/pasadas` |
| RF-02 | `peticion.ts` | Prueba: tras dos mensajes, un texto pegado y una contradicción asumida, el cuerpo de la tercera pasada lleva todo |
| RF-03 | `Resultado.tsx`, `FichaDelEncargo.tsx` | Inspección: ningún `if` decide qué falta o qué choca; solo se recorren las listas recibidas |
| RF-04 | `Resultado.tsx` | Prueba: «Darla por buena» añade el tipo a la siguiente pasada y la tarjeta sigue, marcada |
| RF-05 | `PantallaDelEncargo` | Prueba: una respuesta `lanzada` navega a `/obras/{id}` y deja el almacenamiento vacío |
| RF-06 / OBJ-03 | `usar-borrador.ts` | Prueba: escribir, desmontar, volver a montar; todo sigue. Y el `localStorage` que lanza no rompe la pantalla |
| RF-07 | `Conversacion.tsx` | Inspección: los textos pegados van en tarjetas con su etiqueta, separadas de los mensajes y del `Resultado` |
| RF-08 | `AvisoDeFallo` | Prueba: el 422 de tamaño se enseña literal y ningún texto desaparece |
| RF-20 | `PantallaDelAvance` | Prueba con `EventSource` falso: cada `progreso` repinta capítulo, tareas y tokens |
| RF-21 | `usar-avance.ts` | Prueba: la pantalla enseña la foto de `/progreso/ahora` antes de que el flujo mande nada |
| RF-22 | `avance.ts` | Prueba: un `error` del flujo enseña «Reconectando», se reabre solo y el último progreso sigue en pantalla |
| RF-23 | `PantallaDelAvance` | Prueba: «Detener» manda el motivo; «Reanudar» aparece con `detenida` y vuelve a abrir el flujo |
| RF-24 | `usar-avance.ts` | Prueba: tras `terminada` con `detenida = false`, «Terminada» y «Leer la novela» |
| RF-25 | `PantallaDelAvance` | Inspección: los números salen de la respuesta sin operar, salvo el cociente de la barra |
| RF-40 | `PantallaDelManuscrito`, `agrupar.ts` | Prueba: unidades de dos capítulos se agrupan en orden |
| RF-41 | `PantallaDelManuscrito` | Prueba: el capítulo con `capitulo_marcado` lleva el aviso y el otro no |
| RF-42 | `PantallaDelManuscrito` | Prueba: los cuatro recuentos de la ficha salen en pantalla |
| RF-43 | `manuscrito.css` | Inspección con el navegador: ancho de lectura, índice, anterior y siguiente |
| RF-60 | `Espera`, `AvisoDeFallo`, `usar-consulta` | Prueba: con el servidor simulado caído, las tres pantallas dicen qué pasa |
| RF-61 | `fallos.ts` | Prueba de los cuatro formatos de error |
| RF-62 | `fallos.ts`, `cliente.ts` | Prueba: un fallo de red se pinta distinto de un rechazo y «Reintentar» manda el mismo cuerpo |
| RD-01 / RD-02 | `usar-borrador.ts` | Inspección: `localStorage` solo aparece en `almacen-local.ts` y solo lo usa el encargo |
| RD-03 / RD-04 | `campos.ts`, textos visibles | Análisis del paso 9 y de §6 |
| RI-01 | `cliente.ts`, `avance.ts` | Análisis: ESLint y `estructura.test.ts` |
| RI-02 / OBJ-05 | `generar-contrato.mjs` | Prueba: `contrato.test.ts` |
| RI-03 a RI-07 | `cliente.ts`, `avance.ts` | Las pruebas de sus pantallas |
| RNF-01 a RNF-03 | `eslint.config.js`, `estructura.test.ts` | Análisis |
| RNF-04 | `avance.ts` | Inspección: ninguna pantalla nombra `EventSource` (lo prohíbe además ESLint) |
| RNF-05 | Toda la interfaz | Inspección: sin texto en inglés visible, `lang="es"` |
| RNF-06 | `package.json`, `arrancar.mjs` | Demostración: `npm run dev` con el backend parado deja las dos cosas en pie |

## 8. Criterios de aceptación de SPEC2 §10

| Criterio | Cómo se cierra en este plan |
| --- | --- |
| 1. Borrador sin edad ni tono + carta pegada → se lanza sin salir de la web | Prueba con `msw`: la primera pasada devuelve `faltan: ["destinatario.edad", "destinatario.tono"]`, la segunda (con la carta) devuelve `lanzada`, y la pantalla salta al avance. Con el backend de verdad **gasta**: se hace solo con permiso |
| 2. Recargar a media conversación conserva todo | Prueba de RF-06 |
| 3. Una contradicción bloquea hasta que se asume | Prueba: pasada con contradicción → `pendiente`; se asume; la siguiente lleva el tipo y vuelve `lanzada` |
| 4. Flujo cortado → lo dice, se reengancha y no pierde el estado | Prueba de RF-22 |
| 5. Servidor caído → ninguna pantalla en blanco | Prueba de RF-60 y recorrido del paso 8 con el backend apagado |
| 6. Manuscrito a medias se lee; un capítulo marcado sale marcado | Pruebas de RF-40 y RF-41 |
| 7. Cambiar un campo del borde hace fallar la comprobación del cliente | Paso 2: se cambia un campo en una copia del contrato, se regenera y falla `tsc` o `contrato.test.ts`; se deshace |

## 9. Commits

Mínimos, en la rama en la que se lance, en español y con el mensaje de lo que
hacen:

1. `feat(frontend): interfaz v1 — encargo, avance y lectura` — SPEC2 aprobada,
   todo `frontend/` y sus pruebas.
2. `docs: el frontend v1 en la documentación` — el paso 9.

## 10. Lo que se entrega al terminar

Un resumen en lenguaje llano con: qué se puede hacer ya en la web, la tabla de
comprobaciones de `npm run comprobar` con su última línea, lo que dijo el
`verificador`, qué criterios de §8 se han cerrado con pruebas simuladas y cuáles
necesitan una obra real, y los dos huecos de §1 como candidatos a enmendar
SPEC1.
