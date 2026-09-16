# §10 Inventario de skills. Carpetas con instrucciones reutilizables que el
# harness carga al construir cada llamada. Aqui va lo estable y repetido; lo
# que cambia en cada capitulo viaja en el paquete de contexto (§7), no aqui.
#
# Una skill es texto que lee un modelo, nunca fuente de verdad para el codigo:
# numeros y umbrales viven en config.json (§12).
import re
from pathlib import Path

# Que skill carga cada rol de §5.
SKILLS_POR_ROL = {
    'investigador': ['formato-dossier'],
    'arquitecto': ['formato-fichas'],
    'escritor': ['formato-paquete-contexto', 'estilo-prosa'],
    'validador': ['rubricas-validador'],
    'cronista': ['formato-fichas'],
    'editor_global': [],
}


def _frontmatter(bruto):
    m = re.match(r'^---\n(.*?)\n---\n?', bruto, re.DOTALL)
    if not m:
        return {}, bruto
    meta = {}
    for linea in m.group(1).split('\n'):
        par = re.match(r'^([\w-]+):\s*(.*)$', linea)
        if par:
            meta[par.group(1)] = par.group(2).strip()
    return meta, bruto[m.end():]


def cargar_skill(nombre, raiz='skills'):
    ruta = Path(raiz) / nombre / 'SKILL.md'
    if not ruta.exists():
        raise FileNotFoundError('skill no encontrada: {}'.format(ruta))
    meta, cuerpo = _frontmatter(ruta.read_text(encoding='utf-8'))
    return {'nombre': nombre, 'meta': meta, 'cuerpo': cuerpo.strip(), 'ruta': str(ruta)}


def listar_skills(raiz='skills'):
    base = Path(raiz)
    if not base.exists():
        return []
    return [cargar_skill(d.name, raiz) for d in sorted(base.iterdir())
            if d.is_dir() and (d / 'SKILL.md').exists()]


def instrucciones_de(rol, raiz_agentes='agentes', raiz_skills='skills'):
    """Instrucciones de un rol: su definicion de agente mas las skills que le tocan.

    El agente vive en agentes/<rol>.md y no lleva numeros: los umbrales que
    necesite se le inyectan desde config al construir la llamada.
    """
    ruta_agente = Path(raiz_agentes) / '{}.md'.format(rol.replace('_', '-'))
    if not ruta_agente.exists():
        raise FileNotFoundError('agente no encontrado: {}'.format(ruta_agente))

    meta, cuerpo = _frontmatter(ruta_agente.read_text(encoding='utf-8'))
    skills = [cargar_skill(s, raiz_skills) for s in SKILLS_POR_ROL.get(rol) or []]

    partes = [cuerpo.strip()]
    for skill in skills:
        partes.append('# Skill: {}\n\n{}'.format(skill['nombre'], skill['cuerpo']))

    return {
        'rol': rol,
        'meta': meta,
        'skills': [s['nombre'] for s in skills],
        'texto': '\n\n---\n\n'.join(partes),
    }
