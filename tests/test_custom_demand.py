"""Tests for custom demand component functionality.

Covers:
- CustomDemandComponent model validation (3a)
- Flat profile injection (3b)
- Sector/enduse reference profile injection (3c)
- File-based 8760 profile injection (3c)
- Edge cases: bad schema, missing years, invalid references (3d)
- CLI commands: add, list, remove (3d)
"""

from __future__ import annotations

import csv
from pathlib import Path

import duckdb
import pytest
from chronify.exceptions import InvalidParameter
from click.testing import CliRunner
from pydantic import ValidationError

from stride.cli.stride import cli
from stride.io import create_table_from_file
from stride.models import CustomDemandComponent

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

HOURS_PER_YEAR = 4  # small count to keep tests fast
MODEL_YEARS = [2025, 2030]


def _make_annual_csv(tmp_path: Path, name: str = "annual.csv", years: list[int] | None = None,
                     values: list[float] | None = None) -> Path:
    """Write a simple model_year,value CSV and return its path."""
    years = years or MODEL_YEARS
    values = values or [float(y - 2024) * 1e6 for y in years]
    p = tmp_path / name
    with open(p, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["model_year", "value"])
        for y, v in zip(years, values):
            w.writerow([y, v])
    return p


def _make_profile_csv(tmp_path: Path, n_rows: int = 8760, name: str = "profile.csv") -> Path:
    """Write an 8760-row profile CSV with linearly increasing values."""
    p = tmp_path / name
    with open(p, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["value"])
        for i in range(1, n_rows + 1):
            w.writerow([float(i)])
    return p


def _setup_db(
    con: duckdb.DuckDBPyConnection,
    scenario: str = "baseline",
    hours: int = HOURS_PER_YEAR,
    model_years: list[int] | None = None,
    with_load_shapes: bool = False,
) -> None:
    """Create minimal energy_projection table and optionally load_shapes_expanded."""
    model_years = model_years or MODEL_YEARS
    con.sql(f"CREATE SCHEMA IF NOT EXISTS {scenario}")
    con.sql("CREATE SCHEMA IF NOT EXISTS stride")

    # Per-scenario energy_projection table (materialized, as it would be after
    # the view→table conversion in compute_energy_projection).
    con.sql(f"""
        CREATE TABLE {scenario}.energy_projection (
            timestamp TIMESTAMP,
            model_year BIGINT,
            geography VARCHAR,
            sector VARCHAR,
            metric VARCHAR,
            value DOUBLE,
            scenario VARCHAR
        )
    """)

    for yr in model_years:
        if hours <= 24:
            rows = ", ".join(
                f"(TIMESTAMP '2016-01-01 {h:02d}:00:00', {yr}, 'Germany', 'Residential', "
                f"'heating', 100.0, '{scenario}')"
                for h in range(hours)
            )
            con.sql(f"INSERT INTO {scenario}.energy_projection VALUES {rows}")
        else:
            # Generate multi-day timestamps for large hour counts (e.g., 8760)
            con.sql(f"""
                INSERT INTO {scenario}.energy_projection
                SELECT
                    TIMESTAMP '2016-01-01 00:00:00' + INTERVAL (i) HOUR AS timestamp,
                    {yr} AS model_year,
                    'Germany' AS geography,
                    'Residential' AS sector,
                    'heating' AS metric,
                    100.0 AS value,
                    '{scenario}' AS scenario
                FROM generate_series(0, {hours - 1}) AS t(i)
            """)

    if with_load_shapes:
        con.sql(f"""
            CREATE TABLE {scenario}.load_shapes_expanded (
                geography VARCHAR, model_year BIGINT, sector VARCHAR, enduse VARCHAR,
                timestamp TIMESTAMP, weather_year INT,
                load_shape_value DOUBLE, multiplier DOUBLE, adjusted_value DOUBLE
            )
        """)
        # Residential: heating [40,30,20,10], cooling [5,10,30,55]
        # Commercial: heating [20,30,30,20]
        patterns = [
            ("Residential", "heating", [40, 30, 20, 10]),
            ("Residential", "cooling", [5, 10, 30, 55]),
            ("Commercial", "heating", [20, 30, 30, 20]),
        ]
        for yr in model_years:
            for sector, enduse, vals in patterns:
                for h, v in enumerate(vals[:hours]):
                    con.sql(f"""
                        INSERT INTO {scenario}.load_shapes_expanded VALUES
                        ('Germany', {yr}, '{sector}', '{enduse}',
                         '2016-01-01 {h:02d}:00:00', 2016, {v}, 1.0, {v})
                    """)


