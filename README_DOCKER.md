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
docker build -t dafny_research:latest .
```

# Run the interactive container 
```shell
docker run --rm -it -w /app  dafny_research:latest bash
```
You may need to pass sensitive infomation as the OPENAI\_API\_KEY to test with an actual LLM. To do that the best way is to pass at runtime.
```shell
docker run --rm -it \
  -e OPENAI_API_KEY="$OPENAI_API_KEY" \
  -w /app \
  dafny_research:latest bash
```
For developement run this to be able to change src folder from src
```shell    dafny_research:latest bash
docker run --rm -it \
  -v "$(pwd)/src:/app/src:delegated" \
  -e OPENAI_API_KEY="$OPENAI_API_KEY" \
  -w /app \
  dafny_research:latest bash
```
# Inside the container 
Once inside the contaner follow the main README, README.md
