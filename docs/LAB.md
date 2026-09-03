# CI/CD és DevSecOps, gyakorlati útmutató

ELTE IK, DEDIH 2.0. Ez a dokumentum minden lépést tartalmaz, amit a mai napon
végigcsinálunk, és minden kimenetet, amit látni fogsz. Ha lemaradsz, innen
egyedül is folytatni tudod, és a nap után is végig tudod csinálni újra.

---

## Mit csinálunk ma

Egy működő FastAPI alkalmazás köré építünk fel egy pipeline-t, lépésről
lépésre. A nap végére a saját fork-odban ezek fognak működni:

| Elem | Mit csinál |
| --- | --- |
| `build-and-test` job | lefuttatja a lintet és a teszteket minden pull request-en |
| branch protection ruleset | piros check mellett nem engedi a merge-öt |
| `secret-scan` job | jelzi, ha hitelesítő adat kerül a repóba |
| `needs:` függőség | megállítja az image build-et és a deploy-t, ha a scan piros |
| Trivy gate és report | megmutatja, mi van a kiszállított image-ben |
| AI review job | egy modell kommentet ír a pull request-re, a runneren futva |

Az alkalmazásnak három végpontja van:

| Végpont | Mit csinál |
| --- | --- |
| `GET /` | health check, `{"status": "ok"}` |
| `POST /greet` | köszön, a nevet a Pydantic validálja, 1 és 50 karakter között |
| `GET /config` | megmondja, van-e beállítva API kulcs, de az értéket soha nem adja vissza |

A `GET /config` a 3. blokkban lesz fontos.

---

## Fontos tudnivalók, olvasd el ezt először

**1. Minden lépés elvégezhető a böngészőből, a GitHub felületén.** Telepíteni
nem kell semmit.

**2. A saját fork-odban dolgozol.** Mindenki a saját másolatán állítja be a
gate-eket, nyitja a pull request-eket és hozza létre a secret-eket. Az eredeti
repóba senki nem push-ol.

**3. A repóban lévő függőségek szándékosan régiek.** A 4. blokkban ez adja a
valódi találatokat. A CVE-k igaziak, csak nincsenek kijavítva.

**4. Néhány futás szándékosan pirosra megy.** Ahol ez így van, ott külön le van
írva.

---

## 0. Forkold a repót

Nyisd meg: <https://github.com/joczikszabi/dedih-cicd-devsecops>

Jobb felül **Fork**. A következő képernyőn **vedd ki a pipát** a
**Copy the `main` branch only** jelölőnégyzetből, különben csak a `main` ág jön
át, és a `feature/bad-pr` meg a `secrets-leak` ág nem. Mindkettőre szükség lesz.

Ezután **Create fork**.

Az **Actions** fülön öt workflow-t kell látnod:

```
CI
Deploy
Deploy to an environment
Docker build
AI review
```

---

## 1. Blokk: CI/CD és DevSecOps alapfogalmak

### 1.1 Indítsd el a CI workflow-t

**Actions** > bal oldalt **CI** > jobb oldalt **Run workflow** > **Run
workflow**.

Nagyjából tizenöt másodperc múlva két zöld job:

```
Build and test            success
Secret scan (gitleaks)    success
```

Ezzel lefutott az első CI. Semmit nem kellett telepítened hozzá.

### 1.2 Mi futott le

Kattints a **Build and test** jobra. Öt lépés fut le benne:

```
Check out the repository
Set up Python and install the dependencies
Lint (ruff)
Format check (ruff format)
Tests (pytest)
```

A `Tests (pytest)` lépést nyisd ki:

```
....                                                     [100%]
4 passed in 0.23s
```

Négy teszt fut le, negyed másodperc alatt. Ugyanez fog lefutni minden pull
request-en.

### 1.3 Az alkalmazás

Az alkalmazás forráskódja az `app/` könyvtárban van, összesen három rövid fájl.
A `app/models.py` az egyetlen hely, ahol a név hossza szabályozva van:

