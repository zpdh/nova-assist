# Disposable test environment for the hardware-free Nova test suite.
#
# Runs the unit tests in a clean image with no GPU, microphone, or whisper.cpp
# build present. Integration tests are excluded (see the -m "not integration").
#
#   podman build -f containers/test.Containerfile -t nova-test .
#   podman run --rm nova-test
FROM registry.fedoraproject.org/fedora:44

RUN dnf install -y python3 python3-pip && dnf clean all

WORKDIR /app

# Install project + dev extras first for cache friendliness, then run tests.
COPY pyproject.toml README.md ./
COPY src ./src
COPY tests ./tests
COPY config.toml ./

RUN python3 -m pip install --no-cache-dir -e ".[dev]"

CMD ["python3", "-m", "pytest", "-q", "-m", "not integration"]
