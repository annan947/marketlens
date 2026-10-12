"""Single-user saved research portfolios, with optimistic update/delete locking."""
from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import Field, field_validator, model_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from .schemas import Contract
from .portfolio import PortfolioRequest
from backend.db import SavedPortfolio, utcnow

router = APIRouter(prefix='/api/v1/saved-portfolios', tags=['Saved portfolios'])


class SavePortfolio(Contract):
    name: Annotated[str, Field(min_length=1, max_length=120)]
    notes: Annotated[str, Field(max_length=2000)] = ''
    definition: PortfolioRequest

    @field_validator('name')
    @classmethod
    def clean_name(cls, value):
        value = value.strip()
        if not value or any(ord(char) < 32 for char in value):
            raise ValueError('name must be nonempty and contain no control characters')
        return value

    @model_validator(mode='after')
    def validate_allocation(self):
        definition = self.definition
        if len(definition.weights) != len(definition.assets) or abs(sum(definition.weights)-1) > 1e-8:
            raise ValueError('weights must match the assets and sum to one')
        if len(definition.assets) * len(definition.returns) > 100000:
            raise ValueError('saved portfolios support at most 100000 return cells')
        return self


class UpdatePortfolio(SavePortfolio):
    version: Annotated[int, Field(strict=True, ge=1)]


class PortfolioSummary(Contract):
    id: UUID
    name: str
    notes: str
    version: int
    created_at: datetime
    updated_at: datetime


class PortfolioDetail(PortfolioSummary):
    definition: PortfolioRequest


class PortfolioList(Contract):
    items: list[PortfolioSummary]
    total: int
    offset: int
    limit: int


def session(request: Request):
    database = request.app.state.database
    if database is None:
        raise HTTPException(503, 'Portfolio storage is not configured. Set MARKETLENS_DATABASE_URL and run migrations.')
    with database.sessions() as db:
        yield db


def serialize(row, detail=True):
    def timestamp(value):
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
    data = dict(id=row.id, name=row.name, notes=row.notes, version=row.version,
                created_at=timestamp(row.created_at), updated_at=timestamp(row.updated_at))
    if detail:
        data['definition'] = row.definition
    return data


def get_row(db, portfolio_id):
    row = db.get(SavedPortfolio, str(portfolio_id))
    if row is None:
        raise HTTPException(404, 'Saved portfolio not found.')
    return row


def check_version(row, version):
    if row.version != version:
        raise HTTPException(409, 'This portfolio changed in another session. Reload it before updating or deleting.')


@router.get('', response_model=PortfolioList)
def list_portfolios(db: Annotated[Session, Depends(session)],
                    limit: Annotated[int, Query(ge=1, le=100)] = 50,
                    offset: Annotated[int, Query(ge=0)] = 0):
    # Only summary columns are selected; historical matrices never enter list responses.
    rows = db.execute(select(SavedPortfolio.id, SavedPortfolio.name, SavedPortfolio.notes,
        SavedPortfolio.version, SavedPortfolio.created_at, SavedPortfolio.updated_at)
        .order_by(SavedPortfolio.updated_at.desc(), SavedPortfolio.id).limit(limit).offset(offset)).all()
    total = db.scalar(select(func.count()).select_from(SavedPortfolio))
    return dict(items=[serialize(row, False) for row in rows], total=total, offset=offset, limit=limit)


@router.post('', response_model=PortfolioDetail, status_code=201)
def create_portfolio(body: SavePortfolio, db: Annotated[Session, Depends(session)], response: Response):
    row = SavedPortfolio(name=body.name, notes=body.notes, definition=body.definition.model_dump(mode='json'))
    db.add(row)
    db.commit()
    response.headers['Location'] = f'/api/v1/saved-portfolios/{row.id}'
    return serialize(row)


@router.get('/{portfolio_id}', response_model=PortfolioDetail)
def read_portfolio(portfolio_id: UUID, db: Annotated[Session, Depends(session)]):
    return serialize(get_row(db, portfolio_id))


@router.put('/{portfolio_id}', response_model=PortfolioDetail)
def update_portfolio(portfolio_id: UUID, body: UpdatePortfolio, db: Annotated[Session, Depends(session)]):
    row = get_row(db, portfolio_id)
    check_version(row, body.version)
    row.name, row.notes = body.name, body.notes
    row.definition = body.definition.model_dump(mode='json')
    row.updated_at = utcnow()  # Also increment version for an otherwise identical save.
    db.commit()
    return serialize(row)


@router.delete('/{portfolio_id}', status_code=204)
def delete_portfolio(portfolio_id: UUID, version: Annotated[int, Query(ge=1)],
                     db: Annotated[Session, Depends(session)]):
    row = get_row(db, portfolio_id)
    check_version(row, version)
    db.delete(row)
    db.commit()
    return Response(status_code=204)
