# Lo determinista del harness: config (§12), gate (§8) y validadores (§9).
# Estos tests no llaman a ningun agente ni tocan disco.
import copy
import unittest

from novela.config import validar_config, ErrorConfig
from novela.gate import gate, mejor_intento, incidencias_ordenadas
from novela.validadores import (
    comprobar_salida_de_agente, comprobar_dossier, comprobar_eventos,
    comprobar_referencias, comprobar_numero_de_capitulos,
    comprobar_capitulo_redactado, comprobar_personajes_presentes,
    comprobar_revisiones, comprobar_resumen_solo_si_aprobado,
    contar_palabras, contar_parrafos,
)

CONFIG = {
    'ejecucion': {'modo': 'simulado'},
    'gate': {'nota_minima': 3, 'media_minima': 3.7, 'max_intentos': 3},
    'contexto': {'tope_contexto': 40000, 'ventana_resumenes': 3, 'palabras_enganche': 400},
    'validador': {'modo': 'unico'},
    'margenes': {
        'capitulos_min': 0.8, 'capitulos_max': 1.2,
        'palabras_aviso': 0.15, 'palabras_bloqueo': 0.4, 'parrafos_min': 3,
    },
    'modelo_por_rol': {
        'investigador': 'claude-opus-5', 'arquitecto': 'claude-opus-5',
        'escritor': 'claude-opus-5', 'validador': 'claude-sonnet-5',
        'cronista': 'claude-sonnet-5', 'editor_global': 'claude-opus-5',
    },
    'busqueda_web': True,
}

MARGENES = CONFIG['margenes']


def revision(dimension, nota, incidencias=None):
    return {'dimension': dimension, 'nota': nota, 'incidencias': incidencias or []}


def _comprobacion(resultado, id_validador):
    return next(c for c in resultado.comprobaciones if c['id'] == id_validador)


# ------------------------------------------------------------------- §12

class TestConfig(unittest.TestCase):

    def test_el_fichero_del_proyecto_es_valido(self):
        self.assertEqual(validar_config(copy.deepcopy(CONFIG)), CONFIG)

    def test_los_tres_modos_de_ejecucion_valen(self):
        for modo in ('simulado', 'real', 'claude_code'):
            copia = copy.deepcopy(CONFIG)
            copia['ejecucion']['modo'] = modo
            self.assertEqual(validar_config(copia)['ejecucion']['modo'], modo)

    def test_para_si_el_modo_de_ejecucion_no_existe(self):
        roto = copy.deepcopy(CONFIG)
        roto['ejecucion']['modo'] = 'inventado'
        with self.assertRaisesRegex(ErrorConfig, 'ejecucion.modo'):
            validar_config(roto)

    def test_para_si_falta_una_clave(self):
        roto = copy.deepcopy(CONFIG)
        del roto['busqueda_web']
        with self.assertRaises(ErrorConfig):
            validar_config(roto)

    def test_para_si_un_valor_cae_fuera_de_rango(self):
        roto = copy.deepcopy(CONFIG)
        roto['gate']['media_minima'] = 9
        with self.assertRaisesRegex(ErrorConfig, 'media_minima'):
            validar_config(roto)

    def test_el_margen_de_bloqueo_tiene_que_superar_al_de_aviso(self):
        roto = copy.deepcopy(CONFIG)
        roto['margenes']['palabras_bloqueo'] = 0.1
        with self.assertRaisesRegex(ErrorConfig, 'palabras_bloqueo'):
            validar_config(roto)


# -------------------------------------------------------------------- §8