```python
class Greeting(BaseModel):
    name: str = Field(min_length=1, max_length=50)
```

Ez az `50` a 2. blokkban kerül elő.

---

## 2. Blokk: a workflow felépítése és a merge gate-ek

### 2.1 Olvassuk el a ci.yml-t

Nyisd meg: `.github/workflows/ci.yml`.

A fájl tetején az áll, mikor fut a workflow:

```yaml
on:
  pull_request:
  push:
    branches: [main]
  workflow_dispatch:
```

Minden pull request-re fut, és a merge után a `main`-en még egyszer. A második
futásra azért van szükség, mert egy merge el tud rontani olyasmit, amit
külön-külön egyik ág sem rontott el.

Alatta a jogosultságok:

```yaml
permissions:
  contents: read
```

Ez a least privilege elv. A workflow alapból csak olvasni tud, és amelyik job
ennél többet igényel, annak külön kérnie kell. Az `ai-review.yml`-ben látni fogod, hogy ott
pontosan egy plusz jog szerepel.

A `build-and-test` job második lépése ez:

```yaml
      - name: Set up Python and install the dependencies
        uses: ./.github/actions/setup
```

Ez egy composite action. A lépések a `.github/actions/setup/action.yml`-ben
vannak, egyszer leírva, és minden job onnan használja őket.

### 2.2 Kapcsold be a branch protection-t

**Settings** > **Rules** > **Rulesets** > **New ruleset** > **New branch
ruleset**.

| Mező | Érték |
| --- | --- |
| Ruleset Name | `main protection` |
| Enforcement status | `Active` |
| Target branches | **Add target** > **Include default branch** |

Pipáld be:

- **Require a pull request before merging**
- **Require status checks to pass**, majd **Add checks** és keresd ki:
  `Build and test`

Alul **Create**.

> Ha a check nem jelenik meg a listában, gépeld be a nevét kézzel, és úgy mentsd
> el. A GitHub csak a korábban már lefutott ellenőrzéseket ajánlja fel, de a név
> beírása ugyanúgy működik.

### 2.3 Nyiss egy PR-t a hibás ágról

**Pull requests** > **New pull request**.

| Mező | Érték |
| --- | --- |
| base | `main` |
| compare | `feature/bad-pr` |

**Create pull request**, majd még egyszer **Create pull request**.

Az ág egyetlen dolgot csinál: hozzáad egy tesztet a leghosszabb elfogadott
névre.

```python
def test_greet_accepts_max_length_name():
    # Boundary test: the longest name the endpoint accepts.
    long_name = "A" * 51
    response = client.post("/greet", json={"name": long_name})
    assert response.status_code == 200
```

Néhány másodperc múlva a PR alján:

```
Build and test            Failing after 11s
Secret scan (gitleaks)    Successful in 8s
```

Egy piros és egy zöld. Nyisd ki a pirosat:

```
FAILED tests/test_main.py::test_greet_accepts_max_length_name
assert 422 == 200
 +  where 422 = <Response [422 Unprocessable Entity]>.status_code
```

A teszt 51 karaktert küld és HTTP 200-at vár. A `app/models.py` viszont
`max_length=50`-et mond, ezért a FastAPI 422-vel válaszol, még mielőtt a
kódunk egyáltalán lefutna.

A pull request alján:

```
Merging is blocked
Required status check "Build and test" is expected.
```

A merge gomb inaktív. Nem egy ember tartja vissza a merge-öt, hanem a
beállított szabály.

### 2.4 Javítsd ki a tesztet

A PR **Files changed** fülén a `tests/test_main.py` jobb felső sarkában a
három pont > **Edit file**. Írd át az `51`-et `50`-re:

```python
    long_name = "A" * 50
```

**Commit changes** > **Commit directly to the feature/bad-pr branch**.

A check újraindul, zöldre vált, a merge gomb aktív lesz. **Merge pull
request** > **Confirm merge**.

