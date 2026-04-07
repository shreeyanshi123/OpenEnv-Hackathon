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
    
    # Because openenv observation schemas vary slightly, we check for presence
    # of things our CICDEnv provides
    assert "task_name" in data
    assert data["task_name"] == "log_diagnosis"
    assert "pipeline_status" in data
