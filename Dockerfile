ARG NVIDIA_SMI_VERSION=550.144.03-1
ARG API_CLIENT_TAG=TS-25.04.2.4

FROM debian:bookworm as builder
ARG API_CLIENT_TAG

# Fail fast on errors or unset variables
SHELL ["/bin/bash", "-eux", "-o", "pipefail", "-c"]

RUN <<EOF
  apt-get -q update
  apt-get install -qy --no-install-recommends curl gpg git python3-wheel python3-build python3-venv pip ca-certificates
  curl -fSsL https://developer.download.nvidia.com/compute/cuda/repos/debian12/x86_64/3bf863cc.pub \
    | gpg --dearmor \
    | tee /usr/share/keyrings/nvidia-drivers.gpg > /dev/null 2>&1
  echo 'deb [signed-by=/usr/share/keyrings/nvidia-drivers.gpg] https://developer.download.nvidia.com/compute/cuda/repos/debian12/x86_64/ /' \
    | tee /etc/apt/sources.list.d/nvidia-drivers.list
EOF

WORKDIR /truenas_api_client

RUN pip wheel "truenas_api_client@git+https://github.com/truenas/api_client.git@${API_CLIENT_TAG}"

FROM debian:bookworm
ARG NVIDIA_SMI_VERSION

ENV DEBIAN_FRONTEND=noninteractive PIP_PREFER_BINARY=1

RUN apt-get -q update && apt-get install -qy ca-certificates

COPY --from=builder /usr/share/keyrings/nvidia-drivers.gpg /usr/share/keyrings/nvidia-drivers.gpg
COPY --from=builder /etc/apt/sources.list.d/nvidia-drivers.list /etc/apt/sources.list.d/nvidia-drivers.list

RUN <<EOF
    sed -i -e's/ main/ main contrib non-free/g' /etc/apt/sources.list.d/debian.sources
    apt-get -q update
    apt-get -qy dist-upgrade
    apt-get install --no-install-recommends -y \
        ipython3 vim rsync \
        python3 python3-venv pip \
        liquidctl \
        python3-prctl \
        ipmitool \
        nvidia-alternative=${NVIDIA_SMI_VERSION} libnvidia-ml1=${NVIDIA_SMI_VERSION} nvidia-smi=${NVIDIA_SMI_VERSION}
EOF

RUN <<EOF
    apt-get clean
    rm -rf /var/lib/apt/lists
EOF

WORKDIR /spinpid

ENV VIRTUAL_ENV=/spindpid/venv

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
