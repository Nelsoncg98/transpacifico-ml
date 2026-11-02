-- ============================================================================
-- PROYECTO: TRANSPACÍFICO S.A.C. - SISTEMA INTELIGENTE DE GESTIÓN DE FLOTA
-- ARCHIVO: script_bd_transpacifico.sql
-- MOTOR: PostgreSQL 16.2 | EXTENSIÓN: PostGIS 3.4.0
-- ============================================================================

-- 0. Habilitación de PostGIS
CREATE EXTENSION IF NOT EXISTS postgis;

-- 1. Dominio: Seguridad y Control de Acceso (RBAC)
CREATE TABLE IF NOT EXISTS rol (
    id_rol BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nombre VARCHAR(50) NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS usuario (
    id_usuario BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_rol BIGINT NOT NULL,
    correo VARCHAR(100) NOT NULL UNIQUE,
    contrasena VARCHAR(255) NOT NULL,
    sede_operativa VARCHAR(50) NOT NULL,
    estado VARCHAR(20) NOT NULL DEFAULT 'Activo',
    CONSTRAINT fk_usuario_rol FOREIGN KEY (id_rol) REFERENCES rol(id_rol)
);

CREATE TABLE IF NOT EXISTS registro_sesion (
    id_sesion BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_usuario BIGINT NOT NULL,
    fecha_hora TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    sede VARCHAR(50) NOT NULL,
    CONSTRAINT fk_sesion_usuario FOREIGN KEY (id_usuario) REFERENCES usuario(id_usuario)
);

-- 2. Dominio: Flota y Recursos Operativos
CREATE TABLE IF NOT EXISTS conductor (
    id_conductor BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_usuario BIGINT NOT NULL,
    nombre VARCHAR(100) NOT NULL,
    brevete VARCHAR(20) NOT NULL UNIQUE,
    categoria_brevete VARCHAR(10) NOT NULL DEFAULT 'A-IIIc',
    fecha_vencimiento DATE NOT NULL,
    estado VARCHAR(20) NOT NULL DEFAULT 'Habilitado',
    CONSTRAINT fk_conductor_usuario FOREIGN KEY (id_usuario) REFERENCES usuario(id_usuario)
);

CREATE TABLE IF NOT EXISTS tracto (
    id_tracto BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    placa VARCHAR(10) NOT NULL UNIQUE,
    modelo VARCHAR(50) NOT NULL,
    estado VARCHAR(20) NOT NULL DEFAULT 'Disponible'
);

CREATE TABLE IF NOT EXISTS semirremolque (
    id_semirremolque BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    placa VARCHAR(10) NOT NULL UNIQUE,
    capacidad_tn NUMERIC(5,2) NOT NULL,
    estado VARCHAR(20) NOT NULL DEFAULT 'Disponible'
);

CREATE TABLE IF NOT EXISTS cliente (
    id_cliente BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    razon_social VARCHAR(150) NOT NULL,
    ruc VARCHAR(11) NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS corredor (
    id_corredor BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL UNIQUE,
    distancia_km NUMERIC(7,2) NOT NULL
);

-- 3. Dominio: Core Transaccional de Despacho
CREATE TABLE IF NOT EXISTS solicitud_carga (
    id_solicitud BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_cliente BIGINT NOT NULL,
    id_corredor BIGINT NOT NULL,
    nro_guia_remitente VARCHAR(30) NOT NULL,
    origen VARCHAR(100) NOT NULL,
    destino VARCHAR(100) NOT NULL,
    tipo_carga VARCHAR(50) NOT NULL,
    peso_tn NUMERIC(6,2) NOT NULL,
    fecha DATE NOT NULL,
    ventana_entrega TIMESTAMPTZ NOT NULL,
    estado VARCHAR(20) NOT NULL DEFAULT 'Registrada',
    motivo_rechazo VARCHAR(200),
    fecha_hora_decision TIMESTAMPTZ,
    CONSTRAINT fk_solicitud_cliente FOREIGN KEY (id_cliente) REFERENCES cliente(id_cliente),
    CONSTRAINT fk_solicitud_corredor FOREIGN KEY (id_corredor) REFERENCES corredor(id_corredor)
);

CREATE TABLE IF NOT EXISTS pronostico_demanda (
    id_pronostico BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_corredor BIGINT NOT NULL,
    semana_inicio DATE NOT NULL,
    toneladas_estimadas NUMERIC(10,2) NOT NULL,
    toneladas_min NUMERIC(10,2) NOT NULL,
    toneladas_max NUMERIC(10,2) NOT NULL,
    CONSTRAINT fk_pronostico_corredor FOREIGN KEY (id_corredor) REFERENCES corredor(id_corredor)
);

CREATE TABLE IF NOT EXISTS despacho (
    id_despacho BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_solicitud BIGINT NOT NULL UNIQUE,
    id_tracto BIGINT NOT NULL,
    id_semirremolque BIGINT NOT NULL,
    id_conductor BIGINT NOT NULL,
    estado_viaje VARCHAR(25) NOT NULL DEFAULT 'Programado',
    fof_porcentaje NUMERIC(5,2) NOT NULL,
    eta_estimado TIMESTAMPTZ,
    eta_fecha_hora_calculo TIMESTAMPTZ,
    fecha_hora_ingreso_patio TIMESTAMPTZ,
    fecha_hora_salida TIMESTAMPTZ,
    nro_gre VARCHAR(20) UNIQUE,
    estado_gre VARCHAR(20) DEFAULT 'Pendiente',
    odometro_inicial_km INTEGER NOT NULL,
    odometro_final_km INTEGER,
    odometro_retorno_km INTEGER,
    retorno_con_carga BOOLEAN,
    CONSTRAINT fk_despacho_solicitud FOREIGN KEY (id_solicitud) REFERENCES solicitud_carga(id_solicitud),
    CONSTRAINT fk_despacho_tracto FOREIGN KEY (id_tracto) REFERENCES tracto(id_tracto),
    CONSTRAINT fk_despacho_semirremolque FOREIGN KEY (id_semirremolque) REFERENCES semirremolque(id_semirremolque),
    CONSTRAINT fk_despacho_conductor FOREIGN KEY (id_conductor) REFERENCES conductor(id_conductor)
);

CREATE TABLE IF NOT EXISTS pesaje_bascula (
    id_pesaje BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_despacho BIGINT NOT NULL,
    fecha_hora TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    tara_kg NUMERIC(8,2) NOT NULL,
    peso_bruto_kg NUMERIC(8,2) NOT NULL,
    peso_neto_kg NUMERIC(8,2) NOT NULL,
    resultado VARCHAR(20) NOT NULL,
    CONSTRAINT fk_pesaje_despacho FOREIGN KEY (id_despacho) REFERENCES despacho(id_despacho)
);

CREATE TABLE IF NOT EXISTS precinto (
    id_precinto BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_pesaje BIGINT NOT NULL,
    numero VARCHAR(50) NOT NULL,
    CONSTRAINT fk_precinto_pesaje FOREIGN KEY (id_pesaje) REFERENCES pesaje_bascula(id_pesaje)
);

CREATE TABLE IF NOT EXISTS pod_entrega (
    id_pod BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_despacho BIGINT NOT NULL UNIQUE,
    fecha_hora_real TIMESTAMPTZ NOT NULL,
    receptor_nombre VARCHAR(100) NOT NULL,
    receptor_dni VARCHAR(8) NOT NULL,
    precintos_conformes BOOLEAN NOT NULL DEFAULT TRUE,
    cumplio_otif BOOLEAN NOT NULL,
    archivo_foto_url VARCHAR(255) NOT NULL,
    CONSTRAINT fk_pod_despacho FOREIGN KEY (id_despacho) REFERENCES despacho(id_despacho)
);

CREATE TABLE IF NOT EXISTS verificacion_entrega (
    id_verificacion BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_pod BIGINT NOT NULL UNIQUE,
    estado VARCHAR(20) NOT NULL DEFAULT 'Conforme',
    comentario VARCHAR(255),
    fecha_hora TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_verificacion_pod FOREIGN KEY (id_pod) REFERENCES pod_entrega(id_pod)
);

-- 4. Dominio: Telemetría y Modelos Predictivos
CREATE TABLE IF NOT EXISTS registro_gps (
    id_gps BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_despacho BIGINT NOT NULL,
    ubicacion GEOMETRY(Point, 4326) NOT NULL,
    fecha_hora TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_gps_despacho FOREIGN KEY (id_despacho) REFERENCES despacho(id_despacho)
);

CREATE TABLE IF NOT EXISTS alerta (
    id_alerta BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_despacho BIGINT NOT NULL,
    tipo VARCHAR(50) NOT NULL,
    mensaje VARCHAR(255) NOT NULL,
    fecha_hora TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    retraso_min INTEGER NOT NULL,
    CONSTRAINT fk_alerta_despacho FOREIGN KEY (id_despacho) REFERENCES despacho(id_despacho)
);

CREATE TABLE IF NOT EXISTS incidencia (
    id_incidencia BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_despacho BIGINT NOT NULL,
    tipo VARCHAR(50) NOT NULL,
    descripcion VARCHAR(255) NOT NULL,
    ubicacion GEOMETRY(Point, 4326),
    fecha_hora TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    accion_tomada VARCHAR(255),
    CONSTRAINT fk_incidencia_despacho FOREIGN KEY (id_despacho) REFERENCES despacho(id_despacho)
);

CREATE TABLE IF NOT EXISTS prediccion_retorno (
    id_prediccion_retorno BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_despacho BIGINT NOT NULL,
    nivel_probabilidad VARCHAR(10) NOT NULL,
    probabilidad NUMERIC(4,3) NOT NULL,
    CONSTRAINT fk_prediccion_despacho FOREIGN KEY (id_despacho) REFERENCES despacho(id_despacho)
);

-- Índices de Desempeño
CREATE INDEX IF NOT EXISTS idx_despacho_estado ON despacho(estado_viaje);
CREATE INDEX IF NOT EXISTS idx_gps_despacho_tiempo ON registro_gps(id_despacho, fecha_hora DESC);
CREATE INDEX IF NOT EXISTS idx_gps_ubicacion_gist ON registro_gps USING GIST (ubicacion);
CREATE INDEX IF NOT EXISTS idx_solicitud_corredor_fecha ON solicitud_carga(id_corredor, fecha);
CREATE INDEX IF NOT EXISTS idx_pesaje_despacho ON pesaje_bascula(id_despacho);
