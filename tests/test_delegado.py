# El camino delegado visto desde la interfaz (§19, §21): el lector del canon en
# ficheros, la auditoria del gate y el arbol de trazas reconstruido.
#
# Sin red y sin coste, como el resto: las trazas se prueban por lo que dicen
# cuando la capa esta apagada y por el recuento del plan, que no manda nada.
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from novela.canon_cc import CanonCC, auditar_gate, operacion
from novela import lanzador
from novela.config import cargar_config, validar_config, ErrorConfig
from novela.servidor import RAIZ_WEB, responder
from novela.trazas_cc import disponibilidad, exportar, plan

BRIEF = {
    'epoca': 'Sevilla, 1587',
    'premisa': 'Un registro falsificado hunde a un cargador de Indias.',
    'tono': 'seco',
    'capitulos': 2,
    'palabras_por_capitulo': 600,
}

ESCALETA = {'capitulos': [
    {'numero': 1, 'titulo': 'El carcelaje', 'acto': 1, 'sinopsis': 'Ines paga el carcelaje.',
     'fecha': '1587-02-11', 'etiquetas': ['carcel'], 'personajes': ['ines-monzon'],
     'objetivo': 'Se cierra la apelacion cara.', 'palabras_objetivo': 600},
    {'numero': 2, 'titulo': 'Cuentas de hornada', 'acto': 1, 'sinopsis': 'Cuentan botijas.',
     'fecha': '1587-03-04', 'etiquetas': ['triana'], 'personajes': ['ines-monzon'],
     'objetivo': 'La cifra del registro es imposible.', 'palabras_objetivo': 600},
]}

# El capitulo 1 lo aprobo el segundo intento; el 2 esta pendiente. El intento
# descartado guarda sus notas y sus motivos, que es lo que §21 obliga a guardar.
ESTADO = {
    'estado': 'escribiendo',
    'actualizado': '2026-09-17T10:35:00',
    'capitulos': {
        '1': {
            'estado': 'aprobado', 'intento_aprobado': 2,
            'intentos': [
                {'intento': 1, 'estado': 'descartado',
                 'ruta': 'novela-cc/capitulos/cap-01-intento-1.md',
                 'palabras': 580, 'parrafos': 20, 'vd08': 'ok',
                 'notas': {'continuidad': 1, 'anacronismos': 5, 'logica_ritmo': 4},
                 'minima': 1, 'media': 3.33, 'graves': 1, 'aprueba': False,
                 'motivos': ['nota minima 1 por debajo de 3']},
                {'intento': 2, 'estado': 'aprobado',
                 'ruta': 'novela-cc/capitulos/cap-01-intento-2.md',
                 'palabras': 612, 'parrafos': 22, 'vd08': 'ok',
                 'notas': {'continuidad': 4, 'anacronismos': 5, 'logica_ritmo': 4},
                 'minima': 4, 'media': 4.33, 'graves': 0, 'aprueba': True,
                 'motivos': [], 'tipo_reintento': 'quirurgico'},
            ],
            'contexto': {'tokens': 1800, 'recortes': []},
        },
        '2': {'estado': 'pendiente', 'intento_aprobado': None, 'intentos': []},
    },
}

RESUMEN = {
    'capitulo': 1, 'intento_aprobado': 2, 'resumen': 'Ines lee la sentencia.',
    'hilos_abiertos': ['el registro asienta botijas de mas'], 'hilos_cerrados': [],
    'personajes_presentes': ['ines-monzon'],
    'cambios_personaje': [{'id': 'ines-monzon', 'ubicacion': 'Sevilla', 'sabe': []}],
    'eventos': [{'id': 'evento-cap-1-1', 'tipo': 'trama', 'fecha': '1587-02-11',
                 'descripcion': 'Ines visita a su padre.', 'capitulo': 1,
                 'personajes': ['ines-monzon']}],
}


def _escribir(ruta, valor):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(valor, str):
        ruta.write_text(valor, encoding='utf-8')
    else:
        ruta.write_text(json.dumps(valor, indent=2, ensure_ascii=False), encoding='utf-8')


