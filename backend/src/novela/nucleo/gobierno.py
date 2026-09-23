"""Los permisos por rol, impuestos por el backend y no por el prompt.

Lo que impide que un rol haga lo que no le toca no es una instruccion en su
prompt, que es una peticion y no una garantia: es esta tabla, mas el hecho de
que cada tarea arranque sin mas herramientas que las que su contrato le
concede. Sale de la tabla de entrada y salida de `architecture.md` 2 y de la
tabla de gobierno de `architecture.md` 6.

Es lo que hace cumplir las reglas de integridad del censo sin depender de que
nadie las recuerde, y lo que se comprueba enumerando rol por rol e intentando
la escritura prohibida.
"""

from novela.vocabularios import ROLES

TODOS_LOS_ROLES: frozenset[str] = frozenset(ROLES)

# Los que trabajan sobre una obra ya dada de alta. El Entrevistador actua antes
# de que exista y no escribe nada en el almacen: devuelve una propuesta de brief.
ROLES_DE_LA_OBRA: frozenset[str] = TODOS_LOS_ROLES - {"entrevistador"}


class EscrituraNoAutorizada(Exception):
    """Un rol ha intentado escribir una entidad que no le corresponde."""


class HerramientaNoConcedida(Exception):
    """Un rol ha intentado usar una herramienta que su contrato no le da."""


# Quien puede escribir cada entidad. Lo que no esta aqui no lo escribe nadie:
# `Obra` y `Recuerdo` los da de alta el editor con el brief, y `Agente`, `Tarea`
# y `Traza` las registra el backend al repartir turnos, no un rol.
QUIEN_ESCRIBE: dict[str, frozenset[str]] = {
    # Capa Mundo
    "Personaje": frozenset({"constructor_de_mundo"}),
    "Lugar": frozenset({"constructor_de_mundo"}),
    "Objeto": frozenset({"constructor_de_mundo"}),
    "Faccion": frozenset({"constructor_de_mundo"}),
    "Fuente": frozenset({"documentalista"}),
    "Concepto": frozenset({"documentalista"}),
    "Practica": frozenset({"documentalista"}),
    "RegistroLinguistico": frozenset({"documentalista"}),
    "Evento": frozenset({"planificador", "documentalista"}),
    # Capa Obra
    "Parte": frozenset({"planificador"}),
    "Capitulo": frozenset({"planificador", "revisor"}),
    "Escena": frozenset({"planificador", "revisor"}),
    "Beat": frozenset({"planificador"}),
    "Parrafo": frozenset({"redactor", "editor_de_estilo"}),
    "Compromiso": frozenset({"planificador", "redactor"}),
    # Capa Produccion
    "Plan": frozenset({"planificador"}),
    "Borrador": frozenset({"redactor", "revisor", "editor_de_estilo"}),
    "Critica": frozenset(
        {
            "verificador_de_continuidad",
            "editor_de_estilo",
            "arquitecto_de_arcos",
            "juez_de_rubrica",
        }
    ),
    "Revision": frozenset({"revisor"}),
    "EventoEstado": frozenset({"contable_de_estado"}),
    "ResumenCapitulo": frozenset({"archivero"}),
    "Decision": ROLES_DE_LA_OBRA,
    "Obra": frozenset(),
    "Recuerdo": frozenset(),
    "Agente": frozenset(),
    "Tarea": frozenset(),
    "Traza": frozenset(),
}

# Con que sale cada rol al exterior. Solo el Documentalista sale, y sale a
# buscar fuentes: ningun otro tiene herramienta con la que hacerlo. Lo que trae
# entra como dato delimitado, nunca como instruccion.
HERRAMIENTAS_POR_ROL: dict[str, frozenset[str]] = {
    rol: frozenset() for rol in ROLES
} | {"documentalista": frozenset({"WebSearch", "WebFetch"})}

HERRAMIENTAS_QUE_SALEN_AL_EXTERIOR: frozenset[str] = frozenset({"WebSearch", "WebFetch"})


def puede_escribir(rol: str, tipo: str) -> bool:
    if rol not in TODOS_LOS_ROLES:
        raise KeyError(f"{rol!r} no esta en el censo")
    return rol in QUIEN_ESCRIBE.get(tipo, frozenset())


def comprobar_escritura(rol: str, tipo: str) -> None:
    """Parar aqui cuesta una vuelta; dejar pasar la escritura corrompe la obra."""
    if not puede_escribir(rol, tipo):
        raise EscrituraNoAutorizada(
            f"el rol {rol!r} no escribe {tipo!r}: la tabla de gobierno no se lo asigna"
        )


def escrituras_de(rol: str) -> frozenset[str]:
    if rol not in TODOS_LOS_ROLES:
        raise KeyError(f"{rol!r} no esta en el censo")
    return frozenset(tipo for tipo, roles in QUIEN_ESCRIBE.items() if rol in roles)


def comprobar_herramienta(rol: str, herramienta: str) -> None:
    if herramienta not in HERRAMIENTAS_POR_ROL[rol]:
        raise HerramientaNoConcedida(
            f"el rol {rol!r} no tiene concedida la herramienta {herramienta!r}"
        )


# --- Reglas de integridad del censo, comprobadas al importar ---------------
# Ningun agente valida su propia salida.
assert "redactor" not in QUIEN_ESCRIBE["Critica"], "el Redactor no emite Critica"
assert "verificador_de_continuidad" not in QUIEN_ESCRIBE["Borrador"]
assert "juez_de_rubrica" not in QUIEN_ESCRIBE["Borrador"]
# El Revisor aplica criticas ajenas; no puede crear las suyas.
assert "revisor" not in QUIEN_ESCRIBE["Critica"]
# El mundo solo cambia por EventoEstado del Contable.
assert QUIEN_ESCRIBE["EventoEstado"] == frozenset({"contable_de_estado"})
# Un dato historico sin Fuente es una alucinacion, y solo el Documentalista la
# escribe; ademas es el unico con salida al exterior.
assert QUIEN_ESCRIBE["Fuente"] == frozenset({"documentalista"})
# Un `Recuerdo` no es una `Fuente` de tipo nuevo: nace con el alta de la obra y
# ningun rol lo escribe, que es lo que deja intacto el invariante de arriba.
assert QUIEN_ESCRIBE["Recuerdo"] == frozenset()
assert {
    rol
    for rol, herramientas in HERRAMIENTAS_POR_ROL.items()
    if herramientas & HERRAMIENTAS_QUE_SALEN_AL_EXTERIOR
} == {"documentalista"}
# El Entrevistador no escribe ninguna entidad: ni siquiera `Recuerdo`, que nace
# del alta de la obra con la cita literal que la persona entrego.
assert escrituras_de("entrevistador") == frozenset()
# El Archivero no escribe hechos del mundo ni prosa.
assert escrituras_de("archivero") <= {"ResumenCapitulo", "Decision"}