class TestGate(unittest.TestCase):

    def test_aprueba_con_tres_notas_buenas_y_sin_graves(self):
        v = gate([revision('continuidad', 4), revision('anacronismos', 4),
                  revision('logica_ritmo', 4)], CONFIG['gate'])
        self.assertTrue(v['aprueba'])

    def test_una_nota_por_debajo_del_suelo_tumba_el_capitulo(self):
        v = gate([revision('continuidad', 2), revision('anacronismos', 5),
                  revision('logica_ritmo', 5)], CONFIG['gate'])
        self.assertFalse(v['aprueba'])
        self.assertRegex(' '.join(v['motivos']), 'nota minima')

    def test_la_media_manda_aunque_ninguna_nota_baje_del_suelo(self):
        # 3/3/5 da media 3,67, por debajo de 3,7, con todas las notas en el suelo.
        v = gate([revision('continuidad', 3), revision('anacronismos', 3),
                  revision('logica_ritmo', 5)], CONFIG['gate'])
        self.assertFalse(v['aprueba'])
        self.assertRegex(' '.join(v['motivos']), 'media')

    def test_una_incidencia_grave_veta_por_si_sola_con_tres_cuatros(self):
        v = gate([
            revision('continuidad', 4, [{'cita': 'x', 'severidad': 'grave', 'sugerencia': 'y'}]),
            revision('anacronismos', 4), revision('logica_ritmo', 4),
        ], CONFIG['gate'])
        self.assertFalse(v['aprueba'])
        self.assertEqual(len(v['graves']), 1)

    def test_al_agotar_intentos_se_conserva_el_de_mejor_media(self):
        intentos = [
            {'intento': 1, 'revisiones': [revision('continuidad', 2),
                                          revision('anacronismos', 2),
                                          revision('logica_ritmo', 2)]},
            {'intento': 2, 'revisiones': [revision('continuidad', 3),
                                          revision('anacronismos', 3),
                                          revision('logica_ritmo', 4)]},
            {'intento': 3, 'revisiones': [revision('continuidad', 1),
                                          revision('anacronismos', 5),
                                          revision('logica_ritmo', 2)]},
        ]
        self.assertEqual(mejor_intento(intentos)['intento'], 2)

    def test_las_incidencias_del_reintento_van_por_severidad(self):
        orden = incidencias_ordenadas([
            revision('continuidad', 3, [{'cita': 'a', 'severidad': 'aviso', 'sugerencia': ''}]),
            revision('anacronismos', 2, [{'cita': 'b', 'severidad': 'grave', 'sugerencia': ''}]),
        ])
        self.assertEqual(orden[0]['severidad'], 'grave')


# -------------------------------------------------------------------- §9