class CanonDelegadoDePrueba(unittest.TestCase):
    """Un `novela-cc/` de juguete en su propio directorio.

    El lector resuelve las rutas del canon desde el cwd, igual que el
    orquestador las escribe, asi que cada test necesita su carpeta.
    """

    def setUp(self):
        self.cwd = os.getcwd()
        self.config = cargar_config(str(Path(self.cwd) / 'config.json'))
        self.config = {**self.config, 'trazas': {**self.config['trazas'], 'activas': False}}
        self.dir = tempfile.mkdtemp(prefix='novela-cc-')
        os.chdir(self.dir)
        raiz = Path(self.dir) / 'novela-cc'
        _escribir(raiz / 'canon' / 'brief.json', BRIEF)
        _escribir(raiz / 'canon' / 'estado.json', ESTADO)
        _escribir(raiz / 'canon' / 'escaleta.json', ESCALETA)
        _escribir(raiz / 'canon' / 'dossier.json', {'datos': [
            {'id': 'dato-1', 'categoria': 'comida', 'dato': 'Bizcocho de flota.',
             'fuente': 'modelo', 'estado': 'sin_verificar', 'etiquetas': ['comida']}]})
        _escribir(raiz / 'canon' / 'personajes.json', {'personajes': [
            {'id': 'ines-monzon', 'nombre': 'Ines de Monzon', 'rol': 'protagonista'}]})
        _escribir(raiz / 'canon' / 'hilos.json', {'hilos': [
            {'hilo': 'el registro asienta botijas de mas', 'capitulo': 1, 'cerrado_en': None},
            {'hilo': 'quien firmo el folio', 'capitulo': 1, 'cerrado_en': 2}]})
        _escribir(raiz / 'canon' / 'timeline.json', {'eventos': RESUMEN['eventos']})
        _escribir(raiz / 'canon' / 'resumenes' / 'cap-01.json', RESUMEN)
        _escribir(raiz / 'contexto' / 'cap-01.md', '# Encargo del capitulo 1\n\nObjetivo.')
        _escribir(raiz / 'capitulos' / 'cap-01-intento-1.md', '# El carcelaje\n\nPrimera.')
        _escribir(raiz / 'capitulos' / 'cap-01-intento-2.md', '# El carcelaje\n\nSegunda.')

    def tearDown(self):
        os.chdir(self.cwd)
        shutil.rmtree(self.dir, ignore_errors=True)

    def pedir(self, metodo, ruta, cuerpo=None):
        datos = json.dumps(cuerpo).encode('utf-8') if cuerpo is not None else b''
        codigo, _, salida = responder(metodo, ruta, datos, self.config, RAIZ_WEB)
        return codigo, json.loads(salida)


class TestLector(CanonDelegadoDePrueba):
    def test_lee_el_estado_y_la_escaleta(self):
        canon = CanonCC()
        self.assertTrue(canon.existe)
        self.assertEqual(canon.estado(), 'escribiendo')
        self.assertEqual(canon.actualizado(), '2026-09-17T10:35:00')
        self.assertEqual([c['numero'] for c in canon.escaleta()], [1, 2])
        self.assertEqual(canon.ficha_estado(1)['estado'], 'aprobado')
        self.assertEqual(canon.ficha_estado(2)['intentos'], [])

    def test_el_texto_es_el_del_intento_aprobado_y_no_el_ultimo(self):
        texto, ruta = CanonCC().texto(1)
        self.assertIn('Segunda', texto)
        self.assertTrue(ruta.endswith('cap-01-intento-2.md'))

    def test_tambien_se_lee_el_texto_de_un_intento_descartado(self):
        # El que el gate tumbo es justo el que hace falta para saber si el
        # validador se indulta a si mismo (§20), y `texto()` no llega a el.
        canon = CanonCC()
        descartado = canon.intentos(1)[0]
        texto, ruta = canon.texto_de_intento(descartado)
        self.assertIn('Primera', texto)
        self.assertTrue(ruta.endswith('cap-01-intento-1.md'))

    def test_un_intento_cuyo_fichero_no_esta_se_lee_como_hueco(self):
        Path('novela-cc/capitulos/cap-01-intento-1.md').unlink()
        texto, ruta = CanonCC().texto_de_intento(CanonCC().intentos(1)[0])
        self.assertIsNone(texto)
        self.assertTrue(ruta.endswith('cap-01-intento-1.md'))

    def test_un_fichero_que_falta_no_tumba_la_lectura(self):
        Path('novela-cc/canon/dossier.json').unlink()
        self.assertEqual(CanonCC().datos(), [])

    def test_un_json_roto_se_lee_como_hueco(self):
        Path('novela-cc/canon/hilos.json').write_text('{roto', encoding='utf-8')
        self.assertEqual(CanonCC().hilos_vivos(), [])

    def test_los_hilos_vivos_son_los_que_nadie_cerro(self):
        vivos = CanonCC().hilos_vivos()
        self.assertEqual(len(vivos), 1)
        self.assertIsNone(vivos[0]['cerrado_en'])

    def test_no_escribe_nada_en_el_canon(self):
        antes = {p: p.read_bytes() for p in Path('novela-cc').rglob('*') if p.is_file()}
        canon = CanonCC()
        canon.estado(); canon.escaleta(); canon.resumenes(); canon.texto(1); canon.contexto(1)
        despues = {p: p.read_bytes() for p in Path('novela-cc').rglob('*') if p.is_file()}
        self.assertEqual(antes, despues)


