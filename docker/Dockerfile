# syntax=docker/dockerfile:1

# ============================================================================
# DEDIH 2.0 CI/CD kurzus - demo Dockerfile
# ----------------------------------------------------------------------------
# A cél nem a "legkisebb lehetséges image", hanem hogy láthatóak legyenek a
# container build alapelvei:
#
#   1. multi-stage build:   a telepítéshez kellő eszközök nem kerülnek bele a
#                           kiszállított image-be
#   2. pinned base image:   a base image is egy függőség, amit nem mi írtunk
#   3. non-root user:       az alkalmazás nem root-ként fut a konténerben
#   4. minimális másolás:   csak az app kódja kerül be, a .git és a tesztek nem
#
# Build a repo gyökeréből (figyelem: a context és a Dockerfile helye két
# külön dolog):
#
#   docker build -f docker/Dockerfile -t dedih-demo:local .
#                ^ a Dockerfile helye                     ^ a build context
#
# Futtatás:
#
#   docker run --rm -p 8000:8000 dedih-demo:local
#
# Ezután a Swagger UI a http://127.0.0.1:8000/docs címen érhető el.
# ============================================================================


# ----------------------------------------------------------------------------
# 1. STAGE: builder
# ----------------------------------------------------------------------------
# Itt telepítjük a függőségeket egy külön virtualenv-be. Ez a stage tartalmazza
# a pip-et, a letöltött csomagokat és mindent, ami a telepítéshez kell, de
# ebből a stage-ből csak a kész virtualenv megy tovább a második stage-be.
#
# A base image verziója fixálva van (3.11-slim-bookworm), nem "latest". A
# supply chain blokk logikája ide is érvényes: a base image is egy függőség,
# amit nem mi írtunk. Éles környezetben a tag helyett digest-re szokás
# pinnelni (python:3.11-slim-bookworm@sha256:...), mert a tag átírható,
# a digest nem.
# ----------------------------------------------------------------------------
FROM python:3.11-slim-bookworm AS builder

WORKDIR /build

# Csak a requirements.txt-t másoljuk be először. Amíg ez a fájl nem változik,
# a Docker újrahasznosítja a telepítés rétegét, és a build másodpercek alatt
# lefut. Ha a teljes kódot másolnánk ide, minden apró kódváltozás után újra
# kellene telepíteni az összes csomagot.
COPY requirements.txt .

# Ez a requirements.txt a futtatáshoz kellő csomagokat (fastapi, uvicorn,
# pydantic) és a fejlesztői eszközöket (pytest, ruff, pip-audit) is
# tartalmazza, így a dev eszközök is bekerülnek az image-be. Éles projektben
# ezt szét szokás szedni requirements.txt és requirements-dev.txt fájlokra:
# kisebb image, kisebb támadási felület.
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir --upgrade pip \
    && /opt/venv/bin/pip install --no-cache-dir -r requirements.txt


# ----------------------------------------------------------------------------
# 2. STAGE: runtime
# ----------------------------------------------------------------------------
# Ez az image megy ki "élesbe". Tiszta lappal indul, és csak a kész virtualenv
# és az alkalmazás kódja kerül bele. A letöltött csomagfájlok és a build
# közben keletkezett szemét itt már nincs jelen.
# ----------------------------------------------------------------------------
FROM python:3.11-slim-bookworm AS runtime

# PYTHONDONTWRITEBYTECODE: ne írjon .pyc fájlokat a konténerbe
# PYTHONUNBUFFERED:        a log azonnal megjelenjen, ne pufferelődjön
# PATH:                    a virtualenv legyen az alapértelmezett Python
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

# Least privilege: saját, jogosultság nélküli felhasználó. Alapértelmezésben a
# konténer root-ként futna, és egy kitört folyamat root jogokkal indulna. Ez
# ugyanaz az elv, mint a workflow-ok permissions blokkja: csak annyi jog,
# amennyi feltétlenül szükséges.
RUN useradd --create-home --uid 10001 appuser

WORKDIR /app

# A kész virtualenv átemelése a builder stage-ből.
COPY --from=builder /opt/venv /opt/venv

# Csak az alkalmazás kódja kerül be. Nem másolunk .git könyvtárat, teszteket,
# CI konfigurációt vagy helyi .env fájlt. Ez a második védelmi réteg a
# .dockerignore mellett (defense in depth).
COPY app ./app

USER appuser

# Dokumentációs célú: jelzi, hogy az alkalmazás melyik porton figyel.
# Magát a portot a docker run -p kapcsolója nyitja ki kívülre.
EXPOSE 8000

# A konténer maga jelenti, hogy egészséges-e. Ugyanazt a GET / végpontot
# használja, amit a kurzus elején health check-ként megírtunk.
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/')" || exit 1

# A --host 0.0.0.0 azért kell, hogy a konténeren kívülről is elérhető legyen.
# A 127.0.0.1 csak magán a konténeren belülről lenne elérhető, kívülről nem.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]