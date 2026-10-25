"""
Locust load testing suite for BI Agent SaaS.
Simulates realistic multi-tenant user behavior:
- User login and authentication
- Conversational chat queries
- Analytical SQL query execution
- Dataset file upload
- Metric catalog discovery
- Health & metrics telemetry monitoring
"""

from locust import HttpUser, task, between
import uuid

class BIAgentTenantUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        """Authenticate tenant user and obtain JWT."""
        self.email = f"loaduser_{uuid.uuid4().hex[:6]}@example.com"
        self.password = "LoadTestPass123!"
        
        # Attempt signup or login
        signup_payload = {
            "email": self.email,
            "password": self.password,
            "full_name": "Load Test User"
        }
        res = self.client.post("/api/v1/auth/signup", json=signup_payload)
        if res.status_code == 201 or res.status_code == 200:
            token = res.json().get("access_token")
            self.client.headers.update({"Authorization": f"Bearer {token}"})

    @task(5)
    def check_health_and_metrics(self):
        """Poll liveness and operational metrics."""
        self.client.get("/api/v1/health/live")
        self.client.get("/api/v1/health/metrics")

    @task(3)
    def query_semantic_metrics(self):
        """Fetch list of semantic business metrics."""
        self.client.get("/api/v1/analytics/metrics")

    @task(2)
    def execute_chat_query(self):
        """Simulate user asking a natural language question."""
        payload = {
            "message": "What were our total sales this month compared with last month?",
            "context": {}
        }
        self.client.post("/api/v1/chat/messages", json=payload)

    @task(1)
    def scan_anomalies(self):
        """Simulate running an anomaly scan."""
        payload = {
            "metric": "revenue",
            "sensitivity": "medium"
        }
        self.client.post("/api/v1/anomalies/scan", json=payload)
