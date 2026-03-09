/**
 * AI Girlfriend Frontend Application
 * Connects to backend WebSocket for real-time avatar chat
 */

// Configuration - Auto-detect backend URL from current location
// Usage: index.html?backend=https://pod-id-8000.proxy.runpod.net
function getBackendURL() {
    const params = new URLSearchParams(window.location.search);
    const backendParam = params.get('backend');
    if (backendParam) {
        return backendParam.replace(/\/$/, '');
    }
    const protocol = window.location.protocol;
    const host = window.location.hostname;

    if (host.includes('.proxy.runpod.net')) {
        const backendHost = host.replace('-3000', '-8000').replace(':3000', ':8000');
        return protocol + '//' + backendHost;
    }
    return protocol + '//' + host.replace(':3000', ':8000');
}

const CONFIG = {
    API_URL: getBackendURL(),
    WS_URL: getBackendURL().replace('http://', 'ws://').replace('https://', 'wss://') + '/ws/chat',

    USER_ID: 'user_' + Math.random().toString(36).substr(2, 9)
};

console.log('[DEBUG] Backend URL:', CONFIG.API_URL);
console.log('[DEBUG] WebSocket URL:', CONFIG.WS_URL);

const state = {
    ws: null,
    isConnected: false,
    isRecording: false,
    mediaRecorder: null,
    audioChunks: [],
    currentVideoUrl: null,
    uploadedImage: null
};

const elements = {
    connectionStatus: document.getElementById('connectionStatus'),
    statusDot: document.querySelector('.status-dot'),
    statusText: document.querySelector('.status-text'),
    chatMessages: document.getElementById('chatMessages'),
    messageInput: document.getElementById('messageInput'),
    sendBtn: document.getElementById('sendBtn'),
    voiceBtn: document.getElementById('voiceBtn'),
    voiceModal: document.getElementById('voiceModal'),
    stopRecording: document.getElementById('stopRecording'),
    voiceWave: document.getElementById('voiceWave'),
    avatarContainer: document.getElementById('avatarContainer'),
    avatarVideo: document.getElementById('avatarVideo'),
    avatarPlaceholder: document.getElementById('avatarPlaceholder'),
    loadingOverlay: document.getElementById('loadingOverlay'),
    loadingText: document.getElementById('loadingText'),
    progressFill: document.getElementById('progressFill'),
    generateVideo: document.getElementById('generateVideo'),
    uploadImageBtn: document.getElementById('uploadImageBtn'),
    imageUpload: document.getElementById('imageUpload'),
    imagePreview: document.getElementById('imagePreview'),
    previewImg: document.getElementById('previewImg'),
    clearImage: document.getElementById('clearImage')
};

function init() {
    connectWebSocket();
    setupEventListeners();
    createVoiceWave();
}

function connectWebSocket() {
    updateConnectionStatus('connecting');
    console.log('[DEBUG] Attempting WebSocket connection to:', CONFIG.WS_URL);

    try {
        state.ws = new WebSocket(CONFIG.WS_URL);

        state.ws.onopen = () => {
            console.log('[DEBUG] WebSocket connected successfully');
            state.isConnected = true;
            updateConnectionStatus('connected');
        };

        state.ws.onmessage = (event) => {
            console.log('[DEBUG] Received WebSocket message:', event.data);
            const data = JSON.parse(event.data);
            handleWebSocketMessage(data);
        };

        state.ws.onclose = (event) => {
            console.log('[DEBUG] WebSocket closed. Code:', event.code, 'Reason:', event.reason);
            state.isConnected = false;
            updateConnectionStatus('disconnected');
            setTimeout(connectWebSocket, 3000);
        };

        state.ws.onerror = (error) => {
            console.error('[DEBUG] WebSocket error:', error);
            state.isConnected = false;
            updateConnectionStatus('disconnected');
        };
    } catch (error) {
        console.error('[DEBUG] Failed to create WebSocket:', error);
        updateConnectionStatus('disconnected');
    }
}

function updateConnectionStatus(status) {
    elements.statusDot.className = 'status-dot ' + status;
    elements.statusText.textContent = status.charAt(0).toUpperCase() + status.slice(1);
}

function handleWebSocketMessage(data) {
    console.log('Received:', data);

    switch(data.type) {
        case 'status':
            showLoading(data.message);
            updateProgress(data.message);
            break;

        case 'vlm_result':
            addSystemMessage(' ' + data.context);
            break;

        case 'chat_response':
            addMessage('ai', data.text);
            hideLoading();
            break;

        case 'voice_ready':
            playAudio(data.audio_path);
            break;

        case 'avatar_ready':
            showLoading('Animating avatar...');
            break;

        case 'video_ready':
            showLoading('Syncing lips...');
            break;

        case 'lipsync_ready':
            hideLoading();
            playAvatarVideo(data.video_path);
            break;

        case 'complete':
            hideLoading();
            console.log('Generation complete:', data.total_time + 's');
            break;

        case 'pong':
            break;

        default:
            console.log('Unknown message type:', data.type);
    }
}

