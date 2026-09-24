---------------------------- MODULE Produccion ----------------------------
(***************************************************************************)
(* El flujo de produccion de una obra de my-story-maker como maquina de    *)
(* estados (SPEC1 4.17).                                                   *)
(*                                                                         *)
(* Configuracion (alta y poblar_mundo), planificacion y escritura de cada  *)
(* capitulo, validacion (cribas y auditoria), cierre como punto de         *)
(* guardado, reintentos con su politica al agotarse, caidas del proceso y  *)
(* relanzamiento, detener y reanudar, versiones (rehacer desde N y         *)
(* regeneracion por cambio del lector) y la puerta de publicacion.         *)
(*                                                                         *)
(* Una sola obra. Lo que el modelo NO distingue esta dicho en SPEC1 D-66:  *)
(* el contenido de los artefactos, el bucle de calidad dentro del          *)
(* capitulo, las tandas y el indice de parecido.                           *)
(*                                                                         *)
(* El mapeo de cada accion al codigo que la implementa esta en mapeo.md,   *)
(* junto a este fichero, y los contraejemplos que TLC saco por el camino,  *)
(* en contraejemplos/.                                                     *)
(***************************************************************************)
EXTENDS Naturals, FiniteSets, TLC

CONSTANTS
    C,            \* capitulos de la obra (capitulos_objetivo)
    MaxV,         \* versiones como mucho en el modelo
    R,            \* reintentos de cada paso (guion.toml: reintentos = 2)
    Hechos,       \* hechos de la biblia que el lector puede cambiar
    MaxCaidas,    \* caidas del proceso como mucho: hipotesis de equidad
    MaxReanudar,  \* ordenes de reanudar del editor como mucho
    MaxFallos     \* fallos no previstos del caminante como mucho

ASSUME /\ C \in Nat \ {0}
       /\ MaxV \in Nat \ {0}
       /\ R \in Nat \ {0}
       /\ MaxCaidas \in Nat /\ MaxReanudar \in Nat /\ MaxFallos \in Nat

Caps == 1..C
Versiones == 1..MaxV
\* Cuantos hilos pueden esperar a la vez, como mucho: los que arrancan
\* reanudar y las versiones nuevas mientras hay uno vivo.
MaxEspera == MaxReanudar + MaxV

Min(S) == CHOOSE x \in S : \A y \in S : x <= y

(* Las tareas del guion, reducidas por lo que hacen al agotarse          *)
(* (guion.toml). "planificar" y "plegar" producen testigo: detener_obra.   *)
(* "cribar" hace de las cribas y de documentar: critica_abierta y seguir  *)
(* son iguales para el flujo, porque las dos siguen sin testigo nuevo.     *)
Tareas == {"poblar", "planificar", "cribar", "plegar", "auditar"}
POLITICA == [t \in Tareas |->
                 IF t \in {"cribar", "auditar"} THEN "critica_abierta"
                 ELSE "detener_obra"]
PCs == {"volver", "tarea", "elegir", "cerrar", "aud_check", "guardar_aud", "fin"}

VARIABLES
    proceso,      \* "arriba" | "caido": el proceso del backend
    detenida,     \* control_de_ejecucion.detenida
    auditada,     \* control_de_ejecucion.auditada_hasta
    poblado,      \* la biblia de partida existe (comun a todas las versiones)
    nv,           \* la ultima version: la unica que se produce (D-40)
    terminada,    \* version_de_la_obra.terminada_en IS NOT NULL
    veredicto,    \* lo que diria la puerta de publicacion sobre la version
    foto,         \* lo que la version veia al terminar (para RF-114)
    publicada,    \* la version de la ultima publicacion (0 si ninguna)
    publicadas,   \* toda version que alguna vez entro en el registro
    escrito,      \* los artefactos, con sus marcas de version y caducidad
    cam,          \* el caminante que trabaja: sus variables locales
    esperan,      \* hilos arrancados que esperan (join) al anterior
    caidas, reanudaciones, fallos

vars == << proceso, detenida, auditada, poblado, nv, terminada, veredicto, foto,
           publicada, publicadas, escrito, cam, esperan, caidas,
           reanudaciones, fallos >>

