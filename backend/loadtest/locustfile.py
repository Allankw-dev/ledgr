"""Load test for the Ledgr API — run against a STAGING copy, never production.

    pip install locust
    set LEDGR_TEST_EMAIL=bursar@example.com
    set LEDGR_TEST_PASSWORD=...        (an account WITHOUT 2FA enabled)
    locust -f loadtest/locustfile.py --host http://localhost:4000

Then open http://localhost:8089 and try e.g. 100 users, spawn rate 10.
Watch for: failure %, p95 latency, and 503/429 responses. Login is rate
limited (10/min per IP), so the token is fetched ONCE for the whole run.
"""
import os

import requests
from locust import HttpUser, between, events, task

TOKEN = None


@events.test_start.add_listener
def login_once(environment, **_kwargs):
    global TOKEN
    resp = requests.post(
        f"{environment.host}/api/auth/login",
        json={"email": os.environ["LEDGR_TEST_EMAIL"], "password": os.environ["LEDGR_TEST_PASSWORD"]},
        timeout=15,
    )
    resp.raise_for_status()
    body = resp.json()
    if "token" not in body:
        raise RuntimeError("Login did not return a token — use a test account without 2FA")
    TOKEN = body["token"]


class BursarUser(HttpUser):
    wait_time = between(1, 4)

    def on_start(self):
        self.client.headers.update({"Authorization": f"Bearer {TOKEN}"})

    @task(5)
    def list_students(self):
        self.client.get("/api/students?page=1&page_size=25", name="/api/students")

    @task(5)
    def list_invoices(self):
        self.client.get("/api/invoices?page=1&page_size=25", name="/api/invoices")

    @task(2)
    def analytics(self):
        self.client.get("/api/reports/analytics", name="/api/reports/analytics")

    @task(1)
    def health(self):
        self.client.get("/health/ready", name="/health/ready")
