#!/usr/bin/env node
// CLI del harness. Ningun comando toma decisiones: solo carga config, abre el
// canon y llama al flujo. El estado vive en el canon, nunca aqui (§6, §13).
import { existsSync, readFileSync } from 'node:fs';
import { cargarConfig, ErrorConfig } from '../src/config.mjs';
import { Canon } from '../src/canon.mjs';
import { Agentes, ParadaDelProceso } from '../src/agentes.mjs';
import { generarContexto } from '../src/contexto.mjs';
import { media, notas } from '../src/gate.mjs';
import { listarSkills } from '../src/skills.mjs';
import {
  preparar, escribirCapitulo, cerrar, reanudar, siguienteCapitulo,
} from '../src/flujo.mjs';

const AYUDA = `
novela — sistema multiagente de novelas historicas

  novela init                      crea el canon vacio
  novela brief <fichero.json>      guarda el brief (§3) y deja el proyecto en borrador
  novela preparar                  investigador y arquitecto (§4, tramo de preparacion)
  novela escribir [--capitulo N]   loop de capitulo: escritor, validador, gate, cronista
  novela cerrar                    editor global y retoques.md (§11)
  novela reanudar                  sigue desde donde se quedo, sin argumentos (§13)
  novela estado                    estado del proyecto y de cada capitulo
  novela ver <que> [id]            dossier | personajes | escaleta | resumenes | timeline
                                   | contexto N | capitulo N
  novela poner <que> <fichero>     personaje | capitulo — escritura a mano en el canon
  novela desbloquear --capitulo N [--aprobar-intento K | --reiniciar]
  novela skills                    lista las skills que el harness carga

Opciones globales: --config <ruta> (por defecto config.json)
                   --canon <ruta>  (por defecto canon.db)
`.trim();

function parsear(argv) {
  const posicionales = [];
  const opciones = {};
  for (let i = 0; i < argv.length; i += 1) {
    const a = argv[i];
    if (a.startsWith('--')) {
      const clave = a.slice(2);
      const valor = argv[i + 1] && !argv[i + 1].startsWith('--') ? argv[(i += 1)] : true;
      opciones[clave] = valor;
    } else posicionales.push(a);
  }
  return { posicionales, opciones };
}

const log = (...a) => process.stdout.write(`${a.join(' ')}\n`);

function contarDiario(diario) {
  for (const e of diario) {
    switch (e.tipo) {
      case 'dossier': log(`  dossier: ${e.datos} datos`); break;
      case 'escaleta':
        log(`  escaleta: ${e.capitulos} capitulos, ${e.personajes} personajes`); break;
      case 'recorte': log(`  cap. ${e.capitulo}: contexto recortado (${e.bloques.join(', ')})`); break;
      case 'vd08': log(`  cap. ${e.capitulo} intento ${e.intento}: VD-08 — ${e.detalles.join('; ')}`); break;
      case 'gate':
        log(`  cap. ${e.capitulo} intento ${e.intento}: notas ${e.notas.join('/')}`
          + ` media ${e.media} → ${e.aprueba ? 'aprobado' : `rechazado (${e.motivos.join('; ')})`}`);
        break;
      case 'canon':
        log(`  cap. ${e.capitulo}: canon actualizado`
          + ` (+${e.hilos_abiertos} hilos, -${e.hilos_cerrados}, ${e.eventos} eventos)`);
        break;
      case 'bloqueado': log(`  cap. ${e.capitulo} BLOQUEADO: ${e.motivo}`); break;
      case 'parada': log(`  parada: ${e.motivo}`); break;
      case 'retoques': log(`  ${e.total} retoques en ${e.ruta}`); break;
      default: break;
    }
  }
}

function leerJson(ruta) {
  if (!ruta || !existsSync(ruta)) throw new Error(`no existe el fichero: ${ruta}`);
  return JSON.parse(readFileSync(ruta, 'utf8'));
}

