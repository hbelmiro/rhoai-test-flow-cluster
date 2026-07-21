import json
import urllib.error
from unittest.mock import MagicMock, patch

import pytest

from main import (
    DEFAULT_PARAMS,
    LOG_TAIL_LINES,
    _auth_header,
    _fetch_text,
    _job_url,
    build_url,
    follow_log,
    format_progress,
    get_build_status,
    get_console_log,
    get_crumb,
    main,
    parse_progress,
    show_progress,
    trigger_build,
    wait_for_build_number,
    watch_build,
)


class TestAuthHeader:
    def test_encodes_credentials(self) -> None:
        header = _auth_header("me", "secret")
        assert header.startswith("Basic ")

    def test_round_trips(self) -> None:
        import base64

        header = _auth_header("user", "token123")
        decoded = base64.b64decode(header.removeprefix("Basic ")).decode()
        assert decoded == "user:token123"


class TestJobUrl:
    def test_single_segment(self) -> None:
        assert _job_url("https://ci", "myjob") == "https://ci/job/myjob"

    def test_nested_path(self) -> None:
        assert (
            _job_url("https://ci", "devops/rhoai-test-flow")
            == "https://ci/job/devops/job/rhoai-test-flow"
        )


class TestBuildUrl:
    def test_returns_build_with_parameters_url(self) -> None:
        url = build_url("https://ci", "devops/rhoai-test-flow")
        assert url.endswith("/buildWithParameters")
        assert "/job/devops/job/rhoai-test-flow/" in url


class TestGetCrumb:
    @patch("main.urllib.request.urlopen")
    def test_returns_crumb_dict(self, mock_urlopen: MagicMock) -> None:
        body = json.dumps(
            {"crumbRequestField": "Jenkins-Crumb", "crumb": "abc123"}
        ).encode()
        mock_resp = MagicMock()
        mock_resp.read.return_value = body
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        result = get_crumb("https://ci", "me", "tok")
        assert result == {"Jenkins-Crumb": "abc123"}


class TestTriggerBuild:
    @patch("main.get_crumb", return_value={"Jenkins-Crumb": "abc"})
    @patch("main.urllib.request.urlopen")
    def test_returns_queue_url(
        self, mock_urlopen: MagicMock, _mock_crumb: MagicMock
    ) -> None:
        mock_resp = MagicMock()
        mock_resp.headers = {"Location": "https://ci/queue/item/42/"}
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        queue_url = trigger_build(
            jenkins_url="https://ci",
            job_path="devops/myjob",
            user="me",
            token="tok",
            params={"A": "1"},
        )
        assert queue_url == "https://ci/queue/item/42/"

        req = mock_urlopen.call_args[0][0]
        assert req.full_url == "https://ci/job/devops/job/myjob/buildWithParameters"
        assert req.method == "POST"
        assert req.get_header("Jenkins-crumb") == "abc"
        assert b"A=1" in req.data

    @patch("main.get_crumb", return_value={"Jenkins-Crumb": "abc"})
    @patch("main.urllib.request.urlopen")
    def test_raises_on_http_error(
        self, mock_urlopen: MagicMock, _mock_crumb: MagicMock
    ) -> None:
        mock_urlopen.side_effect = urllib.error.HTTPError(
            "https://ci",
            403,
            "Forbidden",
            {},
            None,  # type: ignore[arg-type]
        )
        with pytest.raises(urllib.error.HTTPError):
            trigger_build(
                jenkins_url="https://ci",
                job_path="devops/myjob",
                user="me",
                token="tok",
                params={"A": "1"},
            )


class TestWaitForBuildNumber:
    @patch("main.time.sleep")
    @patch("main._api_get")
    def test_returns_build_number_immediately(
        self, mock_get: MagicMock, mock_sleep: MagicMock
    ) -> None:
        mock_get.return_value = {"executable": {"number": 100, "url": "..."}}
        result = wait_for_build_number("https://ci/queue/item/42/", "me", "tok")
        assert result == 100
        mock_sleep.assert_not_called()

    @patch("main.time.sleep")
    @patch("main._api_get")
    def test_polls_until_executable(
        self, mock_get: MagicMock, mock_sleep: MagicMock
    ) -> None:
        mock_get.side_effect = [
            {"why": "waiting"},
            {"why": "waiting"},
            {"executable": {"number": 200, "url": "..."}},
        ]
        result = wait_for_build_number(
            "https://ci/queue/item/42/", "me", "tok", poll_interval=1
        )
        assert result == 200
        assert mock_sleep.call_count == 2

    @patch("main.time.sleep")
    @patch("main._api_get")
    def test_raises_on_cancelled(
        self, mock_get: MagicMock, _mock_sleep: MagicMock
    ) -> None:
        mock_get.return_value = {"cancelled": True}
        with pytest.raises(RuntimeError, match="cancelled"):
            wait_for_build_number("https://ci/queue/item/42/", "me", "tok")


