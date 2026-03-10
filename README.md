<div align="center">

# 🔍 Vison

### Reverse Multimedia Search Engine

*Research-oriented, open-source search engine bringing reverse multimedia search to small & mid-scale enterprises.*

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Node.js](https://img.shields.io/badge/Node.js-20+-339933?style=for-the-badge&logo=node.js&logoColor=white)](https://nodejs.org)
[![TensorFlow](https://img.shields.io/badge/TensorFlow-2.15-FF6F00?style=for-the-badge&logo=tensorflow&logoColor=white)](https://tensorflow.org)
[![OpenVINO](https://img.shields.io/badge/Intel-OpenVINO-0068B5?style=for-the-badge&logo=intel&logoColor=white)](https://docs.openvino.ai)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](LICENSE)

---

</div>

## 🌟 Features

| Feature | Description |
|---------|-------------|
| 🖼️ **Reverse Image Search** | Upload an image to find visually similar content using MobileNetV2 feature extraction |
| 🎵 **Audio Fingerprinting** | Search by audio similarity using MFCC, spectral centroid, and chroma features |
| 🎬 **Video Search** | Find similar videos via keyframe sampling and averaged frame features |
| 📝 **NLP Text Search** | TF-IDF powered text search across metadata, titles, and keywords |
| 🕷️ **Web Crawler** | Selenium-based crawler for discovering and indexing multimedia from websites |
| ⚡ **Intel OpenVINO** | Optimized CPU inference with automatic TensorFlow fallback |
| 🔎 **FAISS Vector Search** | Facebook's billion-scale similarity search for lightning-fast retrieval |
| 🎨 **Premium UI** | Dark-mode glassmorphism interface with drag-and-drop upload |

## 🏗️ Architecture

```
┌──────────────────────────────────────────────────┐
│          Node.js Frontend (Express + EJS)         │
│     Drag & Drop Upload · Search · Crawler UI      │
│                 Port 3000                         │
└──────────────────────┬───────────────────────────┘
                       │ REST API (Proxy)
┌──────────────────────▼───────────────────────────┐
│            Python Backend (FastAPI)               │
│                 Port 8000                         │
│                                                   │
│  ┌──────────┐ ┌────────────┐ ┌────────────────┐  │
│  │ NLP/TF-  │ │ TF/OpenVINO│ │ Selenium Web   │  │
│  │ IDF Text │ │ Feature    │ │ Crawler        │  │
│  │ Engine   │ │ Extractor  │ │                │  │
│  └────┬─────┘ └─────┬──────┘ └───────┬────────┘  │
│       │             │                │            │
│  ┌────▼─────────────▼────────────────▼─────────┐  │
│  │       FAISS Vector Store + SQLite DB        │  │
│  └─────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────┘
```

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| **ML/AI** | TensorFlow 2.15, Intel OpenVINO, MobileNetV2, MFCC |
| **Search** | FAISS (Facebook), TF-IDF (scikit-learn) |
| **Backend** | Python 3.11, FastAPI, SQLite |
| **Crawler** | Selenium, BeautifulSoup4, Headless Chrome |
| **Frontend** | Node.js, Express, EJS |
| **Media** | Pillow, librosa, OpenCV |
| **Deploy** | Docker, Docker Compose |

## 📁 Project Structure

```
vison/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI entry point
│   │   ├── config.py            # Central configuration
│   │   ├── ml/
│   │   │   ├── feature_extractor.py  # TF/OpenVINO image, audio, video features
│   │   │   └── text_analyzer.py      # NLP text processing & TF-IDF
│   │   ├── search/
│   │   │   ├── vector_store.py       # FAISS vector similarity search
│   │   │   └── database.py           # SQLite metadata store
│   │   ├── crawler/
│   │   │   ├── crawler.py            # Selenium web crawler
│   │   │   └── media_downloader.py   # Media file downloader
│   │   └── routes/
│   │       ├── search.py             # Search API endpoints
│   │       ├── crawler.py            # Crawler management API
│   │       └── index.py              # Index management API
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── server.js                # Express server
│   ├── views/index.ejs          # Main page template
│   ├── public/
│   │   ├── css/style.css        # Premium dark theme
│   │   └── js/app.js            # Client-side logic
│   ├── package.json
│   └── Dockerfile
├── docker-compose.yml
└── README.md
```

## 🚀 Getting Started

### Prerequisites

- Python 3.11+
- Node.js 20+
- Chrome/Chromium (for web crawler)

### Quick Start (Development)

**1. Start the Python Backend:**

```bash
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
```

**2. Start the Node.js Frontend:**

```bash
cd frontend
npm install
npm start
```

**3. Open your browser:**

```
http://localhost:3000
```

### Docker Deployment

```bash
docker-compose up --build
```

## 📡 API Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/search/upload` | POST | Upload media file for reverse search |
| `/api/search/text?q=` | GET | Text-based metadata search |
| `/api/search/results/{id}` | GET | Get detailed result info |
| `/api/crawler/start` | POST | Start web crawl session |
| `/api/crawler/status` | GET | Get crawler status |
| `/api/crawler/stop` | POST | Stop active crawl |
| `/api/index/stats` | GET | Index statistics |
| `/api/index/add` | POST | Manually add media to index |
| `/api/index/items` | GET | List indexed items |
| `/api/index/{id}` | DELETE | Remove item from index |
| `/api/health` | GET | Health check |

> 📖 Full interactive API docs available at `http://localhost:8000/docs` (Swagger UI)

## 🔍 How It Works

### Reverse Image Search
1. Upload image → Preprocessed to 224×224 RGB
2. MobileNetV2 extracts 1280-dimensional feature vector
3. L2-normalized for cosine similarity
4. FAISS searches indexed vectors for nearest neighbors
5. Returns ranked results with similarity scores

### Audio Search
1. Upload audio → Loaded at 22050 Hz sample rate
2. Extract MFCC (40 coefficients), spectral centroid, spectral rolloff, chroma, zero-crossing rate
3. Aggregate statistics (mean, std, max, min) → 512-dim feature vector
4. FAISS similarity search across audio index

### Video Search
1. Upload video → Sample up to 10 evenly-spaced keyframes
2. Extract MobileNetV2 features from each keyframe
3. Average all frame features → Single 1280-dim vector
4. FAISS similarity search across video index

### Web Crawler
1. Selenium navigates target URL with headless Chrome
2. BeautifulSoup parses HTML for `<img>`, `<audio>`, `<video>`, and media links
3. Downloads discovered media, extracts features, generates thumbnails
4. Stores metadata in SQLite, vectors in FAISS
5. Follows same-domain links up to configured depth

## ⚙️ Configuration

Key settings in `backend/app/config.py` or via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `DEBUG` | `true` | Enable debug logging |
| `USE_OPENVINO` | `true` | Try Intel OpenVINO acceleration |
| `CRAWLER_MAX_DEPTH` | `3` | Maximum crawl depth |
| `CRAWLER_MAX_PAGES` | `100` | Maximum pages per crawl |
| `CRAWLER_DELAY_SECONDS` | `1.0` | Politeness delay between requests |
| `DEFAULT_TOP_K` | `20` | Default search results count |

## 🗺️ Roadmap

- [ ] GPU acceleration (CUDA/TensorRT)
- [ ] Distributed crawling with task queue
- [ ] Search result clustering
- [ ] User accounts and search history
- [ ] REST API authentication
- [ ] Support for more model architectures (ResNet, EfficientNet)
- [ ] Real-time indexing webhooks
- [ ] Elasticsearch integration for hybrid search
- [ ] Browser extension for right-click reverse search

## 📄 License

This project is licensed under the MIT License.

---

<div align="center">
  <b>Built with ❤️ for the open-source community</b>
  <br>
  <sub>Powered by TensorFlow · Intel OpenVINO · FAISS · FastAPI</sub>
</div>
