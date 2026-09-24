# Ontología de novela histórica — Diagramas Mermaid

2026-09-21 · [NOMBRE_ANONIMIZADO]

## Cómo leer estos diagramas

Seis diagramas Mermaid que acompañan al documento de definiciones. Cada uno responde a una pregunta distinta; no hay un único árbol porque la ontología no es un árbol, es un grafo con varias jerarquías superpuestas.

| Diagrama | Responde a |
| --- | --- |
| 1. Árbol de la obra | ¿Cómo se descompone el texto? |
| 2. Árbol del mundo | ¿Qué tipos de referente existen? |
| 3. Relaciones | ¿Qué conecta con qué y de qué forma? |
| 4. Contrato de escena | ¿Qué hace falta para generar una escena? |
| 5. Árbol de calidad | ¿Qué se mide y dónde? |
| 6. Vocabularios | ¿Qué valores cerrados existen? |

Los diagramas de la capa de producción —mapa de capas, entidades de producción, flujo de contexto y ciclo de vida del capítulo— están en `architecture.md`.

**Convenciones:** los nodos en `PascalCase` son entidades, en minúscula son atributos o valores. Las flechas sin etiqueta indican composición o especialización; las etiquetadas, relaciones con nombre propio.

## 1. Árbol de la capa Obra

```mermaid
flowchart TD
  OBRA[Obra] --> PARTE[Parte / Acto]
  PARTE --> CAP[Capitulo]
  CAP --> ESC[Escena]
  ESC --> BEAT[Beat]
  ESC --> PAR[Parrafo]
  CAP --> MEN[Mencion]
  MEN -.- MA[id del hecho<br/>capitulo]
  OBRA -.- OA[epoca<br/>premisa<br/>politicas globales]
  CAP -.- CA[numero<br/>POV dominante<br/>ventana temporal]
  ESC -.- EA[contrato de escena]
  BEAT -.- BA[tipo<br/>agente]
  PAR -.- PA[modo<br/>texto]
```

Jerarquía mereológica estricta: cada nivel pertenece a uno y solo un padre. `Parte` es opcional. La `Escena` es la unidad operativa: es el nivel más bajo en el que se puede declarar un contrato completo antes de generar. La `Mención` cuelga del capítulo cerrado y apunta por `id` a un hecho de la biblia: no forma parte del texto, dice qué nombra.

## 2. Árbol de la capa Mundo

```mermaid
flowchart TD
  MUN[Entidad de mundo] --> AN[Animadas]
  MUN --> IN[Inanimadas]
  MUN --> AB[Abstractas]
  MUN --> DOC[Respaldo]
  AN --> PER[Personaje]
  AN --> FAC[Faccion / Institucion]
  IN --> LUG[Lugar]
  IN --> OBJ[Objeto]
  AB --> EVT[Evento]
  AB --> PRA[Practica / Costumbre]
  AB --> CON[Concepto]
  AB --> REG[Registro linguistico]
  DOC --> FUE[Fuente]
  DOC --> RCD[Recuerdo]
```

El respaldo tiene dos formas: la `Fuente` respalda una época y el `Recuerdo`
respalda a una persona, la del destinatario al que va dedicada la obra.

Los hechos de la biblia —los que registran en qué capítulos se usan— son
`Personaje`, `Facción`, `Lugar`, `Objeto` y `Evento`. La cronología no es un
nodo de este árbol: es una vista que se compone de los eventos y de las fechas
de nacimiento de las fichas.

```mermaid
flowchart LR
  CRO[Cronologia<br/>vista derivada] --> S1[EventoEstado<br/>fecha, lugar, presentes]
  CRO --> S2[Evento<br/>momento, lugar, participantes]
  S1 --> NAC[Personaje<br/>fechas.nacimiento]
  S2 --> NAC
```

Toda entidad de esta capa lleva además el campo transversal de licencia:

```mermaid
flowchart LR
  ENT[Entidad de mundo] --> LIC{licencia}
  LIC --> C[canon<br/>documentado, inmutable]
  LIC --> P[plausible<br/>inventado, compatible]
  LIC --> D[licencia<br/>contradice la evidencia]
  LIC --> PE[personal<br/>de la vida del destinatario]
  C --> F[Fuente]
  D --> J[Justificacion registrada]
  PE --> R[Recuerdo]
  PE --> X[Exento de anacronismo]
```

Ese campo es lo que permite al validador distinguir un error de una decisión artística.

## 3. Relaciones transversales

Las seis familias, con su validador asociado:

```mermaid
flowchart TD
  REL[Relaciones] --> M[Mereologicas]
  REL --> T[Temporales]
  REL --> C[Causales]
  REL --> E[Epistemicas]
  REL --> P[De compromiso]
  REL --> R[Referenciales]
  M -.- MV[integridad estructural]
  T -.- TV[coherencia de calendario]
  C -.- CV[preparacion de giros]
  E -.- EV[flujo de informacion]
  P -.- PV[economia narrativa]
  R -.- RV[trazabilidad historica]
```

