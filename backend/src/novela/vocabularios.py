"""Vocabularios controlados: los valores cerrados del sistema.

Nada de texto libre donde hay vocabulario controlado: los valores cerrados son
lo que hace computables los predicados de calidad. Los de proceso salen de
`architecture.md` 2 y los de forma y de mundo de `definitions.md`. Este fichero
no inventa ninguno: si un valor esta aqui y no en esos documentos, es un
defecto de aqui.
"""

# --- Censo de agentes (architecture.md 2) ---------------------------------

ROLES: tuple[str, ...] = (
    "constructor_de_mundo",
    "documentalista",
    "arquitecto_de_arcos",
    "planificador",
    "redactor",
    "contable_de_estado",
    "verificador_de_continuidad",
    "editor_de_estilo",
    "juez_de_rubrica",
    "revisor",
    "archivero",
    # Actua antes de que la obra exista y no escribe nada en el almacen: completa
    # el brief y devuelve una propuesta (SPEC1 4.8).
    "entrevistador",
)

TIPOS_DE_TAREA: tuple[str, ...] = (
    "poblar_mundo",
    "documentar",
    "auditar",
    "planificar",
    "redactar",
    "plegar",
    "verificar",
    "editar_estilo",
    "juzgar",
    "revisar",
    "destilar",
    "entrevistar",
)

# Un rol, una tarea: la correspondencia es biyectiva por invariante.
TAREA_DE_ROL: dict[str, str] = {
    "constructor_de_mundo": "poblar_mundo",
    "documentalista": "documentar",
    "arquitecto_de_arcos": "auditar",
    "planificador": "planificar",
    "redactor": "redactar",
    "contable_de_estado": "plegar",
    "verificador_de_continuidad": "verificar",
    "editor_de_estilo": "editar_estilo",
    "juez_de_rubrica": "juzgar",
    "revisor": "revisar",
    "archivero": "destilar",
    "entrevistador": "entrevistar",
}

ROL_DE_TAREA: dict[str, str] = {tarea: rol for rol, tarea in TAREA_DE_ROL.items()}

# --- Vocabularios de proceso (architecture.md 2) ---------------------------

SEVERIDAD: tuple[str, ...] = ("bloqueante", "mayor", "menor", "sugerencia")

ESTADO_DE_PRODUCCION: tuple[str, ...] = (
    "planificado",
    "redactado",
    "en_revision",
    "aceptado",
    "descartado",
)

# Lo que el Entrevistador puede senalar en un brief (SPEC1 RF-76). No lo
# resuelve: lo devuelve como pregunta, y la persona puede darlo por asumido.
TIPO_DE_CONTRADICCION: tuple[str, ...] = ("edad_contra_tono", "texto_contra_campo")

TIPO_DE_EVENTO_ESTADO: tuple[str, ...] = (
    "aparece",
    "muere",
    "viaja_a",
    "adquiere",
    "pierde",
    "aprende",
    "revela_a",
    "cambia_relacion",
    "cambia_estado_civil_o_rango",
    "transcurre_tiempo",
)

# Ciclo de vida del capitulo (architecture.md 4). No es el estado de produccion
# de un borrador: nombra en que punto del guion esta el capitulo entero.
CICLO_DE_VIDA_DEL_CAPITULO: tuple[str, ...] = (
    "planificado",
    "redactado",
    "validado",
    "en_revision",
    "aceptado",
    "cerrado",
    "descartado",
)

# Que pasa cuando una tarea agota sus intentos (SPEC1 4.10, RF-96). Lo declara
# cada paso del guion: `detener_obra` para lo que produce el testigo del paso
# siguiente, `critica_abierta` para las comprobaciones y `seguir` para lo que,
# como la busqueda documental, no bloquea nunca (D-09).
AL_AGOTARSE: tuple[str, ...] = ("detener_obra", "critica_abierta", "seguir")

# Los hooks `Stop` que puede llevar el subagente de un paso (SPEC1 4.13, RF-120):
# `validar_capitulo` mira la forma de lo entregado y `policy`, lo vetado.
GANCHOS: tuple[str, ...] = ("validar_capitulo", "policy")

# De que lista sale cada veto que mira `policy` (SPEC1 4.14, RF-130): la global
# de la instalacion y, de los vetos del brief, los de una palabra y los de varias.
NIVEL_DE_VETO: tuple[str, ...] = ("global", "palabra_del_comprador", "tema_del_comprador")

# Que hizo `policy` con una coincidencia (RF-135): devolverla al agente en la
# sesion para que corrija, o dar el intento por fallido en el veredicto final.
DECISION_DE_POLICY: tuple[str, ...] = ("devuelto_al_agente", "intento_fallido")

# Que validador da cada fallo de la puerta de publicacion (SPEC1 4.15, RF-140).
VALIDADOR_DE_LA_PUERTA: tuple[str, ...] = (
    "esquema",
    "nombres",
    "longitud",
    "elementos_personalizados",
    # El validador formal de la cronologia, con Lean (SPEC1 4.16, RF-153).
    "cronologia",
)

# Que invariante de la cronologia demuestra Lean suceso a suceso (SPEC1 4.16,
# RF-151). Van en el orden en que el volcado escribe sus teoremas.
INVARIANTE_DE_LA_CRONOLOGIA: tuple[str, ...] = (
    "orden_temporal",
    "edad_coherente",
    "un_solo_lugar",
    "no_reaparece",
)

# Como quedo la comprobacion formal de una version (RF-152, D-61): Lean la
# demostro, Lean no pudo demostrarla, o Lean no esta en la maquina y no se hizo.
COMPROBACION_FORMAL: tuple[str, ...] = ("demostrada", "fallida", "sin_comprobacion")