# ---------------------------------------------------------------------------
# 3a: Model validation
# ---------------------------------------------------------------------------


class TestCustomDemandComponentModel:
    def test_valid_component(self, tmp_path: Path) -> None:
        csv_path = _make_annual_csv(tmp_path)
        c = CustomDemandComponent(
            name="heat_pumps", sector="Heat Pumps", data_file=csv_path,
        )
        assert c.load_profile == "flat"
        assert c.metric == "other"

    def test_name_must_be_identifier(self, tmp_path: Path) -> None:
        csv_path = _make_annual_csv(tmp_path)
        with pytest.raises(ValidationError, match="valid Python identifier"):
            CustomDemandComponent(
                name="bad-name", sector="X", data_file=csv_path,
            )

    def test_name_with_spaces_rejected(self, tmp_path: Path) -> None:
        csv_path = _make_annual_csv(tmp_path)
        with pytest.raises(ValidationError, match="valid Python identifier"):
            CustomDemandComponent(
                name="bad name", sector="X", data_file=csv_path,
            )

    def test_custom_profile_options(self, tmp_path: Path) -> None:
        csv_path = _make_annual_csv(tmp_path)
        c = CustomDemandComponent(
            name="x", sector="X", data_file=csv_path,
            load_profile="sector:Residential", metric="heating",
        )
        assert c.load_profile == "sector:Residential"
        assert c.metric == "heating"


# ---------------------------------------------------------------------------
# 3b: Flat profile injection
# ---------------------------------------------------------------------------


