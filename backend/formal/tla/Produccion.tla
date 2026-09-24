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
(* junto a este fichero.                                                   *)
(***************************************************************************)
EXTENDS Naturals, FiniteSets, Sequences, TLC

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
\* Cada orden que arranca un caminante crea un hilo nuevo; con este tope no se
\* queda nunca sin hilo ninguna accion que lo pida (alta, relanzamientos,
\* reanudar y versiones nuevas).
MaxHilos == 1 + MaxCaidas + MaxReanudar + (MaxV - 1)
Hilos == 1..MaxHilos

Min(S) == CHOOSE x \in S : \A y \in S : x <= y
Max0(S) == IF S = {} THEN 0 ELSE CHOOSE x \in S : \A y \in S : x >= y

(* Las tareas, reducidas a una por politica de al_agotarse (guion.toml).   *)
Tareas == {"poblar", "planificar", "documentar", "cribar", "plegar", "auditar"}
POLITICA == [t \in Tareas |->
                 CASE t = "documentar"          -> "seguir"
                   [] t \in {"cribar", "auditar"} -> "critica_abierta"
                   [] OTHER                       -> "detener_obra"]
PCs == {"volver", "tarea", "elegir", "cerrar", "aud_check", "guardar_aud", "fin"}
Estados == {"libre", "activo", "espera", "muerto"}

VARIABLES
    proceso,      \* "arriba" | "caido": el proceso del backend
    detenida,     \* control_de_ejecucion.detenida
    auditada,     \* control_de_ejecucion.auditada_hasta
    poblado,      \* la biblia de partida existe (comun a todas las versiones)
    nv,           \* la ultima version: la unica que se produce (D-40)
    terminada,    \* version_de_la_obra.terminada_en IS NOT NULL
    veredicto,    \* lo que diria la puerta de publicacion sobre la version
    foto,         \* lo que la version veia al terminar (para RF-114)
    cambiados,    \* version_de_la_obra.capitulos_cambiados
    tipo,         \* de donde sale cada version: alta, rehacer o lector
    publicada,    \* la version de la ultima publicacion (0 si ninguna)
    publicadas,   \* toda version que alguna vez entro en el registro
    rechazadas,   \* versiones a las que la puerta dijo que no
    escrito,      \* los artefactos, con sus marcas de version y caducidad
    gen,          \* contador de producciones de capitulo (cada planificar)
    hilos,        \* los hilos de produccion (Produccion.hilos y los muertos)
    nh,           \* cuantos hilos se han creado
    ultimo,       \* el hilo registrado para la obra en Produccion.hilos
    caidas, reanudaciones, fallos

vars == << proceso, detenida, auditada, poblado, nv, terminada, veredicto, foto,
           cambiados, tipo, publicada, publicadas, rechazadas, escrito, gen,
           hilos, nh, ultimo, caidas, reanudaciones, fallos >>

HiloNuevo == [est |-> "libre", espera |-> 0, pc |-> "volver", k |-> 1,
              tarea |-> "planificar", intento |-> 1, g |-> 0]

