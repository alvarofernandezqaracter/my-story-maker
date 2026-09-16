# El canon (§3), el generador de contexto (§7) y el flujo entero (§4, §8, §11)
# contra la capa simulada: sin red y sin coste, por el mismo camino que la
# ejecucion de verdad.
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from novela.agentes import Agentes
from novela.canon import Canon, normalizar_fecha
from novela.config import cargar_config
from novela.contexto import generar_contexto, estimar_tokens
from novela.flujo import preparar, escribir_capitulo, cerrar, reanudar

BRIEF = {
    'epoca': 'Sevilla, 1587',
    'premisa': 'Un registro falsificado hunde a un cargador de Indias.',
    'tono': 'seco',
    'capitulos': 4,
    'palabras_por_capitulo': 600,
}


class EntornoDeNovela(unittest.TestCase):
    """Cada test corre en su propio directorio: el harness escribe en el cwd."""

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix='novela-')
        self.cwd = os.getcwd()
        self.config = cargar_config(str(Path(self.cwd) / 'config.json'))
        # Los tests no mandan trazas: correrian contra el Langfuse de quien los
        # lance y este repo se prueba sin red (§20).
        self.config = {**self.config, 'trazas': {**self.config['trazas'], 'activas': False}}
        os.chdir(self.dir)
        self.canon = Canon(str(Path(self.dir) / 'canon.db'))
        self.agentes = Agentes(self.config)
        self.canon.guardar_brief(BRIEF)

    def tearDown(self):
        os.chdir(self.cwd)
        for variable in ('NOVELA_SIM_FALLOS', 'NOVELA_SIM_CORTOS'):
            os.environ.pop(variable, None)
        # Windows no borra el fichero mientras SQLite lo tenga abierto.
        try:
            self.canon.cerrar()
        except Exception:
            pass
        shutil.rmtree(self.dir, ignore_errors=True)


# -------------------------------------------------------------------- §3

class TestCanon(EntornoDeNovela):

    def test_la_escritura_del_cronista_es_una_transaccion_unica(self):
        self.canon.guardar_personajes([{
            'id': 'ines', 'nombre': 'Ines', 'rol': 'protagonista', 'voz': 'v',
            'motivacion': 'm', 'arco': 'a', 'ubicacion': 'Triana', 'sabe': [],
        }])
        self.canon.guardar_fichas([{
            'numero': 1, 'titulo': 'T', 'acto': 1, 'sinopsis': 's', 'fecha': '1587-04',
            'personajes': ['ines'], 'etiquetas': [], 'objetivo': 'o',
            'palabras_objetivo': 600,
        }])

        with self.assertRaises(Exception):
            self.canon.escritura_del_cronista(1, {
                'resumen': 'r', 'hilos_abiertos': [], 'hilos_cerrados': [],
                'personajes_presentes': [],
                'cambios_personaje': [{'id': 'no-existe', 'ubicacion': 'x'}],
            })

        # Ni resumen ni cambio de ficha: o entra todo o no entra nada.
        self.assertEqual(len(self.canon.resumenes()), 0)
        self.assertEqual(self.canon.personaje('ines')['ubicacion'], 'Triana')
        self.assertEqual(self.canon.ficha(1)['estado'], 'pendiente')


class TestFecha(unittest.TestCase):

    def test_fecha_iso_parcial_a_clave_comparable(self):
        self.assertEqual(normalizar_fecha('1587'), '1587-01-01')
        self.assertEqual(normalizar_fecha('1587-04'), '1587-04-01')
        self.assertLess(normalizar_fecha('1587-04'), normalizar_fecha('1587-05-02'))


# -------------------------------------------------------------------- §7

