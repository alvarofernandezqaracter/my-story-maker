// §4 Arquitectura y flujo, §8 loop de capitulo y gate, §11 editor global.
// Tres tramos: preparacion (una vez), loop de capitulo (una vez por capitulo) y
// cierre (una vez). El canon esta en medio de todos y es el unico punto de
// contacto: los agentes nunca se pasan datos entre si por fuera del canon o del
// paquete de contexto.
import { writeFileSync, mkdirSync } from 'node:fs';
import { join } from 'node:path';
import { generarContexto } from './contexto.mjs';
import { gate, mejorIntento, incidenciasOrdenadas, media, notas } from './gate.mjs';
import { ParadaDelProceso } from './agentes.mjs';
import { DIMENSIONES } from './esquemas.mjs';
import {
  Resultado,
  comprobarDossier, comprobarReferencias, comprobarEventos,
  comprobarNumeroDeCapitulos, comprobarCapituloRedactado, comprobarPersonajesPresentes,
  comprobarRevisiones, comprobarResumenSoloSiAprobado, comprobarSinBloqueantesPendientes,
} from './validadores.mjs';

const CARPETA_CAPITULOS = 'capitulos';

export function rutaDeIntento(capitulo, intento, carpeta = CARPETA_CAPITULOS) {
  // El par capitulo e intento identifica cada fichero, asi que repetir un
  // intento sobrescribe en lugar de duplicar (§13).
  return join(carpeta, `${String(capitulo).padStart(3, '0')}-i${intento}.md`);
}

/** Registro de lo que va pasando, para que la CLI lo cuente sin adivinar. */
function traza(diario, tipo, datos) {
  diario.push({ tipo, ...datos });
  return diario.at(-1);
}

// ============================================================ PREPARACION

export async function preparar({ canon, agentes, config, diario = [] }) {
  const proyecto = canon.proyecto();
  if (!proyecto) throw new ParadaDelProceso('no hay brief: usa "novela brief" antes de preparar');

  const brief = {
    epoca: proyecto.epoca,
    premisa: proyecto.premisa,
    tono: proyecto.tono,
    capitulos: proyecto.capitulos,
    palabras_por_capitulo: proyecto.palabras_por_capitulo,
  };

  // ---- Investigador. VD-04 corre antes de habilitar al arquitecto (§9).
  if (proyecto.estado === 'borrador') {
    const { salida } = await agentes.pedir(
      'investigador',
      { brief, busqueda_web: config.busqueda_web },
      (s) => [comprobarDossier(s.datos)],
    );
    canon.guardarDatos(salida.datos);
    canon.marcarEstado('investigado');
    traza(diario, 'dossier', { datos: salida.datos.length });
  }

  // ---- Arquitecto. Necesita el dossier cerrado.
  if (canon.estado() === 'investigado') {
    const dossier = canon.datos();
    const conocidos = canon.idsConocidos();
    const { salida } = await agentes.pedir(
      'arquitecto',
      { brief, dossier },
      (s) => [
        comprobarNumeroDeCapitulos(s.capitulos.length, brief.capitulos, config.margenes),
        comprobarReferencias('arquitecto', s, conocidos),
      ],
    );
    canon.guardarPersonajes(salida.personajes);
    canon.guardarFichas(salida.capitulos);
    canon.marcarEstado('estructurado');
    traza(diario, 'escaleta', {
      personajes: salida.personajes.length, capitulos: salida.capitulos.length,
    });
  }

  return { estado: canon.estado(), diario };
}

// ======================================================= LOOP DE CAPITULO

/**
 * Un capitulo se da por bueno cuando pasa el gate, no cuando el escritor
 * termina. Todo lo de aqui es codigo salvo las cuatro llamadas a agentes.
 */
