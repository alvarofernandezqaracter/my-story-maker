// GENERADO desde backend/openapi.yaml por scripts/generar-contrato.mjs.
// No se edita a mano: si el borde cambia, se regenera (SPEC2 RI-02).
export interface paths {
    "/obras": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Listar Obras
         * @description Todas las obras, de la mas reciente a la mas antigua (RF-204).
         */
        get: operations["listar_obras_obras_get"];
        put?: never;
        /** Lanzar Obra */
        post: operations["lanzar_obra_obras_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/entrevistas": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Abrir Entrevista
         * @description Abre una entrevista y hace su primera pasada. Si el brief queda
         *     completo y sin contradicciones abiertas, la obra se lanza sola (RF-78).
         */
        post: operations["abrir_entrevista_entrevistas_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/entrevistas/{id_entrevista}/pasadas": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Pasar Entrevista
         * @description La pasada siguiente. No recibe nada de las anteriores (D-20).
         */
        post: operations["pasar_entrevista_entrevistas__id_entrevista__pasadas_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/obras/{id_obra}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Ver Obra */
        get: operations["ver_obra_obras__id_obra__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/obras/{id_obra}/manuscrito": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Leer Manuscrito
         * @description Solo el texto aceptado, en orden, con los capitulos marcados, de la
         *     version pedida o de la de referencia.
         */
        get: operations["leer_manuscrito_obras__id_obra__manuscrito_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/obras/{id_obra}/capitulos/{numero}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Ver Capitulo */
        get: operations["ver_capitulo_obras__id_obra__capitulos__numero__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/obras/{id_obra}/criticas": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Ver Criticas */
        get: operations["ver_criticas_obras__id_obra__criticas_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/obras/{id_obra}/trazas": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Ver Trazas */
        get: operations["ver_trazas_obras__id_obra__trazas_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/obras/{id_obra}/policy": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Ver Policy
         * @description El registro de auditoria de `policy`, en orden (RF-138). Solo lectura.
         */
        get: operations["ver_policy_obras__id_obra__policy_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/obras/{id_obra}/estado": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Ver Estado */
        get: operations["ver_estado_obras__id_obra__estado_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/obras/{id_obra}/hechos": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Ver Hechos
         * @description Cada hecho de la biblia con los capitulos en que se ha usado.
         */
        get: operations["ver_hechos_obras__id_obra__hechos_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/obras/{id_obra}/cronologia": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Ver Cronologia
         * @description Sucesos en orden, con momento, lugar y presentes con su nacimiento.
         */
        get: operations["ver_cronologia_obras__id_obra__cronologia_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/obras/{id_obra}/versiones": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Ver Versiones
         * @description Cada version con su base, lo que cambio y si es la publicada.
         */
        get: operations["ver_versiones_obras__id_obra__versiones_get"];
        put?: never;
        /**
         * Rehacer
         * @description Rehacer desde un capitulo: la version anterior se conserva entera y la
         *     nueva reescribe de ese capitulo al final (RF-111). No espera a que termine.
         */
        post: operations["rehacer_obras__id_obra__versiones_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/obras/{id_obra}/cambios": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Cambiar Hecho
         * @description El cambio del lector: el hecho toma su nombre nuevo en una version que
         *     reescribe solo los capitulos que lo mencionan (RF-170, RF-171). La
         *     anterior se conserva entera. No espera a que termine.
         */
        post: operations["cambiar_hecho_obras__id_obra__cambios_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/obras/{id_obra}/versiones/{numero}/publicar": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Publicar
         * @description Publicar es una orden: terminar no publica (RF-116), y la version pasa
         *     antes por la puerta (RF-146), cronologia en Lean incluida (RF-152). Si no
         *     pasa, no se publica y se explica; si falla la cronologia, el fallo queda
         *     ademas como critica del capitulo (RF-154).
         */
        post: operations["publicar_obras__id_obra__versiones__numero__publicar_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/obras/{id_obra}/versiones/{numero}/puerta": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Ver Puerta
         * @description La puerta pasada ahora sobre la version, sin publicar nada (RF-147).
         */
        get: operations["ver_puerta_obras__id_obra__versiones__numero__puerta_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/obras/{id_obra}/pdf": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Descargar Pdf
         * @description Portada, indice y texto aceptado de la version, fabricado en memoria
         *     (RF-178). Nada toca el disco (RD-08).
         */
        get: operations["descargar_pdf_obras__id_obra__pdf_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/obras/{id_obra}/progreso": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Ver Progreso
         * @description Flujo de eventos de progreso mientras la obra corre.
         */
        get: operations["ver_progreso_obras__id_obra__progreso_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/obras/{id_obra}/progreso/ahora": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Ver Progreso Ahora
         * @description El mismo progreso de una sola vez, para quien no quiera el flujo.
         */
        get: operations["ver_progreso_ahora_obras__id_obra__progreso_ahora_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/obras/{id_obra}/pasajes": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Buscar Pasaje */
        get: operations["buscar_pasaje_obras__id_obra__pasajes_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/obras/{id_obra}/detener": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Detener */
        post: operations["detener_obras__id_obra__detener_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/obras/{id_obra}/reanudar": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Reanudar
         * @description Vuelve al ultimo capitulo cerrado; no repite nada de lo cerrado.
         */
        post: operations["reanudar_obras__id_obra__reanudar_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
}
export type webhooks = Record<string, never>;
export interface components {
    schemas: {
        /**
         * BorradorDeBrief
         * @description El brief a medio escribir. Tiene los campos del `Brief`, todos opcionales.
         */
        BorradorDeBrief: {
            /** Titulo */
            titulo?: string | null;
            /** Epoca */
            epoca?: string | null;
            /** Premisa */
            premisa?: string | null;
            /** Tesis Tematica */
            tesis_tematica?: string | null;
            /** Elenco Declarado */
            elenco_declarado?: string[] | null;
            /** Capitulos Objetivo */
            capitulos_objetivo?: number | null;
            /** Politicas Globales */
            politicas_globales?: {
                [key: string]: unknown;
            } | null;
            /** Arcos */
            arcos?: string[] | null;
            destinatario?: components["schemas"]["BorradorDeDestinatario"] | null;
        };
        /**
         * BorradorDeDestinatario
         * @description El destinatario tal como la persona lo lleva escrito: todo opcional.
         *
         *     Un campo ausente es un campo por preguntar. Una lista presente, aunque venga
         *     vacia, es lo que la persona escribio, y ninguna pasada le quita nada (RF-73).
         */
        BorradorDeDestinatario: {
            /** Nombre */
            nombre?: string | null;
            /** Edad */
            edad?: number | null;
            /** Tono */
            tono?: string | null;
            /** Dedicatoria */
            dedicatoria?: string | null;
            /** Rasgos */
            rasgos?: string[] | null;
            /** Recuerdos */
            recuerdos?: string[] | null;
            /** Vetos */
            vetos?: string[] | null;
        };
        /**
         * Brief
         * @description Lo que el editor escribe para lanzar una obra.
         *
         *     Si falta un campo obligatorio, la obra se rechaza nombrando el campo y sin
         *     crear nada. Un brief incompleto es un caso normal, no un error del sistema.
         */
        Brief: {
            /**
             * Titulo
             * @description Titulo de la obra
             */
            titulo: string;
            /**
             * Epoca
             * @description Epoca y ambito geografico
             */
            epoca: string;
            /**
             * Premisa
             * @description De que va
             */
            premisa: string;
            /**
             * Tesis Tematica
             * @description Que sostiene la obra. Opcional: sin ella no hay tesis declarada (D-60)
             */
            tesis_tematica?: string | null;
            /**
             * Elenco Declarado
             * @description Personajes que el editor fija. Vacio: los decide el Constructor de mundo (D-60)
             */
            elenco_declarado?: string[];
            /**
             * Capitulos Objetivo
             * @description Cuantos capitulos
             */
            capitulos_objetivo: number;
            /**
             * Politicas Globales
             * @description POV dominante, tiempo verbal, nivel de arcaismo, extension
             */
            politicas_globales?: {
                [key: string]: unknown;
            };
            /**
             * Arcos
             * @description Arcos declarados
             */
            arcos?: string[];
            /** @description A quien va dedicada. Opcional: sin el, la obra es historica y nada mas */
            destinatario?: components["schemas"]["Destinatario"] | null;
        };
        /**
         * CambioDelLector
         * @description De que cambio del lector nace una version (RF-177).
         */
        CambioDelLector: {
            /** Hecho */
            hecho: string;
            /** Tipo */
            tipo: string;
            /** Anterior */
            anterior: string;
            /** Nuevo */
            nuevo: string;
        };
        /** CapituloInspeccionado */
        CapituloInspeccionado: {
            /** Capitulo */
            capitulo: number;
            /** Estado */
            estado: string | null;
            /** Plan */
            plan: {
                [key: string]: unknown;
            } | null;
            /** Escenas */
            escenas: {
                [key: string]: unknown;
            }[];
            /** Borrador Vigente Por Escena */
            borrador_vigente_por_escena: {
                [key: string]: {
                    [key: string]: unknown;
                };
            };
            /** Criticas */
            criticas: {
                [key: string]: unknown;
            }[];
        };
        /** Confirmacion */
        Confirmacion: {
            /** Id Obra */
            id_obra: string;
            /** Detenida */
            detenida: boolean;
            /** Motivo */
            motivo: string | null;
        };
        /**
         * Contradiccion
         * @description Lo que no casa. El Entrevistador no la resuelve: la devuelve como pregunta.
         */
        Contradiccion: {
            /**
             * Tipo
             * @enum {string}
             */
            tipo: "edad_contra_tono" | "texto_contra_campo";
            /** Campos */
            campos: string[];
            /** Evidencia */
            evidencia: string;
            /** Asumida */
            asumida: boolean;
        };
        /** CriticaServida */
        CriticaServida: {
            /** Id */
            id: string;
            /** Capitulo */
            capitulo: number | null;
            /** Escena */
            escena: string | null;
            /** Estado */
            estado: string | null;
            /** Severidad */
            severidad: string | null;
            /** Dimension */
            dimension: string | null;
            /** Detectada Por */
            detectada_por: string | null;
            /** Evidencia */
            evidencia: string | null;
            /** Accion Sugerida */
            accion_sugerida: string | null;
        };
        /**
         * Cronologia
         * @description Los sucesos de la obra en orden. Es una vista: se deriva al pedirla.
         */
        Cronologia: {
            /** Id Obra */
            id_obra: string;
            /** Sucesos */
            sucesos: components["schemas"]["Suceso"][];
        };
        /**
         * DecisionDePolicy
         * @description Una coincidencia de lo vetado y lo que `policy` hizo con ella (RI-16).
         */
        DecisionDePolicy: {
            /** Id */
            id: number;
            /** Id Traza */
            id_traza: string;
            /** Capitulo */
            capitulo: number | null;
            /** Escena */
            escena: string | null;
            /** Tarea */
            tarea: string | null;
            /** Intento */
            intento: number | null;
            /**
             * Decision
             * @enum {string}
             */
            decision: "devuelto_al_agente" | "intento_fallido";
            /**
             * Nivel
             * @enum {string}
             */
            nivel: "global" | "palabra_del_comprador" | "tema_del_comprador";
            /**
             * Termino
             * @description El veto tal como esta en su lista
             */
            termino: string;
            /**
             * Encontrado
             * @description Lo que casó, tal como esta escrito en la prosa
             */
            encontrado: string;
            /** Registrada En */
            registrada_en: string;
        };
        /**
         * Destinatario
         * @description La persona real a la que la obra va dedicada.
         *
         *     Aparece en la novela con su nombre de verdad, sin traducir a la epoca: lo
         *     que sale de su vida se marca `licencia = "personal"` y el detector de
         *     anacronismos lo deja en paz (D-12). Que papel tiene en la obra no se declara
         *     aqui: lo decide el Planificador y lo escribe en el `Plan` (D-14).
         *
         *     Obligatorios el nombre, la edad, el tono y la dedicatoria. Los tres que son
         *     listas pueden venir vacias, porque vacio es una respuesta: no veto nada, no
         *     aporto recuerdos.
         */
        Destinatario: {
            /**
             * Nombre
             * @description Su nombre real, tal como se escribira
             */
            nombre: string;
            /**
             * Edad
             * @description Edad del destinatario
             */
            edad: number;
            /**
             * Tono
             * @description Tono que se le pide a la obra
             */
            tono: string;
            /**
             * Dedicatoria
             * @description Lo que va en la portada
             */
            dedicatoria: string;
            /**
             * Rasgos
             * @description Como es
             */
            rasgos?: string[];
            /**
             * Recuerdos
             * @description Anecdotas de su vida. Cada una se guarda como Recuerdo (RF-07)
             */
            recuerdos?: string[];
            /**
             * Vetos
             * @description Palabras o temas que no quiere leer
             */
            vetos?: string[];
        };
        /**
         * EstadoPlegado
         * @description El estado plegado hasta el capitulo indicado, y el log de eventos.
         */
        EstadoPlegado: {
            /** Id Obra */
            id_obra: string;
            /** Capitulo */
            capitulo: number;
            /** Estado */
            estado: {
                [key: string]: unknown;
            } | null;
            /** Eventos */
            eventos: {
                [key: string]: unknown;
            }[];
        };
        /**
         * FalloDeLaPuerta
         * @description Lo que no pasa, de que validador y en que capitulo.
         */
        FalloDeLaPuerta: {
            /**
             * Validador
             * @enum {string}
             */
            validador: "esquema" | "nombres" | "longitud" | "elementos_personalizados" | "cronologia";
            /**
             * Capitulo
             * @description Vacio si el fallo no es de ningun capitulo
             */
            capitulo: number | null;
            /** Detalle */
            detalle: string;
        };
        /**
         * FichaDeObra
         * @description Estado de la obra, capitulo en curso y recuento de cerrados y marcados.
         */
        FichaDeObra: {
            /** Id Obra */
            id_obra: string;
            /** Titulo */
            titulo: string;
            /**
             * Situacion
             * @description Donde esta la obra: detenida, en produccion, publicada o terminada, decidido en ese orden (RF-205)
             * @enum {string}
             */
            situacion: "en_produccion" | "detenida" | "terminada" | "publicada";
            /** Detenida */
            detenida: boolean;
            /** Capitulo En Curso */
            capitulo_en_curso: number | null;
            /** Capitulos Cerrados */
            capitulos_cerrados: number;
            /** Capitulos Marcados */
            capitulos_marcados: number;
            /** Criticas Abiertas */
            criticas_abiertas: number;
            /**
             * Version En Curso
             * @description La ultima version, la unica que se produce
             */
            version_en_curso: number;
            /**
             * Version Publicada
             * @description La de la ultima publicacion, si la hay
             */
            version_publicada: number | null;
            /**
             * Motivo De La Detencion
             * @description Por que esta detenida: la tarea, lo que fallo y su traza. Vacio si no (RI-17)
             */
            motivo_de_la_detencion?: string | null;
            /**
             * Destinatario
             * @description Nombre del destinatario, para la portada (RF-177)
             */
            destinatario?: string | null;
            /**
             * Dedicatoria
             * @description La dedicatoria tal como viene en el brief (RF-177)
             */
            dedicatoria?: string | null;
            /**
             * Epoca
             * @description Epoca y ambito geografico, tal como vienen en el brief
             * @default
             */
            epoca: string;
        };
        /** HTTPValidationError */
        HTTPValidationError: {
            /** Detail */
            detail?: components["schemas"]["ValidationError"][];
        };
        /**
         * HechoDeLaBiblia
         * @description Una ficha del mundo que el texto nombra, con los capitulos en que se usa.
         *
         *     Los capitulos se derivan de las `Mencion` que el Archivero anota al cerrar
         *     cada capitulo; la ficha no los guarda (RF-84).
         */
        HechoDeLaBiblia: {
            /** Id */
            id: string;
            /** Tipo */
            tipo: string;
            /** Nombre */
            nombre: string | null;
            /** Licencia */
            licencia: string | null;
            /** Capitulos */
            capitulos: number[];
        };
        /** HechoDescartado */
        HechoDescartado: {
            /** Campo */
            campo: string | null;
            /** Cita */
            cita: string | null;
            /** Motivo */
            motivo: string;
        };
        /**
         * HechoExtraido
         * @description Un hecho sacado de un texto pegado, con su cita literal.
         */
        HechoExtraido: {
            /** Campo */
            campo: string;
            /** Valor */
            valor: unknown;
            /** Cita */
            cita: string;
        };
        /** Manuscrito */
        Manuscrito: {
            /** Id Obra */
            id_obra: string;
            /**
             * Version
             * @description La version que se sirve
             */
            version: number;
            /**
             * Publicada
             * @description Si esa version es la publicada
             */
            publicada: boolean;
            /** Unidades */
            unidades: components["schemas"]["UnidadDelManuscrito"][];
        };
        /** ObraCreada */
        ObraCreada: {
            /** Id Obra */
            id_obra: string;
            /** Estado */
            estado: string;
        };
        /**
         * ObraDelTaller
         * @description Una obra en el listado del taller: su ficha y lo que pide su brief (RF-204).
         */
        ObraDelTaller: {
            /** Id Obra */
            id_obra: string;
            /** Titulo */
            titulo: string;
            /**
             * Situacion
             * @description Donde esta la obra: detenida, en produccion, publicada o terminada, decidido en ese orden (RF-205)
             * @enum {string}
             */
            situacion: "en_produccion" | "detenida" | "terminada" | "publicada";
            /** Detenida */
            detenida: boolean;
            /** Capitulo En Curso */
            capitulo_en_curso: number | null;
            /** Capitulos Cerrados */
            capitulos_cerrados: number;
            /** Capitulos Marcados */
            capitulos_marcados: number;
            /** Criticas Abiertas */
            criticas_abiertas: number;
            /**
             * Version En Curso
             * @description La ultima version, la unica que se produce
             */
            version_en_curso: number;
            /**
             * Version Publicada
             * @description La de la ultima publicacion, si la hay
             */
            version_publicada: number | null;
            /**
             * Motivo De La Detencion
             * @description Por que esta detenida: la tarea, lo que fallo y su traza. Vacio si no (RI-17)
             */
            motivo_de_la_detencion?: string | null;
            /**
             * Destinatario
             * @description Nombre del destinatario, para la portada (RF-177)
             */
            destinatario?: string | null;
            /**
             * Dedicatoria
             * @description La dedicatoria tal como viene en el brief (RF-177)
             */
            dedicatoria?: string | null;
            /**
             * Epoca
             * @description Epoca y ambito geografico, tal como vienen en el brief
             * @default
             */
            epoca: string;
            /**
             * Capitulos Objetivo
             * @description Cuantos capitulos pide el brief
             */
            capitulos_objetivo: number;
            /**
             * Creada En
             * @description Cuando se dio de alta la obra
             */
            creada_en: string;
        };
        /**
         * Orden
         * @description Detener o reanudar. Es control, no mantenimiento.
         */
        Orden: {
            /**
             * Motivo
             * @description Por que se detiene
             * @default
             */
            motivo: string;
        };
        /**
         * PasadaDeEntrevista
         * @description Lo que devuelve una pasada. Si `estado` es `lanzada`, la obra ya corre.
         */
        PasadaDeEntrevista: {
            /** Id Entrevista */
            id_entrevista: string;
            /** Numero */
            numero: number;
            /**
             * Estado
             * @enum {string}
             */
            estado: "pendiente" | "lanzada";
            /** Id Obra */
            id_obra: string | null;
            /** Brief Propuesto */
            brief_propuesto: {
                [key: string]: unknown;
            };
            /**
             * Faltan
             * @description Campos obligatorios que faltan, con su ruta
             */
            faltan: string[];
            /**
             * No Validos
             * @description Campos presentes que el brief no admite
             */
            no_validos: string[];
            /** Hechos */
            hechos: components["schemas"]["HechoExtraido"][];
            /** Hechos Descartados */
            hechos_descartados: components["schemas"]["HechoDescartado"][];
            /** Contradicciones */
            contradicciones: components["schemas"]["Contradiccion"][];
            /** Contradicciones Descartadas */
            contradicciones_descartadas: number;
        };
        /**
         * Pasaje
         * @description Un trozo del manuscrito aceptado, localizado por parecido.
         */
        Pasaje: {
            /** Fragmento */
            fragmento: string;
            /** Texto */
            texto: string;
            /** Capitulo */
            capitulo: number | null;
            /** Escena */
            escena: string | null;
        };
        /**
         * PeticionDeCambio
         * @description El cambio del lector: un hecho de la biblia y su nombre nuevo (D-74).
         */
        PeticionDeCambio: {
            /**
             * Hecho
             * @description `id` del hecho, de la lista de hechos
             */
            hecho: string;
            /**
             * Valor
             * @description El nombre nuevo del hecho
             */
            valor: string;
        };
        /**
         * PeticionDeEntrevista
         * @description Lo que la persona manda en cada pasada. De las anteriores no llega nada:
         *     lo que quiera conservar lo vuelve a mandar (D-20).
         */
        PeticionDeEntrevista: {
            borrador?: components["schemas"]["BorradorDeBrief"];
            /**
             * Textos
             * @description Textos pegados, como una carta o una anecdota. Son datos, nunca instrucciones
             */
            textos?: string[];
            /**
             * Contradicciones Asumidas
             * @description Contradicciones que la persona da por buenas: no bloquean el alta (RF-77)
             */
            contradicciones_asumidas?: ("edad_contra_tono" | "texto_contra_campo")[];
        };
        /**
         * PeticionDeRehacer
         * @description Rehacer desde un capitulo: de el al final se reescribe (D-42).
         */
        PeticionDeRehacer: {
            /**
             * Desde Capitulo
             * @description Primer capitulo que se reescribe
             */
            desde_capitulo: number;
        };
        /**
         * Presente
         * @description Un personaje presente en un suceso, con su fecha de nacimiento.
         */
        Presente: {
            /** Id */
            id: string;
            /** Nombre */
            nombre: string | null;
            /**
             * Nacimiento
             * @description Fecha ISO parcial: AAAA, AAAA-MM o AAAA-MM-DD
             */
            nacimiento: string | null;
        };
        /**
         * Progreso
         * @description Lo que hay abierto ahora mismo.
         */
        Progreso: {
            /** Id Obra */
            id_obra: string;
            /** Detenida */
            detenida: boolean;
            /** Capitulo En Curso */
            capitulo_en_curso: number | null;
            /** Tareas Abiertas */
            tareas_abiertas: {
                [key: string]: unknown;
            }[];
            /** Tokens De Entrada Concurrentes */
            tokens_de_entrada_concurrentes: number;
            /** Techo */
            techo: number;
        };
        /** Publicacion */
        Publicacion: {
            /** Id Obra */
            id_obra: string;
            /** Version */
            version: number;
            /** Publicada En */
            publicada_en: string;
            /**
             * Comprobacion Formal
             * @description Como quedo la cronologia en Lean al publicar: `sin_comprobacion` si Lean no esta en la maquina, que no impide publicar (RF-155)
             * @enum {string}
             */
            comprobacion_formal: "demostrada" | "fallida" | "sin_comprobacion";
        };
        /**
         * PuertaDePublicacion
         * @description El resultado de pasar la puerta sobre una version. Se deriva al pedirlo.
         */
        PuertaDePublicacion: {
            /** Id Obra */
            id_obra: string;
            /** Version */
            version: number;
            /**
             * Terminada
             * @description Sin terminar no se publica aunque pase
             */
            terminada: boolean;
            /** Pasa */
            pasa: boolean;
            /**
             * Comprobacion Formal
             * @description La cronologia en Lean: `demostrada`, `fallida`, o `sin_comprobacion` si Lean no esta en la maquina, que no hace fallar la puerta (RF-152, D-61)
             * @enum {string}
             */
            comprobacion_formal: "demostrada" | "fallida" | "sin_comprobacion";
            /** Fallos */
            fallos: components["schemas"]["FalloDeLaPuerta"][];
        };
        /**
         * RechazoDePublicacion
         * @description Por que no se publico. `puerta` viene si lo que fallo fue la puerta.
         */
        RechazoDePublicacion: {
            /** Detail */
            detail: string;
            puerta?: components["schemas"]["PuertaDePublicacion"] | null;
        };
        /**
         * Suceso
         * @description Una fila de la cronologia: un `EventoEstado` o un `Evento` del mundo.
         */
        Suceso: {
            /**
             * Origen
             * @description evento_de_estado o evento_del_mundo
             */
            origen: string;
            /** Id */
            id: string;
            /** Capitulo */
            capitulo: number | null;
            /** Suceso */
            suceso: string | null;
            /**
             * Momento
             * @description Fecha ISO parcial: AAAA, AAAA-MM o AAAA-MM-DD
             */
            momento: string | null;
            /** Lugar */
            lugar: string | null;
            /** Presentes */
            presentes: components["schemas"]["Presente"][];
        };
        /** TrazaServida */
        TrazaServida: {
            /** Id */
            id: string;
            /** Capitulo */
            capitulo: number | null;
            /** Escena */
            escena: string | null;
            /** Rol */
            rol: string | null;
            /** Tarea */
            tarea: string | null;
            /** Intento */
            intento: number | null;
            /** Tokens De Entrada Estimados */
            tokens_de_entrada_estimados: number | null;
            /** Tokens De Entrada Medidos */
            tokens_de_entrada_medidos: number | null;
            /** Tokens De Salida */
            tokens_de_salida: number | null;
            /** Coste */
            coste: number | null;
            /** Latencia Ms */
            latencia_ms: number | null;
            /** Abierta En */
            abierta_en: string | null;
            /** Cerrada En */
            cerrada_en: string | null;
            /**
             * Ganchos
             * @description Lo que dijeron los hooks del paso durante la sesion y su veredicto final. Vacio si el paso no lleva hooks (RI-15)
             */
            ganchos?: {
                [key: string]: unknown;
            } | null;
        };
        /** UnidadDelManuscrito */
        UnidadDelManuscrito: {
            /** Capitulo */
            capitulo: number;
            /** Escena */
            escena: string;
            /** Texto */
            texto: string;
            /** Capitulo Marcado */
            capitulo_marcado: boolean;
        };
        /** ValidationError */
        ValidationError: {
            /** Location */
            loc: (string | number)[];
            /** Message */
            msg: string;
            /** Error Type */
            type: string;
            /** Input */
            input?: unknown;
            /** Context */
            ctx?: Record<string, never>;
        };
        /** VersionAbierta */
        VersionAbierta: {
            /** Id Obra */
            id_obra: string;
            /** Version */
            version: number;
            /** Capitulos Cambiados */
            capitulos_cambiados: number[];
            /** Estado */
            estado: string;
        };
        /**
         * VersionDeLaObra
         * @description Una version con su base y lo que cambio respecto de ella.
         */
        VersionDeLaObra: {
            /** Numero */
            numero: number;
            /**
             * Base
             * @description La version de la que sale; la 1 no sale de ninguna
             */
            base: number | null;
            /**
             * Capitulos Cambiados
             * @description Los que reescribe respecto de su base
             */
            capitulos_cambiados: number[];
            /** Creada En */
            creada_en: string;
            /** Terminada En */
            terminada_en: string | null;
            /** Terminada */
            terminada: boolean;
            /**
             * Publicada
             * @description Si es la de la ultima publicacion
             */
            publicada: boolean;
            /** @description Si nace de un cambio del lector, cual; vacio si del alta o de rehacer */
            cambio?: components["schemas"]["CambioDelLector"] | null;
        };
    };
    responses: never;
    parameters: never;
    requestBodies: never;
    headers: never;
    pathItems: never;
}
export type $defs = Record<string, never>;
export interface operations {
    listar_obras_obras_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ObraDelTaller"][];
                };
            };
        };
    };
    lanzar_obra_obras_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["Brief"];
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ObraCreada"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    abrir_entrevista_entrevistas_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["PeticionDeEntrevista"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PasadaDeEntrevista"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    pasar_entrevista_entrevistas__id_entrevista__pasadas_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                /** @description Identificador de la entrevista */
                id_entrevista: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["PeticionDeEntrevista"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PasadaDeEntrevista"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    ver_obra_obras__id_obra__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                /** @description Identificador de la obra */
                id_obra: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["FichaDeObra"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    leer_manuscrito_obras__id_obra__manuscrito_get: {
        parameters: {
            query?: {
                /** @description Version que se lee. Sin ella, la publicada, y si no hay, la ultima */
                version?: number | null;
            };
            header?: never;
            path: {
                /** @description Identificador de la obra */
                id_obra: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Manuscrito"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    ver_capitulo_obras__id_obra__capitulos__numero__get: {
        parameters: {
            query?: {
                /** @description Version que se lee. Sin ella, la publicada, y si no hay, la ultima */
                version?: number | null;
            };
            header?: never;
            path: {
                /** @description Identificador de la obra */
                id_obra: string;
                numero: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CapituloInspeccionado"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    ver_criticas_obras__id_obra__criticas_get: {
        parameters: {
            query?: {
                estado?: string | null;
                dimension?: string | null;
                severidad?: string | null;
                capitulo?: number | null;
                /** @description Version que se lee. Sin ella, la publicada, y si no hay, la ultima */
                version?: number | null;
            };
            header?: never;
            path: {
                /** @description Identificador de la obra */
                id_obra: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CriticaServida"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    ver_trazas_obras__id_obra__trazas_get: {
        parameters: {
            query?: {
                capitulo?: number | null;
                rol?: string | null;
                tarea?: string | null;
            };
            header?: never;
            path: {
                /** @description Identificador de la obra */
                id_obra: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TrazaServida"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    ver_policy_obras__id_obra__policy_get: {
        parameters: {
            query?: {
                capitulo?: number | null;
                nivel?: ("global" | "palabra_del_comprador" | "tema_del_comprador") | null;
                decision?: ("devuelto_al_agente" | "intento_fallido") | null;
            };
            header?: never;
            path: {
                /** @description Identificador de la obra */
                id_obra: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DecisionDePolicy"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    ver_estado_obras__id_obra__estado_get: {
        parameters: {
            query?: {
                capitulo?: number;
                /** @description Version que se lee. Sin ella, la publicada, y si no hay, la ultima */
                version?: number | null;
            };
            header?: never;
            path: {
                /** @description Identificador de la obra */
                id_obra: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["EstadoPlegado"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    ver_hechos_obras__id_obra__hechos_get: {
        parameters: {
            query?: {
                tipo?: ("Personaje" | "Lugar" | "Objeto" | "Faccion" | "Evento") | null;
                licencia?: ("canon" | "plausible" | "licencia" | "personal") | null;
                /** @description Version que se lee. Sin ella, la publicada, y si no hay, la ultima */
                version?: number | null;
            };
            header?: never;
            path: {
                /** @description Identificador de la obra */
                id_obra: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HechoDeLaBiblia"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    ver_cronologia_obras__id_obra__cronologia_get: {
        parameters: {
            query?: {
                /** @description Version que se lee. Sin ella, la publicada, y si no hay, la ultima */
                version?: number | null;
            };
            header?: never;
            path: {
                /** @description Identificador de la obra */
                id_obra: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Cronologia"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    ver_versiones_obras__id_obra__versiones_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                /** @description Identificador de la obra */
                id_obra: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["VersionDeLaObra"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    rehacer_obras__id_obra__versiones_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                /** @description Identificador de la obra */
                id_obra: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["PeticionDeRehacer"];
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["VersionAbierta"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    cambiar_hecho_obras__id_obra__cambios_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                /** @description Identificador de la obra */
                id_obra: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["PeticionDeCambio"];
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["VersionAbierta"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    publicar_obras__id_obra__versiones__numero__publicar_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                /** @description Identificador de la obra */
                id_obra: string;
                /** @description Version que se publica */
                numero: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Publicacion"];
                };
            };
            /** @description No se publica: la version no ha terminado, o no pasa la puerta y `puerta` dice que fallo y en que capitulo (RI-18) */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RechazoDePublicacion"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    ver_puerta_obras__id_obra__versiones__numero__puerta_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                /** @description Identificador de la obra */
                id_obra: string;
                /** @description Version que se comprueba */
                numero: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PuertaDePublicacion"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    descargar_pdf_obras__id_obra__pdf_get: {
        parameters: {
            query?: {
                /** @description Version que se lee. Sin ella, la publicada, y si no hay, la ultima */
                version?: number | null;
            };
            header?: never;
            path: {
                /** @description Identificador de la obra */
                id_obra: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description El PDF de la version, como descarga. No se guarda */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/pdf": string;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    ver_progreso_obras__id_obra__progreso_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                /** @description Identificador de la obra */
                id_obra: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Flujo abierto mientras la obra corre. Cada evento `progreso` lleva un `Progreso`; el evento `terminada` lo cierra. */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "text/event-stream": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    ver_progreso_ahora_obras__id_obra__progreso_ahora_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                /** @description Identificador de la obra */
                id_obra: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Progreso"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    buscar_pasaje_obras__id_obra__pasajes_get: {
        parameters: {
            query: {
                consulta: string;
                k?: number;
            };
            header?: never;
            path: {
                /** @description Identificador de la obra */
                id_obra: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Pasaje"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    detener_obras__id_obra__detener_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                /** @description Identificador de la obra */
                id_obra: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["Orden"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Confirmacion"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    reanudar_obras__id_obra__reanudar_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                /** @description Identificador de la obra */
                id_obra: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Confirmacion"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
}
