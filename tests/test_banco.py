# El banco de AUTOAPRENDIZAJE.md, sin red y sin gastar un centimo.
#
# Lo que se prueba aqui es **la aritmetica y las reglas de parada**, que es la
# unica parte del banco que se puede probar: que el loop produzca prompts
# mejores no lo dice ningun test, lo dice la siguiente novela. Nada de esto
# arranca una sesion de Claude Code; el corredor se prueba por sus bordes -sin
# ejecutable, sin salida- y por lo que hace con una corrida ya medida.
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from novela import casos as casos_mod
from novela.banco import (
    comparar, componer, ErrorBanco, Gasto, cargar_objetivo, listar_objetivos,
    arbol_sucio, mejora, merece_la_reserva, promover, resumir,
    sin_frontmatter)
from novela.config import validar_config, ErrorConfig
from novela.metricas import (
    agregar, json_de, medir, MEDIDAS, palabras, parrafos, tokens_estimados)

CONFIG = {
    'gate': {'nota_minima': 3, 'media_minima': 3.7, 'max_intentos': 3},
    'contexto': {'tope_contexto': 40000, 'ventana_resumenes': 3, 'palabras_enganche': 400},
    'interfaz': {'puerto': 8787},
    'lanzador': {'comando': 'claude', 'permisos': 'acceptEdits'},
    'margenes': {'capitulos_min': 0.8, 'capitulos_max': 1.2, 'palabras_aviso': 0.15,
                 'palabras_bloqueo': 0.4, 'parrafos_min': 3},
    'trazas': {'activas': False, 'entorno': 'pruebas', 'texto': True},
    'autoaprendizaje': {'rondas_max': 3, 'candidatos_por_ronda': 3,
                        'margen_mejora': 0.1, 'casos_minimos': 3, 'gasto_max': 5.0,
                        'paciencia': 2, 'corridas_en_paralelo': 3,
                        'tope_segundos': 600, 'repeticiones': 1},
}

OBJETIVO = {
    'id': 'prueba', 'rol': 'investigador',
    'prompt': 'agentes/investigador.md',
    'piezas': ['cabecera.md', 'agentes/investigador.md'],
    'objetivo': {'metrica': 'tokens_rol', 'direccion': 'baja', 'agregado': 'media'},
    'guardias': [{'metrica': 'datos', 'agregado': 'media', 'minimo': 12},
                 {'metrica': 'vd04_fallos', 'agregado': 'suma', 'maximo': 0}],
}


SALTO = chr(10)


def dossier(cuantos, categoria='vestimenta', estado='sin_verificar', fuente='modelo'):
    return json.dumps({'datos': [
        {'id': 'd{}'.format(i), 'categoria': categoria, 'dato': 'Una afirmacion.',
         'fuente': fuente, 'estado': estado, 'etiquetas': ['x']}
        for i in range(cuantos)]}, ensure_ascii=False)


def corrida(salida, tokens_prompt=100, tokens_salida=100, caso='c1'):
    return {'caso': caso, 'ok': True, 'motivo': None, 'salida': salida,
            'tokens_prompt': tokens_prompt, 'tokens_salida': tokens_salida,
            'coste_usd': 0.01, 'segundos': 10.0}


