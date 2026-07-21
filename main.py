import argparse
import base64
import json
import os
import re
import ssl
import sys
import time
import urllib.parse
import urllib.request

JENKINS_URL = os.environ.get("JENKINS_URL", "")
JOB_PATH = os.environ.get("JOB_PATH", "")
POLL_INTERVAL = 30
FOLLOW_INTERVAL = 60

DEFAULT_PARAMS: dict[str, str] = {
    "PRODUCT": "RHODS",
    "CLUSTER_TYPE": "managed",
    "TEST_ENVIRONMENT": "AWS",
    "TEST_PLATFORM": "stage",
    "AKS_RESOURCE_GROUP": "",
    "AKS_CLUSTER_USERS": "",
    "CLUSTER_SOURCE": "internal",
    "OIDC_PROVIDER": "",
    "EXTERNAL_AUTH_METHOD": "",
    "EXTERNAL_KUBECONFIG_FILE": "",
    "OCP_API_URL": "",
    "EXTERNAL_IDP_USERNAME": "",
    "EXTERNAL_IDP_PASSWORD": "",
    "OCM_CUSTOM_TOKEN": "",
    "XKS_KUBECONFIG_FILE": "",
    "INSTALL_CLUSTER": "True",
    "DEPROVISION_AFTER_INSTALL_FAILURE": "False",
    "CLUSTER_ARCHITECTURE": "amd64",
    "TEAM_NAME": os.environ.get("TEAM_NAME", ""),
    "SINGLE_NODE_OPENSHIFT": "",
    "TEST_CLUSTER_DETAILS": os.environ.get("TEST_CLUSTER_DETAILS", ""),
    "PSI_PARAMS": "",
    "ENABLE_FIPS_IN_CLUSTER": "False",
    "DEPLOY_EXTERNAL_DNS": "False",
    "CREATE_IDP": "True",
    "INSTALL_GPU": "false",
    "GPU_NODE_COUNT": "",
    "GPU_VENDOR": "",
    "GPU_FLAVOR": "",
    "ENABLE_RDMA": "",
    "DEPLOY_NFS": "False",
    "STORAGE_SIZE_NFS": "100G",
    "SETUP_BYOIDC": "none",
    "HIBERNATION_TIMEOUT": "",
    "CLUSTER_ACTION_POST_EXECUTION": "Retain Cluster Ready",
    "UNINSTALL_RHOAI": "False",
    "RHAII_CHART_REPO": "",
    "RHAII_VERSION_TAG": "",
    "RHAII_NAMESPACE": "",
    "RHAII_MIDSTREAM": "",
    "RHAII_VALUES_FILE": "",
    "USE_STAGE_ENV": "False",
    "DEPLOY_RHODS_OPERATOR": "True",
    "ENABLE_NEW_OBSERVABILITY_STACK": "False",
    "INSTALL_AUTHORINO_DEPENDENCY": "True",
    "KSERVE_RAW_DEPLOYMENT": "False",
    "RHODS_DEPLOYMENT_TYPE": "Cli",
    "RHOAI_NAMESPACES": "",
    "COMPONENT_NAMES": (
        "dashboard:Managed,aipipelines:Managed,ray:Managed,workbenches:Managed,"
        "kserve:Managed,kueue:Unmanaged,trustyai:Managed,trainingoperator:Removed,"
        "trainer:Managed,modelregistry:Managed,feastoperator:Managed,"
        "llamastackoperator:Removed,ogx:Managed,mlflowoperator:Managed,"
        "modelsasservice:Managed,sparkoperator:Removed,aigateway:Removed,"
        "batchgateway:Removed"
    ),
    "CUSTOM_MANIFEST": "",
    "TEST_REGISTRY": "-- None --",
    "ADD_ICSP": "True",
    "ODS_BUILD_URL": os.environ.get("ODS_BUILD_URL", ""),
    "UPDATE_CHANNEL": "beta",
    "RHOAI_VERSION": "",
    "UPGRADE_RHOAI": "False",
    "UPGRADE_TESTS": "",
    "UPGRADE_TO_VERSION": "",
    "UPGRADE_TO_UPDATE_CHANNEL": "fast",
    "UPGRADE_ODS_BUILD_URL": "",
    "RUN_TESTS": "False",
    "ODS_CI_RUN_SCRIPT_ARGS": "--extra-robot-args '-i Smoke -e deprecatedTest -e ExcludeOnRHOAI'",
    "RUN_DASHBOARD_TESTS": "",
    "REMOVE_MUST_GATHER_FLAGS": "False",
    "QUALITY_GATES": "-- None --",
    "COMPONENTS_TESTS_CONFIG": (
        "ai-pipelines,false,quay.io/opendatahub/ds-pipelines-tests:master,,main,@@@,"
        "codeflare-sdk,false,quay.io/opendatahub/codeflare-sdk-tests:latest,,main,@@@,"
        "customer-workflows,false,quay.io/workflow-validation/director:latest,,main,@@@,"
        "distributed-workloads,false,quay.io/opendatahub/distributed-workloads-tests:latest,,main,@@@,"
        "kuberay,false,quay.io/opendatahub/kuberay-tests:latest,,main,@@@,"
        "llama_stack,false,quay.io/opendatahub/opendatahub-tests:latest,,main,@@@,"
        "maas_billing,false,quay.io/opendatahub/opendatahub-tests:latest,,main,@@@,"
        "mlflow,false,quay.io/opendatahub/mlflow-tests:main,,main,@@@,"
        "model-catalog-upstream,false,quay.io/opendatahub/model-registry-testops:latest,,main,@@@,"
        "ai-safety,false,quay.io/opendatahub/opendatahub-tests:latest,,main,@@@,"
        "model-registry-upstream,false,quay.io/opendatahub/model-registry-testops:latest,,main,@@@,"
        "ai-hub,false,quay.io/opendatahub/opendatahub-tests:latest,,main,@@@,"
        "model-runtime,false,quay.io/opendatahub/opendatahub-tests:latest,,main,@@@,"
        "model-server,false,quay.io/opendatahub/opendatahub-tests:latest,,main,@@@,"
        "mr-async-job-upstream,false,quay.io/opendatahub/model-registry-testops:latest,,main,@@@,"
        "platform,false,quay.io/opendatahub/opendatahub-operator-e2e:main,,main,@@@,"
        "spark-operator,false,quay.io/opendatahub/opendatahub-operator-e2e:main,,main,@@@,"
        "trainer,false,quay.io/opendatahub/distributed-workloads-tests:latest,,main,@@@,"
        "workbench-images,false,quay.io/opendatahub/workbench-images-tests:latest,,main,@@@,"
        "workbenches,false,quay.io/opendatahub/opendatahub-tests:latest,,main,@@@,"
        "ogx,false,quay.io/opendatahub/opendatahub-tests:latest,,main,@@@,"
        "feast,false,quay.io/opendatahub/opendatahub-tests:latest,,main,@@@,"
        "ai-safety-evalhub,false,quay.io/opendatahub/opendatahub-tests:latest,,main,@@@,"
        "ai-safety-guardrails,false,quay.io/opendatahub/opendatahub-tests:latest,,main,@@@,"
        "ai-safety-lmeval,false,quay.io/opendatahub/opendatahub-tests:latest,,main,@@@,"
        "ai-safety-trustyai-operator,false,quay.io/opendatahub/opendatahub-tests:latest,,main,@@@,"
        "ai-safety-trustyai-service,false,quay.io/opendatahub/opendatahub-tests:latest,,main,@@@,"
        "pipelines-automl,false,quay.io/opendatahub/opendatahub-tests:latest,,main,@@@,"
        "pipelines-autorag,false,quay.io/opendatahub/opendatahub-tests:latest,,main"
    ),
    "JOB_TITLE": "",
    "PUBLISH_RESULTS_TO": os.environ.get("PUBLISH_RESULTS_TO", ""),
    "SEND_SLACK_NOTIFICATIONS": "False",
    "SLACK_CHANNEL_ID": "",
    "SLACK_THREAD_ID": "",
    "ARCHIVE_ARTIFACTS": "True",
    "UPDATE_REPORT_PORTAL": "False",
    "UPLOAD_TO_NEXUS": "False",
    "TFA_JIRA_ID": "",
    "REPORT_FAILED_TESTS_TO_JIRA": "False",
    "REPORT_SKIPPED_TESTS_TO_JIRA": "False",
    "ODS_CI_GIT_REPO": "https://github.com/red-hat-data-services/ods-ci.git",
    "ODS_CI_GIT_REPO_BRANCH": "master",
    "ODHCLUSTER_GIT_REPO": os.environ.get("ODHCLUSTER_GIT_REPO", ""),
    "ODHCLUSTER_GIT_REPO_BRANCH": "master",
    "ODS_INSTALL_GIT_REPO": os.environ.get("ODS_INSTALL_GIT_REPO", ""),
    "ODS_INSTALL_GIT_REPO_BRANCH": "master",
    "OLM_INSTALL_GIT_REPO": os.environ.get("OLM_INSTALL_GIT_REPO", ""),
    "OLM_INSTALL_GIT_REPO_BRANCH": "main",
    "ODS_CI_GIT_REPO_PREV_VERSION": "https://github.com/red-hat-data-services/ods-ci.git",
    "ODS_CI_GIT_REPO_BRANCH_PREV_VERSION": "master",
    "GITOPS_REPO_URL": "",
    "GITOPS_REPO_BRANCH": "",
}

