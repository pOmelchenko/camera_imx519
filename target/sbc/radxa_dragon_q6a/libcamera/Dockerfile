FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential ca-certificates git meson ninja-build pkg-config patch \
    python3-jinja2 python3-yaml python3-ply openssl \
    libgnutls28-dev libyaml-dev libevent-dev libudev-dev \
    libegl1-mesa-dev libgles2-mesa-dev libyuv-dev libtiff-dev libjpeg-dev \
    libdrm-dev qt6-base-dev && rm -rf /var/lib/apt/lists/*
