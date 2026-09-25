/-!
# Los invariantes de la cronologia de una obra (SPEC1 4.16)

Lo que el volcado formal le pide a Lean que demuestre sobre la cronologia de
una version. Este fichero es entrada versionada con el repositorio, como el
guion: el sistema lo lee y nunca lo escribe. La cronologia concreta de cada
version la genera `novela.demostrador` en un directorio temporal, importa este
modulo y demuestra con `decide` cada invariante sobre sus datos.

Todo son naturales, para que el nucleo de Lean los compare sin interpretar
texto:

* Una fecha ISO parcial es un intervalo de dias escrito `AAAAMMDD`: `1587`
  es `[15870101, 15871231]`, `1587-04` es `[15870401, 15870431]` y
  `1587-04-03` es `[15870403, 15870403]`. Sin fecha, `[0, 99999999]`, que no
  choca con nada: lo que la cronologia no registra no se puede contradecir.
* Un personaje o un lugar es su posicion en la tabla del volcado, desde 1. El
  `0` es «no consta».
* Un capitulo `0` es un suceso que no pertenece a ninguno.

Cada invariante se comprueba en el sentido de «no hay contradiccion segura»:
con fechas parciales solo falla lo que falla para cualquier dia del intervalo.
-/

namespace Cronologia

/-- Quien estaba presente, con el intervalo en que nacio. -/
structure Presente where
  id : Nat
  nacDesde : Nat
  nacHasta : Nat
deriving Repr

/-- Una fila de la cronologia: un `EventoEstado` o un `Evento` del mundo. -/
structure Suceso where
  capitulo : Nat
  desde : Nat
  hasta : Nat
  lugar : Nat
  presentes : List Presente
  /-- El personaje que muere en el suceso, o `0` si no muere nadie. -/
  muere : Nat
  /-- El personaje que llega al lugar del suceso con un `viaja_a`, o `0`. -/
  llega : Nat
deriving Repr

/-- Los personajes presentes en un suceso. -/
abbrev ids (s : Suceso) : List Nat := s.presentes.map (·.id)

/-- Mas años que estos entre el nacimiento y un suceso no es una edad. -/
abbrev edadMaxima : Nat := 120

/-- Orden temporal: un suceso de un capitulo anterior no ocurre despues de
uno de un capitulo posterior. -/
abbrev Precede (a b : Suceso) : Prop :=
  0 < a.capitulo → a.capitulo < b.capitulo → a.desde ≤ b.hasta

/-- Edad coherente: el presente habia nacido y no pasa de la edad maxima. -/
abbrev NacidoAntes (s : Suceso) (p : Presente) : Prop :=
  p.nacDesde ≤ s.hasta ∧ s.desde / 10000 ≤ p.nacHasta / 10000 + edadMaxima

abbrev EdadCoherente (s : Suceso) : Prop :=
  ∀ p ∈ s.presentes, NacidoAntes s p

/-- Dos sucesos del mismo dia exacto. -/
abbrev MismoDia (a b : Suceso) : Prop :=
  a.desde = a.hasta ∧ b.desde = b.hasta ∧ a.desde = b.desde

/-- En la cronologia consta que `p` llego el dia `a` a su lugar o al de `b`
(SPEC1 RF-213): un suceso de ese dia, en uno de los dos, en el que llega. -/
abbrev Llego (c : List Suceso) (p : Nat) (a b : Suceso) : Prop :=
  c.any (fun x => decide (MismoDia x a) && x.llega == p &&
    (x.lugar == a.lugar || x.lugar == b.lugar)) = true

/-- Nadie esta en dos sitios a la vez: dos sucesos del mismo dia en lugares
distintos no comparten ningun presente, salvo que conste que ese presente
viajo ese dia a uno de los dos. -/
abbrev UnSoloLugar (c : List Suceso) (a b : Suceso) : Prop :=
  MismoDia a b → 0 < a.lugar → 0 < b.lugar → a.lugar ≠ b.lugar →
    ∀ p ∈ ids a, p ∈ ids b → Llego c p a b

/-- `b` ocurre despues de `a`: por capitulo, o por fecha sin solaparse. -/
abbrev Posterior (a b : Suceso) : Prop :=
  (0 < a.capitulo ∧ a.capitulo < b.capitulo) ∨ a.hasta < b.desde

/-- Quien muere en `a` no esta presente en ningun suceso posterior. -/
abbrev NoReaparece (a b : Suceso) : Prop :=
  0 < a.muere → Posterior a b → a.muere ∉ ids b

/-! ## Los cuatro invariantes sobre una cronologia entera -/

