# Run the Geospatial GUI on Windows

This guide walks you through running the website on a Windows PC **from scratch**. 

**What you will end up with:** a local website at **[http://127.0.0.1:8765/](http://127.0.0.1:8765/)** that you open in Chrome, Edge, or Firefox.

---

## What you need before you start


| Item                  | Required?   | Notes                                                                |
| --------------------- | ----------- | -------------------------------------------------------------------- |
| Windows 10 or 11      | Yes         | This guide is Windows-only                                           |
| Internet connection   | Yes         | For downloads and Census data                                        |
| ~2 GB free disk space | Yes         | Python, libraries, and project files                                 |
| Census API key        | Recommended | Free; needed for neighborhood demographics on the dashboard          |
| Ollama                | Optional    | Only for AI chat on the dashboard; maps and analysis work without it |
| VS Code               | Optional    | Helpful for editing settings; Notepad works too                      |


---

## Part 1 — Download the project from GitHub

GitHub is where the project files are stored online. You will download a ZIP file and unzip it on your computer. You do **not** need to install Git for this method.

### 1.1 Open the repository in your browser

1. Open your web browser (Chrome, Edge, or Firefox).
2. Go to: **[https://github.com/manyas207/Geospatial-GUI](https://github.com/manyas207/Geospatial-GUI)**
3. You should see a page titled something like **Geospatial-GUI** with folders such as `backend`, `web`, and `docs`.

### 1.2 Download the ZIP file

1. Near the top-right of the file list, click the green **Code** button.
2. In the menu that opens, click **Download ZIP**.
3. Your browser will save a file named something like `Geospatial-GUI-main.zip` (the exact name depends on the default branch).
4. Wait until the download finishes. On Windows, it usually goes to your **Downloads** folder.

### 1.3 Extract (unzip) the project

1. Open **File Explorer** (folder icon on the taskbar, or press `Win + E`).
2. Go to **Downloads**.
3. Find `Geospatial-GUI-main.zip` (or similar).
4. **Right-click** the ZIP file → **Extract All…**
5. Choose a simple location, for example:
  - `C:\Users\YourName\Desktop\Geospatial-GUI`
  - or `C:\Users\YourName\Documents\Geospatial-GUI`
6. Click **Extract**.
7. Open the new folder. You should see files including:
  - `serve.py`
  - `requirements.txt`
  - `.env.example`
  - folders named `backend`, `web`, `models`, `docs`

**Important:** Remember this folder path. You will open a terminal *inside* this folder later. In the examples below we use:

```text
C:\Users\YourName\Desktop\Geospatial-GUI\Geospatial-GUI-main
```

Replace `YourName` and the folder name with your actual path. If your extracted folder is named `Geospatial-GUI-1` instead of `Geospatial-GUI-main`, that is fine — use whatever name you see.

### 1.4 (Optional) Install Git later

If you prefer updating the project with `git pull` in the future, you can install Git from [https://git-scm.com/download/win](https://git-scm.com/download/win) and clone instead of using ZIP. For a first run, the ZIP method above is enough.

---

## Part 2 — Install Python

Python runs the server that powers the website. You need **Python 3.10 or newer** (3.11 or 3.12 is a good choice).

### 2.1 Download the installer

1. Go to **[https://www.python.org/downloads/](https://www.python.org/downloads/)**
2. Click **Download Python 3.x.x** (the latest 3.10+ version shown).
3. Run the downloaded installer (e.g. `python-3.12.x-amd64.exe`).

### 2.2 Run the installer (critical steps)

1. On the **first** screen of the installer, check the box at the bottom:
  - **Add python.exe to PATH**  
   This is required. If you skip it, the terminal will not find Python.
2. Click **Install Now** (or **Customize installation** if you prefer, then ensure **pip** is included).
3. Wait for installation to finish, then click **Close**.

### 2.3 Verify Python works

1. Press `Win + S`, type **PowerShell**, and open **Windows PowerShell** (not “PowerShell ISE” unless you already use it).
2. Type the following and press **Enter**:
  ```powershell
   python --version
  ```
3. You should see something like `Python 3.12.3`. If you see an error (“python is not recognized”), close PowerShell, **reboot your PC**, and try again. If it still fails, reinstall Python and make sure **Add python.exe to PATH** was checked.
4. Also check pip (Python’s package installer):
  ```powershell
   python -m pip --version
  ```
   You should see a line mentioning `pip` and a version number.

**If `python` does not work but `py` does:** On some PCs you must use `py` instead of `python`. Try `py --version`. For the rest of this guide, replace `python` with `py` wherever it appears (e.g. `py -m pip install …` and `py serve.py`).

---

## Part 3 — (Optional) Install Visual Studio Code

VS Code is a free editor. You can use **Notepad** instead if you only need to edit one settings file (`.env`).

### 3.1 Download and install

1. Go to **[https://code.visualstudio.com/](https://code.visualstudio.com/)**
2. Click **Download for Windows**.
3. Run the installer and accept the defaults (you can leave all checkboxes as they are).
4. Launch **Visual Studio Code** from the Start menu.

### 3.2 Open the project folder in VS Code

1. In VS Code: **File** → **Open Folder…**
2. Select the folder you extracted in Part 1 (the one that contains `serve.py`).
3. Click **Select Folder**.

You can open a terminal inside VS Code with **Terminal** → **New Terminal**. That terminal already starts in your project folder, which is convenient for the next steps.

---

## Part 4 — Install the project’s Python libraries

The app depends on extra packages (FastAPI, geospatial tools, etc.). They are listed in `requirements.txt`.

### 4.1 Open PowerShell in the project folder

**Method A — From File Explorer (easiest for beginners):**

1. Open File Explorer and navigate to your project folder (the one with `serve.py`).
2. Click the address bar at the top, type `powershell`, and press **Enter**.
  A blue PowerShell window opens with that folder as the current directory.

**Method B — From VS Code:**

1. Open the project in VS Code (Part 3).
2. **Terminal** → **New Terminal**.

**Method C — Change directory manually:**

```powershell
cd C:\Users\YourName\Desktop\Geospatial-GUI\Geospatial-GUI-main
```

(Use your real path.)

### 4.2 Install dependencies

In PowerShell, run:

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

This may take several minutes. You will see many lines scroll by; that is normal.

**If installation fails** on packages like `rasterio` or `geopandas`:

- Confirm you are on **64-bit Windows** and used the **64-bit** Python installer from python.org.
- Confirm `python --version` shows 3.10 or higher.
- Try running PowerShell **as Administrator** (right-click PowerShell → **Run as administrator**), `cd` to the project folder again, and rerun the `pip install` command.
- If you still get errors, copy the last 20–30 lines of the error message and ask for help (include your Python version).

When finished, you should see no red “ERROR” lines at the end.

---

## Part 5 — Configure environment settings (`.env`)

The app reads secret keys and options from a file named `.env` in the project root.

### 5.1 Create `.env` from the example file

In the same PowerShell window (still in the project folder), run:

```powershell
copy .env.example .env
```

This creates a new file `.env` you can edit. (If you use Command Prompt instead of PowerShell, the command is the same: `copy .env.example .env`.)

### 5.2 Get a free Census API key (recommended)

Demographics on the **Heat & Equity** dashboard need a Census API key. The app still runs without it, but many numbers will show as dashes (`—`).

1. Open **[https://api.census.gov/data/key_signup.html](https://api.census.gov/data/key_signup.html)** in your browser.
2. Fill in your name and email.
3. Submit the form. You will receive an email with your API key (a long string of letters and numbers).
4. Keep that key handy for the next step.

### 5.3 Edit `.env` and paste your Census key

**Using Notepad:**

1. In File Explorer, go to your project folder.
2. If you do not see `.env`, turn on **Hidden items** on the View tab (Windows 11: **View** → **Show** → **Hidden items**).
3. Right-click `.env` → **Open with** → **Notepad**.
4. Find the line:
  ```env
   CENSUS_API_KEY=your_census_api_key_here
  ```
5. Replace `your_census_api_key_here` with your real key (no spaces around `=`). Example:
  ```env
   CENSUS_API_KEY=abcd1234efgh5678ijkl9012mnop3456qrst
  ```
6. **File** → **Save**, then close Notepad.

**Using VS Code:**

1. In the left sidebar, click `.env`.
2. Edit `CENSUS_API_KEY` as above.
3. Press `Ctrl + S` to save.

**Leave the Ollama lines as-is for now** unless you set up Ollama in Part 7. Defaults are fine:

```env
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=llama3.2
```

---

## Part 6 — Start the website

### 6.1 Run the server

In PowerShell, with your project folder as the current directory:

```powershell
python serve.py
```

You should see output similar to:

```text
Project: Geospatial-GUI-main
Serving API + web from: C:\Users\...\Geospatial-GUI-main
Open: http://127.0.0.1:8765/

POST /api/projects - multi-city LST portfolio (Ask -> Heat & Equity)
```

**Leave this PowerShell window open.** Closing it stops the website.

### 6.2 Open the site in your browser

1. Open Chrome, Edge, or Firefox.
2. In the address bar, type exactly:
  ```text
   http://127.0.0.1:8765/
  ```
3. Press **Enter**.

You should see the **Geospatial GUI** dashboard with a sidebar (e.g. **Ask**, **Demo**).

### 6.3 Quick test without uploading data

1. Click **Demo** in the sidebar.
2. You should see maps and charts for preset cities.
  This confirms the server and web UI are working.

### 6.4 Stop the server when you are done

1. Click the PowerShell window where `serve.py` is running.
2. Press `Ctrl + C`.
3. If asked to terminate the batch job, type `Y` and press **Enter**.

---

## Part 7 — (Optional) AI chat with Ollama

Dashboard **chat** can use a local AI model via [Ollama](https://ollama.com/). **Maps, uploads, and LST analysis work fine without Ollama** — chat will fall back to a short numeric summary instead of a full AI answer.

### 7.1 Install Ollama

1. Go to **[https://ollama.com/](https://ollama.com/)** and download the Windows installer.
2. Install and launch Ollama (it often runs in the system tray near the clock).

### 7.2 Download the language model

Open a **new** PowerShell window and run:

```powershell
ollama pull llama3.2
```

Wait until the download completes.

### 7.3 Confirm Ollama is running

Ollama usually starts automatically after install. If chat still fails, run:

```powershell
ollama serve
```

Leave that window open, or rely on the Ollama desktop app.

Your `.env` should already contain:

```env
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=llama3.2
```

Restart the website (`python serve.py`) after installing Ollama, then try chat on **Demo** or **Your project**.

---

## Part 8 — Using the app (short overview)


| Sidebar item     | What it does                                                                                   |
| ---------------- | ---------------------------------------------------------------------------------------------- |
| **Ask**          | Choose an analysis model, enter a US city as `City, ST`, upload Landsat GeoTIFFs, run analysis |
| **Demo**         | Explore 11 preset cities without uploading files                                               |
| **Your project** | Appears after you finish processing at least one city on **Ask**                               |


**Typical workflow on Ask:**

1. Select an analysis model (e.g. **Land Surface Temperature** or **OBIA Land Cover**).
2. Enter a city like `Round Rock, TX`.
3. Upload the files required for that model (Landsat `ST_B10`, `SR_B4`, `SR_B5` for LST; multispectral GeoTIFF + training shapefile for OBIA).
4. Click **Add city to project** (step 1).
5. Click **Run … for city** when step 2 appears (label matches the model).
6. When processing finishes, you are taken to **Your project** with maps and charts.

After code updates: restart `python serve.py` and hard-refresh the browser (`Ctrl + Shift + R`).

---

## Part 9 — Running the site again later

You do not need to reinstall Python or pip every time. After the first setup:

1. Open PowerShell in the project folder (Part 4.1).
2. (Optional) Start Ollama if you use chat.
3. Run:
  ```powershell
   python serve.py
  ```
4. Open **[http://127.0.0.1:8765/](http://127.0.0.1:8765/)** in your browser.
5. When finished, press `Ctrl + C` in PowerShell to stop the server.

If you downloaded a **new ZIP** from GitHub to get updates, extract it to a new folder (or replace the old files), then run `pip install -r requirements.txt` again in case dependencies changed.

---

## Troubleshooting


| What you see                               | What to try                                                                                       |
| ------------------------------------------ | ------------------------------------------------------------------------------------------------- |
| `python is not recognized`                 | Reinstall Python with **Add python.exe to PATH** checked; reboot; or use `py` instead of `python` |
| `Missing serve.py` or wrong folder         | `cd` into the folder that contains `serve.py`, not a parent folder                                |
| Port 8765 already in use                   | Another `python serve.py` may still be running — close other PowerShell windows or end the process in Task Manager |
| `ImportError: city_run_stats` on startup   | Update to latest code and restart `python serve.py` |
| Blank page or old layout                   | Hard-refresh the browser: `Ctrl + Shift + R` (cache-busted `app.js` / `index.html`) |
| Demographics show `—`                      | Set `CENSUS_API_KEY` in `.env`, save, restart `python serve.py`                                   |
| Could not geocode address                  | Use `City, ST` format, e.g. `Austin, TX`                                                          |
| Chat says Ollama unavailable               | Install/start Ollama and run `ollama pull llama3.2`; restart `serve.py`                           |
| `pip install` fails on geospatial packages | Use 64-bit Python 3.10+ from python.org; try Administrator PowerShell                             |
| ZIP extract blocked                        | Right-click ZIP → **Properties** → if you see **Unblock**, check it → **Apply** → extract again   |


**API documentation (when the server is running):** [http://127.0.0.1:8765/docs](http://127.0.0.1:8765/docs)

**More technical docs:**

- [README.md](../README.md) — overview and configuration reference
- [API.md](API.md) — REST endpoints
- [ARCHITECTURE.md](ARCHITECTURE.md) — how the system is organized
- [DATA.md](DATA.md) — data folders and external APIs

---

## Checklist 

- Downloaded ZIP from [https://github.com/manyas207/Geospatial-GUI](https://github.com/manyas207/Geospatial-GUI) and extracted it
- Installed Python 3.10+ with **Add to PATH**
- `python --version` works in PowerShell
- Ran `python -m pip install -r requirements.txt` in the project folder
- Ran `copy .env.example .env`
- Set `CENSUS_API_KEY` in `.env`
- Ran `python serve.py` and left the window open
- Opened [http://127.0.0.1:8765/](http://127.0.0.1:8765/) in the browser
- (Optional) Installed Ollama and `ollama pull llama3.2` for chat

When all required boxes are checked, you are running the Geospatial GUI locally on Windows.