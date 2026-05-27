"""
Invocacion del LLM via OpenRouter (proveedor unico en produccion).
"""
from __future__ import annotations

import json
import os
import time

from dotenv import load_dotenv

from core.database import get_db_connection
from features.propuestas.schemas import (
    EquipoSeleccionado, PropuestaEquipos, FormularioCliente,
)

load_dotenv()

GEMINI_KEYS = [v for v in [
    os.getenv("GEMINI_API_KEY_LLM"),
    os.getenv("GEMINI_API_KEY"),
    os.getenv("GEMINI_API_KEY_2"),
    os.getenv("GEMINI_API_KEY_3"),
    os.getenv("GEMINI_API_KEY_4"),
    os.getenv("GEMINI_API_KEY_5"),
    os.getenv("GEMINI_API_KEY_6"),
] if v]

GEMINI_MODEL = "gemini-2.5-pro"
OPENROUTER_KEY = os.getenv("OPENROUTER_API_KEY", "")
# Modelo por defecto: un modelo :free de OpenRouter para que funcione tambien
# cuando la cuenta no tiene saldo. DeepSeek V4 Flash es la mejor opcion gratuita
# probada para structured output: 1M tokens de contexto, JSON estable y rapido.
# Si el frontend manda 'openrouter_model' (desde 'Configuracion avanzada') se
# usa ese; si no, este default. La variable de entorno OPENROUTER_MODEL se
# ignora a proposito.
# Para usar un modelo mas potente y sin rate limits agresivos, el cliente debe
# recargar saldo en https://openrouter.ai/credits y elegir el modelo desde el
# desplegable del formulario.
OPENROUTER_MODEL_DEFAULT = "deepseek/deepseek-v4-flash:free"
# Alias retrocompatible (callers viejos)
OPENROUTER_MODEL = OPENROUTER_MODEL_DEFAULT
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OPENROUTER_HEADERS = {
    "HTTP-Referer": os.getenv("OPENROUTER_REFERER", "https://cocinas-repagas-agenete.netlify.app"),
    "X-Title": os.getenv("OPENROUTER_APP_TITLE", "Repagas Concept Designer"),
}

# Ultimo motivo por el que invocar_llm_con_rotacion devolvio None.
# Lo lee el fallback para incluirlo en las notas que ve el usuario.
_ULTIMO_FALLO_LLM: dict | None = None


def obtener_ultimo_fallo_llm() -> dict | None:
    """Devuelve el ultimo motivo por el que el LLM no pudo responder, o None si la
    ultima llamada fue exitosa o no hubo intento. Estructura:
        {"proveedor": "openrouter"|"ninguno", "motivo": str, "detalle": str}
    """
    return _ULTIMO_FALLO_LLM


def _set_fallo_llm(proveedor: str, motivo: str, detalle: str = "") -> None:
    global _ULTIMO_FALLO_LLM
    _ULTIMO_FALLO_LLM = {"proveedor": proveedor, "motivo": motivo, "detalle": detalle[:300]}


def _clasificar_error_openrouter(err: str) -> tuple[str, str]:
    """Clasifica un error de OpenRouter en (motivo_corto, mensaje_user_friendly)."""
    e = err.lower()
    if "402" in err or "payment required" in e or "insufficient" in e or "credit" in e:
        return ("creditos_agotados", "OpenRouter sin creditos disponibles. Recargar saldo en https://openrouter.ai/credits.")
    if "429" in err or "rate limit" in e or "rate-limit" in e:
        return ("rate_limit", "OpenRouter rate limit alcanzado. Reintentar en unos minutos.")
    if "401" in err or "unauthorized" in e or "invalid api key" in e:
        return ("auth", "OPENROUTER_API_KEY invalida o sin permisos. Revisar la variable de entorno en Railway.")
    if "404" in err or "not found" in e or "model" in e and "available" in e:
        return ("modelo_no_disponible", f"El modelo '{OPENROUTER_MODEL}' no esta disponible en OpenRouter. Elegir otro modelo desde 'Configuracion avanzada' del formulario (sugerencia: deepseek/deepseek-v4-flash:free).")
    if "timeout" in e or "timed out" in e:
        return ("timeout", "OpenRouter no respondio a tiempo. Reintentar.")
    return ("error", f"OpenRouter respondio con un error inesperado: {err[:200]}")


# Reglas de diseño base por tipo de negocio.
# En produccion, estas vendran del RAG (Mundo Semantico).
REGLAS_DISENO = {
    "restaurante_tradicional": """
Reglas de diseño para Restaurante Tradicional:
- Línea mural de cocción completa: cocina a gas (4-6 fuegos), fry-top, freidora, plancha
- Elemento neutro entre cada equipo de cocción para apoyo
- Horno combinado (mínimo 6 GN 1/1 para <100 comensales, 10 GN para 100-200, 20 GN para >200)
- Mesa refrigerada de conservación para mise en place
- Lavavajillas de capota para >80 comensales, de cesto para <80
- Dimensionar por ratio: ~0.5m² de cocina por comensal (mínimo)
- Serie 750 para espacios estándar, Serie 900 para alta producción
""",
    "taperia": """
Reglas de diseño para Tapería/Cafetería:
- Línea corta: plancha o fry-top como equipo principal, freidora
- Cocina a gas de 2-4 fuegos
- Horno combinado compacto (6 GN 1/1)
- Mesa refrigerada para ingredientes de tapas
- Barra con mueble cafetería
- Serie 750 (espacios reducidos habitual en tapas)
""",
    "fast_food": """
Reglas de diseño para Fast Food:
- Múltiples freidoras (2-3 unidades) como equipo central
- Plancha o fry-top de ancho grande (800-1200mm)
- Sin cocina de fuegos abiertos típicamente
- Mantenedor de fritos
- Horno combinado compacto para panes/bakery
- Serie 750 o 550 (espacios compactos)
""",
    "hotel": """
Reglas de diseño para Hotel/Buffet:
- Línea mural extensa: múltiples cocinas, fry-tops, planchas
- Varios hornos combinados de gran capacidad (20 GN 1/1)
- Marmita para caldos y sopas
- Baño maría para servicio buffet
- Cuece-pastas si hay menú mediterráneo
- Mesa refrigerada grande para mise en place
- Serie 900 obligatoria por volumen de producción
""",
}

