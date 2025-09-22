# BigQuery AI Hackathon Prototype

This repository contains all files related to my Kaggle BigQuery AI Hackathon project.
For background and context, please see the [Kaggle write-up](./KAGGLE_WRITEUP.md).

---

## Getting Started

### 1. Data

* You can either **scrape the SAP Community HCM Q\&A** yourself, or
* Use the prepared JSONL files:

  * [Google Cloud Storage link 1](https://storage.googleapis.com/bq_public_bucket/sap_hcm_questions.jsonl)
  * [Google Cloud Storage link 2](https://storage.cloud.google.com/bq_public_bucket/sap_hcm_questions.jsonl)

These files should be publicly available.

### 2. Notebook

* Run the notebook in Colab:
  [Open in Colab](https://colab.research.google.com/drive/1BJT7hiBKsmPPXq4_l5gBtEcYC_NfJDSO?usp=sharing)
* A local copy is also included: `BigQuery_Competition.ipynb`.

### 3. API

* Deploy the API as a **Google Cloud Function**.
* The API serves as the backend for the website.
* See the `api/` directory for setup details.

### 4. Website

* Deploy the website to connect with the API.
* The site allows interactive exploration of clusters and their time trends.
* See the `website/` directory for code and instructions.

---

## Repository Structure

Each major step has its own directory:

* `scraper/` → collect data
* `notebook/` → data processing, clustering, labeling
* `api/` → Google Cloud Function backend
* `website/` → frontend visualization (Chart.js)

---
