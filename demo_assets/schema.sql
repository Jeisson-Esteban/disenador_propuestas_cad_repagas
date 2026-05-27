-- ============================================================================
-- Schema demo de la base de datos para el pipeline de diseno de cocinas.
-- Compatible con PostgreSQL 15+ y pgvector (para el RAG semantico).
--
-- IMPORTANTE: los equipos cargados en el seed son ficticios. La marca
-- "AcmeKitchen" y los modelos (AK-COC-750-001, etc.) no representan a ninguna
-- empresa real. En el sistema de produccion de Repagas, esta tabla se
-- alimenta con el catalogo real de equipos.
--
-- Uso:
--   1. Crea la base de datos: createdb kitchen_demo
--   2. Activa pgvector:        psql kitchen_demo -c "CREATE EXTENSION vector;"
--   3. Carga este schema:      psql kitchen_demo < demo_assets/schema.sql
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ─── Catalogo de equipos ────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS marcas (
    id          SERIAL PRIMARY KEY,
    nombre      TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS series (
    id          SERIAL PRIMARY KEY,
    marca_id    INTEGER REFERENCES marcas(id),
    nombre      TEXT NOT NULL,
    catalogo_pdf TEXT,
    UNIQUE (marca_id, nombre)
);

CREATE TABLE IF NOT EXISTS categorias_equipo (
    id          SERIAL PRIMARY KEY,
    nombre      TEXT NOT NULL UNIQUE,
    zona        TEXT NOT NULL  -- coccion | lavado | frio | horno
);

CREATE TABLE IF NOT EXISTS equipos (
    id              SERIAL PRIMARY KEY,
    modelo          TEXT NOT NULL,
    tipo            TEXT NOT NULL,
    alimentacion    TEXT,                   -- gas | electrico | manual
    ancho_mm        INTEGER,
    fondo_mm        INTEGER,
    alto_mm         INTEGER,
    pvp_eur         NUMERIC(10, 2),
    serie_id        INTEGER REFERENCES series(id),
    bloque_cad      TEXT,                   -- nombre del bloque en la libreria DXF
    foto_url        TEXT,
    activo          BOOLEAN DEFAULT TRUE,
    creado_en       TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_equipos_tipo ON equipos(tipo);
CREATE INDEX IF NOT EXISTS idx_equipos_serie ON equipos(serie_id);

-- ─── Historico de propuestas generadas ──────────────────────────────────────

CREATE TABLE IF NOT EXISTS historico_propuestas (
    id              SERIAL PRIMARY KEY,
    nombre_proyecto TEXT,
    tipo_negocio    TEXT,
    comensales      INTEGER,
    total_equipos   INTEGER,
    total_pvp_eur   NUMERIC(12, 2),
    layout          TEXT,
    notas_llm       TEXT,
    formulario      JSONB,
    propuesta       JSONB,
    equipos         JSONB,
    creado_en       TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_historico_creado ON historico_propuestas(creado_en DESC);

-- ─── Feedback del usuario (chat de cambios post-generacion) ─────────────────

CREATE TABLE IF NOT EXISTS feedback (
    id              SERIAL PRIMARY KEY,
    mensaje         TEXT,
    proyecto        TEXT,
    creado_en       TIMESTAMPTZ DEFAULT NOW()
);

-- ─── Textos configurables de los PDFs ───────────────────────────────────────

CREATE TABLE IF NOT EXISTS textos_config (
    clave           TEXT PRIMARY KEY,
    valor           TEXT,
    actualizado_en  TIMESTAMPTZ DEFAULT NOW()
);

-- ─── RAG (busqueda semantica sobre catalogos/manuales) ──────────────────────

CREATE TABLE IF NOT EXISTS documentos_rag (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    titulo          TEXT NOT NULL,
    tipo_archivo    TEXT,
    categoria       TEXT,
    ruta_origen     TEXT,
    num_chunks      INTEGER DEFAULT 0,
    procesado       BOOLEAN DEFAULT FALSE,
    creado_en       TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS chunks_rag (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    documento_id    UUID REFERENCES documentos_rag(id) ON DELETE CASCADE,
    chunk_index     INTEGER,
    contenido       TEXT,
    embedding       vector(768),    -- gemini-embedding-001 = 768 dims
    metadata        JSONB,
    creado_en       TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chunks_embedding
    ON chunks_rag USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- ============================================================================
-- SEED DATA: marcas, series, categorias y 40 equipos ficticios.
-- Estos equipos NO existen en la realidad. La marca "AcmeKitchen" es inventada
-- para no exponer el catalogo real del software de produccion.
-- ============================================================================

INSERT INTO marcas (id, nombre) VALUES
    (1, 'AcmeKitchen')
ON CONFLICT DO NOTHING;

INSERT INTO series (id, marca_id, nombre, catalogo_pdf) VALUES
    (1, 1, 'Serie 750', NULL),
    (2, 1, 'Serie 900', NULL)
ON CONFLICT DO NOTHING;

INSERT INTO categorias_equipo (nombre, zona) VALUES
    ('Coccion gas',         'coccion'),
    ('Coccion electrico',   'coccion'),
    ('Refrigeracion',       'frio'),
    ('Lavado',              'lavado'),
    ('Horneado',            'horno')
ON CONFLICT DO NOTHING;

-- ─── 40 equipos ficticios ───────────────────────────────────────────────────
INSERT INTO equipos (modelo, tipo, alimentacion, ancho_mm, fondo_mm, alto_mm, pvp_eur, serie_id, bloque_cad) VALUES
    -- Coccion gas Serie 750
    ('AK-COC-750-001', 'cocina_gas',       'gas',        400, 750, 900, 2300, 1, 'COC_GAS_400'),
    ('AK-COC-750-002', 'cocina_gas',       'gas',        800, 750, 900, 3800, 1, 'COC_GAS_800'),
    ('AK-FRY-750-001', 'fry_top_gas',      'gas',        400, 750, 900, 1700, 1, 'FRY_GAS_400'),
    ('AK-FRY-750-002', 'fry_top_gas',      'gas',        800, 750, 900, 2900, 1, 'FRY_GAS_800'),
    ('AK-BAR-750-001', 'barbacoa',         'gas',        400, 750, 900, 2100, 1, 'BAR_400'),
    ('AK-BAR-750-002', 'barbacoa',         'gas',        800, 750, 900, 3600, 1, 'BAR_800'),
    ('AK-FRD-750-001', 'freidora_gas',     'gas',        400, 750, 900, 1800, 1, 'FRD_GAS_400'),
    ('AK-FRD-750-002', 'freidora_gas',     'gas',        800, 750, 900, 3100, 1, 'FRD_GAS_800'),
    ('AK-PAE-750-001', 'paellero',         'gas',        400, 750, 900, 2200, 1, 'PAE_400'),
    ('AK-PAE-750-002', 'paellero',         'gas',        800, 750, 900, 3700, 1, 'PAE_800'),
    -- Coccion electrica Serie 750
    ('AK-COC-750-E01', 'cocina_electrica', 'electrico',  400, 750, 900, 2500, 1, 'COC_ELE_400'),
    ('AK-FRY-750-E01', 'fry_top_electrico','electrico',  400, 750, 900, 1900, 1, 'FRY_ELE_400'),
    ('AK-FRD-750-E01', 'freidora_electrica','electrico', 400, 750, 900, 2000, 1, 'FRD_ELE_400'),
    ('AK-PLA-750-001', 'plancha',          'electrico',  400, 750, 900, 1500, 1, 'PLA_400'),
    -- Coccion Serie 900 (proyectos grandes)
    ('AK-COC-900-001', 'cocina_gas',       'gas',        800, 900, 900, 4500, 2, 'COC_GAS_800_900'),
    ('AK-FRY-900-001', 'fry_top_gas',      'gas',        800, 900, 900, 3300, 2, 'FRY_GAS_800_900'),
    ('AK-BAR-900-001', 'barbacoa',         'gas',        800, 900, 900, 4100, 2, 'BAR_800_900'),
    ('AK-FRD-900-001', 'freidora_gas',     'gas',        800, 900, 900, 3500, 2, 'FRD_GAS_800_900'),
    -- Horneado
    ('AK-HRN-001',     'horno',            'gas',        900, 900, 1700, 6800, 1, 'HRN_GAS'),
    ('AK-HRN-E01',     'horno',            'electrico',  900, 900, 1700, 7400, 1, 'HRN_ELE'),
    ('AK-HRN-CMB-001', 'horno_combinado',  'electrico',  900, 900, 1700, 9200, 1, 'HRN_CMB'),
    ('AK-HRN-MQ-001',  'horno_microondas', 'electrico',  600, 500,  400,  450, 1, 'HRN_MQ'),
    -- Refrigeracion
    ('AK-ARM-CON-001', 'armario_conservacion', 'electrico', 740, 730, 2100, 1900, 1, 'ARM_CON_1P'),
    ('AK-ARM-CON-002', 'armario_conservacion', 'electrico', 1440, 730, 2100, 3100, 1, 'ARM_CON_2P'),
    ('AK-ARM-CNG-001', 'armario_congelacion',  'electrico', 740, 730, 2100, 2400, 1, 'ARM_CNG_1P'),
    ('AK-ARM-CNG-002', 'armario_congelacion',  'electrico', 1440, 730, 2100, 3800, 1, 'ARM_CNG_2P'),
    ('AK-MSR-001',     'mesa_refrigerada',     'electrico', 1500, 700, 850, 1800, 1, 'MSR_1500'),
    ('AK-MSR-002',     'mesa_refrigerada',     'electrico', 2000, 700, 850, 2400, 1, 'MSR_2000'),
    ('AK-VIT-001',     'vitrina_refrigerada',  'electrico', 900,  600, 850, 1500, 1, 'VIT_900'),
    -- Lavado
    ('AK-LAV-001',     'lavavajillas',     'electrico',  600, 770, 1450, 3000, 1, 'LAV_FRONTAL'),
    ('AK-LAV-CAP-001', 'lavavajillas',     'electrico',  720, 850, 2000, 5400, 1, 'LAV_CAPOTA'),
    ('AK-LVS-001',     'lavavasos',        'electrico',  470, 530,  720,  900, 1, 'LVS_FRONTAL'),
    ('AK-FRG-001',     'fregadero',        'manual',     500, 700,  850,  350, 1, 'FRG_1SENO'),
    ('AK-FRG-002',     'fregadero',        'manual',    1000, 700,  850,  650, 1, 'FRG_2SENOS'),
    ('AK-MSE-001',     'mesa_entrada',     'manual',    1000, 700,  850,  450, 1, 'MSE_1000'),
    ('AK-MSS-001',     'mesa_salida',      'manual',    1000, 700,  850,  450, 1, 'MSS_1000'),
    -- Mesas y mobiliario
    ('AK-MML-001',     'mesa_mural',       'manual',    1000, 600,  850,  300, 1, 'MML_1000'),
    ('AK-MML-002',     'mesa_mural',       'manual',    1500, 600,  850,  400, 1, 'MML_1500'),
    ('AK-EST-001',     'estanteria',       'manual',     900, 400, 1800,  280, 1, 'EST_900'),
    -- Botellero
    ('AK-BTL-001',     'botellero',        'electrico', 1500, 550,  850, 1100, 1, 'BTL_1500')
ON CONFLICT DO NOTHING;

-- ─── Textos editables de los PDFs ───────────────────────────────────────────

INSERT INTO textos_config (clave, valor) VALUES
    ('prospeccion_intro',
     'Documento generado automaticamente — version simplificada del software de Repagas.'),
    ('prospeccion_cierre',
     'Este documento sirve como punto de partida del proyecto. Incluye una radiografia tecnica y operativa que sera utilizada para ofrecer una propuesta alineada con las necesidades del proyecto.'),
    ('prospeccion_firma',
     'Es indispensable visarlo y firmarlo para confirmar conformidad.'),
    ('presupuesto_intro',
     'Presupuesto orientativo. Precios en EUR sin incluir transporte ni instalacion salvo indicacion contraria.'),
    ('presupuesto_condiciones',
     'Validez: 30 dias desde la fecha de emision. Condiciones de pago: 50% a la confirmacion del pedido, 50% a la entrega. Plazo de entrega estimado: consultar.'),
    ('presupuesto_iva_porcent', '21'),
    ('presupuesto_validez_dias', '30')
ON CONFLICT (clave) DO NOTHING;

-- ─── Listo ──────────────────────────────────────────────────────────────────
-- 40 equipos ficticios + 7 textos de PDF + tablas RAG vacias (carga documentos
-- via /admin/rag/upload).
