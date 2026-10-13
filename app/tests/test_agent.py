from unittest.mock import patch

from app.agent import run_once
from app.config import Settings

SETTINGS = Settings(
    metrics_endpoint="http://api:8000/metrics",
    collection_interval=5,
    request_timeout=3,
)


@patch("app.agent.send_metrics")
@patch("app.agent.format_metrics")
@patch("app.agent.collect_system_metrics")
def test_run_once_collects_formats_and_sends(mock_collect, mock_format, mock_send):
    mock_collect.return_value = {"cpu": {"percent": 10.0}}
    mock_format.return_value = {"agent": "system-metrics-agent"}
    mock_send.return_value = {"status_code": 201}

    result = run_once(SETTINGS)

    mock_format.assert_called_once_with({"cpu": {"percent": 10.0}})
    mock_send.assert_called_once_with(
        endpoint="http://api:8000/metrics",
        payload={"agent": "system-metrics-agent"},
        timeout=3,
    )
    assert result == {"status_code": 201}
