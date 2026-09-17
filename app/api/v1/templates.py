from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_db, verify_api_key
from app.core.exceptions import ResourceNotFoundException, TemplateRenderError
from app.models.template import Template
from app.schemas.template import (
    TemplateCreate,
    TemplateRenderRequest,
    TemplateRenderResponse,
    TemplateResponse,
    TemplateUpdate,
)
from app.services.template_service import template_service

router = APIRouter(prefix="/templates", tags=["Templates"])


@router.post("", response_model=TemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_template(
    payload: TemplateCreate,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    # Check duplicate name
    stmt = select(Template).where(Template.name == payload.name)
    existing = (await db.execute(stmt)).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Template with name '{payload.name}' already exists.",
        )

    template = Template(
        name=payload.name,
        description=payload.description,
        channel=payload.channel.value,
        subject_template=payload.subject_template,
        body_template=payload.body_template,
        variables=payload.variables or [],
    )
    db.add(template)
    await db.commit()
    await db.refresh(template)
    return template


@router.get("", response_model=List[TemplateResponse])
async def list_templates(
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    stmt = select(Template).order_by(Template.created_at.desc())
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.get("/{template_id}", response_model=TemplateResponse)
async def get_template(
    template_id: str,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    stmt = select(Template).where((Template.id == template_id) | (Template.name == template_id))
    template = (await db.execute(stmt)).scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Template '{template_id}' not found.")
    return template


@router.put("/{template_id}", response_model=TemplateResponse)
async def update_template(
    template_id: str,
    payload: TemplateUpdate,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    stmt = select(Template).where((Template.id == template_id) | (Template.name == template_id))
    template = (await db.execute(stmt)).scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Template '{template_id}' not found.")

    if payload.description is not None:
        template.description = payload.description
    if payload.subject_template is not None:
        template.subject_template = payload.subject_template
    if payload.body_template is not None:
        template.body_template = payload.body_template
    if payload.variables is not None:
        template.variables = payload.variables

    await db.commit()
    await db.refresh(template)
    return template


@router.post("/render", response_model=TemplateRenderResponse)
async def render_template(
    payload: TemplateRenderRequest,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    stmt = select(Template).where((Template.id == payload.template_id) | (Template.name == payload.template_id))
    template = (await db.execute(stmt)).scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Template '{payload.template_id}' not found.")

    try:
        subject, body = template_service.render_content(
            body_template=template.body_template,
            subject_template=template.subject_template,
            data=payload.data,
        )
        return TemplateRenderResponse(subject=subject, rendered_body=body)
    except TemplateRenderError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)
