# syntax=docker/dockerfile:1.6
ARG BASE_IMAGE=ubuntu:focal
ARG BASE_RUNTIME_IMAGE=${BASE_IMAGE}

FROM ${BASE_IMAGE} AS python-env

ARG DEBIAN_FRONTEND=noninteractive
ARG PYENV_VERSION=v2.3.29
ARG PYTHON_VERSION=3.11.6

RUN <<EOF
    set -eu

    apt-get update

    apt-get install -y \
        make \
        build-essential \
        libssl-dev \
        zlib1g-dev \
        libbz2-dev \
        libreadline-dev \
        libsqlite3-dev \
        wget \
        curl \
        llvm \
        libncursesw5-dev \
        xz-utils \
        tk-dev \
        libxml2-dev \
        libxmlsec1-dev \
        libffi-dev \
        liblzma-dev \
        git

    apt-get clean
    rm -rf /var/lib/apt/lists/*
EOF

RUN <<EOF
    set -eu

    git clone https://github.com/pyenv/pyenv.git /opt/pyenv
    cd /opt/pyenv
    git checkout "${PYENV_VERSION}"

    PREFIX=/opt/python-build /opt/pyenv/plugins/python-build/install.sh
    /opt/python-build/bin/python-build -v "${PYTHON_VERSION}" /opt/python

    rm -rf /opt/python-build /opt/pyenv
EOF


FROM ${BASE_RUNTIME_IMAGE} AS runtime-env

ARG DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PATH=/home/user/.local/bin:/opt/python/bin:${PATH}

RUN <<EOF
    set -eu

    apt-get update
    apt-get install -y \
        gosu \
        ffmpeg
    apt-get clean
    rm -rf /var/lib/apt/lists/*
EOF

RUN <<EOF
    groupadd --non-unique --gid 1000 user
    useradd --non-unique --uid 1000 --gid 1000 --create-home user
EOF

COPY --from=python-env /opt/python /opt/python

ADD requirements.txt /
RUN gosu user pip3 install -r /requirements.txt

ADD --chown=user:user pyproject.toml README.md /opt/aoirint_matvtool/
ADD --chown=user:user aoirint_matvtool /opt/aoirint_matvtool/aoirint_matvtool

RUN <<EOF
    set -eu

    cd /opt/aoirint_matvtool
    gosu user pip3 install .
EOF

WORKDIR /work
ENTRYPOINT [ "gosu", "user", "matvtool" ]
