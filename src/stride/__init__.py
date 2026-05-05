from importlib.metadata import PackageNotFoundError, version

from stride.project import Project
from stride.models import (
    ProjectConfig,
    Scenario,
)

try:
    __version__ = version("stride-load-forecast")
except PackageNotFoundError:
    __version__ = "0+unknown"

__all__ = (
    "Project",
    "ProjectConfig",
    "Scenario",
)