(***************************************************************************)
(* Lo que ve cada version (RF-113, almacen/artefactos.py:_visible).        *)
(* Un artefacto es un registro con el capitulo del que cuelga, su tipo,    *)
(* la produccion del capitulo que lo escribio (gen), la version en que     *)
(* nacio, la que lo relevo (0 si ninguna), la marca de caducado y los      *)
(* hechos que menciona. "trabajo" es todo lo que un capitulo escribe antes *)
(* de cerrar; "cierre" es lo que entra de una vez al cerrarlo: EventoEstado,*)
(* estado en N, Resumen, Mencion y la marca cerrado (RF-90).               *)
(***************************************************************************)
Visible(v) == {r \in escrito : /\ r.nac <= v
                               /\ (r.rel = 0 \/ r.rel > v)
                               /\ (~r.cad \/ r.rel # 0)}
Vivas == {r \in escrito : ~r.cad}
CerradoVivo(k) == \E r \in Vivas : r.tipo = "cierre" /\ r.cap = k
Proj(r) == [cap |-> r.cap, tipo |-> r.tipo, gen |-> r.gen, men |-> r.men]
Foto(v) == {Proj(r) : r \in Visible(v)}
\* En que capitulos se usa un hecho en la version v (RF-84): los de sus Mencion.
Usos(v, h) == {r.cap : r \in {x \in Visible(v) : x.tipo = "cierre" /\ h \in x.men}}

Vivo(i) == hilos[i].est \in {"activo", "espera"}
\* casa.hilos[id].is_alive(): solo mira el ultimo hilo registrado.
Produciendo == ultimo # 0 /\ Vivo(ultimo)
Terminada == auditada >= C    \* Produccion.terminada (RF-93)

(***************************************************************************)
(* Arrancar la produccion (api/aplicacion.py:Produccion.arrancar). Leer el *)
(* hilo anterior y registrar el nuevo es una sola operacion bajo cerrojo   *)
(* (RF-166, contraejemplo 01). El hilo nuevo, nh+1, espera (join) al       *)
(* anterior si sigue vivo.                                                 *)
(***************************************************************************)
CrearHilo(ant) ==
    /\ nh < MaxHilos
    /\ nh' = nh + 1
    /\ ultimo' = nh + 1
    /\ hilos' = [hilos EXCEPT ![nh + 1] =
                    [HiloNuevo EXCEPT !.est = IF ant # 0 /\ Vivo(ant)
                                              THEN "espera" ELSE "activo",
                                      !.espera = ant]]

\* Un hilo que acaba libera a los que le esperaban (Thread.join).
Acabar(i, h) ==
    [j \in Hilos |->
        IF j = i THEN [h[i] EXCEPT !.est = "muerto"]
        ELSE IF h[j].est = "espera" /\ h[j].espera = i
             THEN [h[j] EXCEPT !.est = "activo"]
             ELSE h[j]]

(***************************************************************************)
(* El punto de guardado (nucleo/caminante.py:volver_al_punto_de_guardado). *)
(* Hoy: descarta lo que cuelga de los capitulos posteriores al ultimo      *)
(* cerrado (almacen.descartar_desde(ultimo + 1)).                          *)
(***************************************************************************)
UltimoCerrado == Max0({k \in Caps : CerradoVivo(k)})
Descartar(E) ==
    {IF ~r.cad /\ r.cap > UltimoCerrado THEN [r EXCEPT !.cad = TRUE] ELSE r : r \in E}

(***************************************************************************)
(* El caminante: un hilo activo con el proceso en pie.                    *)
(***************************************************************************)
Activo(i) == proceso = "arriba" /\ hilos[i].est = "activo"

SetH(i, rec) == hilos' = [hilos EXCEPT ![i] = rec]

Volver(i) ==
    /\ Activo(i) /\ hilos[i].pc = "volver"
    /\ escrito' = Descartar(escrito)
    /\ SetH(i, IF poblado
               THEN [hilos[i] EXCEPT !.pc = "elegir", !.k = 1]
               ELSE [hilos[i] EXCEPT !.pc = "tarea", !.tarea = "poblar", !.intento = 1])
    /\ UNCHANGED << proceso, detenida, auditada, poblado, nv, terminada, veredicto,
                    foto, cambiados, tipo, publicada, publicadas, rechazadas, gen,
                    nh, ultimo, caidas, reanudaciones, fallos >>

\* Capitulo ya cerrado: no se repite (caminante._ya_cerrado).
Elegir(i) ==
    /\ Activo(i) /\ hilos[i].pc = "elegir"
    /\ SetH(i, IF CerradoVivo(hilos[i].k)
               THEN [hilos[i] EXCEPT !.pc = "aud_check"]
               ELSE [hilos[i] EXCEPT !.pc = "tarea", !.tarea = "planificar",
                                     !.intento = 1])
    /\ UNCHANGED << proceso, detenida, auditada, poblado, nv, terminada, veredicto,
                    foto, cambiados, tipo, publicada, publicadas, rechazadas, escrito,
                    gen, nh, ultimo, caidas, reanudaciones, fallos >>

\* A donde va el caminante cuando una tarea sale bien o se agota sin detener.
Despues(h) ==
    CASE h.tarea = "poblar"     -> [h EXCEPT !.pc = "elegir", !.k = 1]
      [] h.tarea = "planificar" -> [h EXCEPT !.tarea = "documentar", !.intento = 1]
      [] h.tarea = "documentar" -> [h EXCEPT !.tarea = "cribar", !.intento = 1]
      [] h.tarea = "cribar"     -> [h EXCEPT !.tarea = "plegar", !.intento = 1]
      [] h.tarea = "plegar"     -> [h EXCEPT !.pc = "cerrar"]
      [] h.tarea = "auditar"    -> [h EXCEPT !.pc = "guardar_aud"]

(* Un intento de la tarea en curso (caminante._mandar y _agotado).          *)
(* Antes del primer intento se mira si la obra esta detenida.               *)
Intento(i) ==
    LET h == hilos[i] IN
    /\ Activo(i) /\ h.pc = "tarea"
    /\ IF h.intento = 1 /\ detenida
       THEN \* ProduccionDetenida: el hilo acaba sin escribir nada
            /\ hilos' = Acabar(i, hilos)
            /\ UNCHANGED << detenida, poblado, escrito, gen >>
       ELSE \/ \* el intento sale bien
               /\ IF h.tarea = "planificar"
                  THEN /\ gen' = gen + 1
                       /\ escrito' = escrito \cup
                            {[cap |-> h.k, tipo |-> "trabajo", gen |-> gen + 1,
                              nac |-> nv, rel |-> 0, cad |-> FALSE, men |-> {}]}
                       /\ SetH(i, [Despues(h) EXCEPT !.g = gen + 1])
                  ELSE /\ UNCHANGED << gen, escrito >>
                       /\ SetH(i, Despues(h))
               /\ poblado' = (poblado \/ h.tarea = "poblar")
               /\ UNCHANGED detenida
            \/ \* el intento falla y quedan intentos
               /\ h.intento < R
               /\ SetH(i, [h EXCEPT !.intento = h.intento + 1])
               /\ UNCHANGED << detenida, poblado, escrito, gen >>
            \/ \* el ultimo intento falla: manda la politica del paso
               /\ h.intento = R
               /\ IF POLITICA[h.tarea] = "detener_obra"
                  THEN /\ detenida' = TRUE
                       /\ hilos' = Acabar(i, hilos)
                  ELSE /\ SetH(i, Despues(h))
                       /\ UNCHANGED detenida
               /\ UNCHANGED << poblado, escrito, gen >>
    /\ UNCHANGED << proceso, auditada, nv, terminada, veredicto, foto, cambiados,
                    tipo, publicada, publicadas, rechazadas, nh, ultimo,
                    caidas, reanudaciones, fallos >>

(* El punto de guardado: cerrar el capitulo es una sola transaccion        *)
(* (almacen.cerrar_capitulo, RF-90). El Archivero decide que hechos        *)
(* menciona el capitulo.                                                   *)
Cerrar(i) ==
    LET h == hilos[i] IN
    /\ Activo(i) /\ h.pc = "cerrar"
    /\ \E M \in SUBSET Hechos :
          escrito' = escrito \cup
             {[cap |-> h.k, tipo |-> "cierre", gen |-> h.g, nac |-> nv, rel |-> 0,
               cad |-> FALSE, men |-> M]}
    /\ SetH(i, [h EXCEPT !.pc = "aud_check"])
    /\ UNCHANGED << proceso, detenida, auditada, poblado, nv, terminada, veredicto,
                    foto, cambiados, tipo, publicada, publicadas, rechazadas, gen,
                    nh, ultimo, caidas, reanudaciones, fallos >>

(* _auditar_si_toca: con cadencia 0 solo toca al cierre de la obra.         *)
AudCheck(i) ==
    LET h == hilos[i] IN
    /\ Activo(i) /\ h.pc = "aud_check"
    /\ SetH(i, IF h.k = C /\ auditada < C
               THEN [h EXCEPT !.pc = "tarea", !.tarea = "auditar", !.intento = 1]
               ELSE IF h.k = C THEN [h EXCEPT !.pc = "fin"]
               ELSE [h EXCEPT !.pc = "elegir", !.k = h.k + 1])
    /\ UNCHANGED << proceso, detenida, auditada, poblado, nv, terminada, veredicto,
                    foto, cambiados, tipo, publicada, publicadas, rechazadas, escrito,
                    gen, nh, ultimo, caidas, reanudaciones, fallos >>

(* almacen.guardar_auditoria(de_cierre=True): las criticas, la constancia   *)
(* y la marca de terminada de la version en curso, juntas (RF-94, RF-110). *)
(* La puerta se deriva de lo que la version ve, y una version terminada no *)
(* cambia (D-59): su veredicto queda fijado aqui, sin decir cual.          *)
GuardarAud(i) ==
    LET h == hilos[i] IN
    /\ Activo(i) /\ h.pc = "guardar_aud"
    /\ auditada' = IF h.k > auditada THEN h.k ELSE auditada
    /\ IF h.k = C /\ ~terminada[nv]
       THEN /\ terminada' = [terminada EXCEPT ![nv] = TRUE]
            /\ \E b \in {"pasa", "no_pasa"} : veredicto' = [veredicto EXCEPT ![nv] = b]
            /\ foto' = [foto EXCEPT ![nv] = Foto(nv)]
       ELSE UNCHANGED << terminada, veredicto, foto >>
    /\ SetH(i, [h EXCEPT !.pc = "fin"])
    /\ UNCHANGED << proceso, detenida, poblado, nv, cambiados, tipo, publicada,
                    publicadas, rechazadas, escrito, gen, nh, ultimo, caidas,
                    reanudaciones, fallos >>

Fin(i) ==
    /\ Activo(i) /\ hilos[i].pc = "fin"
    /\ hilos' = Acabar(i, hilos)
    /\ UNCHANGED << proceso, detenida, auditada, poblado, nv, terminada, veredicto,
                    foto, cambiados, tipo, publicada, publicadas, rechazadas, escrito,
                    gen, nh, ultimo, caidas, reanudaciones, fallos >>

(* Una excepcion que no es ProduccionDetenida sale de caminar_obra: la obra *)
(* queda detenida con su motivo y el hilo acaba (RF-167, contraejemplo 02). *)
FalloNoPrevisto(i) ==
    /\ Activo(i) /\ fallos < MaxFallos
    /\ fallos' = fallos + 1
    /\ detenida' = TRUE
    /\ hilos' = Acabar(i, hilos)
    /\ UNCHANGED << proceso, auditada, poblado, nv, terminada, veredicto,
                    foto, cambiados, tipo, publicada, publicadas, rechazadas, escrito,
                    gen, nh, ultimo, caidas, reanudaciones >>

PasoDelCaminante(i) ==
    Volver(i) \/ Elegir(i) \/ Intento(i) \/ Cerrar(i) \/ AudCheck(i)
    \/ GuardarAud(i) \/ Fin(i)

(***************************************************************************)
(* El entorno: la maquina y el editor.                                    *)
(***************************************************************************)
Caida ==
    /\ proceso = "arriba" /\ caidas < MaxCaidas
    /\ proceso' = "caido"
    /\ caidas' = caidas + 1
    /\ hilos' = [i \in Hilos |-> IF Vivo(i) THEN [hilos[i] EXCEPT !.est = "muerto"]
                                             ELSE hilos[i]]
    /\ UNCHANGED << detenida, auditada, poblado, nv, terminada, veredicto, foto,
                    cambiados, tipo, publicada, publicadas, rechazadas, escrito, gen,
                    nh, ultimo, reanudaciones, fallos >>

