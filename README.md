# Prezicerea rezultatului meciurilor NBA — Etapa 1

Repository-ul conține livrabilele pentru **Etapa 1 (intermediară)** a proiectului realizat la disciplina **Inteligență Artificială și Prelucrarea Datelor**.

**Autori:** Boncan Dragoș-Eduard-Gabriel și Mihăilă Ștefan-Alexandru  
**Program:** Master Știința Datelor

## 1. Descrierea proiectului

Proiectul urmărește pregătirea unui set de date istorice NBA care să permită analizarea factorilor asociați rezultatului unui meci și, în etapa finală, construirea unor modele de predicție.

Problema este formulată ca o clasificare binară:

- **Variabila țintă:** `HOME_WIN` — valoarea 1 indică o victorie a echipei gazdă, iar valoarea 0 indică o înfrângere a acesteia.
- **Unitatea de analiză:** un meci din sezonul regulat NBA.
- **Obiectivul proiectului:** investigarea relației dintre statisticile echipelor, forma recentă, programul meciurilor, odihnă și rezultatul final.

Acest repository este dedicat Etapei 1: achiziția datelor, scripturile de extragere/preprocesare, descrierea datasetului și prezentările intermediare. Analiza exploratorie completă, antrenarea și compararea modelelor ML și analiza erorilor sunt planificate pentru Etapa 2 și nu sunt prezentate ca rezultate deja obținute.

## 2. Sursele și achiziția datelor

Datele provin din surse publice și sunt colectate cu ajutorul bibliotecilor Python și al procesării paginilor HTML.

| Sursă | Script | Tipul datelor |
|---|---|---|
| NBA Stats, prin `nba_api` | `Fetch_games.py` | Loguri istorice ale meciurilor și statistici la nivel de echipă |
| NBA Stats, prin `nba_api` | `Fetch_players.py` | Statistici individuale ale jucătorilor |
| Basketball-Reference | `Scrape_bref.py` | Ratinguri de echipă, inclusiv SRS, rating ofensiv/defensiv și pace |
| Basketball-Reference | `Scrape_bref_players.py` | Statistici avansate ale jucătorilor, inclusiv BPM și VORP |
| Rapoarte NBA de accidentări, prin `nbainjuries` | `Fetch_injuries.py` | Disponibilitatea jucătorilor și statusuri de accidentare |

### Acoperirea datelor colectate

În copia de date folosită pentru proiect sunt disponibile:

- 46 de fișiere `game_log_*.csv`, pentru sezoanele 1980–81 – 2025–26;
- 46 de fișiere `player_log_*.csv`, pentru aceleași sezoane;
- 92 de pagini HTML Basketball-Reference în `data/raw/bref_html/`;
- 1.050 de rapoarte CSV de accidentări în `data/raw/injuries/`;
- `bref_team_ratings.csv`, cu ratinguri de echipă;
- `bref_player_advanced.csv`, cu statistici avansate ale jucătorilor.

Acoperirea diferă în funcție de sursă. De exemplu, rapoartele de accidentări nu acoperă întreaga perioadă istorică, iar unele sezoane NBA au fost scurtate.

## 3. Descrierea datasetului

Fișierul de date curățate inclus în repository este:

`data/processed/games_clean.csv`

Caracteristicile sale sunt:

| Caracteristică | Valoare |
|---|---:|
| Număr de meciuri | 44.237 |
| Număr de coloane | 161 |
| Features de bază | 50 |
| Perioadă | 1985–86 – 2025–26 |
| Sezoane | 41 |
| Tipul meciurilor | Sezon regulat |
| Variabila țintă | `HOME_WIN` |

Caracteristicile sunt organizate în trei categorii:

- `H_*` — statistici pentru echipa gazdă;
- `A_*` — statistici pentru echipa oaspete;
- `D_*` — diferențe între statisticile celor două echipe.

Datasetul folosește o împărțire cronologică a meciurilor:

| Subset | Perioadă | Număr de meciuri |
|---|---|---:|
| Training | până la sezonul 2023–24 | 41.787 |
| Validation | sezonul 2024–25 | 1.225 |
| Testing | sezonul 2025–26 | 1.225 |

