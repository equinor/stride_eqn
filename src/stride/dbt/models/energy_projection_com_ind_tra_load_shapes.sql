{% if var('use_calibration', false) %}
-- Use calibrated shapes for base sectors (already scaled to annual totals, with enduse decomposition)
-- When EV projection is enabled, EV charging is added as a separate metric.
{% if var('use_ev_projection', false) %}
WITH ev_annual_energy AS (
    SELECT
        geography,
        model_year,
        sector,
        subsector,
        value * 277.777777778 AS stride_annual_total
    FROM {{ table_ref('ev_annual_energy_tj') }}
),

{% if var('use_ev_load_shape', false) %}
-- Custom EV load shape: normalize user-provided profile and use for hourly distribution
ev_profile_raw AS (
    SELECT hour_idx, value AS profile_value
    FROM {{ source('scenario', 'ev_load_shape') }}
),
ev_profile_normalized AS (
    SELECT
        hour_idx,
        profile_value / SUM(profile_value) OVER () AS fraction
    FROM ev_profile_raw
),
ev_hourly_timestamps AS (
    SELECT
        timestamp,
        model_year,
        geography,
        ROW_NUMBER() OVER (PARTITION BY model_year, geography ORDER BY timestamp) AS hour_idx
    FROM (
        SELECT DISTINCT timestamp, model_year, geography
        FROM {{ ref('calibrated_load_shapes') }}
        WHERE sector = 'Transportation'
    )
),
ev_annual_total AS (
    SELECT
        model_year,
        geography,
        SUM(stride_annual_total) AS ev_total_mwh
    FROM ev_annual_energy
    GROUP BY model_year, geography
)

SELECT
    timestamp,
    model_year,
    geography,
    sector,
    enduse AS metric,
    value
FROM {{ ref('calibrated_load_shapes') }}
WHERE sector IN ('Commercial', 'Industrial', 'Transportation')

UNION ALL

SELECT
    eht.timestamp,
    eht.model_year,
    eht.geography,
    'Transportation' AS sector,
    'ev_charging' AS metric,
    epn.fraction * eat.ev_total_mwh AS value
FROM ev_hourly_timestamps eht
JOIN ev_profile_normalized epn ON eht.hour_idx = epn.hour_idx
JOIN ev_annual_total eat
    ON eht.model_year = eat.model_year
    AND eht.geography = eat.geography

{% else %}
-- Fallback: use calibrated transport shape for EV hourly distribution
calibrated_transport_hourly AS (
    -- Sum across enduses to get sector-level hourly for EV scaling
    SELECT
        timestamp,
        model_year,
        geography,
        SUM(value) AS hourly_value
    FROM {{ ref('calibrated_load_shapes') }}
    WHERE sector = 'Transportation'
    GROUP BY timestamp, model_year, geography
),

calibrated_transport_annual AS (
    SELECT
        model_year,
        geography,
        SUM(hourly_value) AS annual_total
    FROM calibrated_transport_hourly
    GROUP BY model_year, geography
),

ev_scaling AS (
    SELECT
        ct.model_year,
        ct.geography,
        CASE
            WHEN ct.annual_total > 0
            THEN SUM(ev.stride_annual_total) / ct.annual_total
            ELSE 0
        END AS ev_scale
    FROM calibrated_transport_annual ct
    JOIN ev_annual_energy ev
        ON ct.geography = ev.geography
        AND ct.model_year = ev.model_year
    GROUP BY ct.model_year, ct.geography, ct.annual_total
)

SELECT
    timestamp,
    model_year,
    geography,
    sector,
    enduse AS metric,
    value
FROM {{ ref('calibrated_load_shapes') }}
WHERE sector IN ('Commercial', 'Industrial', 'Transportation')

UNION ALL

SELECT
    cth.timestamp,
    cth.model_year,
    cth.geography,
    'Transportation' AS sector,
    'ev_charging' AS metric,
    cth.hourly_value * es.ev_scale AS value
FROM calibrated_transport_hourly cth
JOIN ev_scaling es
    ON cth.model_year = es.model_year
    AND cth.geography = es.geography