(* El backend vuelve: relanza lo que no esta detenido ni terminado (RF-93). *)
(* Ocurre en el arranque, antes de servir ninguna peticion: es atomico.     *)
ArrancarBackend ==
    /\ proceso = "caido"
    /\ proceso' = "arriba"
    /\ IF ~detenida /\ ~Terminada
       THEN CrearHilo(0)
       ELSE UNCHANGED << hilos, nh, ultimo >>
    /\ UNCHANGED << detenida, auditada, poblado, nv, terminada, veredicto, foto,
                    cambiados, tipo, publicada, publicadas, rechazadas, escrito, gen,
                    caidas, reanudaciones, fallos >>

Detener ==
    /\ proceso = "arriba" /\ ~detenida
    /\ detenida' = TRUE
    /\ UNCHANGED << proceso, auditada, poblado, nv, terminada, veredicto, foto,
                    cambiados, tipo, publicada, publicadas, rechazadas, escrito, gen,
                    hilos, nh, ultimo, caidas, reanudaciones, fallos >>

Reanudar ==
    /\ proceso = "arriba" /\ reanudaciones < MaxReanudar
    /\ reanudaciones' = reanudaciones + 1
    /\ detenida' = FALSE
    /\ IF ~Terminada THEN CrearHilo(ultimo) ELSE UNCHANGED << hilos, nh, ultimo >>
    /\ UNCHANGED << proceso, auditada, poblado, nv, terminada, veredicto, foto,
                    cambiados, tipo, publicada, publicadas, rechazadas, escrito, gen,
                    caidas, fallos >>

