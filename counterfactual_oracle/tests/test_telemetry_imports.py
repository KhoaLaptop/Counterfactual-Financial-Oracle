"""
The deprecated Jaeger exporter must only load when a Jaeger endpoint is configured.
"""

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_telemetry_import_does_not_load_jaeger_exporter():
    code = (
        "import sys; import counterfactual_oracle.src.infrastructure.telemetry; "
        "print('opentelemetry.exporter.jaeger.thrift' in sys.modules)"
    )
    result = subprocess.run([sys.executable, "-c", code], cwd=REPO_ROOT, capture_output=True, text=True)

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().splitlines()[-1] == "False"  # earlier lines are app logs
