# AI-Powered-Voice-Text-and-RAG-App
AI-powered application that combines voice and text interaction with advanced features like sentiment analysis, large language model (LLM) integration, and Retrieval-Augmented Generation (RAG). The app allows users to dictate or listen, analyze sentiment for dynamic replies, and upload/update PDFs for interactive document-based question answering

In previous versions, I used multiple APIs (texttosppech,speechtotext) to have a working app. Now I am using one API to perform all the functionalities. 

In the new version, we are no longer doing text to speech. For now there will only be audio inputs, with genai providing the transcript and sentiment analysis in one text

For the latest version: 
# 📚 Book Knowledge App

The **Book Knowledge App** is a web application that allows users to upload a PDF book and ask spoken questions about its content. It uses **Google Cloud Text-to-Speech**, **Gemini AI**, and **Flask** to transcribe questions, search the book for context, generate intelligent responses, and return an audio response—making reading and comprehension easier and more accessible.

---

## 🌟 Features

- 🎤 **Voice Input** – Record your voice directly in the browser.
- 📄 **PDF Upload** – Upload a book (PDF) to analyze and reference.
- 🤖 **AI-Powered Responses** – Uses Gemini to transcribe your query and generate an intelligent response.
- 🔊 **TTS Audio Output** – Listen to the AI's response with Google Cloud's Text-to-Speech.
- 💾 **File History** – Automatically stores and displays all uploaded books, queries, and responses.
- 🎨 **Modern UI** – Beautiful pink-themed interface with clean sections, a fixed top navbar, and animated transitions.

---

## 🛠️ Tech Stack

| Technology         | Purpose                                |
|--------------------|----------------------------------------|
| Google Cloud Run   | Deployment platform (serverless)       | Purpose                                |
| Python + Flask     | Backend server and routing             |
| HTML + CSS + JS    | Frontend interface                     |
| Google TTS         | Converts text responses to audio       |
| Gemini AI          | Analyzes the audio + book and responds |

## 🚀 How It Works

1. **Upload** a PDF book. (free pdf books on https://www.gutenberg.org/)
2. **Record** your question using your microphone.
3. The app:
   - Transcribes the audio.
   - Reads the uploaded book for context.
   - Generates a text-based answer.
   - Converts it to speech.
4. View and play your question/answer history!

---

## 📂 File Structure

```
project/
│
├── static/
│   ├── style.css          # Custom pink-themed styling
│   └── logo.png           # Pink book logo icon
│
├── templates/
│   └── index.html         # Main HTML template
│
├── uploads/               # User audio inputs (.wav)
├── books/                 # Uploaded book PDFs
├── tts/                   # AI-generated responses
│
├── script.js              # Handles recording logic
├── main.py                # Flask backend
└── README.md              # You're here!
```

---

## 🧪 Local Setup

1. Clone the repository
2. Set up a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # or .\venv\Scripts\activate on Windows
   ```
3. Install requirements:
   ```bash
   pip install -r requirements.txt
   ```
4. Set up Google/Gemini  (retrieve from Gemini AI studio) API keys as environment variables:
   ```bash
   $env:GEMINI_API_KEY = your_key_here
   ```
5. Run the app:
   ```bash
   python main.py
   ```

---

## 🌸 UI Preview

<img src='bookapp.gif' title='UI Preview' width='' alt='UI Preview' />


---

## ✨ Future Ideas

- 🌓 Dark/light mode toggle
- 🧠 Multiple book context memory
- 🗣️ Multilingual support
- 🧾 Upload audio questions instead of recording live

## ☁️ Deployment (Cloud Run + GitHub CI/CD)

This app is deployed using **Google Cloud Run**, a fully managed serverless platform.

### 🔧 Setup for Deployment

To deploy this project on your own Cloud Run instance:

1. **Enable APIs**:
   - Cloud Run
   - Cloud Build
   - Artifact Registry (optional)

2. **Set Environment Variables in Cloud Run**:
   - `GEMINI_API_KEY` – your Gemini AI API key
   - `GOOGLE_APPLICATION_CREDENTIALS` – path to your service account key JSON (optional for local)

3. **Deploy to Cloud Run**:
   - You can deploy via the Google Cloud Console or using the CLI