A merge után a `main`-en még egyszer lefut a CI. Ez az a futás, ami azt
ellenőrzi, hogy a merge önmagában nem rontott el semmit.

---

## 3. Blokk: secret kezelés

### 3.1 Futtasd a Deploy workflow-t a secrets-leak ágon

**Actions** > **Deploy** > **Run workflow**. A **Branch** legördülőből válaszd
a `secrets-leak` ágat, majd **Run workflow**.

A futás három jobból áll. Az eredmény:

```
Secret scan (gitleaks)    failure
Lint and tests            success
Deploy                    skipped
```

### 3.2 Mit mutat az eredmény

Nyisd ki a piros jobot, a `Scan for secrets` lépést:

```
SECRET SCAN   1 finding(s)
==================================================================
app/config.py:25
    rule:    generic-api-key
    entropy: 5.0219283
    match:   API_KEY_ENV, "REDACTED"
------------------------------------------------------------------
The value is redacted above. Open the file at the line shown.
```

A fájl neve és a sor száma megvan, az érték viszont nem. A `--redact`
kapcsoló miatt a szkenner soha nem írja ki magát a titkot, mert azzal
pontosan azt tenné, ami ellen véd: bemásolná egy naplóba, amit sokan
elolvashatnak.

A gitleaks nem ismeri fel, milyen szolgáltatáshoz tartozik a kulcs. Azt látja,
hogy egy `API_KEY` nevű azonosító mellett egy hosszú, magas entrópiájú string
áll, és ez a mintázat elég a jelzéshez.

A harmadik job státusza `skipped`. Nem piros, hanem szürke: el sem indult.

A `deploy.yml`-ben ez az oka:

```yaml
  deploy:
    needs: [secret-scan, verify]
```

Ez a különbség egy check és egy gate között. Egy piros check jelez egy
problémát, és a munka mellette megy tovább. Egy gate megállítja a munkát: a
függő job el sem indul. Nem épült semmi, nem ment ki semmi, nincs mit
visszacsinálni.

### 3.3 Mi okozta

Nyisd meg a `secrets-leak` ágon az `app/config.py` fájlt. Az utolsó sor:

```python
    return bool(os.environ.get(API_KEY_ENV, "sk-proj-<itt a kulcs>").strip())
```

> A teljes érték itt szándékosan nincs kiírva. Ha kiírnánk, a `secret-scan` job
> ezt a fájlt is megtalálná, és a `main` ág pirosra menne. Az igazi értéket a
> `secrets-leak` ágon, magában a fájlban látod.

Ez a leggyakoribb változata ennek a hibának. Senki nem akart rosszat: a
környezeti változó nem volt beállítva, az alkalmazás nem indult el, és a
leggyorsabb megoldás az volt, hogy a fejlesztő beírta az értéket
alapértelmezettnek. Semmilyen komment nem árulkodik róla. A függvény
dokumentációja pedig azóta hazudik: azt állítja, hogy a kulcs a környezetből
jön.

Ezen az ágon az alkalmazás működne, és a `GET /config` `true`-t válaszolna. Ezt
most nem látjuk, mert a gate meg sem engedte, hogy a deploy elinduljon. Pontosan
ez a dolga.

### 3.4 Vedd ki az értéket

Szerkeszd a fájlt a `secrets-leak` ágon (ceruza ikon), és írd vissza üresre:

```python
    return bool(os.environ.get(API_KEY_ENV, "").strip())
```

**Commit changes** > **Commit directly to the secrets-leak branch**.

Futtasd újra a **Deploy** workflow-t ugyanezen az ágon. Most mind a három job
lefut, és a `Deploy` job végén ez áll:

```
GET /config answers:
{"api_key_configured":false}
```

Az értékkel együtt az alkalmazás a hozzáférést is elvesztette. A kulcs tehát
valóban használatban volt, nem csak ott állt a fájlban.

### 3.5 A kulcs beállítása a repository-ban

