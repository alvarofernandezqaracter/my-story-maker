# Las trazas en vivo del camino delegado (§20, §21, §22): el hook sobre el tool
# `Agent`, el lector del transcript y el agregado del informe.
#
# Sin red y sin coste, como el resto. El hook se prueba con las trazas apagadas:
# lo que se comprueba es que situa bien la llamada, que descarta lo que no es
# suyo y que deja su linea en el diario local pase lo que pase, que es
# justamente lo que tiene que seguir funcionando cuando Langfuse no contesta.
import json
import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from novela.informe import agregar, texto
from novela.trazas import id_de_traza
from novela.trazas_cc import traza_de
from novela.trazas_hook import procesar, situar

BRIEF = {
    'epoca': 'Sevilla, 1587',
    'premisa': 'Un registro falsificado hunde a un cargador de Indias.',
    'tono': 'seco',
    'capitulos': 2,
    'palabras_por_capitulo': 600,
}

USO = {'input_tokens': 4, 'output_tokens': 120,
       'cache_read_input_tokens': 30000, 'cache_creation_input_tokens': 500}


def respuesta(**extra):
    base = {'status': 'completed', 'resolvedModel': 'claude-sonnet-5',
            'totalDurationMs': 90000, 'totalTokens': 30624, 'totalToolUseCount': 3,
            'usage': dict(USO), 'content': 'listo'}
    base.update(extra)
    return base


def payload(subagente, prompt, **extra):
    base = {'hook_event_name': 'PostToolUse', 'tool_name': 'Agent',
            'session_id': 'sesion-cc',
            'tool_input': {'subagent_type': subagente, 'prompt': prompt},
            'tool_response': respuesta()}
    base.update(extra)
    return base


class SituarLaLlamada(unittest.TestCase):
    """De que capitulo y de que intento es cada llamada (§21)."""

    def test_el_capitulo_sale_de_la_ruta_del_paquete(self):
        sitio = situar('escritor', 'Lee novela-cc/contexto/cap-04.md y escribe.')
        self.assertEqual(sitio['capitulo'], 4)
        self.assertEqual(sitio['tramo'], 'cap-04')

    def test_el_intento_sale_de_la_ruta_del_borrador(self):
        sitio = situar('escritor', 'Arregla novela-cc/capitulos/cap-06-intento-2.md')
        self.assertEqual((sitio['capitulo'], sitio['intento']), (6, 2))

    def test_los_dos_roles_de_preparacion_no_tienen_capitulo(self):
        for rol in ('investigador', 'arquitecto'):
            sitio = situar(rol, 'el brief dice cap-03 por algun lado')
            self.assertEqual(sitio['tramo'], 'preparar')
            self.assertIsNone(sitio['capitulo'])

    def test_el_editor_global_cierra(self):
        self.assertEqual(situar('editor_global', 'lee los resumenes')['tramo'], 'cerrar')

    def test_sin_capitulo_se_traza_igual_y_se_marca(self):
        sitio = situar('escritor', 'escribe algo')
        self.assertEqual(sitio['tramo'], 'sin-capitulo')
        self.assertEqual(sitio['traza'], 'escribir-capitulo')


class LoQueElHookNoTraza(unittest.TestCase):
    """Un hook puede estar puesto sobre un matcher mas ancho que el nuestro."""

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.perfil = os.path.join(self.dir, 'config.json')
        Path(self.perfil).write_text(json.dumps({'trazas': {'activas': False}}),
                                     encoding='utf-8')

    def _procesar(self, datos):
        return procesar(datos, raiz=os.path.join(self.dir, 'novela-cc'),
                        ruta_config=self.perfil)

    def test_otro_tool_no_se_traza(self):
        r = self._procesar({'tool_name': 'Bash', 'tool_input': {}})
        self.assertFalse(r['trazado'])
        self.assertIn('Agent', r['motivo'])

    def test_un_subagente_ajeno_a_la_novela_no_se_traza(self):
        r = self._procesar(payload('Explore', 'busca cosas'))
        self.assertFalse(r['trazado'])
        self.assertIn('ajeno', r['motivo'])

    def test_una_llamada_hecha_desde_dentro_de_un_subagente_no_se_traza(self):
        r = self._procesar(payload('novela-escritor', 'cap-01', agent_id='xyz'))
        self.assertFalse(r['trazado'])
        self.assertIn('subagente', r['motivo'])


