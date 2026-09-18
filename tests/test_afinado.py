# AFINADO.md. Lo que se prueba aqui es lo unico determinista del loop: la
# forma de una respuesta, las cuentas, el ruido y el veredicto. Lo que llama a
# los subagentes no se prueba, por la misma razon por la que la orquestacion
# tampoco tiene tests: es una conversacion.
#
# Sin red, como todos: nada de aqui toca Langfuse.
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from novela import afinado
from novela.config import cargar_config, validar_config, ErrorConfig


def _caso(ident, tipo, particion='reserva'):
    return {'id': ident, 'tipo': tipo, 'particion': particion,
            'marca': 'reloj de pulsera' if tipo == 'sembrado' else None,
            'origen': 'novela-de-prueba cap-01',
            'capitulo': 'texto del capitulo', 'contexto': 'el paquete'}


def _respuesta(nota, dimension=afinado.DIMENSION):
    return {'revisiones': [{'dimension': dimension, 'nota': nota,
                            'incidencias': []}]}


class _Temporal(unittest.TestCase):
    """Cada test en su propio temporal: la carpeta de trabajo es global y dos
    tests que la compartan se pisan."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        parche = mock.patch.object(
            afinado, 'carpeta_trabajo', lambda: Path(self.tmp.name))
        parche.start()
        self.addCleanup(parche.stop)
        self.addCleanup(self.tmp.cleanup)
        self.config = cargar_config('config.json')

    def _escribir(self, vuelta, prompt, respuestas):
        carpeta = afinado.ruta_vuelta(vuelta) / 'respuestas' / prompt
        carpeta.mkdir(parents=True, exist_ok=True)
        for nombre, cuerpo in respuestas.items():
            (carpeta / (nombre + '.json')).write_text(
                json.dumps(cuerpo, ensure_ascii=False), encoding='utf-8')


class TestLaForma(unittest.TestCase):
    """VD-10 aplicado al bloque unico: lo que no cumple la forma no es una nota
    mala, es una respuesta que no sirve."""

    def test_un_bloque_bien_formado_pasa(self):
        bloque = afinado.leer_bloque(_respuesta(4))
        self.assertEqual(bloque['nota'], 4)

    def test_el_json_puede_venir_como_texto(self):
        self.assertIsNotNone(afinado.leer_bloque(json.dumps(_respuesta(2))))

    def test_dos_bloques_no_pasan(self):
        doble = {'revisiones': [_respuesta(4)['revisiones'][0],
                                _respuesta(3)['revisiones'][0]]}
        self.assertIsNone(afinado.leer_bloque(doble))

    def test_una_nota_con_decimales_no_pasa(self):
        self.assertIsNone(afinado.leer_bloque(_respuesta(4.5)))

    def test_una_nota_fuera_de_rango_no_pasa(self):
        self.assertIsNone(afinado.leer_bloque(_respuesta(6)))

    def test_un_booleano_no_es_una_nota(self):
        self.assertIsNone(afinado.leer_bloque(_respuesta(True)))

    def test_una_dimension_inventada_no_pasa(self):
        self.assertIsNone(afinado.leer_bloque(_respuesta(4, 'ritmo')))

    def test_lo_que_no_es_json_no_pasa(self):
        self.assertIsNone(afinado.leer_bloque('el capitulo me parece correcto'))


class TestLasCuentas(_Temporal):

    def setUp(self):
        super().setUp()
        self.clave = {c['id']: c for c in [
            _caso('caso-01', 'sembrado'), _caso('caso-02', 'sembrado'),
            _caso('caso-03', 'limpio'), _caso('caso-04', 'limpio')]}

    def test_detecta_lo_sembrado_por_debajo_del_suelo_del_gate(self):
        # nota_minima es 3: un 2 bloquea y un 3 no. El suelo sale de config y
        # no de aqui, que es la regla de §12.
        medida = afinado.medir_pasada(self.config, self.clave, {
            'caso-01': _respuesta(2), 'caso-02': _respuesta(4),
            'caso-03': _respuesta(5), 'caso-04': _respuesta(1)})
        self.assertEqual(medida['deteccion'], 0.5)
        self.assertEqual(medida['falsos_positivos'], 0.5)
        self.assertEqual(medida['forma'], 1.0)

    def test_una_respuesta_sin_forma_no_cuenta_como_fallo_de_deteccion(self):
        # Si contara, un prompt que deja de contestar saldria premiado.
        medida = afinado.medir_pasada(self.config, self.clave, {
            'caso-01': _respuesta(2), 'caso-02': 'me he liado',
            'caso-03': _respuesta(5), 'caso-04': _respuesta(5)})
        self.assertEqual(medida['deteccion'], 1.0)
        self.assertEqual(medida['forma'], 0.75)

    def test_la_particion_filtra(self):
        self.clave['caso-01']['particion'] = 'taller'
        medida = afinado.medir_pasada(self.config, self.clave, {
            'caso-01': _respuesta(1), 'caso-02': _respuesta(5)},
            particion='reserva')
        self.assertEqual(medida['sembrados'], 1)
        self.assertEqual(medida['deteccion'], 0.0)


class TestElRuido(_Temporal):

    def test_el_ruido_es_lo_que_se_movio_sin_cambiar_nada(self):
        afinado.ruta_clave(1).parent.mkdir(parents=True, exist_ok=True)
        afinado.ruta_clave(1).write_text(json.dumps(
            {'caso-01': _caso('caso-01', 'sembrado'),
             'caso-02': _caso('caso-02', 'sembrado')}), encoding='utf-8')
        self._escribir(1, 'vigente', {
            'caso-01-p1': _respuesta(1), 'caso-02-p1': _respuesta(1),
            'caso-01-p2': _respuesta(5), 'caso-02-p2': _respuesta(5),
            'caso-01-p3': _respuesta(1), 'caso-02-p3': _respuesta(5)})
        medida = afinado.medir(self.config, 1, 'vigente')
        self.assertEqual([p['deteccion'] for p in medida['pasadas']],
                         [1.0, 0.0, 0.5])
        self.assertEqual(medida['deteccion'], 0.5)
        self.assertEqual(medida['ruido'], 1.0)

    def test_sin_respuestas_se_para_antes_de_inventarse_un_numero(self):
        with self.assertRaises(afinado.ErrorAfinado):
            afinado.medir(self.config, 9, 'vigente')


class TestElVeredicto(unittest.TestCase):
    """La regla entera, impresa. Un margen que no supera al ruido no promueve:
    si lo hiciera, el loop no mediria, sortearia."""

    def setUp(self):
        self.config = cargar_config('config.json')

    def _medida(self, deteccion, ruido, falsos=0.0, forma=1.0):
        return {'deteccion': deteccion, 'ruido': ruido,
                'falsos_positivos': falsos, 'forma': forma}

    def test_una_mejora_por_debajo_del_ruido_no_promueve(self):
        v = afinado.comparar(self.config, self._medida(0.5, 0.33),
                             self._medida(0.7, 0.2))
        self.assertFalse(v['bate_el_ruido'])
        self.assertFalse(v['promueve'])

    def test_una_mejora_por_encima_del_ruido_promueve(self):
        v = afinado.comparar(self.config, self._medida(0.5, 0.1),
                             self._medida(0.8, 0.1))
        self.assertTrue(v['promueve'])
        self.assertIn('>', v['operacion'])

    def test_una_guardia_rota_veta_aunque_la_metrica_suba(self):
        v = afinado.comparar(self.config, self._medida(0.5, 0.1),
                             self._medida(0.9, 0.1, falsos=0.4))
        self.assertTrue(v['bate_el_ruido'])
        self.assertFalse(v['promueve'])
        self.assertEqual(v['rotas'], ['falsos_positivos'])

    def test_una_guardia_sin_medir_no_se_da_por_cumplida(self):
        v = afinado.comparar(self.config, self._medida(0.5, 0.1),
                             self._medida(0.9, 0.1, forma=None))
        self.assertIn('forma', v['rotas'])

    def test_el_ruido_que_manda_es_el_del_vigente(self):
        # El candidato puede salir con ruido cero por suerte; lo que hay que
        # batir es cuanto se mueve la medida cuando nada cambia.
        v = afinado.comparar(self.config, self._medida(0.5, 0.5),
                             self._medida(0.9, 0.0))
        self.assertEqual(v['ruido'], 0.5)
        self.assertFalse(v['promueve'])


class TestLaVuelta(_Temporal):

    def test_abrir_deja_los_casos_sin_decir_cuales_estan_sembrados(self):
        casos = [_caso('caso-01', 'sembrado'), _caso('caso-02', 'limpio')]
        afinado.abrir_vuelta(1, 'afinado', casos)
        carpeta = afinado.ruta_vuelta(1) / 'casos'
        self.assertEqual(sorted(p.name for p in carpeta.iterdir()),
                         ['caso-01', 'caso-02'])
        # Lo que hay dentro de la carpeta de la vuelta no puede delatar nada.
        crudo = '\n'.join(p.read_text(encoding='utf-8')
                          for p in afinado.ruta_vuelta(1).rglob('*.*'))
        self.assertNotIn('sembrado', crudo)
        self.assertNotIn('reloj de pulsera', crudo)

    def test_la_clave_vive_fuera_de_la_carpeta_de_la_vuelta(self):
        afinado.abrir_vuelta(1, 'afinado', [_caso('caso-01', 'sembrado')])
        clave = afinado.ruta_clave(1)
        self.assertTrue(clave.exists())
        self.assertNotIn(afinado.ruta_vuelta(1), clave.parents)

    def test_una_vuelta_sin_casos_no_se_abre(self):
        with self.assertRaises(afinado.ErrorAfinado):
            afinado.abrir_vuelta(1, 'afinado', [])

    def test_el_hook_ve_la_vuelta_abierta_y_deja_de_verla_al_cerrarla(self):
        afinado.abrir_vuelta(1, 'afinado', [_caso('caso-01', 'limpio')])
        marca = afinado.vuelta_en_curso()
        self.assertEqual(marca['sesion'], 'afinado-01')
        self.assertEqual(marca['entorno'], 'afinado')
        afinado.cerrar_vuelta(1)
        self.assertIsNone(afinado.vuelta_en_curso())

    def test_cerrar_borra_los_casos_del_disco(self):
        afinado.abrir_vuelta(1, 'afinado', [_caso('caso-01', 'limpio')])
        afinado.cerrar_vuelta(1)
        self.assertFalse((afinado.ruta_vuelta(1) / 'casos').exists())


class TestQueLlamadaEsDeLaVuelta(_Temporal):
    """El marcador es de la maquina entera: mientras se mide, otra sesion puede
    estar escribiendo una novela, y sus llamadas no pueden acabar en el entorno
    de afinado."""

    def setUp(self):
        super().setUp()
        from novela import trazas_hook
        self.hook = trazas_hook
        afinado.abrir_vuelta(1, 'afinado', [_caso('caso-01', 'sembrado')])

    def test_la_que_apunta_a_los_casos_es_de_la_vuelta(self):
        ruta = str(afinado.ruta_vuelta(1) / 'casos' / 'caso-01' / 'capitulo.md')
        self.assertIsNotNone(self.hook._vuelta_de('Juzga ' + ruta, None))

    def test_la_ruta_vale_con_barras_de_los_dos_lados(self):
        ruta = str(afinado.ruta_vuelta(1) / 'casos').replace('\\', '/')
        self.assertIsNotNone(self.hook._vuelta_de(ruta + '/caso-01/capitulo.md'))

    def test_la_de_una_novela_no_se_desvia_aunque_haya_vuelta_abierta(self):
        self.assertIsNone(self.hook._vuelta_de(
            'Juzga biblioteca/2026-09-18-cadiz-1812/capitulos/cap-02-intento-1.md'))

    def test_sin_vuelta_abierta_no_hay_nada_que_desviar(self):
        afinado.cerrar_vuelta(1)
        ruta = str(afinado.ruta_vuelta(1) / 'casos')
        self.assertIsNone(self.hook._vuelta_de(ruta))


class TestLosFrenos(unittest.TestCase):

    def setUp(self):
        self.config = cargar_config('config.json')

    def test_sin_motivo_no_para(self):
        self.assertIsNone(afinado.parar(self.config, 0, 0, 0.0))

    def test_para_al_agotar_los_candidatos(self):
        self.assertIn('candidatos', afinado.parar(self.config, 0, 3, 0.0))

    def test_para_con_dos_fallos_seguidos(self):
        self.assertIn('seguidos', afinado.parar(self.config, 2, 0, 0.0))

    def test_para_al_llegar_al_tope_de_gasto(self):
        self.assertIn('gasto', afinado.parar(self.config, 0, 0, 1.0))


class TestLaPromocion(unittest.TestCase):

    def test_el_asunto_del_commit_tiene_forma_fija(self):
        # Lo que hace reversible una promocion es poder encontrarla.
        self.assertEqual(
            afinado.mensaje_de_promocion(3, 'validador'),
            'feat(afinado): vuelta 03 promueve el prompt de validador')


class TestSuConfig(unittest.TestCase):

    def setUp(self):
        self.base = cargar_config('config.json')

    def test_una_sola_pasada_no_arranca(self):
        # Con una pasada no hay ruido que medir y el loop se queda ciego.
        with self.assertRaisesRegex(ErrorConfig, 'afinado.pasadas'):
            validar_config({**self.base,
                            'afinado': {**self.base['afinado'], 'pasadas': 1}})

    def test_el_entorno_de_afinado_no_puede_ser_el_de_las_novelas(self):
        with self.assertRaisesRegex(ErrorConfig, 'afinado.entorno'):
            validar_config({**self.base,
                            'afinado': {**self.base['afinado'],
                                        'entorno': self.base['trazas']['entorno']}})


if __name__ == '__main__':
    unittest.main()