async function main() {
  const { posicionales, opciones } = parsear(process.argv.slice(2));
  const comando = posicionales[0];
  if (!comando || comando === 'ayuda' || opciones.help) { log(AYUDA); return; }

  const config = cargarConfig(opciones.config ?? 'config.json');
  const rutaCanon = opciones.canon ?? 'canon.db';
  const canon = new Canon(rutaCanon);
  const agentes = new Agentes(config);

  try {
    switch (comando) {
      // ---------------------------------------------------------------- F0
      case 'init': {
        log(`canon listo en ${rutaCanon}`);
        log(`modo de ejecucion: ${config.ejecucion.modo}`);
        break;
      }

      case 'brief': {
        const brief = leerJson(posicionales[1]);
        for (const campo of ['epoca', 'premisa', 'tono', 'capitulos', 'palabras_por_capitulo']) {
          if (brief[campo] === undefined) throw new Error(`al brief le falta "${campo}"`);
        }
        const p = canon.guardarBrief(brief);
        log(`brief guardado: ${p.capitulos} capitulos de ${p.palabras_por_capitulo} palabras`);
        log(`estado: ${p.estado}`);
        break;
      }

      case 'poner': {
        const que = posicionales[1];
        const datos = leerJson(posicionales[2]);
        const lista = Array.isArray(datos) ? datos : [datos];
        if (que === 'personaje') { canon.guardarPersonajes(lista); log(`${lista.length} personaje(s)`); }
        else if (que === 'capitulo') { canon.guardarFichas(lista); log(`${lista.length} ficha(s)`); }
        else if (que === 'dato') { canon.guardarDatos(lista); log(`${lista.length} dato(s)`); }
        else throw new Error('poner acepta: personaje | capitulo | dato');
        break;
      }

      case 'ver': {
        const que = posicionales[1];
        const arg = posicionales[2];
        if (que === 'dossier') log(JSON.stringify(canon.datos(), null, 2));
        else if (que === 'personajes') log(JSON.stringify(canon.personajes(), null, 2));
        else if (que === 'escaleta') log(JSON.stringify(canon.fichas(), null, 2));
        else if (que === 'resumenes') log(JSON.stringify(canon.resumenes(), null, 2));
        else if (que === 'timeline') log(JSON.stringify(canon.eventos(), null, 2));
        else if (que === 'hilos') log(JSON.stringify(canon.hilosVivos(), null, 2));
        else if (que === 'contexto') {
          const p = generarContexto(canon, Number(arg), config);
          log(`# paquete de contexto — ${p.tokens} tokens estimados`
            + `${p.recortes.length ? ` (recortado: ${p.recortes.join(', ')})` : ''}\n`);
          log(p.texto);
        } else if (que === 'capitulo') {
          const n = Number(arg);
          log(JSON.stringify({ ficha: canon.ficha(n), intentos: canon.intentos(n) }, null, 2));
        } else throw new Error('ver acepta: dossier | personajes | escaleta | resumenes'
          + ' | timeline | hilos | contexto N | capitulo N');
        break;
      }

      case 'estado': {
        const p = canon.proyecto();
        if (!p) { log('no hay brief todavia'); break; }
        log(`proyecto: ${p.estado}   (${p.epoca})`);
        log(`modo: ${config.ejecucion.modo}   validador: ${config.validador.modo}`);
        const fichas = canon.fichas();
        if (!fichas.length) { log('sin escaleta'); break; }
        for (const f of fichas) {
          const intentos = canon.intentos(f.numero);
          const aprobado = intentos.find((i) => i.estado === 'aprobado');
          const nota = aprobado?.revisiones
            ? ` notas ${notas(aprobado.revisiones).join('/')}`
            + ` media ${media(notas(aprobado.revisiones)).toFixed(2)}`
            : '';
          log(`  ${String(f.numero).padStart(3)}  ${f.estado.padEnd(10)}`
            + ` ${intentos.length} intento(s)${nota}  ${f.titulo}`);
        }
        break;
      }

      // ------------------------------------------------------- F1 a F5
      case 'preparar': {
        const { estado, diario } = await preparar({ canon, agentes, config });
        contarDiario(diario);
        log(`estado: ${estado}`);
        break;
      }

      case 'escribir': {
        const diario = [];
        if (opciones.capitulo) {
          const r = await escribirCapitulo({
            canon, agentes, config, numero: Number(opciones.capitulo), diario,
          });
          contarDiario(diario);
          log(r.aprobado ? 'capitulo aprobado' : `capitulo no aprobado: ${r.motivo}`);
          break;
        }
        let siguiente = siguienteCapitulo(canon);
        if (!siguiente) { log('no quedan capitulos por escribir'); break; }
        while (siguiente) {
          const r = await escribirCapitulo({
            canon, agentes, config, numero: siguiente.numero, diario,
          });
          if (!r.aprobado) break;
          siguiente = siguienteCapitulo(canon);
        }
        contarDiario(diario);
        if (!siguienteCapitulo(canon)) {
          canon.marcarEstado('escrito');
          log('todos los capitulos aprobados: el proyecto pasa a escrito');
        }
        break;
      }

      case 'cerrar': {
        if (canon.estado() !== 'escrito') {
          throw new Error(`el editor global corre con el proyecto en escrito, y esta en`
            + ` ${canon.estado()}`);
        }
        const { retoques, ruta, diario } = await cerrar({ canon, agentes });
        contarDiario(diario);
        log(`${retoques.length} retoques en ${ruta}`);
        break;
      }

      case 'reanudar': {
        const r = await reanudar({ canon, agentes, config });
        contarDiario(r.diario);
        log(`estado: ${r.estado}`);
        break;
      }

      // ------------------------------------- salidas manuales del bloqueo (§8)
      case 'desbloquear': {
        const n = Number(opciones.capitulo);
        if (!n) throw new Error('desbloquear necesita --capitulo N');
        const ficha = canon.ficha(n);
        if (!ficha) throw new Error(`no hay capitulo ${n}`);

        if (opciones['aprobar-intento']) {
          const k = Number(opciones['aprobar-intento']);
          const intento = canon.intentos(n).find((i) => i.intento === k);
          if (!intento) throw new Error(`el capitulo ${n} no tiene intento ${k}`);
          canon.fijarIntentoAprobado(n, k);
          canon.marcarFicha(n, 'aprobado');
          log(`intento ${k} del capitulo ${n} aprobado a mano.`);
          log('Ojo: el cronista no ha corrido, asi que el canon no tiene su resumen.');
          log(`Lanza "novela escribir --capitulo ${n}" si quieres regenerarlo entero.`);
        } else if (opciones.reiniciar) {
          for (const i of canon.intentos(n)) canon.marcarIntento(n, i.intento, 'descartado');
          canon.marcarFicha(n, 'pendiente');
          log(`capitulo ${n} a cero: los intentos quedan como rastro en capitulos/`);
        } else {
          canon.marcarFicha(n, 'pendiente');
          log(`capitulo ${n} desbloqueado, el contador de intentos parte de cero`);
        }
        canon.marcarEstado('escribiendo');
        log('proyecto: escribiendo');
        break;
      }

      case 'skills': {
        for (const s of listarSkills()) {
          log(`  ${s.nombre.padEnd(26)} ${s.meta.description ?? ''}`);
        }
        break;
      }

      default:
        throw new Error(`comando desconocido: ${comando}\n\n${AYUDA}`);
    }
  } finally {
    canon.cerrar();
  }
}

main().catch((e) => {
  if (e instanceof ErrorConfig) {
    process.stderr.write(`\n${e.message}\n\nEl harness para al arrancar: una errata en un umbral`
      + ' sale mas barata descubierta ahora que tres capitulos despues.\n');
  } else if (e instanceof ParadaDelProceso) {
    process.stderr.write(`\nEl proceso para: ${e.message}\n`);
    for (const d of e.detalles) process.stderr.write(`  - ${d}\n`);
    process.stderr.write('\nEl estado queda escrito en el canon. Mira y relanza con "reanudar".\n');
  } else {
    process.stderr.write(`\nerror: ${e.message}\n`);
  }
  process.exitCode = 1;
});