# Fallback por defecto si no hay match
REGLAS_DISENO["default"] = REGLAS_DISENO["restaurante_tradicional"]


def obtener_reglas_diseno(formulario) -> str:
    """
    Obtiene las reglas de diseño combinando RAG (Mundo Semántico) + reglas base.

    Acepta un FormularioCliente completo o un str (tipo_negocio) para compatibilidad.
    1. Busca chunks relevantes en el RAG via buscar_similar()
    2. Combina con reglas hardcodeadas como fallback/base
    3. Si RAG falla (keys agotadas, error DB), usa solo hardcodeado
    """
    # Compatibilidad: acepta str o FormularioCliente
    if isinstance(formulario, str):
        tipo_negocio = formulario
        identidad = None
        estructura_menu = None
        tiene_quinta_gama = False
        tiene_congelados = False
    else:
        tipo_negocio = formulario.tipo_negocio
        identidad = formulario.identidad_gastronomica.identidad
        estructura_menu = ", ".join(formulario.identidad_gastronomica.estructura_menu) or None
        tiene_quinta_gama = bool(formulario.identidad_gastronomica.quinta_gama)
        tiene_congelados = bool(formulario.identidad_gastronomica.ingredientes_congelados)

    reglas_base = REGLAS_DISENO.get(tipo_negocio, REGLAS_DISENO["default"])

    # Intentar enriquecer con RAG (con timeout de 15s para no colgar)
    try:
        from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutTimeout
        from features.rag.pipeline import buscar_similar

        def _rag_search():
            queries = [
                f"diseño cocina industrial {tipo_negocio.replace('_', ' ')}",
                f"equipamiento cocina {(identidad or tipo_negocio).replace('_', ' ')} {(estructura_menu or '').replace('_', ' ')} comensales",
            ]
            if tiene_quinta_gama:
                queries.append("horno regeneración quinta gama cocina industrial")
            if tiene_congelados:
                queries.append("conservación congelados cocina industrial equipamiento")
            chunks_vistos = set()
            parts = []
            for q in queries:
                resultados = buscar_similar(q, top_k=3)
                for r in resultados:
                    contenido = r["contenido"][:200]
                    if contenido not in chunks_vistos and r["similitud"] > 0.3:
                        chunks_vistos.add(contenido)
                        parts.append(
                            f"[{r['titulo']} — sim:{r['similitud']:.2f}]\n{r['contenido']}"
                        )
            return parts

        with ThreadPoolExecutor(max_workers=1) as pool:
            reglas_rag_parts = pool.submit(_rag_search).result(timeout=15)

        if reglas_rag_parts:
            reglas_rag = "\n\n".join(reglas_rag_parts[:5])
            print(f"  RAG: {len(reglas_rag_parts)} reglas encontradas del Mundo Semántico")
            return f"{reglas_base}\n\nINFORMACIÓN ADICIONAL DEL RAG (documentación real Repagas):\n{reglas_rag}"
        else:
            print("  RAG: sin resultados relevantes, usando reglas base")
    except FutTimeout:
        print("  RAG: timeout (15s), usando reglas base")
    except Exception as e:
        print(f"  RAG: fallback a reglas base ({e})")

    return reglas_base


def obtener_tipos_disponibles() -> str:
    """Consulta la DB para saber qué tipos de equipo existen realmente."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT LOWER(e.tipo), LOWER(e.alimentacion), COUNT(*)
            FROM equipos e
            WHERE e.activo = TRUE
              AND e.ancho_mm IS NOT NULL
            GROUP BY LOWER(e.tipo), LOWER(e.alimentacion)
            ORDER BY COUNT(*) DESC
        """)
        lineas = []
        for row in cur.fetchall():
            lineas.append(f"  - {row[0]} ({row[1]}): {row[2]} modelos")
        return "\n".join(lineas)
    finally:
        cur.close()
        conn.close()



def _es_error_rate_limit(err: str) -> bool:
    """Detecta si un error es de rate limit (429)."""
    return "429" in err or "RESOURCE_EXHAUSTED" in err


def _es_limite_diario(err: str) -> bool:
    """Detecta si el rate limit es diario (no vale esperar)."""
    err_lower = err.lower()
    return (
        ("PerDay" in err and "limit: 0" in err)
        or "exceeded your current quota" in err_lower
        or "quota exceeded" in err_lower
        or "daily" in err_lower
    )


