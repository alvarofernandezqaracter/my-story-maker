# Lo determinista del harness: config (§12), gate (§8), validadores (§9) y la
# capa de trazas (§20). Estos tests no llaman a ningun agente ni salen a la red;
# los de trazas comprueban justamente que con las trazas apagadas nadie sale.
import copy
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from novela.agentes import reparto_de_tokens
from novela.config import validar_config, ErrorConfig
from novela.entorno import cargar_entorno, leer_env
from novela.trazas import MUDA, Trazas, enmascarar, sesion_de
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
    'interfaz': {'puerto': 8787, 'camino': 'delegado'},
    'trazas': {'activas': False, 'entorno': 'pruebas'},
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

    def test_el_puerto_de_la_interfaz_tiene_que_ser_un_puerto(self):
        for puerto in (80, 0, 70000, 8787.0, '8787'):
            roto = copy.deepcopy(CONFIG)
            roto['interfaz']['puerto'] = puerto
            with self.subTest(puerto=puerto):
                with self.assertRaisesRegex(ErrorConfig, 'interfaz.puerto'):
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

    def test_el_entorno_de_trazas_tiene_que_valer_para_langfuse(self):
        # Langfuse no acepta mayusculas, espacios ni nombres suyos, y un entorno
        # mal escrito no falla: manda las trazas a otro sitio (§20).
        for entorno in ('Desarrollo', 'con espacio', 'langfuse-mio', '', 7):
            roto = copy.deepcopy(CONFIG)
            roto['trazas']['entorno'] = entorno
            with self.subTest(entorno=entorno):
                with self.assertRaisesRegex(ErrorConfig, 'trazas.entorno'):
                    validar_config(roto)

    def test_las_trazas_se_encienden_y_se_apagan_con_un_booleano(self):
        roto = copy.deepcopy(CONFIG)
        roto['trazas']['activas'] = 'si'
        with self.assertRaisesRegex(ErrorConfig, 'trazas.activas'):
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


# -------------------------------------------------------------------- §20

class TestEntorno(unittest.TestCase):
    """El .env de §20: las credenciales no viven en config.json."""

    def _escribir(self, contenido):
        carpeta = tempfile.mkdtemp(prefix='novela-env-')
        ruta = Path(carpeta) / '.env'
        ruta.write_text(contenido, encoding='utf-8')
        return str(ruta)

    def test_lee_pares_y_quita_comillas_y_comentarios(self):
        ruta = self._escribir('# comentario\nA=1\nB="dos"\nC=\'tres\'\n\nsin_igual\n')
        self.assertEqual(leer_env(ruta), {'A': '1', 'B': 'dos', 'C': 'tres'})

    def test_sin_fichero_no_es_un_error(self):
        self.assertEqual(leer_env('no-existe-este-fichero.env'), {})

    def test_el_entorno_real_gana_sobre_el_fichero(self):
        ruta = self._escribir('NOVELA_PRUEBA_ENV=del-fichero\n')
        with mock.patch.dict(os.environ, {'NOVELA_PRUEBA_ENV': 'de-la-consola'}):
            cargar_entorno(ruta)
            self.assertEqual(os.environ['NOVELA_PRUEBA_ENV'], 'de-la-consola')
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop('NOVELA_PRUEBA_ENV', None)
            cargar_entorno(ruta)
            self.assertEqual(os.environ['NOVELA_PRUEBA_ENV'], 'del-fichero')
            os.environ.pop('NOVELA_PRUEBA_ENV', None)


class TestTrazas(unittest.TestCase):
    """La capa de §20 apagada tiene que ser indistinguible de no existir."""

    def test_apagada_por_configuracion_no_arranca_cliente(self):
        trazas = Trazas({**CONFIG, 'trazas': {'activas': False, 'entorno': 'pruebas'}})
        self.assertFalse(trazas.activa)
        self.assertIn('activas', trazas.motivo)

    def test_apagada_devuelve_objetos_mudos_que_aceptan_todo(self):
        trazas = Trazas(CONFIG)
        with trazas.traza('x', entrada={'a': 1}) as t:
            t.actualizar(output={'b': 2})
            t.nota('media', 4.0)
            with trazas.paso('y', 'generation', entrada=1) as p:
                self.assertIs(p, MUDA)
        self.assertIs(t, MUDA)
        trazas.cerrar()

    def test_encendida_sin_credencial_se_queda_muda_y_lo_dice(self):
        # Sin las dos claves en el entorno no hay cliente. El .env no se lee
        # aqui: el test no puede depender del fichero de quien lo lance.
        entorno = {k: v for k, v in os.environ.items() if not k.startswith('LANGFUSE_')}
        with mock.patch.dict(os.environ, entorno, clear=True), \
                mock.patch('novela.trazas.cargar_entorno', lambda *a, **k: []):
            trazas = Trazas({**CONFIG, 'trazas': {'activas': True, 'entorno': 'pruebas'}})
        self.assertFalse(trazas.activa)
        self.assertIn('LANGFUSE_', trazas.motivo)

    def test_un_fallo_apaga_las_trazas_y_no_sube(self):
        trazas = Trazas(CONFIG)
        avisos = []
        trazas.aviso = avisos.append
        trazas._cliente = object()          # basta con que no sea None
        self.assertTrue(trazas.activa)
        trazas.averiado(RuntimeError('la red no va'))
        self.assertFalse(trazas.activa)
        self.assertEqual(len(avisos), 1)
        # El segundo fallo no vuelve a avisar: se avisa una vez y se calla.
        trazas.averiado(RuntimeError('otra vez'))
        self.assertEqual(len(avisos), 1)

    def test_la_mascara_tapa_lo_que_parece_credencial(self):
        limpio = enmascarar(data={'texto': 'la clave es sk-ant-api03-abcdef123456'})
        self.assertNotIn('sk-ant-api03', json.dumps(limpio))
        self.assertIn('CREDENCIAL_OCULTA', json.dumps(limpio))
        # Lo que no lo parece se queda como estaba, byte a byte.
        intacto = {'texto': 'Sevilla, 1587', 'nota': 4}
        self.assertEqual(enmascarar(data=intacto), intacto)

    def test_la_sesion_sale_del_brief_y_distingue_novelas(self):
        uno = {'epoca': 'Sevilla, 1587', 'premisa': 'p', 'tono': 't',
               'capitulos': 6, 'palabras_por_capitulo': 1800}
        self.assertEqual(sesion_de(uno), sesion_de(dict(uno)))
        self.assertNotEqual(sesion_de(uno), sesion_de({**uno, 'premisa': 'otra'}))
        self.assertIsNone(sesion_de(None))


class TestRepartoDeTokens(unittest.TestCase):
    """Las cubetas de §20 no se solapan: cada token en una sola clave."""

    def test_traduce_el_uso_del_sdk_y_el_de_la_cli(self):
        class Uso:                                   # lo que devuelve el SDK
            input_tokens = 100
            output_tokens = 50
            cache_read_input_tokens = 7
            cache_creation_input_tokens = 0

        self.assertEqual(reparto_de_tokens(Uso()),
                         {'input': 100, 'output': 50, 'cache_read_input_tokens': 7})
        self.assertEqual(
            reparto_de_tokens({'input_tokens': 2, 'output_tokens': 9}),
            {'input': 2, 'output': 9})

    def test_sin_datos_no_se_inventa_nada(self):
        self.assertIsNone(reparto_de_tokens(None))
        self.assertIsNone(reparto_de_tokens({}))
        self.assertIsNone(reparto_de_tokens({'input_tokens': 0}))


if __name__ == '__main__':
    unittest.main()