class TestValidadores(unittest.TestCase):

    def test_vd01_vd02_distingue_forma_rota_de_campo_ausente(self):
        sin_campo = comprobar_salida_de_agente('escritor', {'faltantes': []})
        self.assertFalse(_comprobacion(sin_campo, 'VD-02')['ok'])

        forma_mala = comprobar_salida_de_agente('escritor', {'texto': 42})
        self.assertFalse(_comprobacion(forma_mala, 'VD-01')['ok'])

    def test_vd03_rechaza_la_propuesta_entera_no_la_parte_buena(self):
        conocidos = {'personajes': {'ines'}, 'datos': set(), 'capitulos': set()}
        c = comprobar_referencias('cronista', {
            'personajes_presentes': ['ines', 'fantasma'],
        }, conocidos)
        self.assertFalse(c['ok'])
        self.assertRegex(' '.join(c['detalles']), 'fantasma')

    def test_vd04_un_dato_verificado_no_puede_tener_fuente_modelo(self):
        c = comprobar_dossier([
            {'id': 'a', 'categoria': 'comida', 'dato': 'x',
             'fuente': 'modelo', 'estado': 'verificado'},
            {'id': 'b', 'categoria': 'comida', 'dato': 'x',
             'fuente': 'modelo', 'estado': 'sin_verificar'},
        ])
        self.assertFalse(c['ok'])
        self.assertEqual([m['id'] for m in c['malos']], ['a'])

    def test_vd05_trama_lleva_capitulo_historico_no(self):
        self.assertFalse(comprobar_eventos([{'id': 'e', 'tipo': 'trama'}])['ok'])
        self.assertFalse(comprobar_eventos(
            [{'id': 'e', 'tipo': 'historico', 'capitulo': 3}])['ok'])
        self.assertTrue(comprobar_eventos(
            [{'id': 'e', 'tipo': 'trama', 'capitulo': 3}])['ok'])

    def test_vd06_no_hay_resumen_sin_intento_aprobado(self):
        self.assertFalse(comprobar_resumen_solo_si_aprobado(None)['ok'])
        self.assertTrue(comprobar_resumen_solo_si_aprobado({'intento': 1})['ok'])

    def test_vd07_el_numero_de_capitulos_se_mide_contra_los_margenes(self):
        self.assertTrue(comprobar_numero_de_capitulos(10, 10, MARGENES)['ok'])
        self.assertTrue(comprobar_numero_de_capitulos(8, 10, MARGENES)['ok'])
        self.assertFalse(comprobar_numero_de_capitulos(5, 10, MARGENES)['ok'])
        self.assertFalse(comprobar_numero_de_capitulos(20, 10, MARGENES)['ok'])

    def test_vd08_los_dos_escalones_que_es_la_razon_de_los_dos_margenes(self):
        def parrafos(n, palabras_por_parrafo=100):
            uno = ('palabra ' * palabras_por_parrafo).strip()
            return '\n\n'.join([uno] * n)

        # Dentro del margen de aviso: el texto vale y no genera nada.
        self.assertTrue(comprobar_capitulo_redactado(parrafos(10, 100), 1000, MARGENES)['ok'])

        # Desvio del 20%: aviso, y el capitulo sigue camino del validador.
        aviso = comprobar_capitulo_redactado(parrafos(8, 100), 1000, MARGENES)
        self.assertEqual(aviso['severidad'], 'aviso')

        # Desvio del 50%: bloqueante, no se gasta la llamada al validador.
        bloqueo = comprobar_capitulo_redactado(parrafos(5, 100), 1000, MARGENES)
        self.assertEqual(bloqueo['severidad'], 'bloqueante')

        # Pocos parrafos bloquea aunque las palabras cuadren.
        pocos = comprobar_capitulo_redactado(parrafos(2, 500), 1000, MARGENES)
        self.assertEqual(pocos['severidad'], 'bloqueante')

    def test_vd08_el_titulo_markdown_no_cuenta_como_parrafo_pero_si_como_palabras(self):
        texto = '# Titulo\n\n{}'.format('\n\n'.join(['a b c', 'd e f']))
        self.assertEqual(contar_parrafos(texto), 2)
        self.assertEqual(contar_palabras(texto), 8)

    def test_vd09_personajes_presentes_es_subconjunto_de_la_ficha(self):
        self.assertTrue(comprobar_personajes_presentes(['a'], ['a', 'b'])['ok'])
        self.assertFalse(comprobar_personajes_presentes(['a', 'z'], ['a', 'b'])['ok'])

    def test_vd10_tres_dimensiones_una_vez_cada_una_nota_entera_1_5(self):
        buenas = [revision('continuidad', 3), revision('anacronismos', 3),
                  revision('logica_ritmo', 3)]
        self.assertTrue(comprobar_revisiones(buenas)['ok'])

        self.assertFalse(comprobar_revisiones(buenas[:2])['ok'])
        self.assertFalse(comprobar_revisiones(buenas + [revision('continuidad', 4)])['ok'])
        self.assertFalse(comprobar_revisiones([revision('continuidad', 3.5),
                                               revision('anacronismos', 3),
                                               revision('logica_ritmo', 3)])['ok'])
        self.assertFalse(comprobar_revisiones([revision('continuidad', 7),
                                               revision('anacronismos', 3),
                                               revision('logica_ritmo', 3)])['ok'])


if __name__ == '__main__':
    unittest.main()