def invocar_llm_con_rotacion(messages, structured_cls=None, max_reintentos: int = 2, espera_s: int = 15, openrouter_model: str | None = None):
    """
    Invoca el LLM via OpenRouter. Reintenta solo en limites de minuto.

    Args:
        messages: Lista de mensajes para el LLM
        structured_cls: Clase Pydantic para structured output (opcional)
        max_reintentos: Rondas de reintentos si todas fallan por limite por minuto
        espera_s: Segundos de espera entre rondas
        openrouter_model: Modelo de OpenRouter a usar; si None se usa el default
            (google/gemini-3-flash-preview). El frontend puede pasar uno distinto
            desde "Configuracion avanzada".

    Returns:
        Respuesta del LLM o None si todas las keys fallan
    """
    global _ULTIMO_FALLO_LLM

    modelo_efectivo = openrouter_model or OPENROUTER_MODEL_DEFAULT

    # 1. Proveedor principal: OpenRouter. En produccion (Railway de Repagas) es el
    #    unico proveedor: si OpenRouter falla, no hay rotacion posible.
    if OPENROUTER_KEY:
        print(f"  Probando OpenRouter ({modelo_efectivo})...")
        try:
            from langchain_openai import ChatOpenAI
            llm = ChatOpenAI(
                model=modelo_efectivo,
                base_url=OPENROUTER_BASE_URL,
                api_key=OPENROUTER_KEY,
                temperature=0.3,
                timeout=180,
                max_tokens=16384,
                default_headers=OPENROUTER_HEADERS,
            )
            if structured_cls:
                result = llm.with_structured_output(structured_cls).invoke(messages)
            else:
                result = llm.invoke(messages)
            print(f"  LLM respondio via OpenRouter ({modelo_efectivo})")
            _ULTIMO_FALLO_LLM = None  # exito: limpiar motivo previo
            return result
        except Exception as e:
            err = str(e)
            motivo, detalle = _clasificar_error_openrouter(err)
            print(f"  OpenRouter [{motivo}]: {detalle}")
            _set_fallo_llm("openrouter", motivo, detalle)
            if not GEMINI_KEYS:
                # Produccion: solo OpenRouter. Cortamos sin ruido.
                return None
            # Dev local: hay un proveedor alternativo (no se menciona explicitamente
            # en logs/notas para no exponer detalles internos al usuario).
            print("  Intentando proveedor alternativo de desarrollo...")

    # 2. Proveedor alternativo (solo dev local, no aplica en produccion)
    from langchain_google_genai import ChatGoogleGenerativeAI

    os.environ.pop("GOOGLE_API_KEY", None)

    for intento in range(max_reintentos + 1):
        hubo_limite_minuto = False

        for key_idx, key in enumerate(GEMINI_KEYS):
            try:
                llm = ChatGoogleGenerativeAI(
                    model=GEMINI_MODEL,
                    google_api_key=key,
                    temperature=0.3,
                    timeout=120,
                )
                if structured_cls:
                    result = llm.with_structured_output(structured_cls).invoke(messages)
                else:
                    result = llm.invoke(messages)
                print(f"  LLM respondio (alternativo {key_idx + 1}/{len(GEMINI_KEYS)})")
                _ULTIMO_FALLO_LLM = None
                return result
            except Exception as e:
                err = str(e)
                if _es_error_rate_limit(err):
                    if _es_limite_diario(err):
                        print(f"  Alternativo {key_idx + 1}/{len(GEMINI_KEYS)} -- limite DIARIO")
                        continue
                    print(f"  Alternativo {key_idx + 1}/{len(GEMINI_KEYS)} -- rate limit, probando siguiente...")
                    hubo_limite_minuto = True
                    continue
                if "404" in err or "NOT_FOUND" in err:
                    print(f"  ERROR: Modelo alternativo no encontrado.")
                    # No sobrescribir _ULTIMO_FALLO_LLM si OpenRouter ya registro algo
                    if _ULTIMO_FALLO_LLM is None:
                        _set_fallo_llm("openrouter", "modelo_no_disponible", "Proveedor de LLM no disponible. Reintentar mas tarde.")
                    return None
                print(f"  Alternativo {key_idx + 1}/{len(GEMINI_KEYS)} -- error: {err[:100]}")
                continue

        if not hubo_limite_minuto:
            print(f"  Todos los proveedores alternativos con limite DIARIO.")
            # No sobrescribir el motivo de OpenRouter (que es el que el usuario
            # ve en produccion). Solo registrar si no hay nada previo.
            if _ULTIMO_FALLO_LLM is None:
                _set_fallo_llm("openrouter", "cuota_agotada", "Cuota del proveedor de LLM agotada. Reintentar mas tarde o recargar saldo en https://openrouter.ai/credits.")
            break
        if intento < max_reintentos:
            print(f"  Esperando {espera_s}s antes de reintentar ({intento + 1}/{max_reintentos})...")
            time.sleep(espera_s)
        else:
            print(f"  Reintentos agotados tras {max_reintentos + 1} rondas.")
            if _ULTIMO_FALLO_LLM is None:
                _set_fallo_llm("openrouter", "rate_limit", "Limite de peticiones del proveedor de LLM alcanzado. Reintentar en unos minutos.")

    if _ULTIMO_FALLO_LLM is None:
        # Caso edge: ningun proveedor configurado en el .env
        if not OPENROUTER_KEY and not GEMINI_KEYS:
            _set_fallo_llm("ninguno", "sin_proveedor", "No hay ningun proveedor de LLM configurado. Definir OPENROUTER_API_KEY en las variables de entorno.")
    return None


