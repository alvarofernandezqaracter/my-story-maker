// §7 Generador de contexto. Codigo, no agente: mismo capitulo y mismo canon dan
// siempre el mismo paquete. El escritor nunca consulta el canon por su cuenta.
import { readFileSync, existsSync } from 'node:fs';
import { normalizarFecha } from './canon.mjs';

/** Los cuatro bloques recortables, en el orden en que se recortan (§7). */
export const ORDEN_DE_RECORTE = ['memoria_larga', 'cronologia', 'reparto_fondo', 'epoca'];

/** Estimacion de tokens suficiente para decidir recortes. */
export function estimarTokens(texto) {
  return Math.ceil(String(texto).length / 4);
}

function primeraFrase(texto) {
  const corte = String(texto).match(/^.*?[.!?](\s|$)/s);
  return (corte ? corte[0] : String(texto)).trim();
}

function ultimasPalabras(texto, cuantas) {
  const palabras = String(texto).trim().match(/\S+/g) ?? [];
  return palabras.slice(-cuantas).join(' ');
}

function leerTexto(ruta) {
  return existsSync(ruta) ? readFileSync(ruta, 'utf8') : '';
}

/**
 * Construye los nueve bloques de §7 para un capitulo.
 * Devuelve el paquete sin recortar; el recorte lo aplica generarContexto.
 */
function bloques(canon, numero, config) {
  const ficha = canon.ficha(numero);
  if (!ficha) throw new Error(`no hay ficha del capitulo ${numero}`);

  const todosLosPersonajes = canon.personajes();
  const enEscena = new Set(ficha.personajes);

  // Encargo: la ficha entera, siempre.
  const encargo = ficha;

  // Personajes: fichas completas de quien sale.
  const personajes = canon.personajes(ficha.personajes);

  // Reparto de fondo: quien no sale pero se menciona en la sinopsis.
  const reparto_fondo = todosLosPersonajes
    .filter((p) => !enEscena.has(p.id))
    .filter((p) => ficha.sinopsis.toLowerCase().includes(p.nombre.toLowerCase()))
    .map((p) => ({ id: p.id, nombre: p.nombre, linea: primeraFrase(p.motivacion) }));

  // Memoria: resumenes de los capitulos aprobados anteriores.
  const anteriores = canon.resumenes().filter((r) => r.capitulo < numero);
  const corte = numero - config.contexto.ventana_resumenes;
  const memoria_reciente = anteriores.filter((r) => r.capitulo >= corte);
  const memoria_larga = anteriores.filter((r) => r.capitulo < corte)
    .map((r) => ({ capitulo: r.capitulo, resumen: primeraFrase(r.resumen) }));

  // Hilos vivos: abiertos y aun no cerrados.
  const hilos_vivos = canon.hilosVivos();

  // Epoca: datos que casan con las etiquetas de la ficha, verificado primero.
  const etiquetas = new Set(ficha.etiquetas.map((e) => e.toLowerCase()));
  const peso = { verificado: 0, sin_verificar: 1, inventado: 2 };
  const epoca = canon.datos()
    .filter((d) => d.etiquetas.some((e) => etiquetas.has(String(e).toLowerCase())))
    .sort((a, b) => (peso[a.estado] - peso[b.estado]) || a.id.localeCompare(b.id));

  // Cronologia: eventos entre la fecha de la ficha anterior y la de esta.
  const fichaAnterior = canon.fichas().filter((f) => f.numero < numero).at(-1) ?? null;
  const desde = fichaAnterior ? normalizarFecha(fichaAnterior.fecha) : null;
  const hasta = normalizarFecha(ficha.fecha);
  const cronologia = canon.eventos().filter((e) => {
    const f = normalizarFecha(e.fecha);
    if (!f || !hasta) return false;
    return (desde === null || f >= desde) && f <= hasta;
  });

  // Enganche: cola literal del capitulo anterior aprobado.
  let enganche = '';
  if (fichaAnterior) {
    const aprobado = canon.intentoAprobado(fichaAnterior.numero);
    if (aprobado) {
      enganche = ultimasPalabras(leerTexto(aprobado.ruta), config.contexto.palabras_enganche);
    }
  }

  return {
    encargo,
    personajes,
    reparto_fondo,
    memoria_reciente,
    memoria_larga,
    hilos_vivos,
    epoca,
    cronologia,
    enganche,
  };
}

