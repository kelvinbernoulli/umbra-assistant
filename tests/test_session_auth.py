import time
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.api.v1.routes import session_auth as auth
from app.api.deps import get_current_user_id, get_current_workspace_id
from app.core.config import settings
from app.db.auth_models import GoogleUser, BrowserSession, LoginChallenge
from app.db.models import Base, ApiKey, Workspace, WorkspaceMember
from app.db.session import get_db
from app.services.browser_session import digest

HEADERS = {'Origin': 'http://localhost:5173', 'X-Requested-With': 'XmlHttpRequest'}

@pytest.fixture
def setup(monkeypatch):
    monkeypatch.setattr(settings, 'SESSION_COOKIE_SECURE', False)
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    def database():
        with factory() as db:
            yield db
    app = FastAPI()
    app.include_router(auth.router, prefix='/api/v1')
    from app.api.v1.routes import auth as calendar_auth
    app.include_router(calendar_auth.router, prefix='/api/v1')
    app.dependency_overrides[get_db] = database
    @app.get('/records')
    @app.post('/records')
    def records(user=Depends(get_current_user_id), workspace=Depends(get_current_workspace_id)):
        return {'user': user, 'workspace': workspace}
    monkeypatch.setattr(settings, 'GOOGLE_CLIENT_ID', 'test-client')
    claims = {'sub': 'google-one', 'email': 'one@example.com', 'name': 'One', 'email_verified': True}
    def verify(token, transport, audience):
        assert audience == 'test-client'
        if token == 'invalid':
            raise ValueError('private token detail')
        return dict(claims)
    monkeypatch.setattr(auth.id_token, 'verify_oauth2_token', verify)
    with TestClient(app, base_url='http://localhost:5173') as client:
        yield client, factory, claims
    engine.dispose()

def login(client, claims):
    challenge = client.post('/api/v1/auth/challenge', headers=HEADERS)
    assert challenge.status_code == 200
    claims['nonce'] = challenge.json()['nonce']
    return client.post('/api/v1/auth/google', json={'credential': 'valid'}, headers=HEADERS)

def count(db, model):
    return db.scalar(select(func.count()).select_from(model))

def test_signup_hashes_secrets_and_restores_workspace(setup):
    client, factory, claims = setup
    response = login(client, claims)
    assert response.status_code == 200
    data = response.json()
    assert set(data) == {'user', 'workspace'}
    assert response.headers['cache-control'] == 'no-store'
    assert 'HttpOnly' in response.headers['set-cookie'] and 'SameSite=lax' in response.headers['set-cookie']
    assert client.get('/api/v1/auth/session').json() == data
    assert client.get('/records', headers={'X-Workspace-ID': 'spoofed'}).json() == {
        'user': data['user']['id'], 'workspace': data['workspace']['id']}
    with factory() as db:
        assert count(db, GoogleUser) == count(db, Workspace) == count(db, ApiKey) == count(db, WorkspaceMember) == 1
        key = db.scalar(select(ApiKey))
        session = db.scalar(select(BrowserSession))
        assert len(key.key_hash) == 64
        assert session.token_hash == digest(client.cookies['umbra_session'])
        assert session.token_hash != client.cookies['umbra_session']

def test_returning_user_is_not_duplicated_and_session_rotates(setup):
    client, factory, claims = setup
    first = login(client, claims).json()
    old = client.cookies['umbra_session']
    assert login(client, claims).json() == first
    assert client.cookies['umbra_session'] != old
    with factory() as db:
        assert count(db, GoogleUser) == count(db, Workspace) == count(db, ApiKey) == 1
        assert db.get(BrowserSession, digest(old)) is None

def test_different_google_subjects_never_merge_by_email(setup):
    client, factory, claims = setup
    first = login(client, claims).json()
    claims['sub'] = 'google-two'
    second = login(client, claims).json()
    assert first['user']['id'] != second['user']['id']
    assert first['workspace']['id'] != second['workspace']['id']

def test_logout_revokes_cookie_and_server_session(setup):
    client, factory, claims = setup
    login(client, claims)
    old = client.cookies['umbra_session']
    assert client.post('/api/v1/auth/logout', headers=HEADERS).status_code == 204
    assert client.get('/records').status_code == 401
    client.cookies.set('umbra_session', old)
    assert client.get('/api/v1/auth/session').status_code == 401

@pytest.mark.parametrize('headers', [{}, {'Origin': 'https://evil.example', 'X-Requested-With': 'XmlHttpRequest'}])
def test_login_and_session_mutations_require_origin(setup, headers):
    client, factory, claims = setup
    assert client.post('/api/v1/auth/challenge', headers=headers).status_code == 403
    login(client, claims)
    assert client.post('/records', headers=headers).status_code == 403
    assert client.post('/api/v1/auth/logout', headers=headers).status_code == 403
    assert client.post('/records', headers=HEADERS).status_code == 200

