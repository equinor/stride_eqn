-- Annual-only projection: skip hourly load shapes, output one row per
-- sector × subsector × model_year with total annual MWh (no timestamp).

WITH res_annual AS (
    SELECT
        geography,
        model_year,
        sector,
        subsector AS metric,
        value * 277.777777778 AS value
    FROM {{ table_ref('energy_intensity_res_hdi_population_applied_regression') }}
),

cit_annual_base AS (
    SELECT
        geography,
        model_year,
        sector,
        subsector AS metric,
        value * 277.777777778 AS value
    FROM {{ table_ref('energy_intensity_com_ind_tra_gdp_applied_regression') }}
),

ev_annual AS (
    {% if var("use_ev_projection", false) %}
    SELECT
        geography,
        model_year,
        sector,
        subsector AS metric,
        value * 277.777777778 AS value
    FROM {{ table_ref('ev_annual_energy_tj') }}
    {% else %}
    SELECT
        NULL AS geography,
        NULL::INT AS model_year,
        NULL AS sector,
        NULL AS metric,
        NULL::DOUBLE AS value
    WHERE FALSE
    {% endif %}
),

cit_annual AS (
    SELECT geography, model_year, sector, metric, value
    FROM cit_annual_base
    WHERE NOT (sector = 'Transportation' AND metric = 'Road'
               AND {{ var("use_ev_projection", false) }})

    UNION ALL

    SELECT geography, model_year, sector, metric, value
    FROM ev_annual
)

SELECT
    NULL::TIMESTAMP AS timestamp,
    model_year,
    '{{ var("scenario") }}' AS scenario,
    sector,
    geography,
    metric,
    value
FROM (
    SELECT * FROM res_annual
    UNION ALL
    SELECT * FROM cit_annual
)
