// §10 Inventario de skills. Carpetas con instrucciones reutilizables que el
// harness carga al construir cada llamada. Aqui va lo estable y repetido; lo
// que cambia en cada capitulo viaja en el paquete de contexto (§7), no aqui.
//
// Una skill es texto que lee un modelo, nunca fuente de verdad para el codigo:
// numeros y umbrales viven en config.json (§12).
import { readFileSync, existsSync, readdirSync } from 'node:fs';
import { join } from 'node:path';

/** Que skill carga cada rol de §5. */
export const SKILLS_POR_ROL = {
  investigador: ['formato-dossier'],
  arquitecto: ['formato-fichas'],
  escritor: ['formato-paquete-contexto', 'estilo-prosa'],
  validador: ['rubricas-validador'],
  cronista: ['formato-fichas'],
  editor_global: [],
};

function frontmatter(bruto) {
  const m = bruto.match(/^---\n([\s\S]*?)\n---\n?/);
  if (!m) return { meta: {}, cuerpo: bruto };
  const meta = {};
  for (const linea of m[1].split('\n')) {
    const par = linea.match(/^([\w-]+):\s*(.*)$/);
    if (par) meta[par[1]] = par[2].trim();
  }
  return { meta, cuerpo: bruto.slice(m[0].length) };
}

export function cargarSkill(nombre, raiz = 'skills') {
  const ruta = join(raiz, nombre, 'SKILL.md');
  if (!existsSync(ruta)) throw new Error(`skill no encontrada: ${ruta}`);
  const { meta, cuerpo } = frontmatter(readFileSync(ruta, 'utf8'));
  return { nombre, meta, cuerpo: cuerpo.trim(), ruta };
}

export function listarSkills(raiz = 'skills') {
  if (!existsSync(raiz)) return [];
  return readdirSync(raiz, { withFileTypes: true })
    .filter((e) => e.isDirectory() && existsSync(join(raiz, e.name, 'SKILL.md')))
    .map((e) => cargarSkill(e.name, raiz));
}

/**
 * Instrucciones de un rol: su definicion de agente mas las skills que le tocan.
 * El agente vive en agentes/<rol>.md y no lleva numeros: los umbrales que
 * necesite se le inyectan desde config al construir la llamada.
 */
export function instruccionesDe(rol, { raizAgentes = 'agentes', raizSkills = 'skills' } = {}) {
  const rutaAgente = join(raizAgentes, `${rol.replace(/_/g, '-')}.md`);
  if (!existsSync(rutaAgente)) throw new Error(`agente no encontrado: ${rutaAgente}`);
  const { meta, cuerpo } = frontmatter(readFileSync(rutaAgente, 'utf8'));
  const skills = (SKILLS_POR_ROL[rol] ?? []).map((s) => cargarSkill(s, raizSkills));
  const partes = [cuerpo.trim()];
  for (const skill of skills) {
    partes.push(`# Skill: ${skill.nombre}\n\n${skill.cuerpo}`);
  }
  return { rol, meta, skills: skills.map((s) => s.nombre), texto: partes.join('\n\n---\n\n') };
}
