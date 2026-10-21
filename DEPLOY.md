# Deploying DocWeave

Two ways to give people a link:

| | **A. Permanent link (cloud)** | **B. Temporary link (your laptop)** |
|---|---|---|
| Works when your laptop is off | Yes | No |
| Model | Hosted: Groq free tier (Llama 3.3 70B) | Your local Ollama models |
| Cost | $0 | $0 |
| Setup | ~30 min, once | ~10 min |

Cloud hosts have no GPU, so the cloud version cannot run Ollama; it calls a hosted model API instead.

---

## A. Permanent link on Render (free)

How it works: Render builds the `Dockerfile` from your GitHub repository and runs one container that serves the
React app and the Flask backend on a single port. The container calls Groq's API with a key you store as a secret
in Render. Measured memory use is about 220 MB while a run is in progress, so Render's free 512 MB instance is enough.

> Hugging Face Docker Spaces are no longer free, which is why this guide uses Render.

### Step 1. Groq key (the AI model, free, no card)
1. Sign up at <https://console.groq.com>.
2. **API Keys** -> **Create API Key**. Copy the key (starts with `gsk_`). It is shown once.

### Step 2. Put the code on GitHub
Render builds from GitHub, so the deployment files must be committed and pushed.
Pull first, because your teammates also push to this repository:
```powershell
git pull
git add Dockerfile .dockerignore render.yaml requirements-deploy.txt DEPLOY.md start_public.ps1 frontend src
git commit -m "Add hosted deployment (Docker, Groq, public mode)"
git push
```
**Render needs to be able to read the repository.** The team repository (`Gnanesh-12/...`) is currently **private**, so pick one:
- **Easiest:** the repo owner makes it public (GitHub -> repo **Settings** -> **Danger Zone** -> **Change visibility** -> Public).
  No API keys are stored in the code (checked), only placeholders.
- **Or your own public copy:** create an empty **public** repo under your own GitHub account (for example `docweave`), then:
  ```powershell
  git remote add mine https://github.com/<your-username>/docweave.git
  git push mine main
  ```
  and use that URL in Step 3.
- **Or keep it private:** in Step 3 choose **Git Provider** instead of *Public Git Repository* and connect your GitHub account.
  This only works for repositories your own account owns or has authorised Render to access.

### Step 3. Create the Render service
1. Sign up at <https://render.com> (GitHub login is easiest). Render may ask for a card once for a $1 verification
   hold that is cancelled immediately; the free plan stays free.
2. **New +** -> **Web Service**.
3. Choose **Public Git Repository**, paste your repo URL, click **Connect**:
   `https://github.com/Gnanesh-12/DocAgent-A-Multi-Agent-System-for-Automated-Code-Documentation-Generation`
4. Settings:
   - **Name:** `docweave`
   - **Language / Runtime:** **Docker** (detected from the `Dockerfile`)
   - **Branch:** `main`
   - **Instance Type:** **Free**
5. Under **Environment Variables** click **Add**:
   - Key: `GROQ_API_KEY`  Value: your `gsk_...` key
6. Click **Deploy Web Service**.

### Step 4. Wait and get the link
The first build takes about 5 to 10 minutes (watch the **Logs** tab). When it says **Live**, your link is at the top of the page,
like `https://docweave-xxxx.onrender.com`. That is the permanent link.

### Step 5. Test
Open the link, paste `https://github.com/pypa/sampleproject.git`, and the model dropdown should show
**llama-3.3-70b-versatile (hosted on Groq)**. Start a run; expect several minutes.

### Updating later
Push new commits to `main`, then in Render click **Manual Deploy** -> **Deploy latest commit**.

### What the public version does and does not do
- Only public `https://github.com/<owner>/<repo>` links are accepted.
- Only hosted models are offered (no Ollama in the cloud).
- A repo with more than **40 undocumented components** is refused with a clear message (it protects the shared free quota).
  Change it with the environment variable `DOCWEAVE_MAX_COMPONENTS`.
- **One run at a time.** Server state is shared, so a second visitor is told a run is in progress.
- The endpoints that accept arbitrary settings (`/api/start`, `/api/test_api`, ...) are disabled.
- Optional environment variables: `DOCWEAVE_GROQ_MODELS` (comma-separated Groq model ids; use it if Groq retires the default
  `llama-3.3-70b-versatile`), `ANTHROPIC_API_KEY` (adds Claude models; **costs money per visitor run**, so leave it unset on a public link).

### Limits to expect
- **Sleeping.** A free Render service sleeps after 15 minutes without traffic. The next visit takes about a minute to wake it.
  Open the link once a few minutes before showing it to someone.
- **Rate limits.** Groq's free tier is limited (reportedly about 30 requests and 12,000 tokens per minute for this model; check
  Groq's current limits). In practice that is roughly **one component per minute**, so a 7-component repo takes several minutes.
  The client retries automatically when told to slow down. If the daily quota is used up, runs fail until it resets.
  The free quota cannot cost you money. It just runs out.
- **Small machine.** Free instances have 512 MB of memory and a fraction of a CPU: the first page load and repository cloning are slow.
  Keep demo repositories small.
- **Different model from the evaluation.** The demo uses a hosted 70B model, not the local 7B model used in the evaluation.

### Troubleshooting
- *Build fails:* open the **Logs** tab and send the first error line to whoever maintains the project.
- *"No models available":* `GROQ_API_KEY` is missing or misspelled in the Render environment variables. Fix it and redeploy.
- *A run fails with a rate-limit message:* wait a minute and try again, or use a smaller repository.
- *"Out of memory" in the logs:* use a smaller repository, or upgrade the instance type.
- *Page takes a minute to load:* the service was asleep.

---

## B. Temporary link from your own computer (uses local Ollama)

Good for a live demo with the local models. The link works only while your computer is on and the script is running.

1. Install the tunnel tool once (free, no account), then reopen PowerShell:
   ```powershell
   winget install Cloudflare.cloudflared
   ```
2. Make sure Ollama is running and a model is installed.
3. Start sharing:
   ```powershell
   .\start_public.ps1
   ```
   It builds the frontend, starts the server in public mode, prints a **login** and a link like `https://something.trycloudflare.com`.
4. Send the link and the login separately (a password inside the link breaks the page). Stop with `Ctrl + C`.

Options: `-Password "..."` to choose the password, `-NoTunnel` to only run the production server locally.
The link changes every time you start it.