(* Una version nueva que reescribe los capitulos S (versiones.rehacer_desde *)
(* y almacen.abrir_version). Solo con la ultima terminada y sin produccion  *)
(* en marcha (D-40). Lo que colgaba de S se releva; la constancia de        *)
(* auditoria baja para que la nueva se audite al cerrar.                    *)
AbrirVersion(S, t) ==
    /\ proceso = "arriba" /\ ~Produciendo
    /\ nv < MaxV /\ terminada[nv]
    /\ nv' = nv + 1
    /\ cambiados' = [cambiados EXCEPT ![nv + 1] = S]
    /\ tipo' = [tipo EXCEPT ![nv + 1] = t]
    /\ escrito' = {IF ~r.cad /\ r.cap \in S
                   THEN [r EXCEPT !.cad = TRUE, !.rel = nv + 1] ELSE r : r \in escrito}
    /\ auditada' = IF S = {} THEN C - 1 ELSE Min(S) - 1
    /\ detenida' = FALSE
    /\ CrearHilo(ultimo)
    /\ UNCHANGED << proceso, poblado, terminada, veredicto, foto, publicada,
                    publicadas, rechazadas, gen, caidas, reanudaciones, fallos >>

(* Rehacer desde el capitulo N hasta el final (RF-111, D-42).               *)
Rehacer(n) == AbrirVersion(n..C, "rehacer")