_ssl_context = ssl.create_default_context()
_ssl_context.check_hostname = False
_ssl_context.verify_mode = ssl.CERT_NONE


def _auth_header(user: str, token: str) -> str:
    credentials = base64.b64encode(f"{user}:{token}".encode()).decode()
    return f"Basic {credentials}"


def _job_url(jenkins_url: str, job_path: str) -> str:
    parts = job_path.split("/")
    return jenkins_url + "/job/" + "/job/".join(parts)


def _api_get(url: str, user: str, token: str) -> dict:
    req = urllib.request.Request(url)
    req.add_header("Authorization", _auth_header(user, token))
    with urllib.request.urlopen(req, context=_ssl_context) as resp:
        return json.loads(resp.read())


def get_crumb(jenkins_url: str, user: str, token: str) -> dict[str, str]:
    url = f"{jenkins_url}/crumbIssuer/api/json"
    data = _api_get(url, user, token)
    return {data["crumbRequestField"]: data["crumb"]}


def build_url(jenkins_url: str, job_path: str) -> str:
    return _job_url(jenkins_url, job_path) + "/buildWithParameters"


def trigger_build(
    *,
    jenkins_url: str,
    job_path: str,
    user: str,
    token: str,
    params: dict[str, str],
) -> str:
    crumb = get_crumb(jenkins_url, user, token)
    url = build_url(jenkins_url, job_path)
    data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Authorization", _auth_header(user, token))
    for key, value in crumb.items():
        req.add_header(key, value)
    with urllib.request.urlopen(req, context=_ssl_context) as resp:
        return resp.headers["Location"]


