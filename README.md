# Prezicerea rezultatului meciurilor NBA — Etapa 1

Repository-ul conține livrabilele pentru **Etapa 1 (intermediară)** a proiectului realizat la disciplina **Inteligență Artificială și Prelucrarea Datelor**.

**Autori:** Boncan Dragoș-Eduard-Gabriel și Mihăilă Ștefan-Alexandru  
**Program:** Master Știința Datelor

## 1. Descrierea proiectului

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

## 6. Rularea scripturilor

## 7. Analize planificate pentru Etapa 2

## 8. Prezentări

Directorul `docs/Etapa_1/` conține prezentările intermediare în limba română și engleză:

- fișiere `.pptx` în `Prezentari_clasice/`;
- fișiere `.ppsx` în `Prezentari_executabil/`.

## 9. Surse

- [NBA Stats](https://www.nba.com/stats)
- [nba_api — Python client](https://github.com/swar/nba_api)
- [Basketball-Reference](https://www.basketball-reference.com/)
- [nbainjuries — Python package](https://pypi.org/project/nbainjuries/)