class TestAuditoriaDelGate(CanonDelegadoDePrueba):
    """§21 dice que la suma del gate la hace un modelo y que ese es el punto mas
    debil del camino. Esto comprueba que la interfaz lo vigila.
    """

    def test_la_cuenta_rehecha_coincide_con_la_del_canon(self):
        for intento in CanonCC().intentos(1):
            cuenta = auditar_gate(intento, self.config['gate'])
            self.assertTrue(cuenta['cuadra'], intento)

    def test_un_veredicto_que_no_sale_de_la_formula_se_delata(self):
        # El orquestador da por aprobado un intento con una nota por debajo del
        # minimo: el canon manda, pero la discrepancia tiene que verse.
        estado = json.loads(Path('novela-cc/canon/estado.json').read_text(encoding='utf-8'))
        estado['capitulos']['1']['intentos'][0]['aprueba'] = True
        _escribir(Path('novela-cc/canon/estado.json'), estado)

        cuenta = auditar_gate(CanonCC().intentos(1)[0], self.config['gate'])
        self.assertFalse(cuenta['cuadra'])
        self.assertFalse(cuenta['aprueba'])
        self.assertTrue(cuenta['aprueba_canon'])

        _, cuerpo = self.pedir('GET', '/api/proyecto')
        self.assertEqual(len(cuerpo['auditoria']['discrepancias']), 1)
        self.assertEqual(cuerpo['auditoria']['discrepancias'][0]['capitulo'], 1)

    def test_la_operacion_se_imprime_entera(self):
        intento = CanonCC().intentos(1)[0]
        texto = operacion(intento, self.config['gate'])
        for trozo in ('min(1/5/4)', 'media 3.33', '1 grave(s)', 'rechaza'):
            self.assertIn(trozo, texto)

    def test_un_intento_sin_notas_no_tiene_gate_que_auditar(self):
        self.assertIsNone(auditar_gate({'intento': 1, 'vd08': 'bloqueo'},
                                       self.config['gate']))