**Settings** > **Secrets and variables** > **Actions** > **New repository
secret**.

| Mező | Érték |
| --- | --- |
| Name | `OPENAI_API_KEY` |
| Secret | bármi, például `sk-proj-CLASSDEMO-1234` |

**Add secret**, majd futtasd újra a **Deploy** workflow-t a `secrets-leak`
ágon. A `What the log shows of the secret` lépésben:

```
The value, printed straight into the log: ***
The length of the same value: 40 characters
```

És a következő lépésben:

```
GET /config answers:
{"api_key_configured":true}
```

### 3.6 Hogyan jutott el a secret a kódig

A kódban semmi nem utal a GitHub-ra. Az alkalmazás egyetlen dolgot csinál:
beolvas egy környezeti változót.

```python
os.environ.get("OPENAI_API_KEY")
```

A kapcsolatot egyetlen sor teremti meg a `deploy.yml`-ben:

```yaml
      - name: Start the application and ask it about its configuration
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
```

A kettőspont bal oldalán az a környezeti változó neve, amit a folyamat látni
fog. A jobb oldalán az, hogy a GitHub honnan veszi az értéket. A teljes lánc:

```
GitHub secret store
      |
      |   deploy.yml:  env: OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
      v
a runner folyamatának környezete
      |
      |   app/config.py:  os.environ.get("OPENAI_API_KEY")
      v
az alkalmazás
```

A 3.4 lépésben `false` volt a válasz, a 3.5 lépésben `true`, és közben az
alkalmazás kódja nem változott. A különbség az, hogy honnan jön az érték.
Ugyanez az alkalmazás változtatás nélkül megkapja a kulcsot egy laptopon
`export`-tal, egy konténerben `docker run -e`-vel, vagy egy Azure App Service
application setting-jéből. Az alkalmazás nincs hozzákötve a secret tárolóhoz, a workflow az
adapter közöttük.

> A két név csak azért egyezik, mert így döntöttünk. Az
> `OPENAI_API_KEY: ${{ secrets.BARMI_MAS }}` ugyanígy működne.

### 3.7 A kulcs a history-ban marad

Menj a fork-odban a `secrets-leak` ág commit listájára, és nyisd meg azt a
commitot, ami a kulcsot behozta. Az érték olvashatóan ott van a diff-ben.

A CI zöld, a kulcs pedig továbbra is elérhető.

Egy fájlból törölt érték nem tűnik el a git history-ból. Aki forkolta,
klónozta vagy CI job-ot futtatott azon a commiton, annál már megvan. Az
egyetlen valódi javítás a kulcs visszavonása és cseréje a szolgáltatónál.

> Ha van kéznél terminál, ugyanezt a gitleaks is megmutatja:
>
> ```bash
> docker run --rm -v "$PWD":/scan zricethezav/gitleaks:v8.30.1 \
>   git /scan --no-banner --redact
> ```
>
> Kiírja a commit hash-t, a szerzőt és a dátumot is.

### 3.8 Environments, ha külön szeretnéd tartani a secret-eket

Eddig egy repository secret volt, amit minden job lát. Ha több környezetbe
szállítasz, környezetenként külön értéket akarsz.

**Settings** > **Environments** > **New environment**. Hozz létre kettőt,
`staging` és `production` néven. Mindegyikbe:

| Típus | Név | Érték |
| --- | --- | --- |
| Environment secret | `OPENAI_API_KEY` | különböző hosszúságú értékek |
| Environment variable | `DEPLOY_TARGET` | `staging.internal` és `prod.example.com` |

Most **Actions** > **Deploy to an environment** > **Run workflow**. A
legördülőben megjelenik a két environment, amit az előbb hoztál létre. A
GitHub tölti fel a listát, a workflow fájlban egyikük neve sem szerepel.

Futtasd le mindkettőre, és hasonlítsd össze a két log-ot. A `DEPLOY_TARGET`
nyíltan látszik, a secret `***`, de a karakterszáma más.

