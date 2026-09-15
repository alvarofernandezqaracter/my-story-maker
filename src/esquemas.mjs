// Contratos de entrada/salida de los seis agentes de §5. No son un esquema JSON
// completo: solo lo que VD-01 y VD-02 necesitan para decidir si una propuesta
// parsea y trae sus campos obligatorios. El fondo no se juzga aqui.

export const DIMENSIONES = ['continuidad', 'anacronismos', 'logica_ritmo'];
export const CATEGORIAS_DATO = ['vestimenta', 'politica', 'comida', 'lenguaje', 'otro'];
export const ESTADOS_DATO = ['verificado', 'sin_verificar', 'inventado'];
export const ROLES_PERSONAJE = ['protagonista', 'secundario', 'figurante'];
export const TIPOS_EVENTO = ['trama', 'historico'];
export const SEVERIDADES = ['grave', 'aviso'];
export const TIPOS_RETOQUE = ['arco', 'promesa', 'ritmo', 'personaje'];

export const ESTADOS_PROYECTO = [
  'borrador', 'investigado', 'estructurado', 'escribiendo', 'bloqueado', 'escrito', 'editado',
];
export const ESTADOS_FICHA = ['pendiente', 'en_curso', 'aprobado', 'bloqueado'];
export const ESTADOS_REDACTADO = ['propuesto', 'aprobado', 'descartado'];

const texto = { tipo: 'texto' };
const entero = { tipo: 'entero' };
const lista = (de) => ({ tipo: 'lista', de });
const enumerado = (valores) => ({ tipo: 'enum', valores });

export const DATO = {
  id: texto, categoria: enumerado(CATEGORIAS_DATO), dato: texto,
  fuente: texto, estado: enumerado(ESTADOS_DATO), etiquetas: lista(texto),
};

export const PERSONAJE = {
  id: texto, nombre: texto, rol: enumerado(ROLES_PERSONAJE), voz: texto,
  motivacion: texto, arco: texto, ubicacion: texto,
  sabe: { ...lista(texto), opcional: true },
};

export const FICHA_CAPITULO = {
  numero: entero, titulo: texto, acto: entero, sinopsis: texto, fecha: texto,
  personajes: lista(texto), etiquetas: lista(texto), objetivo: texto,
  palabras_objetivo: entero,
};

export const INCIDENCIA = {
  cita: texto, severidad: enumerado(SEVERIDADES), sugerencia: texto,
};

export const BLOQUE_REVISION = {
  dimension: enumerado(DIMENSIONES), nota: entero,
  incidencias: { ...lista(INCIDENCIA), opcional: true },
};

export const EVENTO = {
  id: texto, tipo: enumerado(TIPOS_EVENTO), fecha: texto, descripcion: texto,
  capitulo: { ...entero, opcional: true },
  personajes: { ...lista(texto), opcional: true },
  dato_id: { ...texto, opcional: true },
};

export const CAMBIO_PERSONAJE = {
  id: texto,
  ubicacion: { ...texto, opcional: true },
  sabe: { ...lista(texto), opcional: true },
};

export const RETOQUE = {
  id: texto, tipo: enumerado(TIPOS_RETOQUE), capitulos: lista(entero),
  descripcion: texto, severidad: enumerado(SEVERIDADES),
};

// Salida esperada de cada rol. La clave es el rol de §5.
export const SALIDAS = {
  investigador: { datos: lista(DATO) },
  arquitecto: { personajes: lista(PERSONAJE), capitulos: lista(FICHA_CAPITULO) },
  escritor: { texto, faltantes: { ...lista(texto), opcional: true } },
  validador: { revisiones: lista(BLOQUE_REVISION) },
  cronista: {
    resumen: texto,
    hilos_abiertos: lista(texto), hilos_cerrados: lista(texto),
    personajes_presentes: lista(texto),
    cambios_personaje: { ...lista(CAMBIO_PERSONAJE), opcional: true },
    eventos: { ...lista(EVENTO), opcional: true },
  },
  editor_global: { retoques: lista(RETOQUE) },
};

// En modo separado el validador devuelve un bloque por llamada.
export const SALIDA_VALIDADOR_DIMENSION = { revisiones: lista(BLOQUE_REVISION) };

/** Comprueba forma (VD-01) y obligatoriedad (VD-02). Devuelve lista de fallos. */
export function comprobarForma(valor, esquema, camino = '') {
  const fallos = [];
  if (valor === null || typeof valor !== 'object' || Array.isArray(valor)) {
    return [`${camino || 'raiz'}: se esperaba un objeto`];
  }
  for (const [clave, def] of Object.entries(esquema)) {
    const ruta = camino ? `${camino}.${clave}` : clave;
    const v = valor[clave];
    if (v === undefined || v === null) {
      if (!def.opcional) fallos.push(`${ruta}: campo obligatorio ausente`);
      continue;
    }
    fallos.push(...comprobarValor(v, def, ruta));
  }
  return fallos;
}

function comprobarValor(v, def, ruta) {
  const fallos = [];
  switch (def.tipo) {
    case 'texto':
      if (typeof v !== 'string' || v.trim() === '') fallos.push(`${ruta}: texto vacio o no textual`);
      break;
    case 'entero':
      if (!Number.isInteger(v)) fallos.push(`${ruta}: se esperaba un entero`);
      break;
    case 'enum':
      if (!def.valores.includes(v)) {
        fallos.push(`${ruta}: "${v}" no esta en [${def.valores.join(', ')}]`);
      }
      break;
    case 'lista':
      if (!Array.isArray(v)) { fallos.push(`${ruta}: se esperaba una lista`); break; }
      v.forEach((item, i) => {
        if (def.de.tipo) fallos.push(...comprobarValor(item, def.de, `${ruta}[${i}]`));
        else fallos.push(...comprobarForma(item, def.de, `${ruta}[${i}]`));
      });
      break;
    default:
      fallos.push(...comprobarForma(v, def, ruta));
  }
  return fallos;
}
