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
This repository includes a ready-to-use Dockerfile that installs .NET, Z3, Python deps and builds the Dafny + Laurel tools.


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
  -v "$(pwd)/src:/app/src:delegated" \
  -v "$(pwd)/DafnyTestGen:/app/DafnyTestGen:delegated" \
  -v "$(pwd)/mutdafny:/app/mutdafny:delegated" \
  -v "$(pwd)/datasets:/app/datasets:delegated" \
  -v "$(pwd)/strategies:/app/strategies:delegated" \
  -w /app \
  dafny_research:latest bash
```
# Inside the container 
Once inside the contaner follow the main README, README.md
