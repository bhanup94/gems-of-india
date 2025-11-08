# 🧩 MyNeta–Sansad Data Merger

This project merges **Lok Sabha 2024 winner data** from [MyNeta.info](https://myneta.info/LokSabha2024) with **MP details** from the official [Sansad API](https://sansad.in).  

It scrapes **MyNeta candidate data** using Selenium + BeautifulSoup, retrieves **Sansad member data** and **council of ministers information** via APIs, and outputs a **combined CSV file** containing prefixed columns:
- `myneta_*` → fields from MyNeta
- `sansad_*` → fields from Sansad

---

## 🚀 Features

✅ Scrapes **MyNeta** winners list and individual profiles  
✅ Extracts **photo URL, education detail**, and **past election comparison data**  
✅ Fetches **Sansad MP details** using official APIs  
✅ Integrates **Council of Ministers** data (From Sansad data)  
✅ Fetches **current ministerial position** via Sansad's `positionHeld` API  
✅ Downloads MP photos from Sansad  
✅ Merges both datasets on **constituency name** (exact match)  
✅ Outputs a **clean, unified CSV** for easy analysis

---

## 🗂️ Output Files

| File | Description |
|------|--------------|
| `combined_myneta_sansad.csv` | Final merged dataset (UTF-8 encoded) |
| `mp_photos_sansad/` | Directory containing downloaded Sansad MP photos |

---

## ⚙️ Requirements

- Python **3.8+**
- Google Chrome + ChromeDriver (matching version)
- Python libraries:
  ```bash
  pip install selenium beautifulsoup4 requests
  ```

---

## 🧭 Usage

### 2️⃣ Run the Script

```bash
python3 scripts/python/mps/scrapeLoksabhaMPs.py
```

The script will:
1. Launch a headless Chrome instance  
2. Scrape MyNeta winners’ data and profiles  
3. Fetch Sansad MPs and their detailed info  
4. Merge both datasets by **constituency name**  
5. Save the merged output as `combined_myneta_sansad.csv`

---

## 🧩 Key Functions

| Function | Description |
|-----------|--------------|
| `fetch_council_of_ministers(driver)` | Extracts JSON data from the Sansad "Council of Ministers" page |
| `get_current_position(mp_code)` | Fetches the latest ministerial post for a given MP code |
| `fetch_sansad_for_state(state, page_size, ministers_map)` | Retrieves MP details from Sansad API (across multiple pages) |
| `scrape_myneta_all(driver)` | Scrapes all Lok Sabha 2024 winners from MyNeta |
| `get_myneta_profile_details(driver, url)` | Extracts photo URL, education details, and past elections |
| `merge` logic | Joins MyNeta and Sansad records by normalized constituency name |

---

## 🧹 Data Normalization

Constituency names are normalized by:
- Removing text inside parentheses  
- Removing punctuation and numbers  
- Collapsing extra spaces  
- Converting to uppercase  

Example:  
```
"Amethi (S.C)" → "AMETHI"
```

---

## 📸 Sample Output Columns

| Category | Example Fields |
|-----------|----------------|
| MyNeta | `myneta_candidate`, `myneta_party`, `myneta_constituency`, `myneta_education_summary` |
| Sansad | `sansad_name`, `sansad_party`, `sansad_photo_url`, `sansad_position`, `sansad_education` |

---

## 🧠 Notes

- Headless Chrome can be toggled via `SELENIUM_HEADLESS = True`  
- Modify `MYNETA_PROFILE_LIMIT` to limit how many MyNeta profiles are opened  
- Invalid MyNeta rows (ads, “donate”, “download app”) are automatically filtered  
- Merged matches are logged with a count summary at the end  
- Fallback empty values are inserted when no Sansad match is found  

---

## 📊 Example Output (CSV Preview)

| myneta_candidate | myneta_party | sansad_name | sansad_constituency | sansad_position | sansad_twitter    |
|------------------|---------------|-------------|----------------------|------------------|-------------------|
| ABC              | BJP | XYZ         | AMETHI | Union Minister of Women and Child Development | https://x.com/abc |

---
 