class TestGetBuildStatus:
    @patch("main._api_get")
    def test_returns_build_data(self, mock_get: MagicMock) -> None:
        mock_get.return_value = {"result": "SUCCESS", "duration": 60000}
        data = get_build_status("https://ci", "devops/job", 100, "me", "tok")
        assert data["result"] == "SUCCESS"
        mock_get.assert_called_once_with(
            "https://ci/job/devops/job/job/100/api/json", "me", "tok"
        )


class TestWatchBuild:
    @patch("main.time.sleep")
    @patch("main.get_build_status")
    def test_returns_result_when_finished(
        self, mock_status: MagicMock, mock_sleep: MagicMock
    ) -> None:
        mock_status.return_value = {"result": "SUCCESS", "duration": 60000}
        result = watch_build("https://ci", "devops/job", 100, "me", "tok")
        assert result == "SUCCESS"
        mock_sleep.assert_not_called()

    @patch("main.time.sleep")
    @patch("main.get_build_status")
    def test_polls_until_result(
        self, mock_status: MagicMock, mock_sleep: MagicMock
    ) -> None:
        mock_status.side_effect = [
            {"result": None, "duration": 10000, "estimatedDuration": 60000},
            {"result": None, "duration": 30000, "estimatedDuration": 60000},
            {"result": "FAILURE", "duration": 60000},
        ]
        result = watch_build(
            "https://ci", "devops/job", 100, "me", "tok", poll_interval=1
        )
        assert result == "FAILURE"
        assert mock_sleep.call_count == 2


class TestGetConsoleLog:
    @patch("main.urllib.request.urlopen")
    def test_returns_text_and_offset(self, mock_urlopen: MagicMock) -> None:
        mock_resp = MagicMock()
        mock_resp.read.return_value = b"[Pipeline] stage\n"
        mock_resp.headers = {"X-Text-Size": "500", "X-More-Data": "true"}
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        text, new_start, more = get_console_log(
            "https://ci", "devops/job", 100, "me", "tok", start=0
        )
        assert text == "[Pipeline] stage\n"
        assert new_start == 500
        assert more is True

    @patch("main.urllib.request.urlopen")
    def test_missing_text_size_header_falls_back_to_start(
        self, mock_urlopen: MagicMock
    ) -> None:
        mock_resp = MagicMock()
        mock_resp.read.return_value = b"some output"
        mock_resp.headers = {}
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        _, new_start, _ = get_console_log(
            "https://ci", "devops/job", 100, "me", "tok", start=42
        )
        assert new_start == 42

    @patch("main.urllib.request.urlopen")
    def test_no_more_data(self, mock_urlopen: MagicMock) -> None:
        mock_resp = MagicMock()
        mock_resp.read.return_value = b"Finished: SUCCESS\n"
        mock_resp.headers = {"X-Text-Size": "1000"}
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        _, _, more = get_console_log(
            "https://ci", "devops/job", 100, "me", "tok", start=500
        )
        assert more is False


class TestFollowLog:
    @patch("main.time.sleep")
    @patch("main.get_console_log")
    def test_streams_until_done(
        self, mock_log: MagicMock, mock_sleep: MagicMock
    ) -> None:
        mock_log.side_effect = [
            ("line 1\n", 100, True),
            ("line 2\n", 200, False),
        ]
        follow_log("https://ci", "devops/job", 100, "me", "tok", interval=1)
        assert mock_log.call_count == 2
        assert mock_sleep.call_count == 1

    @patch("main.time.sleep")
    @patch("main.get_console_log")
    def test_no_sleep_when_done_immediately(
        self, mock_log: MagicMock, mock_sleep: MagicMock
    ) -> None:
        mock_log.return_value = ("done\n", 100, False)
        follow_log("https://ci", "devops/job", 100, "me", "tok")
        mock_sleep.assert_not_called()


