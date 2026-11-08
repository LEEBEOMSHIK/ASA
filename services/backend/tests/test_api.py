from fastapi.testclient import TestClient

from asa import database
from asa.api import create_app
from asa.config import Settings


def test_liveness_does_not_claim_database_readiness():
    with TestClient(create_app(Settings(_env_file=None, database_url=""))) as client:
        assert client.get("/health/live").json() == {"status": "alive"}
        response = client.get("/health/ready")
        assert response.status_code == 503
        assert response.json() == {"status": "not_ready", "database": "unconfigured"}


def test_readiness_hides_database_credentials_on_connection_failure():
    settings = Settings(_env_file=None, database_url="postgresql://u:secret@127.0.0.1:1/none")
    with TestClient(create_app(settings)) as client:
        response = client.get("/health/ready")
        assert response.status_code == 503
        assert "secret" not in response.text
        pool = database._pools[settings.database_url]
    try:
        assert pool.closed, "readiness test left its connection pool running"
        assert settings.database_url not in database._pools
    finally:
        database.close_database(settings.database_url)