class TestFlatProfileInjection:
    def test_flat_injection_row_count(self, tmp_path: Path) -> None:
        con = duckdb.connect()
        _setup_db(con)
        csv_path = _make_annual_csv(tmp_path)
        staging = "stride.custom__dc__baseline__annual"
        create_table_from_file(con, staging, csv_path, replace=True)

        sql = f"""
            WITH annual_data AS (
                SELECT model_year, value AS annual_mwh
                FROM {staging}
                WHERE model_year IN (2025, 2030)
            ),
            hourly_timestamps AS (
                SELECT DISTINCT timestamp, model_year
                FROM baseline.energy_projection
            )
            SELECT
                ht.timestamp, ht.model_year,
                'Germany' AS geography,
                'Data Centers' AS sector,
                'other' AS metric,
                ad.annual_mwh / {HOURS_PER_YEAR}.0 AS value,
                'baseline' AS scenario
            FROM hourly_timestamps ht
            JOIN annual_data ad ON ht.model_year = ad.model_year
        """
        con.sql(f"INSERT INTO baseline.energy_projection {sql}")

        count = con.sql(
            "SELECT COUNT(*) FROM baseline.energy_projection "
            "WHERE sector = 'Data Centers'"
        ).fetchone()[0]
        assert count == HOURS_PER_YEAR * len(MODEL_YEARS)

    def test_flat_injection_annual_totals(self, tmp_path: Path) -> None:
        con = duckdb.connect()
        _setup_db(con)
        csv_path = _make_annual_csv(tmp_path, values=[1_000_000, 2_000_000])
        staging = "stride.custom__dc__baseline__annual"
        create_table_from_file(con, staging, csv_path, replace=True)

        sql = f"""
            WITH annual_data AS (
                SELECT model_year, value AS annual_mwh
                FROM {staging}
                WHERE model_year IN (2025, 2030)
            ),
            hourly_timestamps AS (
                SELECT DISTINCT timestamp, model_year
                FROM baseline.energy_projection
            )
            SELECT
                ht.timestamp, ht.model_year,
                'Germany' AS geography,
                'DC' AS sector,
                'other' AS metric,
                ad.annual_mwh / {HOURS_PER_YEAR}.0 AS value,
                'baseline' AS scenario
            FROM hourly_timestamps ht
            JOIN annual_data ad ON ht.model_year = ad.model_year
        """
        con.sql(f"INSERT INTO baseline.energy_projection {sql}")

        for yr, expected in [(2025, 1_000_000), (2030, 2_000_000)]:
            actual = con.sql(
                f"SELECT SUM(value) FROM baseline.energy_projection "
                f"WHERE sector = 'DC' AND model_year = {yr}"
            ).fetchone()[0]
            assert abs(actual - expected) < 0.01

    def test_flat_injection_preserves_existing(self, tmp_path: Path) -> None:
        con = duckdb.connect()
        _setup_db(con)
        csv_path = _make_annual_csv(tmp_path)
        staging = "stride.custom__dc__baseline__annual"
        create_table_from_file(con, staging, csv_path, replace=True)

        before = con.sql(
            "SELECT COUNT(*) FROM baseline.energy_projection WHERE sector = 'Residential'"
        ).fetchone()[0]

        sql = f"""
            WITH annual_data AS (
                SELECT model_year, value AS annual_mwh
                FROM {staging} WHERE model_year IN (2025, 2030)
            ),
            hourly_timestamps AS (
                SELECT DISTINCT timestamp, model_year FROM baseline.energy_projection
            )
            SELECT ht.timestamp, ht.model_year, 'Germany', 'DC', 'other',
                   ad.annual_mwh / {HOURS_PER_YEAR}.0, 'baseline'
            FROM hourly_timestamps ht
            JOIN annual_data ad ON ht.model_year = ad.model_year
        """
        con.sql(f"INSERT INTO baseline.energy_projection {sql}")

        after = con.sql(
            "SELECT COUNT(*) FROM baseline.energy_projection WHERE sector = 'Residential'"
        ).fetchone()[0]
        assert after == before

    def test_idempotent_delete_reinsert(self, tmp_path: Path) -> None:
        con = duckdb.connect()
        _setup_db(con)
        csv_path = _make_annual_csv(tmp_path)
        staging = "stride.custom__dc__baseline__annual"
        create_table_from_file(con, staging, csv_path, replace=True)

        sql = f"""
            SELECT ht.timestamp, ht.model_year, 'Germany', 'DC', 'other',
                   ad.annual_mwh / {HOURS_PER_YEAR}.0, 'baseline'
            FROM (SELECT DISTINCT timestamp, model_year FROM baseline.energy_projection) ht
            JOIN (SELECT model_year, value AS annual_mwh FROM {staging}
                  WHERE model_year IN (2025, 2030)) ad
            ON ht.model_year = ad.model_year
        """
        con.sql(f"INSERT INTO baseline.energy_projection {sql}")
        con.sql("DELETE FROM baseline.energy_projection WHERE sector = 'DC'")
        con.sql(f"INSERT INTO baseline.energy_projection {sql}")
        count = con.sql(
            "SELECT COUNT(*) FROM baseline.energy_projection WHERE sector = 'DC'"
        ).fetchone()[0]
        assert count == HOURS_PER_YEAR * len(MODEL_YEARS)


# ---------------------------------------------------------------------------
# 3c: Reference profile injection (sector/enduse)
# ---------------------------------------------------------------------------