async function sendMessage(text) {
    console.log('[DEBUG] sendMessage called with:', text);
    console.log('[DEBUG] Connection status:', state.isConnected);

    if (!state.isConnected) {
        addSystemMessage('Not connected to server. Please wait...');
        console.log('[DEBUG] Not connected, aborting');
        return;
    }

    if (!text.trim()) return;

    addMessage('user', text);
    elements.messageInput.value = '';

    showLoading('Processing...');

    if (state.uploadedImage) {
        console.log('[DEBUG] Using HTTP API with uploaded image');
        try {
            await generateAvatarWithImage(text, state.uploadedImage);
        } catch (error) {
            console.error('[DEBUG] Avatar generation failed:', error);
            addSystemMessage('Failed to generate avatar. Please try again.');
            hideLoading();
        }
        return;
    }

    const message = {
        type: 'chat',
        user_id: CONFIG.USER_ID,
        message: text,
        webcam_frame: null
    };

    console.log('[DEBUG] Sending WebSocket message:', JSON.stringify(message));
    state.ws.send(JSON.stringify(message));
    console.log('[DEBUG] Message sent');
}

async function generateAvatarWithImage(prompt, imageData) {
    showLoading('Generating avatar with your image...');

    try {
        console.log('Converting image data to blob...');
        const response = await fetch(imageData);
        const blob = await response.blob();
        const file = new File([blob], 'avatar_reference.png', { type: 'image/png' });
        console.log('File created:', file.name, file.size, 'bytes');

        const formData = new FormData();
        formData.append('prompt', prompt);
        formData.append('webcam_image', file);
        formData.append('user_id', CONFIG.USER_ID);

        console.log('Sending request to:', `${CONFIG.API_URL}/api/v1/generate/avatar`);
        const result = await fetch(`${CONFIG.API_URL}/api/v1/generate/avatar`, {
            method: 'POST',
            body: formData
        });

        console.log('Response status:', result.status);

        if (!result.ok) {
            const errorText = await result.text();
            console.error('Server error response:', errorText);
            throw new Error(`HTTP error! status: ${result.status} - ${errorText}`);
        }

        const data = await result.json();
        console.log('Response data:', data);

        if (data.output_path) {
            addSystemMessage('Avatar generated successfully!');
            elements.avatarPlaceholder.style.display = 'none';
            elements.avatarVideo.style.display = 'none';

            const img = document.createElement('img');
            img.src = `${CONFIG.API_URL}/${data.output_path}`;
            img.style.width = '100%';
            img.style.height = '100%';
            img.style.objectFit = 'cover';
            img.id = 'generatedAvatar';

            const prevAvatar = document.getElementById('generatedAvatar');
            if (prevAvatar) prevAvatar.remove();

            elements.avatarContainer.appendChild(img);
        } else {
            addSystemMessage('Avatar generation completed but no output path received');
        }

        hideLoading();
    } catch (error) {
        console.error('Error generating avatar:', error);
        addSystemMessage('Error generating avatar: ' + error.message);
        hideLoading();
    }
}

function createVoiceWave() {
    const wave = elements.voiceWave;
    for (let i = 0; i < 20; i++) {
        const span = document.createElement('span');
        span.style.animationDelay = (i * 0.05) + 's';
        span.style.height = Math.random() * 60 + 20 + '%';
        wave.appendChild(span);
    }
}

async function startVoiceRecording() {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        state.mediaRecorder = new MediaRecorder(stream);
        state.audioChunks = [];

        state.mediaRecorder.ondataavailable = (event) => {
            state.audioChunks.push(event.data);
        };

        state.mediaRecorder.onstop = async () => {
            const audioBlob = new Blob(state.audioChunks, { type: 'audio/wav' });
            await transcribeAudio(audioBlob);
            stream.getTracks().forEach(track => track.stop());
        };

        state.mediaRecorder.start();
        state.isRecording = true;
        elements.voiceModal.style.display = 'flex';
        elements.voiceBtn.classList.add('recording');
    } catch (error) {
        console.error('Microphone access denied:', error);
        addSystemMessage('Microphone access denied. Please use text input.');
    }
}

function stopVoiceRecording() {
    if (state.mediaRecorder && state.isRecording) {
        state.mediaRecorder.stop();
        state.isRecording = false;
        elements.voiceModal.style.display = 'none';
        elements.voiceBtn.classList.remove('recording');
    }
}

