# syntax=docker/dockerfile:1.7
FROM ubuntu:24.04

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

ARG Z3_VERSION=4.12.1
ARG DAFNY_VERSION=v4.11.0
ARG DAFNY_REPO=https://github.com/dafny-lang/dafny.git

# Base packages, installed once
RUN --mount=type=cache,target=/var/cache/apt \
    --mount=type=cache,target=/var/lib/apt/lists \
    apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl wget sudo make build-essential unzip zip \
      python3 python3-pip python3-venv libicu-dev tzdata \
      git openssh-client openjdk-17-jdk ant rsync \
    && rm -rf /var/lib/apt/lists/*

# Z3 – pick the right binary for the build architecture
RUN set -eux; \
    ARCH=$(uname -m); \
    case "$ARCH" in \
        x86_64)  Z3_ARCH="x64-glibc-2.35" ;; \
        aarch64) Z3_ARCH="arm64-osx-11.0" ;; \
        *)       echo "Unsupported architecture: $ARCH"; exit 1 ;; \
    esac; \
    url="https://github.com/Z3Prover/z3/releases/download/z3-${Z3_VERSION}/z3-${Z3_VERSION}-${Z3_ARCH}.zip"; \
    curl -fsSL -o /tmp/z3.zip "$url"; \
    unzip /tmp/z3.zip -d /tmp/z3; \
    dir="$(find /tmp/z3 -maxdepth 1 -mindepth 1 -type d | head -n1)"; \
    cp -a "$dir"/bin/z3 /usr/local/bin/; \
    cp -a "$dir"/bin/libz3.so* /usr/local/lib/; \
    cp -a "$dir"/include/* /usr/local/include/ 2>/dev/null || true; \
    chmod 755 /usr/local/bin/z3; \
    ldconfig; \
    rm -rf /tmp/z3 /tmp/z3.zip

ENV LD_LIBRARY_PATH="/usr/local/lib:${LD_LIBRARY_PATH}"

# .NET SDK 8
RUN curl -fsSL https://dot.net/v1/dotnet-install.sh -o /tmp/dotnet-install.sh && \
    bash /tmp/dotnet-install.sh --channel 8.0 --install-dir /usr/share/dotnet && \
    ln -sfn /usr/share/dotnet/dotnet /usr/local/bin/dotnet && \
    rm -f /tmp/dotnet-install.sh

# Make JAVA_HOME architecture‑independent
RUN JAVA_ARCH=$(dpkg --print-architecture) && \
    ln -s "/usr/lib/jvm/java-17-openjdk-${JAVA_ARCH}" /usr/lib/jvm/default-java
ENV JAVA_HOME=/usr/lib/jvm/default-java

# Build Dafny from the repo you point at
RUN git clone --depth 1 --branch "${DAFNY_VERSION}" "${DAFNY_REPO}" /app/dafny && \
    make -C /app/dafny -j"$(nproc)" && \
    ln -sf /app/dafny/Binaries/Dafny /usr/local/bin/dafny

    # Daikon
ENV DAIKONDIR="/opt/daikon"
RUN git clone --depth 1 --branch master https://github.com/codespecs/daikon.git /tmp/daikon-src && \
    cd /tmp/daikon-src && \
    make -j"$(nproc)" daikon.jar && \
    mkdir -p "${DAIKONDIR}" && \
    cp daikon.jar "${DAIKONDIR}/" && \
    cp -r scripts "${DAIKONDIR}/" && \
    rm -rf /tmp/daikon-src
ENV PATH="${DAIKONDIR}:${PATH}"

# Python dependencies: copy only requirements first
COPY src/requirements.txt /app/src/requirements.txt
RUN python3 -m venv /opt/venv && \
    /opt/venv/bin/pip install --upgrade pip && \
    /opt/venv/bin/pip install -r /app/src/requirements.txt
ENV PATH="/opt/venv/bin:${PATH}"

# Now copy the rest of src
COPY src/ /app/src/

# Small marker file
COPY .repo_verifixer_fault_localization_marker /app/

# Build DafnyTestGen

# Build SpecTestGenerator
COPY SpecTestGenerator/ /app/SpecTestGenerator/
RUN make -C /app/SpecTestGenerator -j"$(nproc)"

COPY DafnyTestGen/ /app/DafnyTestGen/
RUN --mount=type=cache,target=/root/.nuget/packages \
    dotnet restore /app/DafnyTestGen/DafnyTestGen/DafnyTestGen.csproj && \
    dotnet build /app/DafnyTestGen/DafnyTestGen/DafnyTestGen.csproj \
      -c Release -o /app/build_output/DafnyTestGen --no-restore

# Build strategies
COPY strategies/ /app/strategies/
RUN --mount=type=cache,target=/root/.nuget/packages \
    find /app/strategies -name '*.csproj' -print0 | \
    while IFS= read -r -d '' csproj; do \
      dir="$(dirname "$csproj")"; \
      out="/app/build_output/$(basename "$dir")"; \
      dotnet restore "$csproj" && \
      dotnet build "$csproj" -c Release -o "$out" --no-restore; \
    done

# Build Autofix
COPY Dafny-AutoFix/ /app/Dafny-AutoFix/
RUN --mount=type=cache,target=/root/.nuget/packages \
    dotnet restore /app/Dafny-AutoFix/autofix && \
    dotnet build /app/Dafny-AutoFix/autofix -c Release -o /app/build_output/Autofix --no-restore

# Copy large runtime-only assets last
COPY dafnybench/ /app/dafnybench/
COPY mutdafny/ /app/mutdafny/
COPY datasets/ /app/datasets/

CMD ["bash"]
