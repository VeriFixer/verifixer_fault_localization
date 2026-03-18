# Dockerfile - Fully self-contained Ubuntu 22.04 image
FROM ubuntu:24.04

# Avoid interactive prompts
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
WORKDIR /app

# --- Install system dependencies ---
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl wget sudo make build-essential unzip zip python3 python3-pip python3-venv \
    libicu-dev tzdata ca-certificates git openssh-client && \
    rm -rf /var/lib/apt/lists/*

# --- Install z3 
# Build and install using some version of vscode extension ships with
# Note that also it ships with two this and 4.12.1
ARG Z3_VERSION="4.12.1"
ENV Z3_VERSION=${Z3_VERSION}

RUN set -eux; \
    url="https://github.com/Z3Prover/z3/releases/download/z3-${Z3_VERSION}/z3-${Z3_VERSION}-x64-glibc-2.35.zip"; \
    echo "Downloading Z3 from $url"; \
    curl -L -o z3-${Z3_VERSION}.zip "$url"; \
    unzip z3-${Z3_VERSION}.zip; \
    # Determine the extracted folder (likely something like z3-${Z3_VERSION}-x64-glibc-2.35) \
    dir="$(unzip -Z -1 z3-${Z3_VERSION}.zip | head -n1 | cut -d/ -f1)"; \
    echo "Installing Z3 from folder: $dir"; \
    cp -a "$dir"/bin/* /usr/local/bin/; \
    cp -a "$dir"/include/* /usr/local/include/ 2>/dev/null || true; \
    ldconfig; \
    # If python bindings present, install them
    rm -rf /app/z3-${Z3_VERSION}.zip /app/"$dir"

# --- Install .NET SDK 8.0 ---
RUN wget https://dot.net/v1/dotnet-install.sh -O /tmp/dotnet-install.sh && \
    chmod +x /tmp/dotnet-install.sh && \
    /tmp/dotnet-install.sh --channel 8.0 --install-dir /usr/share/dotnet && \
    ln -s /usr/share/dotnet/dotnet /usr/bin/dotnet

#ENV DOTNET_CLI_HOME=/tmp
#ENV HOME=/tmp

# Install OpenJDK for Java/Gradle builds
RUN apt-get update && apt-get install -y openjdk-17-jdk && \
    rm -rf /var/lib/apt/lists/*

ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
ENV PATH="$JAVA_HOME/bin:$PATH"

ENV DAFNY_VERSION=v4.11.0




# --- Build Dafny version v4.11.0 (it is not a fork)


COPY dafnybench /app/dafnybench/
COPY mutdafny /app/mutdafny/
COPY datasets /app/datasets/

ARG DAFNY_VERSION=v4.11.0

COPY .git /app/.git
COPY dafny /app/dafny/

RUN cd dafny && \
    git fetch --depth 1 origin ${DAFNY_VERSION} && \
    git checkout ${DAFNY_VERSION} && \
    make && \
    ln -sf /app/dafny/Binaries/Dafny /usr/local/bin/dafny

# For now i am using a submodule but can change ideas
#RUN git clone --depth 1 --branch ${DAFNY_VERSION} \
#    https://github.com/dafny-lang/dafny.git dafny &&\
#    cd dafny && \
#    make && \
#    ln -s dafny/Binaries/Dafny /usr/local/bin/dafny

COPY src /app/src 

# --- Python virtual environment ---
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

RUN pip install --upgrade pip && \
    pip install -r /app/src/requirements.txt

COPY .repo_verifixer_fault_localizaion_marker /app/
COPY strategies /app/strategies
# --- Build all dotnet strategies ---
RUN for dir in strategies/*/; do \
        if [ -d "$dir" ]; then \
            dotnet build "$dir" -c Release -o /app/build_output/$(basename "$dir"); \
        fi; \
    done

CMD ["bash"]