def generar_propuesta_llm(formulario: FormularioCliente, openrouter_model: str | None = None) -> PropuestaEquipos:
    """
    EL CEREBRO: Usa LangChain + LLM (via OpenRouter) para generar la propuesta de equipos.

    Modo lista cliente (Excel/manual): si el formulario trae equipos en
    `necesidades_equipamiento`, esa lista es VINCULANTE — no se llama al LLM, se
    construye la propuesta respetando exactamente los equipos del cliente. Asi
    garantizamos que TODOS los equipos del Excel aparecen en el plano, sin que el
    LLM quite, anada o sustituya.

    Modo libre: si no hay lista del cliente, el LLM disena desde cero a partir
    del resto del formulario (comensales, tipo de negocio, identidad...).

    openrouter_model: Modelo de OpenRouter a usar.
    """
    # === Modo lista cliente: lista del Excel es vinculante ===
    # La IA NO puede tocar la lista de equipos (la lista del cliente manda) pero
    # SI se le pide enriquecer metadatos (layout, notas contextuales, nombre del
    # proyecto). Si la IA falla, queda la propuesta base con nota generica.
    eq = formulario.necesidades_equipamiento
    if any([eq.coccion, eq.refrigeracion, eq.lavado, eq.otros]):
        n_total = (len(eq.coccion) + len(eq.refrigeracion) + len(eq.lavado) + len(eq.otros))
        print(f"\n-- Modo lista cliente: respetando los {n_total} equipos del cliente --")
        propuesta_base = _construir_desde_lista_cliente(formulario)
        print("   Pidiendo a la IA layout + notas + nombre del proyecto...")
        return _enriquecer_con_llm(propuesta_base, formulario, openrouter_model)

    # === Modo libre: el LLM disena desde cero ===
    print("\n--Consultando reglas de diseño --")
    reglas = obtener_reglas_diseno(formulario)
    print(f"  Reglas cargadas para: {formulario.tipo_negocio}")

    print("\n--Consultando equipos disponibles en DB --")
    try:
        tipos_db = obtener_tipos_disponibles()
        print(f"  {tipos_db.count(chr(10)) + 1} tipos de equipo encontrados")
    except Exception:
        tipos_db = "  (No se pudo consultar la DB)"
        print("  WARN: No se pudo conectar a Supabase")

    # Intentar usar el LLM real
    print("\n-- Conectando con LLM --")

    # Prompt del sistema con toda la información
    system_prompt = f"""Eres un ingeniero experto en diseño de cocinas industriales para la empresa Repagas.
Tu trabajo es seleccionar los equipos necesarios para una cocina industrial.

REGLAS DE DISEÑO PARA ESTE TIPO DE NEGOCIO:
{reglas}

TIPOS DE EQUIPO DISPONIBLES EN BASE DE DATOS:
{tipos_db}

REGLAS DE SELECCIÓN:
- Solo usa tipos de equipo que existan en la lista anterior
- El campo 'tipo' debe coincidir EXACTAMENTE con los nombres de la lista
- Cada equipo de cocción debe tener un elemento neutro adyacente para apoyo
- Serie 750 (fondo 750mm) para espacios estándar; Serie 900 (fondo 900mm) para alta producción o alta cocina
- Para alimentación, usa exactamente "gas" o "electrico" (sin tilde)

REGLAS DE LAYOUT — elige el tipo de distribución más adecuado:
  * "lineal" — todo en una pared (espacios <20m²)
  * "L" — cocción en una pared + frío/lavado perpendicular (espacios 20-40m²)
  * "U" — tres paredes, máximo aprovechamiento (espacios 25-50m²)
  * "paralelo" — dos líneas enfrentadas con pasillo (espacios >35m²)

REGLAS SEGÚN PERFIL DEL CLIENTE:
- Si trabaja con quinta gama (platos listos para calentar), priorizar horno de regeneración
- Si trabaja con muchos ingredientes frescos, necesita más mesas refrigeradas de conservación
- Si trabaja con congelados, necesita armario o arcón de congelación
- Si la identidad es "alta_cocina" o "creativa", considerar Serie 900 y equipos premium
- Si es "buffet", considerar mesas calientes y baños maría
- Si la potencia eléctrica contratada es baja (<15kW), priorizar equipos a gas
- Si el acceso al local es estrecho (<90cm), evitar equipos de más de 800mm de ancho
- Si la altura del techo es <2.5m, no apilar hornos
- Dimensionar lavavajillas según cantidad de vajilla declarada (>200 piezas/servicio → capota)
- Dimensionar refrigeración según kg de producto declarados
- Más personas en cocina = más espacio de trabajo = más neutros y mesas de apoyo
"""

    # Construir secciones del user prompt solo con datos disponibles
    proy = formulario.proyecto
    _sec = []
    _sec.append(f"""DATOS BÁSICOS:
- Proyecto: {proy.nombre or proy.tipo_negocio}
- Tipo de negocio: {proy.tipo_negocio}{f' ({proy.concepto})' if proy.concepto else ''}
- Comensales: {proy.comensales}
- Superficie: {proy.superficie_m2 or 'no especificada'}m²
- Presupuesto: {'€{:,.0f}'.format(proy.presupuesto_max) if proy.presupuesto_max else 'sin límite'}
- Personas en cocina: {formulario.personal.personas_en_cocina or 'no especificado'}
- Roles: {', '.join(formulario.personal.roles) if formulario.personal.roles else 'no especificado'}""")

    ei = formulario.energia
    _sec.append(f"""ENERGÍA:
- Tipo principal: {ei.tipo_energia}
- Gas: {ei.tipo_gas or 'no especificado'}{f' (caudal: {ei.caudal_gas_disponible})' if ei.caudal_gas_disponible else ''}
- Eléctrico: {ei.tipo_electrico or 'no especificado'}
- Potencia contratada: {str(ei.potencia_contratada_kw) + 'kW' if ei.potencia_contratada_kw else 'no especificada'}""")

    ig = formulario.identidad_gastronomica
    _sec.append(f"""IDENTIDAD GASTRONÓMICA:
- Identidad: {ig.identidad or 'no especificada'}{f' ({ig.tipo_cocina})' if ig.tipo_cocina else ''}
- Menú: {', '.join(ig.estructura_menu) or 'no especificado'}
- Nº platos en carta: {ig.cantidad_platos or 'no especificado'}
- Ingredientes frescos: {', '.join(ig.ingredientes_frescos) or 'no especificado'}
- Ingredientes congelados: {', '.join(ig.ingredientes_congelados) or 'no especificado'}
- Cuarta gama: {', '.join(ig.cuarta_gama) or 'no'}
- Quinta gama: {', '.join(ig.quinta_gama) or 'no'}""")

    ti = formulario.parte_tecnica
    accesos_str = 'no especificado'
    if ti.dimensiones_accesos:
        accesos_str = ', '.join(f"{k}: {v}m" for k, v in ti.dimensiones_accesos.items())
    _sec.append(f"""INFRAESTRUCTURA:
- {'Renovación' + (' (retirar antigua)' if ti.retirar_cocina_antigua else '') if ti.tipo_proyecto == 'renovacion' else 'Instalación nueva'}
- Plano técnico: {'sí' if ti.existe_plano_tecnico else 'no'}
- Altura techo: {str(ti.altura_suelo_techo_m) + 'm' if ti.altura_suelo_techo_m else 'no especificada'}
- Paredes: {', '.join(ti.material_paredes) or 'no especificado'}
- Suelo: {ti.material_suelo or 'no especificado'}{' (con desniveles: ' + ti.desniveles_suelo.detalle + ')' if ti.desniveles_suelo.existe and ti.desniveles_suelo.detalle else ''}
- Accesos: {accesos_str}""")

    li = formulario.lavado
    if any([li.platos, li.vasos, li.copas, li.cubiertos]):
        _sec.append(f"""VAJILLA POR SERVICIO:
- Platos: {li.platos or '?'}, Vasos: {li.vasos or '?'}, Copas: {li.copas or '?'}
- Cubiertos: {li.cubiertos or '?'}, Tazas: {li.tazas or '?'}
- Otros: {', '.join(li.otros_utensilios) or 'no'}
- Consideraciones: {', '.join(li.consideraciones) or 'ninguna'}""")

    ri = formulario.refrigeracion
    if any([ri.primera_gama.kg_aproximados, ri.tercera_gama.kg_aproximados, ri.cuarta_gama.kg_aproximados]):
        _sec.append(f"""ALMACENAMIENTO:
- 1ª gama (frescos): {', '.join(ri.primera_gama.productos) or '?'} — {ri.primera_gama.kg_aproximados or '?'}kg
- 2ª gama (conservas): {', '.join(ri.segunda_gama.productos) or '?'} — estanterías: {'sí' if ri.segunda_gama.necesita_estanterias else 'no'}
- 3ª gama (congelados): {', '.join(ri.tercera_gama.productos) or '?'} — {ri.tercera_gama.kg_aproximados or '?'}kg
- 4ª gama: {', '.join(ri.cuarta_gama.productos) or '?'} — {ri.cuarta_gama.kg_aproximados or '?'}kg
- 5ª gama: {', '.join(ri.quinta_gama.productos) or 'no'}""")

    neq = formulario.necesidades_equipamiento
    if any([neq.coccion, neq.refrigeracion, neq.lavado, neq.otros]):
        _sec.append(f"""EQUIPAMIENTO SOLICITADO:
- Cocción: {', '.join(neq.coccion) or 'a determinar'}
- Refrigeración: {', '.join(neq.refrigeracion) or 'a determinar'}
- Lavado: {', '.join(neq.lavado) or 'a determinar'}
- Otros: {', '.join(neq.otros) or 'ninguno'}
- Marcas preferidas: {', '.join(neq.marcas_preferidas) or 'sin preferencia'}""")

    if neq.preferencias_colocacion:
        _sec.append(f"PREFERENCIAS DE COLOCACIÓN: {neq.preferencias_colocacion}")

    user_prompt = "Diseña la cocina industrial para este cliente:\n\n" + "\n\n".join(_sec)
    user_prompt += f"""

Responde SOLO con un JSON válido que siga exactamente este schema Pydantic:
{json.dumps(PropuestaEquipos.model_json_schema(), indent=2, ensure_ascii=False)}

Recuerda: el campo "tipo" de cada equipo DEBE ser uno de los tipos disponibles en la DB.
"""

    print("  Generando propuesta con IA...")
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "human", "content": user_prompt},
    ]
    propuesta = invocar_llm_con_rotacion(messages, structured_cls=PropuestaEquipos, openrouter_model=openrouter_model)

    if propuesta is None:
        print("  WARN: Todas las API keys agotadas -- usando fallback dummy")
        return _propuesta_fallback(formulario)

    print(f"  Propuesta generada: {propuesta.nombre_proyecto}")
    return propuesta