(***************************************************************************)
(* Los hilos (api/aplicacion.py:Produccion.arrancar). Leer el hilo        *)
(* anterior y registrar el nuevo es una sola operacion bajo cerrojo        *)
(* (RF-166, contraejemplo 01), asi que los hilos forman una cola: cada uno *)
(* hace join del que se registro antes. El primero trabaja (cam) y los     *)
(* demas esperan; al esperar no tienen estado propio, y basta contarlos.   *)
(***************************************************************************)
Ninguno == [est |-> "ninguno", pc |-> "volver", k |-> 1, tarea |-> "planificar",
            intento |-> 1]
Nuevo == [Ninguno EXCEPT !.est = "activo"]

\* casa.hilos[id].is_alive(): el ultimo registrado vive si hay alguno.
Produciendo == cam.est = "activo"
Terminada == auditada >= C    \* Produccion.terminada (RF-93)

\* Arrancar: el hilo nuevo trabaja, o espera si hay uno vivo.
Arrancar ==
    IF cam.est = "activo"
    THEN /\ esperan < MaxEspera
         /\ esperan' = esperan + 1
         /\ UNCHANGED cam
    ELSE /\ cam' = Nuevo
         /\ UNCHANGED esperan

\* El hilo que trabaja acaba y el siguiente de la cola, si lo hay, empieza.
Acabar ==
    IF esperan > 0
    THEN /\ cam' = Nuevo
         /\ esperan' = esperan - 1
    ELSE /\ cam' = Ninguno
         /\ UNCHANGED esperan

