# Traffic Monitoring System

यो repository को पूर्ण web application
`phase-07-traffic-monitoring-system` भित्र छ। Backend FastAPI/Python मा र frontend
React/Vite मा बनेको छ।

## आवश्यक software

- Git
- Python 3.11 वा नयाँ
- Node.js 20 वा नयाँ
- npm 10 वा नयाँ

## Project clone गर्ने

```bash
git clone https://github.com/devotedhruv/traffic-monitoring.git
cd traffic-monitoring/phase-07-traffic-monitoring-system
```

पहिले नै project download/clone गरिएको छ भने:

```bash
cd phase-07-traffic-monitoring-system
```

## Backend चलाउने

Project को `phase-07-traffic-monitoring-system` directory बाट:

### Linux/macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
python run_web.py
```

### Windows PowerShell

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
Copy-Item .env.example .env
python run_web.py
```

Backend `http://localhost:8000` मा चल्छ। Swagger API documentation:
`http://localhost:8000/docs`

> `.env` file पहिले नै छ भने copy command फेरि चलाउनु पर्दैन। आवश्यक परे
> `.env` मा video source, model path, speed limit र अन्य settings परिवर्तन गर्न
> सकिन्छ।

## Frontend चलाउने

Backend चलिरहेकै अवस्थामा **अर्को terminal** खोल्नुहोस्:

```bash
cd phase-07-traffic-monitoring-system/frontend
```

यदि terminal अहिले `phase-07-traffic-monitoring-system` मै छ भने:

```bash
cd frontend
```

### Linux/macOS

```bash
cp .env.example .env
npm install
npm run dev
```

### Windows PowerShell

```powershell
Copy-Item .env.example .env
npm install
npm run dev
```

Backend सँग frontend जोड्न `frontend/.env` मा यो value हुनुपर्छ:

```env
VITE_API_BASE_URL=http://localhost:8000
VITE_WS_URL=ws://localhost:8000/ws/live
VITE_USE_MOCKS=false
```

Frontend `http://localhost:5173` मा खोल्नुहोस्।

## Docker बाट frontend र backend दुवै चलाउने

Docker र Docker Compose install छ भने
`phase-07-traffic-monitoring-system` directory बाट:

```bash
cp .env.example .env
docker compose up --build
```

Windows PowerShell मा पहिलो command:

```powershell
Copy-Item .env.example .env
docker compose up --build
```

त्यसपछि application `http://localhost:8080` मा खुल्छ। बन्द गर्न:

```bash
docker compose down
```

## Project verify गर्ने

Backend tests:

```bash
cd phase-07-traffic-monitoring-system
TRAFFIC_AUTOSTART=false .venv/bin/python -m unittest discover -s tests -v
```

Frontend checks:

```bash
cd frontend
npm run lint
npm run test
npm run build
```

Windows मा backend test चलाउँदा:

```powershell
$env:TRAFFIC_AUTOSTART="false"
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## GitHub मा changes push गर्ने

Repository root (`traffic-monitoring`) मा फर्केर:

```bash
cd ..
```

यदि अहिले `frontend` directory मा हुनुहुन्छ भने repository root पुग्न:

```bash
cd ../..
```

Changes हेर्नुहोस्, commit गर्नुहोस् र हालको branch push गर्नुहोस्:

```bash
git status
git add .
git commit -m "docs: add frontend and backend run instructions"
git push -u origin "$(git branch --show-current)"
```

Windows PowerShell मा:

```powershell
git status
git add .
git commit -m "docs: add frontend and backend run instructions"
git push -u origin (git branch --show-current)
```

पहिलो push पछि त्यही branch का अर्को changes का लागि:

```bash
git add .
git commit -m "describe your changes"
git push
```

`git add .` ले सबै changed files stage गर्छ। केही निश्चित files मात्र push गर्न
चाहेमा `git add path/to/file` प्रयोग गर्नुहोस्। `.env`, credentials, API keys वा
camera password commit नगर्नुहोस्।