def _propuesta_fallback(formulario: FormularioCliente) -> PropuestaEquipos:
    """
    Fallback usado solo cuando el LLM falla en modo libre (no hay lista del cliente).
    Si por algun motivo se llega aqui con lista del cliente, igualmente la respetamos.
    """
    eq = formulario.necesidades_equipamiento
    if any([eq.coccion, eq.refrigeracion, eq.lavado, eq.otros]):
        return _construir_desde_lista_cliente(formulario)
    return _fallback_generico(formulario)


# Mapeo de nombres del cliente (Excel/formulario) a tipos canonicos del catalogo.
# Orden de las claves importa: patrones especificos antes que genericos.
_TIPO_PATRONES = (
    ("lavavajillas",                            "lavavajillas"),
    ("fry top",                                 "fry_top_gas"),
    ("fry-top",                                 "fry_top_gas"),
    ("freidora",                                "freidora_gas"),
    ("paellero",                                "paellero"),
    ("barbacoa",                                "barbacoa"),
    ("parrilla",                                "barbacoa"),
    ("plancha",                                 "plancha"),
    ("horno",                                   "horno_combinado"),
    ("campana",                                 "campana"),
    ("extractor",                               "campana"),
    ("mesa refrig",                             "mesa_refrig_conservacion"),
    ("mesa refrigerada",                        "mesa_refrig_conservacion"),
    ("armario congel",                          "armario_congelacion"),
    ("armario cong",                            "armario_congelacion"),
    ("armario conserv",                         "armario_refrigeracion"),
    ("armario refrig",                          "armario_refrigeracion"),
    ("armario",                                 "armario_refrigeracion"),
    ("mesa prelavado",                          "mesa_lavado"),
    ("mesa lavado",                             "mesa_lavado"),
    ("mesa salida",                             "mesa_lavado"),
    ("mesa mural inox con seno",                "mesa_lavado"),
    ("seno",                                    "mesa_lavado"),
    ("estanter",                                "estanteria"),
    ("cocina",                                  "cocina_gas"),
    ("fuego",                                   "cocina_gas"),
    ("neutro",                                  "neutro"),
    ("soporte",                                 "mesa_neutra"),
    ("mesa",                                    "mesa_neutra"),
)