class TestContexto(EntornoDeNovela):

    def test_mismo_capitulo_y_mismo_canon_dan_el_mismo_paquete(self):
        preparar(self.canon, self.agentes, self.config)
        a = generar_contexto(self.canon, 2, self.config)
        b = generar_contexto(self.canon, 2, self.config)
        self.assertEqual(a['texto'], b['texto'])

    def test_el_encargo_y_los_personajes_nunca_se_recortan(self):
        preparar(self.canon, self.agentes, self.config)
        escribir_capitulo(self.canon, self.agentes, self.config, 1)

        # Un tope absurdamente bajo fuerza todos los recortes posibles.
        apretado = {**self.config,
                    'contexto': {**self.config['contexto'], 'tope_contexto': 120}}
        p = generar_contexto(self.canon, 2, apretado)

        self.assertRegex(p['texto'], '# Encargo del capitulo 2')
        self.assertRegex(p['texto'], '# Personajes en escena')
        self.assertEqual(len(p['bloques']['memoria_larga']), 0)
        self.assertEqual(len(p['bloques']['epoca']), 0)
        # Ni aun asi cabe: el capitulo se marcaria bloqueado en lugar de mutilarse.
        self.assertFalse(p['cabe'])

    def test_el_texto_entero_del_capitulo_anterior_no_entra_solo_el_enganche(self):
        preparar(self.canon, self.agentes, self.config)
        escribir_capitulo(self.canon, self.agentes, self.config, 1)

        p = generar_contexto(self.canon, 2, self.config)
        texto_cap1 = Path(self.canon.intento_aprobado(1)['ruta']).read_text(encoding='utf-8')
        self.assertNotIn(texto_cap1, p['texto'])
        self.assertRegex(p['texto'], '# Enganche con el capitulo anterior')

        palabras_enganche = len(p['bloques']['enganche'].split())
        self.assertLessEqual(palabras_enganche, self.config['contexto']['palabras_enganche'])

    def test_la_epoca_se_filtra_por_etiquetas_y_pone_verificado_primero(self):
        preparar(self.canon, self.agentes, self.config)
        self.canon.guardar_datos([
            {'id': 'z-verificado', 'categoria': 'comida', 'dato': 'd',
             'fuente': 'https://ejemplo', 'estado': 'verificado',
             'etiquetas': ['vestimenta']},
            {'id': 'sin-etiqueta', 'categoria': 'comida', 'dato': 'd', 'fuente': 'modelo',
             'estado': 'sin_verificar', 'etiquetas': ['nada-que-ver']},
        ])
        self.canon.guardar_fichas([{**self.canon.ficha(1), 'etiquetas': ['vestimenta']}])

        p = generar_contexto(self.canon, 1, self.config)
        self.assertEqual(p['bloques']['epoca'][0]['id'], 'z-verificado')
        self.assertFalse(any(d['id'] == 'sin-etiqueta' for d in p['bloques']['epoca']))


class TestEstimacion(unittest.TestCase):

    def test_estimar_tokens_crece_con_el_texto(self):
        self.assertGreater(estimar_tokens('a' * 400), estimar_tokens('a' * 40))


# ------------------------------------------------------------- §4, §8, §11

