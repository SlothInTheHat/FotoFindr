# FotoFindr

AI that understands your camera roll

FotoFindr is an AI-powered photo intelligence system that automatically analyzes, tags, organizes, and narrates your photo library.

* Upload photos.
* Search them naturally.
* Let AI understand what’s inside.

#  Features
* Automatic Image Understanding
* Scene description generation
* Image tagging
* Object detection
* Face detection & clustering
* Emotion detection
* Detect "unimportant" images with no objects

# Natural Language Search
* Search like: "Find photos of Jake where he looks happy at the beach"
Semantic search combines:
* Vector similarity
* Named person filtering
* Emotion filtering
* Metadata constraints

# How It Works
## 1️⃣ Upload Photo
User uploads via mobile app.

## 🏗 Architecture
```
Mobile App (Expo)
        ↓
Cloudflare API Gateway
        ↓
FastAPI Backend (DigitalOcean)
        ↓
AI Processing Workers
        ↓
Metadata DB + Vector DB
        ↓
Search API
```