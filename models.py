"""Pydantic models for request/response validation."""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, validator, model_validator
from datetime import datetime


class Audience(BaseModel):
    market: str
    level: str = Field(..., pattern="^(beginner|intermediate|expert)$")
    painPoints: List[str] = []
    objections: List[str] = []


class ToneOfVoice(BaseModel):
    style: List[str] = []
    formality: str = Field(..., pattern="^(je|u)$")
    do: List[str] = []
    dont: List[str] = []


class InternalLinkTarget(BaseModel):
    title: str
    url: str


class SEO(BaseModel):
    focusKeyword: str
    secondaryKeywords: List[str] = []
    internalLinkTargets: List[InternalLinkTarget] = []
    metaTitlePattern: str = "{topic} | {brand}"
    metaDescMaxLen: int = Field(default=155, ge=50, le=300)


class Brand(BaseModel):
    name: str
    cta: str = ""


class MultilangConfig(BaseModel):
    enabled: bool = False
    languages: List[str] = []
    strategy: str = Field(default="translate",
                          pattern="^(translate|localize)$")


class ConnectSiteRequest(BaseModel):
    wpBaseUrl: str
    wpUsername: str
    wpApplicationPassword: str

    @validator("wpBaseUrl")
    def validate_url(cls, v):
        if not (v.startswith("https://") or v.startswith("http://")):
            raise ValueError("wpBaseUrl must start with http:// or https://")
        return v.rstrip("/")


class GeneratePostRequest(BaseModel):
    siteId: str
    topic: str
    audience: Audience
    toneOfVoice: ToneOfVoice
    seo: SEO
    brand: Brand
    language: str = "nl"
    status: str = Field(default="draft", pattern="^(draft|publish|future)$")
    scheduleDateGmt: Optional[str] = None
    multilang: MultilangConfig = MultilangConfig(enabled=False)
    generateImage: bool = True  # Enable featured image generation by default
    imageSettings: Optional[Dict[str, Any]] = None  # Image generation settings


class PublishPostRequest(BaseModel):
    siteId: str
    draft: Optional[Dict[str, Any]] = None
    drafts: Optional[Dict[str, Dict[str, Any]]] = None

    @model_validator(mode='after')
    def validate_draft_or_drafts(self):
        if not self.draft and not self.drafts:
            raise ValueError("Either 'draft' or 'drafts' must be provided")
        return self


class DraftContent(BaseModel):
    title: str
    slug: str
    excerpt: str
    contentHtml: str
    yoast: Dict[str, str] = Field(..., alias="yoast")
    tags: List[str] = []
    categories: List[str] = []
