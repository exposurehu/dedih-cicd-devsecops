# CI/CD és DevSecOps demo

Minimális FastAPI alkalmazás GitHub Actions CI workflow-val.

Ez a repo egy oktatási demo a DEDIH 2.0 / ELTE "CI/CD és DevSecOps" kurzushoz. A cél, hogy egy futtatható, valódi (bár szándékosan apró) projekten lehessen megmutatni a CI/CD baseline-tól a security gate-ekig (branch protection, secret scan, supply chain audit, AI assisted review) vezető utat.

## Stack

- Python 3.11+
- FastAPI + Pydantic
- pytest, ruff
- GitHub Actions
- Docker

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Futás

Tesztek:

```bash
pytest
```

Lint:

```bash
ruff check .
```

Formátum:

```bash
ruff format .
```

Helyi szerver:

```bash
uvicorn app.main:app --reload
```

Swagger UI: <http://127.0.0.1:8000/docs>

## Függőségek frissítése

Ha a `pip-audit` ismert CVE-t talál egy függőségben, a leggyorsabb javítás:

```bash
pip-audit -r requirements.txt --fix
pytest
ruff check .
ruff format --check .
```

A `--fix` automatikusan frissíti az érintett csomagokat egy javított verzióra, és a `requirements.txt`-t is átírja. A tesztek és a lint újrafuttatása ellenőrzi, hogy a frissítés nem tört el semmit.

## Ágak

| Ág | Tartalom |
| --- | --- |
| `main` | Zöld baseline. Egy GET és egy POST végpont, három teszt. |
| `feature/bad-pr` | Új határeset-teszt szándékos off-by-one bug-gal (51 vs 50). |
| `secrets-leak` | `app/config.py`-ban planted "fake" hitelesítő adat, `DONOTUSE` jelölt. |

## A CI workflow

A `.github/workflows/ci.yml` egy aktív `build-and-test` job-bal indul (checkout, install, `ruff check`, `ruff format --check`, pytest). Alatta három kommentelt szekció vár a `# ` jelek mögött:

- `gitleaks` secret scan
- `pip-audit` SCA
- `anthropics/claude-code-action` AI code review

Ezek a kurzus során élőben kerülnek aktiválásra.

## Docker image

A repo tartalmaz egy külön Docker build demót is. Két fájl tartozik hozzá:

| Fájl | Szerep |
| --- | --- |
| `docker/Dockerfile` | Két lépcsős (multi-stage) build, non-root felhasználóval. |
| `.dockerignore` | Meghatározza, mi ne kerüljön bele a build contextbe. |

### Indítás böngészőből

A `.github/workflows/docker.yml` workflow csak kézzel indul, nem fut le minden push-ra: **Actions** fül > **Docker build** > **Run workflow**. Megadható egy saját tag, üresen hagyva a rövid commit SHA lesz a tag.

A workflow megépíti az image-et, majd el is indítja, és meghívja a `/` és a `/greet` végpontot. Ez a különbség a "lefordult" és a "működik" között: attól, hogy egy image megépül, még nem biztos, hogy el is indul.

### Helyi build

```bash
docker build -f docker/Dockerfile -t dedih-demo:local .
docker run --rm -p 8000:8000 dedih-demo:local
```

A `-f` a Dockerfile helyét adja meg, a záró `.` pedig a build contextet, vagyis azt a könyvtárat, amit a Docker megkap. A kettő nem ugyanaz.

Ezután a Swagger UI a <http://127.0.0.1:8000/docs> címen érhető el, ugyanúgy, mint helyi `uvicorn` futtatásnál.

### Mit mutat meg az image

- **multi-stage build**: a csomagok telepítése egy külön lépcsőben történik, a kiszállított image-be már csak a kész virtualenv és az alkalmazás kódja kerül
- **pinned base image**: a `python:3.11-slim-bookworm` verziója fixált, nem `latest`, mert a base image is egy függőség, amit nem mi írtunk
- **non-root user**: az alkalmazás `appuser` néven fut, nem root-ként
- **`.dockerignore`**: a `.git` könyvtár nem kerül be az image-be. Egy fájlból törölt secret a commit history-ban még ott lehet, és egy `COPY . .` azt is becsomagolná az image-be

### Mi jön a build után

A `docker.yml` alján kommentben szerepel, hogyan lehet az elkészült image-et registrybe feltölteni, három tipikus célponttal (GitHub Packages, Docker Hub, Azure Container Registry), valamint mi szokott ezt követni: image vizsgálat CVE-kre, SBOM generálás, image aláírás és deploy.