**Notă privind fișierele procesate:** `Build_dataset.py` generează fișierul `data/processed/games.csv`. La testarea curentă, acesta a avut 47.218 rânduri și 178 de coloane. `games_clean.csv` este o versiune separată, cu 44.237 rânduri și 161 de coloane, folosită pentru descrierea datasetului din prezentarea Etapei 1. Cele două fișiere nu trebuie considerate identice. Fișierul `games.csv` este exclus din Git prin `.gitignore`; `games_clean.csv` este fișierul procesat păstrat în repository.

## 4. Structura repository-ului

```text
Prezicere_meciuri_NBA/
├── extraction/
│   ├── Build_dataset.py
│   ├── Fetch_games.py
│   ├── Fetch_injuries.py
│   ├── Fetch_players.py
│   ├── Roaster_features.py
│   ├── Scrape_bref.py
│   └── Scrape_bref_players.py
├── data/
│   ├── raw/
│   │   ├── bref_html/
│   │   ├── injuries/
│   │   ├── game_log_*.csv
│   │   ├── player_log_*.csv
│   │   ├── bref_team_ratings.csv
│   │   └── bref_player_advanced.csv
│   └── processed/
│       └── games_clean.csv
├── docs/
│   └── Etapa_1/
│       ├── Prezentari_clasice/
│       │   ├── Prezentare_etapa_1_ro.pptx
│       │   └── Prezentare_etapa_1_eng.pptx
│       └── Prezentari_executabil/
│           ├── Prezentare_etapa_1_ro.ppsx
│           └── Prezentare_etapa_1_eng.ppsx
├── .gitignore
├── requirements.txt
└── README.md
```

## 5. Instalare și configurare

Este recomandată utilizarea Python 3.12 sau a unei versiuni compatibile cu pachetele din `requirements.txt`.

### Linux / WSL

Creează și activează un mediu virtual:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Instalează dependențele:

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Pentru componenta `nbainjuries`, care folosește JPype și Java Virtual Machine, este necesar un Java Runtime Environment. În Ubuntu/WSL se poate instala astfel:

```bash
sudo apt update
sudo apt install -y default-jre
```

Verificarea importurilor principale:

```bash
python -c "import numpy, pandas, nba_api, nbainjuries, requests; print('Importurile sunt OK')"
```

## 6. Rularea scripturilor

Comenzile se execută din directorul rădăcină al repository-ului.

```bash
python extraction/Fetch_games.py
python extraction/Fetch_players.py
python extraction/Scrape_bref.py
python extraction/Scrape_bref_players.py
python extraction/Fetch_injuries.py
python extraction/Build_dataset.py
```

Scripturile de colectare verifică existența unor fișiere locale și pot sări peste fișierele care au fost deja descărcate. Prin urmare, mesajele de tipul „există deja, sar peste” indică faptul că fișierul respectiv este deja prezent.

`Build_dataset.py` salvează rezultatul în `data/processed/games.csv`. Acest fișier este ignorat de Git în configurația repository-ului. Nu îl confunda cu `games_clean.csv`, descris în secțiunea 3.

`Roaster_features.py` conține funcționalități suplimentare pentru caracteristici legate de lot și accidentări. În versiunea curentă, modulul nu este apelat automat de `Build_dataset.py`; integrarea acestor caracteristici în pipeline-ul principal rămâne de evaluat.

## 7. Analize planificate pentru Etapa 2

În etapa finală sunt planificate următoarele activități:

- analiza exploratorie a distribuției meciurilor și a calității datelor;
- analiza avantajului terenului propriu și a evoluției statisticilor pe sezoane;
- investigarea relației dintre caracteristicile echipelor și rezultatul meciurilor;
- evaluarea influenței perioadelor de odihnă și a meciurilor consecutive;
- antrenarea și compararea mai multor modele de clasificare;
- evaluarea modelelor folosind metrici precum Accuracy, ROC-AUC, Log-loss și Brier Score;
- analiza erorilor și a calibrării probabilităților.

Aceste activități reprezintă direcții de lucru pentru Etapa 2; repository-ul de față nu include încă rezultatele EDA sau modelele antrenate.

## 8. Prezentări

Directorul `docs/Etapa_1/` conține prezentările intermediare în limba română și engleză:

- fișiere `.pptx` în `Prezentari_clasice/`;
- fișiere `.ppsx` în `Prezentari_executabil/`.

## 9. Surse

- [NBA Stats](https://www.nba.com/stats)
- [nba_api — Python client](https://github.com/swar/nba_api)
- [Basketball-Reference](https://www.basketball-reference.com/)
- [nbainjuries — Python package](https://pypi.org/project/nbainjuries/)