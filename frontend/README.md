# AI Girlfriend Frontend

A web interface for chatting with your AI avatar through text, voice, or video input.

## Features

- **Text Input**: Type messages to chat with the AI
- **Voice Input**: Click the microphone button to speak (uses Web Speech API)
- **Webcam Integration**: Your face is captured to generate personalized avatars
- **Video Response**: The AI responds with a lip-synced video avatar
- **Real-time Updates**: WebSocket connection shows progress during generation

## Quick Start

### Option 1: Python HTTP Server

```bash
cd frontend
python serve.py
```

Then open `http://localhost:3000` in your browser.

### Option 2: Simple HTTP Server

```bash
cd frontend
python -m http.server 3000
```

### Option 3: VS Code Live Server

Install the "Live Server" extension in VS Code and click "Go Live" on `index.html`.

## Configuration

Edit `app.js` and update the `CONFIG` object with your backend URL:

```javascript
const CONFIG = {
    WS_URL: 'ws://YOUR_RUNPOD_IP:8000/ws/chat',
    API_URL: 'http://YOUR_RUNPOD_IP:8000',
    USER_ID: 'user_' + Math.random().toString(36).substr(2, 9)
};
```

## Usage

1. **Allow Webcam Access**: The app will ask for camera permission to capture your face for avatar generation
2. **Type or Speak**: Enter text or click the microphone to use voice input
3. **Watch Progress**: The loading overlay shows each step:
   - Analyzing webcam (VLM)
   - Thinking (LLM generating response)
   - Generating voice (TTS)
   - Generating avatar (Flux + IP-Adapter)
   - Animating (Wan 2.2 I2V)
   - Syncing lips (SadTalker)
4. **Enjoy**: The final lip-synced video plays in the avatar area

## Browser Requirements

- Modern browser with WebSocket support
- Webcam access (for personalized avatars)
- Microphone access (for voice input)
- Web Speech API support (Chrome, Edge, Safari)

## Options

- **Use webcam for avatar**: Toggle to enable/disable face capture
- **Generate video response**: Toggle to enable/disable video generation (text-only mode if off)

## Troubleshooting

**Connection Failed**: Check that your backend is running and the CONFIG URLs are correct

**Webcam Not Working**: Ensure you've granted camera permissions in your browser

**Voice Input Not Working**: Use Chrome or Edge for best Web Speech API support

**Video Not Playing**: Check browser console for CORS errors; ensure backend has CORS enabled