class TestReferenceProfileInjection:
    def test_sector_profile_annual_totals(self, tmp_path: Path) -> None:
        con = duckdb.connect()
        _setup_db(con, with_load_shapes=True)
        csv_path = _make_annual_csv(tmp_path, values=[1_000_000, 2_000_000])
        staging = "stride.custom__hp__baseline__annual"
        create_table_from_file(con, staging, csv_path, replace=True)

        sql = f"""
            WITH annual_data AS (
                SELECT model_year, value AS annual_mwh FROM {staging}
                WHERE model_year IN (2025, 2030)
            ),
            aggregated_shape AS (
                SELECT timestamp, model_year, SUM(adjusted_value) AS total
                FROM baseline.load_shapes_expanded
                WHERE sector = 'Residential' AND model_year IN (2025, 2030)
                GROUP BY timestamp, model_year
            ),
            reference_shape AS (
                SELECT timestamp, model_year,
                    total / SUM(total) OVER (PARTITION BY model_year) AS fraction
                FROM aggregated_shape
            )
            SELECT rs.timestamp, rs.model_year, 'Germany', 'HP', 'heating',
                   ad.annual_mwh * rs.fraction, 'baseline'
            FROM reference_shape rs
            JOIN annual_data ad ON rs.model_year = ad.model_year
        """
        con.sql(f"INSERT INTO baseline.energy_projection {sql}")

        for yr, expected in [(2025, 1_000_000), (2030, 2_000_000)]:
            actual = con.sql(
                f"SELECT SUM(value) FROM baseline.energy_projection "
                f"WHERE sector = 'HP' AND model_year = {yr}"
            ).fetchone()[0]
            assert abs(actual - expected) < 0.01

    def test_sector_profile_shape_not_flat(self, tmp_path: Path) -> None:
        con = duckdb.connect()
        _setup_db(con, with_load_shapes=True)
        csv_path = _make_annual_csv(tmp_path, values=[1_000_000, 2_000_000])
        staging = "stride.custom__hp__baseline__annual"
        create_table_from_file(con, staging, csv_path, replace=True)

        sql = f"""
            WITH annual_data AS (
                SELECT model_year, value AS annual_mwh FROM {staging}
                WHERE model_year IN (2025, 2030)
            ),
            agg AS (
                SELECT timestamp, model_year, SUM(adjusted_value) AS total
                FROM baseline.load_shapes_expanded
                WHERE sector = 'Residential' AND model_year IN (2025, 2030)
                GROUP BY timestamp, model_year
            ),
            ref AS (
                SELECT timestamp, model_year,
                    total / SUM(total) OVER (PARTITION BY model_year) AS fraction
                FROM agg
            )
            SELECT ref.timestamp, ref.model_year, 'Germany', 'HP', 'heating',
                   ad.annual_mwh * ref.fraction, 'baseline'
            FROM ref JOIN annual_data ad ON ref.model_year = ad.model_year
        """
        con.sql(f"INSERT INTO baseline.energy_projection {sql}")

        vals = con.sql(
            "SELECT value FROM baseline.energy_projection "
            "WHERE sector = 'HP' AND model_year = 2025 ORDER BY timestamp"
        ).fetchall()
        hourly = [r[0] for r in vals]
        # Residential aggregate: heating[40,30,20,10]+cooling[5,10,30,55]=[45,40,50,65]
        # Not all equal → not flat
        assert len(set(hourly)) > 1, "Sector profile should NOT be flat"

    def test_enduse_profile_annual_totals(self, tmp_path: Path) -> None:
        con = duckdb.connect()
        _setup_db(con, with_load_shapes=True)
        csv_path = _make_annual_csv(tmp_path, values=[1_000_000, 2_000_000])
        staging = "stride.custom__hp__baseline__annual"
        create_table_from_file(con, staging, csv_path, replace=True)

        sql = f"""
            WITH annual_data AS (
                SELECT model_year, value AS annual_mwh FROM {staging}
                WHERE model_year IN (2025, 2030)
            ),
            agg AS (
                SELECT timestamp, model_year, SUM(adjusted_value) AS total
                FROM baseline.load_shapes_expanded
                WHERE enduse = 'heating' AND model_year IN (2025, 2030)
                GROUP BY timestamp, model_year
            ),
            ref AS (
                SELECT timestamp, model_year,
                    total / SUM(total) OVER (PARTITION BY model_year) AS fraction
                FROM agg
            )
            SELECT ref.timestamp, ref.model_year, 'Germany', 'HP', 'heating',
                   ad.annual_mwh * ref.fraction, 'baseline'
            FROM ref JOIN annual_data ad ON ref.model_year = ad.model_year
        """
        con.sql(f"INSERT INTO baseline.energy_projection {sql}")

        for yr, expected in [(2025, 1_000_000), (2030, 2_000_000)]:
            actual = con.sql(
                f"SELECT SUM(value) FROM baseline.energy_projection "
                f"WHERE sector = 'HP' AND model_year = {yr}"
            ).fetchone()[0]
            assert abs(actual - expected) < 0.01

    def test_sector_and_enduse_profiles_differ(self, tmp_path: Path) -> None:
        """sector:Residential and enduse:heating should produce different shapes."""
        con = duckdb.connect()
        _setup_db(con, with_load_shapes=True)
        csv_path = _make_annual_csv(tmp_path, values=[1_000_000, 2_000_000])
        staging = "stride.custom__hp__baseline__annual"
        create_table_from_file(con, staging, csv_path, replace=True)

        # sector:Residential
        sector_sql = f"""
            WITH ad AS (SELECT model_year, value AS mwh FROM {staging} WHERE model_year=2025),
            agg AS (SELECT timestamp, model_year, SUM(adjusted_value) AS t
                    FROM baseline.load_shapes_expanded WHERE sector='Residential' AND model_year=2025
                    GROUP BY timestamp, model_year),
            ref AS (SELECT timestamp, model_year, t/SUM(t) OVER (PARTITION BY model_year) AS f FROM agg)
            SELECT ref.timestamp, ad.mwh * ref.f AS value
            FROM ref JOIN ad ON ref.model_year = ad.model_year ORDER BY ref.timestamp
        """
        sector_vals = [r[1] for r in con.sql(sector_sql).fetchall()]

        # enduse:heating
        enduse_sql = f"""
            WITH ad AS (SELECT model_year, value AS mwh FROM {staging} WHERE model_year=2025),
            agg AS (SELECT timestamp, model_year, SUM(adjusted_value) AS t
                    FROM baseline.load_shapes_expanded WHERE enduse='heating' AND model_year=2025
                    GROUP BY timestamp, model_year),
            ref AS (SELECT timestamp, model_year, t/SUM(t) OVER (PARTITION BY model_year) AS f FROM agg)
            SELECT ref.timestamp, ad.mwh * ref.f AS value
            FROM ref JOIN ad ON ref.model_year = ad.model_year ORDER BY ref.timestamp
        """
        enduse_vals = [r[1] for r in con.sql(enduse_sql).fetchall()]

        assert sector_vals != enduse_vals