(* Regeneracion por cambio del lector (SPEC1 4.18, pendiente de T14): el    *)
(* lector cambia el valor de un hecho y se reescriben los capitulos que lo  *)
(* usan en la ultima version, contiguos o no. Si ninguno lo usa, T14 decide:*)
(* rechazarlo es no hacer nada (no cambia el estado) y abrir una version   *)
(* sin capitulos cambiados es la rama S = {} de AbrirVersion.              *)
CambioLector(h) == AbrirVersion(Usos(nv, h), "lector")

(* Publicar (versiones.publicar, el unico sitio, RF-116 y RF-146). La       *)
(* puerta abarca los cuatro validadores de hoy y el formal de T10: pasa o  *)
(* no pasa, y si no pasa no se publica nada.                               *)
Publicar(v) ==
    /\ proceso = "arriba" /\ v \in 1..nv /\ terminada[v]
    /\ IF veredicto[v] = "pasa"
       THEN /\ publicada' = v
            /\ publicadas' = publicadas \cup {v}
            /\ UNCHANGED rechazadas
       ELSE /\ rechazadas' = rechazadas \cup {v}
            /\ UNCHANGED << publicada, publicadas >>
    /\ UNCHANGED << proceso, detenida, auditada, poblado, nv, terminada, veredicto,
                    foto, cambiados, tipo, escrito, gen, hilos, nh, ultimo,
                    caidas, reanudaciones, fallos >>

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
    /\ cambiados = [v \in Versiones |-> IF v = 1 THEN Caps ELSE {}]
    /\ tipo = [v \in Versiones |-> IF v = 1 THEN "alta" ELSE "ninguno"]
    /\ publicada = 0
    /\ publicadas = {}
    /\ rechazadas = {}
    /\ escrito = {}
    /\ gen = 0
    /\ hilos = [i \in Hilos |-> IF i = 1 THEN [HiloNuevo EXCEPT !.est = "activo"]
                                         ELSE HiloNuevo]
    /\ nh = 1
    /\ ultimo = 1
    /\ caidas = 0 /\ reanudaciones = 0 /\ fallos = 0