def OrdenTemporal (c : List Suceso) : Prop := ∀ a ∈ c, ∀ b ∈ c, Precede a b
def EdadesCoherentes (c : List Suceso) : Prop := ∀ s ∈ c, EdadCoherente s
def NadieEnDosSitios (c : List Suceso) : Prop := ∀ a ∈ c, ∀ b ∈ c, UnSoloLugar c a b
def NadieReaparece (c : List Suceso) : Prop := ∀ a ∈ c, ∀ b ∈ c, NoReaparece a b

instance (c : List Suceso) : Decidable (OrdenTemporal c) :=
  inferInstanceAs (Decidable (∀ a ∈ c, ∀ b ∈ c, Precede a b))
instance (c : List Suceso) : Decidable (EdadesCoherentes c) :=
  inferInstanceAs (Decidable (∀ s ∈ c, EdadCoherente s))
instance (c : List Suceso) : Decidable (NadieEnDosSitios c) :=
  inferInstanceAs (Decidable (∀ a ∈ c, ∀ b ∈ c, UnSoloLugar c a b))
instance (c : List Suceso) : Decidable (NadieReaparece c) :=
  inferInstanceAs (Decidable (∀ a ∈ c, ∀ b ∈ c, NoReaparece a b))

/-- La cronologia es coherente si cumple los cuatro. -/
abbrev Coherente (c : List Suceso) : Prop :=
  OrdenTemporal c ∧ EdadesCoherentes c ∧ NadieEnDosSitios c ∧ NadieReaparece c

/-- Reune los cuatro invariantes de una cronologia a partir de lo demostrado
suceso a suceso: es lo que hace el volcado de cada version. -/
theorem coherente_de (c : List Suceso)
    (orden : ∀ a ∈ c, ∀ b ∈ c, Precede a b)
    (edad : ∀ s ∈ c, EdadCoherente s)
    (lugar : ∀ a ∈ c, ∀ b ∈ c, UnSoloLugar c a b)
    (reaparece : ∀ a ∈ c, ∀ b ∈ c, NoReaparece a b) : Coherente c :=
  ⟨orden, edad, lugar, reaparece⟩

/-- Un invariante demostrado para el primer suceso y para el resto vale para
toda la lista. El volcado encadena asi lo demostrado suceso a suceso. -/
theorem todos_cons {P : Suceso → Prop} {s : Suceso} {c : List Suceso}
    (h : P s) (t : ∀ x ∈ c, P x) : ∀ x ∈ s :: c, P x :=
  List.forall_mem_cons.2 ⟨h, t⟩

theorem todos_nil {P : Suceso → Prop} : ∀ x ∈ ([] : List Suceso), P x :=
  fun _ h => nomatch h

/-! ## Lo que se demuestra una vez para toda obra -/

/-- Una cronologia vacia no contradice nada. -/
theorem vacia_coherente : Coherente [] := by decide

/-- Lo que no consta no se puede contradecir: un suceso sin fecha, sin lugar y
sin presentes cumple los cuatro con cualquier otro. -/
theorem sin_datos_no_contradice (c : List Suceso) (b : Suceso) :
    Precede ⟨0, 0, 99999999, 0, [], 0, 0⟩ b ∧ EdadCoherente ⟨0, 0, 99999999, 0, [], 0, 0⟩ ∧
      UnSoloLugar c ⟨0, 0, 99999999, 0, [], 0, 0⟩ b ∧
        NoReaparece ⟨0, 0, 99999999, 0, [], 0, 0⟩ b := by
  refine ⟨?_, ?_, ?_, ?_⟩
  · intro h; exact absurd h (by decide)
  · intro p hp; simp at hp
  · intro _ h; exact absurd h (by decide)
  · intro h; exact absurd h (by decide)

/-- Un personaje que muere en un capitulo y esta presente en uno posterior
rompe la cronologia, sean cuales sean las fechas. -/
theorem reaparecer_rompe (a b : Suceso) (hm : 0 < a.muere) (hc : 0 < a.capitulo)
    (hab : a.capitulo < b.capitulo) (hp : a.muere ∈ ids b) : ¬ NoReaparece a b :=
  fun h => h hm (Or.inl ⟨hc, hab⟩) hp

/-- Aplazar la fecha de un suceso nunca le hace preceder a otro que no
precedia: el orden temporal es monotono en la fecha del segundo. -/
theorem precede_monotono (a b : Suceso) (h : Precede a b) (n : Nat) :
    Precede a { b with hasta := b.hasta + n } := by
  intro h1 h2
  have := h h1 h2
  simp only
  omega

end Cronologia
