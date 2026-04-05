# Deployment Guide

## Platform: Hugging Face Spaces (Primary — Recommended)

Hugging Face Spaces provides **free, always-on** hosting for Streamlit apps.
There is no sleep policy, no credit card required, and the URL never changes.

| Property | Detail |
|---|---|
| URL format | `https://huggingface.co/spaces/YOUR_USERNAME/finance-intelligence` |
| Sleep / hibernation | **Never** |
| Cost | **Free** |
| Time to deploy | ~10 min |
| Python | 3.10 (managed) |
| Secrets | Set via HF dashboard → injected as `os.environ` |

---

### Prerequisites

- A GitHub account with the repo pushed as **public**
- A Hugging Face account — [huggingface.co/join](https://huggingface.co/join) (free)
- An OpenAI API key (or Azure OpenAI credentials)

---

### Step 1 — Push the repo to GitHub

```bash
git init
git add .
git commit -m "Initial commit — Finance Intelligence System"
git remote add origin https://github.com/YOUR_USERNAME/finance-intelligence.git
git push -u origin main
```

---

### Step 2 — Create a Hugging Face Space

1. Go to [huggingface.co/new-space](https://huggingface.co/new-space)
2. Fill in the form:
   - **Space name:** `finance-intelligence`
   - **License:** MIT
   - **SDK:** Streamlit  ← **important**
   - **SDK version:** 1.35.0
3. Click **Create Space**

---

### Step 3 — Connect your GitHub repo

In your Space:

1. Go to **Files** tab → click **...** → **Link GitHub repository**
2. Authenticate and select your `finance-intelligence` repo
3. Select branch: `main`

Every `git push` to `main` will now trigger an automatic redeploy.

> **Alternative:** Clone the HF Space repo directly and push there instead of linking GitHub.
> ```bash
> git remote add hf https://huggingface.co/spaces/YOUR_USERNAME/finance-intelligence
> git push hf main
> ```

---

### Step 4 — Add secrets

In your Space, go to **Settings → Variables and Secrets → New secret**:

| Secret name | Value |
|---|---|
| `OPENAI_API_KEY` | Your OpenAI API key |
| `OPENAI_MODEL` | `gpt-3.5-turbo` (or `gpt-4o-mini`) |

For Azure OpenAI, add instead:

| Secret name | Value |
|---|---|
| `USE_AZURE` | `true` |
| `AZURE_OPENAI_ENDPOINT` | `https://YOUR_RESOURCE.openai.azure.com/` |
| `AZURE_OPENAI_API_KEY` | Your Azure OpenAI key |
| `AZURE_OPENAI_DEPLOYMENT` | Your deployment name |

> Secrets are injected as `os.environ` — the app's `config.py` reads them automatically.

---

### Step 5 — Verify the deployment

1. Go to your Space's **App** tab
2. Wait ~2 minutes for the first build to complete
3. You should see the Finance Intelligence System home screen
4. Test with the sample CSV or a question in the Finance Assistant tab

Your live URL: `https://huggingface.co/spaces/YOUR_USERNAME/finance-intelligence`

---

### Step 6 — Future deployments

```bash
git add .
git commit -m "Your change description"
git push origin main   # triggers automatic redeploy on HF Spaces
```

Build logs are visible in the Space's **Logs** tab.

---

### Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| "Module not found" | Missing package | Add to `requirements.txt`, push again |
| "Secrets not found" | Env var not set | Add in Settings → Variables and Secrets |
| App shows blank screen | Build error | Check Logs tab for traceback |
| CSV upload fails | File > 200 MB | Reduce file size; HF Spaces cap is 200 MB per upload |
| Slow first response | Cold model load | Not applicable — Spaces is always warm |

---

## Platform: Azure Container Apps (Alternative — Azure Portfolio Experience)

Use this option if you want to demonstrate Azure deployment skills on your CV.
Azure Container Apps has a generous free allowance (~180,000 vCPU-seconds/month)
sufficient for a low-traffic portfolio demo.

| Property | Detail |
|---|---|
| URL | `https://finance-intelligence.delightful-reef-xxxxx.australiaeast.azurecontainerapps.io` |
| Sleep | None if `min-replicas=1` |
| Cost | Free tier; ~AUD $15/month if always-on |
| Azure services used | Azure Container Registry, Azure Container Apps, Azure Resource Group |

---

### Prerequisites

- Azure subscription ([azure.com/free](https://azure.com/free) — 12-month free trial available)
- [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli) installed
- Docker installed locally

---

### Step 1 — Build and push image to Azure Container Registry

```bash
# Log in
az login
az acr login --name YOUR_REGISTRY_NAME

# Build and push
docker build -t finance-intelligence:latest .
docker tag finance-intelligence:latest YOUR_REGISTRY_NAME.azurecr.io/finance-intelligence:latest
docker push YOUR_REGISTRY_NAME.azurecr.io/finance-intelligence:latest
```

Or use the GitHub Actions workflow at `.github/workflows/azure-deploy.yml` to build and push automatically.

---

### Step 2 — Deploy to Azure Container Apps

```bash
# Create resource group
az group create --name finance-intelligence-rg --location australiaeast

# Create Container Apps environment
az containerapp env create \
  --name finance-intelligence-env \
  --resource-group finance-intelligence-rg \
  --location australiaeast

# Deploy
az containerapp create \
  --name finance-intelligence \
  --resource-group finance-intelligence-rg \
  --environment finance-intelligence-env \
  --image YOUR_REGISTRY_NAME.azurecr.io/finance-intelligence:latest \
  --target-port 8501 \
  --ingress external \
  --min-replicas 1 \
  --secrets openai-key=YOUR_OPENAI_API_KEY \
  --env-vars OPENAI_API_KEY=secretref:openai-key
```

---

### GitHub Actions auto-deploy for Azure

The workflow at `.github/workflows/azure-deploy.yml` builds, pushes, and deploys
on every push to `main`. Add these GitHub Secrets in your repo settings:

| Secret | Description |
|---|---|
| `AZURE_CREDENTIALS` | Output of `az ad sp create-for-rbac --sdk-auth` |
| `REGISTRY_LOGIN_SERVER` | e.g. `yourregistry.azurecr.io` |
| `REGISTRY_USERNAME` | ACR username |
| `REGISTRY_PASSWORD` | ACR password |
| `OPENAI_API_KEY` | Your OpenAI API key |

---

### ACS Portfolio Note

When listing Azure Container Apps deployment in your skills evidence document:

- **Highlight:** Container Registry, Container Apps Environment, ingress configuration, min-replicas, GitHub Actions CI/CD pipeline
- **Evidence:** Screenshot of the running Container App in Azure Portal, GitHub Actions workflow run log, and the live public URL
- **ACS Category:** ICT Professional — Cloud Infrastructure / DevOps
