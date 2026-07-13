FROM python:3.11-slim

WORKDIR /app

# TA-Lib's Python wrapper (requirements.txt) links against the compiled
# TA-Lib C library, which python:3.11-slim's apt repos don't carry. This is
# a locked stack decision (docs/CLAUDE.md section 4: "TA-Lib ... do not
# deviate without asking"), not something to swap out for a lighter
# dependency.
#
# Installed from TA-Lib's official prebuilt .deb (arch-detected) rather
# than compiled from source: source-building the old 0.4.0 sourceforge
# tarball fails on Debian trixie's gcc 14 (C23 makes an ABI mismatch in the
# generated Cython wrapper a hard compile error, not just a warning) — the
# actively maintained TA-Lib/ta-lib GitHub project ships prebuilt .deb
# packages for exactly this reason.
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        ca-certificates \
    && ARCH="$(dpkg --print-architecture)" \
    && curl -sSL "https://github.com/TA-Lib/ta-lib/releases/download/v0.7.1/ta-lib_0.7.1_${ARCH}.deb" -o /tmp/ta-lib.deb \
    && dpkg -i /tmp/ta-lib.deb \
    && rm -f /tmp/ta-lib.deb \
    && apt-get purge -y curl \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 8000
