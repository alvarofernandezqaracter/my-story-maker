# VD-14 (§9): el capitulo esta en el idioma de la novela.
#
# La comprobacion nacio de una pasada real: un capitulo entero en ingles paso el
# gate con 4/4/4 porque ninguna de las tres rubricas mira el idioma. Estos tests
# fijan lo que tiene que cazar y, sobre todo, lo que no debe tocar.
import unittest

from novela.idioma import revisar, MINIMO_PALABRAS

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
    def test_el_castellano_pasa(self):
        escalon, detalle = revisar(CASTELLANO)
        self.assertEqual(escalon, 'ok')
        self.assertGreater(detalle['espanol'], detalle['ingles'])

    def test_el_capitulo_en_ingles_bloquea(self):
        escalon, detalle = revisar(INGLES)
        self.assertEqual(escalon, 'bloqueo')
        self.assertIn('ingles', detalle['motivo'])

    def test_las_tildes_no_cambian_el_recuento(self):
        # `mas` y `más` son la misma palabra funcional: el escritor acentua y
        # los prompts del repositorio no, asi que contar por la forma exacta
        # dejaria fuera justo el texto que hay que medir.
        con = revisar('Habia mas hambre que pan, y mas dias por delante '
                      'de los que nadie queria contar en voz alta alli.')
        sin = revisar('Había más hambre que pan, y más días por delante '
                      'de los que nadie quería contar en voz alta allí.')
        self.assertEqual(con[1]['espanol'], sin[1]['espanol'])

    def test_un_texto_corto_no_decide_nada(self):
        # Dos frases no dan senal, y un falso bloqueo aqui tira un capitulo
        # bueno sin que ninguna nota lo pueda defender.
        escalon, _ = revisar('# Barro rojo')
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
            'noche tenia prisa por volver a su puesto antes de tiempo.')
        self.assertEqual(escalon, 'ok')

    def test_el_minimo_es_el_que_dice_el_modulo(self):
        self.assertEqual(len(('palabra ' * MINIMO_PALABRAS).split()), MINIMO_PALABRAS)


if __name__ == '__main__':
    unittest.main()