A `deploy.yml` és a `deploy-environments.yml` szándékosan két külön fájl.
Hasonlítsd össze őket: a különbség négy sor, a workflow neve, egy input, a job
megjelenő neve, és ez:

```yaml
    environment: ${{ inputs.target }}
```

Ennyibe kerül egy pipeline-t environment mögé tenni. A keresési sorrend
environment, aztán repository, aztán organisation, tehát ha a `production`-ben
elfelejtesz secret-et megadni, csendben a repository-szintű értéket kapja.

Az environment ezen kívül kaput is ad. A `production` beállításainál a
**Required reviewers** pipával a job addig várakozik, amíg valaki jóvá nem
hagyja. A branch protection azt dönti el, mit lehet merge-elni. Az environment
azt, mit lehet kiszállítani.

---

## 4. Blokk: függőségek és supply chain

### 4.1 Futtasd a Docker build workflow-t

**Actions** > **Docker build** > **Run workflow**, a `main` ágon.

A futás két jobból áll, és a `Docker build` job a `secret-scan`-től függ,
ugyanúgy, mint a deploy. Ennek itt is oka van: egy hitelesítő adat, ami a build
pillanatában a fában van, bekerül egy image rétegbe, és a réteget bárki
elolvashatja, aki le tudja húzni az image-et. A fájl későbbi törlése ezen nem
segít, ugyanúgy, ahogy a git history-n sem.

A job végigmegy a build-en és a smoke teszten, majd kétszer szkenneli
ugyanazt az image-et. **A második szkennelés pirosra viszi a futást. Ez a
gyakorlat része.**

### 4.2 A gate

Nyisd ki a `Scan the image, gate` lépést:

```
==================================================================
GATE   our own packages, fixable only, HIGH and CRITICAL only
==================================================================
PACKAGE      INSTALLED  VULNERABILITY      SEVERITY  FIXED IN
starlette    0.38.6     CVE-2024-47874     HIGH      0.40.0
starlette    0.38.6     CVE-2026-48818     HIGH      1.1.0
starlette    0.38.6     CVE-2026-54283     HIGH      1.3.1
------------------------------------------------------------------
3 finding(s). The build stops here.
Error: Process completed with exit code 1.
```

Három szűrő van rajta, mindegyiknek oka van:

| Kapcsoló | Mit jelent |
| --- | --- |
| `--pkg-types library` | csak a saját csomagjaink, az operációs rendszer nem |
| `--ignore-unfixed` | csak az, amire létezik javított verzió |
| `--severity HIGH,CRITICAL` | csak az, amiért érdemes megállítani egy release-t |
| `--exit-code 1` | ha marad valami a szűrők után, a build piros |

Érdemes megnézni a csomag nevét. A `starlette` **nincs benne a
`requirements.txt`-ben**, a `fastapi` hozza magával. Ez a transitive
dependency: nem közvetlenül mi választottuk, de mi szállítjuk ki.

### 4.3 A report

Ugyanaz a szkenner, ugyanaz az image, szűrők nélkül:

```
==================================================================
REPORT   everything in the image, nothing filtered out
==================================================================
                               FINDINGS   WITH A FIX
Base operating system               231            0
Python packages                       8            8
------------------------------------------------------------------
Total                               239            8

CRITICAL 5   HIGH 24   MEDIUM 100   LOW 103   UNKNOWN 7
------------------------------------------------------------------
```

Ugyanezt a futás **Summary** oldalán táblázatként is megtalálod, a teljes
Trivy kimenet pedig a `trivy-reports` artifactban van.

### 4.4 A két szám különbsége

A gate 3 találatot jelentett, a report 239-et. A gate azt mutatja, amit
választottunk, a report azt, amit valójában kiszállítunk.

A táblázat lényeges sora ez: a 231 operációs rendszer szintű
találatból **nulla** javítható. Nincs hozzá kiadott csomagverzió. Az összes
javítható találat, mind a 8, a Python csomagokban van. Az öt CRITICAL és a HIGH
találatok nagy része a base image-ből jön, amit nem mi írtunk.