class ElDiarioLocal(unittest.TestCase):
    """Con las trazas apagadas no se manda nada, pero se anota igual (§20)."""

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.raiz = os.path.join(self.dir, 'novela-cc')
        os.makedirs(os.path.join(self.raiz, 'canon'))
        Path(self.raiz, 'canon', 'brief.json').write_text(
            json.dumps(BRIEF), encoding='utf-8')
        self.perfil = os.path.join(self.dir, 'config.json')
        Path(self.perfil).write_text(json.dumps({'trazas': {'activas': False}}),
                                     encoding='utf-8')

    def _linea(self, datos):
        procesar(datos, raiz=self.raiz, ruta_config=self.perfil)
        crudo = Path(self.raiz, 'trazas', 'llamadas.jsonl').read_text(encoding='utf-8')
        return [json.loads(l) for l in crudo.strip().splitlines()]

    def test_se_anota_aunque_las_trazas_esten_apagadas(self):
        lineas = self._linea(payload('novela-validador-continuidad',
                                     'revisa cap-02-intento-1'))
        self.assertEqual(len(lineas), 1)
        self.assertEqual(lineas[0]['rol'], 'validador')
        self.assertEqual(lineas[0]['dimension'], 'continuidad')
        self.assertEqual((lineas[0]['capitulo'], lineas[0]['intento']), (2, 1))

    def test_el_reparto_de_tokens_no_se_solapa(self):
        linea = self._linea(payload('novela-escritor', 'cap-01'))[0]
        self.assertEqual(linea['reparto'], {
            'input': 4, 'output': 120,
            'cache_read_input_tokens': 30000, 'cache_creation_input_tokens': 500})

    def test_la_sesion_sale_del_brief_y_no_de_la_sesion_de_claude_code(self):
        linea = self._linea(payload('novela-escritor', 'cap-01'))[0]
        self.assertTrue(linea['sesion'].startswith('novela-'))
        self.assertEqual(linea['sesion_cc'], 'sesion-cc')

    def test_con_las_trazas_apagadas_no_se_manda_nada(self):
        r = procesar(payload('novela-cronista', 'resume cap-03'),
                     raiz=self.raiz, ruta_config=self.perfil)
        self.assertFalse(r['trazado'])
        self.assertTrue(r['diario'])


class LaTrazaCompartida(unittest.TestCase):
    """El hook y la reconstruccion tienen que caer en la misma traza (§21)."""

    def test_el_id_se_siembra_igual_en_los_dos_sitios(self):
        self.assertEqual(traza_de('novela-abc', 'cap-04'),
                         id_de_traza('novela-abc|cap-04'))

    def test_dos_tramos_distintos_no_comparten_traza(self):
        self.assertNotEqual(traza_de('novela-abc', 'cap-04'),
                            traza_de('novela-abc', 'cap-05'))


def observacion(nombre, tipo, origen, capitulo=None, uso=None, coste=0.0, modelo=None):
    return {'id': nombre + str(capitulo), 'nombre': nombre, 'tipo': tipo,
            'modelo': modelo, 'uso': uso or {}, 'coste': coste, 'latencia': 0,
            'traza': 'tz', 'metadata': {'origen': origen, 'capitulo': capitulo,
                                        'tokens_totales': sum((uso or {}).values()),
                                        'duracion_ms': 1000}}


class AgregarElInforme(unittest.TestCase):
    """Lo que cuenta y lo que no (§22)."""

    def setUp(self):
        self.uso = {'input': 10, 'output': 20, 'cache_read_input_tokens': 900}
        self.observaciones = [
            observacion('redactar-capitulo', 'generation', 'hook', 1, self.uso, 0.5,
                        'claude-opus-5'),
            observacion('escritor', 'agent', 'hook', 1, self.uso, 0.5, 'claude-opus-5'),
            observacion('escritor', 'agent', 'novela-cc', 1),
            observacion('gate', 'evaluator', 'novela-cc', 1),
        ]

    def test_solo_cuenta_la_generacion_observada_en_vivo(self):
        informe = agregar(self.observaciones)
        self.assertEqual(informe['observaciones'], 4)
        self.assertEqual(informe['llamadas'], 1)
        self.assertEqual(informe['total']['tokens'], 930)

    def test_el_reparto_de_cache_se_calcula_sobre_la_entrada(self):
        informe = agregar(self.observaciones)
        self.assertEqual(informe['cache']['leida'], 900)
        self.assertEqual(informe['cache']['porcentaje_leido'], 98.9)

    def test_un_modelo_sin_precio_se_avisa_en_el_texto(self):
        sin_precio = [observacion('redactar-capitulo', 'generation', 'hook', 2,
                                  self.uso, 0.0, 'claude-opus-5[1m]')]
        salida = texto(agregar(sin_precio), 'novela-abc')
        self.assertIn('Sin precio en Langfuse', salida)
        self.assertIn('claude-opus-5[1m]', salida)

    def test_sin_nada_observado_en_vivo_el_informe_no_inventa_gasto(self):
        informe = agregar([o for o in self.observaciones
                           if o['metadata']['origen'] != 'hook'])
        self.assertEqual(informe['llamadas'], 0)
        self.assertEqual(informe['total']['coste'], 0)


if __name__ == '__main__':
    unittest.main()
