from enum import StrEnum
from pathlib import Path
from typing import Self

from chronify.exceptions import InvalidParameter
from dsgrid.data_models import DSGBaseModel
from pydantic import Field, field_validator


class DatasetType(StrEnum):
    ENERGY_BY_SECTOR = "energy_by_sector"
    ENERGY_INTENSITY_BY_SECTOR = "energy_intensity_by_sector"
    ENERGY_INTENSITY_REGRESSION_BY_SECTOR = "energy_intensity_regression_by_sector"
    GDP = "gdp"
    HDI = "hdi"
    POPULATION = "population"


class ProjectionSliceType(StrEnum):
    ENERGY_BY_SECTOR = "energy_by_sector"
    EVS = "evs"
    HEAT_PUMPS = "heat_pumps"


class CustomDemandComponent(DSGBaseModel):  # type: ignore
    """Defines an additive custom demand component.

    A custom demand component is a user-defined electricity load (e.g., heat pumps,
    data centers) that is injected into the energy projection after dbt computation.
    Annual MWh values are distributed into 8760 hourly rows using the specified
    load profile.
    """

    name: str = Field(
        description="Unique identifier for this component (e.g., 'heat_pumps')"
    )
    sector: str = Field(
        description="Sector label for UI grouping (e.g., 'Heat Pumps')"
    )
    data_file: Path = Field(
        description="Path to CSV/Parquet with model_year and value (annual MWh) columns"
    )
    load_profile: str = Field(
        default="flat",
        description=(
            "How to distribute annual energy into hours. Options: "
            "'flat', 'sector:<name>', 'enduse:<name>', or a file path to an 8760 CSV"
        ),
    )
    metric: str = Field(
        default="other",
        description="End-use/metric label (e.g., 'heating', 'cooling', 'other')",
    )

    @field_validator("name")
    @classmethod
    def check_name(cls, name: str) -> str:
        if not name.isidentifier():
            msg = f"Component name must be a valid Python identifier: {name!r}"
            raise ValueError(msg)
        return name


class Scenario(DSGBaseModel):  # type: ignore
    """Allows the user to add custom tables to compare against the defaults."""

    name: str = Field(description="Name of the scenario")
    energy_intensity: Path | None = Field(
        default=None,
        description="Optional path to a user-provided energy intensity table",
    )
    gdp: Path | None = Field(
        default=None,
        description="Optional path to a user-provided GDP table",
    )
    hdi: Path | None = Field(
        default=None,
        description="Optional path to a user-provided HDI table",
    )
    load_shapes: Path | None = Field(
        default=None,
        description="Optional path to a user-provided load shapes table",
    )
    population: Path | None = Field(
        default=None,
        description="Optional path to a user-provided population table",
    )
    weather_bait: Path | None = Field(
        default=None,
        description="Optional path to a user-provided weather_bait table",
    )
    use_ev_projection: bool = Field(
        default=False,
        description="Use EV-based projection for (Transportation, Road) instead of energy intensity regression",
    )
    electricity_per_vehicle_km_projections: Path | None = Field(
        default=None,
        description="Optional path to a user-provided population table",
    )
    ev_stock_share_projections: Path | None = Field(
        default=None,
        description="Optional path to a user-provided ev_stock_share_projections table",
    )
    km_per_vehicle_year_regressions: Path | None = Field(
        default=None,
        description="Optional path to a user-provided km_per_vehicle_year_regressions table",
    )
    phev_share_projections: Path | None = Field(
        default=None,
        description="Optional path to a user-provided phev_share_projections table",
    )
    vehicle_per_capita_regressions: Path | None = Field(
        default=None,
        description="Optional path to a user-provided vehicle_per_capita_regressions table",
    )
    skip_custom_demand: bool = Field(
        default=False,
        description="When True, skip custom demand component injection for this scenario.",
    )
    custom_demand_overrides: dict[str, Path] = Field(
        default={},
        description=(
            "Per-scenario overrides for custom demand components. "
            "Keys are component names, values are paths to alternative data files."
        ),
    )

    @field_validator("name")
    @classmethod
    def check_name(cls, name: str) -> str:
        if name in (
            "dsgrid_data",
            "dsgrid_lookup",
            "dsgrid_missing_associations",
            "stride",
            "default",  # Not allowed by DuckDB
        ):
            msg = (
                f"A scenario name cannot be {name} because it conflicts with existing "
                "database schema names."
            )
            raise ValueError(msg)
        return name


class CalculatedTableOverride(DSGBaseModel):  # type: ignore
    """Defines an override for a calculated table in a scenario."""

    scenario: str = Field(description="Scenario name")
    table_name: str = Field(description="Base name of calculated table being overridden")
    filename: Path | None = Field(
        default=None, description="Path to file containing the override data."
    )


# Default model parameter values
# These constants ensure consistency across Python code and should match dbt model defaults
DEFAULT_HEATING_THRESHOLD = 18.0
DEFAULT_COOLING_THRESHOLD = 18.0
DEFAULT_ENABLE_SHOULDER_MONTH_SMOOTHING = True
DEFAULT_SHOULDER_MONTH_SMOOTHING_FACTOR = 10.0


