from unittest.mock import patch

from fastapi.testclient import TestClient

from repomind.api.main import app


def test_health():
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ingest_calls_ingest_repo_and_shapes_response():
    fake_result = {"repo_url": "https://github.com/x/y.git", "files_parsed": 3, "classes": 1, "functions": 2}

    with patch("repomind.api.main.ingest_repo", return_value=fake_result) as mock_ingest:
        with TestClient(app) as client:
            response = client.post("/ingest", json={"repo_url": "https://github.com/x/y.git"})

    assert response.status_code == 200
    assert response.json() == fake_result
    mock_ingest.assert_called_once_with("https://github.com/x/y.git")


def test_ingest_returns_400_when_clone_fails():
    with patch("repomind.api.main.ingest_repo", side_effect=RuntimeError("clone failed")):
        with TestClient(app) as client:
            response = client.post("/ingest", json={"repo_url": "https://github.com/x/y.git"})

    assert response.status_code == 400
    assert "clone failed" in response.json()["detail"]


def test_query_uses_the_chain_stored_on_app_state():
    fake_answer = {
        "question": "what?",
        "cypher": "MATCH (n) RETURN n",
        "results": [{"a": 1}],
        "error": None,
        "answer": "there is one node",
    }

    class FakeChain:
        async def ask(self, question: str) -> dict:
            assert question == "what?"
            return fake_answer

    with TestClient(app) as client:
        client.app.state.chain = FakeChain()
        response = client.post("/query", json={"question": "what?"})

    assert response.status_code == 200
    assert response.json() == fake_answer


def test_graph_stats_returns_counts_for_every_label_and_relationship():
    with TestClient(app) as client:
        response = client.get("/graph/stats")

    assert response.status_code == 200
    assert set(response.json().keys()) == {"files", "classes", "functions", "calls", "inherits", "imports"}
