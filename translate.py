#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import argparse
import time
from typing import List, Dict, Any, Tuple

import pandas as pd
import requests

DEEPL_API_KEY = os.getenv("DEEPL_API_KEY", "").strip()
DEEPL_URL = os.getenv("DEEPL_API_URL", "https://api-free.deepl.com/v2/translate").strip()

# Friendy nazivi jezika -> DeepL target kodovi
LANG_ALIASES = {
    "bg": "BG", "bulgarian": "BG",
    "cs": "CS", "czech": "CS",
    "da": "DA", "danish": "DA",
    "de": "DE", "german": "DE", "deutsch": "DE",
    "el": "EL", "greek": "EL",
    "en": "EN", "english": "EN",
    "en-us": "EN-US", "english-us": "EN-US", "en_us": "EN-US",
    "en-gb": "EN-GB", "english-gb": "EN-GB", "en_gb": "EN-GB", "british": "EN-GB",
    "es": "ES", "spanish": "ES", "espanol": "ES", "español": "ES",
    "et": "ET", "estonian": "ET",
    "fi": "FI", "finnish": "FI",
    "fr": "FR", "french": "FR", "français": "FR", "francais": "FR",
    "hu": "HU", "hungarian": "HU", "magyar": "HU",
    "id": "ID", "indonesian": "ID",
    "it": "IT", "italian": "IT",
    "ja": "JA", "japanese": "JA",
    "ko": "KO", "korean": "KO",
    "lt": "LT", "lithuanian": "LT",
    "lv": "LV", "latvian": "LV",
    "nb": "NB", "norwegian": "NB", "bokmal": "NB", "bokmål": "NB",
    "nl": "NL", "dutch": "NL",
    "pl": "PL", "polish": "PL",
    "pt": "PT-PT", "portuguese": "PT-PT", "pt-pt": "PT-PT", "pt_pt": "PT-PT",
    "pt-br": "PT-BR", "pt_br": "PT-BR", "brazilian": "PT-BR",
    "ro": "RO", "romanian": "RO",
    "ru": "RU", "russian": "RU",
    "sk": "SK", "slovak": "SK",
    "sl": "SL", "slovenian": "SL", "slovene": "SL",
    "sv": "SV", "swedish": "SV",
    "tr": "TR", "turkish": "TR",
    "uk": "UK", "ukrainian": "UK",
    "zh": "ZH", "chinese": "ZH", "zh-cn": "ZH", "zh_cn": "ZH",
    "ko-kr": "KO", "ja-jp": "JA"
}

EXPECTED_COL_HINTS = {"name", "description", "short description", "regular price", "sku", "categories", "images"}

# Kolone koje nikad ne prevodimo
NEVER_TRANSLATE_KEYS = [
    "id", "sku", "slug", "price", "regular price", "sale price", "stock", "weight", "length", "width", "height",
    "download", "image", "images", "gallery", "virtual", "tax", "shipping", "menu order", "status", "catalog visibility",
    "date", "parent", "upsells", "cross-sells", "external url", "button text", "position", "reviews", "sold", "rating",
    "manage stock", "stock status", "allow backorders", "purchase note",
    "categories", "tags", "brands", "swatches attributes",
]

ATTRIBUTE_NAME_KEY = "attribute "
ATTRIBUTE_NAME_SUFFIX = " name"
ATTRIBUTE_VALUES_SUFFIX = " value(s)"
HTML_LIKE_KEYS = ["description", "content", "excerpt", "short description"]

# Prepoznavanje "ingredients" u više jezika
INGREDIENTS_KEYS = [
    "ingredients", "ingredienti", "ingredientes", "ingrédients", "ingrediens", "inhaltstoffe", "inhaltsstoffe",
    "zloženie", "zlozenie", "složení", "slozeni", "skład", "sklad",
    "összetevők", "osszetevok",
    "sastojci", "sastav", "sestavine", "состав", "склад", "ingrediente"
]

def normalize_lang(s: str) -> str:
    code = s.strip().lower().replace(" ", "").replace("_", "-")
    return LANG_ALIASES.get(code, s.strip().upper())

