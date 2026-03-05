# GitHub Repository Setup Guide

This guide will help you push the AI Girlfriend project to your private GitHub repository.

## Repository Details

- **Owner**: `dobrinsm`
- **Repository Name**: `ai-girlfriend-comfyui`
- **Visibility**: Private
- **URL**: `https://github.com/dobrinsm/ai-girlfriend-comfyui`

## Step 1: Create Repository on GitHub

### Option A: Using GitHub Web Interface

1. Go to [github.com/new](https://github.com/new)
2. Fill in the details:
   - **Repository name**: `ai-girlfriend-comfyui`
   - **Description**: `Real-time AI avatar generation with ComfyUI + WaveSpeed`
   - **Visibility**: Select **Private**
   - **Initialize**: **DO NOT** initialize with README (we already have one)
3. Click **"Create repository"**

### Option B: Using GitHub CLI (if installed)

```bash
# Install GitHub CLI if needed
# macOS: brew install gh
# Windows: winget install --id GitHub.cli
# Linux: see https://github.com/cli/cli/blob/trunk/docs/install_linux.md

# Authenticate
gh auth login

# Create repository
gh repo create dobrinsm/ai-girlfriend-comfyui \
  --private \
  --description "Real-time AI avatar generation with ComfyUI + WaveSpeed" \
  --source=. \
  --remote=origin \
  --push
```

## Step 2: Push Your Code

After creating the repository on GitHub, run these commands in your project directory:

```bash
cd ~/projects/ai-girlfriend-comfyui

# Add the remote repository
git remote add origin https://github.com/dobrinsm/ai-girlfriend-comfyui.git

# Push to GitHub
git push -u origin master
```

## Step 3: Verify

Check that everything pushed correctly:

1. Go to `https://github.com/dobrinsm/ai-girlfriend-comfyui`
2. You should see all your files:
   - `README.md`
   - `backend/`
   - `workflows/`
   - `docs/`
   - etc.

## Step 4: Set Up SSH (Recommended)

For easier pushing/pulling without entering your password every time:

```bash
# Generate SSH key (if you don't have one)
ssh-keygen -t ed25519 -C "m.dobrinski@hotmail.com"

# Add to SSH agent
eval "$(ssh-agent -s)"
ssh-add ~/.ssh/id_ed25519

# Copy public key
cat ~/.ssh/id_ed25519.pub
```

Then add the key to GitHub:
1. Go to GitHub → Settings → SSH and GPG keys
2. Click "New SSH key"
3. Paste your public key

Update the remote to use SSH:
```bash
git remote set-url origin git@github.com:dobrinsm/ai-girlfriend-comfyui.git
```

## Using the Repository

### Clone on Another Machine

```bash
git clone https://github.com/dobrinsm/ai-girlfriend-comfyui.git
```

### Update Documentation Links

After pushing, all documentation has been pre-configured with the correct repository URL:
- `https://github.com/dobrinsm/ai-girlfriend-comfyui`

### Download Script on RunPod

Once pushed, you can use this one-liner on RunPod:

```bash
curl -fsSL https://raw.githubusercontent.com/dobrinsm/ai-girlfriend-comfyui/main/scripts/setup_runpod.sh | bash
```

Or clone directly:

```bash
git clone https://github.com/dobrinsm/ai-girlfriend-comfyui.git /runpod-volume/ai-girlfriend-comfyui
```

## Troubleshooting

### Authentication Failed

If you get an authentication error:
```bash
# Use personal access token instead of password
# Go to GitHub → Settings → Developer settings → Personal access tokens
# Create a token with 'repo' scope
```

### Remote Already Exists

```bash
# Remove existing remote
git remote remove origin

# Add new remote
git remote add origin https://github.com/dobrinsm/ai-girlfriend-comfyui.git
```

### Large Files

If you have large files (>100MB), use Git LFS:
```bash
# Install Git LFS
git lfs install

# Track large files
git lfs track "*.safetensors"
git lfs track "*.ckpt"
git lfs track "*.pth"

# Commit and push
git add .gitattributes
git commit -m "Add Git LFS tracking"
git push
```

**Note**: Models are already in `.gitignore`, so they won't be pushed to GitHub.

## Next Steps

1. ✅ Create repository on GitHub
2. ✅ Push your code
3. ✅ Verify files are there
4. 🔄 Set up RunPod deployment using the repository URL
5. 🔄 Share with collaborators (if needed)

## Repository URL Reference

All documentation files have been updated with the correct URL:

| File | URL Reference |
|------|---------------|
| `README.md` | Clone instructions |
| `docs/SETUP.md` | Clone instructions |
| `docs/RUNPOD_GETTING_STARTED.md` | Clone and curl commands |
| `scripts/setup_runpod.sh` | Project directory path |

The repository URL is: **https://github.com/dobrinsm/ai-girlfriend-comfyui**
