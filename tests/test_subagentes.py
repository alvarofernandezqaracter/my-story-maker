# Los ocho subagentes de `.claude/agents/`, comprobados como ficheros (§21).
#
# Esto existe por un fallo real: los tres validadores llevaban dos puntos y un
# espacio dentro de una `description` sin comillas. En YAML eso vuelve ambiguo
# el valor, Claude Code descartaba el fichero **sin decir nada**, y la sesion
# arrancaba con cinco subagentes en vez de ocho. El orquestador los sustituyo
# por genericos, la novela salio entera y las doce llamadas al validador no
# aparecieron en ninguna traza, porque el hook solo reconoce los nombres de
# `ROLES`. El resultado era el peor posible: cifras mas bajas que las reales,
# con aspecto de buenas.
#
# Ningun test puede arrancar una sesion de Claude Code, asi que esto no prueba
# que el agente cargue. Prueba lo que se puede probar sin red: que el
# frontmatter no tiene la forma que lo rompe, y que el reparto de ficheros y el
# que conoce el hook son el mismo. Sin red y sin coste, como el resto.
import unittest
from pathlib import Path

from novela.trazas_hook import ROLES

AGENTES = Path(__file__).resolve().parent.parent / '.claude' / 'agents'

# Las claves del frontmatter que el sistema da por supuestas en cada subagente.
# El modelo vive aqui y no en `config.json` a proposito: las llamadas las hace
# Claude Code y solo lee el frontmatter.
CLAVES = ('name', 'description', 'tools', 'model')


def leer_frontmatter(ruta):
    """El frontmatter de un fichero de subagente, en bruto.

    Devuelve la lista de pares `(clave, valor)` tal y como estan escritos, sin
    interpretar el valor: lo que se quiere mirar aqui es precisamente como esta
    escrito. Lee bytes y normaliza el salto de linea para que el resultado no
    dependa de si el fichero se guardo en Windows o no.
    """
    crudo = ruta.read_bytes().replace(b'\r\n', b'\n').decode('utf-8')
    if not crudo.startswith('---\n'):
        return None
    fin = crudo.find('\n---', 3)
    if fin == -1:
        return None
    pares = []
    for linea in crudo[4:fin].split('\n'):
        if not linea.strip():
            continue
        if ':' not in linea:
            return None
        clave, valor = linea.split(':', 1)
        pares.append((clave.strip(), valor.strip()))
    return pares


def entrecomillado(valor):
    return len(valor) >= 2 and valor[0] == valor[-1] and valor[0] in ('"', "'")


class TestSubagentes(unittest.TestCase):

    def setUp(self):
        self.ficheros = sorted(AGENTES.glob('*.md'))

    def test_hay_uno_por_rol_del_hook(self):
        """El reparto en ficheros y el que traza el hook son el mismo.

        Si se anade un subagente y no entra en `ROLES`, sus llamadas no se
        trazan y nadie se entera; si se quita uno que sigue en `ROLES`, se
        espera una traza que no llega. Las dos cosas caen aqui.
        """
        en_disco = {f.stem for f in self.ficheros}
        self.assertEqual(en_disco, set(ROLES),
                         'los ficheros de .claude/agents y ROLES no coinciden')

    def test_el_frontmatter_se_puede_leer(self):
        for f in self.ficheros:
            with self.subTest(agente=f.name):
                self.assertIsNotNone(leer_frontmatter(f),
                                     'frontmatter ausente o sin cerrar')

    def test_estan_las_cuatro_claves(self):
        for f in self.ficheros:
            with self.subTest(agente=f.name):
                claves = [c for c, _ in leer_frontmatter(f)]
                for clave in CLAVES:
                    self.assertIn(clave, claves)

    def test_el_nombre_es_el_del_fichero(self):
        for f in self.ficheros:
            with self.subTest(agente=f.name):
                valores = dict(leer_frontmatter(f))
                self.assertEqual(valores['name'].strip('"\''), f.stem)

    def test_ningun_valor_suelto_lleva_dos_puntos(self):
        """La trampa que dejo la novela de Cadiz sin validador.

        Un valor sin comillas con `: ` dentro no es un escalar para YAML, y el
        fichero entero se descarta en silencio. Con comillas es legitimo, asi
        que lo que se exige no es que no haya dos puntos, sino que si los hay
        el valor vaya entrecomillado.
        """
        for f in self.ficheros:
            for clave, valor in leer_frontmatter(f):
                with self.subTest(agente=f.name, clave=clave):
                    if ': ' in valor and not entrecomillado(valor):
                        self.fail(
                            "'{}' lleva ': ' sin comillas; Claude Code "
                            'descartaria el subagente sin avisar'.format(clave))


if __name__ == '__main__':
    unittest.main()
