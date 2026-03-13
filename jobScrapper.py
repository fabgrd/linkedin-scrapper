import logging
import random
import re
import time
from datetime import datetime
from io import BytesIO
from urllib.parse import quote

import pandas as pd
import requests
import streamlit as st
from bs4 import BeautifulSoup

try:
    from openpyxl import Workbook
except ImportError:  # pragma: no cover
    Workbook = None


DURATION_MAP = {
    "1 jour": "r86400",
    "1 semaine": "r604800",
}

DEFAULT_CITIES = [
    "Paris, France",
    "Lyon, France",
    "Marseille, France",
    "Geneva, Switzerland",
    "Lausanne, Switzerland",
    "Casablanca, Morocco",
    "Rabat, Morocco",
]

DEFAULT_KEYWORDS = [
    "frontend developer",
    "software engineer",
    "sales engineer",
    "IT analyst",
]


class LinkedInJobScraper:
    def __init__(self):
        self.session = requests.Session()
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
            "Connection": "keep-alive",
        }

    @staticmethod
    def is_masked(text):
        if not text:
            return True
        stars_ratio = text.count("*") / max(len(text), 1)
        return stars_ratio > 0.3

    @staticmethod
    def parse_delay_to_minutes(delay_text):
        if not delay_text or delay_text == "N/A":
            return float("inf")

        delay_text = delay_text.lower().strip()
        number_match = re.search(r"(\d+)", delay_text)
        if not number_match:
            return float("inf")

        number = int(number_match.group(1))
        if "minute" in delay_text:
            return number
        if "heure" in delay_text:
            return number * 60
        if "jour" in delay_text:
            return number * 60 * 24
        if "semaine" in delay_text:
            return number * 60 * 24 * 7
        if "mois" in delay_text:
            return number * 60 * 24 * 30
        return float("inf")

    def extract_job_info_bs4(self, card, searched_city, searched_keyword):
        try:
            title_elem = card.find("h3", class_="base-search-card__title")
            title = title_elem.get_text().strip() if title_elem else "N/A"

            company_elem = card.find("h4", class_="base-search-card__subtitle")
            company = company_elem.get_text().strip() if company_elem else "N/A"

            location_elem = card.find("span", class_="job-search-card__location")
            location = location_elem.get_text().strip() if location_elem else "N/A"

            if self.is_masked(title) or self.is_masked(company) or self.is_masked(location):
                return None

            link_elem = card.find("a", class_="base-card__full-link")
            link = link_elem["href"] if link_elem else "N/A"

            date_elem = card.find("time")
            date_raw = date_elem["datetime"] if date_elem and date_elem.has_attr("datetime") else "N/A"
            date_text = date_elem.get_text().strip() if date_elem else "N/A"

            try:
                dt = datetime.fromisoformat(date_raw.replace("Z", "+00:00"))
                date_formatted = dt.strftime("%d/%m/%Y")
            except Exception:
                date_formatted = date_raw

            return {
                "keyword": searched_keyword,
                "ville_recherchee": searched_city,
                "titre": title,
                "entreprise": company,
                "localisation": location,
                "date_publication": date_formatted,
                "delai_publication": date_text,
                "lien": link,
            }
        except Exception as error:
            logging.error("Erreur extraction BeautifulSoup: %s", error)
            return None

    def scrape_search(self, keyword, location, max_pages, duration):
        jobs = []
        tpr_value = DURATION_MAP.get(duration, "r604800")
        base_url = "https://www.linkedin.com/jobs/search"

        for page in range(max_pages):
            params = {
                "keywords": keyword,
                "location": location,
                "start": page * 25,
                "f_TPR": tpr_value,
            }
            url = f"{base_url}?" + "&".join(f"{k}={quote(str(v))}" for k, v in params.items())

            try:
                response = self.session.get(url, headers=self.headers, timeout=15)
                if response.status_code == 429:
                    time.sleep(20)
                    continue
                if response.status_code != 200:
                    continue

                soup = BeautifulSoup(response.content, "html.parser")
                job_cards = soup.find_all("div", class_="base-card")
                if not job_cards:
                    break

                for card in job_cards:
                    job = self.extract_job_info_bs4(card, location, keyword)
                    if job:
                        jobs.append(job)

                time.sleep(random.uniform(1.0, 2.2))
            except Exception as error:
                logging.error("Erreur pendant le scraping (%s - %s): %s", keyword, location, error)

        return jobs

    @staticmethod
    def deduplicate_jobs(jobs):
        seen = set()
        unique_jobs = []
        for job in jobs:
            key = (job.get("titre"), job.get("entreprise"), job.get("localisation"), job.get("lien"))
            if key not in seen:
                seen.add(key)
                unique_jobs.append(job)
        return unique_jobs


