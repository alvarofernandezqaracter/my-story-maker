# La interfaz del brief (§19) por donde decide: responder() enruta y valida sin
# socket de por medio, asi que los tests entran por ahi y no abren ningun
# puerto. Sin red, igual que el resto.
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from novela.canon import Canon
from novela.config import cargar_config
from novela.servidor import RAIZ_WEB, Motor, responder

BRIEF = {
    'epoca': 'Sevilla, 1587',
    'premisa': 'Un registro falsificado hunde a un cargador de Indias.',
    'tono': 'seco',
    'capitulos': 4,
    'palabras_por_capitulo': 600,
}


class EntornoDeInterfaz(unittest.TestCase):
    def setUp(self):
        self.raiz = Path(os.getcwd())
        self.config = cargar_config(str(self.raiz / 'config.json'))
        # Los tests no mandan trazas: correrian contra el Langfuse de quien los
        # lance y este repo se prueba sin red (§20).
        self.config = {**self.config, 'trazas': {**self.config['trazas'], 'activas': False}}
        self.dir = tempfile.mkdtemp(prefix='novela-ui-')
        self.canon = Canon(str(Path(self.dir) / 'canon.db'))
        self.motor = Motor(self.config, str(Path(self.dir) / 'canon.db'))

    def tearDown(self):
        self.canon.cerrar()
        shutil.rmtree(self.dir, ignore_errors=True)

    def pedir(self, metodo, camino, cuerpo=None):
        datos = json.dumps(cuerpo).encode('utf-8') if cuerpo is not None else b''
        codigo, tipo, salida = responder(
            metodo, camino, datos, self.canon, self.config, self.motor, RAIZ_WEB)
        return codigo, tipo, salida


class TestProyecto(EntornoDeInterfaz):
    def test_sin_brief_devuelve_el_canon_vacio(self):
        codigo, _, salida = self.pedir('GET', '/api/proyecto')
        cuerpo = json.loads(salida)
        self.assertEqual(codigo, 200)
        self.assertIsNone(cuerpo['estado'])
        self.assertIsNone(cuerpo['brief'])
        self.assertEqual(cuerpo['capitulos'], [])
        self.assertTrue(cuerpo['editable'])
        self.assertEqual(cuerpo['modo'], self.config['ejecucion']['modo'])

    def test_la_escaleta_viaja_con_estado_y_notas(self):
        self.canon.guardar_brief(BRIEF)
        self.canon.guardar_fichas([{
            'numero': 1, 'titulo': 'El registro', 'acto': 1, 'sinopsis': 's',
            'fecha': '1587-04-01', 'personajes': [], 'etiquetas': [],
            'objetivo': 'o', 'palabras_objetivo': 600,
        }])
        self.canon.guardar_intento(1, 1, 'capitulos/01-1.md', 600, estado='aprobado')
        self.canon.guardar_revisiones(1, 1, [
            {'dimension': 'continuidad', 'nota': 4, 'incidencias': [], 'notas_libres': ''},
            {'dimension': 'anacronismos', 'nota': 5, 'incidencias': [], 'notas_libres': ''},
            {'dimension': 'logica_ritmo', 'nota': 4, 'incidencias': [], 'notas_libres': ''},
        ])
        cuerpo = json.loads(self.pedir('GET', '/api/proyecto')[2])
        capitulo = cuerpo['capitulos'][0]
        self.assertEqual(capitulo['numero'], 1)
        self.assertEqual(capitulo['notas'], [4, 5, 4])
        self.assertEqual(capitulo['media'], 4.33)
        self.assertEqual(capitulo['intentos'], 1)