class TestFlujo(EntornoDeNovela):

    def test_la_preparacion_deja_dossier_y_escaleta_coherentes_entre_si(self):
        resultado = preparar(self.canon, self.agentes, self.config)

        self.assertEqual(resultado['estado'], 'estructurado')
        self.assertGreater(len(self.canon.datos()), 0)
        self.assertEqual(len(self.canon.fichas()), BRIEF['capitulos'])

        # Cada ficha apunta a personajes que existen, y trae fecha y etiquetas.
        ids = {p['id'] for p in self.canon.personajes()}
        for f in self.canon.fichas():
            self.assertTrue(f['fecha'], 'el capitulo {} no trae fecha'.format(f['numero']))
            self.assertTrue(f['etiquetas'],
                            'el capitulo {} no trae etiquetas'.format(f['numero']))
            for id_personaje in f['personajes']:
                self.assertIn(id_personaje, ids)

    def test_un_capitulo_aprobado_actualiza_el_canon_una_sola_vez(self):
        preparar(self.canon, self.agentes, self.config)
        r = escribir_capitulo(self.canon, self.agentes, self.config, 1)

        self.assertTrue(r['aprobado'])
        self.assertEqual(self.canon.ficha(1)['estado'], 'aprobado')
        self.assertEqual(len(self.canon.resumenes()), 1)
        primero = self.canon.ficha(1)['personajes'][0]
        self.assertEqual(self.canon.personaje(primero)['actualizado_en'], 1)
        self.assertTrue(Path(self.canon.intento_aprobado(1)['ruta']).exists())

    def test_un_capitulo_malo_se_rechaza_y_el_reintento_lo_arregla(self):
        preparar(self.canon, self.agentes, self.config)

        os.environ['NOVELA_SIM_FALLOS'] = '1:1'

        diario = []
        r = escribir_capitulo(self.canon, self.agentes, self.config, 1, diario)

        self.assertTrue(r['aprobado'])
        self.assertEqual(r['intento'], 2)
        puertas = [e for e in diario if e['tipo'] == 'gate']
        self.assertFalse(puertas[0]['aprueba'])
        self.assertTrue(puertas[1]['aprueba'])
        # El intento malo queda como rastro, descartado.
        primero = next(i for i in self.canon.intentos(1) if i['intento'] == 1)
        self.assertEqual(primero['estado'], 'descartado')

    def test_vd08_descarta_el_intento_sin_llamar_al_validador(self):
        preparar(self.canon, self.agentes, self.config)

        os.environ['NOVELA_SIM_CORTOS'] = '1:1'

        diario = []
        escribir_capitulo(self.canon, self.agentes, self.config, 1, diario)

        self.assertTrue(any(e['tipo'] == 'vd08' and e['intento'] == 1 for e in diario))
        # El primer intento no llego al gate: la unica entrada de gate es la del segundo.
        puertas = [e for e in diario if e['tipo'] == 'gate']
        self.assertEqual(len(puertas), 1)
        self.assertEqual(puertas[0]['intento'], 2)
        # Y el intento descartado no tiene revisiones guardadas.
        primero = next(i for i in self.canon.intentos(1) if i['intento'] == 1)
        self.assertIsNone(primero['revisiones'])

    def test_al_agotar_intentos_se_bloquea_el_capitulo_y_el_proyecto(self):
        preparar(self.canon, self.agentes, self.config)

        os.environ['NOVELA_SIM_FALLOS'] = '1:1,1:2,1:3'

        r = escribir_capitulo(self.canon, self.agentes, self.config, 1)

        self.assertFalse(r['aprobado'])
        self.assertEqual(self.canon.ficha(1)['estado'], 'bloqueado')
        self.assertEqual(self.canon.estado(), 'bloqueado')
        # Se conserva un intento en propuesto y el resto descartados.
        intentos = self.canon.intentos(1)
        self.assertEqual(len([i for i in intentos if i['estado'] == 'propuesto']), 1)
        self.assertEqual(len([i for i in intentos if i['estado'] == 'descartado']), 2)
        # Y el canon no crecio: sin resumen, no hay agujero que propagar.
        self.assertEqual(len(self.canon.resumenes()), 0)

    def test_reanudar_no_desbloquea(self):
        preparar(self.canon, self.agentes, self.config)

        os.environ['NOVELA_SIM_FALLOS'] = '1:1,1:2,1:3'
        escribir_capitulo(self.canon, self.agentes, self.config, 1)
        del os.environ['NOVELA_SIM_FALLOS']

        r = reanudar(self.canon, self.agentes, self.config)
        self.assertEqual(r['estado'], 'bloqueado')
        self.assertEqual(self.canon.ficha(2)['estado'], 'pendiente')

    def test_reanudar_localiza_el_primer_capitulo_no_aprobado_y_termina_el_libro(self):
        preparar(self.canon, self.agentes, self.config)
        escribir_capitulo(self.canon, self.agentes, self.config, 1)

        r = reanudar(self.canon, self.agentes, self.config)

        self.assertEqual(r['estado'], 'editado')
        self.assertTrue(all(f['estado'] == 'aprobado' for f in self.canon.fichas()))
        self.assertEqual(len(self.canon.resumenes()), BRIEF['capitulos'])
        self.assertTrue(Path('retoques.md').exists())

    def test_el_editor_global_deja_retoques_accionables_fuera_del_canon(self):
        preparar(self.canon, self.agentes, self.config)
        for f in self.canon.fichas():
            escribir_capitulo(self.canon, self.agentes, self.config, f['numero'])
        self.canon.marcar_estado('escrito')

        resultado = cerrar(self.canon, self.agentes)

        self.assertGreater(len(resultado['retoques']), 0)
        self.assertEqual(self.canon.estado(), 'editado')
        self.assertRegex(Path(resultado['ruta']).read_text(encoding='utf-8'),
                         '# Retoques finales')
        # retoques.md vive junto al canon, no dentro.
        self.assertIsNone(self.canon.db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='retoque'",
        ).fetchone())

    def test_el_modo_separado_del_validador_compone_las_tres_dimensiones(self):
        separado = {**self.config, 'validador': {'modo': 'separado'}}
        agentes = Agentes(separado)

        preparar(self.canon, agentes, separado)
        r = escribir_capitulo(self.canon, agentes, separado, 1)

        self.assertTrue(r['aprobado'])
        self.assertEqual([x['dimension'] for x in r['revisiones']],
                         ['continuidad', 'anacronismos', 'logica_ritmo'])


if __name__ == '__main__':
    unittest.main()
