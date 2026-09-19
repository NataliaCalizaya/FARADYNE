-- FARADYNE Database DDL Reference
-- Base de datos: faradyne
-- PostgreSQL 13+

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 1. Tabla proyecto
CREATE TABLE IF NOT EXISTS proyecto (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    nombre VARCHAR(255) NOT NULL,
    descripcion TEXT,
    ubicacion VARCHAR(500),
    departamento VARCHAR(100),
    provincia VARCHAR(100),
    distrito VARCHAR(100),
    estado VARCHAR(50) DEFAULT 'borrador',
    fecha_creacion TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    fecha_actualizacion TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 2. Tabla plano
CREATE TABLE IF NOT EXISTS plano (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    id_proyecto UUID NOT NULL REFERENCES proyecto(id) ON DELETE CASCADE,
    nombre_archivo VARCHAR(500) NOT NULL,
    tipo_archivo VARCHAR(50) NOT NULL, -- dxf, pdf
    ruta_archivo VARCHAR(1000) NOT NULL,
    tamano_bytes BIGINT NOT NULL,
    metadatos JSONB DEFAULT '{}',
    fecha_creacion TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 3. Tabla zona_ceraunica
CREATE TABLE IF NOT EXISTS zona_ceraunica (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    departamento VARCHAR(100) NOT NULL,
    provincia VARCHAR(100),
    nivel_ceraunico_td FLOAT NOT NULL DEFAULT 30.0, -- días de tormenta al año (Td)
    densidad_rayos_ng FLOAT NOT NULL DEFAULT 2.5,   -- descargas/km²/año (Ng = 0.04 * Td^1.25)
    descripcion VARCHAR(255)
);

-- 4. Tabla modelo2d
CREATE TABLE IF NOT EXISTS modelo2d (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    id_plano UUID NOT NULL REFERENCES plano(id) ON DELETE CASCADE,
    id_proyecto UUID NOT NULL REFERENCES proyecto(id) ON DELETE CASCADE,
    poligonos JSONB DEFAULT '[]',
    capas JSONB DEFAULT '[]',
    cotas_altura JSONB DEFAULT '[]',
    entidades_geom JSONB DEFAULT '{}',
    fecha_creacion TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 5. Tabla modelo3d
CREATE TABLE IF NOT EXISTS modelo3d (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    id_modelo2d UUID NOT NULL REFERENCES modelo2d(id) ON DELETE CASCADE,
    id_proyecto UUID NOT NULL REFERENCES proyecto(id) ON DELETE CASCADE,
    geometria_volumetrica JSONB NOT NULL DEFAULT '{}', -- vertices, indices, mesh data para ThreeJS
    vista_defecto JSONB DEFAULT '{"camera": [50, 50, 50], "target": [0, 0, 0]}',
    fecha_creacion TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 6. Tabla nivel_de_proteccion
CREATE TABLE IF NOT EXISTS nivel_de_proteccion (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    id_proyecto UUID NOT NULL REFERENCES proyecto(id) ON DELETE CASCADE,
    id_zona UUID REFERENCES zona_ceraunica(id),
    longitud_edificacion FLOAT NOT NULL,
    anchura_edificacion FLOAT NOT NULL,
    altura_edificacion FLOAT NOT NULL,
    area_equivalente_ae FLOAT NOT NULL,
    frecuencia_impactos_nd FLOAT NOT NULL,
    frecuencia_tolerable_nc FLOAT NOT NULL,
    requiere_spcr BOOLEAN NOT NULL DEFAULT FALSE,
    nivel_proteccion_calculado VARCHAR(50), -- Nivel I, II, III, IV
    eficiencia_proteccion FLOAT,             -- 0.98, 0.95, 0.90, 0.80
    factores_riesgo JSONB DEFAULT '{}',      -- Cd, Cb, Cc, Ce
    fecha_calculo TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 7. Tabla mastil
CREATE TABLE IF NOT EXISTS mastil (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    id_modelo3d UUID NOT NULL REFERENCES modelo3d(id) ON DELETE CASCADE,
    id_proyecto UUID NOT NULL REFERENCES proyecto(id) ON DELETE CASCADE,
    posicion_x FLOAT NOT NULL,
    posicion_y FLOAT NOT NULL,
    posicion_z FLOAT NOT NULL,
    altura FLOAT NOT NULL,
    tipo VARCHAR(100) DEFAULT 'Franklin',
    radio_cobertura FLOAT,
    angulo_proteccion FLOAT,
    fecha_creacion TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 8. Tabla resultado_simulacion
CREATE TABLE IF NOT EXISTS resultado_simulacion (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    id_proyecto UUID NOT NULL REFERENCES proyecto(id) ON DELETE CASCADE,
    id_modelo3d UUID NOT NULL REFERENCES modelo3d(id) ON DELETE CASCADE,
    puntos_cobertura JSONB DEFAULT '[]',
    puntos_desprotegidos JSONB DEFAULT '[]',
    porcentaje_cobertura FLOAT DEFAULT 0.0,
    metodo_calculo VARCHAR(100) DEFAULT 'Esfera Rodante',
    fecha_simulacion TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 9. Tabla memoria_descriptiva
CREATE TABLE IF NOT EXISTS memoria_descriptiva (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    id_proyecto UUID NOT NULL REFERENCES proyecto(id) ON DELETE CASCADE,
    titulo VARCHAR(255) NOT NULL,
    contenido JSONB NOT NULL DEFAULT '{}',
    estado VARCHAR(50) DEFAULT 'borrador',
    fecha_creacion TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    fecha_actualizacion TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Índices de optimización
CREATE INDEX IF NOT EXISTS idx_plano_proyecto ON plano(id_proyecto);
CREATE INDEX IF NOT EXISTS idx_modelo2d_proyecto ON modelo2d(id_proyecto);
CREATE INDEX IF NOT EXISTS idx_modelo3d_proyecto ON modelo3d(id_proyecto);
CREATE INDEX IF NOT EXISTS idx_nivel_proteccion_proyecto ON nivel_de_proteccion(id_proyecto);
CREATE INDEX IF NOT EXISTS idx_mastil_modelo3d ON mastil(id_modelo3d);
CREATE INDEX IF NOT EXISTS idx_mastil_proyecto ON mastil(id_proyecto);