class TestBrief(EntornoDeInterfaz):
    def test_un_brief_completo_entra_en_el_canon(self):
        codigo, _, salida = self.pedir('POST', '/api/brief', BRIEF)
        self.assertEqual(codigo, 200)
        self.assertEqual(self.canon.estado(), 'borrador')
        self.assertEqual(self.canon.proyecto()['capitulos'], 4)
        self.assertEqual(json.loads(salida)['brief']['tono'], 'seco')

    def test_sin_un_campo_no_escribe_nada(self):
        incompleto = {k: v for k, v in BRIEF.items() if k != 'tono'}
        codigo, _, salida = self.pedir('POST', '/api/brief', incompleto)
        self.assertEqual(codigo, 400)
        self.assertIn('tono', json.loads(salida)['error'])
        self.assertIsNone(self.canon.proyecto())

    def test_los_capitulos_tienen_que_ser_un_entero_positivo(self):
        for valor in (0, -3, 2.5, '6', True):
            with self.subTest(valor=valor):
                codigo, _, _ = self.pedir(
                    'POST', '/api/brief', {**BRIEF, 'capitulos': valor})
                self.assertEqual(codigo, 400)
        self.assertIsNone(self.canon.proyecto())

    def test_el_texto_en_blanco_no_cuela(self):
        codigo, _, salida = self.pedir('POST', '/api/brief', {**BRIEF, 'epoca': '   '})
        self.assertEqual(codigo, 400)
        self.assertIn('epoca', json.loads(salida)['error'])

    def test_no_pisa_un_libro_en_marcha(self):
        self.canon.guardar_brief(BRIEF)
        self.canon.marcar_estado('escribiendo')
        codigo, _, salida = self.pedir(
            'POST', '/api/brief', {**BRIEF, 'epoca': 'Toledo, 1492'})
        self.assertEqual(codigo, 409)
        self.assertIn('novela brief', json.loads(salida)['error'])
        self.assertEqual(self.canon.proyecto()['epoca'], 'Sevilla, 1587')

    def test_el_cuerpo_que_no_es_json_se_rechaza(self):
        codigo, _, salida = responder(
            'POST', '/api/brief', b'no soy json', self.canon, self.config,
            self.motor, RAIZ_WEB)
        self.assertEqual(codigo, 400)
        self.assertIn('JSON', json.loads(salida)['error'])


class TestEstatico(EntornoDeInterfaz):
    def test_la_raiz_sirve_la_pagina(self):
        codigo, tipo, salida = self.pedir('GET', '/')
        self.assertEqual(codigo, 200)
        self.assertIn('text/html', tipo)
        self.assertIn(b'<title>Taller de novelas</title>', salida)

    def test_no_se_sale_de_web(self):
        for camino in ('/../config.json', '/../../etc/hosts', '/..%2fconfig.json'):
            with self.subTest(camino=camino):
                self.assertEqual(self.pedir('GET', camino)[0], 404)

    def test_una_ruta_de_api_desconocida_es_404(self):
        self.assertEqual(self.pedir('GET', '/api/agentes')[0], 404)

    def test_la_interfaz_no_acepta_otros_metodos(self):
        self.assertEqual(self.pedir('DELETE', '/estilo.css')[0], 405)


