CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE IF NOT EXISTS ais_messages (
    id SERIAL PRIMARY KEY,
    mmsi VARCHAR(20) NOT NULL,
    timestamp_utc TIMESTAMPTZ NOT NULL,
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    speed DOUBLE PRECISION,
    course DOUBLE PRECISION,
    vessel_type VARCHAR(100),
    geom GEOMETRY(Point, 4326)
);

CREATE INDEX IF NOT EXISTS idx_ais_messages_geom
ON ais_messages
USING GIST (geom);

CREATE INDEX IF NOT EXISTS idx_ais_messages_time
ON ais_messages (timestamp_utc);

CREATE INDEX IF NOT EXISTS idx_ais_messages_mmsi
ON ais_messages (mmsi);

CREATE UNIQUE INDEX IF NOT EXISTS ux_ais_message_unique
ON ais_messages (mmsi, timestamp_utc, latitude, longitude);

CREATE TABLE IF NOT EXISTS vessel_trajectories (
    id SERIAL PRIMARY KEY,
    mmsi VARCHAR(20) NOT NULL,
    start_time TIMESTAMPTZ NOT NULL,
    end_time TIMESTAMPTZ NOT NULL,
    points_count INTEGER NOT NULL,
    geom GEOMETRY(LineString, 4326)
);

CREATE INDEX IF NOT EXISTS idx_vessel_trajectories_geom
ON vessel_trajectories
USING GIST (geom);

CREATE INDEX IF NOT EXISTS idx_vessel_trajectories_mmsi
ON vessel_trajectories (mmsi);

CREATE INDEX IF NOT EXISTS idx_vessel_trajectories_time
ON vessel_trajectories (start_time, end_time);

CREATE TABLE IF NOT EXISTS reports (
    id SERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    route_name VARCHAR(255),
    risk_level VARCHAR(50),
    risk_score DOUBLE PRECISION,
    content TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS risk_zones (
    id SERIAL PRIMARY KEY,
    risk_level VARCHAR(50) NOT NULL,
    risk_score DOUBLE PRECISION NOT NULL,
    points_count INTEGER NOT NULL,
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    geom GEOMETRY(Polygon, 4326)
);

CREATE INDEX IF NOT EXISTS idx_risk_zones_geom
ON risk_zones
USING GIST (geom);

CREATE INDEX IF NOT EXISTS idx_risk_zones_level
ON risk_zones (risk_level);