def wait_for_build_number(
    queue_url: str, user: str, token: str, poll_interval: int = POLL_INTERVAL
) -> int:
    api_url = queue_url.rstrip("/") + "/api/json"
    while True:
        data = _api_get(api_url, user, token)
        executable = data.get("executable")
        if executable and "number" in executable:
            return executable["number"]
        if data.get("cancelled"):
            raise RuntimeError("Build was cancelled while queued")
        print("Waiting in queue...", flush=True)
        time.sleep(poll_interval)


def _fetch_text(url: str, user: str, token: str) -> str:
    req = urllib.request.Request(url)
    req.add_header("Authorization", _auth_header(user, token))
    with urllib.request.urlopen(req, context=_ssl_context) as resp:
        return resp.read().decode()


PIPELINE_STAGES = [
    "Install new cluster",
    "Setup BYOIDC",
    "Generate Test Config File",
    "Register Cluster in Lockable Resources",
    "RHOAI Operator Cleanup",
    "Deploy external DNS",
    "Add ICSP",
    "Create IDP",
    "Add OCP CatalogSource",
    "Setup Stage Environment",
    "Deploy RHOAI operator",
    "Cluster Verification - Cluster Health Check",
    "Build Verification - RHOAI Health Check",
    "Install GPU Operator",
    "Install RHAII on xKS",
    "Deploy NFS",
    "Set Hibernate Timeout",
    "Upgrade RHOAI Operator",
    "Execute RF tests",
    "Trigger Dynamic ShiftLeft Stages",
    "Trigger Dashboard Cypress Tests",
]

_RE_STAGE_ENTER = re.compile(r"\[Pipeline\] \{ \((.+?)\)")
_RE_STAGE_SKIP = re.compile(r'Stage "(.+?)" skipped')
_RE_CLUSTER_STATE = re.compile(r">: (validating|installing|ready|error|uninstalling)")
_RE_TIMESTAMP = re.compile(r"^\[(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})\.\d+Z\]")