# ---------- CSV helpers ----------

def _try_read(path, sep, enc, header=None):
    return pd.read_csv(
        path,
        dtype=str,
        keep_default_na=False,
        encoding=enc,
        engine="python",
        sep=sep,
        quotechar='"',
        doublequote=True,
        escapechar='\\',
        on_bad_lines="error",
        header=header,
    )

def _find_header_and_sep(path, encodings, seps, max_lines=100):
    # pokušaj da lociraš pravi header i delimiter
    for enc in encodings:
        try:
            with open(path, "r", encoding=enc, errors="ignore") as f:
                lines = [next(f) for _ in range(max_lines)]
        except Exception:
            continue
        for i, line in enumerate(lines):
            for s in seps:
                parts = [p.strip().strip('"').lower() for p in line.rstrip("\n\r").split(s)]
                score = sum(1 for p in parts if p in EXPECTED_COL_HINTS)
                if score >= 2:
                    return i, s, enc
    return None, None, None

def sniff_read_csv(path: str, sep: str = None, encoding: str = None) -> pd.DataFrame:
    encodings = [encoding] if encoding else ["utf-8-sig", "utf-8", "cp1250", "latin1"]
    seps = [sep] if sep is not None else [",", ";", "\t", "|"]
    # 1) auto-detekcija headera
    hdr_idx, hdr_sep, hdr_enc = _find_header_and_sep(path, encodings, seps)
    if hdr_idx is not None:
        try:
            return _try_read(path, hdr_sep, hdr_enc, header=hdr_idx)
        except Exception:
            pass
    # 2) brute-force fallback
    last_err = None
    for enc in encodings:
        for s in [None] + seps:
            try:
                df = _try_read(path, s, enc, header="infer")
                if df.shape[1] == 1 and s is None:
                    continue
                return df
            except Exception as e:
                last_err = e
                continue
    raise last_err

# ---------- Heuristike za kolone ----------

def is_never_translate(col: str) -> bool:
    c = col.lower()
    if any(key in c for key in NEVER_TRANSLATE_KEYS):
        return True
    if ATTRIBUTE_NAME_KEY in c and ATTRIBUTE_NAME_SUFFIX in c:
        return True
    return False

def is_ingredient_col(col: str) -> bool:
    c = col.lower()
    return any(k in c for k in INGREDIENTS_KEYS)

def looks_textual(col_name: str, series: pd.Series) -> bool:
    if is_never_translate(col_name):
        return False
    c = col_name.lower()
    if ATTRIBUTE_NAME_KEY in c and ATTRIBUTE_VALUES_SUFFIX in c:
        return True
    # tipične tekstualne kolone
    KEYS = [
        "name", "title", "description", "short description", "excerpt", "content",
        "meta: rank_math_title", "meta: rank_math_description", "yoast", "og:", "twitter:", "seo",
    ]
    if any(key in c for key in KEYS):
        return True
    # heuristika po sadržaju
    if series.dtype == object:
        sample = series.dropna().astype(str).head(50)
        if len(sample) == 0:
            return False
        alpha_ratio = sum(any(ch.isalpha() for ch in s) for s in sample) / len(sample)
        return alpha_ratio >= 0.3
    return False

def choose_columns(df: pd.DataFrame, exclude_ingredients: bool, only_cols: List[str]) -> Tuple[List[str], List[str], List[str]]:
    cols: List[str] = []
    html_cols: List[str] = []
    skipped: List[str] = []

    if only_cols:
        for col in df.columns:
            if col in only_cols:
                cols.append(col)
                if any(k in col.lower() for k in HTML_LIKE_KEYS):
                    html_cols.append(col)
            else:
                skipped.append(col)
        return cols, html_cols, skipped

    for col in df.columns:
        if is_never_translate(col):
            skipped.append(col)
            continue
        if exclude_ingredients and is_ingredient_col(col):
            skipped.append(col)
            continue
        if looks_textual(col, df[col]) or is_ingredient_col(col):
            cols.append(col)
            if any(k in col.lower() for k in HTML_LIKE_KEYS):
                html_cols.append(col)
        else:
            skipped.append(col)

    return cols, html_cols, skipped