def _clasificar_equipo(nombre: str) -> str:
    """Mapea un nombre libre (p.ej. del Excel del cliente) a un tipo canonico
    que el resolver puede buscar en el catalogo Repagas."""
    n = nombre.lower()
    for patron, tipo in _TIPO_PATRONES:
        if patron in n:
            return tipo
    return "otro"


def _alimentacion_para(tipo: str, es_gas: bool) -> str:
    """Determina alimentacion segun el tipo y la energia principal del local."""
    tipos_gas = {"cocina_gas", "freidora_gas", "fry_top_gas", "paellero", "barbacoa"}
    if tipo in tipos_gas and es_gas:
        return "gas"
    return "electrico"


def _nota_motivo_llm() -> str:
    """Construye un sufijo legible para las notas explicando por que cayo al fallback."""
    f = obtener_ultimo_fallo_llm()
    if not f:
        return ""
    return f" [LLM no disponible — {f['proveedor']}/{f['motivo']}: {f['detalle']}]"


def _enriquecer_con_llm(
    propuesta_base: PropuestaEquipos,
    formulario: FormularioCliente,
    openrouter_model: str | None = None,
) -> PropuestaEquipos:
    """Pide al LLM solo metadatos contextuales (layout, notas, nombre del proyecto)
    a partir de una propuesta YA construida con la lista del cliente. La IA NO puede
    tocar la lista de equipos: el schema devuelto solo contiene los tres campos.

    Si la IA falla (sin saldo, rate limit, error), se devuelve la propuesta base
    intacta con su nota generica.
    """
    from pydantic import BaseModel, Field as PField

    class EnriquecimientoPropuesta(BaseModel):
        """Lo unico que el LLM puede decidir en modo lista cliente."""
        layout: str = PField(
            description='Tipo de distribucion: "lineal" | "L" | "U" | "paralelo"'
        )
        nombre_proyecto: str = PField(
            description="Nombre descriptivo del proyecto (max 70 caracteres)"
        )
        notas: str = PField(
            description="2-3 frases con recomendaciones de disposicion/serie/energia para esta cocina"
        )

    # Resumen breve de la lista del cliente para el prompt
    def _resumen(items):
        if not items:
            return "(ninguno)"
        nombres = [(e.razon or e.tipo) for e in items]
        if len(nombres) <= 6:
            return ", ".join(nombres)
        return ", ".join(nombres[:6]) + f"... (+{len(nombres) - 6} mas)"

    proy = formulario.proyecto
    ig = formulario.identidad_gastronomica
    n_total = (
        len(propuesta_base.zona_coccion)
        + len(propuesta_base.zona_frio)
        + len(propuesta_base.zona_lavado)
        + len(propuesta_base.zona_horno)
    )

    system_msg = (
        "Eres un ingeniero experto en cocinas industriales para Repagas. "
        "Recibes una lista de equipos YA DEFINIDA por el cliente. Tu trabajo es decidir el "
        "layout, escribir un nombre descriptivo del proyecto y unas notas con recomendaciones. "
        "BAJO NINGUN CONCEPTO debes anadir, quitar o sustituir equipos: esa lista es vinculante. "
        "Devuelve unicamente los tres campos del schema (layout, nombre_proyecto, notas)."
    )

    user_msg = f"""CONTEXTO DEL PROYECTO:
- Proyecto: {proy.nombre or "sin nombre"}
- Tipo de negocio: {proy.tipo_negocio}{f' ({proy.concepto})' if proy.concepto else ''}
- Comensales: {proy.comensales}
- Superficie: {proy.superficie_m2 or 'no especificada'} m2
- Identidad gastronomica: {ig.identidad or 'no especificada'}{f' ({ig.tipo_cocina})' if ig.tipo_cocina else ''}
- Energia: {formulario.energia.tipo_energia}{f' ({formulario.energia.tipo_gas})' if formulario.energia.tipo_gas else ''}

LISTA DE EQUIPOS (DEFINIDA POR EL CLIENTE — NO MODIFICAR, total {n_total} equipos):
- Coccion: {_resumen(propuesta_base.zona_coccion)}
- Frio:    {_resumen(propuesta_base.zona_frio)}
- Lavado:  {_resumen(propuesta_base.zona_lavado)}
- Horno:   {_resumen(propuesta_base.zona_horno)}

LAYOUTS DISPONIBLES:
- "lineal"   — todo en una pared (espacios <20m2)
- "L"        — coccion en una pared + frio/lavado perpendicular (20-40m2)
- "U"        — tres paredes (25-50m2)
- "paralelo" — dos lineas enfrentadas con pasillo (>35m2)

Devuelve JSON con:
- layout: uno de los cuatro tipos
- nombre_proyecto: nombre descriptivo (max 70 chars)
- notas: 2-3 frases con recomendaciones sobre serie Repagas (750 o 900), disposicion y energia
"""

    messages = [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": user_msg},
    ]

    try:
        enriquecimiento = invocar_llm_con_rotacion(
            messages,
            structured_cls=EnriquecimientoPropuesta,
            openrouter_model=openrouter_model,
        )
    except Exception as e:
        print(f"   WARN: enriquecimiento fallo ({type(e).__name__}: {str(e)[:120]}); uso propuesta base")
        return propuesta_base

    if enriquecimiento is None:
        print("   WARN: LLM no respondio; uso propuesta base sin enriquecer")
        return propuesta_base

    # Sustituir solo los 3 campos enriquecidos; equipos quedan intactos
    print(f"   Enriquecido por IA: layout={enriquecimiento.layout!r}, "
          f"proyecto={enriquecimiento.nombre_proyecto[:40]!r}")
    return PropuestaEquipos(
        nombre_proyecto=enriquecimiento.nombre_proyecto[:200],
        layout=enriquecimiento.layout,
        zona_coccion=propuesta_base.zona_coccion,
        zona_frio=propuesta_base.zona_frio,
        zona_lavado=propuesta_base.zona_lavado,
        zona_horno=propuesta_base.zona_horno,
        notas=enriquecimiento.notas,
    )


