# El archivo de novelas de §21.
#
# Sin red, en su propio directorio temporal. Lo que se prueba es lo que duele si
# falla: que la copia se lleve el canon entero y no solo los JSON, que no
# sobrescriba una novela ya archivada, y que no toque el original -porque la
# unica razon de que esto exista es no perder la novela de antes-.
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from novela.archivo import archivar, ErrorArchivo, listar, nombre_para, plan
from novela.canon_cc import CanonCC

BRIEF = {
    'epoca': 'Sevilla, 1587, barrio de Triana',
    'premisa': 'Un registro falsificado hunde a un cargador de Indias.',
    'tono': 'seco',
    'capitulos': 1,
    'palabras_por_capitulo': 600,
}

ESCALETA = {'capitulos': [
    {'numero': 1, 'titulo': 'El carcelaje', 'acto': 1, 'sinopsis': 'Ines paga.',
     'objetivo': 'Se cierra la apelacion.', 'palabras_objetivo': 600},
]}

ESTADO = {
    'estado': 'editado',
    'capitulos': {
        '1': {'estado': 'aprobado', 'intento_aprobado': 1,
              'intentos': [{'intento': 1, 'estado': 'aprobado',
                            'ruta': 'novela-cc/capitulos/cap-01-intento-1.md',
                            'palabras': 612, 'parrafos': 22, 'vd08': 'ok',
                            'notas': {'continuidad': 4, 'anacronismos': 5,
                                      'logica_ritmo': 4},
                            'aprueba': True}]},
    },
}


def _escribir(ruta, valor):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(valor if isinstance(valor, str)
                    else json.dumps(valor, ensure_ascii=False, indent=2),
                    encoding='utf-8')


class ArchivoDePrueba(unittest.TestCase):
    def setUp(self):
        self.cwd = os.getcwd()
        self.dir = tempfile.mkdtemp(prefix='archivo-')
        os.chdir(self.dir)
        raiz = Path('novela-cc')
        _escribir(raiz / 'canon' / 'brief.json', BRIEF)
        _escribir(raiz / 'canon' / 'estado.json', ESTADO)
        _escribir(raiz / 'canon' / 'escaleta.json', ESCALETA)
        _escribir(raiz / 'capitulos' / 'cap-01-intento-1.md', '# El carcelaje\n\nTexto.')
        _escribir(raiz / 'contexto' / 'cap-01.md', '# Encargo\n\nObjetivo.')
        _escribir(raiz / 'retoques.md', '### RET-01\n\nUn retoque.')

    def tearDown(self):
        os.chdir(self.cwd)
        shutil.rmtree(self.dir, ignore_errors=True)


class TestNombre(ArchivoDePrueba):
    def test_el_nombre_sale_de_la_fecha_y_la_epoca(self):
        # Un contador no dice nada seis meses despues; la epoca si.
        self.assertEqual(nombre_para(CanonCC(), hoy='2026-09-18'),
                         '2026-09-18-sevilla-1587')

    def test_una_epoca_con_acentos_y_signos_cabe_en_un_nombre_de_carpeta(self):
        _escribir(Path('novela-cc/canon/brief.json'),
                  {**BRIEF, 'epoca': 'Cádiz, 1812: las Cortes'})
        self.assertEqual(nombre_para(CanonCC(), hoy='2026-09-18'),
                         '2026-09-18-cadiz-1812')

    def test_sin_epoca_sigue_habiendo_nombre(self):
        _escribir(Path('novela-cc/canon/brief.json'), {**BRIEF, 'epoca': ''})
        self.assertEqual(nombre_para(CanonCC(), hoy='2026-09-18'), '2026-09-18-novela')


class TestArchivar(ArchivoDePrueba):
    def test_se_copia_el_canon_entero_y_no_solo_los_json(self):
        # El capitulo, el paquete y los retoques son la novela tanto como el
        # canon: archivar solo los JSON seria archivar el indice de un libro.
        datos = archivar(hoy='2026-09-18')
        destino = Path(datos['destino'])
        for relativa in ('canon/brief.json', 'canon/estado.json',
                         'capitulos/cap-01-intento-1.md', 'contexto/cap-01.md',
                         'retoques.md'):
            self.assertTrue((destino / relativa).is_file(), relativa)

    def test_el_original_no_se_toca(self):
        # Es toda la razon de ser de esto: copiar, nunca mover.
        archivar(hoy='2026-09-18')
        self.assertTrue(Path('novela-cc/canon/brief.json').is_file())
        self.assertTrue(Path('novela-cc/capitulos/cap-01-intento-1.md').is_file())

    def test_el_resumen_cuenta_los_capitulos_aprobados(self):
        datos = archivar(hoy='2026-09-18')
        self.assertEqual((datos['aprobados'], datos['capitulos']), (1, 1))
        self.assertEqual(datos['palabras'], 612)
        self.assertEqual(datos['estado'], 'editado')

    def test_no_sobrescribe_una_novela_ya_archivada(self):
        archivar(hoy='2026-09-18')
        with self.assertRaises(ErrorArchivo) as e:
            archivar(hoy='2026-09-18')
        self.assertIn('ya existe', str(e.exception))

    def test_con_otro_nombre_si_entra(self):
        archivar(hoy='2026-09-18')
        datos = archivar(nombre='segunda-pasada')
        self.assertEqual(datos['destino'], 'novelas/segunda-pasada')

    def test_sin_canon_no_hay_nada_que_archivar(self):
        shutil.rmtree('novela-cc')
        with self.assertRaises(ErrorArchivo) as e:
            archivar()
        self.assertIn('no hay canon', str(e.exception))


class TestListado(ArchivoDePrueba):
    def test_sin_carpeta_el_listado_esta_vacio(self):
        self.assertEqual(listar(), [])

    def test_las_archivadas_salen_de_la_mas_nueva_a_la_mas_vieja(self):
        archivar(hoy='2026-09-17')
        archivar(hoy='2026-09-18')
        self.assertEqual([n['nombre'] for n in listar()],
                         ['2026-09-18-sevilla-1587', '2026-09-17-sevilla-1587'])

    def test_cada_archivada_se_lee_como_un_canon_mas(self):
        archivar(hoy='2026-09-18')
        novela = listar()[0]
        self.assertEqual(novela['aprobados'], 1)
        self.assertEqual(novela['epoca'], BRIEF['epoca'])


class TestPlan(ArchivoDePrueba):
    def test_el_plan_dice_el_nombre_sin_copiar_nada(self):
        datos = plan(hoy='2026-09-18')
        self.assertTrue(datos['puede'])
        self.assertEqual(datos['nombre'], '2026-09-18-sevilla-1587')
        self.assertFalse(Path('novelas').exists())

    def test_el_plan_avisa_de_que_el_destino_ya_esta_ocupado(self):
        archivar(hoy='2026-09-18')
        datos = plan(hoy='2026-09-18')
        self.assertFalse(datos['puede'])
        self.assertIn('ya existe', datos['motivo'])


if __name__ == '__main__':
    unittest.main()