class TestParseProgress:
    def test_detects_entered_stages(self) -> None:
        log = (
            "[2026-07-20T12:29:05.374Z] [Pipeline] { (Install new cluster)\n"
            "[2026-07-20T12:30:00.000Z] [Pipeline] { (Generate Test Config File)\n"
        )
        result = parse_progress(log)
        stages = {s["name"]: s["status"] for s in result["stages"]}
        assert stages["Install new cluster"] == "done"
        assert stages["Generate Test Config File"] == "running"
        assert stages["Deploy RHOAI operator"] == "pending"

    def test_detects_skipped_stages(self) -> None:
        log = (
            '[2026-07-20T12:29:05.374Z] Stage "Setup BYOIDC" skipped due to'
            " when conditional\n"
        )
        result = parse_progress(log)
        stages = {s["name"]: s["status"] for s in result["stages"]}
        assert stages["Setup BYOIDC"] == "skipped"

    def test_detects_cluster_state(self) -> None:
        log = (
            "[2026-07-20T12:30:00.000Z] >: installing\n"
            "[2026-07-20T12:45:00.000Z] >: ready\n"
        )
        result = parse_progress(log)
        assert result["cluster_state"] == "ready"

    def test_single_stage_entered_is_running(self) -> None:
        log = "[2026-07-20T12:29:05.374Z] [Pipeline] { (Install new cluster)\n"
        result = parse_progress(log)
        stages = {s["name"]: s["status"] for s in result["stages"]}
        assert stages["Install new cluster"] == "running"
        assert result["current_stage"] == "Install new cluster"

    def test_entered_and_skipped_together(self) -> None:
        log = (
            "[2026-07-20T12:29:05.374Z] [Pipeline] { (Install new cluster)\n"
            '[2026-07-20T12:30:00.000Z] Stage "Setup BYOIDC" skipped due to when conditional\n'
            "[2026-07-20T12:31:00.000Z] [Pipeline] { (Generate Test Config File)\n"
        )
        result = parse_progress(log)
        stages = {s["name"]: s["status"] for s in result["stages"]}
        assert stages["Install new cluster"] == "done"
        assert stages["Setup BYOIDC"] == "skipped"
        assert stages["Generate Test Config File"] == "running"

    def test_empty_log(self) -> None:
        result = parse_progress("")
        assert result["cluster_state"] == ""
        assert result["current_stage"] == ""
        assert all(s["status"] == "pending" for s in result["stages"])


class TestFormatProgress:
    def test_shows_build_number_and_stages(self) -> None:
        progress = {
            "stages": [
                {"name": "Install new cluster", "status": "done"},
                {"name": "Setup BYOIDC", "status": "skipped"},
                {"name": "Generate Test Config File", "status": "running"},
                {"name": "Deploy RHOAI operator", "status": "pending"},
            ],
            "cluster_state": "ready",
            "current_stage": "Generate Test Config File",
            "first_ts": "2026-07-20T12:29:05",
            "last_ts": "2026-07-20T13:16:59",
        }
        output = format_progress(progress, 13972, None)
        assert "Build #13972: IN PROGRESS" in output
        assert "elapsed" in output
        assert "Cluster: ready" in output
        assert "[x] Install new cluster" in output
        assert "[-] Setup BYOIDC" in output
        assert "[>] Generate Test Config File" in output
        assert "[ ] Deploy RHOAI operator" in output

    def test_shows_result_when_finished(self) -> None:
        progress = {
            "stages": [{"name": "Install new cluster", "status": "done"}],
            "cluster_state": "",
            "current_stage": "",
            "first_ts": "2026-07-20T12:00:00",
            "last_ts": "2026-07-20T12:05:00",
        }
        output = format_progress(progress, 100, "SUCCESS")
        assert "Build #100: SUCCESS" in output

    def test_no_timestamps_omits_elapsed(self) -> None:
        progress = {
            "stages": [{"name": "Install new cluster", "status": "pending"}],
            "cluster_state": "",
            "current_stage": "",
            "first_ts": "",
            "last_ts": "",
        }
        output = format_progress(progress, 100, None)
        assert "elapsed" not in output
        assert "Build #100: IN PROGRESS" in output

    def test_no_cluster_state_omits_line(self) -> None:
        progress = {
            "stages": [{"name": "Install new cluster", "status": "running"}],
            "cluster_state": "",
            "current_stage": "Install new cluster",
            "first_ts": "",
            "last_ts": "",
        }
        output = format_progress(progress, 100, None)
        assert "Cluster:" not in output


