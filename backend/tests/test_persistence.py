"""Real SQL sessions and migrations; SQLite locally, optional PostgreSQL smoke test."""
import os
from pathlib import Path
from uuid import uuid4
import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import inspect
from sqlalchemy.orm.exc import StaleDataError
from backend.config import Settings
from backend.db import Database, SavedPortfolio
from backend.main import create_app

ROOT = Path(__file__).resolve().parents[2]


def migrate(url, monkeypatch):
    monkeypatch.setenv('MARKETLENS_DATABASE_URL', url)
    config = Config(str(ROOT / 'alembic.ini'))
    command.upgrade(config, 'head')
    return config


@pytest.fixture
def database_url(tmp_path, monkeypatch):
    url = 'sqlite:///' + str(tmp_path / 'storage.db').replace('\\', '/')
    migrate(url, monkeypatch)
    return url


@pytest.fixture
def client(database_url):
    with TestClient(create_app(Settings(database_url=database_url))) as client:
        yield client


def payload():
    return dict(name='Balanced research', notes='Synthetic inputs', definition={
        'assets': ['AAA', 'BBB'], 'dates': ['2025-01-02', '2025-01-03'],
        'returns': [[.01, -.02], [-.01, .02]], 'weights': [.6, .4],
        'periods_per_year': 252, 'risk_free_rate': .02})


def test_crud_versions_and_stale_delete(client):
    response = client.post('/api/v1/saved-portfolios', json=payload())
    assert response.status_code == 201
    first = response.json()
    assert first['version'] == 1
    assert first['created_at'].endswith('Z')
    location = response.headers['location']
    assert client.get(location).json()['definition'] == payload()['definition']
    updated = client.put(location, json={**payload(), 'name': 'Updated', 'version': 1})
    assert updated.status_code == 200
    assert updated.json()['version'] == 2
    assert client.put(location, json={**payload(), 'version': 1}).status_code == 409
    assert client.delete(location+'?version=1').status_code == 409
    assert client.get(location).json()['name'] == 'Updated'
    assert client.delete(location+'?version=2').status_code == 204
    assert client.get(location).status_code == 404


def test_persists_across_app_restart(client, database_url):
    row = client.post('/api/v1/saved-portfolios', json=payload()).json()
    with TestClient(create_app(Settings(database_url=database_url))) as restarted:
        result = restarted.get('/api/v1/saved-portfolios/'+row['id'])
        assert result.json()['definition'] == payload()['definition']


def test_paginated_summary_does_not_return_history(client):
    for index in range(3):
        assert client.post('/api/v1/saved-portfolios', json={**payload(), 'name': f'Portfolio {index}'}).status_code == 201
    response = client.get('/api/v1/saved-portfolios?limit=2&offset=1')
    body = response.json()
    assert body['total'] == 3 and len(body['items']) == 2
    assert 'definition' not in body['items'][0]
    assert client.get('/api/v1/saved-portfolios?limit=101').status_code == 422
    assert client.get('/api/v1/saved-portfolios?offset=-1').status_code == 422


@pytest.mark.parametrize('change', [{'name': '  '}, {'name': 'x'*121}, {'notes': 'x'*2001},
    {'definition': {**payload()['definition'], 'weights': [.5]}},
    {'definition': {**payload()['definition'], 'weights': [.6, .6]}},
    {'definition': {**payload()['definition'], 'dates': ['2025-01-02']*2}}])
def test_saved_input_validation(client, change):
    assert client.post('/api/v1/saved-portfolios', json={**payload(), **change}).status_code == 422
    assert client.get('/api/v1/saved-portfolios').json()['total'] == 0


def test_id_and_version_validation(client):
    assert client.get('/api/v1/saved-portfolios/not-a-uuid').status_code == 422
    assert client.get('/api/v1/saved-portfolios/'+str(uuid4())).status_code == 404
    row = client.post('/api/v1/saved-portfolios', json=payload()).json()
    location = '/api/v1/saved-portfolios/'+row['id']
    assert client.put(location, json=payload()).status_code == 422
    assert client.delete(location).status_code == 422


def test_actual_orm_race_is_detected(client, database_url):
    row = client.post('/api/v1/saved-portfolios', json=payload()).json()
    database = Database(database_url)
    try:
        with database.sessions() as first, database.sessions() as second:
            a = first.get(SavedPortfolio, row['id'])
            b = second.get(SavedPortfolio, row['id'])
            a.name = 'First writer'
            first.commit()
            b.name = 'Second writer'
            with pytest.raises(StaleDataError):
                second.commit()
            second.rollback()
        assert client.get('/api/v1/saved-portfolios/'+row['id']).json()['name'] == 'First writer'
    finally:
        database.dispose()


def test_readiness_and_absent_configuration(client):
    assert client.get('/ready').json() == {'status': 'ready', 'database': 'ok'}
    with TestClient(create_app(Settings())) as disabled:
        assert disabled.get('/health').status_code == 200
        assert disabled.get('/ready').status_code == 503
        assert disabled.get('/api/v1/saved-portfolios').status_code == 503
        assert disabled.post('/api/v1/options/black-scholes', json=dict(spot=100, strike=100, years=1, rate=.05, volatility=.2)).status_code == 200


def test_unmigrated_database_fails_safely(tmp_path):
    url = 'sqlite:///' + str(tmp_path / 'unmigrated.db').replace('\\', '/')
    with TestClient(create_app(Settings(database_url=url))) as client:
        assert client.get('/ready').status_code == 503
        response = client.get('/api/v1/saved-portfolios')
        assert response.status_code == 503
        assert 'SELECT' not in response.text and str(tmp_path) not in response.text


def test_migration_idempotency_schema_and_round_trip(database_url, monkeypatch):
    config = migrate(database_url, monkeypatch)
    command.check(config)
    database = Database(database_url)
    try:
        assert 'saved_portfolios' in inspect(database.engine).get_table_names()
    finally:
        database.dispose()
    # Downgrade is only exercised on this fixture's disposable test database.
    command.downgrade(config, 'base')
    command.upgrade(config, 'head')


def test_database_setting_masks_password():
    settings = Settings(database_url='postgresql+psycopg://name:secret@localhost/db')
    assert 'secret' not in repr(settings)


@pytest.mark.skipif(not os.getenv('MARKETLENS_TEST_POSTGRES_URL'), reason='PostgreSQL test server not configured')
def test_postgres_migrations_and_persistence(monkeypatch):
    url = os.environ['MARKETLENS_TEST_POSTGRES_URL']
    assert url.startswith('postgresql+psycopg://')
    migrate(url, monkeypatch)
    with TestClient(create_app(Settings(database_url=url))) as client:
        assert client.get('/ready').status_code == 200
        created = client.post('/api/v1/saved-portfolios', json=payload())
        assert created.status_code == 201
        row = created.json()
        location = '/api/v1/saved-portfolios/'+row['id']
        try:
            assert client.get(location).json()['definition'] == payload()['definition']
            update = client.put(location, json={**payload(), 'version': 1, 'name': 'Postgres update'})
            assert update.status_code == 200
            assert update.json()['version'] == 2
        finally:
            latest = client.get(location).json()
            assert client.delete(location+f"?version={latest['version']}").status_code == 204
