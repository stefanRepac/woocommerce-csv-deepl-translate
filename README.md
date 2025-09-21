
# WooCommerce CSV prevod (DeepL)

Skript: `translate.py`  
Namena: robustan prevod WooCommerce CSV izvoza uz automatsku detekciju delimiter-a i header-a, HTML handling i pametno biranje kolona.  
Podrazumevano prevodi i **Ingredients** (sastojci).

---

## Zahtevi

- **Python 3.9+** (radi i na 3.13)
- Paketi: `pandas`, `requests`
- DeepL API ključ (Free ili Pro)

Instalacija paketa:
```bash
python3 -m pip install -U pandas requests
```

> Ako `pip` ne radi: `python3 -m ensurepip --upgrade` pa ponovo komandu iznad.

---

## DeepL podešavanje

Obavezno izvezi ključ kao promenljivu okruženja:

**Free nalog (podrazumevano u skripti):**
```bash
export DEEPL_API_KEY='TVOJ_KLJUC_IZ_DEEPL_FREE'
# URL se ne mora menjati (ostaje api-free.deepl.com)
```

**Pro nalog:**
```bash
export DEEPL_API_KEY='TVOJ_KLJUC_IZ_DEEPL_PRO'
export DEEPL_API_URL='https://api.deepl.com/v2/translate'
```

---

## Brzi start

Prevod na mađarski (HU):
```bash
python3 translate.py --in "products.csv" --out "products_HU.csv" --to HU
```

Procena troška (ne šalje na API):
```bash
python3 translate.py --in "products.csv" --out "products_HU.csv" --to HU --estimate
```

Prevod na nemački:
```bash
python3 translate.py --in "products.csv" --out "products_DE.csv" --to DE
```

Radi i sa nazivima:
```bash
python3 translate.py --in "products.csv" --out "products_ENUS.csv" --to english-us
python3 translate.py --in "products.csv" --out "products_PTBR.csv" --to brazilian
```

---

## Argumenti (CLI)

- `--in` *(obavezno)*: putanja do ulaznog CSV fajla (WooCommerce export).
- `--out` *(obavezno)*: izlazni CSV.
- `--to` / `--target-lang` *(podrazumevano: HU)*: ciljni jezik. Dozvoljeno: `HU`, `DE`, `EN-GB`, `EN-US`, `PT-BR`… ili nazivi (`hungarian`, `german`, `english-us`).
- `--estimate`: samo procena karaktera (bez slanja na DeepL).
- `--only-cols "Name,Description,Short description"`: prevodi **samo** navedene kolone (broj i redosled nebitni, poredi se po nazivu).
- `--category-contains "parfum"`: prevodi samo redove gde kolona **Categories** sadrži zadati string (case-insensitive).
- `--limit-rows 50`: obradi samo prvih N redova (korisno za test).
- `--sep ';'` / `--sep '\t'`: ručno zadaj delimiter (ako auto-detekcija ne pogodi).
- `--encoding 'utf-8-sig'` / `'cp1250'`: ručni encoding (ako treba).
- `--exclude-ingredients`: **isključi** prevod sastojaka (podrazumevano se prevode).
  - Napomena: `--include-ingredients` je podržan zbog kompatibilnosti, ali je **no-op** (već su uključeni).

---

## Šta se prevodi

- Tekstualne kolone: **Name, Description, Short description, Content, SEO title/description, attribute value(s)**, itd.
- **Ingredients / Sastojci**: **prevodi se podrazumevano**, prepoznaje više jezika (*Ingredients, Zloženie, Skład, Sastojci, Összetevők, Ingrédients…*).
- **HTML** u opisima: čuva tagove (DeepL `tag_handling=html`).

**Ne prevodi** sistemske/taksonomske kolone: ID, SKU, Prices, Stock, Categories/Tags/Brands, Attribute **name**, sl. (da se ne pokvare veze i taksonomije).

---

## Kako radi detekcija CSV-a

