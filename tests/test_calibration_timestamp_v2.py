"""Tests for calibration timestamp fix v2 — date components approach.

Tests the following stride_eqn changes:
- _read_country_timezone(): reads timezone from dimensions/countries.csv
- _resolve_historical_demand(): dual-path (new components + legacy timestamp)
- _find_alternative_sources(): handles both formats
"""

import calendar
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from chronify.exceptions import InvalidParameter

from stride.project import Project


# ---- Fixtures ----


def _create_components_parquet(
    path: Path,
    country: str = "Germany",
    year: int = 2019,
    tz_offset: int = 1,
) -> Path:
    """Create a date-components format parquet (v2 format).

    Generates 8760/8784 rows with weather_year, month, day, hour, geography, total_load_mwh.
    """
    n_hours = 8784 if calendar.isleap(year) else 8760
    # Standard-time local timestamps (no DST)
    local_start = pd.Timestamp(f"{year}-01-01 00:00:00")
    local_timestamps = pd.date_range(start=local_start, periods=n_hours, freq="h")

    df = pd.DataFrame(
        {
            "weather_year": local_timestamps.year.astype("int64"),
            "month": local_timestamps.month.astype("int64"),
            "day": local_timestamps.day.astype("int64"),
            "hour": local_timestamps.hour.astype("int64"),
            "geography": country,
            "total_load_mwh": np.random.default_rng(42).uniform(30000, 80000, n_hours),
        }
    )
    parquet_path = path / "load_data.parquet"
    df.to_parquet(parquet_path, index=False)
    return parquet_path


def _create_legacy_parquet(
    path: Path,
    country: str = "Germany",
    year: int = 2019,
) -> Path:
    """Create a legacy timestamp format parquet (v1/original format)."""
    n_hours = 8784 if calendar.isleap(year) else 8760
    timestamps = pd.date_range(
        start=f"{year}-01-01 00:00:00", periods=n_hours, freq="h", tz="UTC"
    )
    df = pd.DataFrame(
        {
            "timestamp": timestamps,
            "geography": country,
            "total_load_mwh": np.random.default_rng(42).uniform(30000, 80000, n_hours),
        }
    )
    parquet_path = path / "load_data.parquet"
    df.to_parquet(parquet_path, index=False)
    return parquet_path


def _create_countries_csv(path: Path, entries: list[tuple[str, str]]) -> Path:
    """Create a dimensions/countries.csv file.

    entries: list of (country_id, time_zone) tuples.
    """
    dimensions_dir = path / "dimensions"
    dimensions_dir.mkdir(parents=True, exist_ok=True)
    csv_path = dimensions_dir / "countries.csv"
    lines = ["id,name,time_zone"]
    for country_id, tz in entries:
        lines.append(f"{country_id},{country_id},{tz}")
    csv_path.write_text("\n".join(lines) + "\n")
    return csv_path


def _setup_dataset_dir(
    tmp_path: Path,
    source: str = "entsoe",
    country: str = "Germany",
    year: int = 2019,
    tz: str = "Etc/GMT-1",
    use_components: bool = True,
) -> Path:
    """Set up a fake dataset directory with parquet + countries.csv."""
    dataset_dir = tmp_path / "dataset"
    table_dir = dataset_dir / "profile_data" / f"historical_demand_{source}"
    table_dir.mkdir(parents=True)

    if use_components:
        _create_components_parquet(table_dir, country=country, year=year)
    else:
        _create_legacy_parquet(table_dir, country=country, year=year)

    _create_countries_csv(table_dir, [(country, tz)])
    return dataset_dir


# ---- Tests for _read_country_timezone ----


