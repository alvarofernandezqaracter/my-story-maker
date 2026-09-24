"""Un backend de prueba sembrado, para el validador visual (SPEC2 RF-78).

    python tests/servidor_sembrado.py --puerto 8765

Levanta la API con el ejecutor fingido —no lanza ningun subagente ni gasta—
sobre una base temporal, da de alta una obra de tres capitulos con destinatario
y dedicatoria, espera a que termine y escribe en la salida una linea JSON con
el `id_obra` y el puerto. Sigue sirviendo hasta que se cierra su entrada; al
pararse, la base temporal se borra. No es parte del sistema: vive en `tests/` junto al
ejecutor fingido que usa.
"""

import argparse
import contextlib
import json
import sys
import tempfile
import threading
import time
from pathlib import Path

import httpx
import uvicorn

from dobles import EjecutorFingido
from novela.api.aplicacion import crear_aplicacion

BRIEF = {
    "titulo": "El taller de la calle de las Sierpes",
    "epoca": "Sevilla, 1587",
    "premisa": "Una impresora clandestina",
    "politicas_globales": {"pov": "tercera_limitada"},
    "capitulos_objetivo": 3,
    "destinatario": {
        "nombre": "Lucía",
        "edad": 40,
        "tono": "calido",
        "dedicatoria": "Para Lucía, que me enseñó a leer entre pliegos",
        "rasgos": [],
        "recuerdos": [],
        "vetos": [],
    },
}

PROSA = "Lucía cruzó el taller antes del alba. " + "La tinta olía a nuez. " * 120


def main() -> int:
    argumentos = argparse.ArgumentParser()
    argumentos.add_argument("--puerto", type=int, required=True)
    puerto = argumentos.parse_args().puerto

    with tempfile.TemporaryDirectory(prefix="novela-sembrada-") as carpeta:
        app = crear_aplicacion(
            Path(carpeta) / "sembrada.sqlite3",
            ejecutor=EjecutorFingido(texto_cosido=PROSA),
        )
        servidor = uvicorn.Server(
            uvicorn.Config(app, host="127.0.0.1", port=puerto, log_level="warning")
        )
        hilo = threading.Thread(target=servidor.run, daemon=True)
        hilo.start()
        base = f"http://127.0.0.1:{puerto}"
        with httpx.Client(base_url=base, timeout=10) as cliente:
            for _ in range(200):
                try:
                    cliente.get("/openapi.json")
                    break
                except httpx.TransportError:
                    time.sleep(0.1)
            id_obra = cliente.post("/obras", json=BRIEF).json()["id_obra"]
            for _ in range(600):
                versiones = cliente.get(f"/obras/{id_obra}/versiones").json()
                if versiones and versiones[-1]["terminada"]:
                    break
                time.sleep(0.2)
            else:
                print(json.dumps({"error": "la obra sembrada no termino"}), flush=True)
                return 1
        print(json.dumps({"id_obra": id_obra, "puerto": puerto}), flush=True)
        # Sirve hasta que quien lo lanzo cierra su entrada: asi se para limpio y
        # la base temporal se borra al salir del `with`.
        with contextlib.suppress(KeyboardInterrupt):
            sys.stdin.read()
        servidor.should_exit = True
        hilo.join(timeout=5)
    return 0


if __name__ == "__main__":
    sys.exit(main())
