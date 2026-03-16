"""Worker that runs BabelDOC translation in a background thread."""

import asyncio
import logging
import os
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.database import async_session_factory
from app.models.models import TranslationTask, TaskStatus, CustomModel, GlossarySet

logger = logging.getLogger(__name__)


async def run_translation_task(task_id: int):
    """Execute a translation task using BabelDOC core."""
    async with async_session_factory() as db:
        result = await db.execute(
            select(TranslationTask).where(TranslationTask.id == task_id)
        )
        task = result.scalar_one_or_none()
        if not task:
            logger.error(f"Task {task_id} not found")
            return

        if task.status == TaskStatus.cancelled:
            return

        task.status = TaskStatus.running
        task.started_at = datetime.now(timezone.utc)
        await db.commit()

        # Load related model config
        model_config = None
        if task.model_id:
            m_result = await db.execute(
                select(CustomModel).where(CustomModel.id == task.model_id)
            )
            model_config = m_result.scalar_one_or_none()

        # Load glossary entries
        glossary_entries = []
        if task.glossary_id:
            g_result = await db.execute(
                select(GlossarySet)
                .options(selectinload(GlossarySet.entries))
                .where(GlossarySet.id == task.glossary_id)
            )
            gs = g_result.scalar_one_or_none()
            if gs:
                glossary_entries = gs.entries

    # Run translation in thread pool
    try:
        result_files = await asyncio.get_event_loop().run_in_executor(
            None,
            _do_translation,
            task_id,
            task.stored_filename,
            task.lang_in,
            task.lang_out,
            task.pages,
            task.extra_body,
            task.no_dual,
            task.no_mono,
            task.use_alternating_pages_dual,
            task.enhance_compatibility,
            task.ocr_workaround,
            task.skip_translation,
            task.custom_system_prompt,
            model_config,
            glossary_entries,
        )

        async with async_session_factory() as db:
            result = await db.execute(
                select(TranslationTask).where(TranslationTask.id == task_id)
            )
            task = result.scalar_one_or_none()
            if task and task.status != TaskStatus.cancelled:
                task.status = TaskStatus.completed
                task.progress = 100.0
                task.completed_at = datetime.now(timezone.utc)
                if result_files.get("mono"):
                    task.output_mono_filename = result_files["mono"]
                if result_files.get("dual"):
                    task.output_dual_filename = result_files["dual"]
                task.token_usage = result_files.get("token_usage")
                await db.commit()

    except Exception as e:
        logger.exception(f"Translation task {task_id} failed")
        async with async_session_factory() as db:
            result = await db.execute(
                select(TranslationTask).where(TranslationTask.id == task_id)
            )
            task = result.scalar_one_or_none()
            if task:
                task.status = TaskStatus.failed
                task.error_message = str(e)[:2000]
                task.completed_at = datetime.now(timezone.utc)
                await db.commit()


def _do_translation(
    task_id,
    stored_filename,
    lang_in,
    lang_out,
    pages,
    extra_body,
    no_dual,
    no_mono,
    use_alternating_pages_dual,
    enhance_compatibility,
    ocr_workaround,
    skip_translation,
    custom_system_prompt,
    model_config,
    glossary_entries,
):
    """Synchronous translation using BabelDOC core, runs in thread pool."""
    import sys
    # Ensure BabelDOC package is importable
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    from babeldoc.translator.translator import OpenAITranslator
    from babeldoc.glossary import Glossary as BabelGlossary, GlossaryEntry as BabelGlossaryEntry

    # Build translator
    model_name = settings.DEFAULT_MODEL
    base_url = None
    api_key = os.environ.get("OPENAI_API_KEY", "")
    translator_extra_body = {}
    send_temperature = True
    reasoning = None
    disable_thinking = False
    enable_json_mode = False

    if model_config:
        model_name = model_config.model_name
        base_url = model_config.base_url
        api_key = model_config.api_key
        send_temperature = model_config.send_temperature
        reasoning = model_config.reasoning
        disable_thinking = model_config.disable_thinking
        enable_json_mode = model_config.enable_json_mode
        if model_config.extra_body:
            translator_extra_body.update(model_config.extra_body)

    # Merge task-level extra_body (overrides model-level)
    if extra_body:
        translator_extra_body.update(extra_body)

    translator = OpenAITranslator(
        lang_in=lang_in,
        lang_out=lang_out,
        model=model_name,
        base_url=base_url,
        api_key=api_key,
        send_temperature=send_temperature,
        reasoning=reasoning,
        disable_thinking=disable_thinking,
        enable_json_mode_if_requested=enable_json_mode,
    )

    # Apply extra_body to translator
    if translator_extra_body:
        translator.extra_body.update(translator_extra_body)

    # Build glossary
    glossaries = []
    if glossary_entries:
        entries = [
            BabelGlossaryEntry(source=e.source, target=e.target, target_language=e.target_language)
            for e in glossary_entries
        ]
        glossaries.append(BabelGlossary(name="user_glossary", entries=entries))

    # Input / output paths
    input_path = os.path.join(settings.UPLOAD_DIR, stored_filename)
    os.makedirs(settings.OUTPUT_DIR, exist_ok=True)
    output_id = uuid.uuid4().hex

    from babeldoc.format.pdf.high_level import translate
    from babeldoc.format.pdf.translation_config import TranslationConfig

    config = TranslationConfig(
        translator=translator,
        input_file=input_path,
        lang_in=lang_in,
        lang_out=lang_out,
        doc_layout_model=None,
        pages=pages,
        output_dir=settings.OUTPUT_DIR,
        no_dual=no_dual,
        no_mono=no_mono,
        use_alternating_pages_dual=use_alternating_pages_dual,
        enhance_compatibility=enhance_compatibility,
        ocr_workaround=ocr_workaround,
        skip_translation=skip_translation,
        custom_system_prompt=custom_system_prompt,
        glossaries=glossaries if glossaries else None,
        qps=settings.DEFAULT_QPS,
        use_rich_pbar=False,
    )

    result = translate(config)

    output_files = {}
    if result.mono_pdf_path and os.path.isfile(result.mono_pdf_path):
        mono_name = f"{output_id}_mono.pdf"
        dest = os.path.join(settings.OUTPUT_DIR, mono_name)
        shutil.move(str(result.mono_pdf_path), dest)
        output_files["mono"] = mono_name

    if result.dual_pdf_path and os.path.isfile(result.dual_pdf_path):
        dual_name = f"{output_id}_dual.pdf"
        dest = os.path.join(settings.OUTPUT_DIR, dual_name)
        shutil.move(str(result.dual_pdf_path), dest)
        output_files["dual"] = dual_name

    # Collect token usage
    output_files["token_usage"] = {
        "total_tokens": translator.token_count.value,
        "prompt_tokens": translator.prompt_token_count.value,
        "completion_tokens": translator.completion_token_count.value,
    }

    return output_files
