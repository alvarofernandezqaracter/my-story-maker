// §12 Modo de ejecucion simulado. Capa local que resuelve las llamadas a
// agentes devolviendo respuestas fijas con el formato correcto. El resto del
// harness no sabe cual de los dos modos esta activo, asi que los tests y las
// demostraciones corren sin red y sin coste por el mismo camino que la
// ejecucion de verdad.
//
// Nada de lo que hay aqui es prosa que valga: es relleno con la forma exacta
// que los validadores de §9 y el gate de §8 esperan.
import { DIMENSIONES } from './esquemas.mjs';

export function slug(texto) {
  return String(texto).normalize('NFD').replace(/[̀-ͯ]/g, '')
    .toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 40);
}

function anyoDe(epoca) {
  const m = String(epoca).match(/\b(\d{3,4})\b/);
  return m ? Number(m[1]) : 1600;
}

function fechaDeCapitulo(epoca, numero) {
  const base = anyoDe(epoca);
  const mes = ((numero - 1) % 12) + 1;
  const anyo = base + Math.floor((numero - 1) / 12);
  return `${anyo}-${String(mes).padStart(2, '0')}`;
}

// ---- inyeccion de fallos, para poder demostrar el gate y VD-08 sin tocar codigo
// Formato: "capitulo:intento,capitulo:intento". Solo tiene efecto en simulado.
function inyectado(variable, capitulo, intento) {
  const bruto = process.env[variable];
  if (!bruto) return false;
  return bruto.split(',').map((p) => p.trim()).includes(`${capitulo}:${intento}`);
}

// --------------------------------------------------------------- investigador

const CATEGORIAS = ['vestimenta', 'politica', 'comida', 'lenguaje'];

const PLANTILLA_DATO = {
  vestimenta: 'Se lleva %s de pano basto, sin tintes caros, y el calzado se remienda antes que cambiarse.',
  politica: 'Las ordenanzas locales las aplica %s, que cobra por licencia y no por justicia.',
  comida: 'Se come %s a media manana y la carne aparece solo en dias senalados.',
  lenguaje: 'Se trata de vuesa merced a quien tiene cargo y se tutea al aprendiz; %s es insulto serio.',
};

const RELLENO = {
  vestimenta: ['sayo pardo', 'jubon remendado', 'capa corta'],
  politica: ['el veinticuatro del cabildo', 'el alguacil mayor', 'el juez de la aduana'],
  comida: ['pan de centeno con aceite', 'sopa de ajo', 'sardina en salazon'],
  lenguaje: ['llamar a alguien converso', 'mentar el oficio del padre', 'nombrar la carcel'],
};

export function investigador(entrada) {
  const { brief } = entrada;
  const datos = [];
  for (const categoria of CATEGORIAS) {
    for (let i = 1; i <= 3; i += 1) {
      // Por indice y no por hash: tres datos por categoria, tres rellenos
      // distintos, sin duplicados en el dossier.
      const relleno = RELLENO[categoria][(i - 1) % RELLENO[categoria].length];
      // Sin busqueda web (§12, F6) el investigador no puede marcar verificado
      // nada que solo recuerde: alterna sin_verificar e inventado.
      const estado = i === 3 ? 'inventado' : 'sin_verificar';
      datos.push({
        id: `dato-${categoria}-${i}`,
        categoria,
        dato: PLANTILLA_DATO[categoria].replace('%s', relleno),
        fuente: 'modelo',
        estado,
        etiquetas: [categoria, slug(brief.epoca).split('-')[0] || 'epoca', `${categoria}-${i}`],
      });
    }
  }
  return { datos };
}

// ------------------------------------------------------------------ arquitecto

const REPARTO = [
  { nombre: 'Ines de Arteaga', rol: 'protagonista',
    voz: 'Frases cortas y secas. Usa terminos de oficio con naturalidad. Nunca jura en voz alta.',
    motivacion: 'Recuperar el nombre de su padre, condenado sin juicio.',
    arco: 'De obedecer las reglas del gremio a romperlas a sabiendas.',
    ubicacion: 'en la casa familiar' },
  { nombre: 'Martin Coloma', rol: 'secundario',
    voz: 'Habla de mas cuando esta nervioso y se corrige a media frase.',
    motivacion: 'Conservar el puesto que le costo diez anos conseguir.',
    arco: 'De comodo a comprometido, tarde y a su pesar.',
    ubicacion: 'en la oficina del cabildo' },
  { nombre: 'Dona Ursula Pardo', rol: 'secundario',
    voz: 'Cortesia impecable usada como arma. Nunca levanta la voz.',
    motivacion: 'Que el asunto se cierre antes de que llegue a oidos de la corte.',
    arco: 'De arbitro neutral a parte interesada.',
    ubicacion: 'en su casa de la plaza' },
  { nombre: 'El escribano Lucas', rol: 'figurante',
    voz: 'Habla en formulas de registro incluso fuera del oficio.',
    motivacion: 'Cobrar sus derechos sin meterse en nada.',
    arco: 'Sigue igual al final que al principio, y eso importa.',
    ubicacion: 'en la escribania' },
];

