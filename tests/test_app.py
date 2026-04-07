from fastapi.testclient import TestClient
from server.app import app

client = TestClient(app)

def test_root():
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "CI/CD Pipeline Diagnosis Environment"
    assert "status" in data

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}

def test_reset():
    response = client.post("/reset", json={"task": "log_diagnosis"})
    assert response.status_code == 200
    data = response.json()
    
    # The response wraps the CICDObservation under 'observation'
    obs = data.get("observation", data)
    assert "task_name" in obs
    assert obs["task_name"] == "log_diagnosis"
    assert "pipeline_status" in obs