export async function escribirCapitulo({ canon, agentes, config, numero, diario = [] }) {
  canon.marcarFicha(numero, 'en_curso');
  if (canon.estado() === 'estructurado') canon.marcarEstado('escribiendo');

  const paquete = generarContexto(canon, numero, config);
  if (!paquete.cabe) {
    // §7: si no cabe ni recortando, el capitulo se bloquea en lugar de
    // escribirse con el contexto mutilado.
    canon.marcarFicha(numero, 'bloqueado');
    canon.marcarEstado('bloqueado');
    traza(diario, 'bloqueado', { capitulo: numero, motivo: 'el paquete de contexto no cabe' });
    return { aprobado: false, motivo: 'contexto' };
  }
  if (paquete.recortes.length) {
    traza(diario, 'recorte', { capitulo: numero, bloques: paquete.recortes });
  }

  const ficha = paquete.bloques.encargo;
  const personajes = paquete.bloques.personajes;
  mkdirSync(CARPETA_CAPITULOS, { recursive: true });

  let incidencias = [];
  let textoPrevio = null;

  for (let intento = 1; intento <= config.gate.max_intentos; intento += 1) {
    const esUltimo = intento === config.gate.max_intentos;

    // ---- Escritor
    const { salida: redaccion } = await agentes.pedir('escritor', {
      paquete: paquete.texto,
      encargo: ficha,
      personajes,
      texto_previo: textoPrevio,
      incidencias,
      intento,
    });

    const ruta = rutaDeIntento(numero, intento);
    writeFileSync(ruta, redaccion.texto, 'utf8');

    // ---- VD-08, antes del validador
    const det = comprobarCapituloRedactado(
      redaccion.texto, ficha.palabras_objetivo, config.margenes,
    );
    canon.guardarIntento({
      capitulo: numero,
      intento,
      ruta,
      palabras: det.palabras,
      faltantes: redaccion.faltantes ?? [],
    });
    const resultadoDet = new Resultado([det]);

    if (resultadoDet.bloqueantes.length) {
      // VD-08 en su escalon de bloqueo: se reintenta la generacion sin gastar
      // la llamada al agente validador, y el reintento va de cero.
      traza(diario, 'vd08', { capitulo: numero, intento, detalles: det.detalles });
      canon.marcarIntento(numero, intento, 'descartado');
      incidencias = resultadoDet.incidencias();
      textoPrevio = null;
      continue;
    }

    // ---- Validador. Una llamada, o tres si validador.modo es separado (§5).
    const revisiones = await validar({
      agentes, config, texto: redaccion.texto, paquete, encargo: ficha, intento,
    });
    canon.guardarRevisiones(numero, intento, revisiones);

    // ---- Gate. Solo se calcula sobre revisiones que ya pasaron VD-10 (§9).
    const veredicto = gate(revisiones, config.gate);
    traza(diario, 'gate', {
      capitulo: numero,
      intento,
      aprueba: veredicto.aprueba,
      notas: notas(revisiones),
      media: Number(veredicto.media.toFixed(2)),
      motivos: veredicto.motivos,
    });

    if (veredicto.aprueba) {
      canon.fijarIntentoAprobado(numero, intento);
      await volcarEnElCanon({
        canon, agentes, numero, texto: redaccion.texto, ficha, personajes, diario,
      });
      return { aprobado: true, intento, revisiones };
    }

    // §8: incidencias del validador mas los avisos deterministas.
    incidencias = [...incidenciasOrdenadas(revisiones), ...resultadoDet.incidencias()];
    // Su propio texto en todos los intentos menos el ultimo: ahi se le pide
    // arreglo quirurgico. El ultimo va desde cero.
    textoPrevio = esUltimo ? null : redaccion.texto;
  }

  // ---- Al agotar los intentos
  const todos = canon.intentos(numero);
  const mejor = mejorIntento(todos);
  for (const i of todos) {
    canon.marcarIntento(numero, i.intento, i === mejor ? 'propuesto' : 'descartado');
  }
  canon.marcarFicha(numero, 'bloqueado');
  canon.marcarEstado('bloqueado');
  traza(diario, 'bloqueado', {
    capitulo: numero,
    motivo: `agotados los ${config.gate.max_intentos} intentos`,
    conservado: mejor ? mejor.ruta : null,
  });
  return { aprobado: false, motivo: 'intentos' };
}

/**
 * Una llamada al validador, o tres en paralelo si el modo es separado (§5).
 * VD-10 se aplica siempre al conjunto de las tres dimensiones, venga de donde
 * venga, y su fallo reintenta la llamada al validador, no al escritor (§9).
 */
async function validar({ agentes, config, texto, paquete, encargo, intento }) {
  const base = { texto, paquete: paquete.texto, encargo, intento };

  if (config.validador.modo !== 'separado') {
    const { salida } = await agentes.pedir(
      'validador', base, (s) => [comprobarRevisiones(s.revisiones)],
    );
    return salida.revisiones;
  }

  // Modo separado: cada llamada trae un bloque, y solo se comprueba ese bloque.
  const partes = await Promise.all(DIMENSIONES.map((dimension) => agentes.pedir(
    'validador',
    { ...base, dimension },
    (s) => [comprobarRevisiones([
      ...s.revisiones.filter((r) => r.dimension === dimension),
      ...DIMENSIONES.filter((d) => d !== dimension).map((d) => ({ dimension: d, nota: 3 })),
    ])],
  )));

  const revisiones = DIMENSIONES.map((d) => partes
    .flatMap((p) => p.salida.revisiones)
    .find((r) => r.dimension === d))
    .filter(Boolean);

  const vd10 = comprobarRevisiones(revisiones);
  if (!vd10.ok) {
    throw new ParadaDelProceso(
      'las tres llamadas al validador no componen tres bloques validos', vd10.detalles,
    );
  }
  return revisiones;
}

/**
 * Unica escritura en el canon dentro del loop: el cronista convierte el
 * capitulo aprobado en resumen y en cambios de ficha, y el harness lo persiste
 * en una transaccion (VD-11).
 */