class TestReadCountryTimezone:
    """Tests for Project._read_country_timezone() helper."""

    def test_reads_timezone_for_known_country(self, tmp_path: Path) -> None:
        """Returns correct timezone string for a country in the CSV."""
        csv_path = _create_countries_csv(
            tmp_path,
            [("Germany", "Etc/GMT-1"), ("Greece", "Etc/GMT-2"), ("Portugal", "Etc/GMT")],
        )
        tz = Project._read_country_timezone(csv_path, "Germany")
        assert tz == "Etc/GMT-1"

    def test_reads_timezone_for_utc_country(self, tmp_path: Path) -> None:
        """Returns Etc/GMT for UTC-offset-0 country."""
        csv_path = _create_countries_csv(tmp_path, [("Portugal", "Etc/GMT")])
        tz = Project._read_country_timezone(csv_path, "Portugal")
        assert tz == "Etc/GMT"

    def test_reads_timezone_for_eet_country(self, tmp_path: Path) -> None:
        """Returns Etc/GMT-2 for EET country."""
        csv_path = _create_countries_csv(
            tmp_path, [("Finland", "Etc/GMT-2"), ("Greece", "Etc/GMT-2")]
        )
        tz = Project._read_country_timezone(csv_path, "Greece")
        assert tz == "Etc/GMT-2"

    def test_raises_for_unknown_country(self, tmp_path: Path) -> None:
        """Raises InvalidParameter if country not found in CSV."""
        csv_path = _create_countries_csv(tmp_path, [("Germany", "Etc/GMT-1")])
        with pytest.raises(InvalidParameter, match="not found"):
            Project._read_country_timezone(csv_path, "Atlantis")


# ---- Tests for _resolve_historical_demand (v2 components path) ----


class TestResolveHistoricalDemandComponents:
    """Tests for the new date-components code path in _resolve_historical_demand."""

    def test_returns_dataframe_with_timestamp_and_load(self, tmp_path: Path) -> None:
        """New format produces DataFrame with timestamp and total_load_mwh columns."""
        dataset_dir = _setup_dataset_dir(tmp_path, country="Germany", year=2019, tz="Etc/GMT-1")

        result = Project._resolve_historical_demand_static(
            source="entsoe",
            dataset_dir=dataset_dir,
            country="Germany",
            year=2019,
        )
        assert result is not None
        assert set(result.columns) == {"timestamp", "total_load_mwh"}

    def test_returns_correct_row_count_non_leap(self, tmp_path: Path) -> None:
        """Non-leap year returns 8760 rows."""
        dataset_dir = _setup_dataset_dir(tmp_path, country="Germany", year=2019, tz="Etc/GMT-1")

        result = Project._resolve_historical_demand_static(
            source="entsoe", dataset_dir=dataset_dir, country="Germany", year=2019
        )
        assert result is not None
        assert len(result) == 8760

    def test_returns_correct_row_count_leap(self, tmp_path: Path) -> None:
        """Leap year returns 8784 rows."""
        dataset_dir = _setup_dataset_dir(
            tmp_path, country="Germany", year=2020, tz="Etc/GMT-1"
        )

        result = Project._resolve_historical_demand_static(
            source="entsoe", dataset_dir=dataset_dir, country="Germany", year=2020
        )
        assert result is not None
        assert len(result) == 8784

    def test_timestamp_has_correct_timezone(self, tmp_path: Path) -> None:
        """Constructed timestamps are localized to the country's standard timezone."""
        dataset_dir = _setup_dataset_dir(tmp_path, country="Germany", year=2019, tz="Etc/GMT-1")

        result = Project._resolve_historical_demand_static(
            source="entsoe", dataset_dir=dataset_dir, country="Germany", year=2019
        )
        assert result is not None
        # Check timezone info is present and correct
        assert result["timestamp"].dt.tz is not None
        # First timestamp should be 2019-01-01 00:00 in Etc/GMT-1
        first_ts = result["timestamp"].iloc[0]
        assert first_ts.year == 2019
        assert first_ts.month == 1
        assert first_ts.day == 1
        assert first_ts.hour == 0
        # UTC equivalent should be 2018-12-31 23:00 (offset -1h from local)
        utc_first = first_ts.tz_convert("UTC")
        assert utc_first.year == 2018
        assert utc_first.month == 12
        assert utc_first.day == 31
        assert utc_first.hour == 23

    def test_utc_country_no_offset(self, tmp_path: Path) -> None:
        """For UTC+0 country (Portugal), local == UTC."""
        dataset_dir = _setup_dataset_dir(
            tmp_path, country="Portugal", year=2019, tz="Etc/GMT"
        )

        result = Project._resolve_historical_demand_static(
            source="entsoe", dataset_dir=dataset_dir, country="Portugal", year=2019
        )
        assert result is not None
        first_ts = result["timestamp"].iloc[0]
        utc_first = first_ts.tz_convert("UTC")
        # For UTC+0, local time == UTC time
        assert utc_first.hour == 0
        assert utc_first.day == 1
        assert utc_first.month == 1
        assert utc_first.year == 2019

    def test_eet_country_offset(self, tmp_path: Path) -> None:
        """For EET country (Greece, UTC+2), local midnight = 22:00 UTC previous day."""
        dataset_dir = _setup_dataset_dir(
            tmp_path, country="Greece", year=2019, tz="Etc/GMT-2"
        )

        result = Project._resolve_historical_demand_static(
            source="entsoe", dataset_dir=dataset_dir, country="Greece", year=2019
        )
        assert result is not None
        first_ts = result["timestamp"].iloc[0]
        utc_first = first_ts.tz_convert("UTC")
        assert utc_first.year == 2018
        assert utc_first.month == 12
        assert utc_first.day == 31
        assert utc_first.hour == 22

    def test_returns_none_for_missing_country(self, tmp_path: Path) -> None:
        """Returns None when country not in parquet (no data available)."""
        dataset_dir = _setup_dataset_dir(tmp_path, country="Germany", year=2019, tz="Etc/GMT-1")

        result = Project._resolve_historical_demand_static(
            source="entsoe", dataset_dir=dataset_dir, country="France", year=2019
        )
        assert result is None

    def test_returns_none_for_missing_year(self, tmp_path: Path) -> None:
        """Returns None when year not in parquet."""
        dataset_dir = _setup_dataset_dir(tmp_path, country="Germany", year=2019, tz="Etc/GMT-1")

        result = Project._resolve_historical_demand_static(
            source="entsoe", dataset_dir=dataset_dir, country="Germany", year=2020
        )
        assert result is None


