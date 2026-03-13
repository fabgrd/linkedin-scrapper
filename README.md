# Job Scrapper Web (sans Selenium)

Outil web pour scraper des offres LinkedIn Jobs (page publique) avec paramètres:
- Durée: `1 jour` ou `1 semaine`
- Nombre de pages à scraper
- Villes (multi-sélection + ajout personnalisé)
- Keywords (tags via entrée texte séparée par virgules)

## Lancer en local

```bash
cd /Users/fabiengiraudier/Documents/jobScrapper
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
streamlit run jobScrapper.py
```

Puis ouvrir l’URL locale affichée dans le terminal (souvent `http://localhost:8501`).

## Déploiement gratuit (Streamlit Community Cloud)

1. Crée un repo GitHub et pousse ces fichiers:
   - `jobScrapper.py`
   - `requirements.txt`
   - `README.md`
2. Va sur <https://share.streamlit.io/>
3. Connecte ton GitHub et choisis ton repo
4. `Main file path`: `jobScrapper.py`
5. Clique **Deploy**

Tu obtiendras un lien public gratuit du type:
`https://<ton-app>.streamlit.app`

## Limites importantes

- LinkedIn applique des protections anti-bot; les résultats peuvent varier ou être limités.
- Ce script cible la partie publique des jobs LinkedIn via `requests` + `BeautifulSoup`.