Ebből következik a szabály:

> **Ami blokkol, annak megoldhatónak kell lennie. Ami tájékoztat, az lehet
> teljes.**

Egy gate, ami olyasmire riaszt, amit senki nem tud megjavítani, egy hónapon
belül ki lesz kapcsolva. Utána viszont sem a gate nincs meg, sem az információ.

### 4.5 Mit javítanánk, és milyen sorrendben

A 239 találatból ma három blokkol. Mind a három ugyanabban a csomagban van, és
azt a csomagot egyetlen sor hozza be. A javítás:

```diff
- fastapi==0.115.0
+ fastapi==0.141.1
```

Ez a `starlette`-et 0.38.6-ról 1.6.0-ra viszi. Az eredmény mérve:

| | Előtte | Utána |
| --- | --- | --- |
| Gate találatok | 3 | **0** |
| Gate kilépési kód | 1, a build piros | **0, a build zöld** |
| Report, összesen | 239 | 232 |
| Report, Python csomagok | 8 | 1 |

A tesztek továbbra is zöldek. Nincs automatikus javító parancs: a Trivy megadja
a csomagot, a telepített verziót és a javított verziót, a pin átírása kézi
munka.

Érdemes megnézni, mi maradt. A report 232-nél áll meg, nem nullánál, és az egyetlen
megmaradt Python találat a `pytest` egy MEDIUM besorolású hibája. A gate ezt
nem is nézi, mert a súlyossági szűrő kiveszi. Egy blokkoló hiba javítása nem
azt jelenti, hogy a repó tiszta lett. Azt jelenti, hogy ma nincs olyan
találatunk, ami megállítaná a kiszállítást.

A maradék 231-gyel nem csinálunk semmit ma. Nem azért, mert nem érdekes, hanem
mert ma nincs mit tenni velük. Amit tudni kell róluk, azt a report megmondja, és
ezért írja ki minden futásnál, akkor is, ha a gate megállította a build-et.

---

## 5. Blokk: LLM a pipeline-ban

### 5.1 Indítsd el a review job-ot

Ehhez kell egy nyitott PR. Ha a 2. blokkban lezártad, nyiss egy újat bármelyik
ágról, és jegyezd fel a számát.

**Actions** > **AI review** > **Run workflow**, a `main` ágon, a **The number
of the pull request to review** mezőbe a PR száma, majd **Run workflow**.

Amíg fut, ez történik: a job letölt egy nyílt súlyú modellt magára a runnerre,
és ott futtatja. Semmilyen API kulcs nem kell hozzá, és a kód nem hagyja el a
futást.

Ennek a minőségre is van következménye. Egy ingyenes runner négy CPU magot ad
és GPU-t nem, ezért a modellnek kicsinek kell lennie, egy kicsi modell pedig
szerény kritikát ír.

### 5.2 A mérés

A job negyvennégy másodperc alatt lefut:

| Lépés | Idő |
| --- | --- |
| Ollama telepítése | 6 mp |
| A modell letöltése (`qwen2.5-coder:1.5b`) | 9 mp |
| A kritika megírása | 21 mp, 95 token, 24,4 token per másodperc |
| A komment kiírása a PR-re | 1 mp |

### 5.3 Olvasd el, amit írt

A PR-en megjelenik egy komment. A tényleges kimenet a mi futásunkban ez volt:

```
- The api_key_configured function reads the API key from the environment on
  every call, which can lead to unexpected behavior if the key is set after
  startup.
- The Greeting model does not enforce the length constraint of the name field,
  which can lead to invalid input being accepted by the endpoint.
- The read_config endpoint does not return the value of the API key, which can
  lead to confusion about the secret's configuration.
```

Nézzük meg mind a hármat a kód mellett.