export function arquitecto(entrada) {
  const { brief, dossier } = entrada;
  const personajes = REPARTO.map((p) => ({ ...p, id: slug(p.nombre), sabe: [] }));
  const etiquetasDisponibles = [...new Set((dossier ?? []).flatMap((d) => d.etiquetas))];
  const total = brief.capitulos;
  const capitulos = [];

  for (let n = 1; n <= total; n += 1) {
    const acto = n <= Math.ceil(total * 0.25) ? 1 : n <= Math.ceil(total * 0.75) ? 2 : 3;
    const reparto = personajes
      .filter((_, i) => i === 0 || (n + i) % 3 !== 0)
      .map((p) => p.id);
    const etiquetas = etiquetasDisponibles.length
      ? [CATEGORIAS[(n - 1) % CATEGORIAS.length],
        etiquetasDisponibles[(n * 2) % etiquetasDisponibles.length]]
      : [CATEGORIAS[(n - 1) % CATEGORIAS.length]];
    capitulos.push({
      numero: n,
      titulo: `Capitulo ${n}`,
      acto,
      sinopsis: `Inés de Arteaga da un paso mas en el asunto que abre la novela.`
        + ` El acto ${acto} exige que algo se cierre y algo quede abierto,`
        + ` y aqui le toca a la pieza ${n} de ${total}.`,
      fecha: fechaDeCapitulo(brief.epoca, n),
      personajes: [...new Set(reparto)],
      etiquetas: [...new Set(etiquetas)],
      objetivo: `Al acabar el capitulo ${n}, la protagonista sabe una cosa que al empezar ignoraba`
        + ` y ha perdido una opcion que tenia.`,
      palabras_objetivo: brief.palabras_por_capitulo,
    });
  }
  return { personajes, capitulos };
}

// -------------------------------------------------------------------- escritor

const PARRAFOS = [
  'La manana entro por el postigo con el olor de siempre, a cuerda mojada y a ceniza fria. %NOMBRE% no se movio de la silla hasta que el ruido de la calle tuvo la forma que esperaba.',
  'Habia aprendido a contar los pasos ajenos. Dos cortos y uno largo era el aguacil; tres iguales, cualquiera con prisa y sin cargo. Los de aquella manana no eran ninguno de los dos.',
  'Lo que dijeron despues no le sorprendio tanto como la manera de decirlo, con las manos quietas y la mirada en el suelo, como quien repite algo aprendido la noche anterior.',
  'Salio sin cerrar del todo. En la esquina el mercado ya estaba montado y el precio del pan seguia clavado donde el cabildo lo habia dejado, que era lo unico que en aquel ano no se movia.',
  'Penso en su padre y aparto el pensamiento con el mismo gesto con que se aparta una mosca: sin rabia, porque la rabia cansa, y ella necesitaba el dia entero.',
  'El papel estaba doblado en cuatro y tenia una mancha en el borde. No hizo falta leerlo dos veces; hizo falta decidir si convenia haberlo leido, que es otra cosa.',
  'Al volver, la casa estaba como la habia dejado salvo en un detalle, y el detalle era el que importaba. Se quedo un rato largo mirandolo antes de tocar nada.',
  'Por la noche escribio dos lineas y quemo la primera. La segunda la dejo encima de la mesa, donde cualquiera que entrase iba a verla, que era exactamente lo que buscaba.',
];

export function escritor(entrada) {
  const { encargo: ficha, personajes = [], incidencias = [], texto_previo = null } = entrada;
  const nombre = personajes[0]?.nombre ?? 'La protagonista';
  const intento = entrada.intento ?? 1;

  // Gancho de simulacion: un capitulo deliberadamente corto para ejercitar VD-08.
  if (inyectado('NOVELA_SIM_CORTOS', ficha.numero, intento)) {
    return {
      texto: `# ${ficha.titulo}\n\nUn parrafo y nada mas, que es justo lo que VD-08 tiene que cazar.`,
      faltantes: [],
    };
  }

  const objetivo = ficha.palabras_objetivo;
  const cuerpo = [];
  let palabras = 0;
  let i = 0;
  while (palabras < objetivo - 12) {
    const base = PARRAFOS[i % PARRAFOS.length].replace('%NOMBRE%', nombre);
    const parrafo = i < PARRAFOS.length ? base : `${base} (${ficha.titulo}, hilo ${i})`;
    cuerpo.push(parrafo);
    palabras += (parrafo.match(/\S+/g) ?? []).length;
    i += 1;
  }

  const cabecera = [`# ${ficha.titulo}`];
  if (texto_previo && incidencias.length) {
    // Arreglo quirurgico: el texto de salida sigue siendo el capitulo entero.
    cabecera.push(`<!-- reescritura sobre ${incidencias.length} incidencia(s) -->`);
  }

  return {
    texto: [...cabecera, ...cuerpo].join('\n\n'),
    // §5: si le falta un detalle de epoca resuelve la escena sin el y lo anota.
    faltantes: ficha.etiquetas.length
      ? [`Falta un dato concreto de ${ficha.etiquetas[0]} para el capitulo ${ficha.numero}`]
      : [],
  };
}

