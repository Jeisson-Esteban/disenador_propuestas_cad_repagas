# --- Stage 1: compilar libredwg (dwg2dxf + dxf2dwg) ---
FROM python:3.13-slim-bookworm AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    git build-essential autoconf automake libtool texinfo pkg-config \
    swig python3-dev \
    && rm -rf /var/lib/apt/lists/*

RUN git clone --depth 1 https://github.com/LibreDWG/libredwg.git /tmp/libredwg \
    && cd /tmp/libredwg \
    && sh autogen.sh \
    && ./configure --disable-shared --enable-static --disable-bindings \
    && make -j"$(nproc)"

# dxf2dwg en libredwg es un script perl (no un binario C). Instalamos ambos.
RUN cp /tmp/libredwg/programs/dwg2dxf /usr/local/bin/dwg2dxf \
    && cp /tmp/libredwg/programs/dxf2dwg /usr/local/bin/dxf2dwg \
    && chmod +x /usr/local/bin/dwg2dxf /usr/local/bin/dxf2dwg

# --- Stage 2: imagen final ---
FROM python:3.13-slim-bookworm

# perl es necesario porque dxf2dwg es un script perl
# fuentes DejaVu son necesarias para que ezdxf.addons.drawing renderice PNGs
# con textos (evita 'no fonts available, not even fallback fonts')
RUN apt-get update && apt-get install -y --no-install-recommends \
    perl \
    fonts-dejavu-core \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /usr/local/bin/dwg2dxf /usr/local/bin/dwg2dxf
COPY --from=builder /usr/local/bin/dxf2dwg /usr/local/bin/dxf2dwg

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

WORKDIR /app/server

EXPOSE 8000

CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
