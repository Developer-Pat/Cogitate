"""
Provider domain schemas.

Pydantic schemas for provider request/response validation.
"""

from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field


class OllamaModel(BaseModel):
    """Schema for Ollama model information."""

    name: str = Field(..., description="Model name")
    size: int = Field(..., description="Model size in bytes")
    size_formatted: str = Field(..., description="Human-readable size")
    family: str = Field(..., description="Model family")
    format: str = Field(..., description="Model format")
    parameter_size: str = Field(..., description="Parameter size")
    quantization: str = Field(..., description="Quantization level")
    digest: str = Field(default="", description="Model digest")
    modified_at: str = Field(default="", description="Last modified timestamp")


class OllamaModelListResponse(BaseModel):
    """Schema for Ollama model list response."""

    models: List[OllamaModel] = Field(..., description="List of available models")
    total: int = Field(..., description="Total number of models")


class ModelDetail(BaseModel):
    """Schema for detailed model information."""

    name: str = Field(..., description="Model name")
    license: Optional[str] = Field(default=None, description="Model license")
    modelfile: Optional[str] = Field(default=None, description="Modelfile content")
    parameters: Optional[str] = Field(default=None, description="Model parameters")
    template: Optional[str] = Field(default=None, description="Model template")
    details: Dict[str, Any] = Field(default_factory=dict, description="Model details")
