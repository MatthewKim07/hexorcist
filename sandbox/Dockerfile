# Sandbox image: arduino-cli + arduino:avr + simavr + hexharness.
# Everything is fetched at build time because the runtime has no network.
# Builds natively on linux/arm64 and linux/amd64.

FROM debian:bookworm-slim AS simavr
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential ca-certificates git pkg-config \
        gcc-avr avr-libc libelf-dev libcjson-dev \
    && rm -rf /var/lib/apt/lists/*
ARG SIMAVR_REF=v1.7
RUN git clone --depth 1 --branch "${SIMAVR_REF}" https://github.com/buserror/simavr.git /src/simavr \
    && make -C /src/simavr/simavr RELEASE=1 libsimavr \
    && make -C /src/simavr/simavr RELEASE=1 install DESTDIR=/usr/local
COPY harness/hexharness.c /src/harness/hexharness.c
RUN gcc -O2 -std=gnu11 -Wall -Wextra -I/usr/local/include \
        -o /usr/local/bin/hexharness /src/harness/hexharness.c \
        /usr/local/lib/libsimavr.a -lelf -lcjson -lm -lpthread

FROM debian:bookworm-slim AS arduino
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*
ARG ARDUINO_CLI_VERSION=1.1.1
ARG ARDUINO_AVR_VERSION=1.8.6
COPY arduino-cli.yaml /etc/arduino-cli.yaml
RUN curl -fsSL https://raw.githubusercontent.com/arduino/arduino-cli/v${ARDUINO_CLI_VERSION}/install.sh \
        | BINDIR=/usr/local/bin sh -s "${ARDUINO_CLI_VERSION}" \
    && arduino-cli --config-file /etc/arduino-cli.yaml core update-index \
    && arduino-cli --config-file /etc/arduino-cli.yaml core install "arduino:avr@${ARDUINO_AVR_VERSION}" \
    && arduino-cli --config-file /etc/arduino-cli.yaml lib install Servo \
    && rm -rf /opt/arduino/downloads \
    && mkdir -p /opt/arduino/downloads

FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates jq libelf1 libcjson1 \
    && rm -rf /var/lib/apt/lists/*
COPY --from=simavr /usr/local/bin/hexharness /usr/local/bin/hexharness
COPY --from=simavr /usr/local/lib/libsimavr.a /usr/local/lib/libsimavr.a
COPY --from=simavr /usr/local/include/simavr /usr/local/include/simavr
COPY --from=arduino /usr/local/bin/arduino-cli /usr/local/bin/arduino-cli
COPY --from=arduino /opt/arduino /opt/arduino
COPY arduino-cli.yaml /etc/arduino-cli.yaml
COPY entry.sh /usr/local/bin/sandbox-entry
RUN chmod 0555 /usr/local/bin/sandbox-entry \
    && useradd --uid 1000 --no-create-home --home-dir /work --shell /usr/sbin/nologin hex \
    && chmod -R a+rX /opt/arduino \
    && mkdir -p /work && chown hex:hex /work
USER 1000:1000
WORKDIR /work
ENTRYPOINT ["/usr/local/bin/sandbox-entry"]
