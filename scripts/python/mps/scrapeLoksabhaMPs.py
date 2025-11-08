#!/usr/bin/env python3
"""
Merge MyNeta LokSabha winners data with Sansad API data by constituency.
- MyNeta scraping: Selenium + BeautifulSoup
- Sansad scraping: requests to sansad.in API
Outputs merged CSV with prefixed columns: myneta_* and sansad_*
"""

import os
import time
import re
import json
import csv
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup

# -----------------------
# CONFIG
# -----------------------
STATE = ""
PAGE_SIZE = 10
MYNETA_URL = "https://www.myneta.info/LokSabha2024/index.php?action=show_winners&sort=default"

# Sansad API endpoints
SANSAD_API_BASE = "https://sansad.in/api_ls/member"
SANSAD_DETAIL = "https://sansad.in/api_ls/member/{}?locale=en"
SANSAD_PROFILE_TEMPLATE = "https://sansad.in/ls/members/biographyM/{}?from=members"
SANSAD_MINISTERS_URL = "https://sansad.in/ls/members/in-council-of-ministers"

# Output
OUTPUT_CSV = "combined_myneta_sansad.csv"
PHOTO_DIR_SANSAD = "mp_photos_sansad"
os.makedirs(PHOTO_DIR_SANSAD, exist_ok=True)

# Selenium options
SELENIUM_HEADLESS = True

# -----------------------
# UTILITIES
# -----------------------
def norm_constituency(name):
    """Normalize constituency names for matching: remove parentheses, punctuation and uppercase."""
    if not name:
        return ""
    s = re.sub(r"\([^)]*\)", "", name)           # remove parenthetical content
    s = re.sub(r"[^A-Za-z\s]", " ", s)           # drop punctuation/numbers -> spaces
    s = re.sub(r"\s+", " ", s).strip()           # collapse whitespace
    return s.upper()

def clean_email_field(raw_email):
    """Convert obfuscated email formats into normal emails"""
    if not raw_email:
        return ""
    if isinstance(raw_email, list):
        raw_email = ", ".join(raw_email)
    cleaned = raw_email
    cleaned = cleaned.replace("[at]", "@").replace("[dot]", ".")
    cleaned = cleaned.replace("(at)", "@").replace("(dot)", ".")
    cleaned = cleaned.replace("{at}", "@").replace("{dot}", ".")
    cleaned = cleaned.replace("\n", " ").strip()
    cleaned = re.sub(r"\s*,\s*", ", ", cleaned)
    cleaned = re.sub(r"\s*@\s*", "@", cleaned)
    cleaned = re.sub(r"\s*\.\s*", ".", cleaned)
    cleaned = cleaned.strip(", ")
    return cleaned

def download_photo(photo_url, name, dest_dir):
    """Download photo and return local filename (empty on failure)"""
    if not photo_url:
        return ""
    filename = re.sub(r"[^\w\-\.]", "_", name)[:120] + ".jpg"
    path = os.path.join(dest_dir, filename)
    try:
        r = requests.get(photo_url, timeout=10)
        r.raise_for_status()
        with open(path, "wb") as fh:
            fh.write(r.content)
        return filename
    except Exception as e:
        print(f"⚠️ Could not download photo for {name}: {e}")
        return ""
# -----------------------
# COUNCIL OF MINISTERS SCRAPER
# -----------------------
def fetch_council_of_ministers(driver):
    """Fetch council of ministers JSON and return dict of mpsno -> position (only LS)."""
    driver.get(SANSAD_MINISTERS_URL)
    time.sleep(2)
    soup = BeautifulSoup(driver.page_source, "html.parser")
    script_tag = soup.find("script", id="__NEXT_DATA__", type="application/json")
    if not script_tag:
        print("⚠️ Could not find ministers JSON script tag.")
        return {}

    try:
        data = json.loads(script_tag.string)
        council_list = data["props"]["pageProps"]["councilMinister"]
    except Exception as e:
        print(f"⚠️ Error parsing ministers JSON: {e}")
        return {}

    ministers = {}
    for m in council_list:
        if m.get("house") != "LS":
            continue
        ministers[m["mpsno"]] = {
            "name": m.get("fullName"),
            "position": m.get("position"),
            "photoUrl": m.get("photoUrl")
        }

    print(f"🏛️ Loaded {len(ministers)} LS ministers")
    return ministers

