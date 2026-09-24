// Nombres cortos para los tipos generados desde el contrato. Aquí no se define
// ninguna forma: todas salen de esquema.d.ts.
import type { components } from "./esquema";

type Esquemas = components["schemas"];

export type PeticionDeEntrevista = Esquemas["PeticionDeEntrevista"];
export type BorradorDeBrief = Esquemas["BorradorDeBrief"];
export type BorradorDeDestinatario = Esquemas["BorradorDeDestinatario"];
export type PasadaDeEntrevista = Esquemas["PasadaDeEntrevista"];
export type Contradiccion = Esquemas["Contradiccion"];
export type TipoDeContradiccion = Contradiccion["tipo"];
export type HechoExtraido = Esquemas["HechoExtraido"];
export type FichaDeObra = Esquemas["FichaDeObra"];
export type ObraDelTaller = Esquemas["ObraDelTaller"];
export type SituacionDeLaObra = FichaDeObra["situacion"];
export type Progreso = Esquemas["Progreso"];
export type Manuscrito = Esquemas["Manuscrito"];
export type UnidadDelManuscrito = Esquemas["UnidadDelManuscrito"];
export type Confirmacion = Esquemas["Confirmacion"];
export type TrazaServida = Esquemas["TrazaServida"];
export type HechoDeLaBiblia = Esquemas["HechoDeLaBiblia"];
export type VersionDeLaObra = Esquemas["VersionDeLaObra"];
export type CambioDelLector = Esquemas["CambioDelLector"];
export type VersionAbierta = Esquemas["VersionAbierta"];
export type CriticaServida = Esquemas["CriticaServida"];
export type PuertaDePublicacion = Esquemas["PuertaDePublicacion"];
export type FalloDeLaPuerta = Esquemas["FalloDeLaPuerta"];
export type Publicacion = Esquemas["Publicacion"];
