-- =========================================
-- 1. TABLE BRUTE (IMPORT SANS ERREUR)
-- =========================================

DROP TABLE IF EXISTS environmental_footprint_raw;

CREATE TABLE environmental_footprint_raw (
    manufacturer text,
    name text,
    category text,
    subcategory text,
    gwp_total text,
    gwp_use_ratio text,
    yearly_tec text,
    lifetime text,
    use_location text,
    report_date text,
    sources text,
    sources_hash text,
    gwp_error_ratio text,
    gwp_manufacturing_ratio text,
    weight text,
    assembly_location text,
    screen_size text,
    server_type text,
    hard_drive text,
    memory text,
    number_cpu text,
    height text,
    added_date text,
    add_method text,
    gwp_transport_ratio text,
    gwp_eol_ratio text,
    gwp_electronics_ratio text,
    gwp_battery_ratio text,
    gwp_hdd_ratio text,
    gwp_ssd_ratio text,
    gwp_othercomponents_ratio text,
    comment text
);

-- =========================================
-- 2. IMPORT CSV (RAW) — Boavizta FR uniquement
-- =========================================

COPY environmental_footprint_raw
FROM '/data/boavizta-data-fr.csv'
DELIMITER ';'
CSV HEADER;

-- =========================================
-- 3. TABLE FINALE (TYPÉE + PROPRE)
-- =========================================

DROP TABLE IF EXISTS environmental_footprint;

CREATE TABLE environmental_footprint (
    id serial PRIMARY KEY,

    manufacturer text,
    name text,
    category text,
    subcategory text,

    gwp_total numeric,
    gwp_use_ratio numeric,
    yearly_tec numeric,
    lifetime numeric,

    use_location text,
    report_date date,

    sources text,
    sources_hash text,

    gwp_error_ratio numeric,
    gwp_manufacturing_ratio numeric,

    weight numeric,
    assembly_location text,
    screen_size numeric,

    server_type text,
    hard_drive text,
    memory text,

    number_cpu numeric,
    height numeric,

    added_date date,
    add_method text,

    gwp_transport_ratio numeric,
    gwp_eol_ratio numeric,
    gwp_electronics_ratio numeric,
    gwp_battery_ratio numeric,
    gwp_hdd_ratio numeric,
    gwp_ssd_ratio numeric,
    gwp_othercomponents_ratio numeric,

    comment text
);

-- =========================================
-- 4. TRANSFORMATION + INSERT CLEAN DATA
-- =========================================

SET datestyle = 'DMY, ISO';
SET lc_time = 'C';

INSERT INTO environmental_footprint (
    manufacturer, name, category, subcategory,
    gwp_total, gwp_use_ratio, yearly_tec, lifetime,
    use_location, report_date,
    sources, sources_hash,
    gwp_error_ratio, gwp_manufacturing_ratio,
    weight, assembly_location, screen_size,
    server_type, hard_drive, memory,
    number_cpu, height,
    added_date, add_method,
    gwp_transport_ratio, gwp_eol_ratio,
    gwp_electronics_ratio, gwp_battery_ratio,
    gwp_hdd_ratio, gwp_ssd_ratio,
    gwp_othercomponents_ratio,
    comment
)
SELECT
    manufacturer,
    name,
    category,
    subcategory,

    NULLIF(REPLACE(gwp_total, ',', '.'), '')::numeric,
    NULLIF(REPLACE(gwp_use_ratio, ',', '.'), '')::numeric,
    NULLIF(REPLACE(yearly_tec, ',', '.'), '')::numeric,
    NULLIF(REPLACE(lifetime, ',', '.'), '')::numeric,

    use_location,

    CASE
        WHEN report_date ~ '^[0-9]{4}$' THEN
            TO_DATE(report_date, 'YYYY')
        WHEN report_date ~ '^[A-Za-z]+ [0-9]{4}$' THEN
            CASE
                WHEN length(split_part(trim(both from report_date), ' ', 1)) <= 3 THEN
                    TO_DATE(trim(both from report_date), 'Mon YYYY')
                ELSE
                    TO_DATE(trim(both from report_date), 'FMMonth YYYY')
            END
        ELSE NULL
    END,

    sources,
    sources_hash,

    NULLIF(REPLACE(gwp_error_ratio, ',', '.'), '')::numeric,
    NULLIF(REPLACE(gwp_manufacturing_ratio, ',', '.'), '')::numeric,

    NULLIF(REPLACE(weight, ',', '.'), '')::numeric,
    assembly_location,
    NULLIF(REPLACE(screen_size, ',', '.'), '')::numeric,

    server_type,
    hard_drive,
    memory,

    NULLIF(number_cpu, '')::numeric,
    NULLIF(REPLACE(height, ',', '.'), '')::numeric,

    CASE
        WHEN added_date ~ '^[0-9]{2}-[0-9]{2}-[0-9]{4}$' THEN
            TO_DATE(added_date, 'DD-MM-YYYY')
        WHEN added_date ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$' THEN
            TO_DATE(added_date, 'YYYY-MM-DD')
        WHEN added_date ~ '^[0-9]{2}/[0-9]{2}/[0-9]{4}$' THEN
            TO_DATE(added_date, 'DD/MM/YYYY')
        ELSE NULL
    END,

    add_method,

    NULLIF(REPLACE(gwp_transport_ratio, ',', '.'), '')::numeric,
    NULLIF(REPLACE(gwp_eol_ratio, ',', '.'), '')::numeric,
    NULLIF(REPLACE(gwp_electronics_ratio, ',', '.'), '')::numeric,
    NULLIF(REPLACE(gwp_battery_ratio, ',', '.'), '')::numeric,
    NULLIF(REPLACE(gwp_hdd_ratio, ',', '.'), '')::numeric,
    NULLIF(REPLACE(gwp_ssd_ratio, ',', '.'), '')::numeric,
    NULLIF(REPLACE(gwp_othercomponents_ratio, ',', '.'), '')::numeric,

    comment
FROM environmental_footprint_raw;

-- =========================================
-- 5. VERIFICATION
-- =========================================

SELECT COUNT(*) AS total_rows FROM environmental_footprint;
SELECT * FROM environmental_footprint LIMIT 5;