{% endif %}
{# end use_ev_load_shape #}

{% else %}
-- No EV projection: just use calibrated shapes directly
SELECT
    timestamp,
    model_year,
    geography,
    sector,
    enduse AS metric,
    value
FROM {{ ref('calibrated_load_shapes') }}
WHERE sector IN ('Commercial', 'Industrial', 'Transportation')
{% endif %}

{% else %}
WITH load_shapes_filtered AS (
    -- Get temperature-adjusted load shapes for commercial, industrial, and transportation sectors
    SELECT
        geography,
        model_year,
        sector,
        enduse,
        timestamp,
        adjusted_value
    FROM {{ ref('load_shapes_expanded') }}
    WHERE sector IN ('Commercial', 'Industrial', 'Transportation')
),

load_shapes_annual_totals AS (
    -- Calculate annual energy totals from load shapes (for scaling)
    -- Sum across all enduses since STRIDE annual energy is at sector level
    SELECT
        geography,
        model_year,
        sector,
        SUM(adjusted_value) AS load_shape_annual_total
    FROM load_shapes_filtered
    GROUP BY geography, model_year, sector
),

stride_annual_energy_base AS (
    -- Get STRIDE annual energy projections (from energy intensity calculations)
    -- Convert from TJ to MWh (1 TJ = 277.777777778 MWh)
    SELECT
        geography,
        model_year,
        sector,
        subsector,
        value * 277.777777778 AS stride_annual_total
    FROM {{ table_ref('energy_intensity_com_ind_tra_gdp_applied_regression') }}
),

ev_annual_energy AS (
    -- Get EV-based annual energy projections if use_ev_projection is enabled
    -- Convert from TJ to MWh (1 TJ = 277.777777778 MWh)
    {% if var("use_ev_projection", False) %}
    SELECT
        geography,
        model_year,
        sector,
        subsector,
        value * 277.777777778 AS stride_annual_total
    FROM {{ table_ref('ev_annual_energy_tj') }}
    {% else %}
    -- Return empty result if EV projection is not enabled
    SELECT
        NULL AS geography,
        NULL AS model_year,
        NULL AS sector,
        NULL AS subsector,
        NULL AS stride_annual_total
    WHERE FALSE
    {% endif %}
),

stride_annual_energy AS (
    -- Combine base energy intensity projections with optional EV projections
    -- If use_ev_projection is true, replace Transportation + Road with EV-based calculation
    -- Tag each row with energy_source so we can assign distinct metrics later
    SELECT
        geography,
        model_year,
        sector,
        subsector,
        stride_annual_total,
        'base' AS energy_source
    FROM stride_annual_energy_base
    WHERE NOT (sector = 'Transportation' AND subsector = 'Road' AND {{ var("use_ev_projection", False) }})
    
    UNION ALL
    
    SELECT
        geography,
        model_year,
        sector,
        subsector,
        stride_annual_total,
        'ev' AS energy_source
    FROM ev_annual_energy
),

scaling_factors AS (
    -- Compute scaling factor: STRIDE annual / load shape annual
    -- This scales the temperature-adjusted load shapes to match STRIDE totals
    -- Same scaling factor applies to all enduses within a sector
    -- Note: Load shapes are at sector level, so we aggregate subsectors
    -- When EV is enabled, Transportation gets two scaling factors (base vs ev)
    SELECT
        ls.geography,
        ls.model_year,
        ls.sector,
        stride.energy_source,
        CASE 
            WHEN ls.load_shape_annual_total > 0 
            THEN SUM(stride.stride_annual_total) / ls.load_shape_annual_total
            ELSE 1.0
        END AS scaling_factor
    FROM load_shapes_annual_totals ls
    JOIN stride_annual_energy stride
        ON ls.geography = stride.geography
        AND ls.model_year = stride.model_year
        AND ls.sector = stride.sector
    GROUP BY ls.geography, ls.model_year, ls.sector,
             ls.load_shape_annual_total, stride.energy_source
)

-- Non-EV rows: use base scaling factor, keep original end-use metric
SELECT
    ls.timestamp,
    ls.model_year,
    ls.geography,
    ls.sector,
    ls.enduse AS metric,
    ls.adjusted_value * sf.scaling_factor AS value
FROM load_shapes_filtered ls
JOIN scaling_factors sf
    ON ls.geography = sf.geography
    AND ls.model_year = sf.model_year
    AND ls.sector = sf.sector
WHERE sf.energy_source = 'base'

UNION ALL

-- EV rows: use EV scaling factor, single 'ev_charging' metric per hour.
-- Aggregate load shape across enduses to avoid per-enduse duplication.
-- Only applies to Transportation sector when EV projection is enabled.
{% if var('use_ev_load_shape', false) %}
-- Custom EV load shape: normalize user-provided profile and use for hourly distribution
SELECT
    ls_ts.timestamp,
    ls_ts.model_year,
    ls_ts.geography,
    'Transportation' AS sector,
    'ev_charging' AS metric,
    (ep.profile_value / ep_total.total_value) * ev_totals.ev_annual_mwh AS value
FROM (
    SELECT DISTINCT timestamp, model_year, geography,
        ROW_NUMBER() OVER (PARTITION BY model_year, geography ORDER BY timestamp) AS hour_idx
    FROM load_shapes_filtered
    WHERE sector = 'Transportation'
) ls_ts
JOIN (
    SELECT hour_idx, value AS profile_value
    FROM {{ source('scenario', 'ev_load_shape') }}
) ep ON ls_ts.hour_idx = ep.hour_idx
CROSS JOIN (
    SELECT SUM(value) AS total_value
    FROM {{ source('scenario', 'ev_load_shape') }}
) ep_total
JOIN (
    SELECT geography, model_year, SUM(stride_annual_total) AS ev_annual_mwh
    FROM ev_annual_energy
    GROUP BY geography, model_year
) ev_totals
    ON ls_ts.geography = ev_totals.geography
    AND ls_ts.model_year = ev_totals.model_year
{% else %}
-- Fallback: use Transportation sector aggregate shape for EV hourly distribution
SELECT
    ls.timestamp,
    ls.model_year,
    ls.geography,
    ls.sector,
    'ev_charging' AS metric,
    SUM(ls.adjusted_value) * sf.scaling_factor AS value
FROM load_shapes_filtered ls
JOIN scaling_factors sf
    ON ls.geography = sf.geography
    AND ls.model_year = sf.model_year
    AND ls.sector = sf.sector
WHERE sf.energy_source = 'ev'
  AND ls.sector = 'Transportation'
GROUP BY ls.timestamp, ls.model_year, ls.geography, ls.sector, sf.scaling_factor
{% endif %}
{% endif %}