**Az első** visszafelé mondja. A függvény dokumentációja pontosan azt írja, hogy
azért olvassa minden híváskor a környezetet, hogy elkapja az indulás után
beállított kulcsot is. A modell felismerte a mechanizmust, és a következtetést
fordítva vonta le.

**A második** egyszerűen nem igaz. A `Field(min_length=1, max_length=50)` ott
volt a promptjában. Ez az a pont, ami a legközelebb áll a valódi hibához, és
pont az ellenkezőjét állítja.

**A harmadik** a szándékos tervezést jelenti be hibaként. Ha valaki követné ezt
a tanácsot, egy HTTP végpont visszaadná a secret értékét.

A valódi hibát, az 51 és az 50 közötti eltérést, nem találta meg.

### 5.4 Mit jelent ez

Nem azt, hogy a modell gyenge. Azt, hogy egy kicsi modell folyékony,
magabiztos és téves mondatokat írt, és az egyik tanácsa biztonsági hibát
okozott volna, ha valaki követi.

Ezért nem gate egy modell kommentje. A merge-öt a tesztek és a szkennerek
blokkolják, ez a komment egy tipp.

Ugyanez a workflow más hardveren mást ad:

| Hol fut a modell | Modell mérete | A kritika minősége | Elhagyja a kód a hálózatot | Költség |
| --- | --- | --- | --- | --- |
| ingyenes runner (ezt használtuk) | 1B - 3B | szerény | nem | ingyenes |
| saját GPU-s gép | 14B - 32B és felette | használható | nem | hardver |
| hosztolt API | nagy | használható | igen | tokenenként |

A workflow ugyanaz marad, a `MODEL` sort kell átírni benne.

---

## Hibaelhárítás

**Nem látom a workflow-kat az Actions fülön.** A fork-ban engedélyezni kell
őket, lásd a 0.2 lépést.

**A "Run workflow" gomb nem jelenik meg.** Csak azoknál a workflow-knál van,
amelyek a default branch-en is léteznek. Ha a fájlt csak egy ágon módosítottad,
a gomb az alapértelmezett ág verziója alapján jelenik meg.

**A ruleset nem találja a "Build and test" check-et.** A check csak akkor
választható ki, ha már lefutott legalább egyszer a repóban.

**A PR-en nem indulnak el a check-ek.** Az Actions engedélyezése a fork-ban a
PR-ekre is vonatkozik. Ellenőrizd a 0.2 lépést.

**A Docker build piros.** A `Scan the image, gate` lépésnél az. Ez szándékos,
lásd a 4.2 pontot. Ha máshol pirosodik el, az nem az.

**Az AI review job nem ír kommentet.** A `pr_number` mezőbe a PR sorszáma kell,
a `#` jel nélkül, és a PR-nek nyitottnak kell lennie.

---

## Amit ma használtunk, egy lapon

| Eszköz | Verzió | Mire |
| --- | --- | --- |
| gitleaks | 8.30.1 | secret-ek keresése a fájlokban és a git history-ban |
| Trivy | 0.74.0 | image szkennelés, operációs rendszer és Python csomagok |
| Ollama | 0.33.2 | modell futtatása a runneren |
| qwen2.5-coder | 1.5b | a review job modellje |

| Fájl | Mi van benne |
| --- | --- |
| `.github/workflows/ci.yml` | build, lint, teszt és secret scan minden PR-en |
| `.github/workflows/docker.yml` | image build, smoke teszt, Trivy gate és report |
| `.github/workflows/deploy.yml` | két gate, majd a deploy, ami mindkettőtől függ |
| `.github/workflows/deploy-environments.yml` | ugyanaz, environment-tel |
| `.github/workflows/ai-review.yml` | a modell a runneren, komment a PR-re |
| `.github/workflows/reusable-checks.yml` | reusable workflow, a deploy hívja |
| `.github/actions/setup/` | composite action, Python és függőségek |
| `.github/actions/secret-scan/` | composite action, gitleaks |
| `docker/Dockerfile` | multi-stage build, non-root user, telepítő nélküli image |
