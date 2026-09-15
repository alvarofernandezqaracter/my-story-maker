// §9 Inventario de validadores. Comprobaciones deterministas en codigo, con id
// VD-xx. No confundir con el agente validador de §5: aqui no hay criterio
// literario ni llamadas a modelos, solo reglas que se cumplen o no.
//
// Bloqueante: el artefacto no se usa. Aviso: se registra y el proceso sigue.
import { comprobarForma, SALIDAS, DIMENSIONES } from './esquemas.mjs';

export const BLOQ = 'bloqueante';
export const AVISO = 'aviso';

const ok = (id) => ({ id, ok: true, severidad: null, detalles: [] });
const falla = (id, severidad, detalles) => ({
  id, ok: false, severidad, detalles: [].concat(detalles),
});

/** Resultado agregado de una tanda de comprobaciones. */
export class Resultado {
  constructor(comprobaciones) {
    this.comprobaciones = comprobaciones;
  }

  get bloqueantes() {
    return this.comprobaciones.filter((c) => !c.ok && c.severidad === BLOQ);
  }

  get avisos() {
    return this.comprobaciones.filter((c) => !c.ok && c.severidad === AVISO);
  }

  get ok() { return this.bloqueantes.length === 0; }

  /** Las incidencias en el formato que viaja al escritor en el reintento (§8). */
  incidencias() {
    return this.comprobaciones.filter((c) => !c.ok).map((c) => ({
      cita: `[${c.id}]`,
      severidad: c.severidad === BLOQ ? 'grave' : 'aviso',
      sugerencia: c.detalles.join('; '),
    }));
  }

  resumen() {
    return this.comprobaciones.filter((c) => !c.ok)
      .map((c) => `${c.id} (${c.severidad}): ${c.detalles.join('; ')}`);
  }
}

// ---------------------------------------------------------------- VD-01, VD-02

/** VD-01 la salida parsea y cumple el esquema; VD-02 obligatorios no vacios. */
export function comprobarSalidaDeAgente(rol, salida) {
  if (salida === null || typeof salida !== 'object' || Array.isArray(salida)) {
    return new Resultado([
      falla('VD-01', BLOQ, 'la salida no parsea como objeto'),
      ok('VD-02'),
    ]);
  }
  const esquema = SALIDAS[rol];
  if (!esquema) throw new Error(`rol sin contrato de salida: ${rol}`);
  const fallos = comprobarForma(salida, esquema);
  const ausentes = fallos.filter((f) => f.includes('obligatorio ausente'));
  const forma = fallos.filter((f) => !f.includes('obligatorio ausente'));
  return new Resultado([
    forma.length ? falla('VD-01', BLOQ, forma) : ok('VD-01'),
    ausentes.length ? falla('VD-02', BLOQ, ausentes) : ok('VD-02'),
  ]);
}

// ---------------------------------------------------------------------- VD-03

/** VD-03 los ids referenciados existen en el canon. Arquitecto y cronista. */
export function comprobarReferencias(rol, salida, conocidos) {
  const huerfanos = [];
  if (rol === 'arquitecto') {
    // El arquitecto trae sus propios personajes: valen los que el mismo propone.
    const propios = new Set((salida.personajes ?? []).map((p) => p.id));
    for (const f of salida.capitulos ?? []) {
      for (const id of f.personajes ?? []) {
        if (!propios.has(id) && !conocidos.personajes.has(id)) {
          huerfanos.push(`capitulo ${f.numero}: personaje ${id}`);
        }
      }
    }
  }
  if (rol === 'cronista') {
    for (const id of salida.personajes_presentes ?? []) {
      if (!conocidos.personajes.has(id)) huerfanos.push(`personajes_presentes: ${id}`);
    }
    for (const c of salida.cambios_personaje ?? []) {
      if (!conocidos.personajes.has(c.id)) huerfanos.push(`cambios_personaje: ${c.id}`);
    }
    for (const e of salida.eventos ?? []) {
      for (const id of e.personajes ?? []) {
        if (!conocidos.personajes.has(id)) huerfanos.push(`evento ${e.id}: personaje ${id}`);
      }
      if (e.dato_id && !conocidos.datos.has(e.dato_id)) {
        huerfanos.push(`evento ${e.id}: dato ${e.dato_id}`);
      }
    }
  }
  return huerfanos.length ? falla('VD-03', BLOQ, huerfanos) : ok('VD-03');
}

// ---------------------------------------------------------------------- VD-04

/** VD-04 todo dato historico lleva fuente y estado valido. Devuelve los malos. */
export function comprobarDossier(datos) {
  const malos = [];
  for (const d of datos ?? []) {
    const sinFuente = !d.fuente || String(d.fuente).trim() === '';
    const estadoMalo = !['verificado', 'sin_verificar', 'inventado'].includes(d.estado);
    // Un dato verificado tiene que apoyarse en algo que no sea la memoria del modelo.
    const verificadoSinRespaldo = d.estado === 'verificado' && d.fuente === 'modelo';
    if (sinFuente || estadoMalo || verificadoSinRespaldo) {
      malos.push({
        id: d.id,
        motivo: sinFuente ? 'sin fuente'
          : estadoMalo ? `estado no valido: ${d.estado}`
            : 'marcado verificado con fuente "modelo"',
      });
    }
  }
  const comprobacion = malos.length
    ? falla('VD-04', BLOQ, malos.map((m) => `${m.id}: ${m.motivo}`))
    : ok('VD-04');
  comprobacion.malos = malos;
  return comprobacion;
}

// ---------------------------------------------------------------------- VD-05

