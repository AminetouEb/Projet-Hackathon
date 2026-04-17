-- =========================================
-- 1. Création de la table unique
-- =========================================
CREATE TABLE environmental_footprint (
    id SERIAL PRIMARY KEY,

    manufacturer TEXT,
    name TEXT,
    category TEXT,
    subcategory TEXT,

    gwp_total FLOAT,
    gwp_use_ratio FLOAT,
    yearly_tec FLOAT,
    lifetime FLOAT,

    use_location TEXT,
    report_date DATE,
    sources TEXT,
    sources_hash TEXT,

    gwp_error_ratio FLOAT,
    gwp_manufacturing_ratio FLOAT,

    weight FLOAT,
    assembly_location TEXT,

    screen_size FLOAT,
    server_type TEXT,
    hard_drive TEXT,
    memory TEXT,
    number_cpu INT,
    height FLOAT,

    added_date DATE,
    add_method TEXT,

    gwp_transport_ratio FLOAT,
    gwp_eol_ratio FLOAT,
    gwp_electronics_ratio FLOAT,
    gwp_battery_ratio FLOAT,
    gwp_hdd_ratio FLOAT,
    gwp_ssd_ratio FLOAT,
    gwp_othercomponents_ratio FLOAT,

    comment TEXT,

    country TEXT
);

-- =========================================
-- 2. Import données FR
-- =========================================
COPY environmental_footprint(
    manufacturer, name, category, subcategory,
    gwp_total, gwp_use_ratio, yearly_tec, lifetime,
    use_location, report_date, sources, sources_hash,
    gwp_error_ratio, gwp_manufacturing_ratio,
    weight, assembly_location,
    screen_size, server_type, hard_drive, memory,
    number_cpu, height,
    added_date, add_method,
    gwp_transport_ratio, gwp_eol_ratio, gwp_electronics_ratio,
    gwp_battery_ratio, gwp_hdd_ratio, gwp_ssd_ratio,
    gwp_othercomponents_ratio,
    comment
)
FROM '/data/boavizta-data-fr.csv'
DELIMITER ';'
CSV HEADER;

-- Ajouter le pays FR
UPDATE environmental_footprint
SET country = 'FR'
WHERE country IS NULL;

-- =========================================
-- 3. Import données US
-- =========================================
COPY environmental_footprint(
    manufacturer, name, category, subcategory,
    gwp_total, gwp_use_ratio, yearly_tec, lifetime,
    use_location, report_date, sources, sources_hash,
    gwp_error_ratio, gwp_manufacturing_ratio,
    weight, assembly_location,
    screen_size, server_type, hard_drive, memory,
    number_cpu, height,
    added_date, add_method,
    gwp_transport_ratio, gwp_eol_ratio, gwp_electronics_ratio,
    gwp_battery_ratio, gwp_hdd_ratio, gwp_ssd_ratio,
    gwp_othercomponents_ratio,
    comment
)
FROM '/data/boavizta-data-us.csv'
DELIMITER ';'
CSV HEADER;

-- Ajouter le pays US
UPDATE environmental_footprint
SET country = 'US'
WHERE country IS NULL;