-- Praxis IQ Database Schema
-- Version: 0.1 draft
-- Purpose: Core platform foundation for review before PostgreSQL execution.

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE clients (
    client_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    client_name TEXT NOT NULL,
    ticker TEXT,
    cik TEXT,
    sector TEXT,
    status TEXT DEFAULT 'active',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE companies (
    company_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    ticker TEXT NOT NULL,
    company_name TEXT NOT NULL,
    cik TEXT,
    cusip TEXT,
    exchange TEXT,
    sector TEXT,
    industry TEXT,
    market_cap NUMERIC,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE institutions (
    institution_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    cik TEXT,
    institution_name TEXT NOT NULL,
    normalized_name TEXT,
    investor_type TEXT,
    city TEXT,
    state TEXT,
    country TEXT,
    aum_estimate NUMERIC,
    website TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE peer_groups (
    peer_group_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    client_id UUID REFERENCES clients(client_id),
    peer_group_name TEXT NOT NULL,
    version TEXT DEFAULT '1.0',
    active_flag BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE peer_group_companies (
    peer_group_company_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    peer_group_id UUID REFERENCES peer_groups(peer_group_id),
    company_id UUID REFERENCES companies(company_id),
    tier INTEGER NOT NULL,
    weight INTEGER NOT NULL,
    inclusion_reason TEXT,
    active_flag BOOLEAN DEFAULT TRUE
);

CREATE TABLE features (
    feature_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    feature_name TEXT NOT NULL UNIQUE,
    feature_description TEXT,
    active_flag BOOLEAN DEFAULT TRUE
);

CREATE TABLE subscription_plans (
    plan_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    plan_name TEXT NOT NULL UNIQUE,
    plan_description TEXT,
    active_flag BOOLEAN DEFAULT TRUE
);

CREATE TABLE plan_features (
    plan_feature_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    plan_id UUID REFERENCES subscription_plans(plan_id),
    feature_id UUID REFERENCES features(feature_id),
    enabled BOOLEAN DEFAULT TRUE
);

CREATE TABLE client_feature_entitlements (
    entitlement_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    client_id UUID REFERENCES clients(client_id),
    feature_id UUID REFERENCES features(feature_id),
    enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE signals (
    signal_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    client_id UUID REFERENCES clients(client_id),
    institution_id UUID REFERENCES institutions(institution_id),
    company_id UUID REFERENCES companies(company_id),
    signal_category TEXT NOT NULL,
    signal_type TEXT NOT NULL,
    signal_date TIMESTAMP NOT NULL,
    signal_weight NUMERIC DEFAULT 0,
    confidence_score NUMERIC DEFAULT 0,
    source_system TEXT,
    source_url TEXT,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE recommendations (
    recommendation_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    client_id UUID REFERENCES clients(client_id),
    institution_id UUID REFERENCES institutions(institution_id),
    recommendation_type TEXT NOT NULL,
    recommendation_title TEXT NOT NULL,
    recommendation_summary TEXT,
    priority_score NUMERIC,
    confidence_score NUMERIC,
    status TEXT DEFAULT 'open',
    explanation JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