class ModelParameters(DSGBaseModel):  # type: ignore
    """Advanced model parameters for energy projections."""

    heating_threshold: float = Field(
        default=DEFAULT_HEATING_THRESHOLD,
        description="Temperature threshold (°C) below which heating degree days are calculated. "
        "Used for temperature adjustment of heating end uses in load shapes.",
    )
    cooling_threshold: float = Field(
        default=DEFAULT_COOLING_THRESHOLD,
        description="Temperature threshold (°C) above which cooling degree days are calculated. "
        "Used for temperature adjustment of cooling end uses in load shapes.",
    )
    enable_shoulder_month_smoothing: bool = Field(
        default=DEFAULT_ENABLE_SHOULDER_MONTH_SMOOTHING,
        description="Enable smoothing of temperature multipliers in shoulder months. "
        "When True, days with zero degree days in months with mixed heating/cooling are assigned "
        "small values to prevent unrealistic load spikes. When False, uses traditional calculation.",
    )
    shoulder_month_smoothing_factor: float = Field(
        default=DEFAULT_SHOULDER_MONTH_SMOOTHING_FACTOR,
        description="Divisor applied to maximum degree days to set minimum threshold for smoothing. "
        "In months with mixed heating/cooling activity, degree days below (max / factor) are "
        "raised to this minimum threshold to prevent unrealistic load concentration. "
        "Smaller values create smoother transitions. Typical values: 5.0 (aggressive), 10.0 (moderate), 20.0 (gentle). "
        "Only used when enable_shoulder_month_smoothing is True.",
    )


class ProjectConfig(DSGBaseModel):  # type: ignore
    """Defines a Stride project."""

    project_id: str = Field(description="Unique identifier for the project")
    creator: str = Field(description="Creator of the project")
    description: str = Field(description="Description of the project")
    country: str = Field(description="Country upon which the data is based")
    start_year: int = Field(description="Start year for the forecasted data")
    end_year: int = Field(description="End year for the forecasted data")
    step_year: int = Field(default=1, description="End year for the forecasted data")
    weather_year: int = Field(description="Weather year upon which the data is based")
    model_parameters: ModelParameters = Field(
        default_factory=ModelParameters,
        description="Advanced model parameters for temperature adjustments and other calculations",
    )
    scenarios: list[Scenario] = Field(
        default=[Scenario(name="baseline")],
        description="Scenarios for the project. Users may add custom scenarios.",
        min_length=1,
    )
    calculated_table_overrides: list[CalculatedTableOverride] = Field(
        default=[],
        description="Calculated tables to override",
    )
    custom_demand_components: list[CustomDemandComponent] = Field(
        default=[],
        description="Additive custom demand components (e.g., heat pumps, data centers)",
    )
    color_palette: dict[str, dict[str, str]] = Field(
        default={"scenarios": {}, "model_years": {}, "sectors": {}, "end_uses": {}},
        description="Color palette organized into scenarios, model_years, sectors, and end_uses categories. Each category maps labels to hex/rgb color strings for the UI.",
    )

    @staticmethod
    def _resolve_scenario_paths(scenario: "Scenario", base_path: Path) -> None:
        for field in Scenario.model_fields:
            if field in ("name", "use_ev_projection", "skip_custom_demand", "custom_demand_overrides"):
                continue
            val = getattr(scenario, field)
            if val is not None and not val.is_absolute():
                setattr(scenario, field, (base_path / val).resolve())
            val = getattr(scenario, field)
            if val is not None and not val.exists():
                msg = (
                    f"Scenario={scenario.name} dataset={field} filename={val} "
                    f"does not exist"
                )
                raise InvalidParameter(msg)
        for key, val in scenario.custom_demand_overrides.items():
            if not val.is_absolute():
                val = (base_path / val).resolve()
                scenario.custom_demand_overrides[key] = val
            if not val.exists():
                msg = (
                    f"Scenario={scenario.name} custom_demand_override={key} "
                    f"filename={val} does not exist"
                )
                raise InvalidParameter(msg)

    @classmethod
    def from_file(cls, filename: Path | str) -> Self:
        path = Path(filename)
        config = super().from_file(path)
        for scenario in config.scenarios:
            cls._resolve_scenario_paths(scenario, path.parent)
            for table in config.calculated_table_overrides:
                if table.filename is not None and not table.filename.is_absolute():
                    table.filename = path.parent / table.filename
                if table.filename is not None and not table.filename.exists():
                    msg = (
                        f"Scenario={scenario.name} calculated_table={table.table_name} "
                        f"filename={table.filename} does not exist"
                    )
                    raise InvalidParameter(msg)
        for component in config.custom_demand_components:
            if not component.data_file.is_absolute():
                component.data_file = (path.parent / component.data_file).resolve()
            if not component.data_file.exists():
                msg = (
                    f"Custom demand component={component.name} "
                    f"data_file={component.data_file} does not exist"
                )
                raise InvalidParameter(msg)
        return config  # type: ignore

    def list_model_years(self) -> list[int]:
        """List the model years in the project."""
        return list(range(self.start_year, self.end_year + 1, self.step_year))


"""
    dataset_id: "",
    filepath: "",
    projection_slice: "energy_by_sector|evs|heat_pumps",
    # valid dataset_types depend on chosen projection_slice
    dataset_type: "energy_by_sector|energy_intensity_by_sector|energy_intensity_regression_by_sector|population|gdp|...",
    # data that might go here, or in project_user_config, or in a separate "submit-to-project" step:
    # dataset requirements (e.g., to which sector(s) are these data applicable?)
    # mappings
    # ways to fill in missing data
    # in which scenario(s) to use these data

default datasets:
- GDP
- HDI
- energy intensity regressions
- population projections

When we generate the project config, the base dimensions will be the union of dimensions
in these datasets.

Regarding base dimensions:
- When we create the project, allow the user to specify dimensions from a library (2020 census counties).
- When we create a dataset, allow the user to specify which dimensions will become project base dimensions?
"""
