-- ==============================================================================
-- GMIP (Global Macroeconomic Intelligence Platform)
-- Supabase PostgreSQL Schema DDL & Row Level Security Setup
-- ==============================================================================

-- 1. DATA SOURCES TABLE
CREATE TABLE IF NOT EXISTS public.data_sources (
    id VARCHAR(32) PRIMARY KEY,
    name VARCHAR(128) NOT NULL,
    base_url VARCHAR(255) NOT NULL,
    auth_type VARCHAR(32) DEFAULT 'NONE',
    rate_limit_per_minute INTEGER DEFAULT 60,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 2. INDICATORS TABLE (24 Core Macroeconomic & Financial Indicators)
CREATE TABLE IF NOT EXISTS public.indicators (
    id VARCHAR(64) PRIMARY KEY,
    symbol VARCHAR(64) NOT NULL,
    name_vi VARCHAR(255) NOT NULL,
    name_en VARCHAR(255) NOT NULL,
    category VARCHAR(32) NOT NULL,
    unit VARCHAR(32) NOT NULL,
    frequency VARCHAR(32) DEFAULT 'DAILY',
    primary_source_id VARCHAR(32) NOT NULL REFERENCES public.data_sources(id),
    fallback_source_id VARCHAR(32) REFERENCES public.data_sources(id),
    priority INTEGER DEFAULT 1,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 3. INDICATOR VALUES TABLE (Historical Time-Series & Technical Signals)
CREATE TABLE IF NOT EXISTS public.indicator_values (
    id BIGSERIAL PRIMARY KEY,
    indicator_id VARCHAR(64) NOT NULL REFERENCES public.indicators(id) ON DELETE CASCADE,
    record_date DATE NOT NULL,
    value DOUBLE PRECISION NOT NULL,
    change_1d DOUBLE PRECISION,
    change_1w DOUBLE PRECISION,
    change_1m DOUBLE PRECISION,
    change_yoy DOUBLE PRECISION,
    ma_20 DOUBLE PRECISION,
    ma_50 DOUBLE PRECISION,
    trend_state VARCHAR(32),
    source_used VARCHAR(32) NOT NULL,
    fetched_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_indicator_date UNIQUE (indicator_id, record_date)
);

CREATE INDEX IF NOT EXISTS idx_indicator_values_query ON public.indicator_values(indicator_id, record_date);
CREATE INDEX IF NOT EXISTS idx_indicator_values_date ON public.indicator_values(record_date);

-- 4. DAILY REPORTS TABLE (Standardized 5-Section Markdown Reports)
CREATE TABLE IF NOT EXISTS public.daily_reports (
    id VARCHAR(64) PRIMARY KEY,
    report_date DATE NOT NULL UNIQUE,
    title VARCHAR(255) NOT NULL,
    summary TEXT,
    risk_level VARCHAR(32) DEFAULT 'MEDIUM',
    content_markdown TEXT NOT NULL,
    status VARCHAR(32) DEFAULT 'PUBLISHED',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    published_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX IF NOT EXISTS idx_daily_reports_date ON public.daily_reports(report_date);

-- 5. INGESTION LOGS TABLE (Audit Logs & Failover Tracking)
CREATE TABLE IF NOT EXISTS public.ingestion_logs (
    id BIGSERIAL PRIMARY KEY,
    indicator_id VARCHAR(64) REFERENCES public.indicators(id),
    source_id VARCHAR(32) REFERENCES public.data_sources(id),
    status VARCHAR(32) NOT NULL,
    response_time_ms INTEGER,
    error_message TEXT,
    executed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_ingestion_logs_date ON public.ingestion_logs(executed_at);

-- ==============================================================================
-- ROW LEVEL SECURITY (RLS) POLICIES
-- ==============================================================================
ALTER TABLE public.data_sources ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.indicators ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.indicator_values ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.daily_reports ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.ingestion_logs ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'data_sources' AND policyname = 'Allow public read access on data_sources') THEN
        CREATE POLICY "Allow public read access on data_sources" ON public.data_sources FOR SELECT USING (true);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'indicators' AND policyname = 'Allow public read access on indicators') THEN
        CREATE POLICY "Allow public read access on indicators" ON public.indicators FOR SELECT USING (true);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'indicator_values' AND policyname = 'Allow public read access on indicator_values') THEN
        CREATE POLICY "Allow public read access on indicator_values" ON public.indicator_values FOR SELECT USING (true);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'daily_reports' AND policyname = 'Allow public read access on daily_reports') THEN
        CREATE POLICY "Allow public read access on daily_reports" ON public.daily_reports FOR SELECT USING (true);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'ingestion_logs' AND policyname = 'Allow public read access on ingestion_logs') THEN
        CREATE POLICY "Allow public read access on ingestion_logs" ON public.ingestion_logs FOR SELECT USING (true);
    END IF;
END $$;