(***************************************************************************)
(* Lo que ve cada version (RF-113, almacen/artefactos.py:_visible).        *)
(* Un artefacto es un registro con el capitulo del que cuelga, su tipo,    *)
(* la version en que nacio, la que lo relevo (0 si ninguna), la marca de   *)
(* caducado y los hechos que menciona. "trabajo" es todo lo que un         *)
(* capitulo escribe antes de cerrar, y n dice cuantas producciones vivas   *)
(* del capitulo habia al escribirlo, contando esta: 2 es un duplicado.     *)
(* "cierre" es lo que entra de una vez al cerrarlo: EventoEstado, estado   *)
(* en N, Resumen, Mencion y la marca cerrado (RF-90). "ficha" es la ficha  *)
(* de un hecho de la biblia: no cuelga de ningun capitulo (cap = 0), la    *)
(* escribe poblar_mundo y, al cambiarla el lector, el backend escribe la   *)
(* nueva en la version nueva y releva la vieja (D-72 de T14).              *)
(* Lo que se descarta al volver al punto de guardado queda caducado y sin  *)
(* relevo: ninguna version lo ve nunca. RD-07 lo guarda, pero ninguna      *)
(* propiedad lo mira, asi que el modelo lo olvida en vez de guardarlo.     *)
(***************************************************************************)
Visible(v) == {r \in escrito : /\ r.nac <= v
                               /\ (r.rel = 0 \/ r.rel > v)
                               /\ (~r.cad \/ r.rel # 0)}
Vivas == {r \in escrito : ~r.cad}
CerradoVivo(k) == \E r \in Vivas : r.tipo = "cierre" /\ r.cap = k
Proj(r) == [cap |-> r.cap, tipo |-> r.tipo, n |-> r.n, nac |-> r.nac, men |-> r.men]
TrabajoVivo(k) == {r \in Vivas : r.tipo = "trabajo" /\ r.cap = k}
Foto(v) == {Proj(r) : r \in Visible(v)}
\* En que capitulos se usa un hecho en la version v (RF-84): los de sus Mencion.
Usos(v, h) == {r.cap : r \in {x \in Visible(v) : x.tipo = "cierre" /\ h \in x.men}}

(***************************************************************************)
(* El punto de guardado (nucleo/caminante.py:volver_al_punto_de_guardado). *)
(* Descarta lo vivo que cuelga de todo capitulo que no esta cerrado en la  *)
(* version en curso (RF-165, contraejemplo 03). El codigo lo hace con     *)
(* almacen.descartar_sin_cerrar (RF-176): descartar solo lo posterior al   *)
(* ultimo cerrado bastaba mientras los cerrados eran 1..ultimo, que es     *)
(* todo lo que rehacer desde N deja; la regeneracion del lector reescribe  *)
(* capitulos sueltos y lo rompia.                                          *)
(***************************************************************************)
Descartar(E) == {r \in E : r.cad \/ r.cap = 0 \/ CerradoVivo(r.cap)}

(***************************************************************************)
(* El caminante: el hilo que trabaja, con el proceso en pie.              *)
(***************************************************************************)
Activo == proceso = "arriba" /\ cam.est = "activo"

Global == << proceso, auditada, nv, terminada, veredicto, foto, publicada,
             publicadas, caidas, reanudaciones, fallos >>

Volver ==
    /\ Activo /\ cam.pc = "volver"
    /\ escrito' = Descartar(escrito)
    /\ cam' = IF poblado
              THEN [cam EXCEPT !.pc = "elegir", !.k = 1]
              ELSE [cam EXCEPT !.pc = "tarea", !.tarea = "poblar", !.intento = 1]
    /\ UNCHANGED << Global, detenida, poblado, esperan >>

\* Capitulo ya cerrado: no se repite (caminante._ya_cerrado).
Elegir ==
    /\ Activo /\ cam.pc = "elegir"
    /\ cam' = IF CerradoVivo(cam.k)
              THEN [cam EXCEPT !.pc = "aud_check"]
              ELSE [cam EXCEPT !.pc = "tarea", !.tarea = "planificar", !.intento = 1]
    /\ UNCHANGED << Global, detenida, poblado, escrito, esperan >>

\* A donde va el caminante cuando una tarea sale bien o se agota sin detener.
Despues(h) ==
    CASE h.tarea = "poblar"     -> [h EXCEPT !.pc = "elegir", !.k = 1]
      [] h.tarea = "planificar" -> [h EXCEPT !.tarea = "cribar", !.intento = 1]
      [] h.tarea = "cribar"     -> [h EXCEPT !.tarea = "plegar", !.intento = 1]
      [] h.tarea = "plegar"     -> [h EXCEPT !.pc = "cerrar"]
      [] h.tarea = "auditar"    -> [h EXCEPT !.pc = "guardar_aud"]

(* Un intento de la tarea en curso (caminante._mandar y _agotado).          *)
(* Antes del primer intento se mira si la obra esta detenida.               *)
Intento ==
    /\ Activo /\ cam.pc = "tarea"
    /\ IF cam.intento = 1 /\ detenida
       THEN \* ProduccionDetenida: el hilo acaba sin escribir nada
            /\ Acabar
            /\ UNCHANGED << detenida, poblado, escrito >>
       ELSE \/ \* el intento sale bien
               /\ IF cam.tarea = "planificar"
                  THEN escrito' = escrito \cup
                            {[cap |-> cam.k, tipo |-> "trabajo",
                              n |-> Cardinality(TrabajoVivo(cam.k)) + 1,
                              nac |-> nv, rel |-> 0, cad |-> FALSE, men |-> {}]}
                  ELSE IF cam.tarea = "poblar" THEN TRUE
                  ELSE UNCHANGED escrito
               /\ cam' = Despues(cam)
               /\ poblado' = (poblado \/ cam.tarea = "poblar")
               /\ cam.tarea = "poblar" =>
                     escrito' = escrito \cup
                        {[cap |-> 0, tipo |-> "ficha", n |-> 1, nac |-> nv, rel |-> 0,
                          cad |-> FALSE, men |-> {h}] : h \in Hechos}
               /\ UNCHANGED << detenida, esperan >>
            \/ \* el intento falla y quedan intentos
               /\ cam.intento < R
               /\ cam' = [cam EXCEPT !.intento = cam.intento + 1]
               /\ UNCHANGED << detenida, poblado, escrito, esperan >>
            \/ \* el ultimo intento falla: manda la politica del paso
               /\ cam.intento = R
               /\ IF POLITICA[cam.tarea] = "detener_obra"
                  THEN /\ detenida' = TRUE
                       /\ Acabar
                  ELSE /\ cam' = Despues(cam)
                       /\ UNCHANGED << detenida, esperan >>
               /\ UNCHANGED << poblado, escrito >>
    /\ UNCHANGED Global

(* El punto de guardado: cerrar el capitulo es una sola transaccion        *)
(* (almacen.cerrar_capitulo, RF-90). El Archivero decide que hechos        *)
(* menciona el capitulo.                                                   *)
Cerrar ==
    /\ Activo /\ cam.pc = "cerrar"
    /\ \E M \in SUBSET Hechos :
          escrito' = escrito \cup
             {[cap |-> cam.k, tipo |-> "cierre", n |-> 1, nac |-> nv, rel |-> 0,
               cad |-> FALSE, men |-> M]}
    /\ cam' = [cam EXCEPT !.pc = "aud_check"]
    /\ UNCHANGED << Global, detenida, poblado, esperan >>

(* _auditar_si_toca: con cadencia 0 solo toca al cierre de la obra.         *)
AudCheck ==
    /\ Activo /\ cam.pc = "aud_check"
    /\ cam' = IF cam.k = C /\ auditada < C
              THEN [cam EXCEPT !.pc = "tarea", !.tarea = "auditar", !.intento = 1]
              ELSE IF cam.k = C THEN [cam EXCEPT !.pc = "fin"]
              ELSE [cam EXCEPT !.pc = "elegir", !.k = cam.k + 1]
    /\ UNCHANGED << Global, detenida, poblado, escrito, esperan >>

(* almacen.guardar_auditoria(de_cierre=True): las criticas, la constancia   *)
(* y la marca de terminada de la version en curso, juntas (RF-94, RF-110). *)
(* La puerta se deriva de lo que la version ve, y una version terminada no *)
(* cambia (D-59): su veredicto queda fijado aqui, sin decir cual (D-67).   *)
GuardarAud ==
    /\ Activo /\ cam.pc = "guardar_aud"
    /\ auditada' = IF cam.k > auditada THEN cam.k ELSE auditada
    /\ IF cam.k = C /\ ~terminada[nv]
       THEN /\ terminada' = [terminada EXCEPT ![nv] = TRUE]
            /\ \E b \in {"pasa", "no_pasa"} : veredicto' = [veredicto EXCEPT ![nv] = b]
            /\ foto' = [foto EXCEPT ![nv] = Foto(nv)]
       ELSE UNCHANGED << terminada, veredicto, foto >>
    /\ cam' = [cam EXCEPT !.pc = "fin"]
    /\ UNCHANGED << proceso, detenida, poblado, nv, publicada, publicadas, escrito,
                    esperan, caidas, reanudaciones, fallos >>

Fin ==
    /\ Activo /\ cam.pc = "fin"
    /\ Acabar
    /\ UNCHANGED << Global, detenida, poblado, escrito >>

(* Una excepcion que no es ProduccionDetenida sale de caminar_obra: la obra *)
(* queda detenida con su motivo y el hilo acaba (RF-167, contraejemplo 02). *)
FalloNoPrevisto ==
    /\ Activo /\ fallos < MaxFallos
    /\ fallos' = fallos + 1
    /\ detenida' = TRUE
    /\ Acabar
    /\ UNCHANGED << proceso, auditada, poblado, nv, terminada, veredicto, foto,
                    publicada, publicadas, escrito, caidas, reanudaciones >>

PasoDelCaminante ==
    Volver \/ Elegir \/ Intento \/ Cerrar \/ AudCheck \/ GuardarAud \/ Fin

(***************************************************************************)
(* El entorno: la maquina y el editor.                                    *)
(***************************************************************************)
Caida ==
    /\ proceso = "arriba" /\ caidas < MaxCaidas
    /\ proceso' = "caido"
    /\ caidas' = caidas + 1
    /\ cam' = Ninguno
    /\ esperan' = 0
    /\ UNCHANGED << detenida, auditada, poblado, nv, terminada, veredicto, foto,
                    publicada, publicadas, escrito, reanudaciones, fallos >>

(* El backend vuelve: relanza lo que no esta detenido ni terminado (RF-93). *)
(* Ocurre en el arranque, antes de servir ninguna peticion: es atomico.     *)
ArrancarBackend ==
    /\ proceso = "caido"
    /\ proceso' = "arriba"
    /\ IF ~detenida /\ ~Terminada THEN Arrancar ELSE UNCHANGED << cam, esperan >>
    /\ UNCHANGED << detenida, auditada, poblado, nv, terminada, veredicto, foto,
                    publicada, publicadas, escrito, caidas, reanudaciones, fallos >>

Detener ==
    /\ proceso = "arriba" /\ ~detenida
    /\ detenida' = TRUE
    /\ UNCHANGED << Global, poblado, escrito, cam, esperan >>

Reanudar ==
    /\ proceso = "arriba" /\ reanudaciones < MaxReanudar
    /\ reanudaciones' = reanudaciones + 1
    /\ detenida' = FALSE
    /\ IF ~Terminada THEN Arrancar ELSE UNCHANGED << cam, esperan >>
    /\ UNCHANGED << proceso, auditada, poblado, nv, terminada, veredicto, foto,
                    publicada, publicadas, escrito, caidas, fallos >>

(* Una version nueva que reescribe los capitulos S (versiones.rehacer_desde *)
(* y almacen.abrir_version). Solo con la ultima terminada y sin produccion  *)
(* en marcha (D-40). Lo que colgaba de S se releva; la constancia de        *)
(* auditoria baja para que la nueva se audite al cerrar. Despues arranca.   *)
(* Con un hecho H cambiado, ademas, su ficha viva se releva y nace la nueva *)
(* en la version nueva, en la misma transaccion (D-72 de T14).              *)
Relevar(S, H, E) ==
    {IF ~r.cad /\ (r.cap \in S \/ (r.tipo = "ficha" /\ r.men \cap H # {}))
     THEN [r EXCEPT !.cad = TRUE, !.rel = nv + 1] ELSE r : r \in E}
AbrirVersion(S, H) ==
    /\ proceso = "arriba" /\ ~Produciendo
    /\ nv < MaxV /\ terminada[nv]
    /\ S # {}
    /\ nv' = nv + 1
    /\ escrito' = Relevar(S, H, escrito) \cup
                    {[cap |-> 0, tipo |-> "ficha", n |-> nv + 1, nac |-> nv + 1, rel |-> 0,
                      cad |-> FALSE, men |-> {h}] : h \in H}
    /\ auditada' = Min(S) - 1
    /\ detenida' = FALSE
    /\ Arrancar
    /\ UNCHANGED << proceso, poblado, terminada, veredicto, foto, publicada,
                    publicadas, caidas, reanudaciones, fallos >>

(* Rehacer desde el capitulo N hasta el final (RF-111, D-42).               *)
Rehacer(n) == AbrirVersion(n..C, {})

(* Regeneracion por cambio del lector (RF-164; la implementa SPEC1 4.18):   *)
(* el lector cambia el valor de un hecho, su ficha se                      *)
(* sustituye en la version nueva y se reescriben los capitulos que lo usan  *)
(* en la ultima version, contiguos o no. Si ninguno lo usa, se rechaza y no *)
(* nace version (D-73): en el modelo, la accion no esta habilitada.         *)
CambioLector(h) == AbrirVersion(Usos(nv, h), {h})

(* Publicar (versiones.publicar, el unico sitio, RF-116 y RF-146). La       *)
(* puerta abarca los cuatro validadores de hoy y el formal de T10: si no    *)
(* pasa, no se publica nada y el estado no cambia; si pasa, se publica.     *)
Publicar(v) ==
    /\ proceso = "arriba" /\ v \in 1..nv /\ terminada[v]
    /\ veredicto[v] = "pasa"
    /\ publicada' = v
    /\ publicadas' = publicadas \cup {v}
    /\ UNCHANGED << proceso, detenida, auditada, poblado, nv, terminada, veredicto,
                    foto, escrito, cam, esperan, caidas, reanudaciones, fallos >>

(***************************************************************************)
(* Especificacion.                                                        *)
(***************************************************************************)
Init ==
    \* El alta crea la obra y su version 1 y arranca la produccion (RF-02).
    /\ proceso = "arriba"
    /\ detenida = FALSE
    /\ auditada = 0
    /\ poblado = FALSE
    /\ nv = 1
    /\ terminada = [v \in Versiones |-> FALSE]
    /\ veredicto = [v \in Versiones |-> "pendiente"]
    /\ foto = [v \in Versiones |-> {}]
    /\ publicada = 0
    /\ publicadas = {}
    /\ escrito = {}
    /\ cam = Nuevo
    /\ esperan = 0
    /\ caidas = 0 /\ reanudaciones = 0 /\ fallos = 0

Entorno ==
    \/ Caida \/ ArrancarBackend \/ Detener \/ Reanudar \/ FalloNoPrevisto
    \/ \E n \in Caps : Rehacer(n)
    \/ \E h \in Hechos : CambioLector(h)
    \/ \E v \in Versiones : Publicar(v)

Next == PasoDelCaminante \/ Entorno

(* Equidad: el caminante avanza si puede (debil), y el proceso caido vuelve *)
(* a arrancar (debil). Ni el editor ni la maquina deben nada: sus acciones  *)
(* no llevan equidad, y las caidas estan acotadas por MaxCaidas, que es la  *)
(* hipotesis de que dejan de ocurrir.                                       *)
Fairness == WF_vars(PasoDelCaminante) /\ WF_vars(ArrancarBackend)

Spec == Init /\ [][Next]_vars /\ Fairness

(***************************************************************************)
(* Propiedades.                                                           *)
(***************************************************************************)
Registro == [cap : 0..C, tipo : {"trabajo", "cierre", "ficha"}, n : Nat, nac : Versiones,
             rel : 0..MaxV, cad : BOOLEAN, men : SUBSET Hechos]
TypeOK ==
    /\ proceso \in {"arriba", "caido"}
    /\ detenida \in BOOLEAN /\ poblado \in BOOLEAN
    /\ auditada \in 0..C
    /\ nv \in Versiones
    /\ terminada \in [Versiones -> BOOLEAN]
    /\ veredicto \in [Versiones -> {"pendiente", "pasa", "no_pasa"}]
    /\ publicada \in 0..MaxV /\ publicadas \subseteq Versiones
    /\ escrito \subseteq Registro
    \* El contador de intentos nunca pasa del tope del guion (RF-95).
    /\ cam \in [est : {"ninguno", "activo"}, pc : PCs, k : Caps, tarea : Tareas,
                intento : 1..R]
    /\ esperan \in 0..MaxEspera

(* S1. Nunca hay publicada una version que no paso la puerta (RF-146). *)
PuertaRespetada ==
    /\ \A v \in publicadas : terminada[v] /\ veredicto[v] = "pasa"
    /\ publicada # 0 => publicada \in publicadas

(* S2. La version anterior se conserva siempre: lo que ve una version      *)
(* terminada es lo mismo que veia al terminar (RF-114).                    *)
AnteriorIntacta == \A v \in 1..nv : terminada[v] => Foto(v) = foto[v]

(* S3. Una sola produccion a la vez: toda version salvo la ultima esta     *)
(* terminada (D-40), y ningun hilo espera sin otro delante que trabaje.    *)
(* Que haya un solo caminante es, desde RF-166, la forma de la cola.       *)
UnaSolaProduccion ==
    /\ \A v \in 1..(nv - 1) : terminada[v]
    /\ esperan > 0 => cam.est = "activo"

(* Auxiliar. Ni duplica: lo vivo de un capitulo es de una sola produccion  *)
(* (RF-92, RF-165).                                                        *)
NiDuplica == \A k \in Caps : Cardinality(TrabajoVivo(k)) <= 1

(* Auxiliares, de accion. Ni pierde: un capitulo cerrado sigue cerrado     *)
(* salvo que una version nueva lo releve (RF-92). Y nadie escribe en una   *)
(* version que ya termino, que es lo que sostiene S2 desde la escritura:  *)
(* un artefacto nuevo (no una marca sobre uno que ya estaba) nace en una   *)
(* version sin terminar.                                                   *)
NiPierde ==
    [][\A k \in Caps : CerradoVivo(k) => (CerradoVivo(k)' \/ nv' = nv + 1)]_vars
Nace(r) == \A s \in escrito : Proj(s) # Proj(r)
NoEscribeEnTerminada ==
    [][\A r \in escrito' : Nace(r) => ~terminada[r.nac]]_vars

(* L1. Toda version en produccion acaba terminada, o la obra acaba         *)
(* detenida y dice por que. Incluye las versiones del lector.              *)
AcabaTerminadaODetenida == (~terminada[nv]) ~> (terminada[nv] \/ detenida)

=============================================================================