# ---------------------------------------------------------------------------
# 3c (cont): File-based 8760 profile
# ---------------------------------------------------------------------------


class TestFileProfileInjection:
    def test_file_profile_annual_totals(self, tmp_path: Path) -> None:
        """An 8760-row profile file should distribute annual energy correctly."""
        con = duckdb.connect()
        n_hours = 8760
        _setup_db(con, hours=n_hours, model_years=[2025])
        csv_path = _make_annual_csv(tmp_path, years=[2025], values=[1_000_000.0])
        profile_path = _make_profile_csv(tmp_path, n_rows=n_hours)

        staging = "stride.custom__dc__baseline__annual"
        create_table_from_file(con, staging, csv_path, replace=True)
        profile_table = "stride.custom__dc__baseline__profile"
        create_table_from_file(con, profile_table, profile_path, replace=True)

        sql = f"""
            WITH annual_data AS (
                SELECT model_year, value AS annual_mwh FROM {staging}
                WHERE model_year = 2025
            ),
            hourly_timestamps AS (
                SELECT DISTINCT timestamp, model_year,
                    ROW_NUMBER() OVER (PARTITION BY model_year ORDER BY timestamp) AS hour_idx
                FROM baseline.energy_projection
            ),
            profile_data AS (
                SELECT ROW_NUMBER() OVER (ORDER BY rowid) AS hour_idx,
                    value AS profile_value FROM {profile_table}
            ),
            profile_normalized AS (
                SELECT hour_idx,
                    profile_value / SUM(profile_value) OVER () AS fraction
                FROM profile_data
            )
            SELECT ht.timestamp, ht.model_year, 'Germany', 'DC', 'other',
                   ad.annual_mwh * pn.fraction, 'baseline'
            FROM hourly_timestamps ht
            JOIN annual_data ad ON ht.model_year = ad.model_year
            JOIN profile_normalized pn ON ht.hour_idx = pn.hour_idx
        """
        con.sql(f"INSERT INTO baseline.energy_projection {sql}")

        actual = con.sql(
            "SELECT SUM(value) FROM baseline.energy_projection "
            "WHERE sector = 'DC' AND model_year = 2025"
        ).fetchone()[0]
        assert abs(actual - 1_000_000.0) < 0.01

    def test_file_profile_shape_not_flat(self, tmp_path: Path) -> None:
        """A non-uniform profile file should produce non-uniform hourly values."""
        con = duckdb.connect()
        n_hours = 8760
        _setup_db(con, hours=n_hours, model_years=[2025])
        csv_path = _make_annual_csv(tmp_path, years=[2025], values=[1_000_000.0])
        profile_path = _make_profile_csv(tmp_path, n_rows=n_hours)

        staging = "stride.custom__dc__baseline__annual"
        create_table_from_file(con, staging, csv_path, replace=True)
        profile_table = "stride.custom__dc__baseline__profile"
        create_table_from_file(con, profile_table, profile_path, replace=True)

        sql = f"""
            WITH annual_data AS (
                SELECT model_year, value AS annual_mwh FROM {staging}
                WHERE model_year = 2025
            ),
            hourly_timestamps AS (
                SELECT DISTINCT timestamp, model_year,
                    ROW_NUMBER() OVER (PARTITION BY model_year ORDER BY timestamp) AS hour_idx
                FROM baseline.energy_projection
            ),
            profile_data AS (
                SELECT ROW_NUMBER() OVER (ORDER BY rowid) AS hour_idx,
                    value AS profile_value FROM {profile_table}
            ),
            profile_normalized AS (
                SELECT hour_idx,
                    profile_value / SUM(profile_value) OVER () AS fraction
                FROM profile_data
            )
            SELECT ht.timestamp, ht.model_year, 'Germany', 'DC', 'other',
                   ad.annual_mwh * pn.fraction, 'baseline'
            FROM hourly_timestamps ht
            JOIN annual_data ad ON ht.model_year = ad.model_year
            JOIN profile_normalized pn ON ht.hour_idx = pn.hour_idx
        """
        result = con.sql(sql).fetchall()
        vals = [r[5] for r in result]
        assert len(set(vals)) > 1, "File profile should NOT produce flat output"


