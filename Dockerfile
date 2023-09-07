ARG NVIDIA_SMI_VERSION=515.65.01-1
ARG MIDDLEWARED_TAG=TS-22.12.3.3

FROM debian:bullseye as builder
ARG MIDDLEWARED_TAG

RUN apt-get -q update && \
    apt-get install -qy --no-install-recommends curl gpg git python3-wheel python3-build && \
    curl -fSsL https://developer.download.nvidia.com/compute/cuda/repos/debian11/x86_64/3bf863cc.pub \
    | gpg --dearmor \
    | tee /usr/share/keyrings/nvidia-drivers.gpg > /dev/null 2>&1 && \
    echo 'deb [signed-by=/usr/share/keyrings/nvidia-drivers.gpg] https://developer.download.nvidia.com/compute/cuda/repos/debian11/x86_64/ /' \
    | tee /etc/apt/sources.list.d/nvidia-drivers.list

ENV MIDDLEWARED_ROOT=/middlewared

RUN git clone https://github.com/truenas/middleware/ --depth 1 --branch ${MIDDLEWARED_TAG} ${MIDDLEWARED_ROOT}

WORKDIR ${MIDDLEWARED_ROOT}/src/middlewared

RUN \
    mv setup_client.py setup.py && \
    python3 -m build --wheel

FROM debian:bullseye
ARG NVIDIA_SMI_VERSION

ENV DEBIAN_FRONTEND=noninteractive PIP_PREFER_BINARY=1

RUN apt-get -q update && apt-get install -qy ca-certificates

COPY --from=builder /usr/share/keyrings/nvidia-drivers.gpg /usr/share/keyrings/nvidia-drivers.gpg
COPY --from=builder /etc/apt/sources.list.d/nvidia-drivers.list /etc/apt/sources.list.d/nvidia-drivers.list

RUN \
    sed -i -e's/ main/ main contrib non-free/g' /etc/apt/sources.list && \
    apt-get -q update && \
    apt-get -qy dist-upgrade && \
    apt-get install --no-install-recommends -y \
        ipython3 vim rsync \
        python pip \
        liquidctl \
        python3-prctl python3-ws4py python3-websocket \
        ipmitool \
        nvidia-alternative=${NVIDIA_SMI_VERSION} libnvidia-ml1=${NVIDIA_SMI_VERSION} nvidia-smi=${NVIDIA_SMI_VERSION}

RUN apt-get clean && rm -rf /var/lib/apt/lists

COPY --from=builder /middlewared/src/middlewared/dist/middlewared.client-*.whl /middlewared/
RUN ls -l /middlewared/ && pip install /middlewared/middlewared.client-*.whl && rm -r /middlewared/

WORKDIR /spinpid

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

ENV PYTHONPATH="${PYTHONPATH}:${PWD}" EXTRA_ARGS=""

CMD ./spinpid.sh ${EXTRA_ARGS}