# Las tres memorias (architecture.md 3). Cada artefacto declara a cual pertenece
# porque es lo que permite al Archivero retirar la de capitulo sin decidir nada.
MEMORIA: tuple[str, ...] = ("tarea", "capitulo", "obra")

METODO_DE_VERIFICACION: tuple[str, ...] = (
    "prueba",
    "analisis",
    "inspeccion",
    "demostracion",
    "inverificable",
)

# --- Vocabularios de forma textual (definitions.md) ------------------------

POV: tuple[str, ...] = (
    "primera",
    "tercera_limitada",
    "tercera_omnisciente",
    "epistolar",
    "mixta",
)

MODO_DEL_PARRAFO: tuple[str, ...] = (
    "escena",
    "sumario",
    "descripcion",
    "dialogo",
    "monologo_interior",
    "digresion",
)

FUNCION_ESTRUCTURAL: tuple[str, ...] = (
    "setup",
    "escalada",
    "giro",
    "revelacion",
    "respiro",
    "pago",
    "resolucion",
)

TIPO_DE_BEAT: tuple[str, ...] = (
    "accion",
    "reaccion",
    "decision",
    "revelacion",
    "transicion",
)

ESTADO_DE_COMPROMISO: tuple[str, ...] = ("abierto", "reforzado", "pagado", "abandonado")

# --- Vocabularios de mundo (definitions.md) --------------------------------

ESTATUS_ONTOLOGICO: tuple[str, ...] = ("historico", "ficticio", "compuesto")

# `personal` es lo que viene de la vida del destinatario (RD-17). Es inmutable
# como `canon`, pero su respaldo no es una `Fuente` sino un `Recuerdo`, y por eso
# queda exento de las cuatro dimensiones de anacronismo: el nombre de hoy se
# escribe tal cual (D-12).
LICENCIA: tuple[str, ...] = ("canon", "plausible", "licencia", "personal")

LICENCIA_EXENTA_DE_ANACRONISMO: str = "personal"

# Que papel se le da al destinatario dentro de la obra. Lo decide el
# Planificador y lo deja escrito en el `Plan`: ni el editor lo elige ni el
# validador lo supone (D-14).
PAPEL_DEL_DESTINATARIO: tuple[str, ...] = (
    "protagonista",
    "secundario",
    "testigo",
    "narrador",
)

TIPO_DE_FUENTE: tuple[str, ...] = ("primaria", "secundaria", "divulgativa", "sin_respaldo")

TIPO_DE_ANACRONISMO: tuple[str, ...] = (
    "material",
    "lexico",
    "conceptual",
    "social",
    "institucional",
)

# --- Dimensiones de calidad (definitions.md, repartidas en validators.md 4) -

DIMENSIONES_LOCALES: tuple[str, ...] = (
    "anacronismo_material",
    "anacronismo_conceptual",
    "anacronismo_social_e_institucional",
    "anacronismo_lexico",
    "fatiga_lexica",
    "tics_de_modelo",
    "coherencia_de_voz",
)

DIMENSIONES_DE_ESCENA_Y_CAPITULO: tuple[str, ...] = (
    "cumplimiento_del_contrato",
    "cambio_de_valor",
    "integridad_de_pov",
    "violacion_epistemica",
    "continuidad_de_estado",
    "coherencia_temporal",
    "ritmo",
)

DIMENSIONES_GLOBALES: tuple[str, ...] = (
    "progresion_de_arcos",
    "economia_narrativa",
    "curva_de_tension",
    "distribucion_de_revelaciones",
    "fidelidad_historica",
    "cobertura_documental",
    "obra_cerrada_sin_defectos_abiertos",
)

DIMENSIONES: tuple[str, ...] = (
    DIMENSIONES_LOCALES + DIMENSIONES_DE_ESCENA_Y_CAPITULO + DIMENSIONES_GLOBALES
)

# --- Tipos de artefacto ----------------------------------------------------

TIPOS_DE_LA_CAPA_OBRA: tuple[str, ...] = (
    "Obra",
    "Parte",
    "Capitulo",
    "Escena",
    "Beat",
    "Parrafo",
    "Compromiso",
    "Mencion",
)

TIPOS_DE_LA_CAPA_MUNDO: tuple[str, ...] = (
    "Personaje",
    "Lugar",
    "Evento",
    "Objeto",
    "Faccion",
    "Practica",
    "Concepto",
    "RegistroLinguistico",
    "Fuente",
    "Recuerdo",
)

# Los hechos de la biblia: las fichas del mundo que el texto nombra. Son las que
# registran en que capitulos se usan (RF-80). `Fuente`, `Concepto`, `Practica`
# y `RegistroLinguistico` respaldan o filtran el texto sin ser algo de lo que el
# texto hable, y el `Recuerdo` es la materia prima de la ficha, no la ficha.
HECHOS_DE_LA_BIBLIA: tuple[str, ...] = ("Personaje", "Lugar", "Objeto", "Faccion", "Evento")

TIPOS_DE_LA_CAPA_PRODUCCION: tuple[str, ...] = (
    "Agente",
    "Tarea",
    "Plan",
    "Borrador",
    "Critica",
    "Revision",
    "Decision",
    "EventoEstado",
    "ResumenCapitulo",
    "Traza",
)

TIPOS_DE_ARTEFACTO: tuple[str, ...] = (
    TIPOS_DE_LA_CAPA_OBRA + TIPOS_DE_LA_CAPA_MUNDO + TIPOS_DE_LA_CAPA_PRODUCCION
)