def _parse_log_entries(
    log_text: str,
) -> tuple[set[str], set[str], str, str, str]:
    entered: set[str] = set()
    skipped: set[str] = set()
    cluster_state = ""
    first_ts = ""
    last_ts = ""

    for line in log_text.splitlines():
        ts_match = _RE_TIMESTAMP.match(line)
        if ts_match:
            ts = ts_match.group(1)
            if not first_ts:
                first_ts = ts
            last_ts = ts

        m = _RE_STAGE_ENTER.search(line)
        if m:
            entered.add(m.group(1))

        m = _RE_STAGE_SKIP.search(line)
        if m:
            skipped.add(m.group(1))

        m = _RE_CLUSTER_STATE.search(line)
        if m:
            cluster_state = m.group(1)

    return entered, skipped, cluster_state, first_ts, last_ts


def parse_progress(log_text: str) -> dict:
    entered, skipped, cluster_state, first_ts, last_ts = _parse_log_entries(log_text)

    stages: list[dict[str, str]] = []
    for name in PIPELINE_STAGES:
        if name in skipped:
            stages.append({"name": name, "status": "skipped"})
        elif name in entered:
            stages.append({"name": name, "status": "done"})
        else:
            stages.append({"name": name, "status": "pending"})

    current = ""
    for stage in reversed(stages):
        if stage["status"] == "done":
            current = stage["name"]
            stage["status"] = "running"
            break

    return {
        "stages": stages,
        "cluster_state": cluster_state,
        "current_stage": current,
        "first_ts": first_ts,
        "last_ts": last_ts,
    }


def format_progress(progress: dict, build_number: int, result: str | None) -> str:
    lines: list[str] = []

    elapsed = ""
    if progress["first_ts"] and progress["last_ts"]:
        fmt = "%Y-%m-%dT%H:%M:%S"
        t0 = time.strptime(progress["first_ts"], fmt)
        t1 = time.strptime(progress["last_ts"], fmt)
        delta_s = int(time.mktime(t1) - time.mktime(t0))
        elapsed = f"{delta_s // 60}m {delta_s % 60}s"

    status = result or "IN PROGRESS"
    header = f"Build #{build_number}: {status}"
    if elapsed:
        header += f" ({elapsed} elapsed)"
    lines.append(header)

    if progress["cluster_state"]:
        lines.append(f"  Cluster: {progress['cluster_state']}")

    lines.append("")
    for stage in progress["stages"]:
        if stage["status"] == "done":
            icon = "[x]"
        elif stage["status"] == "running":
            icon = "[>]"
        elif stage["status"] == "skipped":
            icon = "[-]"
        else:
            icon = "[ ]"
        lines.append(f"  {icon} {stage['name']}")

    return "\n".join(lines)


LOG_TAIL_LINES = 15


def show_progress(
    jenkins_url: str,
    job_path: str,
    build_number: int,
    user: str,
    token: str,
) -> None:
    build_data = get_build_status(jenkins_url, job_path, build_number, user, token)
    log_url = _job_url(jenkins_url, job_path) + f"/{build_number}/consoleText"
    log_text = _fetch_text(log_url, user, token)
    progress = parse_progress(log_text)
    print(format_progress(progress, build_number, build_data.get("result")))

    log_lines = log_text.rstrip("\n").splitlines()
    tail = log_lines[-LOG_TAIL_LINES:]
    print(f"\n  --- Last {len(tail)} log lines ---")
    for line in tail:
        print(f"  {line}")


def get_console_log(
    jenkins_url: str,
    job_path: str,
    build_number: int,
    user: str,
    token: str,
    start: int = 0,
) -> tuple[str, int, bool]:
    url = (
        _job_url(jenkins_url, job_path)
        + f"/{build_number}/logText/progressiveText?start={start}"
    )
    req = urllib.request.Request(url)
    req.add_header("Authorization", _auth_header(user, token))
    with urllib.request.urlopen(req, context=_ssl_context) as resp:
        text = resp.read().decode()
        new_start = int(resp.headers.get("X-Text-Size", start))
        more_data = resp.headers.get("X-More-Data", "false") == "true"
    return text, new_start, more_data


def follow_log(
    jenkins_url: str,
    job_path: str,
    build_number: int,
    user: str,
    token: str,
    interval: int = FOLLOW_INTERVAL,
) -> None:
    build_page = _job_url(jenkins_url, job_path) + f"/{build_number}/"
    print(f"Following build #{build_number}: {build_page}", flush=True)
    print("---", flush=True)
    start = 0
    while True:
        text, start, more_data = get_console_log(
            jenkins_url, job_path, build_number, user, token, start
        )
        if text:
            sys.stdout.write(text)
            if not text.endswith("\n"):
                sys.stdout.write("\n")
            sys.stdout.flush()
        if not more_data:
            break
        time.sleep(interval)


