ARG NVIDIA_SMI_VERSION=545.23.08-1
ARG MIDDLEWARED_TAG=TS-24.04.1.1

FROM debian:bookworm as builder
ARG MIDDLEWARED_TAG

# Fail fast on errors or unset variables
SHELL ["/bin/bash", "-eux", "-o", "pipefail", "-c"]

RUN <<EOF
  apt-get -q update
  apt-get install -qy --no-install-recommends curl gpg git python3-wheel python3-build python3-venv ca-certificates
  curl -fSsL https://developer.download.nvidia.com/compute/cuda/repos/debian12/x86_64/3bf863cc.pub \
    | gpg --dearmor \
    | tee /usr/share/keyrings/nvidia-drivers.gpg > /dev/null 2>&1
  echo 'deb [signed-by=/usr/share/keyrings/nvidia-drivers.gpg] https://developer.download.nvidia.com/compute/cuda/repos/debian12/x86_64/ /' \
    | tee /etc/apt/sources.list.d/nvidia-drivers.list
EOF

ENV MIDDLEWARED_ROOT=/middlewared

RUN git clone https://github.com/truenas/middleware/ --depth 1 --branch ${MIDDLEWARED_TAG} ${MIDDLEWARED_ROOT}

WORKDIR ${MIDDLEWARED_ROOT}/src/middlewared

RUN <<EOF
    mv setup_client.py setup.py
    python3 -m build --wheel
EOF

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

COPY --from=builder /middlewared/src/middlewared/dist/middlewared.client-*.whl /middlewared/
RUN ls -l /middlewared/ && pip install /middlewared/middlewared.client-*.whl && rm -r /middlewared/


COPY requirements-middleware.txt .
RUN pip install -r requirements-middleware.txt


COPY requirements.txt .
# don't run liquidctl through pip, otherwise it will try to build smbus which fails
RUN sed -i -e's/liquidctl/# $0/' requirements.txt
RUN pip install -r requirements.txt

COPY . .

ENV PYTHONPATH="${PYTHONPATH}:${PWD}" EXTRA_ARGS=""

CMD ./spinpid.sh ${EXTRA_ARGS}