/** VD-05 evento de trama con capitulo; evento historico sin el. */
export function comprobarEventos(eventos) {
  const malos = [];
  for (const e of eventos ?? []) {
    if (e.tipo === 'trama' && (e.capitulo === null || e.capitulo === undefined)) {
      malos.push(`${e.id}: evento de trama sin capitulo`);
    }
    if (e.tipo === 'historico' && e.capitulo !== null && e.capitulo !== undefined) {
      malos.push(`${e.id}: evento historico con capitulo`);
    }
  }
  return malos.length ? falla('VD-05', BLOQ, malos) : ok('VD-05');
}

// ---------------------------------------------------------------------- VD-06

/** VD-06 solo hay resumen si el capitulo esta aprobado. */
export function comprobarResumenSoloSiAprobado(intentoAprobado) {
  return intentoAprobado
    ? ok('VD-06')
    : falla('VD-06', BLOQ, 'no hay intento aprobado: el resumen no puede entrar en el canon');
}

// ---------------------------------------------------------------------- VD-07

/** VD-07 numero de capitulos dentro de los margenes de config. */
export function comprobarNumeroDeCapitulos(propuestos, pedidos, margenes) {
  const min = Math.floor(pedidos * margenes.capitulos_min);
  const max = Math.ceil(pedidos * margenes.capitulos_max);
  const comprobacion = (propuestos >= min && propuestos <= max)
    ? ok('VD-07')
    : falla('VD-07', BLOQ,
      `la escaleta trae ${propuestos} capitulos y el margen para ${pedidos} es [${min}, ${max}]`);
  comprobacion.margen = { min, max };
  return comprobacion;
}

// ---------------------------------------------------------------------- VD-08

export function contarPalabras(texto) {
  return (String(texto).trim().match(/\S+/g) ?? []).length;
}

export function contarParrafos(texto) {
  return String(texto).split(/\n\s*\n/)
    .map((p) => p.trim())
    .filter((p) => p !== '' && !/^#{1,6}\s/.test(p))
    .length;
}

/**
 * VD-08, la unica comprobacion de dos escalones y por eso lleva dos margenes.
 * Dentro de palabras_aviso el texto vale y la desviacion viaja como aviso al
 * reintento; pasado palabras_bloqueo no se gasta la llamada al validador.
 */
export function comprobarCapituloRedactado(texto, palabrasObjetivo, margenes) {
  const palabras = contarPalabras(texto);
  const parrafos = contarParrafos(texto);
  const desvio = palabrasObjetivo > 0
    ? Math.abs(palabras - palabrasObjetivo) / palabrasObjetivo
    : 0;

  const detalles = [];
  let severidad = null;
  if (parrafos < margenes.parrafos_min) {
    severidad = BLOQ;
    detalles.push(`${parrafos} parrafos, el minimo es ${margenes.parrafos_min}`);
  }
  if (desvio > margenes.palabras_bloqueo) {
    severidad = BLOQ;
    detalles.push(`${palabras} palabras frente a ${palabrasObjetivo} objetivo`
      + ` (desvio ${(desvio * 100).toFixed(0)}%, bloqueo en ${margenes.palabras_bloqueo * 100}%)`);
  } else if (desvio > margenes.palabras_aviso) {
    severidad = severidad ?? AVISO;
    detalles.push(`${palabras} palabras frente a ${palabrasObjetivo} objetivo`
      + ` (desvio ${(desvio * 100).toFixed(0)}%, aviso en ${margenes.palabras_aviso * 100}%)`);
  }

  const comprobacion = severidad ? falla('VD-08', severidad, detalles) : ok('VD-08');
  comprobacion.palabras = palabras;
  comprobacion.parrafos = parrafos;
  return comprobacion;
}

// ---------------------------------------------------------------------- VD-09

/** VD-09 personajes presentes ⊆ personajes de la ficha. Suele ser colado. */
export function comprobarPersonajesPresentes(presentes, deLaFicha) {
  const permitidos = new Set(deLaFicha);
  const colados = (presentes ?? []).filter((id) => !permitidos.has(id));
  return colados.length
    ? falla('VD-09', BLOQ, `personajes que no estan en la ficha: ${colados.join(', ')}`)
    : ok('VD-09');
}

// ---------------------------------------------------------------------- VD-10

/** VD-10 tres dimensiones, una vez cada una, nota entera 1-5. */
export function comprobarRevisiones(revisiones) {
  const detalles = [];
  const vistas = (revisiones ?? []).map((r) => r.dimension);
  for (const d of DIMENSIONES) {
    const veces = vistas.filter((v) => v === d).length;
    if (veces !== 1) detalles.push(`dimension ${d} aparece ${veces} veces, debe aparecer 1`);
  }
  for (const v of vistas) {
    if (!DIMENSIONES.includes(v)) detalles.push(`dimension desconocida: ${v}`);
  }
  for (const r of revisiones ?? []) {
    if (!Number.isInteger(r.nota) || r.nota < 1 || r.nota > 5) {
      detalles.push(`${r.dimension}: nota ${r.nota} no es un entero entre 1 y 5`);
    }
  }
  return detalles.length ? falla('VD-10', BLOQ, detalles) : ok('VD-10');
}

// ---------------------------------------------------------------------- VD-11

/**
 * VD-11 ningun bloqueante pendiente al confirmar. La transaccion del canon vive
 * en Canon.escrituraDelCronista; aqui se decide si se llega a abrir.
 */
export function comprobarSinBloqueantesPendientes(resultados) {
  const pendientes = resultados.flatMap((r) => (r instanceof Resultado ? r.bloqueantes : []))
    .concat(resultados.filter((r) => !(r instanceof Resultado) && !r.ok && r.severidad === BLOQ));
  return pendientes.length
    ? falla('VD-11', BLOQ, `bloqueantes sin resolver: ${pendientes.map((p) => p.id).join(', ')}`)
    : ok('VD-11');
}

export const _internos = { ok, falla };