def get_current_position(mp_code: int) -> str:
    """
    Fetches the latest position held by an MP from the Sansad API.

    Args:
        mp_code (int): The MP's unique code (mpsno) from sansad.in.

    Returns:
        str: The first entry's 'positionHeld' value, or an empty string if unavailable.
    """
    url = f"https://sansad.in/api_ls/member/positionHeld?mpCode={mp_code}&locale=en"

    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()

        if isinstance(data, list) and len(data) > 0:
            # Return the most recent (first) positionHeld entry
            position = data[0].get("positionHeld", "").strip()
            return position
        else:
            return ""
    except requests.RequestException as e:
        print(f"Error fetching position for mpCode {mp_code}: {e}")
        return ""
    except ValueError:
        print(f"Invalid JSON for mpCode {mp_code}")
        return ""

# -----------------------
# SANSAD SCRAPER
# -----------------------
def fetch_sansad_for_state(state, page_size=10, ministers_map=None):
    """Return list of sansad records for the given state using sansad API (all pages)."""
    records = []
    page = 1
    while True:
        params = {
            "loksabha": "18",
            "page": page,
            "size": page_size,
            "sitting": "1",
            "locale": "en",
            "memberStatus": "s"
        }
        resp = requests.get(SANSAD_API_BASE, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        members = data.get("membersDtoList", [])
        if not members:
            break
        for m in members:
            member_id = m.get("mpsno")
            name = m.get("mpFirstLastName", "").strip()
            party = m.get("partyFname", "").strip()
            gender = m.get("gender", "").strip()
            constituency = m.get("constName", "").strip()
            state_name = m.get("stateName", "").strip()
            raw_email = m.get("email", "")
            email = clean_email_field(raw_email)
            photo_url = m.get("imageUrl", "").strip()
            loksabha_expr = m.get("lsExpr", "").strip()
            profile_url = SANSAD_PROFILE_TEMPLATE.format(member_id)

            # fetch details (optional)
            details = {}
            try:
                r = requests.get(SANSAD_DETAIL.format(member_id), timeout=10)
                if r.status_code == 200:
                    details = r.json()
            except Exception as e:
                print(f"⚠️ Failed to fetch Sansad details for {member_id}: {e}")

            dob = details.get("dateOfBirth", "")
            education = details.get("education", "") or ""
            education = education.replace("<br>", " ")
            present_addr = (details.get("presentFaddr", "") + " " + details.get("presentLaddr", "")).strip()
            permanent_addr = (details.get("permanentFaddr", "") + " " + details.get("permanentLaddr", "")).strip()
            facebook = details.get("facebook", "")
            twitter = details.get("twitter", "").lower()
            instagram = details.get("instagram", "")
            linkedin = details.get("linkedIn", "")
            if twitter and not re.match(r'^(https?:\/\/)?(www\.)?(x|twitter)\.com\/', twitter, re.IGNORECASE):
                twitter = "https://x.com/" + twitter


            sansad_rec = {
                "sansad_id": member_id,
                "sansad_name": name,
                "sansad_profile_url": profile_url,
                "sansad_constituency_raw": constituency,
                "sansad_constituency": norm_constituency(constituency),
                "sansad_party": party,
                "sansad_gender": gender,
                "sansad_state": state_name,
                "sansad_email": email,
                "sansad_dob": dob,
                "sansad_education": education,
                "sansad_present_address": present_addr,
                "sansad_permanent_address": permanent_addr,
                "sansad_facebook": facebook,
                "sansad_twitter": twitter,
                "sansad_instagram": instagram,
                "sansad_linkedin": linkedin,
                "sansad_photo_url": photo_url,
                "sansad_loksabha_terms": loksabha_expr,
                "sansad_position": "",
                "sansad_position_detail": ""
            }
            # Enrich with minister info
            if ministers_map and member_id in ministers_map:
                sansad_rec["sansad_position"] = ministers_map[member_id]["position"]
                sansad_rec["sansad_position_detail"] = get_current_position(member_id)
            sansad_rec["sansad_photo_file"] = download_photo(photo_url, name, PHOTO_DIR_SANSAD) if photo_url else ""
            records.append(sansad_rec)
            print(f"Sansad: {name} ({constituency})")
            time.sleep(0.2)

        total_pages = data.get("metaDatasDto", {}).get("totalPages", 1)
        if page >= total_pages:
            break
        page += 1

    print(f"📥 Fetched {len(records)} Sansad records for {state}")
    return records

# -----------------------
# MYNETA SCRAPER
# -----------------------
def setup_selenium(headless=True):
    opts = Options()
    if headless:
        opts.add_argument("--headless=new")
    driver = webdriver.Chrome(options=opts)
    return driver

def looks_like_valid_compare_row(cols_texts):
    """Filter out junk rows such as 'Donate now', 'Download app', 'Follow us', etc."""
    if not cols_texts:
        return False

    joined = " ".join([c.strip().upper() for c in cols_texts])
    junk_tokens = [
        "DONATE",
        "DONATE NOW",
        "DOWNLOAD",
        "FOLLOW US",
        "SHARE ON",
        "DOWNLOAD APP",
        "CLICK HERE",
        "ADVERTISEMENT",
    ]

    for token in junk_tokens:
        if token in joined:
            return False

    if not re.search(r"\d", joined):
        return False
    if len(cols_texts) < 3:
        return False

    return True

def get_myneta_profile_details(driver, profile_url):
    """Open a MyNeta profile page and extract photo, education detail, and past elections."""
    driver.get(profile_url)
    time.sleep(1.5)
    psoup = BeautifulSoup(driver.page_source, "html.parser")

    photo_url = ""
    photo_div = psoup.select_one("div.w3-third img")
    if photo_div:
        src = photo_div.get("src", "")
        if src.startswith("http"):
            photo_url = src
        elif src.startswith("/"):
            photo_url = "https://www.myneta.info" + src
        else:
            photo_url = "https://www.myneta.info/LokSabha2024/" + src

    education_detail = ""
    edu_label = psoup.find(text=re.compile(r"Education", re.I))
    if edu_label:
        parent_td = edu_label.find_parent("td")
        if parent_td and parent_td.find_next_sibling("td"):
            education_detail = parent_td.find_next_sibling("td").get_text(" ", strip=True)

    other_elections = []
    more_link = psoup.find("a", string=re.compile("Click here for more details", re.I))
    if more_link and more_link.get("href"):
        compare_url = more_link["href"]
        if compare_url.startswith("/"):
            compare_url = "https://www.myneta.info" + compare_url
        elif not compare_url.startswith("http"):
            compare_url = "https://www.myneta.info/LokSabha2024/" + compare_url

        driver.get(compare_url)
        time.sleep(1.5)
        csoup = BeautifulSoup(driver.page_source, "html.parser")

        target_table = None
        for tbl in csoup.find_all("table"):
            th_texts = " ".join([th.get_text(" ", strip=True).upper() for th in tbl.find_all("th")])
            if any(keyword in th_texts for keyword in ["DECLARATION", "ASSETS", "DECLARED"]):
                target_table = tbl
                break
        if not target_table:
            tables = csoup.find_all("table")
            if tables:
                target_table = max(tables, key=lambda t: len(t.find_all("tr")))

        if target_table:
            for tr in target_table.find_all("tr")[1:]:
                cols = tr.find_all("td")
                cols_texts = [c.get_text(" ", strip=True) for c in cols]
                if not looks_like_valid_compare_row(cols_texts):
                    continue
                if len(cols_texts) >= 8:
                    entry = {
                        "Election Name": cols_texts[0],
                        "Constituency": norm_constituency(cols_texts[1]),
                        "Party Code": cols_texts[2],
                        "Criminal Cases": cols_texts[3],
                        "Number of Cases": cols_texts[4],
                        "Education Level": cols_texts[5],
                        "Total Assets": cols_texts[6],
                        "Total Liabilities": cols_texts[7],
                    }
                    other_elections.append(entry)
    return photo_url, education_detail, other_elections

def scrape_myneta_all(driver):
    """Scrape MyNeta winners table. Returns list of myneta records."""
    driver.get(MYNETA_URL)
    time.sleep(4)
    soup = BeautifulSoup(driver.page_source, "html.parser")
    rows = soup.select("table tr")

    myneta_records = []
    for tr in rows[1:]:
        tds = tr.find_all("td")
        if len(tds) < 8:
            continue

        candidate_td = tds[1]
        candidate_name = candidate_td.get_text(strip=True)
        profile_url = ""
        a_tags = candidate_td.find_all("a")
        if len(a_tags) >= 2:
            href = a_tags[1].get("href", "")
            if href.startswith("/"):
                profile_url = "https://www.myneta.info" + href
            else:
                profile_url = "https://www.myneta.info/LokSabha2024/" + href

        constituency_raw = tds[2].get_text(strip=True)
        constituency = norm_constituency(constituency_raw)
        party = tds[3].get_text(strip=True)
        criminal_case = tds[4].get_text(strip=True)
        education_summary = tds[5].get_text(strip=True)
        total_assets = tds[6].get_text(strip=True)
        liabilities = tds[7].get_text(strip=True)

        photo_url = ""
        education_detail = ""
        other_elections = []

        if profile_url:
            try:
                photo_url, education_detail, other_elections = get_myneta_profile_details(driver, profile_url)
            except Exception as e:
                print(f"⚠️ Error fetching myneta profile {candidate_name}: {e}")

        rec = {
            "myneta_candidate": candidate_name,
            "myneta_profile_url": profile_url,
            "myneta_constituency_raw": constituency_raw,
            "myneta_constituency": constituency,
            "myneta_party": party,
            "myneta_criminal_cases": criminal_case,
            "myneta_education_summary": education_summary,
            "myneta_education_detail": education_detail,
            "myneta_total_assets": total_assets,
            "myneta_liabilities": liabilities,
            "myneta_other_elections": json.dumps(other_elections, ensure_ascii=False),
            "myneta_photo_url": photo_url,
        }
        myneta_records.append(rec)
        print(f"MyNeta: {candidate_name} ({constituency_raw})")

    print(f"📥 Scraped {len(myneta_records)} MyNeta records")
    return myneta_records

# -----------------------
# MERGE LOGIC
# -----------------------
def build_sansad_lookup(sansad_records):
    d = {}
    for r in sansad_records:
        key = r.get("sansad_constituency", "")
        d.setdefault(key, []).append(r)
    return d

def find_sansad_by_constituency(myneta_const, sansad_lookup):
    """Exact match only"""
    if myneta_const in sansad_lookup:
        return sansad_lookup[myneta_const][0]
    return None

# -----------------------
# MAIN
# -----------------------
def main():
    driver_local = setup_selenium(headless=SELENIUM_HEADLESS)
    try:
        # Load ministers first
        ministers_map = fetch_council_of_ministers(driver_local)
        myneta_data = scrape_myneta_all(driver_local)
        sansad_data = fetch_sansad_for_state(STATE, page_size=PAGE_SIZE, ministers_map=ministers_map)

        sansad_lookup = build_sansad_lookup(sansad_data)
        merged = []
        match_count = 0

        for m in myneta_data:
            key = m.get("myneta_constituency", "")
            sansad_rec = find_sansad_by_constituency(key, sansad_lookup)
            combined = dict(m)
            if sansad_rec:
                match_count += 1
                for k, v in sansad_rec.items():
                    if k not in combined:
                        combined[k] = v
                    else:
                        combined["sansad_" + k] = v
            else:
                for k in [
                    "sansad_name", "sansad_profile_url", "sansad_constituency_raw",
                    "sansad_constituency", "sansad_party", "sansad_email", "sansad_photo_url"
                ]:
                    combined.setdefault(k, "")
            merged.append(combined)

        print(f"\n🔍 Matches found: {match_count}/{len(myneta_data)}")
        all_keys = set()
        for r in merged:
            all_keys.update(r.keys())
        fieldnames = sorted(all_keys)

        with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(merged)

        print(f"✅ Combined CSV written to {OUTPUT_CSV} ({len(merged)} rows)")
    finally:
        driver_local.quit()

if __name__ == "__main__":
    main()
