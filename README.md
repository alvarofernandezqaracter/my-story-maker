# my-story-maker

Un generador de novelas históricas escrito por agentes de inteligencia
artificial. Tú escribes un encargo corto —la época, de qué va la historia y, si
quieres, a quién se la regalas— y el sistema escribe la novela entera, capítulo a
capítulo, revisándose a sí mismo por el camino. Al final la lees en el navegador
o la descargas en PDF.

## Qué hace, en pocas palabras

- **El encargo se llama *brief*.** Es una ficha con el título, la época, la
  premisa y cuántos capítulos quieres. Si la novela es un regalo, lleva también
  al *destinatario*: su nombre, su edad, el tono que le gusta, la dedicatoria,
  algún recuerdo suyo y las palabras que no quiere leer. La novela sigue siendo
  histórica; el destinatario aparece dentro de ella.
- **Lo escriben agentes.** Un *agente* es un programa de IA con un solo trabajo:
  uno planifica, otro redacta, otro busca documentación de la época, otro
  critica lo redactado… Ninguno revisa su propio trabajo. Aquí cada agente es
  una sesión de [Claude Code](https://claude.com/claude-code), la herramienta de
  Anthropic, lanzada sin nadie delante.
- **Nadie tiene que intervenir por el camino.** Lanzas el encargo y te olvidas.
  Si el equipo se apaga a mitad, la novela sigue desde el último capítulo
  terminado en cuanto vuelves a arrancar.
- **Todo se guarda en un único fichero de base de datos** (SQLite, una base de
  datos que es un solo fichero y no necesita servidor). No hay carpetas de
  trabajo que limpiar.

El repositorio tiene dos partes: el **backend**, el servidor que guarda la obra
y dirige a los agentes (en Python), y el **frontend**, la página web desde la
que se encarga y se lee (en React). La web nunca toca la base de datos: todo se
lo pide al servidor.

## Qué necesitas instalado

| Programa | Para qué | Cómo comprobar que lo tienes |
| --- | --- | --- |
| Python 3.13 | El servidor | `python --version` |
| Node.js (el proyecto se desarrolla con la 24) | La página web | `node --version` |
| Claude Code, con tu sesión iniciada | Es quien ejecuta a los agentes. El servidor no usa ninguna clave de API: lanza la orden `claude` de tu equipo | `claude --version` |
| Lean 4, con su instalador `elan` (opcional) | Comprueba que la cronología de la novela no se contradice antes de publicarla. Sin él la novela se publica igual, marcada como «sin comprobar». Se instala siguiendo <https://lean-lang.org/install/>; la versión la elige solo | `lake --version` |

En Windows, las órdenes de este documento están pensadas para **Git Bash** (la
consola que viene con Git). En PowerShell algunas cambian.

## Instalación, desde cero

Todas las órdenes se lanzan desde la carpeta raíz del repositorio.

**1. El servidor.** Crea su entorno de Python —una carpeta `.venv` con sus
propias librerías, para no mezclarlas con las del sistema— e instala el
backend dentro:

```sh
cd backend
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"   # en Linux o macOS: .venv/bin/python
cd ..
```

**2. La página web.** Descarga sus librerías:

```sh
cd frontend
npm install
cd ..
```

**3. La configuración.** Copia la plantilla de variables de entorno —ajustes
que el programa lee al arrancar en lugar de llevarlos escritos en el código— y
rellena lo que vayas a usar:

```sh
cp .env.example .env
```

Cada variable de [`.env.example`](.env.example) explica qué es y de dónde se
saca. El fichero `.env` es tuyo y nunca se sube al repositorio: ahí van tus
claves. El backend lo lee por su cuenta al arrancar.

## Cómo se arranca

```sh
cd frontend
npm run dev
```

Esta sola orden arranca el servidor en el puerto 8000 y la web en
<http://localhost:5173>. Para pararlo todo, `Ctrl+C` en esa consola.

La web abre en el **taller**: un tablero, como el de un gestor de proyectos, con
todas tus obras repartidas en cuatro columnas según su situación —en producción,
detenida, terminada y publicada—. Pulsa una para entrar en ella; dentro, un
lateral salta entre su avance, sus tareas, la lectura y sus versiones. Una obra
detenida dice en su tarjeta por qué se detuvo.

> **Ojo, que gasta.** Al arrancar, el servidor retoma solo cualquier novela que
> se quedara a medias. Cada novela en marcha lanza agentes, y los agentes
> cuestan dinero.

Si solo quieres el servidor, sin la web:

```sh
cd backend
.venv/Scripts/python -m uvicorn novela.api.principal:app --host 127.0.0.1 --port 8000
```

La base de datos se crea sola la primera vez, como `backend/novela.sqlite3`.

## Un brief de ejemplo, de principio a fin

[`ejemplos/brief-de-ejemplo.json`](ejemplos/brief-de-ejemplo.json) es un
encargo pequeño, de un solo capítulo, pensado solo para ver que todo funciona:
una aventura en el Toledo del siglo XVI dedicada a una niña inventada. Lleva un
recuerdo suyo de hoy —unas llaves en la nevera— para ver cómo entra en la
historia sin que el sistema lo trate como un error de época.

**Lanzarlo gasta dinero**: pone a trabajar a los agentes de verdad.

**1. Arranca el sistema** como se explica arriba y deja esa consola abierta.

**2. Lanza el encargo.** En otra consola, desde la raíz del repositorio:

```sh
curl -X POST http://127.0.0.1:8000/obras \
  -H "Content-Type: application/json" \
  --data-binary @ejemplos/brief-de-ejemplo.json
```

La respuesta trae el identificador de la obra, algo como
`{"id_obra": "obr_…", "estado": "en produccion"}`. Apúntalo: a partir de aquí
lo llamamos `ID`. Es la única orden que hay que dar; lo demás lo hace el
sistema.

**3. Mírala avanzar** en <http://localhost:5173/obras/ID>, o desde la consola:

```sh
curl http://127.0.0.1:8000/obras/ID/progreso/ahora
```

**4. Léela** cuando termine, en <http://localhost:5173/obras/ID/manuscrito>. O
descárgala en PDF:

```sh
curl -o novela.pdf http://127.0.0.1:8000/obras/ID/pdf
```

**5. Publícala**, si quieres, desde la pantalla de versiones
(<http://localhost:5173/obras/ID/versiones>) o con:

```sh
curl -X POST http://127.0.0.1:8000/obras/ID/versiones/1/publicar
```

Antes de publicar, el sistema pasa sus comprobaciones finales. Si alguna falla,
no publica y dice cuál y en qué capítulo.

**Por la web, sin consola.** Con «+ Nueva obra», arriba a la derecha
(<http://localhost:5173/encargo>), se encarga la misma novela conversando: escribes lo que tengas —o pegas una carta, una anécdota— y
un agente, el Entrevistador, te pregunta lo que falta. En cuanto el encargo está
completo, la novela se lanza sola. Es más cómodo, pero cada vuelta de la
conversación también lanza un agente; el fichero de arriba se lanza de una vez.

**Si quieres pararla** a medias:

```sh
curl -X POST http://127.0.0.1:8000/obras/ID/detener \
  -H "Content-Type: application/json" -d '{"motivo": "prueba"}'
curl -X POST http://127.0.0.1:8000/obras/ID/reanudar     # sigue donde se quedó
```

Con el servidor en marcha, <http://127.0.0.1:8000/docs> enseña todas las
operaciones que ofrece, con sus campos, y deja probarlas desde el navegador.

## Dónde está cada cosa

| Carpeta o fichero | Qué hay |
| --- | --- |
| [`backend/`](backend/) | El servidor, sus pruebas y los modelos formales del flujo |
| [`frontend/`](frontend/) | La página web |
| [`docs/`](docs/) | Cómo es el sistema: el vocabulario de la novela, la arquitectura y cómo se comprueba cada cosa. [`docs/proceso.md`](docs/proceso.md) reúne la documentación de cómo se ha construido |
| [`specs/`](specs/) | Qué tiene que hacer cada parte y por qué |
| [`ejemplos/`](ejemplos/) | El brief de ejemplo |
| [`presentacion/`](presentacion/) | La presentación del proyecto |
| [`AGENTS.md`](AGENTS.md) | Las reglas del proyecto, para quien lo desarrolla |
| [`CLAUDE.md`](CLAUDE.md) | Lo que Claude Code necesita saber para desarrollar aquí |

## Para quien lo desarrolla

Las pruebas del servidor se lanzan desde `backend/` y no gastan nada:

```sh
cd backend
.venv/Scripts/python -m pytest
```

Las que ponen a trabajar agentes de verdad llevan la marca `gasta` y quedan
fuera por defecto. Las de la web, desde `frontend/`, con `npm run comprobar`; y
`npm run validar-visual` abre la lectura en un navegador sin ventana y comprueba
que la portada, el índice y la ficha de personajes se ven.

Cómo se hace un cambio —primero la spec, luego el código, luego los
documentos— está en [`AGENTS.md`](AGENTS.md).
