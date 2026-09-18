# La biblioteca de §21: todas las novelas, una carpeta cada una.
#
# Sin red, en su propio directorio temporal. Lo que se prueba es lo que el diseno
# promete: que una novela nueva nunca escribe donde ya hay otra, que la de ahora
# se averigua sola sin puntero que se quede desfasado, y que crear una novela no
# escribe canon, que es de quien escribe y de nadie mas.
import json
import os
import shutil
import tempfile
import time
import unittest
from pathlib import Path

from novela.biblioteca import (actual, crear, ErrorBiblioteca, listar, nombre_para,
                               RAIZ)

BRIEF = {
    'epoca': 'Sevilla, 1587, barrio de Triana',
    'premisa': 'Un registro falsificado hunde a un cargador de Indias.',
    'tono': 'seco',
    'capitulos': 3,
    'palabras_por_capitulo': 900,
}


class BibliotecaDePrueba(unittest.TestCase):
    def setUp(self):
        self.cwd = os.getcwd()
        self.dir = tempfile.mkdtemp(prefix='biblioteca-')
        os.chdir(self.dir)

    def tearDown(self):
        os.chdir(self.cwd)
        shutil.rmtree(self.dir, ignore_errors=True)

    def con_estado(self, ruta, estado='escribiendo'):
        fichero = Path(ruta) / 'canon' / 'estado.json'
        fichero.parent.mkdir(parents=True, exist_ok=True)
        fichero.write_text(json.dumps({'estado': estado}), encoding='utf-8')
        return fichero


class TestNombre(BibliotecaDePrueba):
    def test_el_nombre_sale_de_la_fecha_y_la_epoca(self):
        # Un contador no dice nada seis meses despues; la epoca si.
        self.assertEqual(nombre_para(BRIEF, hoy='2026-09-18'),
                         '2026-09-18-sevilla-1587')

    def test_una_epoca_con_acentos_y_signos_cabe_en_un_nombre_de_carpeta(self):
        self.assertEqual(nombre_para({'epoca': 'Cádiz, 1812: las Cortes'}, hoy='2026-09-18'),
                         '2026-09-18-cadiz-1812')

    def test_sin_epoca_sigue_habiendo_nombre(self):
        self.assertEqual(nombre_para({'epoca': ''}, hoy='2026-09-18'), '2026-09-18-novela')
        self.assertEqual(nombre_para({}, hoy='2026-09-18'), '2026-09-18-novela')


class TestCrear(BibliotecaDePrueba):
    def test_la_novela_nace_en_su_propia_carpeta(self):
        novela = crear(BRIEF, hoy='2026-09-18')
        self.assertEqual(novela['ruta'], 'biblioteca/2026-09-18-sevilla-1587')
        self.assertTrue(Path(novela['ruta']).is_dir())

    def test_crear_no_escribe_canon(self):
        # En el canon escribe el orquestador y nadie mas: un directorio vacio no
        # es canon, y esta es la linea que no se cruza.
        novela = crear(BRIEF, hoy='2026-09-18')
        self.assertEqual(list(Path(novela['ruta']).iterdir()), [])

    def test_dos_novelas_iguales_el_mismo_dia_no_se_pisan(self):
        # Es el fallo entero que esto viene a arreglar: escribir encima de la
        # novela anterior. Antes que fallar o que sobrescribir, se numera.
        primera = crear(BRIEF, hoy='2026-09-18')
        segunda = crear(BRIEF, hoy='2026-09-18')
        self.assertNotEqual(primera['nombre'], segunda['nombre'])
        self.assertEqual(segunda['nombre'], '2026-09-18-sevilla-1587-2')
        self.assertTrue(Path(primera['ruta']).is_dir())

    def test_una_carpeta_con_novela_dentro_nunca_se_reutiliza(self):
        primera = crear(BRIEF, hoy='2026-09-18')
        self.con_estado(primera['ruta'])
        segunda = crear(BRIEF, hoy='2026-09-18')
        self.assertTrue((Path(primera['ruta']) / 'canon' / 'estado.json').is_file())
        self.assertEqual(list(Path(segunda['ruta']).iterdir()), [])


class TestActual(BibliotecaDePrueba):
    def test_sin_biblioteca_no_hay_novela_en_curso(self):
        self.assertIsNone(actual())

    def test_la_novela_en_curso_es_la_que_se_toco_ultima(self):
        # Se deduce de la fecha del estado y no de un puntero guardado: un
        # puntero es un segundo sitio donde vive el estado y se queda desfasado.
        vieja = crear(BRIEF, hoy='2026-09-10')
        nueva = crear({**BRIEF, 'epoca': 'Cadiz, 1812'}, hoy='2026-09-18')
        self.con_estado(vieja['ruta'])
        time.sleep(0.01)
        self.con_estado(nueva['ruta'])
        self.assertEqual(actual(), nueva['ruta'])

        # Y si se retoma la vieja, vuelve a ser la de ahora.
        time.sleep(0.01)
        self.con_estado(vieja['ruta'])
        self.assertEqual(actual(), vieja['ruta'])

    def test_se_puede_elegir_a_dedo(self):
        crear(BRIEF, hoy='2026-09-18')
        vieja = crear({**BRIEF, 'epoca': 'Cadiz, 1812'}, hoy='2026-09-10')
        self.assertEqual(actual(nombre=Path(vieja['ruta']).name), vieja['ruta'])

    def test_un_nombre_que_no_existe_se_dice_y_no_se_inventa(self):
        crear(BRIEF, hoy='2026-09-18')
        with self.assertRaises(ErrorBiblioteca) as e:
            actual(nombre='la-que-no-esta')
        self.assertIn('la-que-no-esta', str(e.exception))


class TestListado(BibliotecaDePrueba):
    def test_sin_carpeta_el_listado_esta_vacio(self):
        self.assertEqual(listar(), [])

    def test_una_novela_apartada_y_sin_brief_se_distingue(self):
        # La carpeta existe desde antes de que el orquestador escriba nada, y
        # eso tiene que verse en vez de parecer una novela vacia y rota.
        crear(BRIEF, hoy='2026-09-18')
        novela = listar()[0]
        self.assertFalse(novela['empezada'])

    def test_con_brief_ya_cuenta_como_empezada(self):
        novela = crear(BRIEF, hoy='2026-09-18')
        brief = Path(novela['ruta']) / 'canon' / 'brief.json'
        brief.parent.mkdir(parents=True, exist_ok=True)
        brief.write_text(json.dumps(BRIEF), encoding='utf-8')
        self.assertTrue(listar()[0]['empezada'])

    def test_el_listado_va_de_la_mas_reciente_a_la_mas_antigua(self):
        vieja = crear(BRIEF, hoy='2026-09-10')
        nueva = crear({**BRIEF, 'epoca': 'Cadiz, 1812'}, hoy='2026-09-18')
        self.con_estado(vieja['ruta'])
        time.sleep(0.01)
        self.con_estado(nueva['ruta'])
        self.assertEqual([n['nombre'] for n in listar()],
                         [Path(nueva['ruta']).name, Path(vieja['ruta']).name])

    def test_la_raiz_por_defecto_es_biblioteca(self):
        self.assertEqual(RAIZ, 'biblioteca')


if __name__ == '__main__':
    unittest.main()
