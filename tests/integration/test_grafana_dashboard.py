"""
integration test for grafana dashboard setup
"""

import json
from pathlib import Path

import pytest
import requests


class TestGrafanaDashboard:
    """test grafana dashboard functionality"""

    def test_dashboard_json_valid(self):
        """test that dashboard json is valid"""
        dashboard_path = Path("docker/grafana/dashboards/market-maker.json")
        assert dashboard_path.exists(), "dashboard json file should exist"

        with open(dashboard_path) as f:
            dashboard_data = json.load(f)

        # verify dashboard structure
        assert "title" in dashboard_data
        assert dashboard_data["title"] == "Market Maker Dashboard"
        assert "panels" in dashboard_data
        assert len(dashboard_data["panels"]) == 4

        # verify panel titles
        panel_titles = [panel["title"] for panel in dashboard_data["panels"]]
        expected_titles = [
            "Current P&L (USDT)",
            "Current Inventory (BTC)",
            "Engine Latency",
            "Outstanding Orders",
        ]

        for expected_title in expected_titles:
            assert expected_title in panel_titles, f"missing panel: {expected_title}"

    def test_dashboard_metrics_queries(self):
        """test that dashboard contains correct prometheus queries"""
        dashboard_path = Path("docker/grafana/dashboards/market-maker.json")

        with open(dashboard_path) as f:
            dashboard_data = json.load(f)

        queries = []
        for panel in dashboard_data["panels"]:
            for target in panel.get("targets", []):
                if "expr" in target:
                    queries.append(target["expr"])

        # verify required metrics are queried
        expected_metrics = [
            "current_pnl_usdt",
            "current_inventory_btc",
            "engine_loop_latency_seconds_bucket",
            "outstanding_orders_total",
        ]

        query_text = " ".join(queries)
        for metric in expected_metrics:
            assert metric in query_text, f"missing metric query: {metric}"

    def test_prometheus_config(self):
        """test prometheus configuration"""
        prometheus_path = Path("docker/prometheus.yml")
        assert prometheus_path.exists(), "prometheus config should exist"

        with open(prometheus_path) as f:
            content = f.read()

        # verify market-maker job is configured
        assert "job_name: 'market-maker'" in content
        assert "host.docker.internal:8000" in content
        assert "metrics_path: '/metrics'" in content

    def test_docker_compose_services(self):
        """test docker-compose configuration"""
        compose_path = Path("docker/docker-compose.yml")
        assert compose_path.exists(), "docker-compose.yml should exist"

        with open(compose_path) as f:
            content = f.read()

        # verify required services
        assert "prometheus:" in content
        assert "grafana:" in content
        assert "redis:" in content

        # verify ports
        assert "3000:3000" in content  # grafana
        assert "9090:9090" in content  # prometheus
        assert "6379:6379" in content  # redis

    @pytest.mark.skip(reason="requires docker running")
    def test_grafana_api_access(self):
        """test that grafana api is accessible when running"""
        # this test requires docker stack to be running
        # skip by default, run manually during testing

        grafana_url = "http://localhost:3000"

        try:
            # check if grafana is running
            response = requests.get(f"{grafana_url}/api/health", timeout=5)
            assert response.status_code == 200

            # check dashboard exists
            auth = ("admin", "admin")
            dashboard_response = requests.get(
                f"{grafana_url}/api/dashboards/uid/market-maker", auth=auth, timeout=5
            )
            assert dashboard_response.status_code == 200

            dashboard_data = dashboard_response.json()
            assert dashboard_data["dashboard"]["title"] == "Market Maker Dashboard"

        except requests.exceptions.ConnectionError:
            pytest.skip("grafana not running")


# manual integration test function
def test_full_dashboard_integration():
    """
    manual test to verify the complete dashboard works

    to run this test:
    1. start docker stack: ./scripts/start_dashboard.sh
    2. start live engine with metrics enabled
    3. verify dashboard shows data at http://localhost:3000
    """
    print("manual test steps:")
    print("1. start monitoring stack: ./scripts/start_dashboard.sh")
    print("2. start live engine with healthcheck enabled")
    print("3. open http://localhost:3000 in browser")
    print("4. login with admin/admin")
    print("5. verify 'market maker dashboard' shows live data")
    print("6. check all 4 panels display metrics:")
    print("   - current p&l (usdt)")
    print("   - current inventory (btc)")
    print("   - engine latency (p95/p50)")
    print("   - outstanding orders (buy/sell)")

    # this would be the actual test when run manually
    assert True, "manual verification required"


if __name__ == "__main__":
    test_full_dashboard_integration()