# ---------------------------------------------------------------------------
# 3d: Edge cases & validation
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_missing_value_column(self, tmp_path: Path) -> None:
        """CSV without 'value' column should be rejected."""
        csv_path = tmp_path / "bad.csv"
        with open(csv_path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["model_year", "amount"])
            w.writerow([2025, 100])

        con = duckdb.connect()
        _setup_db(con)
        staging = "stride.custom__dc__baseline__annual"
        create_table_from_file(con, staging, csv_path, replace=True)

        columns = [col[0] for col in con.sql(f"DESCRIBE {staging}").fetchall()]
        assert "value" not in columns

    def test_missing_model_year_column(self, tmp_path: Path) -> None:
        """CSV without 'model_year' column should be rejected."""
        csv_path = tmp_path / "bad.csv"
        with open(csv_path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["year", "value"])
            w.writerow([2025, 100])

        con = duckdb.connect()
        _setup_db(con)
        staging = "stride.custom__dc__baseline__annual"
        create_table_from_file(con, staging, csv_path, replace=True)

        columns = [col[0] for col in con.sql(f"DESCRIBE {staging}").fetchall()]
        assert "model_year" not in columns

    def test_missing_years_in_data(self, tmp_path: Path) -> None:
        """CSV missing required model years should be detectable."""
        csv_path = _make_annual_csv(tmp_path, years=[2025], values=[1_000_000])
        con = duckdb.connect()
        _setup_db(con)
        staging = "stride.custom__dc__baseline__annual"
        create_table_from_file(con, staging, csv_path, replace=True)

        available = {
            row[0] for row in con.sql(
                f"SELECT DISTINCT model_year FROM {staging}"
            ).fetchall()
        }
        required = set(MODEL_YEARS)
        assert required - available == {2030}

    def test_unknown_sector_reference(self, tmp_path: Path) -> None:
        """Referencing a non-existent sector in load_shapes_expanded returns 0 rows."""
        con = duckdb.connect()
        _setup_db(con, with_load_shapes=True)

        count = con.sql(
            "SELECT COUNT(*) FROM baseline.load_shapes_expanded "
            "WHERE sector = 'Manufacturing' AND model_year IN (2025, 2030)"
        ).fetchone()[0]
        assert count == 0

    def test_unknown_enduse_reference(self, tmp_path: Path) -> None:
        """Referencing a non-existent enduse in load_shapes_expanded returns 0 rows."""
        con = duckdb.connect()
        _setup_db(con, with_load_shapes=True)

        count = con.sql(
            "SELECT COUNT(*) FROM baseline.load_shapes_expanded "
            "WHERE enduse = 'transport' AND model_year IN (2025, 2030)"
        ).fetchone()[0]
        assert count == 0

    def test_file_profile_wrong_row_count(self, tmp_path: Path) -> None:
        """Profile CSV with != 8760 rows should be detectable."""
        profile_path = _make_profile_csv(tmp_path, n_rows=100)
        con = duckdb.connect()
        con.sql("CREATE SCHEMA IF NOT EXISTS stride")
        create_table_from_file(con, "stride.profile", profile_path, replace=True)
        count = con.sql("SELECT COUNT(*) FROM stride.profile").fetchone()[0]
        assert count != 8760

    def test_file_profile_missing_value_column(self, tmp_path: Path) -> None:
        """Profile CSV without 'value' column should be detectable."""
        csv_path = tmp_path / "bad_profile.csv"
        with open(csv_path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["load"])
            for i in range(8760):
                w.writerow([i])

        con = duckdb.connect()
        con.sql("CREATE SCHEMA IF NOT EXISTS stride")
        create_table_from_file(con, "stride.profile", csv_path, replace=True)
        columns = [col[0] for col in con.sql("DESCRIBE stride.profile").fetchall()]
        assert "value" not in columns