def get_build_status(
    jenkins_url: str, job_path: str, build_number: int, user: str, token: str
) -> dict:
    url = _job_url(jenkins_url, job_path) + f"/{build_number}/api/json"
    return _api_get(url, user, token)


def watch_build(
    jenkins_url: str,
    job_path: str,
    build_number: int,
    user: str,
    token: str,
    poll_interval: int = POLL_INTERVAL,
) -> str:
    build_page = _job_url(jenkins_url, job_path) + f"/{build_number}/"
    print(f"Build #{build_number}: {build_page}", flush=True)
    while True:
        data = get_build_status(jenkins_url, job_path, build_number, user, token)
        if data.get("result") is not None:
            return data["result"]
        duration_ms = data.get("duration", 0)
        estimated_ms = data.get("estimatedDuration", 0)
        if estimated_ms > 0 and duration_ms > 0:
            pct = min(int(duration_ms / estimated_ms * 100), 99)
            print(f"  Running... ~{pct}%", flush=True)
        else:
            print("  Running...", flush=True)
        time.sleep(poll_interval)


def _handle_status(
    jenkins_url: str, job_path: str, build_number: int, user: str, token: str
) -> None:
    data = get_build_status(jenkins_url, job_path, build_number, user, token)
    result = data.get("result") or "IN PROGRESS"
    building = data.get("building", False)
    duration_s = (
        data.get("estimatedDuration", 0) // 1000
        if building
        else data.get("duration", 0) // 1000
    )
    build_page = _job_url(jenkins_url, job_path) + f"/{build_number}/"
    duration_label = "Est. duration" if building else "Duration"
    print(f"Build #{build_number}: {result}")
    print(f"  {duration_label}: {duration_s // 60}m {duration_s % 60}s")
    print(f"  URL: {build_page}")
    if not building and result != "SUCCESS":
        sys.exit(1)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Trigger a Jenkins rhoai-test-flow build"
    )
    parser.add_argument("--user", default=os.environ.get("JENKINS_USER"))
    parser.add_argument("--token", default=os.environ.get("JENKINS_TOKEN"))
    parser.add_argument("--cluster-name")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the URL and params without executing",
    )
    parser.add_argument(
        "--status",
        type=int,
        metavar="BUILD_NUMBER",
        help="Check status of an existing build instead of triggering a new one",
    )
    parser.add_argument(
        "--watch",
        action="store_true",
        help="After triggering, poll until the build finishes",
    )
    parser.add_argument(
        "--progress",
        type=int,
        metavar="BUILD_NUMBER",
        help="Show a stage-by-stage progress summary for a build",
    )
    parser.add_argument(
        "--follow",
        type=int,
        metavar="BUILD_NUMBER",
        help="Stream console output of a build, polling every --interval seconds",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=FOLLOW_INTERVAL,
        help=f"Polling interval in seconds for --follow (default: {FOLLOW_INTERVAL})",
    )
    args = parser.parse_args(argv)

    if not args.user:
        parser.error("--user is required (or set JENKINS_USER env var)")
    if not args.token:
        parser.error("--token is required (or set JENKINS_TOKEN env var)")

    if args.status:
        _handle_status(JENKINS_URL, JOB_PATH, args.status, args.user, args.token)
        return

    if args.progress:
        show_progress(JENKINS_URL, JOB_PATH, args.progress, args.user, args.token)
        return

    if args.follow:
        follow_log(
            JENKINS_URL,
            JOB_PATH,
            args.follow,
            args.user,
            args.token,
            interval=args.interval,
        )
        return

    if not args.cluster_name:
        parser.error("--cluster-name is required when creating a cluster")

    params = {**DEFAULT_PARAMS, "CLUSTER_NAME": args.cluster_name}

    if args.dry_run:
        url = build_url(JENKINS_URL, JOB_PATH)
        print(f"POST {url}")
        for key, value in params.items():
            print(f"  {key}={value}")
        return

    queue_url = trigger_build(
        jenkins_url=JENKINS_URL,
        job_path=JOB_PATH,
        user=args.user,
        token=args.token,
        params=params,
    )
    print(f"Build queued: {queue_url}")

    if args.watch:
        build_number = wait_for_build_number(queue_url, args.user, args.token)
        result = watch_build(JENKINS_URL, JOB_PATH, build_number, args.user, args.token)
        print(f"Build #{build_number} finished: {result}")
        if result != "SUCCESS":
            sys.exit(1)


if __name__ == "__main__":
    main()