# ---------- DeepL ----------

def deepl_translate_batch(texts: List[str], html: bool, target_lang: str) -> Tuple[List[str], List[str]]:
    if not texts:
        return [], []
    params: Dict[str, Any] = {
        "auth_key": DEEPL_API_KEY,
        "target_lang": target_lang,
        "preserve_formatting": 1,
    }
    if html:
        params["tag_handling"] = "html"
    data = []
    for t in texts:
        data.append(("text", "" if t is None else str(t)))

    # jednostavan retry/backoff
    backoff = 1.5
    tries = 0
    while True:
        tries += 1
        try:
            resp = requests.post(DEEPL_URL, data=list(params.items()) + data, timeout=60)
        except Exception:
            if tries < 5:
                time.sleep(backoff)
                backoff *= 1.8
                continue
            raise
        if resp.status_code in (429, 500, 502, 503, 504):
            if tries < 5:
                time.sleep(backoff)
                backoff *= 1.8
                continue
            resp.raise_for_status()
        resp.raise_for_status()
        j = resp.json()
        trs = [item["text"] for item in j.get("translations", [])]
        det = [item.get("detected_source_language", "") for item in j.get("translations", [])]
        return trs, det

# ---------- Utility ----------

def estimate_chars(df: pd.DataFrame, cols: List[str]) -> Dict[str, int]:
    out: Dict[str, int] = {}
    total = 0
    for col in cols:
        s = df[col].fillna("").astype(str)
        n = int(s.str.len().sum())
        out[col] = n
        total += n
    out["__TOTAL__"] = total
    return out

# ---------- Main ----------

