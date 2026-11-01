-- Зіркова схема «Погодинне споживання електроенергії» (DuckDB)
-- Зерно факту: одне погодинне показання одного лічильника AMI (лічильник × дата × година).

CREATE TABLE IF NOT EXISTS dim_date (
    date_key      INTEGER PRIMARY KEY,          -- YYYYMMDD
    date          DATE     NOT NULL UNIQUE,
    day           SMALLINT NOT NULL,
    day_of_week   SMALLINT NOT NULL,            -- 1 = понеділок … 7 = неділя (ISO)
    day_name      VARCHAR  NOT NULL,
    is_weekend    BOOLEAN  NOT NULL,
    iso_week      SMALLINT NOT NULL,
    month         SMALLINT NOT NULL,
    month_name    VARCHAR  NOT NULL,
    quarter       SMALLINT NOT NULL,
    year          SMALLINT NOT NULL
);

CREATE TABLE IF NOT EXISTS dim_hour (
    hour_key      SMALLINT PRIMARY KEY,         -- 0…23
    hour_label    VARCHAR  NOT NULL,            -- '08:00'
    part_of_day   VARCHAR  NOT NULL,            -- ніч / ранок / день / вечір
    is_peak       BOOLEAN  NOT NULL             -- пікові години 08–10 і 18–21
);

-- Вимір-таксономія: гілка «Споживач» таксономії ЛР4, IRI класів — з онтології ЛР8
-- ієрархія: предметна область → категорія → клас → підклас (рівні 1–4 таксономії ЛР4)
CREATE TABLE IF NOT EXISTS dim_consumer_class (
    class_key      SMALLINT PRIMARY KEY,
    class_iri      VARCHAR  NOT NULL UNIQUE,
    class_label    VARCHAR  NOT NULL,
    parent_iri     VARCHAR,                     -- NULL для класу «Споживач»
    parent_label   VARCHAR,
    category_label VARCHAR  NOT NULL,           -- рівень 2 ЛР4: «Суб'єкти енергосистеми»
    domain_label   VARCHAR  NOT NULL,           -- рівень 1 ЛР4: «Прогнозування енергоспоживання»
    level          SMALLINT NOT NULL            -- 3 = клас «Споживач», 4 = підклас (рівні ЛР4)
);

-- Вимір мережі: підстанція → область (ієрархія з 2 рівнів), SCD 1
CREATE TABLE IF NOT EXISTS dim_substation (
    substation_key      SMALLINT PRIMARY KEY,
    substation_id       VARCHAR NOT NULL UNIQUE,
    substation_name     VARCHAR NOT NULL,
    nominal_capacity_kw DOUBLE  NOT NULL,
    region_id           VARCHAR NOT NULL,
    region_name         VARCHAR NOT NULL
);

-- Вимір споживача, SCD 2 (історія договірного ліміту); назва — SCD 1
CREATE TABLE IF NOT EXISTS dim_consumer (
    consumer_key      INTEGER PRIMARY KEY,      -- сурогатний ключ версії
    consumer_id       VARCHAR NOT NULL,         -- природний ключ (IRI-фрагмент графа ЛР9)
    consumer_name     VARCHAR NOT NULL,
    class_key         SMALLINT NOT NULL REFERENCES dim_consumer_class(class_key),
    contract_limit_kw DOUBLE  NOT NULL,
    valid_from        DATE    NOT NULL,
    valid_to          DATE    NOT NULL,         -- '9999-12-31' для поточної версії
    is_current        BOOLEAN NOT NULL,
    UNIQUE (consumer_id, valid_from)
);

CREATE TABLE IF NOT EXISTS fact_consumption (
    date_key        INTEGER  NOT NULL REFERENCES dim_date(date_key),
    hour_key        SMALLINT NOT NULL REFERENCES dim_hour(hour_key),
    consumer_key    INTEGER  NOT NULL REFERENCES dim_consumer(consumer_key),
    class_key       SMALLINT NOT NULL REFERENCES dim_consumer_class(class_key),
    substation_key  SMALLINT NOT NULL REFERENCES dim_substation(substation_key),
    meter_id        VARCHAR  NOT NULL,          -- вироджений вимір
    energy_kwh      DOUBLE   NOT NULL,          -- адитивна
    register_kwh    DOUBLE   NOT NULL,          -- напівадитивна (накопичувальний регістр)
    voltage_v       DOUBLE   NOT NULL,          -- неадитивна
    temperature_c   DOUBLE   NOT NULL,          -- неадитивна
    PRIMARY KEY (meter_id, date_key, hour_key)
);