class TestApiDelegada(CanonDelegadoDePrueba):
    def test_el_proyecto_sale_del_canon_en_ficheros(self):
        codigo, cuerpo = self.pedir('GET', '/api/proyecto')
        self.assertEqual(codigo, 200)
        self.assertEqual(cuerpo['orquestador'], 'Claude Code')
        self.assertEqual(cuerpo['estado'], 'escribiendo')
        self.assertEqual(len(cuerpo['capitulos']), 2)
        self.assertEqual(cuerpo['capitulos'][0]['notas'], [4, 5, 4])
        self.assertEqual(cuerpo['capitulos'][0]['media'], 4.33)
        self.assertEqual(cuerpo['capitulos'][0]['contexto_tokens'], 1800)
        self.assertFalse(cuerpo['capitulos'][1]['legible'])
        self.assertEqual(len(cuerpo['cronologia']), 1)
        self.assertEqual(len(cuerpo['reparto']), 1)

    def test_el_capitulo_aprobado_trae_texto_resumen_e_hilos(self):
        codigo, cuerpo = self.pedir('GET', '/api/capitulo/1')
        self.assertEqual(codigo, 200)
        self.assertIn('Segunda', cuerpo['texto'])
        self.assertEqual(cuerpo['intento'], 2)
        self.assertEqual(cuerpo['resumen'], 'Ines lee la sentencia.')
        self.assertEqual(cuerpo['hilos_abiertos'], RESUMEN['hilos_abiertos'])

    def test_un_capitulo_sin_aprobar_no_se_lee(self):
        self.assertEqual(self.pedir('GET', '/api/capitulo/2')[0], 409)

    def test_el_paquete_guardado_es_el_que_se_uso(self):
        codigo, cuerpo = self.pedir('GET', '/api/contexto/1')
        self.assertEqual(codigo, 200)
        self.assertEqual(cuerpo['origen'], 'guardado')
        self.assertIn('Encargo del capitulo 1', cuerpo['texto'])

    def test_sin_paquete_guardado_se_dice_y_no_se_regenera(self):
        self.assertEqual(self.pedir('GET', '/api/contexto/2')[0], 404)

    def test_la_interfaz_no_escribe_en_el_canon(self):
        # En este canon escribe el orquestador y nadie mas (§21). Las rutas que
        # escribian ya no existen, y las que quedan solo leen: contra
        # la API, cualquier metodo que no sea GET se contesta con el porque.
        for ruta in ('/api/brief', '/api/flujo', '/api/desbloquear'):
            codigo, cuerpo = self.pedir('POST', ruta, BRIEF)
            self.assertEqual(codigo, 409)
            self.assertIn('orquestar-novela', cuerpo['error'])

    def test_lanzar_sin_los_cinco_campos_no_arranca_nada(self):
        # La comprobacion de verdad la hacen los VD-xx en el orquestador; esta
        # solo evita gastar una sesion entera en un brief a medias (§3).
        codigo, cuerpo = self.pedir('POST', '/api/lanzar', {'epoca': 'Sevilla, 1587'})
        self.assertEqual(codigo, 409)
        for campo in ('premisa', 'tono', 'capitulos', 'palabras_por_capitulo'):
            self.assertIn(campo, cuerpo['error'])

    def test_lanzar_con_un_numero_que_no_es_numero_no_arranca_nada(self):
        codigo, cuerpo = self.pedir('POST', '/api/lanzar', {**BRIEF, 'capitulos': 'seis'})
        self.assertEqual(codigo, 409)
        self.assertIn('capitulos', cuerpo['error'])

    def test_sin_lanzamiento_el_estado_lo_dice(self):
        codigo, cuerpo = self.pedir('GET', '/api/lanzar')
        self.assertEqual(codigo, 200)
        self.assertFalse(cuerpo['corriendo'])

    def test_el_prompt_lleva_la_skill_y_los_cinco_campos(self):
        # Va como un solo argumento y nunca por un shell, asi que lo que se
        # teclee en la pagina no puede convertirse en otra orden.
        texto = lanzador.prompt(lanzador.validar(BRIEF))
        self.assertTrue(texto.startswith('/orquestar-novela'))
        for campo in lanzador.CAMPOS:
            self.assertIn(campo + ':', texto)

    def test_la_raiz_sirve_la_pagina(self):
        codigo, _, salida = responder('GET', '/', b'', self.config, RAIZ_WEB)
        self.assertEqual(codigo, 200)
        self.assertIn(b'<!doctype html>', salida[:64].lower())

    def test_no_se_sale_de_web(self):
        codigo, _, _ = responder(
            'GET', '/../config.json', b'', self.config, RAIZ_WEB)
        self.assertEqual(codigo, 404)

    def test_una_ruta_de_api_desconocida_es_404(self):
        self.assertEqual(self.pedir('GET', '/api/inventada')[0], 404)

    def test_la_pagina_no_acepta_otros_metodos(self):
        codigo, _, _ = responder('POST', '/', b'', self.config, RAIZ_WEB)
        self.assertEqual(codigo, 405)


