# Prezicerea rezultatului meciurilor NBA — Etapa 1

Repository-ul conține livrabilele pentru **Etapa 1 (intermediară)** a proiectului realizat la disciplina **Inteligență Artificială și Prelucrarea Datelor**.

**Autori:** Boncan Dragoș-Eduard-Gabriel și Mihăilă Ștefan-Alexandru  
**Program:** Master Știința Datelor

## 1. Descrierea proiectului

## 2. Sursele și achiziția datelor

### Acoperirea datelor colectate

## 3. Descrierea datasetului

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