def _construir_desde_lista_cliente(formulario: FormularioCliente) -> PropuestaEquipos:
    """Construye una propuesta respetando exactamente la lista de equipos que el
    cliente aporto en el formulario (tipicamente importados desde su Excel).

    Esta NO es una funcion de fallback: es el modo principal cuando hay datos del
    cliente. Garantiza que TODOS los equipos del cliente aparezcan en el plano,
    en sus zonas correspondientes, sin que un LLM los modifique."""
    eq = formulario.necesidades_equipamiento
    es_gas = formulario.energia_principal in ("gas", "mixto")

    def to_equipos(nombres):
        items = []
        for n in nombres:
            n = (n or "").strip()
            if not n:
                continue
            t = _clasificar_equipo(n)
            items.append(EquipoSeleccionado(
                tipo=t,
                cantidad=1,
                alimentacion=_alimentacion_para(t, es_gas),
                ancho_mm_preferido=None,
                razon=n,  # nombre original; el resolver hace match flexible contra el catalogo
            ))
        return items

    zona_coccion = to_equipos(eq.coccion) + to_equipos(eq.otros)
    zona_frio = to_equipos(eq.refrigeracion)
    zona_lavado = to_equipos(eq.lavado)

    # Si hay hornos clasificados dentro de coccion, mover a zona_horno
    zona_horno = [e for e in zona_coccion if e.tipo == "horno_combinado"]
    zona_coccion = [e for e in zona_coccion if e.tipo != "horno_combinado"]

    identidad = formulario.identidad_gastronomica.identidad or ""
    serie_nota = "Serie 900" if identidad in ("alta_cocina", "creativa") else "Serie 750"
    n_total = len(zona_coccion) + len(zona_frio) + len(zona_lavado) + len(zona_horno)

    # Si esta funcion se invoca como parte de un fallback (porque el LLM en modo
    # libre fallo) propagamos el motivo. Si se invoca en modo lista cliente
    # deliberado, no hay motivo de fallo y la nota es positiva.
    motivo_extra = _nota_motivo_llm()
    if motivo_extra:
        notas = (
            f"Propuesta basada en los {n_total} equipos aportados por el cliente "
            f"(no se pudo consultar al LLM). {serie_nota} Repagas. "
            f"Energía: {formulario.energia_principal}.{motivo_extra}"
        )
    else:
        notas = (
            f"Propuesta basada en la lista de {n_total} equipos aportada por el cliente. "
            f"{serie_nota} Repagas. Energía: {formulario.energia_principal}."
        )

    return PropuestaEquipos(
        nombre_proyecto=f"Cocina {formulario.tipo_negocio.replace('_', ' ').title()} — {formulario.comensales} comensales",
        zona_coccion=zona_coccion,
        zona_frio=zona_frio,
        zona_lavado=zona_lavado,
        zona_horno=zona_horno,
        notas=notas,
    )


