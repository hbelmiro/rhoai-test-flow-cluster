# rhoai-test-flow-cluster

Trigger and monitor Jenkins `rhoai-test-flow` builds to provision OpenShift clusters.

## Setup

```bash
uv sync --group dev
```

## Configuration

Set environment variables in your `.zshrc` (or equivalent):

```bash
export JENKINS_USER=your-user
export JENKINS_TOKEN=your-token
export JENKINS_URL=https://your-jenkins-server
export JOB_PATH=devops/rhoai-test-flow
export TEAM_NAME=your-team
export TEST_CLUSTER_DETAILS=...
export ODS_BUILD_URL=...
export PUBLISH_RESULTS_TO=...
export ODHCLUSTER_GIT_REPO=...
export ODS_INSTALL_GIT_REPO=...
export OLM_INSTALL_GIT_REPO=...
```

CLI arguments override environment variables.

## Usage

### Create a cluster

```bash
uv run python main.py --cluster-name <CLUSTER_NAME>
```

Create and wait until the build finishes:

```bash
uv run python main.py --cluster-name <CLUSTER_NAME> --watch
```

### Check cluster creation status

```bash
uv run python main.py --status <BUILD_NUMBER>
```

### Show build progress

Stage-by-stage summary with the last 15 log lines:

```bash
uv run python main.py --progress <BUILD_NUMBER>
```

### Stream console output

Streams the raw console log, polling every 60 seconds by default:

```bash
uv run python main.py --follow <BUILD_NUMBER>
```

Custom polling interval:

```bash
uv run python main.py --follow <BUILD_NUMBER> --interval 30
```

## Tests

```bash
uv run pytest
```

## Linting

```bash
uv run ruff check .
uv run ruff format --check .
```
