from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, model_validator


class ProjectType(str, Enum):
    MOBILE_APP = "mobile_app"
    WEB_SAAS = "web_saas"
    INTERNAL_TOOL = "internal_tool"
    DATA_PIPELINE = "data_pipeline"


class DetailLevel(str, Enum):
    SUMMARY = "summary"
    MEDIUM = "medium"
    DETAILED = "detailed"


class OutputFormat(str, Enum):
    PHASES_TABLE = "phases_table"
    LINE_ITEMS = "line_items"
    NARRATIVE = "narrative"


class TaskBlock(BaseModel):
    name: str
    hours_min: int = Field(ge=1)
    hours_max: int = Field(ge=1)

    @model_validator(mode="after")
    def check_hours_range(self) -> "TaskBlock":
        if self.hours_min > self.hours_max:
            raise ValueError("hours_min debe ser ≤ hours_max")
        return self


class EstimationOutput(BaseModel):
    project_summary: str = Field(min_length=10)
    assumptions: list[str] = Field(min_length=1)
    tasks: list[TaskBlock] = Field(min_length=1)
    total_hours_min: int = Field(ge=1)
    total_hours_max: int = Field(ge=1)
    recommended_team: list[str] = Field(min_length=1)
    duration_weeks_min: int = Field(ge=1)
    duration_weeks_max: int = Field(ge=1)
    risks: list[str]
    open_questions: list[str]

    @model_validator(mode="after")
    def check_coherence(self) -> "EstimationOutput":
        if self.total_hours_min > self.total_hours_max:
            raise ValueError("total_hours_min debe ser ≤ total_hours_max")
        if self.duration_weeks_min > self.duration_weeks_max:
            raise ValueError("duration_weeks_min debe ser ≤ duration_weeks_max")

        task_sum_min = sum(t.hours_min for t in self.tasks)
        task_sum_max = sum(t.hours_max for t in self.tasks)
        tolerance = 0.25

        if task_sum_min > 0 and abs(self.total_hours_min - task_sum_min) > task_sum_min * tolerance:
            raise ValueError(
                f"total_hours_min ({self.total_hours_min}) no es coherente "
                f"con la suma de tareas ({task_sum_min}) — tolerancia ±25%"
            )
        if task_sum_max > 0 and abs(self.total_hours_max - task_sum_max) > task_sum_max * tolerance:
            raise ValueError(
                f"total_hours_max ({self.total_hours_max}) no es coherente "
                f"con la suma de tareas ({task_sum_max}) — tolerancia ±25%"
            )
        return self


class ProjectMetadata(BaseModel):
    project_name: Optional[str] = None
    assumed_team_size: Optional[int] = None
    mentioned_technologies: list[str] = Field(default_factory=list)
    agreed_scope: Optional[str] = None


class EstimationRequest(BaseModel):
    description: str = Field(min_length=20, max_length=2000)
    project_type: ProjectType
    detail_level: DetailLevel
    output_format: OutputFormat


class TierInfo(BaseModel):
    tier: int
    score: float
    model_selected: str
    keywords_detected: list[str]
    reason: str


class EstimationResponse(BaseModel):
    output: EstimationOutput
    prompt_version: str
    model: str
    provider: str
    project_metadata: Optional[ProjectMetadata] = None
    tier_info: Optional[TierInfo] = None
