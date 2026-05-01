ARG NVIDIA_SMI_VERSION=570.172.08
ARG API_CLIENT_TAG=TS-25.10.3.1

FROM debian:bookworm AS builder
ARG NVIDIA_SMI_VERSION
ARG API_CLIENT_TAG

# Fail fast on errors or unset variables
SHELL ["/bin/bash", "-eux", "-o", "pipefail", "-c"]

RUN <<EOF
  apt-get -q update
  apt-get install -qy --no-install-recommends curl git python3-wheel python3-build python3-venv pip
EOF

WORKDIR /truenas_api_client

RUN pip wheel "truenas_api_client@git+https://github.com/truenas/api_client.git@${API_CLIENT_TAG}"

WORKDIR /

RUN <<EOF
  curl -fSsL https://download.nvidia.com/XFree86/Linux-x86_64/${NVIDIA_SMI_VERSION}/NVIDIA-Linux-x86_64-${NVIDIA_SMI_VERSION}-no-compat32.run \
    | tee /nvidia-driver.run > /dev/null 2>&1
EOF

RUN sh /nvidia-driver.run --extract-only --target nvidia

FROM debian:bookworm
ARG NVIDIA_SMI_VERSION

SHELL ["/bin/bash", "-eux", "-o", "pipefail", "-c"]

ENV DEBIAN_FRONTEND=noninteractive PIP_PREFER_BINARY=1

COPY --from=builder /nvidia/libnvidia-ml.so.${NVIDIA_SMI_VERSION} /usr/lib/x86_64-linux-gnu/
COPY --from=builder /nvidia/nvidia-smi /usr/bin/nvidia-smi

RUN <<EOF
    sed -i -e's/ main/ main contrib non-free/g' /etc/apt/sources.list.d/debian.sources
    apt-get -q update
    apt-get -qy dist-upgrade
    apt-get install --no-install-recommends -y \
        ipython3 vim rsync \
        python3 python3-venv pip \
        liquidctl \
        python3-prctl \
        ipmitool
EOF

RUN <<EOF
    apt-get clean
    rm -rf /var/lib/apt/lists
EOF

WORKDIR /spinpid

ENV VIRTUAL_ENV=/spinpid/venv

# create virtual environment to manage packages
RUN python3 -m venv --system-site-packages ${VIRTUAL_ENV}

# run python and pip from venv
ENV PATH="${VIRTUAL_ENV}/bin:${PATH}"

COPY --from=builder /truenas_api_client/*.whl /truenas_api_client/
RUN ls -l /truenas_api_client/ && pip install /truenas_api_client/*.whl && rm -r /truenas_api_client/


COPY requirements.txt .
# don't run liquidctl through pip, otherwise it will try to build smbus which fails
RUN sed -i -e's/liquidctl/# $0/' requirements.txt
RUN pip install -r requirements.txt

COPY . .

ENV PYTHONPATH="${PYTHONPATH}:${PWD}" EXTRA_ARGS=""

CMD ./spinpid.sh ${EXTRA_ARGS}
