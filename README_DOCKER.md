# Docker Quickstart 

This file helps anyone (including anonymous reviewers) set up and use the Docker environment for this project. It is intentionally separate from the project README and only covers Docker commands, common fixes and sharing the final image.

# Install e enable Docker
https://docs.docker.com/engine/install/

# Use a premade docker image
Load with
```shell
docker load -i dafny_research_latest.tar
docker run --rm -it -w /app dafny_research:latest bash
```
Image previous saved with:
```shell
docker save -o dafny_research_latest.tar dafny_research:latest
```

# Build the docker image (from reporoot)
This repository includes a ready-to-use Dockerfile that installs .NET, Z3, Python deps and builds all tools.


```shell
DOCKER_BUILDKIT=1 docker build -t dafny_research:latest .
```

```shell
docker build -t dafny_research:latest .
```

# Run the interactive container 
```shell
docker run --rm -it -w /app  dafny_research:latest bash
```
```shell
docker run --rm -it \
  -u $(id -u):$(id -g) \
  -e PYTHONPATH=/app/src \
  -e FL_LOG_LEVEL=INFO \
  -e PYTEST_ADDOPTS='-o cache_dir=/tmp/pytest_cache' \
  -v "$(pwd)/src:/app/src:delegated" \
  -v "$(pwd)/run_artifacts:/app/run_artifacts:delegated" \
  -v "$(pwd)/Dafny-AutoFix:/app/Dafny-AutoFix:delegated" \
  -v "$(pwd)/run_artifacts:/app/run_artifacts:delegated" \
  -v "$(pwd)/DafnyTestGen:/app/DafnyTestGen:delegated" \
  -v "$(pwd)/mutdafny:/app/mutdafny:delegated" \
  -v "$(pwd)/datasets:/app/datasets:delegated" \
  -v "$(pwd)/strategies:/app/strategies:delegated" \
  -w /app \
  dafny_research:latest bash
```
# Inside the container 
Once inside the contaner follow the main README, README.md

# Logging Configuration

Control logging output inside the container with `FL_LOG_LEVEL` environment variable:

```shell
# Verbose debugging (shows all messages)
docker run ... -e FL_LOG_LEVEL=DEBUG ... 

# Info level (default, shows info/warning/error)
docker run ... -e FL_LOG_LEVEL=INFO ...

# Errors only
docker run ... -e FL_LOG_LEVEL=ERROR ...

# Save logs to file (optional)
docker run ... -e FL_LOG_FILE=/app/run.log ...
```

# Non-interactive test pipeline commands (inside container)

Install test dependency and run Python unit tests:

```shell
python -m pip install pytest
pytest -q
```

Run static type checking (same class of issues surfaced by Pylance):

```shell
python -m pip install pyright
pyright src
```

Run complete repository health check:

```shell
python src/run_repo_health_check.py --clean-cache
```

Run infrastructure safeguard with full `pos_test`:

```shell
python src/run_pos_test_guard.py --dataset-tar datasets/pos_test.tar.gz --clean-cache
```
