CREATE TABLE IF NOT EXISTS telemetria_industrial (
    id BIGSERIAL PRIMARY KEY,
    origem VARCHAR(50) NOT NULL,
    topico VARCHAR(120) NOT NULL,
    payload JSONB NOT NULL,
    registrado_em TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_telemetria_origem_tempo ON telemetria_industrial (origem, registrado_em DESC);
CREATE INDEX idx_telemetria_payload_gin ON telemetria_industrial USING GIN (payload);

CREATE TABLE IF NOT EXISTS eventos_alarme (
    id BIGSERIAL PRIMARY KEY,
    origem VARCHAR(50) NOT NULL,
    severidade VARCHAR(20) NOT NULL,
    mensagem TEXT NOT NULL,
    reconhecido BOOLEAN NOT NULL DEFAULT FALSE,
    registrado_em TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
