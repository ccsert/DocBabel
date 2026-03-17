from datetime import datetime
from pydantic import BaseModel, EmailStr, Field


# ─── Auth ─────────────────────────────────────────────────

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)


# ─── User ─────────────────────────────────────────────────

class UserOut(BaseModel):
    id: int
    username: str
    email: str
    role: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class UserUpdate(BaseModel):
    email: str | None = None
    is_active: bool | None = None
    role: str | None = None


# ─── Translation Task ────────────────────────────────────

class TaskCreate(BaseModel):
    lang_in: str = "en"
    lang_out: str = "zh"
    model_id: int
    glossary_id: int | None = None
    pages: str | None = None
    extra_body: dict | None = None
    no_dual: bool = False
    no_mono: bool = False
    use_alternating_pages_dual: bool = False
    enhance_compatibility: bool = False
    ocr_workaround: bool = False
    skip_translation: bool = False
    custom_system_prompt: str | None = None
    auto_extract_glossary: bool = False
    reuse_existing: bool = False
    force_regenerate: bool = False


class TaskOut(BaseModel):
    id: int
    user_id: int
    status: str
    original_filename: str
    lang_in: str
    lang_out: str
    model_id: int | None
    glossary_id: int | None
    pages: str | None
    extra_body: dict | None
    no_dual: bool
    no_mono: bool
    use_alternating_pages_dual: bool
    enhance_compatibility: bool
    ocr_workaround: bool
    skip_translation: bool
    custom_system_prompt: str | None
    progress: float
    progress_message: str | None
    error_message: str | None
    token_usage: dict | None
    duration_seconds: float | None
    queue_position: int | None
    output_mono_filename: str | None
    output_dual_filename: str | None
    auto_extract_glossary: bool
    extracted_glossary_data: list | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None

    model_config = {"from_attributes": True}


class TaskListOut(BaseModel):
    tasks: list[TaskOut]
    total: int


class FileLibraryItemOut(BaseModel):
    file_hash: str
    original_filename: str
    latest_task_id: int
    latest_created_at: datetime
    latest_completed_at: datetime | None
    latest_duration_seconds: float | None
    task_count: int
    output_mono_filename: str | None
    output_dual_filename: str | None


class FileLibraryListOut(BaseModel):
    files: list[FileLibraryItemOut]
    total: int


# ─── Glossary ────────────────────────────────────────────

class GlossaryEntryIn(BaseModel):
    source: str
    target: str
    target_language: str | None = None


class GlossaryEntryUpdate(BaseModel):
    source: str | None = None
    target: str | None = None
    target_language: str | None = None


class GlossaryEntryOut(BaseModel):
    id: int
    source: str
    target: str
    target_language: str | None

    model_config = {"from_attributes": True}


class GlossaryContributionIn(BaseModel):
    source: str
    target: str
    target_language: str | None = None


class GlossaryContributionReviewIn(BaseModel):
    review_note: str | None = None


class GlossaryContributionOut(BaseModel):
    id: int
    glossary_set_id: int
    proposer_user_id: int
    source: str
    target: str
    target_language: str | None
    status: str
    review_note: str | None
    created_at: datetime
    reviewed_at: datetime | None

    model_config = {"from_attributes": True}


class GlossarySetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    description: str | None = None
    is_collaborative: bool = False
    entries: list[GlossaryEntryIn] = []


class GlossarySetUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    is_collaborative: bool | None = None


class GlossarySetOut(BaseModel):
    id: int
    user_id: int
    name: str
    description: str | None
    is_collaborative: bool
    is_owner: bool = False
    created_at: datetime
    updated_at: datetime
    entries: list[GlossaryEntryOut] = []
    pending_contributions: list[GlossaryContributionOut] = []

    model_config = {"from_attributes": True}


# ─── Custom Model ────────────────────────────────────────

class CustomModelCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    model_name: str
    base_url: str | None = None
    api_key: str
    extra_body: dict | None = None
    send_temperature: bool = True
    temperature: float | None = 0.0
    reasoning: str | None = None
    disable_thinking: bool = False
    enable_json_mode: bool = False


class CustomModelUpdate(BaseModel):
    name: str | None = None
    model_name: str | None = None
    base_url: str | None = None
    api_key: str | None = None
    extra_body: dict | None = None
    send_temperature: bool | None = None
    temperature: float | None = None
    reasoning: str | None = None
    disable_thinking: bool | None = None
    enable_json_mode: bool | None = None


class CustomModelOut(BaseModel):
    id: int
    user_id: int
    name: str
    model_name: str
    base_url: str | None
    extra_body: dict | None
    send_temperature: bool
    temperature: float | None
    reasoning: str | None
    disable_thinking: bool
    enable_json_mode: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