def build_excel_bytes(dataframe):
    if Workbook is None:
        return None

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "offres"

    for row in dataframe.itertuples(index=False):
        if sheet.max_row == 1 and sheet[1][0].value is None:
            sheet.append(list(dataframe.columns))
        sheet.append(list(row))

    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    return output.getvalue()


def parse_tag_input(raw_tags):
    parsed = [item.strip() for item in raw_tags.split(",") if item.strip()]
    unique = []
    seen = set()
    for item in parsed:
        lowered = item.lower()
        if lowered not in seen:
            unique.append(item)
            seen.add(lowered)
    return unique


def run_app():
    st.set_page_config(page_title="Job Scrapper", page_icon="🔎", layout="wide")
    st.title("🔎 Job Scrapper LinkedIn (sans Selenium)")
    st.caption("Outil en ligne paramétrable : durée, pages, villes et keywords (tags).")

    with st.sidebar:
        st.subheader("Paramètres")
        duration = st.radio("Durée", options=["1 semaine", "1 jour"], horizontal=True, index=0)
        max_pages = st.number_input("Nombre de pages à scraper", min_value=1, max_value=20, value=2, step=1)

        selected_cities = st.multiselect(
            "Villes",
            options=DEFAULT_CITIES,
            default=["Paris, France", "Geneva, Switzerland"],
        )
        custom_city = st.text_input("Ajouter une ville", placeholder="Ex: Toulouse, France")
        if custom_city and custom_city not in selected_cities:
            selected_cities.append(custom_city)

        default_kw_string = ", ".join(DEFAULT_KEYWORDS)
        raw_tags = st.text_input(
            "Keywords (tags, séparés par des virgules)",
            value=default_kw_string,
        )
        keywords = parse_tag_input(raw_tags)

        start_scrape = st.button("Lancer le scraping", type="primary", use_container_width=True)

    st.info(
        "Ce scraper utilise la page publique LinkedIn Jobs (requests + BeautifulSoup). "
        "Les résultats peuvent varier selon les limites anti-bot LinkedIn."
    )

    if not start_scrape:
        st.stop()

    if not selected_cities:
        st.error("Sélectionne au moins une ville.")
        st.stop()
    if not keywords:
        st.error("Ajoute au moins un keyword/tag.")
        st.stop()

    scraper = LinkedInJobScraper()
    all_jobs = []
    total_searches = len(selected_cities) * len(keywords)
    progress = st.progress(0.0)
    status = st.empty()
    current = 0

    for city in selected_cities:
        for keyword in keywords:
            current += 1
            status.write(f"Scraping `{keyword}` à `{city}` ({current}/{total_searches})...")
            jobs = scraper.scrape_search(keyword=keyword, location=city, max_pages=max_pages, duration=duration)
            all_jobs.extend(jobs)
            progress.progress(current / total_searches)

    clean_jobs = scraper.deduplicate_jobs(all_jobs)
    if not clean_jobs:
        st.warning("Aucune offre trouvée avec ces paramètres.")
        st.stop()

    dataframe = pd.DataFrame(clean_jobs)
    dataframe["delai_minutes"] = dataframe["delai_publication"].apply(scraper.parse_delay_to_minutes)
    dataframe = dataframe.sort_values(by=["ville_recherchee", "delai_minutes"], ascending=[True, True])
    dataframe = dataframe.drop(columns=["delai_minutes"])

    st.success(f"{len(dataframe)} offres trouvées (dédupliquées).")
    st.dataframe(dataframe, use_container_width=True, hide_index=True)

    csv_bytes = dataframe.to_csv(index=False).encode("utf-8")
    excel_bytes = build_excel_bytes(dataframe)

    col1, col2 = st.columns(2)
    col1.download_button(
        "Télécharger CSV",
        data=csv_bytes,
        file_name="linkedin_jobs.csv",
        mime="text/csv",
        use_container_width=True,
    )
    if excel_bytes is not None:
        col2.download_button(
            "Télécharger Excel",
            data=excel_bytes,
            file_name="linkedin_jobs.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )


if __name__ == "__main__":
    run_app()