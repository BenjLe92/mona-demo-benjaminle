import pytest
from fastapi.testclient import TestClient

from app.api.routes import get_as_of
from app.main import create_app
from tests.conftest import AS_OF, FIXTURES


@pytest.fixture(scope="module")
def client():
    app = create_app(FIXTURES)
    app.dependency_overrides[get_as_of] = lambda: AS_OF
    with TestClient(app) as test_client:
        yield test_client


def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok"}


def test_meta_reports_loaded_and_skipped_rows(client):
    body = client.get("/api/meta").json()
    assert body["as_of"] == "2026-10-13"
    assert (body["businesses"], body["grants"], body["loan_offers"]) == (3, 7, 5)
    grant_file = next(f for f in body["files"] if "Grant" in f["file"])
    assert grant_file["excluded"]["closed"] == 1 and len(grant_file["skipped"]) == 2


def test_list_and_search_businesses(client):
    assert [b["profile_id"] for b in client.get("/api/businesses").json()] == ["MONA-0001", "MONA-0002", "MONA-0004"]
    assert [b["profile_id"] for b in client.get("/api/businesses", params={"search": "brooklyn"}).json()] == ["MONA-0002"]
    assert [b["profile_id"] for b in client.get("/api/businesses", params={"state": "nm"}).json()] == ["MONA-0004"]


def test_get_business_and_404(client):
    body = client.get("/api/businesses/mona-0002").json()
    assert body["profile_id"] == "MONA-0002" and "Credit score" in body["unknown_fields"]
    missing = client.get("/api/businesses/MONA-9999")
    assert missing.status_code == 404 and "MONA-9999" in missing.json()["detail"]
    assert client.get("/api/businesses/MONA-9999/matches").status_code == 404


def test_matches_default_hides_ineligible_and_expired(client):
    body = client.get("/api/businesses/MONA-0001/matches").json()
    names = [m["name"] for m in body["results"]]
    assert "Expired Grant" not in names and "Closed Grant" not in names
    assert all(m["eligibility"]["status"] != "ineligible" for m in body["results"])
    assert body["total"] == len(body["results"])
    assert body["counts"]["grant"] == {"likely_eligible": 2, "needs_verification": 2, "ineligible": 1}
    assert body["counts"]["coming_soon"]["ineligible"] == 1


def test_match_explains_eligibility_and_relevance(client):
    body = client.get("/api/businesses/MONA-0001/matches", params={"kind": "grant"}).json()
    # The local, woman-owned, brick-and-mortar grant outranks the national industry grant.
    # Grants with something left to verify always sort after the ones with nothing left.
    assert [m["name"] for m in body["results"]] == [
        "Chicago Women Grant", "National Food Grant", "Revenue Cap Grant", "Silent Grant",
    ]
    top = body["results"][1]
    assert top["eligibility"]["status"] == "likely_eligible"
    assert all(check["reason"] for check in top["eligibility"]["checks"])
    assert top["eligibility"]["warnings"]
    assert top["relevance"]["score"] == sum(c["points"] for c in top["relevance"]["components"])
    assert all(c["reason"] for c in top["relevance"]["components"])

    chicago = next(m for m in body["results"] if m["name"] == "Chicago Women Grant")
    assert {c["rule"]: c["outcome"] for c in chicago["eligibility"]["checks"]} == {
        "location": "pass",
        "founder_requirement": "pass",
    }
    assert chicago["criteria_text"] == "- Must be at least 51% woman-owned."


def test_unparsed_and_absent_criteria_surface_as_needs_verification(client):
    body = client.get("/api/businesses/MONA-0001/matches", params={"status": "needs_verification"}).json()
    by_name = {m["name"]: m["eligibility"] for m in body["results"]}

    capped = by_name["Revenue Cap Grant"]
    assert capped["summary"] == (
        "Passed: location. To verify: annual revenue requirement; employee count requirement; time in business requirement."
    )
    assert [c["rule"] for c in capped["checks"]] == ["location", "unchecked_revenue", "unchecked_employees", "unchecked_tenure"]
    assert "Your profile shows: $100,000 - $249,999." in capped["checks"][1]["reason"]

    silent = by_name["Silent Grant"]  # no criteria; its promotional description is not used
    assert [c["rule"] for c in silent["checks"]] == ["location", "criteria_not_listed"]


def test_unknown_attributes_surface_as_needs_verification(client):
    body = client.get("/api/businesses/MONA-0002/matches", params={"kind": "loan", "include_ineligible": True}).json()
    by_id = {m["opportunity_id"]: m for m in body["results"]}
    assert by_id["L-kiva"]["eligibility"]["status"] == "likely_eligible"
    assert by_id["L-honeycomb"]["eligibility"]["status"] == "needs_verification"
    assert "not on file" in by_id["L-honeycomb"]["eligibility"]["checks"][1]["reason"]


def test_filters_and_paging(client):
    url = "/api/businesses/MONA-0001/matches"
    loans = client.get(url, params={"kind": "loan", "include_ineligible": True}).json()
    assert {m["kind"] for m in loans["results"]} == {"loan"} and loans["total"] == 5

    ineligible = client.get(url, params={"status": "ineligible"}).json()
    assert ineligible["total"] > 0
    assert {m["eligibility"]["status"] for m in ineligible["results"]} == {"ineligible"}

    upcoming = client.get(url, params={"kind": "coming_soon", "include_ineligible": True}).json()
    assert [m["name"] for m in upcoming["results"]] == ["Upcoming Pitch"]

    page = client.get(url, params={"include_ineligible": True, "limit": 2, "offset": 1}).json()
    everything = client.get(url, params={"include_ineligible": True}).json()
    assert [m["opportunity_id"] for m in page["results"]] == [m["opportunity_id"] for m in everything["results"][1:3]]
    assert page["total"] == everything["total"]


def test_invalid_query_values_are_rejected(client):
    url = "/api/businesses/MONA-0001/matches"
    assert client.get(url, params={"kind": "bond"}).status_code == 422
    assert client.get(url, params={"limit": 0}).status_code == 422


def test_as_of_env_override(monkeypatch):
    monkeypatch.setenv("MONA_AS_OF_DATE", "2026-01-02")
    assert get_as_of().isoformat() == "2026-01-02"
    monkeypatch.delenv("MONA_AS_OF_DATE")
    assert get_as_of() is not None