// ------------------------------------------------------------------- validador

export function validador(entrada) {
  const { encargo, dimension = null, intento = 1 } = entrada;
  const numero = encargo.numero;
  const malo = inyectado('NOVELA_SIM_FALLOS', numero, intento);

  const bloque = (dim) => {
    if (malo) {
      const esContinuidad = dim === 'continuidad';
      return {
        dimension: dim,
        nota: esContinuidad ? 2 : 3,
        incidencias: esContinuidad
          ? [{
            cita: 'La casa estaba como la habia dejado',
            severidad: 'grave',
            sugerencia: 'El canon situa a la protagonista fuera de la casa desde el capitulo anterior.',
          }]
          : [{
            cita: 'el precio del pan seguia clavado',
            severidad: 'aviso',
            sugerencia: 'Apoyalo en un dato del dossier o quitalo.',
          }],
      };
    }
    return {
      dimension: dim,
      nota: 4,
      incidencias: dim === 'logica_ritmo'
        ? [{
          cita: 'Por la noche escribio dos lineas',
          severidad: 'aviso',
          sugerencia: 'La escena final puede cerrar medio parrafo antes.',
        }]
        : [],
    };
  };

  const dims = dimension ? [dimension] : DIMENSIONES;
  return { revisiones: dims.map(bloque) };
}

// -------------------------------------------------------------------- cronista

export function cronista(entrada) {
  const { ficha, personajes } = entrada;
  const presentes = personajes.map((p) => p.id);
  return {
    resumen: `En el capitulo ${ficha.numero}, ${ficha.sinopsis} Al cerrar, la posicion de`
      + ` ${personajes[0]?.nombre ?? 'la protagonista'} ha cambiado y el asunto principal`
      + ' avanza un escalon.',
    hilos_abiertos: [`Hilo abierto en el capitulo ${ficha.numero}: ${ficha.objetivo}`],
    hilos_cerrados: ficha.numero > 1
      ? [`Hilo abierto en el capitulo ${ficha.numero - 1}: ${ficha.objetivo.replace(
        `capitulo ${ficha.numero}`, `capitulo ${ficha.numero - 1}`)}`]
      : [],
    personajes_presentes: presentes,
    cambios_personaje: personajes.map((p) => ({
      id: p.id,
      ubicacion: `${p.ubicacion.replace(/ \(cap\. \d+\)$/, '')} (cap. ${ficha.numero})`,
      sabe: [...new Set([...p.sabe, `Lo ocurrido en el capitulo ${ficha.numero}`])],
    })),
    eventos: [{
      id: `evento-cap-${ficha.numero}`,
      tipo: 'trama',
      fecha: ficha.fecha,
      descripcion: `Sucesos del capitulo ${ficha.numero}: ${ficha.titulo}.`,
      capitulo: ficha.numero,
      personajes: presentes,
    }],
  };
}

// --------------------------------------------------------------- editor global

export function editorGlobal(entrada) {
  const { resumenes = [], hilos_vivos = [], personajes = [] } = entrada;
  const retoques = [];

  for (const [i, hilo] of hilos_vivos.slice(0, 5).entries()) {
    retoques.push({
      id: `RET-${String(i + 1).padStart(2, '0')}`,
      tipo: 'promesa',
      capitulos: [hilo.capitulo],
      descripcion: `Queda sin saldar: ${hilo.hilo}. Cierralo o retiralo del capitulo ${hilo.capitulo}.`,
      severidad: i === 0 ? 'grave' : 'aviso',
    });
  }

  const protagonista = personajes.find((p) => p.rol === 'protagonista');
  if (protagonista) {
    retoques.push({
      id: `RET-${String(retoques.length + 1).padStart(2, '0')}`,
      tipo: 'personaje',
      capitulos: [1, resumenes.length],
      descripcion: `El arco de ${protagonista.nombre} se enuncia en el capitulo 1 y no vuelve a`
        + ' tocarse hasta el final: falta un paso intermedio visible.',
      severidad: 'aviso',
    });
  }

  if (resumenes.length >= 3) {
    retoques.push({
      id: `RET-${String(retoques.length + 1).padStart(2, '0')}`,
      tipo: 'ritmo',
      capitulos: resumenes.slice(1, -1).map((r) => r.capitulo),
      descripcion: 'El acto central avanza al mismo paso en todos los capitulos; conviene'
        + ' acelerar uno y frenar otro.',
      severidad: 'aviso',
    });
  }

  return { retoques };
}

export const AGENTES_SIMULADOS = {
  investigador, arquitecto, escritor, validador, cronista, editor_global: editorGlobal,
};
