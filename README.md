# qobuzdl-collab

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/zenin-373/qobuzdl-collab/blob/main/qobuzdl_collab_colab.ipynb)

Collaborative Qobuz downloader with **multi-token / region switching** support.

Based on [jcomicsutils/qobuz-dl](https://github.com/jcomicsutils/qobuz-dl).

## Features

- Download albums, tracks, and **full artist discographies**
- **Multiple auth tokens** (3–7 recommended) with automatic switching
- Region / availability fallback when content is locked on one account
- Always prefers **Hi-Res** (`hi-res-192` → `hi-res`)
- Clean folder structure (Structure A):

```
Artist Name/
└── 2023 - Album Title/
    ├── 01 - Track Title.flac
    ├── 02 - Track Title.flac
    └── cover.jpg
```

- Duration check (detects 30s previews and retries with other tokens)
- Quality fallback for broken CDN files
- Customizable templates, metadata, cover art
- **Google Colab** notebook included

## Requirements

- Python 3.10+
- Active Qobuz subscription(s)
- `app_id`, `secret`, and one or more `auth_token`s

## Google Colab (easiest)

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/zenin-373/qobuzdl-collab/blob/main/qobuzdl_collab_colab.ipynb)

Click the badge above, or open:  
**https://colab.research.google.com/github/zenin-373/qobuzdl-collab/blob/main/qobuzdl_collab_colab.ipynb**

Then run the cells in order:
1. **Install**
2. **Config** → put your `app_id`, `secret`, and tokens
3. **Download** → paste album / artist / track URL
4. **Zip & download** → get the files on your computer

## Local Installation

```bash
git clone https://github.com/zenin-373/qobuzdl-collab.git
cd qobuzdl-collab

# Add the download engine (one-time)
curl -o qobuz_dl/downloader.py \
  https://raw.githubusercontent.com/jcomicsutils/qobuz-dl/main/qobuz_dl/downloader.py

python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pip install -e .
```

After install you can use either:

```bash
qobuzdl-collab ...
# or
qobuz-dl ...
```

## Quick Start (local)

```bash
# 1. Interactive setup (add your tokens here)
qobuzdl-collab setup

# 2. Download
qobuzdl-collab dl https://open.qobuz.com/album/XXXX
qobuzdl-collab dl https://open.qobuz.com/artist/XXXX   # all albums
qobuzdl-collab dl al-id XXXX
qobuzdl-collab dl ar-id XXXX
qobuzdl-collab dl tr-id XXXX
```

### Multiple tokens

During `setup` (or in the Colab config cell), enter tokens comma-separated / as a list:

```
token1,token2,token3,...
```

The tool will automatically try other tokens when it detects previews or certain failures.

## Default Settings (collab version)

| Setting              | Value                                      |
|----------------------|--------------------------------------------|
| Quality              | `hi-res-192` (with fallback to `hi-res`)  |
| Folder template      | `{main_artist}/{year} - {album}`           |
| Track template       | `{track:02d} - {title}`                    |
| Duration check       | Enabled                                    |
| Quality fallback     | Enabled                                    |

## Credits

- Original work: [jcomicsutils/qobuz-dl](https://github.com/jcomicsutils/qobuz-dl)
- Collaborative improvements: zenin-373 + Grok

## License

GNU GPL v3 (same as upstream)