class TestShowProgress:
    @patch("main._fetch_text")
    @patch("main.get_build_status")
    def test_prints_progress_and_log_tail(
        self,
        mock_status: MagicMock,
        mock_fetch: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        mock_status.return_value = {"result": None}
        log_lines = [f"log line {i}" for i in range(20)]
        mock_fetch.return_value = "\n".join(log_lines)

        show_progress("https://ci", "devops/job", 100, "me", "tok")

        output = capsys.readouterr().out
        assert "Build #100: IN PROGRESS" in output
        assert f"--- Last {LOG_TAIL_LINES} log lines ---" in output
        assert "log line 19" in output
        assert "log line 5" in output
        assert "log line 4" not in output

    @patch("main._fetch_text")
    @patch("main.get_build_status")
    def test_shows_result_when_finished(
        self,
        mock_status: MagicMock,
        mock_fetch: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        mock_status.return_value = {"result": "SUCCESS"}
        mock_fetch.return_value = "[2026-07-20T12:00:00.000Z] done\n"

        show_progress("https://ci", "devops/job", 100, "me", "tok")

        output = capsys.readouterr().out
        assert "Build #100: SUCCESS" in output

    @patch("main._fetch_text")
    @patch("main.get_build_status")
    def test_short_log_shows_all_lines(
        self,
        mock_status: MagicMock,
        mock_fetch: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        mock_status.return_value = {"result": None}
        mock_fetch.return_value = "line 1\nline 2\nline 3"

        show_progress("https://ci", "devops/job", 100, "me", "tok")

        output = capsys.readouterr().out
        assert "--- Last 3 log lines ---" in output
        assert "line 1" in output
        assert "line 3" in output


class TestFetchText:
    @patch("main.urllib.request.urlopen")
    def test_returns_decoded_text(self, mock_urlopen: MagicMock) -> None:
        mock_resp = MagicMock()
        mock_resp.read.return_value = b"hello world"
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        result = _fetch_text("https://ci/log", "me", "tok")
        assert result == "hello world"


class TestDefaultParams:
    def test_required_params_present(self) -> None:
        required = ["PRODUCT", "CLUSTER_TYPE", "TEST_ENVIRONMENT", "COMPONENT_NAMES"]
        for param in required:
            assert param in DEFAULT_PARAMS, f"Missing required param: {param}"

    def test_password_params_present(self) -> None:
        assert "EXTERNAL_IDP_PASSWORD" in DEFAULT_PARAMS
        assert "OCM_CUSTOM_TOKEN" in DEFAULT_PARAMS


@pytest.fixture(autouse=True)
def _set_jenkins_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JENKINS_URL", "https://ci")
    monkeypatch.setenv("JOB_PATH", "devops/rhoai-test-flow")
    import main

    monkeypatch.setattr(main, "JENKINS_URL", "https://ci")
    monkeypatch.setattr(main, "JOB_PATH", "devops/rhoai-test-flow")


class TestMain:
    @patch("main.trigger_build")
    def test_dry_run_does_not_trigger(self, mock_trigger: MagicMock) -> None:
        main(["--user", "me", "--token", "secret", "--cluster-name", "c1", "--dry-run"])
        mock_trigger.assert_not_called()

    @patch("main.trigger_build", return_value="https://ci/queue/item/1/")
    def test_triggers_build(self, mock_trigger: MagicMock) -> None:
        main(["--user", "me", "--token", "secret", "--cluster-name", "my-cluster"])
        mock_trigger.assert_called_once()
        kwargs = mock_trigger.call_args[1]
        assert kwargs["params"]["CLUSTER_NAME"] == "my-cluster"

    @patch("main.trigger_build", return_value="https://ci/queue/item/1/")
    def test_custom_cluster_name(self, mock_trigger: MagicMock) -> None:
        main(["--user", "me", "--token", "secret", "--cluster-name", "custom-99"])
        kwargs = mock_trigger.call_args[1]
        assert kwargs["params"]["CLUSTER_NAME"] == "custom-99"

    def test_requires_cluster_name_for_trigger(self) -> None:
        with pytest.raises(SystemExit, match="2"):
            main(["--user", "me", "--token", "secret"])

    @patch("main.trigger_build")
    def test_raises_on_error(self, mock_trigger: MagicMock) -> None:
        mock_trigger.side_effect = urllib.error.HTTPError(
            "https://ci",
            403,
            "Forbidden",
            {},
            None,  # type: ignore[arg-type]
        )
        with pytest.raises(urllib.error.HTTPError):
            main(["--user", "me", "--token", "secret", "--cluster-name", "c1"])

    @patch("main.trigger_build", return_value="https://ci/queue/item/1/")
    def test_all_default_params_in_trigger(self, mock_trigger: MagicMock) -> None:
        main(["--user", "me", "--token", "secret", "--cluster-name", "test-cluster"])
        kwargs = mock_trigger.call_args[1]
        for key in DEFAULT_PARAMS:
            assert key in kwargs["params"], f"{key} missing from params"

    @patch("main.watch_build", return_value="SUCCESS")
    @patch("main.wait_for_build_number", return_value=500)
    @patch("main.trigger_build", return_value="https://ci/queue/item/1/")
    def test_watch_polls_until_done(
        self,
        mock_trigger: MagicMock,
        mock_wait: MagicMock,
        mock_watch: MagicMock,
    ) -> None:
        main(["--user", "me", "--token", "secret", "--cluster-name", "c1", "--watch"])
        mock_wait.assert_called_once_with("https://ci/queue/item/1/", "me", "secret")
        mock_watch.assert_called_once()

    @patch("main.watch_build", return_value="FAILURE")
    @patch("main.wait_for_build_number", return_value=500)
    @patch("main.trigger_build", return_value="https://ci/queue/item/1/")
    def test_watch_exits_nonzero_on_failure(
        self,
        _mock_trigger: MagicMock,
        _mock_wait: MagicMock,
        _mock_watch: MagicMock,
    ) -> None:
        with pytest.raises(SystemExit, match="1"):
            main(
                ["--user", "me", "--token", "secret", "--cluster-name", "c1", "--watch"]
            )

    @patch("main.get_build_status")
    def test_status_flag(self, mock_status: MagicMock) -> None:
        mock_status.return_value = {"result": "SUCCESS", "duration": 120000}
        main(["--user", "me", "--token", "secret", "--status", "100"])
        mock_status.assert_called_once()

    @patch("main.get_build_status")
    def test_status_in_progress(
        self, mock_status: MagicMock, capsys: pytest.CaptureFixture[str]
    ) -> None:
        mock_status.return_value = {
            "result": None,
            "building": True,
            "estimatedDuration": 180000,
            "duration": 0,
        }
        main(["--user", "me", "--token", "secret", "--status", "100"])
        output = capsys.readouterr().out
        assert "IN PROGRESS" in output
        assert "Est. duration" in output
        assert "3m 0s" in output

    @patch("main.get_build_status")
    def test_status_exits_nonzero_on_failure(self, mock_status: MagicMock) -> None:
        mock_status.return_value = {"result": "FAILURE", "duration": 60000}
        with pytest.raises(SystemExit, match="1"):
            main(["--user", "me", "--token", "secret", "--status", "100"])

    @patch("main.follow_log")
    def test_follow_flag(self, mock_follow: MagicMock) -> None:
        main(["--user", "me", "--token", "secret", "--follow", "200"])
        mock_follow.assert_called_once_with(
            "https://ci", "devops/rhoai-test-flow", 200, "me", "secret", interval=60
        )

    @patch("main.follow_log")
    def test_follow_custom_interval(self, mock_follow: MagicMock) -> None:
        main(
            [
                "--user",
                "me",
                "--token",
                "secret",
                "--follow",
                "200",
                "--interval",
                "30",
            ]
        )
        mock_follow.assert_called_once_with(
            "https://ci", "devops/rhoai-test-flow", 200, "me", "secret", interval=30
        )

    @patch("main.show_progress")
    def test_progress_flag(self, mock_progress: MagicMock) -> None:
        main(["--user", "me", "--token", "secret", "--progress", "300"])
        mock_progress.assert_called_once_with(
            "https://ci", "devops/rhoai-test-flow", 300, "me", "secret"
        )