class TestTrazasDelegadas(CanonDelegadoDePrueba):
    def test_el_plan_cuenta_lo_que_saldria_sin_mandar_nada(self):
        resumen = plan(CanonCC(), self.config)
        self.assertTrue(resumen['preparar'])
        self.assertEqual(resumen['capitulos'], 1)
        self.assertEqual(resumen['intentos'], 2)
        # Tres notas, media y veredicto por intento puntuado, mas los intentos
        # que costo el capitulo.
        self.assertEqual(resumen['notas'], 2 * 5 + 1)
        self.assertFalse(resumen['cerrar'])
        self.assertTrue(resumen['reconstruido'])
        self.assertTrue(resumen['sesion'].startswith('novela-'))

    def test_la_sesion_sale_del_brief_y_no_de_ningun_id(self):
        # El canon no guarda ningun id de proyecto -es fila unica-, asi que la
        # sesion se deriva del brief: misma novela, misma sesion (§20).
        from novela.trazas import sesion_de
        self.assertEqual(plan(CanonCC(), self.config)['sesion'], sesion_de(BRIEF))

    def test_con_las_trazas_apagadas_no_se_manda_y_se_dice_por_que(self):
        resultado = exportar(self.config)
        self.assertFalse(resultado['enviado'])
        self.assertIn('activas', resultado['motivo'])
        self.assertEqual(resultado['plan']['intentos'], 2)

    def test_sin_canon_delegado_no_hay_nada_que_reconstruir(self):
        shutil.rmtree('novela-cc')
        resultado = exportar(self.config)
        self.assertFalse(resultado['enviado'])
        self.assertIn('no hay canon', resultado['motivo'])

    def test_la_disponibilidad_no_construye_cliente_y_da_el_motivo(self):
        self.assertEqual(disponibilidad(self.config),
                         {'lista': False,
                          'motivo': 'trazas.activas esta a false en el perfil'})

    def test_el_panel_de_trazas_ensena_el_plan(self):
        codigo, cuerpo = self.pedir('GET', '/api/trazas')
        self.assertEqual(codigo, 200)
        self.assertTrue(cuerpo['reconstruido'])
        self.assertFalse(cuerpo['activas'])
        self.assertEqual(cuerpo['plan']['capitulos'], 1)

class CapaDeMentira:
    """Una capa de §20 que apunta en una lista en vez de hablar con Langfuse.

    Sirve para recorrer el arbol entero sin red: lo que se comprueba es la forma
    -que raices cuelgan de que, y que puntuaciones salen-, que es justo lo que
    un fallo de reconstruccion rompe y el modo apagado no llega a ejercitar.
    """

    def __init__(self, *_, **__):
        self.activa = True
        self.motivo = None
        self.arbol = []
        self.notas = []
        self.cerrada = False
        self._pila = []

    def _abrir(self, nombre, tipo, metadata, entrada=None):
        capa = self
        padre = capa._pila[-1] if capa._pila else None
        nodo = {'nombre': nombre, 'tipo': tipo, 'padre': padre,
                'metadata': metadata or {}, 'entrada': entrada, 'output': None}

        class Obs:
            # La entrada y la salida se apuntan porque son lo unico que un
            # evaluador de Langfuse puede leer (§20): si el capitulo no esta
            # ahi, el juez no tiene nada que puntuar y la traza no se entera.
            def actualizar(self, output=None, **_):
                if output is not None:
                    nodo['output'] = output

            def nota(self, nombre_nota, valor, comentario=None, tipo=None):
                capa.notas.append((nombre, nombre_nota, valor))

        class Contexto:
            def __enter__(self):
                capa.arbol.append(nodo)
                capa._pila.append(nombre)
                return Obs()

            def __exit__(self, *_):
                capa._pila.pop()
                return False

        return Contexto()

    def traza(self, nombre, entrada=None, sesion=None, etiquetas=None, metadata=None,
              tipo='span', trace_id=None, nombre_traza=None):
        # La firma sigue a la de la capa de verdad, incluidos los tres
        # argumentos que usa el camino delegado para que el hook y la
        # reconstruccion caigan en la misma traza (§21).
        self.sesion = sesion
        self.etiquetas = etiquetas
        self.trazas_pedidas = getattr(self, 'trazas_pedidas', [])
        self.trazas_pedidas.append((nombre, trace_id))
        return self._abrir(nombre, tipo, metadata, entrada)

    def paso(self, nombre, tipo='span', entrada=None, metadata=None, modelo=None,
             parametros=None):
        return self._abrir(nombre, tipo, metadata, entrada)

    def cerrar(self):
        self.cerrada = True