def main():
    if not DEEPL_API_KEY:
        print("ERROR: Nije postavljen DEEPL_API_KEY u okruženju.")
        print("Primer: export DEEPL_API_KEY='xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx:fx'")
        sys.exit(1)

    p = argparse.ArgumentParser(description="Prevod WooCommerce CSV fajla preko DeepL API-ja (izbor jezika).")
    p.add_argument("--in", dest="inp", required=True, help="Ulazni CSV (export iz WooCommerce-a).")
    p.add_argument("--out", dest="out", required=True, help="Izlazni CSV sa prevodom.")
    p.add_argument("--to", "--target-lang", dest="target_lang", default="HU",
                   help="Ciljni jezik (npr. HU, DE, EN-GB, PT-BR, 'german', 'hungarian').")
    # Sastojci se prevode PODRAZUMEVANO
    p.add_argument("--exclude-ingredients", action="store_true",
                   help="Isključi prevod kolona sa sastojcima (ingredients/zloženie/...); podrazumevano se prevodi.")
    # Back-compat: prihvati --include-ingredients ali nema efekta
    p.add_argument("--include-ingredients", action="store_true",
                   help="Zastarelo: već se prevodi podrazumevano (bez efekta).")
    p.add_argument("--only-cols", dest="only_cols", help="Zarezom odvojena lista kolona koje se prevode (overrajd svega).")
    p.add_argument("--limit-rows", type=int, default=0, help="Prevedi samo prvih N redova (0 = sve).")
    p.add_argument("--category-contains", dest="cat_contains", help="Prevedi samo redove gde 'Categories' sadrži dati string (case-insensitive).")
    p.add_argument("--estimate", action="store_true", default=False, dest="estimate",
                   help="Ne šalje ka API-ju; samo prikaže procenu karaktera po koloni i ukupno.")
    p.add_argument("--sep", dest="sep", help="Manuelni separator (npr. ',' ';' '\\t' '|').")
    p.add_argument("--encoding", dest="encoding", help="Manuelni encoding (npr. 'utf-8-sig', 'cp1250').")
    args = p.parse_args()

    target_lang = normalize_lang(args.target_lang)
    if not (len(target_lang) in (2, 5) and target_lang.isupper() and (len(target_lang)==2 or "-" in target_lang)):
        print(f"ERROR: Neprepoznat format ciljnog jezika: {args.target_lang}. Probaj npr. 'HU', 'DE', 'EN-GB', 'PT-BR'.")
        sys.exit(1)

    if not os.path.exists(args.inp):
        print(f"ERROR: Ulazni fajl ne postoji: {args.inp}")
        print(f"Trenutni folder: {os.getcwd()}")
        sys.exit(1)

    try:
        df = sniff_read_csv(args.inp, sep=args.sep, encoding=args.encoding)
    except Exception as e:
        print("ERROR: Problem sa čitanjem CSV fajla.")
        print(f"Detalji: {e}")
        print("Saveti: probaj sa --sep ';' ili --sep '\\t' i/ili --encoding 'utf-8' ili 'cp1250'.")
        sys.exit(1)

    # Filter po kategoriji (ako je traženo)
    if args.cat_contains and "Categories" in df.columns:
        mask = df["Categories"].str.lower().str.contains(args.cat_contains.lower(), na=False)
        df = df[mask].copy()
        print(f"[INFO] Filter po kategoriji: ostaje {len(df)} redova.")

    # Limit redova (ako je traženo)
    if args.limit_rows and args.limit_rows > 0:
        df = df.head(args.limit_rows).copy()
        print(f"[INFO] Limit: prevodim prvih {len(df)} redova.")

    # only-cols (ako je zadat)
    only_cols_list: List[str] = []
    if args.only_cols:
        only_cols_list = [c.strip() for c in args.only_cols.split(",") if c.strip()]

    exclude_ingredients = bool(args.exclude_ingredients)
    if args.include_ingredients:
        print("[INFO] --include-ingredients je zastareo i nema efekta (ingredients se prevodi podrazumevano).")

    cols, html_cols, skipped = choose_columns(df, exclude_ingredients=exclude_ingredients, only_cols=only_cols_list)

    if not cols:
        print("UPOZORENJE: Nije pronađena nijedna kolona za prevod. Proverite nazive kolona ili --only-cols.")
        df.to_csv(args.out, index=False, encoding="utf-8-sig")
        sys.exit(0)

    print(f"[LANG] Ciljni jezik: {target_lang}")
    print("[COLUMNS] Prevodiću {} kolona: {}".format(len(cols), cols))
    if html_cols:
        print("[HTML] HTML tretman za: {}".format(html_cols))
    if skipped:
        print("[SKIPPED] Preskačem {} kolona (npr. taksonomije, ID, SKU...)".format(len(skipped)))

    if args.estimate:
        est = estimate_chars(df, cols)
        total = est.pop("__TOTAL__", 0)
        print("\n[ESTIMATE] Karakteri po koloni:")
        for k, v in sorted(est.items(), key=lambda x: (-x[1], x[0])):
            print("  {}: {}".format(k, v))
        print(f"\n[ESTIMATE] UKUPNO: {total}")
        sys.exit(0)

    detected_summary: Dict[str, int] = {}
    for col in cols:
        series = df[col].astype("object")
        values = series.fillna("").astype(str).tolist()

        out_vals: List[str] = []
        det_langs: List[str] = []

        is_html = col in html_cols
        for i in range(0, len(values), 50):
            batch = values[i:i+50]
            trs, det = deepl_translate_batch(batch, html=is_html, target_lang=target_lang)
            if len(trs) != len(batch):
                diff = len(batch) - len(trs)
                trs += batch[len(trs):]
                det += [""] * diff
            out_vals.extend(trs)
            det_langs.extend(det)

        for lang in det_langs:
            if not lang:
                continue
            detected_summary[lang] = detected_summary.get(lang, 0) + 1

        df[col] = out_vals

    if detected_summary:
        total_det = sum(detected_summary.values())
        top_lang = sorted(detected_summary.items(), key=lambda x: x[1], reverse=True)[0][0]
        print("[INFO] Detektovani izvori jezika (uzorak {}): {} | Najčešći: {}".format(total_det, detected_summary, top_lang))
    else:
        print("[INFO] Nije dobijena detekcija jezika (polja možda bila prazna).")

    df.to_csv(args.out, index=False, encoding="utf-8-sig")
    print("✅ Gotovo: {}".format(args.out))

if __name__ == "__main__":
    main()