@pytest.mark.parametrize('failure', ['invalid', 'nonce', 'expired', 'unverified', 'missing-cookie'])
def test_rejects_invalid_identity_or_challenge_without_provisioning(setup, failure):
    client, factory, claims = setup
    claims['nonce'] = client.post('/api/v1/auth/challenge', headers=HEADERS).json()['nonce']
    if failure == 'nonce': claims['nonce'] = 'wrong'
    if failure == 'unverified': claims['email_verified'] = False
    if failure == 'missing-cookie': client.cookies.clear()
    if failure == 'expired':
        with factory() as db:
            db.scalar(select(LoginChallenge)).expires_at = 0
            db.commit()
    response = client.post('/api/v1/auth/google', json={'credential': 'invalid' if failure == 'invalid' else 'valid'}, headers=HEADERS)
    assert response.status_code == 401
    assert 'private token detail' not in response.text
    with factory() as db: assert count(db, GoogleUser) == count(db, Workspace) == count(db, ApiKey) == 0

def test_challenge_cannot_be_replayed(setup):
    client, factory, claims = setup
    login(client, claims)
    client.cookies.set('umbra_login_challenge', claims['nonce'])
    assert client.post('/api/v1/auth/google', json={'credential': 'valid'}, headers=HEADERS).status_code == 401

@pytest.mark.parametrize('failure', ['expired', 'disabled', 'membership'])
def test_session_expiry_and_revoked_access(setup, failure):
    client, factory, claims = setup
    login(client, claims)
    with factory() as db:
        if failure == 'expired': db.scalar(select(BrowserSession)).expires_at = int(time.time()) - 1
        if failure == 'disabled': db.scalar(select(ApiKey)).active = False
        if failure == 'membership': db.delete(db.scalar(select(WorkspaceMember)))
        db.commit()
    assert client.get('/records').status_code == 401

def test_existing_api_keys_still_work(setup):
    client, factory, claims = setup
    with factory() as db:
        db.add(Workspace(id='existing', name='Existing'))
        db.add(ApiKey(id='key', user_id='existing-user', key_hash=digest('external-api-key'), active=True))
        db.flush()
        db.add(WorkspaceMember(workspace_id='existing', user_id='existing-user', role='owner'))
        db.commit()
    assert client.get('/records', headers={'X-API-Key': 'external-api-key', 'X-Workspace-ID': 'existing'}).json() == {'user': 'existing-user', 'workspace': 'existing'}
    assert client.get('/records', headers={'X-API-Key': 'external-api-key', 'X-Workspace-ID': 'other'}).status_code == 403

def test_secure_cookie_configuration(setup, monkeypatch):
    client, factory, claims = setup
    monkeypatch.setattr(settings, 'SESSION_COOKIE_SECURE', True)
    response = client.post('/api/v1/auth/challenge', headers=HEADERS)
    assert 'Secure' in response.headers['set-cookie']
    assert 'HttpOnly' in response.headers['set-cookie']

def test_calendar_uses_session_identity_without_api_key(setup, monkeypatch):
    from types import SimpleNamespace
    from app.api.v1.routes import auth as calendar_auth
    client, factory, claims = setup
    user = login(client, claims).json()['user']['id']
    monkeypatch.setattr(settings, 'GOOGLE_CLIENT_SECRET', 'secret')
    monkeypatch.setattr(calendar_auth, 'cipher', lambda: None)
    monkeypatch.setattr(calendar_auth.Flow, 'from_client_config', lambda *args, **kwargs: SimpleNamespace(
        fetch_token=lambda **kwargs: None, credentials=SimpleNamespace(refresh_token='refresh-token')))
    saved = []
    monkeypatch.setattr(calendar_auth, 'save_refresh_token', lambda user_id, token: saved.append((user_id, token)))
    response = client.post('/api/v1/auth/google/save', json={'code': 'calendar-code'}, headers=HEADERS)
    assert response.status_code == 200
    assert saved == [(user, 'refresh-token')]

def test_migration_creates_session_schema():
    import importlib.util
    from pathlib import Path
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from sqlalchemy import inspect
    root = Path('C:/Users/KELVIN/Desktop/KELVIN/PYTHON/umbra-assistant')
    versions = root / 'alembic/versions'
    latest = Path(__file__).parent / '0006_google_sessions.py'
    if not latest.exists(): latest = versions / '0006_google_sessions.py'
    files = sorted(path for path in versions.glob('*.py') if path.name < '0006') + [latest]
    engine = create_engine('sqlite://')
    with engine.begin() as connection:
        with Operations.context(MigrationContext.configure(connection)):
            for path in files:
                spec = importlib.util.spec_from_file_location(path.stem, path)
                migration = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(migration)
                migration.upgrade()
        assert {'google_users', 'browser_sessions', 'login_challenges'} <= set(inspect(connection).get_table_names())
    engine.dispose()