class Metricas(unittest.TestCase):

    def test_los_tokens_se_estiman_siempre_con_la_misma_regla(self):
        # No pretende ser exacto: pretende no cambiar. Lo que compara el banco
        # son dos candidatos medidos con esta misma regla.
        self.assertEqual(tokens_estimados('a' * 400), 100)
        self.assertEqual(tokens_estimados(''), 1)

    def test_el_json_se_lee_aunque_venga_con_vallas(self):
        self.assertEqual(json_de('```json\n{"a": 1}\n```'), {'a': 1})
        self.assertIsNone(json_de('esto es prosa'))

    def test_vd04_cuenta_el_verificado_con_fuente_modelo(self):
        malo = dossier(1, estado='verificado', fuente='modelo')
        bueno = dossier(1, estado='verificado', fuente='Archivo de Indias, leg. 2')
        medidas = medir(corrida(malo), {}, CONFIG, ['vd04_fallos'])
        self.assertEqual(medidas['vd04_fallos'], 1)
        self.assertEqual(medir(corrida(bueno), {}, CONFIG, ['vd04_fallos'])['vd04_fallos'], 0)

    def test_vd04_tumba_la_salida_que_ni_siquiera_es_json(self):
        self.assertEqual(medir(corrida('prosa'), {}, CONFIG, ['vd04_fallos'])['vd04_fallos'], 1)

    def test_las_categorias_utiles_no_cuentan_otro(self):
        salida = json.dumps({'datos': [
            {'categoria': 'otro', 'dato': 'x', 'fuente': 'y', 'estado': 'inventado'},
            {'categoria': 'comida', 'dato': 'x', 'fuente': 'y', 'estado': 'inventado'}]})
        self.assertEqual(medir(corrida(salida), {}, CONFIG, ['categorias'])['categorias'], 1)

    def test_vd08_tiene_sus_dos_escalones_y_salen_de_la_config(self):
        caso = {'palabras_objetivo': 100}
        texto = lambda n: '\n\n'.join(['palabra ' * 10] * (n // 10))
        # 100 palabras exactas en diez parrafos: pasa.
        self.assertEqual(medir(corrida(texto(100)), caso, CONFIG, ['vd08'])['vd08'], 0)
        # 80 palabras: se sale del aviso (0,15) y no llega al bloqueo (0,4).
        self.assertEqual(medir(corrida(texto(80)), caso, CONFIG, ['vd08'])['vd08'], 1)
        # 50 palabras: bloqueo.
        self.assertEqual(medir(corrida(texto(50)), caso, CONFIG, ['vd08'])['vd08'], 2)

    def test_pocos_parrafos_bloquean_aunque_la_longitud_este_bien(self):
        caso = {'palabras_objetivo': 100}
        de_una_pieza = 'palabra ' * 100
        self.assertEqual(medir(corrida(de_una_pieza), caso, CONFIG, ['vd08'])['vd08'], 2)

    def test_el_desvio_no_lleva_signo(self):
        caso = {'palabras_objetivo': 100}
        corto = medir(corrida('palabra ' * 80), caso, CONFIG, ['desvio_palabras'])
        largo = medir(corrida('palabra ' * 120), caso, CONFIG, ['desvio_palabras'])
        self.assertAlmostEqual(corto['desvio_palabras'], 0.2)
        self.assertAlmostEqual(largo['desvio_palabras'], 0.2)

    def test_un_caso_sin_numero_no_es_un_cero(self):
        # Contarlo como cero haria baratisimo al candidato que falla la mitad
        # de los casos, que es justo al reves de lo que pasa.
        self.assertAlmostEqual(agregar([10, None, 20]), 15.0)
        self.assertIsNone(agregar([None, None]))
        self.assertEqual(agregar([1, 2, 3], 'suma'), 6)

    def test_el_json_se_rescata_de_debajo_de_un_preambulo(self):
        # El modelo antepone cortesias aunque su prompt se lo prohiba. Si eso
        # dejara a cero las metricas de contenido, el banco no distinguiria un
        # prompt charlatan de uno que no trabaja.
        con_preambulo = 'Aqui tienes el dossier:' + SALTO + SALTO + dossier(3)
        self.assertEqual(len(json_de(con_preambulo)['datos']), 3)
        self.assertEqual(medir(corrida(con_preambulo), {}, CONFIG, ['datos'])['datos'], 3)

    def test_la_forma_si_penaliza_el_preambulo(self):
        limpio = dossier(3)
        con_valla = '```json' + SALTO + limpio + SALTO + '```'
        self.assertEqual(medir(corrida(limpio), {}, CONFIG, ['vd01'])['vd01'], 0)
        self.assertEqual(medir(corrida('Aqui tienes:' + SALTO + limpio), {}, CONFIG,
                               ['vd01'])['vd01'], 1)
        self.assertEqual(medir(corrida(con_valla), {}, CONFIG, ['vd01'])['vd01'], 0)

    def test_una_llave_dentro_de_una_cadena_no_corta_el_json(self):
        crudo = 'texto antes {"datos": [{"dato": "un } dentro", "categoria": "comida"}]}'
        self.assertEqual(json_de(crudo)['datos'][0]['categoria'], 'comida')

    def test_los_tokens_por_dato_premian_al_que_rinde_y_no_al_que_trabaja_menos(self):
        # Un dossier el doble de grande por el mismo precio es mejor, y en
        # tokens absolutos se leeria como un empeoramiento.
        flojo = corrida(dossier(5), tokens_prompt=500, tokens_salida=500)
        lleno = corrida(dossier(20), tokens_prompt=500, tokens_salida=700)
        self.assertEqual(medir(flojo, {}, CONFIG, ['tokens_por_dato'])['tokens_por_dato'], 200)
        self.assertEqual(medir(lleno, {}, CONFIG, ['tokens_por_dato'])['tokens_por_dato'], 60)

    def test_sin_datos_no_hay_tokens_por_dato_en_vez_de_una_division_por_cero(self):
        vacio = corrida('esto no es un dossier')
        self.assertIsNone(medir(vacio, {}, CONFIG, ['tokens_por_dato'])['tokens_por_dato'])

    def test_palabras_y_parrafos_cuentan_lo_que_parece(self):
        self.assertEqual(palabras('una dos tres'), 3)
        self.assertEqual(parrafos('uno\n\ndos\n\n\ntres'), 3)


class PromptCompuesto(unittest.TestCase):

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        Path(self.dir, 'cabecera.md').write_text(
            '---\nrol: x\n---\n\nCabecera del subagente.', encoding='utf-8')
        Path(self.dir, 'agentes').mkdir()
        Path(self.dir, 'agentes', 'investigador.md').write_text(
            '---\nrol: investigador\n---\n\nPrompt vigente.', encoding='utf-8')

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_el_frontmatter_no_viaja_dentro_del_prompt(self):
        self.assertEqual(sin_frontmatter('---\na: 1\n---\nhola'), 'hola')
        self.assertEqual(sin_frontmatter('sin frontmatter'), 'sin frontmatter')

    def test_el_candidato_sustituye_a_su_pieza_y_las_demas_siguen(self):
        texto = componer(OBJETIVO, 'PROMPT CANDIDATO', raiz=self.dir)
        self.assertIn('Cabecera del subagente.', texto)
        self.assertIn('PROMPT CANDIDATO', texto)
        self.assertNotIn('Prompt vigente.', texto)
        self.assertIn('No busques ningun fichero', texto)

    def test_sin_candidato_se_compone_el_vigente(self):
        texto = componer(OBJETIVO, None, raiz=self.dir)
        self.assertIn('Prompt vigente.', texto)

    def test_una_pieza_que_no_existe_se_dice_al_arrancar(self):
        objetivo = dict(OBJETIVO, piezas=['no-esta.md', 'agentes/investigador.md'])
        with self.assertRaises(ErrorBanco):
            componer(objetivo, None, raiz=self.dir)


class ReglaDePromocion(unittest.TestCase):

    def _resumen(self, tokens, datos=20, fallos=0, validas=6):
        return {'agregados': {'tokens_rol': tokens, 'datos': datos,
                              'vd04_fallos': fallos},
                'detalle': [], 'casos': validas, 'validas': validas, 'coste_usd': 0.1}

    def test_la_mejora_se_mide_en_la_direccion_del_objetivo(self):
        self.assertAlmostEqual(mejora(100, 80, 'baja'), 0.2)
        self.assertAlmostEqual(mejora(100, 80, 'sube'), -0.2)
        self.assertIsNone(mejora(0, 80, 'baja'))
        self.assertIsNone(mejora(None, 80, 'baja'))

    def test_gana_el_que_mejora_por_encima_del_margen(self):
        veredicto = comparar(self._resumen(1000), self._resumen(700), OBJETIVO, CONFIG)
        self.assertTrue(veredicto['gana'])
        self.assertAlmostEqual(veredicto['ganancia'], 0.3)

    def test_una_mejora_por_debajo_del_margen_no_promueve(self):
        # Empate y casi empate son lo mismo: cambiar el prompt tiene un coste
        # que no esta en la tabla.
        veredicto = comparar(self._resumen(1000), self._resumen(950), OBJETIVO, CONFIG)
        self.assertFalse(veredicto['gana'])
        self.assertIn('margen', veredicto['motivos'][0])

    def test_una_guardia_caida_veta_por_si_sola(self):
        veredicto = comparar(self._resumen(1000), self._resumen(400, datos=5),
                             OBJETIVO, CONFIG)
        self.assertFalse(veredicto['gana'])
        self.assertTrue(any('guardia datos' in m for m in veredicto['motivos']))

    def test_vd04_no_admite_ni_un_fallo(self):
        veredicto = comparar(self._resumen(1000), self._resumen(400, fallos=1),
                             OBJETIVO, CONFIG)
        self.assertFalse(veredicto['gana'])

    def test_sin_casos_suficientes_no_hay_promocion_por_mucho_que_gane(self):
        veredicto = comparar(self._resumen(1000), self._resumen(100, validas=2),
                             OBJETIVO, CONFIG)
        self.assertFalse(veredicto['gana'])
        self.assertTrue(any('casos validos' in m for m in veredicto['motivos']))

    def test_no_peor_que_vigente_deja_pasar_el_empate(self):
        objetivo = dict(OBJETIVO, guardias=[
            {'metrica': 'datos', 'agregado': 'media', 'minimo': 1,
             'no_peor_que_vigente': True}])
        igual = comparar(self._resumen(1000, datos=20), self._resumen(500, datos=20),
                         objetivo, CONFIG)
        peor = comparar(self._resumen(1000, datos=20), self._resumen(500, datos=19),
                        objetivo, CONFIG)
        self.assertTrue(igual['gana'])
        self.assertFalse(peor['gana'])

    def test_no_se_gasta_la_reserva_en_un_candidato_que_ya_ha_perdido(self):
        # La primera ronda real gasto seis llamadas midiendo en la reserva un
        # candidato que en el taller era un 18% peor. El resultado ya se sabia.
        self.assertTrue(merece_la_reserva(0.3, 0.1))
        self.assertTrue(merece_la_reserva(0.1, 0.1))
        self.assertFalse(merece_la_reserva(0.05, 0.1))
        self.assertFalse(merece_la_reserva(-0.18, 0.1))
        self.assertFalse(merece_la_reserva(None, 0.1))

    def test_una_guardia_con_tolerancia_admite_un_canje(self):
        # Sin tolerancia, la guardia es binaria y tumba cualquier candidato que
        # mejore una cosa a cambio de empeorar otra un poco.
        objetivo = dict(OBJETIVO, guardias=[
            {'metrica': 'datos', 'agregado': 'media', 'maximo': 99,
             'no_peor_que_vigente': True, 'tolerancia': 0.2}])
        dentro = comparar(self._resumen(1000, datos=10), self._resumen(500, datos=11),
                          objetivo, CONFIG)
        fuera = comparar(self._resumen(1000, datos=10), self._resumen(500, datos=13),
                         objetivo, CONFIG)
        self.assertTrue(dentro['gana'])
        self.assertFalse(fuera['gana'])

    def test_el_resumen_solo_agrega_las_corridas_validas(self):
        lista = [{'id': 'c1'}, {'id': 'c2'}]
        corridas = [corrida(dossier(20), caso='c1'),
                    dict(corrida('', caso='c2'), ok=False, motivo='sin salida')]
        resumen = resumir(corridas, lista, OBJETIVO, CONFIG)
        self.assertEqual(resumen['casos'], 2)
        self.assertEqual(resumen['validas'], 1)
        self.assertEqual(resumen['agregados']['datos'], 20)

    def test_las_repeticiones_no_inflan_el_recuento_de_casos(self):
        # Tres casos corridos cuatro veces son tres casos, no doce: si contaran
        # como doce, el suelo de casos_minimos dejaria de significar nada.
        lista = [{'id': 'c1'}, {'id': 'c2'}]
        corridas = [corrida(dossier(20), caso='c1'), corrida(dossier(20), caso='c1'),
                    corrida(dossier(20), caso='c2'), corrida(dossier(20), caso='c2')]
        resumen = resumir(corridas, lista, OBJETIVO, CONFIG)
        self.assertEqual(resumen['corridas'], 4)
        self.assertEqual(resumen['validas'], 2)


class TopeDeGasto(unittest.TestCase):

    def test_el_tope_se_mira_antes_de_gastar_y_no_despues(self):
        gasto = Gasto(1.0)
        self.assertFalse(gasto.agotado)
        gasto.suma(0.6)
        self.assertFalse(gasto.agotado)
        gasto.suma(0.6)
        self.assertTrue(gasto.agotado)

    def test_lo_que_no_trae_coste_no_suma(self):
        gasto = Gasto(1.0)
        gasto.suma(None)
        self.assertEqual(gasto.total, 0.0)


class Promocion(unittest.TestCase):
    """La promocion escribe un fichero y lo commitea, y eso se prueba de verdad.

    En un repositorio de mentira, creado y tirado aqui mismo: es el unico camino
    del banco que cambia el repositorio, y probarlo solo por la aritmetica que
    lleva delante seria dejar sin red justo lo que la necesita.
    """

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        for orden in (['init', '-q'], ['config', 'user.email', 'banco@pruebas'],
                      ['config', 'user.name', 'banco'], ['commit', '--allow-empty',
                                                         '-q', '-m', 'raiz']):
            subprocess.run(['git', '-C', self.dir] + orden, capture_output=True)
        destino = Path(self.dir, 'agentes')
        destino.mkdir()
        (destino / 'investigador.md').write_text('Prompt vigente.' + SALTO,
                                                 encoding='utf-8')
        subprocess.run(['git', '-C', self.dir, 'add', '-A'], capture_output=True)
        subprocess.run(['git', '-C', self.dir, 'commit', '-q', '-m', 'prompt'],
                       capture_output=True)

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def _log(self):
        return subprocess.run(['git', '-C', self.dir, 'log', '--pretty=%s'],
                              capture_output=True, text=True).stdout

    def test_escribe_el_prompt_y_lo_deja_en_un_commit_propio(self):
        comparacion = {'metrica': 'tokens_rol', 'ganancia': 0.31, 'casos_reserva': 6}
        salida = promover(OBJETIVO, {'nombre': '01', 'texto': 'Prompt nuevo.'},
                          comparacion, 'ronda-de-prueba', raiz=self.dir)
        self.assertTrue(salida['commit'], salida['salida'])
        self.assertEqual(Path(self.dir, 'agentes', 'investigador.md').read_text(
            encoding='utf-8'), 'Prompt nuevo.' + SALTO)
        # El mensaje lleva el numero que gano y la ronda: sin eso, revertir el
        # commit dentro de un mes es adivinar cual fue.
        cabeza = self._log().splitlines()[0]
        self.assertIn('investigador', cabeza)
        self.assertIn('tokens_rol', cabeza)

    def test_el_commit_no_arrastra_nada_mas(self):
        # Si barriera el arbol, revertirlo se llevaria por delante trabajo ajeno.
        Path(self.dir, 'otra-cosa.txt').write_text('a medias', encoding='utf-8')
        promover(OBJETIVO, {'nombre': '01', 'texto': 'Prompt nuevo.'},
                 {'metrica': 'tokens_rol', 'ganancia': 0.2, 'casos_reserva': 6},
                 'ronda', raiz=self.dir)
        tocados = subprocess.run(
            ['git', '-C', self.dir, 'show', '--name-only', '--pretty=', 'HEAD'],
            capture_output=True, text=True).stdout.split()
        self.assertEqual(tocados, ['agentes/investigador.md'])

    def test_el_arbol_sucio_se_ve_antes_de_gastar_nada(self):
        self.assertFalse(arbol_sucio(OBJETIVO, raiz=self.dir))
        Path(self.dir, 'agentes', 'investigador.md').write_text('a medias',
                                                                encoding='utf-8')
        self.assertTrue(arbol_sucio(OBJETIVO, raiz=self.dir))


class Casos(unittest.TestCase):

    def setUp(self):
        self.dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def _casos(self, cuantos):
        return [{'id': 'caso-{:02d}'.format(i), 'entrada': 'x', 'origen': 'prueba'}
                for i in range(cuantos)]

    def test_la_particion_es_mitad_y_mitad_y_no_se_mueve(self):
        casos = self._casos(6)
        una = casos_mod.repartir(casos)
        otra = casos_mod.repartir(list(reversed(casos)))
        self.assertEqual(len(una['taller']), 3)
        self.assertEqual(len(una['reserva']), 3)
        # El orden en que se encontraron los casos no puede cambiar de lado a
        # ninguno: si bailara, el optimizador acabaria viendo la reserva.
        self.assertEqual([c['id'] for c in una['taller']],
                         [c['id'] for c in otra['taller']])

    def test_taller_y_reserva_no_comparten_ni_un_caso(self):
        partes = casos_mod.repartir(self._casos(9))
        self.assertFalse({c['id'] for c in partes['taller']} &
                         {c['id'] for c in partes['reserva']})

    def test_el_espejo_va_y_vuelve_igual(self):
        casos = self._casos(4)
        casos_mod.escribir_espejo('investigador', 'taller', casos, self.dir)
        self.assertEqual(casos_mod.leer_espejo('investigador', 'taller', self.dir), casos)

    def test_sin_espejo_no_hay_casos_y_no_revienta(self):
        self.assertEqual(casos_mod.leer_espejo('escritor', 'reserva', self.dir), [])

    def test_las_semillas_del_objetivo_entran_con_su_marca(self):
        objetivo = {'rol': 'desconocido', 'semillas': [
            {'id': 's1', 'entrada': {'epoca': 'Lisboa, 1755'}}]}
        reunidos = casos_mod.reunir(objetivo)
        self.assertEqual(len(reunidos), 1)
        self.assertEqual(reunidos[0]['origen'], 'semilla')
        self.assertIn('Lisboa', reunidos[0]['entrada'])


class Objetivos(unittest.TestCase):

    def test_los_objetivos_del_repositorio_son_validos(self):
        objetivos = listar_objetivos()
        self.assertTrue(objetivos, 'no hay ningun objetivo definido')
        for objetivo in objetivos:
            cargado = cargar_objetivo(objetivo['id'])
            self.assertIn(cargado['prompt'], cargado['piezas'])
            for pieza in cargado['piezas']:
                self.assertTrue(Path(pieza).is_file(), 'falta la pieza {}'.format(pieza))
            # Contra el registro de metricas y no contra una lista escrita a
            # mano: una lista aparte se queda vieja en cuanto entra una metrica
            # nueva, y entonces el test rechaza objetivos que son correctos.
            self.assertIn(cargado['objetivo']['metrica'], MEDIDAS)
            for guardia in cargado.get('guardias') or []:
                self.assertIn(guardia['metrica'], MEDIDAS)
                self.assertTrue(str(guardia.get('porque') or '').strip(),
                                'la guardia {} de {} no dice por que existe'.format(
                                    guardia['metrica'], cargado['id']))

    def test_un_objetivo_que_no_existe_lo_dice_con_los_que_si(self):
        with self.assertRaises(ErrorBanco) as fallo:
            cargar_objetivo('no-existe')
        self.assertIn('investigador-barato', str(fallo.exception))


class ConfiguracionDelBanco(unittest.TestCase):

    def test_las_claves_del_banco_son_obligatorias(self):
        sin_banco = {k: v for k, v in CONFIG.items() if k != 'autoaprendizaje'}
        with self.assertRaises(ErrorConfig) as fallo:
            validar_config(sin_banco)
        self.assertIn('autoaprendizaje.rondas_max', str(fallo.exception))

    def test_un_margen_de_cero_convertiria_el_ruido_en_promociones(self):
        malo = json.loads(json.dumps(CONFIG))
        malo['autoaprendizaje']['margen_mejora'] = 0
        with self.assertRaises(ErrorConfig):
            validar_config(malo)

    def test_la_paciencia_no_puede_pasarse_de_las_rondas(self):
        malo = json.loads(json.dumps(CONFIG))
        malo['autoaprendizaje']['paciencia'] = 9
        with self.assertRaises(ErrorConfig) as fallo:
            validar_config(malo)
        self.assertIn('paciencia', str(fallo.exception))

    def test_el_perfil_del_banco_de_la_raiz_vale(self):
        with open('config.banco.json', encoding='utf-8') as fichero:
            perfil = json.load(fichero)
        self.assertEqual(validar_config(perfil)['trazas']['entorno'], 'banco')


if __name__ == '__main__':
    unittest.main()
