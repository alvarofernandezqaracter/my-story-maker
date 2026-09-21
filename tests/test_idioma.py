# VD-14 (§9): el capitulo esta en el idioma de la novela.
#
# La comprobacion nacio de una pasada real: un capitulo entero en ingles paso el
# gate con 4/4/4 porque ninguna de las tres rubricas mira el idioma. Estos tests
# fijan lo que tiene que cazar y, sobre todo, lo que no debe tocar.
import tempfile
import unittest
from pathlib import Path

from novela.__main__ import main
from novela.config import cargar_config
from novela.idioma import revisar

CASTELLANO = (
    'El barro pegaba entre los dedos. Amara lo golpeaba contra la tabla para '
    'sacudir el aire atrapado, y el sonido seco llenaba el taller. Laia '
    'observaba desde el rincon donde guardaban las vasijas terminadas, sentada '
    'con un punado de arcilla que amasaba sin forma alguna, mientras su madre '
    'contaba las piezas que el consejo habia pedido para esa misma manana.'
)

INGLES = (
    'The night had come. In the workshop, Amara was wrapping what little food '
    'remained, a paste of ground acorns and barley that barely held together in '
    'her hands. Laia sat against the wall, watching her mother move. The child '
    'was wrapped in dark cloth, and her feet were bare on the cold floor of the '
    'room where they had always worked together.'
)


class TestIdioma(unittest.TestCase):

    def setUp(self):
        self.config = cargar_config('config.json')

    def test_el_castellano_pasa(self):
        escalon, detalle = revisar(CASTELLANO, self.config)
        self.assertEqual(escalon, 'ok')
        self.assertGreater(detalle['espanol'], detalle['ingles'])

    def test_el_capitulo_en_ingles_bloquea(self):
        escalon, detalle = revisar(INGLES, self.config)
        self.assertEqual(escalon, 'bloqueo')
        self.assertIn('ingles', detalle['motivo'])

    def test_las_tildes_no_cambian_el_recuento(self):
        # `mas` y `más` son la misma palabra funcional: el escritor acentua y
        # los prompts del repositorio no, asi que contar por la forma exacta
        # dejaria fuera justo el texto que hay que medir.
        con = revisar('Habia mas hambre que pan, y mas dias por delante '
                      'de los que nadie queria contar en voz alta alli.',
                      self.config)
        sin = revisar('Había más hambre que pan, y más días por delante '
                      'de los que nadie quería contar en voz alta allí.',
                      self.config)
        self.assertEqual(con[1]['espanol'], sin[1]['espanol'])

    def test_un_texto_corto_no_decide_nada(self):
        # Dos frases no dan senal, y un falso bloqueo aqui tira un capitulo
        # bueno sin que ninguna nota lo pueda defender.
        escalon, _ = revisar('# Barro rojo', self.config)
        self.assertEqual(escalon, 'sin_datos')

    def test_el_castellano_con_nombres_latinos_sigue_pasando(self):
        # El riesgo real del metodo: una novela romana esta llena de nombres y
        # terminos latinos. Como solo se cuentan funcionales, no contaminan.
        escalon, _ = revisar(
            'Scipio Aemilianus mando levantar la circunvalacion con siete '
            'campamentos, y el consejo de ancianos de Numancia respondio con '
            'el silencio de quien ya ha contado el grano que le queda en casa. '
            'Los auxiliares hispanos del campamento de Castillejo cobraban en '
            'denarios, y por eso ninguno de los que vigilaban el foso aquella '
            'noche tenia prisa por volver a su puesto antes de tiempo.',
            self.config)
        self.assertEqual(escalon, 'ok')

    def test_los_dos_umbrales_salen_de_config_y_no_del_codigo(self):
        # Es la regla de §12. Se comprueba moviendolos: si el modulo tuviera el
        # numero escrito dentro, cambiar la config no cambiaria el veredicto y
        # este test seguiria en verde con el bug puesto.
        corto = dict(self.config,
                     margenes=dict(self.config['margenes'],
                                   idioma_palabras_min=1))
        self.assertEqual(revisar('# Barro rojo', corto)[0], 'ok')

        tolerante = dict(self.config,
                         margenes=dict(self.config['margenes'],
                                       idioma_factor=1000))
        self.assertEqual(revisar(INGLES, tolerante)[0], 'ok')

    def test_el_umbral_separa_los_capitulos_reales_por_tres_ordenes(self):
        # Con los dieciseis capitulos escritos delante, el peor castellano esta
        # a 0,003 de disparar la comprobacion y el capitulo en ingles la pasa
        # nueve veces. El umbral no se eligio a ojo.
        _, ingles = revisar(INGLES, self.config)
        _, castellano = revisar(CASTELLANO, self.config)
        factor = self.config['margenes']['idioma_factor']
        self.assertGreater(ingles['ingles'], ingles['espanol'] * factor * 2)
        self.assertLess(castellano['ingles'], castellano['espanol'] * factor / 10)


class TestElComando(unittest.TestCase):
    """El escalon tiene que notarse en el codigo de salida: quien encadena
    comandos no lee la prosa de la salida, mira si fue cero."""

    def _fichero(self, texto):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        ruta = Path(tmp.name) / 'cap-01-intento-1.md'
        ruta.write_text(texto, encoding='utf-8')
        return str(ruta)

    def test_un_capitulo_en_castellano_sale_con_cero(self):
        self.assertEqual(main(['idioma', self._fichero(CASTELLANO)]), 0)

    def test_un_capitulo_en_ingles_sale_con_uno(self):
        self.assertEqual(main(['idioma', self._fichero(INGLES)]), 1)

    def test_un_texto_corto_no_bloquea(self):
        # `sin_datos` no es un fallo: un falso bloqueo tira un capitulo bueno
        # sin que ninguna nota lo pueda defender.
        self.assertEqual(main(['idioma', self._fichero('# Barro rojo')]), 0)

    def test_sin_ruta_no_revienta_feo(self):
        self.assertEqual(main(['idioma']), 1)


if __name__ == '__main__':
    unittest.main()
