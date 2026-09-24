// El único sitio que sabe cómo viene un error del servidor. Todo lo demás
// recibe un Fallo y lo pinta.

export type Fallo =
  | { tipo: "sin_servidor"; mensaje: string }
  | { tipo: "rechazo"; estado: number; mensaje: string; campos: string[] };

// Es el único texto de error que redacta la interfaz; los demás son del
// servidor, tal cual (SPEC2 RF-61).
export const MENSAJE_SIN_SERVIDOR =
  "No hay conexión con el servidor. Lo que llevas hecho no se ha perdido.";

export function falloDeRed(): Fallo {
  return { tipo: "sin_servidor", mensaje: MENSAJE_SIN_SERVIDOR };
}

type ErrorDeValidacion = { loc: (string | number)[]; msg: string };

function esObjeto(valor: unknown): valor is Record<string, unknown> {
  return typeof valor === "object" && valor !== null && !Array.isArray(valor);
}

function esErrorDeValidacion(valor: unknown): valor is ErrorDeValidacion {
  return esObjeto(valor) && Array.isArray(valor.loc) && typeof valor.msg === "string";
}

// {"detail": "texto"}                -> rechazo con ese texto, sin tocarlo
// {"detalle": "texto", "campos": []} -> rechazo con texto y rutas
// {"detail": [ValidationError...]}   -> rechazo; mensaje = msg de cada uno, campos = loc sin el primer tramo
// cualquier otra cosa (sin JSON)     -> sin_servidor
export function falloDesde(estado: number, cuerpo: unknown): Fallo {
  if (esObjeto(cuerpo)) {
    if (typeof cuerpo.detail === "string") {
      return { tipo: "rechazo", estado, mensaje: cuerpo.detail, campos: [] };
    }
    if (typeof cuerpo.detalle === "string") {
      const campos = Array.isArray(cuerpo.campos)
        ? cuerpo.campos.filter((c): c is string => typeof c === "string")
        : [];
      return { tipo: "rechazo", estado, mensaje: cuerpo.detalle, campos };
    }
    if (Array.isArray(cuerpo.detail) && cuerpo.detail.every(esErrorDeValidacion)) {
      const errores = cuerpo.detail;
      return {
        tipo: "rechazo",
        estado,
        mensaje: errores.map((e) => e.msg).join("; "),
        campos: errores.map((e) => e.loc.slice(1).join(".")),
      };
    }
  }
  return falloDeRed();
}