/**
 * Serializa el paquete en el orden de §7. Este es el formato que el escritor
 * espera; la skill formato-paquete-contexto describe el mismo contrato en prosa.
 */
export function serializar(paquete) {
  const b = paquete.bloques;
  const partes = [];

  partes.push(`# Encargo del capitulo ${b.encargo.numero}`);
  partes.push([
    `- Titulo: ${b.encargo.titulo}`,
    `- Acto: ${b.encargo.acto}`,
    `- Fecha: ${b.encargo.fecha}`,
    `- Objetivo: ${b.encargo.objetivo}`,
    `- Palabras objetivo: ${b.encargo.palabras_objetivo}`,
    `- Sinopsis: ${b.encargo.sinopsis}`,
  ].join('\n'));

  partes.push('# Personajes en escena');
  partes.push(b.personajes.map((p) => [
    `## ${p.nombre} (${p.id}, ${p.rol})`,
    `- Voz: ${p.voz}`,
    `- Motivacion: ${p.motivacion}`,
    `- Arco: ${p.arco}`,
    `- Donde esta: ${p.ubicacion}`,
    `- Que sabe: ${p.sabe.length ? p.sabe.join(' | ') : '(sin anotar)'}`,
  ].join('\n')).join('\n\n') || '(ninguno)');

  if (b.reparto_fondo.length) {
    partes.push('# Reparto de fondo');
    partes.push(b.reparto_fondo.map((p) => `- ${p.nombre} (${p.id}): ${p.linea}`).join('\n'));
  }

  if (b.memoria_reciente.length) {
    partes.push('# Memoria reciente');
    partes.push(b.memoria_reciente.map((r) => `## Capitulo ${r.capitulo}\n${r.resumen}`).join('\n\n'));
  }

  if (b.memoria_larga.length) {
    partes.push('# Memoria larga');
    partes.push(b.memoria_larga.map((r) => `- Cap. ${r.capitulo}: ${r.resumen}`).join('\n'));
  }

  if (b.hilos_vivos.length) {
    partes.push('# Hilos vivos');
    partes.push(b.hilos_vivos.map((h) => `- (abierto en cap. ${h.capitulo}) ${h.hilo}`).join('\n'));
  }

  if (b.epoca.length) {
    // En el paquete viaja el estado de cada dato: el escritor necesita saber
    // que es firme y que es relleno.
    partes.push('# Epoca');
    partes.push(b.epoca.map((d) => `- [${d.estado}] (${d.categoria}) ${d.dato} — fuente: ${d.fuente}`)
      .join('\n'));
  }

  if (b.cronologia.length) {
    partes.push('# Cronologia');
    partes.push(b.cronologia.map((e) => `- ${e.fecha} (${e.tipo}) ${e.descripcion}`).join('\n'));
  }

  if (b.enganche) {
    partes.push('# Enganche con el capitulo anterior');
    partes.push(`> ${b.enganche}`);
  }

  return partes.join('\n\n');
}

/**
 * §7: si el paquete se pasa del tope se recorta en orden fijo. El encargo, los
 * personajes y los hilos vivos no se recortan; si aun asi no cabe, el capitulo
 * se marca bloqueado en lugar de escribirse con el contexto mutilado.
 */
export function generarContexto(canon, numero, config) {
  const paquete = { capitulo: numero, bloques: bloques(canon, numero, config), recortes: [] };
  const tope = config.contexto.tope_contexto;

  for (const nombre of ORDEN_DE_RECORTE) {
    while (estimarTokens(serializar(paquete)) > tope && paquete.bloques[nombre].length > 0) {
      paquete.bloques[nombre] = paquete.bloques[nombre].slice(0, -1);
      paquete.recortes.push(nombre);
    }
    if (estimarTokens(serializar(paquete)) <= tope) break;
  }

  paquete.texto = serializar(paquete);
  paquete.tokens = estimarTokens(paquete.texto);
  paquete.cabe = paquete.tokens <= tope;
  paquete.recortes = [...new Set(paquete.recortes)];
  return paquete;
}
