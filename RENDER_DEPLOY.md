# Food Scanner API - Render Deployment

## Quick Deploy to Render

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy)

### Manual Deployment Steps

1. **Fork/Push to GitHub**: Ensure your code is pushed to GitHub (already done: `dkwarude-cell/OpenCV`)

2. **Create Render Account**: Sign up at [render.com](https://render.com)

3. **Create New Web Service**:
   - Click "New +" → "Web Service"
   - Connect your GitHub repository: `dkwarude-cell/OpenCV`
   - Select the `food_scanner` directory (use Root Directory setting if needed)

4. **Configure Service**:
   - **Name**: `food-scanner-api`
   - **Region**: Oregon (or closest to you)
   - **Branch**: `main`
   - **Root Directory**: `food_scanner` (if repo root contains multiple projects)
   - **Runtime**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn api:app --app-dir src --host 0.0.0.0 --port $PORT`

5. **Environment Variables** (optional):
   - `PYTHON_VERSION`: `3.10.0`
   - `FOOD_SCANNER_DEBUG`: `false`

6. **Deploy**: Click "Create Web Service"

### Alternative: Using render.yaml

If `render.yaml` is in your repo root, Render will auto-detect it:

```yaml
services:
  - type: web
    name: food-scanner-api
    env: python
    region: oregon
    plan: free
    branch: main
    buildCommand: pip install -r requirements.txt
    startCommand: uvicorn api:app --app-dir src --host 0.0.0.0 --port $PORT
```

### Post-Deployment

Your API will be available at: `https://food-scanner-api.onrender.com`

**Endpoints**:
- `GET /` - API info
- `GET /health` - Health check
- `GET /docs` - Swagger documentation
- `GET /product/{barcode}` - Product lookup
- `POST /scan-image` - Upload barcode image
- `GET /search?q=term` - Search products
- `POST /dish-detect` - Detect dish from ingredients

### Important Notes

1. **Free Tier Limitations**:
   - Service spins down after 15 minutes of inactivity
   - First request after sleep takes 30-60 seconds
   - 750 hours/month free

2. **ZBar Library**: 
   - On Render, use system package: Add `zbar` to apt packages in Render dashboard
   - Or use build script to install libzbar

3. **OpenCV**: 
   - Using `opencv-python-headless` (no GUI support) for cloud deployment

### Troubleshooting

**If deployment fails with ZBar errors:**

Create a `render-build.sh`:
```bash
#!/bin/bash
apt-get update && apt-get install -y libzbar0
pip install -r requirements.txt
```

Then set Build Command to: `./render-build.sh`

**If PORT issues:**
Render automatically sets `$PORT` environment variable. Make sure start command uses it.

### Local Testing

Test the production setup locally:
```bash
PORT=8000 uvicorn api:app --app-dir src --host 0.0.0.0 --port $PORT
```

### Connect React Native App

Update your RN app to use the Render URL:
```javascript
const API_URL = 'https://food-scanner-api.onrender.com';
```
