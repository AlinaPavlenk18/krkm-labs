-- Зіркова схема «Точність прогнозів добового споживання» (DuckDB)
-- Зерно: один прогноз добового споживання, складений однією версією моделі для однієї підстанції
--        на одну цільову дату з одним горизонтом (модель × підстанція × цільова дата × горизонт).

CREATE TABLE IF NOT EXISTS dim_date (            -- рольовий вимір: цільова дата і дата складання
    date_key     INTEGER PRIMARY KEY,            -- YYYYMMDD
    date         DATE     NOT NULL UNIQUE,
    day_of_week  SMALLINT NOT NULL,
    is_weekend   BOOLEAN  NOT NULL,
    iso_week     SMALLINT NOT NULL,
    month        SMALLINT NOT NULL,
    quarter      SMALLINT NOT NULL,
    year         SMALLINT NOT NULL
);

CREATE TABLE IF NOT EXISTS dim_horizon (         -- тип прогнозу → горизонт (таксономія ЛР4)
    horizon_key   SMALLINT PRIMARY KEY,
    horizon_days  SMALLINT NOT NULL UNIQUE,
    horizon_label VARCHAR  NOT NULL,
    forecast_type VARCHAR  NOT NULL               -- «короткостроковий прогноз»
);

CREATE TABLE IF NOT EXISTS dim_model_class (     -- гілка «Моделі та методи» таксономії ЛР4, IRI — онтологія ЛР8
    class_key      SMALLINT PRIMARY KEY,
    class_iri      VARCHAR  NOT NULL UNIQUE,
    class_label    VARCHAR  NOT NULL,
    parent_iri     VARCHAR,
    parent_label   VARCHAR,
    category_label VARCHAR  NOT NULL,             -- «Формалізовані (математичні) моделі»
    level          SMALLINT NOT NULL
);

CREATE TABLE IF NOT EXISTS dim_model (           -- SCD 2: версія, дата навчання, точність
    model_key        INTEGER  PRIMARY KEY,        -- сурогатний ключ версії
    model_id         VARCHAR  NOT NULL,           -- природний ключ (граф ЛР9)
    model_name       VARCHAR  NOT NULL,
    model_type       VARCHAR  NOT NULL,           -- VAR / LSTM
    class_key        SMALLINT NOT NULL REFERENCES dim_model_class(class_key),
    version          SMALLINT NOT NULL,
    training_date    DATE     NOT NULL,
    accuracy_pct     DOUBLE   NOT NULL,
    valid_from       DATE     NOT NULL,
    valid_to         DATE     NOT NULL,
    is_current       BOOLEAN  NOT NULL,
    UNIQUE (model_id, version)
);

CREATE TABLE IF NOT EXISTS dim_substation (      -- область → підстанція, SCD 1
    substation_key      SMALLINT PRIMARY KEY,
    substation_id       VARCHAR NOT NULL UNIQUE,
    substation_name     VARCHAR NOT NULL,
    nominal_capacity_kw DOUBLE  NOT NULL,
    region_name         VARCHAR NOT NULL
);

CREATE TABLE IF NOT EXISTS fact_forecast (
    target_date_key   INTEGER  NOT NULL REFERENCES dim_date(date_key),
    issue_date_key    INTEGER  NOT NULL REFERENCES dim_date(date_key),
    horizon_key       SMALLINT NOT NULL REFERENCES dim_horizon(horizon_key),
    model_key         INTEGER  NOT NULL REFERENCES dim_model(model_key),   -- версія, чинна на дату складання
    class_key         SMALLINT NOT NULL REFERENCES dim_model_class(class_key),
    substation_key    SMALLINT NOT NULL REFERENCES dim_substation(substation_key),
    forecast_kwh      DOUBLE NOT NULL,            -- адитивна
    actual_kwh        DOUBLE NOT NULL,            -- адитивна
    error_kwh         DOUBLE NOT NULL,            -- адитивна (прогноз − факт, зі знаком)
    abs_error_kwh     DOUBLE NOT NULL,            -- адитивна
    ape_pct           DOUBLE NOT NULL,            -- неадитивна (|e| / факт · 100)
    mtd_abs_error_kwh DOUBLE NOT NULL,            -- напівадитивна (накопичено з 1-го числа)
    PRIMARY KEY (model_key, substation_key, target_date_key, horizon_key)
);