async function volcarEnElCanon({ canon, agentes, numero, texto, ficha, personajes, diario }) {
  const conocidos = canon.idsConocidos();
  const { salida: propuesta, comprobaciones } = await agentes.pedir(
    'cronista',
    { texto, ficha, personajes },
    (s) => [
      comprobarPersonajesPresentes(s.personajes_presentes, ficha.personajes),
      comprobarReferencias('cronista', s, conocidos),
      comprobarEventos(s.eventos),
      comprobarResumenSoloSiAprobado(canon.intentoAprobado(numero)),
    ],
  );

  const vd11 = comprobarSinBloqueantesPendientes(comprobaciones);
  if (!vd11.ok) {
    throw new ParadaDelProceso('VD-11 impide confirmar la escritura del cronista', vd11.detalles);
  }

  canon.escrituraDelCronista(numero, propuesta);
  traza(diario, 'canon', {
    capitulo: numero,
    hilos_abiertos: propuesta.hilos_abiertos.length,
    hilos_cerrados: propuesta.hilos_cerrados.length,
    eventos: (propuesta.eventos ?? []).length,
  });
}

// ================================================================== CIERRE

/**
 * §11. Corre una sola vez, cuando el proyecto entra en escrito, y fuera del
 * loop. Lee los resumenes, nunca el texto. La lista se guarda como retoques.md
 * junto al canon, no dentro: el canon es la verdad de la novela escrita y esto
 * es una lista de tareas.
 */
export async function cerrar({ canon, agentes, ruta = 'retoques.md', diario = [] }) {
  const resumenes = canon.resumenes();
  const escaleta = canon.fichas();
  const personajes = canon.personajes();

  const { salida } = await agentes.pedir('editor_global', {
    resumenes, escaleta, personajes, hilos_vivos: canon.hilosVivos(),
  });

  writeFileSync(ruta, renderRetoques(salida.retoques, canon), 'utf8');
  canon.marcarEstado('editado');
  traza(diario, 'retoques', { total: salida.retoques.length, ruta });
  return { retoques: salida.retoques, ruta, diario };
}

function renderRetoques(retoques, canon) {
  const proyecto = canon.proyecto();
  const lineas = [
    '# Retoques finales',
    '',
    `Lista del editor global sobre ${canon.resumenes().length} capitulos aprobados.`,
    'El editor no aplica nada: decides tu que vale y lo aplicas editando los capitulos.',
    '',
    `- Epoca: ${proyecto.epoca}`,
    `- Tono: ${proyecto.tono}`,
    '',
  ];
  for (const r of retoques) {
    lineas.push(`## ${r.id} — ${r.tipo} (${r.severidad})`);
    lineas.push(`Capitulos: ${r.capitulos.join(', ') || '—'}`);
    lineas.push('');
    lineas.push(r.descripcion);
    lineas.push('');
  }
  if (!retoques.length) lineas.push('Sin retoques. Revisa si el cronista esta registrando hilos.');
  return lineas.join('\n');
}

// ============================================== ORQUESTACION Y REANUDACION

/** El primer capitulo que no esta aprobado. */
export function siguienteCapitulo(canon) {
  return canon.fichas().find((f) => f.estado !== 'aprobado') ?? null;
}

/**
 * §13. Un unico comando reanudar, sin argumentos: lee el estado del proyecto,
 * localiza el primer capitulo no aprobado y sigue desde ahi. Reanudar no
 * desbloquea: mientras el proyecto siga en bloqueado, vuelve a parar en el
 * mismo capitulo.
 */
export async function reanudar({ canon, agentes, config, diario = [] }) {
  const proyecto = canon.proyecto();
  if (!proyecto) throw new ParadaDelProceso('no hay brief que reanudar');

  if (proyecto.estado === 'bloqueado') {
    const bloqueado = canon.fichas().find((f) => f.estado === 'bloqueado');
    traza(diario, 'parada', {
      motivo: 'el proyecto esta bloqueado y reanudar no desbloquea',
      capitulo: bloqueado?.numero ?? null,
    });
    return { estado: 'bloqueado', diario };
  }

  if (['borrador', 'investigado'].includes(proyecto.estado)) {
    await preparar({ canon, agentes, config, diario });
  }

  // Los intentos huerfanos de una caida se descartan al relanzar (§13).
  for (const f of canon.fichas()) {
    if (f.estado === 'aprobado') continue;
    for (const i of canon.intentos(f.numero)) {
      if (i.estado === 'propuesto') canon.marcarIntento(f.numero, i.intento, 'descartado');
    }
  }

  let siguiente = siguienteCapitulo(canon);
  while (siguiente) {
    const res = await escribirCapitulo({
      canon, agentes, config, numero: siguiente.numero, diario,
    });
    if (!res.aprobado) return { estado: 'bloqueado', capitulo: siguiente.numero, diario };
    siguiente = siguienteCapitulo(canon);
  }

  canon.marcarEstado('escrito');
  const cierre = await cerrar({ canon, agentes, diario });
  return { estado: canon.estado(), retoques: cierre.retoques, diario };
}

export { media };
