import time

import pytest

from comfyremote_connector.protocol import service_origin, validate_command
from comfyremote_connector.state import State


@pytest.mark.parametrize(
    "origin", ["https://example.com", "http://127.0.0.1:8189", "http://localhost:8189"]
)
def test_origins(origin):
    assert service_origin(origin + "/") == origin


@pytest.mark.parametrize(
    "origin",
    [
        "http://example.com",
        "https://user:pass@example.com",
        "https://example.com/path",
        "https://example.com?token=x",
        "file:///tmp",
        "https://example.com#x",
    ],
)
def test_unsafe_origins(origin):
    with pytest.raises(ValueError):
        service_origin(origin)


def command(method, path):
    return {"id": "a" * 32, "size": 0, "method": method, "path": path, "expires": time.time() + 60}


def test_expired_commands_are_rejected_after_restart(tmp_path):
    value = command("POST", "/prompt")
    value["expires"] = time.time() - 1
    with pytest.raises(ValueError, match="expired"):
        validate_command(value, State(tmp_path))


def test_owned_history_cancellation_and_outputs(tmp_path):
    state = State(tmp_path)
    with state.db() as db:
        db.execute("INSERT INTO prompts VALUES ('owned')")
    for method, path in [("GET", "/history/owned"), ("POST", "/api/jobs/owned/cancel")]:
        validate_command(command(method, path), state)
    state.own_history_outputs(
        {
            "owned": {
                "outputs": {
                    "1": {
                        "audio": [
                            {"filename": "sound.wav", "subfolder": "ComfyRemote", "type": "output"}
                        ]
                    }
                }
            }
        }
    )
    validate_command(
        command("GET", "/view?filename=sound.wav&subfolder=ComfyRemote&type=output"), state
    )
    for method, path in [
        ("GET", "/history/other"),
        ("POST", "/api/jobs/other/cancel"),
        ("GET", "/view?filename=private.png"),
        ("GET", "/system_stats?extra=1"),
        ("POST", "/interrupt"),
        ("POST", "/manager/install"),
        ("GET", "//evil.com/queue"),
    ]:
        with pytest.raises(ValueError):
            validate_command(command(method, path), state)


def test_credentials_are_encrypted_and_not_in_plaintext(tmp_path):
    state = State(tmp_path)
    payload = {"token": "secret-test-token", "origin": "https://example.com"}
    state.save_pairing(payload)
    assert b"secret-test-token" not in (tmp_path / "pairing.dpapi").read_bytes()
    assert state.load_pairing() == payload
    state.clear_pairing()
    assert state.load_pairing() is None


def test_workflow_secrets_are_blocked_before_network():
    from comfyremote_connector.workflow import validate_workflow

    for node in [
        {"class_type": "Test", "inputs": {"api_key": "secret"}},
        {"class_type": "PythonExec", "inputs": {}},
        {"class_type": "Test", "inputs": {"text": "Bearer abcdefghijklmnop"}},
    ]:
        with pytest.raises(ValueError):
            validate_workflow({"1": node})


def test_model_inventory_is_reduced_to_referenced_models():
    from comfyremote_connector.workflow import minimal_info

    graph = {"1": {"class_type": "UNETLoader", "inputs": {"unet_name": "selected"}}}
    info = {"UNETLoader": {"input": {"required": {"unet_name": [["selected", "private-other"]]}}}}
    assert minimal_info(graph, info)["UNETLoader"]["input"]["required"]["unet_name"][0] == [
        "selected"
    ]
