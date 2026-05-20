{{
    config(
        materialized='view',
        enabled=var('use_calibration', false)
    )
}}

-- calibrated_load_shapes.sql
-- Applies historical load shape calibration when a calibration source is available.
-- Distributes historical total hourly demand to sectors using STRIDE's sector shares,
-- then rescales to preserve STRIDE's annual regression totals exactly.
-- Finally, decomposes the calibrated sector totals back into enduses using IMAGE shares.

WITH historical AS (
    -- The user-provided or ENTSO-E hourly total demand
    SELECT
        timestamp,
        total_load_mwh
    FROM {{ source('scenario', 'calibration_load_shape') }}
),

stride_enduse_hourly AS (
    -- STRIDE's enduse-level load shapes (from weather module)
    -- Kept at enduse granularity for decomposing calibrated output later
    SELECT
        ls.timestamp,
        ls.model_year,
        ls.geography,
        ls.sector,
        ls.enduse,
        ls.adjusted_value
    FROM {{ ref('load_shapes_expanded') }} ls
),

stride_sector_hourly AS (
    -- STRIDE's existing sectorial load shapes (from weather module + annual regression)
    -- These provide the sector shares for disaggregation
    SELECT
        timestamp,
        model_year,
        geography,
        sector,
        SUM(adjusted_value) AS sector_value
    FROM stride_enduse_hourly
    GROUP BY timestamp, model_year, geography, sector
),

stride_total_hourly AS (
    -- Total across all sectors at each hour
    SELECT
        timestamp,
        model_year,
        geography,
        SUM(sector_value) AS total_value
    FROM stride_sector_hourly
    GROUP BY timestamp, model_year, geography
),

sector_shares AS (
    -- Sector share at each hour (the STRIDE prior)
    SELECT
        s.timestamp,
        s.model_year,
        s.geography,
        s.sector,
        s.sector_value / NULLIF(t.total_value, 0) AS share
    FROM stride_sector_hourly s
    JOIN stride_total_hourly t
        ON s.timestamp = t.timestamp
        AND s.model_year = t.model_year
        AND s.geography = t.geography
),

raw_distributed AS (
    -- Step 1: distribute historical shape to sectors
    -- The historical table has no model_year dimension — it's a single year of
    -- hourly data. The JOIN on timestamp replicates it across all model_years from
    -- sector_shares. This is intentional: the same historical hourly pattern is applied
    -- to every model_year, with the scale_factor (Step 2) adjusting magnitudes per year.
    SELECT
        sh.timestamp,
        sh.model_year,
        sh.geography,
        sh.sector,
        h.total_load_mwh * sh.share AS raw_value
    FROM sector_shares sh
    JOIN historical h
        ON sh.timestamp = h.timestamp
),

stride_annual AS (
    -- STRIDE's regression-based annual demand per sector (in MWh).
    -- Commercial, Industrial, Transportation: from energy intensity × GDP regression (TJ→MWh)
    -- When EV projection is enabled, exclude Transportation/Road (added separately downstream)
    SELECT
        geography,
        model_year,
        sector,
        SUM(value) * 277.777777778 AS annual_total
    FROM {{ table_ref('energy_intensity_com_ind_tra_gdp_applied_regression') }}
    WHERE NOT (sector = 'Transportation' AND subsector = 'Road' AND {{ var("use_ev_projection", false) }})
    GROUP BY geography, model_year, sector

    UNION ALL

    -- Residential: from energy intensity × HDI × population regression (TJ→MWh)
    SELECT
        geography,
        model_year,
        sector,
        SUM(value) * 277.777777778 AS annual_total
    FROM {{ table_ref('energy_intensity_res_hdi_population_applied_regression') }}
    GROUP BY geography, model_year, sector
),

scale_factors AS (
    -- Step 2: compute one scalar per (sector, model_year) to honor annual totals
    SELECT
        r.model_year,
        r.geography,
        r.sector,
        a.annual_total / NULLIF(SUM(r.raw_value), 0) AS scale_factor
    FROM raw_distributed r
    JOIN stride_annual a
        ON r.model_year = a.model_year
        AND r.geography = a.geography
        AND r.sector = a.sector
    GROUP BY r.model_year, r.geography, r.sector, a.annual_total
),

calibrated_sector AS (
    -- Calibrated hourly values at sector level
    SELECT
        r.timestamp,
        r.model_year,
        r.geography,
        r.sector,
        r.raw_value * sf.scale_factor AS value
    FROM raw_distributed r
    JOIN scale_factors sf
        ON r.model_year = sf.model_year
        AND r.geography = sf.geography
        AND r.sector = sf.sector
),

enduse_shares AS (
    -- Step 3: compute enduse share within each sector at each hour
    -- This preserves the IMAGE/BAIT enduse composition (heating vs cooling vs other)
    SELECT
        se.timestamp,
        se.model_year,
        se.geography,
        se.sector,
        se.enduse,
        se.adjusted_value / NULLIF(sh.sector_value, 0) AS enduse_share
    FROM stride_enduse_hourly se
    JOIN stride_sector_hourly sh
        ON se.timestamp = sh.timestamp
        AND se.model_year = sh.model_year
        AND se.geography = sh.geography
        AND se.sector = sh.sector
)

-- Final calibrated output with enduse decomposition
SELECT
    c.timestamp,
    c.model_year,
    c.geography,
    c.sector,
    es.enduse,
    c.value * es.enduse_share AS value
FROM calibrated_sector c
JOIN enduse_shares es
    ON c.timestamp = es.timestamp
    AND c.model_year = es.model_year
    AND c.geography = es.geography
    AND c.sector = es.sector
