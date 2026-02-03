from pydantic import BaseModel, Field
from typing import List


class GeneratedExample(BaseModel):
    title: str
    example: str


class CompetencyExamples(BaseModel):
    competency: str
    examples: List[GeneratedExample] = Field(min_length=3, max_length=3)


class GenerateExamplesBatchResult(BaseModel):
    level: str
    results: List[CompetencyExamples]