class TestArbolDeTrazas(CanonDelegadoDePrueba):
    """El arbol de §20 reconstruido, recorrido entero contra la capa de mentira."""

    def setUp(self):
        super().setUp()
        import novela.trazas_cc as modulo
        self.modulo = modulo
        self.capa = CapaDeMentira()
        self.original = modulo.Trazas
        modulo.Trazas = lambda *a, **k: self.capa

    def tearDown(self):
        self.modulo.Trazas = self.original
        super().tearDown()

    def correr(self):
        return exportar(self.config)

    def nombres(self, tipo=None):
        return [o['nombre'] for o in self.capa.arbol if tipo is None or o['tipo'] == tipo]

    def test_las_raices_son_las_tres_de_la_seccion_20(self):
        resultado = self.correr()
        self.assertTrue(resultado['enviado'])
        raices = [o['nombre'] for o in self.capa.arbol if o['padre'] is None]
        # Un capitulo escrito y ningun retoque: preparar y una traza de capitulo.
        self.assertEqual(raices, ['preparar-novela', 'escribir-capitulo'])
        self.assertEqual(resultado['trazas'], 2)

    def test_cada_rol_de_la_seccion_5_tiene_su_paso(self):
        self.correr()
        agentes = self.nombres('agent')
        self.assertEqual(agentes.count('investigador'), 1)
        self.assertEqual(agentes.count('arquitecto'), 1)
        # Dos intentos, un escritor por intento.
        self.assertEqual(agentes.count('escritor'), 2)
        # Tres validadores por intento puntuado, y los dos lo estan.
        self.assertEqual(agentes.count('validador'), 6)
        self.assertEqual(agentes.count('cronista'), 1)

    def test_el_contexto_es_un_retriever_y_el_gate_un_evaluator(self):
        self.correr()
        self.assertEqual(self.nombres('retriever'), ['reunir-contexto'])
        self.assertEqual(self.nombres('evaluator'),
                         ['vd-08-extension', 'gate', 'vd-08-extension', 'gate'])

    def test_los_nombres_no_llevan_numeros_dentro(self):
        # §20: los nombres se tratan como una API; el capitulo y el intento van
        # en metadatos, porque un nombre distinto por ejecucion no se agrupa.
        self.correr()
        for observacion in self.capa.arbol:
            # `vd-08-extension` es el nombre fijo de un validador de §9, no un
            # numero de ejecucion: es el mismo en todas y agrupa igual.
            if observacion['nombre'] == 'vd-08-extension':
                continue
            self.assertNotRegex(observacion['nombre'], r'\d',
                                observacion['nombre'])

    def test_el_capitulo_y_el_intento_viajan_en_metadatos(self):
        self.correr()
        gates = [o for o in self.capa.arbol if o['nombre'] == 'gate']
        self.assertEqual([g['metadata']['capitulo'] for g in gates], [1, 1])
        self.assertEqual([g['metadata']['intento'] for g in gates], [1, 2])
        self.assertTrue(all(g['metadata']['reconstruido'] for g in gates))

    def test_las_notas_del_gate_salen_como_puntuaciones(self):
        self.correr()
        del_gate = [(n, v) for origen, n, v in self.capa.notas if origen == 'gate']
        self.assertIn(('continuidad', 1), del_gate)
        self.assertIn(('media', 3.33), del_gate)
        self.assertIn(('aprueba', False), del_gate)
        self.assertIn(('aprueba', True), del_gate)
        # Los intentos que costo el capitulo van sobre la traza, no sobre el gate.
        self.assertIn(('escribir-capitulo', 'intentos', 2), self.capa.notas)

    def test_un_gate_que_no_cuadra_deja_su_propia_puntuacion(self):
        estado = json.loads(Path('novela-cc/canon/estado.json').read_text(encoding='utf-8'))
        estado['capitulos']['1']['intentos'][0]['aprueba'] = True
        _escribir(Path('novela-cc/canon/estado.json'), estado)
        self.correr()
        self.assertIn(('gate', 'gate-cuadra', False), self.capa.notas)

    def test_la_etiqueta_dice_que_esto_es_reconstruido(self):
        self.correr()
        self.assertEqual(tuple(self.capa.etiquetas), ('delegado', 'reconstruido'))

    def test_el_buzon_se_vacia_aunque_algo_falle(self):
        self.correr()
        self.assertTrue(self.capa.cerrada)

    def escritores(self):
        return [o for o in self.capa.arbol if o['nombre'] == 'escritor']

    def test_el_escritor_lleva_el_paquete_que_recibio_y_el_capitulo_que_escribio(self):
        # Sin las dos cosas en la misma observacion no hay evaluador posible:
        # un juez de Langfuse lee el input, el output y la metadata de la
        # observacion a la que apunta, y no abre ficheros ni mira a sus hermanas.
        self.correr()
        primero, segundo = self.escritores()
        self.assertIn('Encargo del capitulo 1', primero['entrada']['paquete'])
        self.assertIn('Primera', primero['output']['texto'])
        # Tambien el descartado: es la mitad de la comparacion que interesa.
        self.assertIn('Segunda', segundo['output']['texto'])

    def test_con_trazas_texto_apagada_la_novela_no_sale_de_casa(self):
        self.config = {**self.config,
                       'trazas': {**self.config['trazas'], 'texto': False}}
        self.correr()
        for observacion in self.escritores():
            self.assertNotIn('paquete', observacion['entrada'])
            self.assertNotIn('texto', observacion['output'])
        # Y el arbol sigue entero: lo que se apaga es el texto, no las trazas.
        self.assertEqual(len(self.escritores()), 2)

    def test_el_plan_dice_cuantas_palabras_saldrian(self):
        # Exportar deja marca fuera, y con el texto puesto lo que sale es la
        # novela: el panel de §19 lo ensena antes de que nadie pulse nada.
        con = plan(CanonCC(), self.config)
        self.assertTrue(con['texto'])
        # Seis palabras del paquete del capitulo 1 y cuatro de cada intento.
        self.assertEqual(con['palabras_fuera'], 14)
        sin = plan(CanonCC(), {**self.config,
                               'trazas': {**self.config['trazas'], 'texto': False}})
        self.assertFalse(sin['texto'])
        self.assertEqual(sin['palabras_fuera'], 0)


class TestClavesDeConfig(unittest.TestCase):
    """Los umbrales de §12 se validan enteros al arrancar, y las claves que se
    unicas que hay son las que alguien lee."""

    def setUp(self):
        self.base = cargar_config('config.json')

    def test_el_perfil_del_repositorio_vale(self):
        self.assertEqual(
            sorted(self.base),
            ['contexto', 'gate', 'interfaz', 'lanzador', 'margenes', 'trazas'])

    def test_un_modo_de_permiso_inventado_no_arranca(self):
        with self.assertRaisesRegex(ErrorConfig, 'lanzador.permisos'):
            validar_config({**self.base,
                            'lanzador': {**self.base['lanzador'], 'permisos': 'a saco'}})

    def test_un_umbral_fuera_de_rango_no_arranca(self):
        with self.assertRaisesRegex(ErrorConfig, 'gate.nota_minima'):
            validar_config({**self.base, 'gate': {**self.base['gate'], 'nota_minima': 9}})

    def test_sin_una_clave_no_arranca(self):
        with self.assertRaisesRegex(ErrorConfig, 'interfaz.puerto'):
            validar_config({**self.base, 'interfaz': {}})


if __name__ == '__main__':
    unittest.main()
