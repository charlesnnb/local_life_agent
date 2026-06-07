"""Black-box tests for the Demo/Hybrid/Live profile launcher."""

import os
from pathlib import Path
import socket
import subprocess


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RUNNER = PROJECT_ROOT / "run.sh"


def test_launcher_execs_service_processes_so_cleanup_targets_real_pids():
    script = RUNNER.read_text(encoding="utf-8")

    assert "exec python run_backend.py" in script
    assert 'exec "$project_root/frontend/node_modules/.bin/vite"' in script


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _run_profile(
    tmp_path: Path,
    *arguments: str,
    inherited_env: dict[str, str] | None = None,
):
    env = os.environ.copy()
    env["LOCAL_LIFE_PROJECT_ROOT"] = str(tmp_path)
    env.update(inherited_env or {})
    return subprocess.run(
        ["bash", str(RUNNER), *arguments],
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def _write_dot_env(tmp_path: Path, content: str) -> None:
    _write(tmp_path / ".env", content)


def _write_frontend_env(tmp_path: Path, content: str) -> None:
    _write(tmp_path / "frontend" / ".env", content)


def test_demo_profile_check_succeeds_without_keys(tmp_path):
    # Demo mode does not need .env — the run.sh case statement sets all flags.
    result = _run_profile(tmp_path, "demo", "--check")

    assert result.returncode == 0
    assert "Profile check passed: demo" in result.stdout
    assert "DEEPSEEK_API_KEY" not in result.stdout


def test_live_profile_check_succeeds_with_required_keys(tmp_path):
    _write_dot_env(
        tmp_path,
        "\n".join(
            [
                "DEEPSEEK_API_KEY=live-deepseek-key",
                "AMAP_WEB_SERVICE_KEY=live-amap-key",
            ]
        ),
    )
    _write_frontend_env(
        tmp_path,
        "VITE_AMAP_JS_KEY=live-js-key\nVITE_AMAP_SECURITY_JS_CODE=\n",
    )

    result = _run_profile(tmp_path, "live", "--check")

    assert result.returncode == 0
    assert "Profile check passed: live" in result.stdout
    assert "live-deepseek-key" not in result.stdout
    assert "live-amap-key" not in result.stdout
    assert "live-js-key" not in result.stdout


def test_hybrid_profile_check_succeeds_with_real_provider_keys(tmp_path):
    _write_dot_env(
        tmp_path,
        "\n".join(
            [
                "DEEPSEEK_API_KEY=hybrid-deepseek-key",
                "AMAP_WEB_SERVICE_KEY=hybrid-amap-key",
            ]
        ),
    )
    _write_frontend_env(
        tmp_path,
        "VITE_AMAP_JS_KEY=hybrid-js-key\nVITE_AMAP_SECURITY_JS_CODE=\n",
    )

    result = _run_profile(tmp_path, "hybrid", "--check")

    assert result.returncode == 0
    assert "Profile check passed: hybrid" in result.stdout
    assert "hybrid-deepseek-key" not in result.stdout
    assert "hybrid-amap-key" not in result.stdout
    assert "hybrid-js-key" not in result.stdout


def test_hybrid_profile_requires_real_provider_keys(tmp_path):
    _write_dot_env(
        tmp_path,
        "DEEPSEEK_API_KEY=\nAMAP_WEB_SERVICE_KEY=\n",
    )
    _write_frontend_env(tmp_path, "VITE_AMAP_JS_KEY=\n")

    result = _run_profile(
        tmp_path,
        "hybrid",
        "--check",
        inherited_env={
            "DEEPSEEK_API_KEY": "stale-deepseek",
            "AMAP_WEB_SERVICE_KEY": "stale-amap",
        },
    )

    assert result.returncode != 0
    assert "Hybrid profile is incomplete" in result.stderr
    assert "DEEPSEEK_API_KEY" in result.stderr
    assert "AMAP_WEB_SERVICE_KEY or AMAP_API_KEY" in result.stderr
    assert "VITE_AMAP_JS_KEY" in result.stderr
    assert "stale-deepseek" not in result.stderr
    assert "stale-amap" not in result.stderr


def test_live_profile_check_lists_missing_keys(tmp_path):
    _write_dot_env(
        tmp_path,
        "ENABLE_LLM=true\nDEEPSEEK_API_KEY=\nENABLE_AMAP=true\n",
    )
    _write_frontend_env(
        tmp_path,
        "VITE_AMAP_JS_KEY=\n",
    )

    result = _run_profile(
        tmp_path,
        "live",
        "--check",
        inherited_env={"AMAP_API_KEY": "stale-parent-key"},
    )

    assert result.returncode != 0
    assert "Live profile is incomplete" in result.stderr
    assert "DEEPSEEK_API_KEY" in result.stderr
    assert "AMAP_WEB_SERVICE_KEY or AMAP_API_KEY" in result.stderr
    assert "VITE_AMAP_JS_KEY" in result.stderr


def test_unknown_profile_shows_usage(tmp_path):
    result = _run_profile(tmp_path, "staging", "--check")

    assert result.returncode != 0
    assert "Usage: ./run.sh demo [scenario] [--check]" in result.stderr
    assert "./run.sh hybrid [restaurant_full] [--check]" in result.stderr


def test_demo_profile_accepts_exception_scenario(tmp_path):
    result = _run_profile(
        tmp_path,
        "demo",
        "restaurant_full",
        "--check",
    )

    assert result.returncode == 0
    assert "Demo scenario: restaurant_full" in result.stdout


def test_demo_profile_rejects_unknown_scenario(tmp_path):
    result = _run_profile(tmp_path, "demo", "power_outage", "--check")

    assert result.returncode != 0
    assert "Unknown Demo scenario: power_outage" in result.stderr


def test_hybrid_profile_accepts_restaurant_full_scenario(tmp_path):
    _write_dot_env(
        tmp_path,
        "\n".join(
            [
                "DEEPSEEK_API_KEY=test-key",
                "AMAP_WEB_SERVICE_KEY=test-key",
            ]
        ),
    )
    _write_frontend_env(
        tmp_path,
        "VITE_AMAP_JS_KEY=test-key\n",
    )

    result = _run_profile(
        tmp_path,
        "hybrid",
        "restaurant_full",
        "--check",
    )

    assert result.returncode == 0
    assert "Demo scenario: restaurant_full" in result.stdout


def test_hybrid_profile_rejects_other_demo_scenarios(tmp_path):
    result = _run_profile(
        tmp_path,
        "hybrid",
        "traffic_delay",
        "--check",
    )

    assert result.returncode != 0
    assert "Hybrid mode only supports restaurant_full" in result.stderr


def test_live_profile_rejects_demo_scenario(tmp_path):
    result = _run_profile(tmp_path, "live", "traffic_delay", "--check")

    assert result.returncode != 0
    assert "Demo scenarios are not available in live mode" in result.stderr


def test_start_refuses_to_mix_with_an_existing_backend(tmp_path):
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        backend_port = listener.getsockname()[1]
        _write(
            tmp_path / ".env",
            f"PORT={backend_port}\nFRONTEND_PORT=5199\n",
        )

        result = _run_profile(tmp_path, "demo")

    assert result.returncode != 0
    assert f"Backend port {backend_port} is already in use" in result.stderr
    assert "Stop the existing process" in result.stderr


def test_start_refuses_to_move_frontend_to_another_port(tmp_path):
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        frontend_port = listener.getsockname()[1]
        _write(
            tmp_path / ".env",
            f"PORT=5198\nFRONTEND_PORT={frontend_port}\n",
        )

        result = _run_profile(tmp_path, "demo")

    assert result.returncode != 0
    assert f"Frontend port {frontend_port} is already in use" in result.stderr
    assert "Vite will not switch to another port" in result.stderr
