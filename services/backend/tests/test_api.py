from fastapi.testclient import TestClient

from asa.api import create_app
from asa.config import Settings


def test_liveness_does_not_claim_database_readiness():
    client = TestClient(create_app(Settings(_env_file=None, database_url="")))
    assert client.get("/health/live").json() == {"status": "alive"}
    response = client.get("/health/ready")
    assert response.status_code == 503
    assert response.json() == {"status": "not_ready", "database": "unconfigured"}


def test_readiness_hides_database_credentials_on_connection_failure():
    settings = Settings(_env_file=None, database_url="postgresql://u:secret@127.0.0.1:1/none")
    response = TestClient(create_app(settings)).get("/health/ready")
    assert response.status_code == 503
    assert "secret" not in response.text
