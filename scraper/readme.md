# SAP Community Scraper

This script downloads Q\&A posts from the SAP Community (HCM questions) and saves them locally.

## Usage

```bash
python sap_community_scraper.py \
  --sitemap https://community.sap.com/sitemap_hcm-questions.xml.gz \
  --limit 16000 \
  --out-jsonl sap_hcm_questions.jsonl \
  --out-json sap_hcm_questions.json
```

## Notes

* The `--sitemap` points to the official sitemap for HCM questions.
* The `--limit` parameter restricts the number of posts to scrape (here: 16,000).
* Data is exported in both **JSONL** (`.jsonl`) and **JSON** (`.json`) formats.
* ⚠️ The scraping process can take **several hours** depending on your connection and system performance.