def _fallback_generico(formulario: FormularioCliente) -> PropuestaEquipos:
    """Plantilla generica cuando no hay datos del cliente: reglas por comensales,
    tipo de negocio e identidad."""
    c = formulario.comensales
    es_gas = formulario.energia_principal in ("gas", "mixto")
    tipo_cocina = "cocina_gas" if es_gas else "cocina_gas"
    tipo_fry = "fry_top_gas" if es_gas else "fry_top_gas"
    tipo_freidora = "freidora_gas" if es_gas else "freidora_gas"
    identidad = formulario.identidad_gastronomica.identidad or ""

    # Zona de cocción: escalar según comensales y tipo
    zona_coccion = []

    if formulario.tipo_negocio == "fast_food":
        zona_coccion = [
            EquipoSeleccionado(tipo=tipo_freidora, cantidad=2, alimentacion="gas", ancho_mm_preferido=400, razon=f"Doble freidora para {c} comensales fast food"),
            EquipoSeleccionado(tipo="neutro", cantidad=1, alimentacion="gas", ancho_mm_preferido=400, razon="Apoyo entre freidoras y plancha"),
            EquipoSeleccionado(tipo="plancha", cantidad=1, alimentacion="gas", ancho_mm_preferido=800, razon="Plancha para hamburguesas y sandwiches"),
            EquipoSeleccionado(tipo="neutro", cantidad=1, alimentacion="gas", ancho_mm_preferido=400, razon="Apoyo lateral"),
        ]
    else:
        n_fuegos = 1 if c <= 50 else (2 if c <= 150 else 3)
        # Alta cocina / creativa: Serie 900 (ancho 800)
        ancho = 800 if identidad in ("alta_cocina", "creativa") else 800
        zona_coccion.append(EquipoSeleccionado(
            tipo=tipo_cocina, cantidad=n_fuegos, alimentacion="gas",
            ancho_mm_preferido=ancho, razon=f"Cocina gas {n_fuegos}x para {c} comensales"
        ))
        zona_coccion.append(EquipoSeleccionado(
            tipo="neutro", cantidad=1, alimentacion="gas",
            ancho_mm_preferido=400, razon="Elemento neutro de apoyo"
        ))
        zona_coccion.append(EquipoSeleccionado(
            tipo=tipo_fry, cantidad=1, alimentacion="gas",
            ancho_mm_preferido=800, razon="Fry-top para planchas y salteados"
        ))
        zona_coccion.append(EquipoSeleccionado(
            tipo="neutro", cantidad=1, alimentacion="gas",
            ancho_mm_preferido=400, razon="Elemento neutro de apoyo"
        ))
        zona_coccion.append(EquipoSeleccionado(
            tipo=tipo_freidora, cantidad=1 if c <= 100 else 2, alimentacion="gas",
            ancho_mm_preferido=400, razon=f"Freidora para {c} comensales"
        ))

    # Zona frío — más refrigeración si trabaja con frescos
    zona_frio = [
        EquipoSeleccionado(
            tipo="mesa_refrig_conservacion", cantidad=1, alimentacion="electrico",
            razon="Mesa refrigerada para mise en place"
        ),
    ]
    if formulario.identidad_gastronomica.ingredientes_congelados:
        zona_frio.append(EquipoSeleccionado(
            tipo="armario_congelacion", cantidad=1, alimentacion="electrico",
            razon=f"Armario congelación para: {', '.join(formulario.identidad_gastronomica.ingredientes_congelados)}"
        ))

    # Zona lavado
    zona_lavado = [
        EquipoSeleccionado(
            tipo="lavavajillas", cantidad=1, alimentacion="electrico",
            razon=f"Lavavajillas para {c} comensales"
        ),
    ]

    # Zona horno — añadir horno regeneración si quinta gama
    zona_horno = [
        EquipoSeleccionado(
            tipo="horno_combinado", cantidad=1, alimentacion="electrico",
            razon=f"Horno combinado para {c} comensales"
        ),
    ]

    # Serie según identidad
    serie_nota = "Serie 900" if identidad in ("alta_cocina", "creativa") else "Serie 750"

    return PropuestaEquipos(
        nombre_proyecto=f"Cocina {formulario.tipo_negocio.replace('_', ' ').title()} — {c} comensales",
        zona_coccion=zona_coccion,
        zona_frio=zona_frio,
        zona_lavado=zona_lavado,
        zona_horno=zona_horno,
        notas=(
            f"Propuesta generada por fallback (sin LLM). {serie_nota} Repagas. "
            f"Energía: {formulario.energia_principal}.{_nota_motivo_llm()}"
        ),
    )


# --───────────────────────────────────────────
# 4.  EL MÚSCULO GEOMÉTRICO — ezdxf para DXF
# --───────────────────────────────────────────

# --───────────────────────────────────────────
# PLANTILLAS DE LAYOUT — basadas en planos reales analizados
# Cada zona tiene: (start_x, start_y, dirección)
#   "auto" = continúa tras la zona anterior en el mismo tramo
#   "end"  = empieza donde terminó la primera zona (esquina del L/U)
# Dirección: "X" = izq→der, "-X" = der→izq, "Y" = abajo→arriba, "-Y" = arriba→abajo
# --───────────────────────────────────────────

LAYOUTS = {
    "lineal": {
        "coccion": (0, 0, "X"),
        "frio":    ("auto", 0, "X"),
        "lavado":  ("auto", 0, "X"),
        "horno":   ("auto", 0, "X"),
    },
    "l": {
        "coccion": (0, 0, "X"),           # Tramo horizontal (pared superior)
        "frio":    ("end", 0, "-Y"),       # Gira 90° hacia abajo desde la esquina
        "lavado":  ("auto", 0, "-Y"),      # Continúa vertical
        "horno":   ("auto", 0, "-Y"),      # Al final del tramo vertical
    },
    "u": {
        "coccion": (0, 0, "X"),            # Tramo horizontal superior
        "frio":    ("end", 0, "-Y"),       # Baja por la derecha
        "lavado":  ("end_u", 0, "-X"),     # Vuelve horizontal por abajo
        "horno":   ("auto", 0, "-X"),      # Continúa en el tramo inferior
    },
    "paralelo": {
        "coccion": (0, 0, "X"),            # Línea superior
        "frio":    (0, -2500, "X"),        # Línea inferior (pasillo ~1500mm + fondo equipo)
        "lavado":  ("auto", -2500, "X"),   # Continúa línea inferior
        "horno":   ("auto", -2500, "X"),
    },
}

# Colores por zona de layout
COLORES_ZONA_LAYOUT = {
    "coccion": 1,   # Rojo
    "frio":    4,   # Cyan
    "lavado":  5,   # Azul
    "horno":   30,  # Naranja
}

# Colores AutoCAD DXF por zona
COLORES_ZONA = {
    "cocina_gas": 1,          # Rojo — fuego
    "fry_top_gas": 1,         # Rojo
    "freidora_gas": 1,        # Rojo
    "plancha": 1,             # Rojo
    "marmita": 1,             # Rojo
    "bano_maria": 1,          # Rojo
    "cuece_pastas": 1,        # Rojo
    "barbacoa": 1,            # Rojo
    "neutro": 8,              # Gris — neutro
    "soporte": 8,             # Gris
    "mesa_trabajo": 8,        # Gris
    "horno_combinado": 30,    # Naranja — hornos
    "lavavajillas": 5,        # Azul — lavado
    "lavautensilios": 5,      # Azul
    "mesa_refrig_conservacion": 4,     # Cyan — frío
    "mesa_refrig_congelacion": 4,      # Cyan
    "armario_conservacion": 4,         # Cyan
    "armario_congelacion": 4,          # Cyan
}