Entorno ==
    \/ Caida \/ ArrancarBackend \/ Detener \/ Reanudar
    \/ \E n \in Caps : Rehacer(n)
    \/ \E h \in Hechos : CambioLector(h)
    \/ \E v \in Versiones : Publicar(v)
    \/ \E i \in Hilos : FalloNoPrevisto(i)

Next ==
    \/ \E i \in Hilos : PasoDelCaminante(i)
    \/ Entorno

(* Equidad: el caminante avanza si puede (debil), y el proceso              *)
(* caido vuelve a arrancar (debil). Ni el editor ni la maquina deben nada:  *)
(* sus acciones no llevan equidad, y las caidas estan acotadas por         *)
(* MaxCaidas, que es la hipotesis de que dejan de ocurrir.                 *)
Fairness ==
    /\ \A i \in Hilos : WF_vars(PasoDelCaminante(i))
    /\ WF_vars(ArrancarBackend)

Spec == Init /\ [][Next]_vars /\ Fairness

(***************************************************************************)
(* Propiedades.                                                           *)
(***************************************************************************)
Registro == [cap : Caps, tipo : {"trabajo", "cierre"}, gen : Nat, nac : Versiones,
             rel : 0..MaxV, cad : BOOLEAN, men : SUBSET Hechos]
TypeOK ==
    /\ proceso \in {"arriba", "caido"}
    /\ detenida \in BOOLEAN
    /\ auditada \in 0..C
    /\ nv \in Versiones
    /\ terminada \in [Versiones -> BOOLEAN]
    /\ veredicto \in [Versiones -> {"pendiente", "pasa", "no_pasa"}]
    /\ publicada \in 0..MaxV
    /\ escrito \subseteq Registro
    /\ hilos \in [Hilos -> [est : Estados, espera : 0..MaxHilos, pc : PCs, k : Caps,
                            tarea : Tareas, intento : 1..R, g : Nat]]
    /\ nh \in Hilos /\ ultimo \in 0..MaxHilos

(* S1. Nunca hay publicada una version que no paso la puerta (RF-146). *)
PuertaRespetada ==
    /\ \A v \in publicadas : terminada[v] /\ veredicto[v] = "pasa"
    /\ publicada # 0 => publicada \in publicadas

(* S2. La version anterior se conserva siempre: lo que ve una version      *)
(* terminada es lo mismo que veia al terminar (RF-114).                    *)
AnteriorIntacta == \A v \in 1..nv : terminada[v] => Foto(v) = foto[v]

(* S3. Una sola produccion a la vez: toda version salvo la ultima esta     *)
(* terminada (D-40) y como mucho un caminante trabaja la obra.             *)
UnaSolaProduccion ==
    /\ \A v \in 1..(nv - 1) : terminada[v]
    /\ Cardinality({i \in Hilos : hilos[i].est = "activo"}) <= 1

(* Auxiliar. Ni duplica: lo vivo de un capitulo es de una sola produccion  *)
(* (RF-92).                                                                *)
NiDuplica ==
    \A k \in Caps : Cardinality({r.gen : r \in {x \in Vivas : x.cap = k}}) <= 1

(* Auxiliar. Ni pierde: un capitulo cerrado sigue cerrado salvo que una    *)
(* version nueva lo releve (RF-92). Es propiedad de accion.                *)
NiPierde ==
    [][\A k \in Caps : CerradoVivo(k) => (CerradoVivo(k)' \/ nv' = nv + 1)]_vars

(* L1. Toda version en produccion acaba terminada, o la obra acaba         *)
(* detenida y dice por que. Incluye las versiones del lector.              *)
AcabaTerminadaODetenida == (~terminada[nv]) ~> (terminada[nv] \/ detenida)

=============================================================================