async function transcribeAudio(audioBlob) {
    if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        const recognition = new SpeechRecognition();

        recognition.lang = 'en-US';
        recognition.interimResults = false;
        recognition.maxAlternatives = 1;

        recognition.onresult = (event) => {
            const transcript = event.results[0][0].transcript;
            elements.messageInput.value = transcript;
            sendMessage(transcript);
        };

        recognition.onerror = (event) => {
            console.error('Speech recognition error:', event.error);
            addSystemMessage('Voice recognition failed. Please type your message.');
        };

        recognition.start();
    } else {
        addSystemMessage('Voice recognition not supported. Please type your message.');
    }
}

function addMessage(sender, text) {
    const message = document.createElement('div');
    message.className = 'message ' + sender;

    const header = document.createElement('div');
    header.className = 'message-header';
    header.textContent = sender === 'user' ? 'You' : 'AI Girlfriend';

    const content = document.createElement('div');
    content.textContent = text;

    message.appendChild(header);
    message.appendChild(content);

    elements.chatMessages.appendChild(message);
    elements.chatMessages.scrollTop = elements.chatMessages.scrollHeight;
}

function addSystemMessage(text) {
    const message = document.createElement('div');
    message.className = 'message system';
    message.textContent = text;
    elements.chatMessages.appendChild(message);
    elements.chatMessages.scrollTop = elements.chatMessages.scrollHeight;
}

function showLoading(text) {
    elements.loadingText.textContent = text;
    elements.loadingOverlay.style.display = 'flex';
}

function hideLoading() {
    elements.loadingOverlay.style.display = 'none';
    elements.progressFill.style.width = '0%';
}

function updateProgress(status) {
    const progressMap = {
        'Analyzing webcam...': 20,
        'Thinking...': 40,
        'Generating voice...': 60,
        'Generating avatar...': 70,
        'Animating...': 80,
        'Syncing lips...': 90
    };

    const progress = progressMap[status] || 0;
    elements.progressFill.style.width = progress + '%';
}

function playAvatarVideo(videoPath) {
    if (state.currentVideoUrl) {
        URL.revokeObjectURL(state.currentVideoUrl);
    }

    const fullUrl = videoPath.startsWith('http')
        ? videoPath
        : `${CONFIG.API_URL}/${videoPath}`;

    elements.avatarVideo.src = fullUrl;
    elements.avatarVideo.style.display = 'block';
    elements.avatarPlaceholder.style.display = 'none';

    elements.avatarVideo.play().catch(error => {
        console.error('Video playback failed:', error);
    });
}

function playAudio(audioPath) {
    const fullUrl = audioPath.startsWith('http')
        ? audioPath
        : `${CONFIG.API_URL}/${audioPath}`;

    const audio = new Audio(fullUrl);
    audio.play().catch(error => {
        console.error('Audio playback failed:', error);
    });
}

function setupEventListeners() {
    elements.sendBtn.addEventListener('click', () => {
        sendMessage(elements.messageInput.value);
    });

    elements.messageInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            sendMessage(elements.messageInput.value);
        }
    });

    elements.voiceBtn.addEventListener('click', () => {
        if (state.isRecording) {
            stopVoiceRecording();
        } else {
            startVoiceRecording();
        }
    });

    elements.stopRecording.addEventListener('click', stopVoiceRecording);

    setInterval(() => {
        if (state.isConnected && state.ws) {
            state.ws.send(JSON.stringify({ type: 'ping' }));
        }
    }, 30000);

    elements.uploadImageBtn.addEventListener('click', () => {
        elements.imageUpload.click();
    });

    elements.imageUpload.addEventListener('change', handleImageUpload);

    elements.clearImage.addEventListener('click', clearUploadedImage);
}

function handleImageUpload(event) {
    const file = event.target.files[0];
    if (!file) return;

    if (!file.type.startsWith('image/')) {
        addSystemMessage('Please select an image file');
        return;
    }

    if (file.size > 10 * 1024 * 1024) {
        addSystemMessage('Image size must be less than 10MB');
        return;
    }

    const reader = new FileReader();
    reader.onload = (e) => {
        state.uploadedImage = e.target.result;
        elements.previewImg.src = e.target.result;
        elements.imagePreview.style.display = 'inline-block';
        addSystemMessage('Avatar reference image uploaded. Your message will generate an avatar using this image.');
    };
    reader.onerror = () => {
        addSystemMessage('Failed to read image file');
    };
    reader.readAsDataURL(file);
}

function clearUploadedImage() {
    state.uploadedImage = null;
    elements.imagePreview.style.display = 'none';
    elements.previewImg.src = '';
    elements.imageUpload.value = '';
}

document.addEventListener('DOMContentLoaded', init);