# ---- Tests for legacy format backward compatibility ----


class TestResolveHistoricalDemandLegacy:
    """Tests for the legacy timestamp path (backward compat)."""

    def test_legacy_format_still_works(self, tmp_path: Path) -> None:
        """Legacy parquet (timestamp column) still loads correctly."""
        dataset_dir = _setup_dataset_dir(
            tmp_path, country="Germany", year=2019, use_components=False
        )

        result = Project._resolve_historical_demand_static(
            source="entsoe", dataset_dir=dataset_dir, country="Germany", year=2019
        )
        assert result is not None
        assert "timestamp" in result.columns
        assert "total_load_mwh" in result.columns
        assert len(result) == 8760


# ---- Tests for _find_alternative_sources ----


class TestFindAlternativeSourcesV2:
    """Tests for _find_alternative_sources with both formats."""

    def test_finds_alternative_with_components_format(self, tmp_path: Path) -> None:
        """Detects availability in components-format parquet."""
        dataset_dir = tmp_path / "dataset"
        # Create entsoe (components) with Germany 2019
        entsoe_dir = dataset_dir / "profile_data" / "historical_demand_entsoe"
        entsoe_dir.mkdir(parents=True)
        _create_components_parquet(entsoe_dir, country="Germany", year=2019)

        # Create smard (components) with Germany 2019
        smard_dir = dataset_dir / "profile_data" / "historical_demand_smard"
        smard_dir.mkdir(parents=True)
        _create_components_parquet(smard_dir, country="Germany", year=2019)

        result = Project._find_alternative_sources_static(
            dataset_dir=dataset_dir, country="Germany", year=2019, exclude="entsoe"
        )
        assert "smard" in result

    def test_finds_alternative_with_legacy_format(self, tmp_path: Path) -> None:
        """Detects availability in legacy-format parquet."""
        dataset_dir = tmp_path / "dataset"
        # Create smard (legacy) with Germany 2019
        smard_dir = dataset_dir / "profile_data" / "historical_demand_smard"
        smard_dir.mkdir(parents=True)
        _create_legacy_parquet(smard_dir, country="Germany", year=2019)

        result = Project._find_alternative_sources_static(
            dataset_dir=dataset_dir, country="Germany", year=2019, exclude="entsoe"
        )
        assert "smard" in result

    def test_excludes_current_source(self, tmp_path: Path) -> None:
        """Does not include the excluded source in alternatives."""
        dataset_dir = tmp_path / "dataset"
        entsoe_dir = dataset_dir / "profile_data" / "historical_demand_entsoe"
        entsoe_dir.mkdir(parents=True)
        _create_components_parquet(entsoe_dir, country="Germany", year=2019)

        result = Project._find_alternative_sources_static(
            dataset_dir=dataset_dir, country="Germany", year=2019, exclude="entsoe"
        )
        assert "entsoe" not in result
