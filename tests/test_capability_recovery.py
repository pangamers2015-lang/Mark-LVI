from actions.capability_recovery import is_capability_failure, _safe_value, _topic_for


def test_unknown_tool_triggers_capability_recovery():
    assert is_capability_failure("missing_action", {}, "Unknown tool: missing_action")


def test_explicit_unsupported_platform_triggers_recovery():
    assert is_capability_failure(
        "desktop_control", {}, "This operation is not supported on this platform."
    )


def test_permission_denial_does_not_trigger_recovery():
    assert not is_capability_failure("file_controller", {}, "Permission denied.")


def test_missing_file_does_not_trigger_recovery():
    assert not is_capability_failure("file_controller", {}, "File not found: notes.txt")


def test_transient_timeout_does_not_trigger_recovery():
    assert not is_capability_failure("web_search", {}, "The request timed out.")


def test_secret_arguments_are_redacted():
    assert _safe_value("api_key", "private-value") == "[REDACTED]"
    assert _safe_value("folder_path", r"C:\Users\Example\Documents") == "Documents"


def test_folder_requests_get_a_stable_capability_topic():
    assert _topic_for("file_controller", {"folder_path": "Documents"}) == (
        "local filesystem and folder access"
    )

def test_unavailable_tool_result_triggers_recovery():
    assert is_capability_failure("file_controller", {}, "Action 'file_controller' is not available.")


def test_unavailable_model_service_does_not_trigger_recovery():
    assert not is_capability_failure("consult_local", {}, "Local model is not available.")


def test_user_profile_path_is_redacted_before_cloud_research():
    from actions.capability_recovery import _safe_failure
    result = _safe_failure(r"Could not access C:\Users\Andrei\Documents")
    assert "Andrei" not in result
    assert "[LOCAL_USER_PATH]" in result