class TestFlujo(unittest.TestCase):
    """El motor de §19 contra la capa simulada, en su propio directorio: el
    flujo escribe capitulos/ en el cwd.
    """

    def setUp(self):
        self.cwd = os.getcwd()
        self.raiz_repo = Path(self.cwd)
        self.config = cargar_config(str(Path(self.cwd) / 'config.json'))
        # Los tests no mandan trazas: correrian contra el Langfuse de quien los
        # lance y este repo se prueba sin red (§20).
        self.config = {**self.config, 'trazas': {**self.config['trazas'], 'activas': False}}
        self.dir = tempfile.mkdtemp(prefix='novela-motor-')
        os.chdir(self.dir)
        self.ruta = str(Path(self.dir) / 'canon.db')
        self.canon = Canon(self.ruta)
        self.motor = Motor(self.config, self.ruta)

    def tearDown(self):
        self.canon.cerrar()
        os.chdir(self.cwd)
        shutil.rmtree(self.dir, ignore_errors=True)

    def correr(self, accion='todo'):
        self.motor.arrancar(accion)
        self.motor._hilo.join(timeout=120)
        self.assertFalse(self.motor.corriendo, 'el motor no termino')

    def pedir(self, metodo, camino, cuerpo=None):
        datos = json.dumps(cuerpo).encode('utf-8') if cuerpo is not None else b''
        return responder(metodo, camino, datos, self.canon, self.config,
                         self.motor, RAIZ_WEB)

    def test_una_novela_entera_desde_la_interfaz(self):
        self.canon.guardar_brief(BRIEF)
        self.correr('todo')
        self.assertIsNone(self.motor.error)
        self.assertEqual(self.canon.estado(), 'editado')
        self.assertTrue(all(f['estado'] == 'aprobado' for f in self.canon.fichas()))

    def test_el_diario_cuenta_quien_trabaja_y_por_donde_va(self):
        self.canon.guardar_brief(BRIEF)
        self.correr('preparar')
        tipos = {e['tipo'] for e in self.motor.diario}
        self.assertIn('agente', tipos)
        roles = [e['rol'] for e in self.motor.diario if e['tipo'] == 'agente']
        self.assertEqual(roles[:2], ['investigador', 'arquitecto'])

    def test_sin_brief_el_motor_para_y_lo_cuenta(self):
        self.correr('preparar')
        self.assertIn('no hay brief', self.motor.error)
        self.assertFalse(self.motor.corriendo)

    def test_una_accion_que_no_existe_se_rechaza(self):
        codigo, _, salida = self.pedir('POST', '/api/flujo', {'accion': 'inventada'})
        self.assertEqual(codigo, 400)
        self.assertIn('accion desconocida', json.loads(salida)['error'])

    def test_el_capitulo_no_se_lee_hasta_que_esta_aprobado(self):
        self.canon.guardar_brief(BRIEF)
        self.correr('preparar')
        self.assertEqual(self.pedir('GET', '/api/capitulo/1')[0], 409)
        self.correr('escribir')
        codigo, _, salida = self.pedir('GET', '/api/capitulo/1')
        self.assertEqual(codigo, 200)
        capitulo = json.loads(salida)
        self.assertTrue(capitulo['texto'].startswith('#'))
        self.assertEqual(len(capitulo['notas']), 3)
        self.assertEqual(self.pedir('GET', '/api/capitulo/99')[0], 404)

    def test_los_perfiles_son_los_config_de_la_raiz(self):
        # El test corre en un directorio temporal, asi que aqui no hay ninguno.
        self.assertEqual(json.loads(self.pedir('GET', '/api/proyecto')[2])['perfiles'], [])
        (Path(self.dir) / 'config.json').write_bytes(
            (self.raiz_repo / 'config.json').read_bytes())
        perfiles = json.loads(self.pedir('GET', '/api/proyecto')[2])['perfiles']
        self.assertEqual([p['nombre'] for p in perfiles], ['config'])
        self.assertEqual(perfiles[0]['modo'], 'simulado')

    def test_un_perfil_que_no_existe_se_rechaza(self):
        codigo, _, salida = self.pedir('POST', '/api/flujo',
                                       {'accion': 'preparar', 'perfil': 'inventado'})
        self.assertEqual(codigo, 400)
        self.assertIn('perfil', json.loads(salida)['error'])
        self.assertFalse(self.motor.corriendo)

    def test_sin_capitulo_en_curso_se_ensena_el_ultimo_trabajado(self):
        self.canon.guardar_brief(BRIEF)
        self.correr('todo')
        cuerpo = json.loads(self.pedir('GET', '/api/proyecto')[2])
        foco = cuerpo['en_curso']
        self.assertFalse(foco['activo'])
        self.assertEqual(foco['numero'], len(cuerpo['capitulos']))
        self.assertTrue(foco['intentos'])
        # La regla se recalcula con el gate de §8, no se guarda en el canon.
        self.assertTrue(foco['intentos'][0]['regla'].startswith('gate:'))
        self.assertIn('/', foco['intentos'][0]['ruta'])

    def test_pistas_deuda_y_archivos_salen_del_canon(self):
        self.canon.guardar_brief(BRIEF)
        self.correr('todo')
        cuerpo = json.loads(self.pedir('GET', '/api/proyecto')[2])
        self.assertTrue(cuerpo['dossier'])
        self.assertTrue(all(d['estado'] for d in cuerpo['dossier']))
        self.assertTrue(cuerpo['archivos'])
        self.assertTrue(all('cuando' in a for a in cuerpo['archivos']))
        # La deuda son los hilos que abrio un capitulo y no cerro ninguno.
        self.assertEqual(cuerpo['deuda'], self.canon.hilos_vivos())
        # La cuota diaria no tiene fuente en el harness y va vacia a proposito.
        self.assertIsNone(cuerpo['cuota'])

    def test_desbloquear_devuelve_el_capitulo_a_pendiente(self):
        self.canon.guardar_brief(BRIEF)
        self.correr('preparar')
        self.canon.marcar_ficha(1, 'bloqueado')
        codigo, _, _ = self.pedir('POST', '/api/desbloquear',
                                  {'capitulo': 1, 'modo': 'reintentar'})
        self.assertEqual(codigo, 200)
        self.assertEqual(self.canon.ficha(1)['estado'], 'pendiente')
        self.assertEqual(self.canon.estado(), 'escribiendo')


if __name__ == '__main__':
    unittest.main()
