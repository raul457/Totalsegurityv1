-- Execute este SQL no seu banco de dados PostgreSQL (Supabase, Neon, Vercel Postgres, etc.)
-- Cole no SQL Editor do Supabase ou em qualquer cliente PostgreSQL

CREATE TABLE IF NOT EXISTS orcamentos (
    id               SERIAL PRIMARY KEY,
    nome             VARCHAR(255),
    email            VARCHAR(255),
    telefone         VARCHAR(50),
    estado           VARCHAR(100),
    cidade           VARCHAR(255),
    natureza         VARCHAR(100),
    servicos         JSONB,
    whatsapp_enviado BOOLEAN DEFAULT FALSE,
    created_at       TIMESTAMP DEFAULT NOW()
);

-- Índices para facilitar buscas
CREATE INDEX IF NOT EXISTS idx_orcamentos_created_at ON orcamentos (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_orcamentos_email      ON orcamentos (email);
CREATE INDEX IF NOT EXISTS idx_orcamentos_telefone   ON orcamentos (telefone);