# ---------------------------------------------------------------------------
# 3d (cont): CLI commands
# ---------------------------------------------------------------------------


class TestCustomDemandCLI:
    def test_list_empty(self, copy_project_input_data: tuple[Path, Path, Path]) -> None:
        """Listing components on a project with none configured."""
        scratch, data_dir, config_path = copy_project_input_data
        runner = CliRunner()
        result = runner.invoke(cli, [
            "projects", "create", str(config_path),
            "--directory", str(scratch),
            "--dataset", "global-test",
        ])
        assert result.exit_code == 0, result.output

        project_dir = scratch / "test_project"
        result = runner.invoke(cli, ["custom-demand", "list", str(project_dir)])
        assert result.exit_code == 0, result.output
        assert "No custom demand components" in result.output

    def test_add_list_remove_cycle(
        self, copy_project_input_data: tuple[Path, Path, Path], tmp_path: Path,
    ) -> None:
        """Full add → list → remove lifecycle."""
        scratch, data_dir, config_path = copy_project_input_data
        runner = CliRunner()
        result = runner.invoke(cli, [
            "projects", "create", str(config_path),
            "--directory", str(scratch),
            "--dataset", "global-test",
        ])
        assert result.exit_code == 0, result.output
        project_dir = scratch / "test_project"

        # Create annual CSV with correct model years for this project
        csv_path = _make_annual_csv(
            tmp_path,
            years=[2025, 2030, 2035, 2040, 2045, 2050],
            values=[1e6, 2e6, 3e6, 4e6, 5e6, 6e6],
        )

        # Add
        result = runner.invoke(cli, [
            "custom-demand", "add", str(project_dir),
            "--name", "data_centers",
            "--sector", "Data Centers",
            "--data-file", str(csv_path),
        ])
        assert result.exit_code == 0, result.output
        assert "Added custom demand component" in result.output

        # List
        result = runner.invoke(cli, ["custom-demand", "list", str(project_dir)])
        assert result.exit_code == 0, result.output
        assert "data_centers" in result.output
        assert "Data Centers" in result.output

        # Remove
        result = runner.invoke(cli, [
            "custom-demand", "remove", str(project_dir),
            "--name", "data_centers",
        ])
        assert result.exit_code == 0, result.output
        assert "Removed" in result.output

        # List again — empty
        result = runner.invoke(cli, ["custom-demand", "list", str(project_dir)])
        assert result.exit_code == 0, result.output
        assert "No custom demand components" in result.output

    def test_add_duplicate_rejected(
        self, copy_project_input_data: tuple[Path, Path, Path], tmp_path: Path,
    ) -> None:
        """Adding a component with an existing name should fail."""
        scratch, data_dir, config_path = copy_project_input_data
        runner = CliRunner()
        result = runner.invoke(cli, [
            "projects", "create", str(config_path),
            "--directory", str(scratch),
            "--dataset", "global-test",
        ])
        assert result.exit_code == 0, result.output
        project_dir = scratch / "test_project"

        csv_path = _make_annual_csv(
            tmp_path,
            years=[2025, 2030, 2035, 2040, 2045, 2050],
            values=[1e6, 2e6, 3e6, 4e6, 5e6, 6e6],
        )

        # First add
        result = runner.invoke(cli, [
            "custom-demand", "add", str(project_dir),
            "--name", "dc", "--sector", "DC",
            "--data-file", str(csv_path),
        ])
        assert result.exit_code == 0, result.output

        # Duplicate add
        result = runner.invoke(cli, [
            "custom-demand", "add", str(project_dir),
            "--name", "dc", "--sector", "DC",
            "--data-file", str(csv_path),
        ])
        assert result.exit_code != 0

    def test_remove_nonexistent_rejected(
        self, copy_project_input_data: tuple[Path, Path, Path],
    ) -> None:
        """Removing a component that doesn't exist should fail."""
        scratch, data_dir, config_path = copy_project_input_data
        runner = CliRunner()
        result = runner.invoke(cli, [
            "projects", "create", str(config_path),
            "--directory", str(scratch),
            "--dataset", "global-test",
        ])
        assert result.exit_code == 0, result.output
        project_dir = scratch / "test_project"

        result = runner.invoke(cli, [
            "custom-demand", "remove", str(project_dir),
            "--name", "nonexistent",
        ])
        assert result.exit_code != 0
