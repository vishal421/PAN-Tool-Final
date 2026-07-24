"""
Phase 1 smoke tests.

These verify the scaffold itself: the API is reachable, the vendor
registry mechanism works, the normalized model + generator produce
valid output for a hand-built NormalizedConfig, and uploading against
an unregistered vendor fails cleanly instead of pretending to work.

Real parser correctness tests land per-vendor in tests/parsers/ starting
Phase 2.
"""
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.normalizer.models import (
    NormalizedConfig, AddressObject, AddressType,
    ServiceObject, ServiceProtocol, AddressGroup,
)
from app.generators.paloalto.generator import PaloAltoGenerator


@pytest.fixture()
def client():
    # Using the context manager form triggers FastAPI's startup event
    # (init_db), which is required before the SQLite tables exist.
    with TestClient(app) as c:
        yield c


def test_health(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_vendors_endpoint_returns_list(client):
    resp = client.get("/api/vendors")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_upload_unregistered_vendor_fails_cleanly(client):
    fake_file = io.BytesIO(b"config firewall address\nend\n")
    resp = client.post(
        "/api/convert",
        data={"vendor": "does-not-exist"},
        files={"file": ("test.conf", fake_file, "text/plain")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["job"]["status"] == "failed"
    assert "No parser registered" in body["job"]["error_message"]


def test_generator_produces_valid_looking_cli_from_manual_model():
    config = NormalizedConfig()
    config.addresses.append(
        AddressObject(name="Server01", type=AddressType.IP_NETMASK, value="10.10.10.10/32")
    )
    config.address_groups.append(
        AddressGroup(name="DMZ", members=["Server01"])
    )
    config.services.append(
        ServiceObject(name="TCP_8443", protocol=ServiceProtocol.TCP, dest_port="8443")
    )

    cli = PaloAltoGenerator(config).generate_all()

    assert "set address Server01 ip-netmask 10.10.10.10/32" in cli
    assert "set address-group DMZ static Server01" in cli
    assert "set service TCP_8443 protocol tcp port 8443" in cli


def test_generator_flags_unsupported_without_guessing():
    config = NormalizedConfig()
    config.addresses.append(
        AddressObject(name="WeirdObj", type=AddressType.IP_WILDCARD, value="10.0.0.0/0.0.255.255")
    )
    cli = PaloAltoGenerator(config).generate_all()
    assert "TODO (UNSUPPORTED)" in cli
    assert "WeirdObj" in cli
