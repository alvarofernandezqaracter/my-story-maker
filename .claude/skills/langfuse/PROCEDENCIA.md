# Procedencia de esta skill

No es código de este repo. Es la skill oficial de Langfuse, copiada tal cual de
[github.com/langfuse/skills](https://github.com/langfuse/skills) (MIT, © Langfuse
GmbH), en el commit `ab83111ed644c583a9ce963de773dbfbf09aebf3` del 2026-09-15.

Va versionada para que quien clone el repo tenga la misma guía con la que se
escribió §20 del spec, sin depender de que la descargue. **No se edita a mano**:
para actualizarla se vuelve a copiar de su repositorio y se anota aquí el commit
nuevo.

```bash
git clone --depth 1 https://github.com/langfuse/skills.git /tmp/langfuse-skills
cp -r /tmp/langfuse-skills/skills/langfuse .claude/skills/langfuse
```