Skripta pokušava:
1. Da pronađe **stvarni header** (npr. red sa „Name, Description, Regular price…“) i automatski odredi delimiter (`,` `;` `\t` `|`) i encoding (`utf-8-sig`, `utf-8`, `cp1250`, `latin1`).
2. Ako to ne uspe, radi „brute-force“ kombinacije.

Ako CSV i dalje „puca“, probaj ručno `--sep` i/ili `--encoding`.

---

## Primeri korišćenja

Samo par proizvoda za test:
```bash
python3 translate.py --in "products.csv" --out "products_HU_50.csv" --to HU --limit-rows 50
```

Filter po kategoriji:
```bash
python3 translate.py --in "products.csv" --out "perfumes_HU.csv" --to HU --category-contains "parfum"
```

Prevod samo ključnih kolona:
```bash
python3 translate.py --in "products.csv" --out "products_HU_min.csv"   --to HU --only-cols "Name,Description,Short description"
```

Specifičan delimiter/encoding:
```bash
python3 translate.py --in "products_semicolon.csv" --out "out_HU.csv" --to HU --sep ';' --encoding utf-8-sig
```

---

## Procena troška

`--estimate` izračuna zbir karaktera po koloni i ukupno, na osnovu ulaza (pre prevoda).  
To pomaže da proceniš DeepL potrošnju pre slanja.

---

## Import u WooCommerce (kratko)

1. **Products → All Products → Import**
2. Izaberi generisani `out.csv`.
3. Prođi kroz **mapping** (Woo obično sam prepozna).
4. Ako ažuriraš postojeće, uključi „Update existing products“ i obavezno mapiraj **SKU**.

> CSV se snima u `utf-8-sig` (kompatibilno sa Excel/Woo).

---

## Najčešće greške & rešenja

- `zsh: command not found: python` → koristi `python3 …`
- `zsh: command not found: pip` → `python3 -m ensurepip --upgrade` pa `python3 -m pip install -U pandas requests`
- `SyntaxError: unterminated string literal` kod `escapechar="\"` → uvek treba **dupli backslash** u stringu: `escapechar='\\'`
- `FileNotFoundError: 'wc-products.csv'` → proveri putanju i ekstenziju, koristi navodnike ako ima razmaka u putanji.
- `pandas.errors.ParserError: Expected X fields…` → CSV ima drugačiji delimiter ili „meta“ red. Probaj `--sep ';'` ili `--sep '\t'` i/ili `--encoding 'utf-8-sig'`. Ako i dalje ne radi, otvori prvih 10 linija i pogledaj header.
- DeepL 429 / 5xx → skripta radi retry/backoff automatski; ako i dalje problem, uspori ili podeli CSV.

---

## Saveti

- Ako izvorni jezik = ciljni (npr. `--to SK`, a tekst već slovački), prevod će biti identičan. Za HU stavi `--to HU`.
- Čuvaj originalni CSV. Radi test na `--limit-rows` pre kompletnog prevoda.
- Ako želiš zaštitu brendova/termina, smisli **glossary** (moguće je dodati podršku — reci ako želiš).

---

## FAQ

**Zašto Ingredients sada prevodi?**  
Traženo je „obavezno“ — zato je default uključen. Ako ne želiš, koristi `--exclude-ingredients`.

**Mogu li da nateram skriptu da prevodi samo tačno određene kolone?**  
Da: `--only-cols "Name,Description,Short description,Ingredients"`.

**Šta ako deo teksta ostane nepreveden?**  
Najčešće je u koloni koja se preskače (npr. taksonomije) ili nije u listi `--only-cols`. Ako zatreba, mogu da dodam opciju `--find "tekst"` za dijagnostiku.

---

## Licenca / Odricanje odgovornosti

Koristi na sopstvenu odgovornost. Proveri rezultate pre uvoza u produkciju.  
Skripta ne menja fajlove sem izlaznog `--out`. Ne čuvamo sadržaj ni ključeve.