Cómo se instancian entre entidades concretas:

```mermaid
flowchart LR
  ESC[Escena] -- ocurre_en --> LUG[Lugar]
  ESC -- focaliza --> PER[Personaje]
  ESC -- planta_setup --> COM[Compromiso]
  ESC -- paga_setup --> COM
  PER -- sabe_que --> PRO[Proposicion]
  PER -- pertenece_a --> FAC[Faccion]
  PER -- vinculado_a --> PER2[Personaje]
  EVT[Evento] -- causa --> EVT2[Evento]
  EVT -- precede_a --> EVT2
  EVT -- documentado_por --> FUE[Fuente]
  CAP[Capitulo] -- menciona --> PER
  CAP -- menciona --> LUG
  LECTOR[Lector] -- sabe_que --> PRO
```

El `Lector` aparece como sujeto epistémico de pleno derecho. Es lo que permite comprobar si una revelación llega preparada o cae en el vacío, y es la relación que casi ningún sistema de generación modela.

## 4. Contrato de escena

```mermaid
flowchart LR
  ESC[Escena] --> ENC[Encuadre]
  ESC --> DRA[Dramaturgia]
  ESC --> INF[Informacion]
  ESC --> EST[Estructura]
  ENC --> POV[pov y focalizacion]
  ENC --> MAR[marco espaciotemporal]
  ENC --> ELE[elenco presente]
  DRA --> OBJ[objetivo del foco]
  DRA --> OBS[obstaculo]
  DRA --> CAM[cambio de valor]
  INF --> REV[informacion revelada]
  INF --> QUI[a quien y al lector]
  EST --> FUN[funcion estructural]
  EST --> AB[compromisos abiertos]
  EST --> PA[compromisos pagados]
```

Si falta un campo, la escena no es generable. Si el texto producido no lo satisface, la escena se rechaza. Es el punto donde la ontología deja de ser descriptiva y se vuelve ejecutable.

## 5. Árbol de calidad

```mermaid
flowchart TD
  CAL[Calidad] --> LOC[Alcance local<br/>parrafo y pagina]
  CAL --> MED[Alcance escena<br/>y capitulo]
  CAL --> GLO[Alcance global<br/>obra]
  LOC --> ANA[Anacronismo]
  LOC --> FAT[Fatiga lexica]
  LOC --> VOZ[Coherencia de voz]
  ANA --> A1[material]
  ANA --> A2[lexico]
  ANA --> A3[conceptual]
  ANA --> A4[social]
  ANA --> A5[institucional]
  MED --> CON[Cumplimiento de contrato]
  MED --> EPI[Violacion epistemica]
  MED --> CNT[Continuidad de estado]
  MED --> TEM[Coherencia temporal]
  MED --> RIT[Ritmo]
  MED --> CAM[Cambio de valor]
  MED --> POV[Integridad de POV]
  LOC --> TIC[Tics de modelo]
  GLO --> ARC[Progresion de arcos]
  GLO --> ECO[Economia narrativa]
  GLO --> TEN[Curva de tension]
  GLO --> REV[Distribucion de revelaciones]
  GLO --> FID[Fidelidad historica]
  GLO --> DOC[Cobertura documental]
  GLO --> CIE[Obra cerrada sin defectos abiertos]
```

Cada hoja es una dimensión observable solo en su alcance, y formulada como predicado sobre entidades de la ontología, no como impresión sobre el texto.

## 6. Vocabularios controlados

```mermaid
flowchart TD
  VOC[Vocabularios] --> FORMA[De forma textual]
  VOC --> MUNDO[De mundo]
  VOC --> NARR[De estado narrativo]
  FORMA --> POV[pov: primera / tercera limitada /<br/>tercera omnisciente / epistolar / mixta]
  FORMA --> MODO[modo: escena / sumario / descripcion /<br/>dialogo / monologo interior / digresion]
  FORMA --> FUN[funcion: setup / escalada / giro /<br/>revelacion / respiro / pago / resolucion]
  FORMA --> BEAT[beat: accion / reaccion / decision /<br/>revelacion / transicion]
  MUNDO --> ONT[estatus: historico / ficticio / compuesto]
  MUNDO --> LIC[licencia: canon / plausible /<br/>licencia / personal]
  MUNDO --> PAP[papel del destinatario: protagonista /<br/>secundario / testigo / narrador]
  MUNDO --> FTE[fuente: primaria / secundaria /<br/>divulgativa / sin respaldo]
  MUNDO --> ANA[anacronismo: material / lexico /<br/>conceptual / social / institucional]
  NARR --> COM[compromiso: abierto / reforzado /<br/>pagado / abandonado]
```

Estos valores cerrados son los que hacen computables los predicados de calidad. Los vocabularios de proceso están en `architecture.md`.
