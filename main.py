from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, send_file, send_from_directory, flash
from werkzeug.utils import secure_filename
import os
#GeminI AI library
import google.generativeai as genai
#from google.generativeai import types
from google.cloud import texttospeech_v1

# --- Flask setup ---
app = Flask(__name__)

# --- GCP Auth ---
project_id = "project1-amarrahouraney"

# --- Configure folders --- 
UPLOAD_FOLDER = 'uploads'
PDF_FOLDER = 'books'
TTS_FOLDER    = 'tts'
ALLOWED_EXTENSIONS = {'wav'}
ALLOWED_PDF_EXTENSIONS = {'pdf'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['PDF_FOLDER'] = PDF_FOLDER
app.config['TTS_FOLDER']    = TTS_FOLDER


# -- create directories --
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PDF_FOLDER, exist_ok=True)
os.makedirs(TTS_FOLDER, exist_ok=True)

# Global variables to track current book
current_book_path = None


# Allowed extensions
ALLOWED_AUDIO_EXTS = {'wav'}
ALLOWED_PDF_EXTS   = {'pdf'}


# --- Gemni LLM + TTS function integration ---
def text_to_speech(text, output_path):
    #Initialize Google Cloud Clients
    tts_client = texttospeech_v1.TextToSpeechClient()

    synthesis_input = texttospeech_v1.SynthesisInput(text=text)
    voice = texttospeech_v1.VoiceSelectionParams(language_code="en-US")
    audio_config = texttospeech_v1.AudioConfig(audio_encoding=texttospeech_v1.AudioEncoding.LINEAR16)

    response = tts_client.synthesize_speech(
        input=synthesis_input, voice=voice, audio_config=audio_config
    )

    with open(output_path, "wb") as out:
        out.write(response.audio_content)
        print(f"✅ TTS audio saved: {output_path}")

def generate(audio_path, pdf_path):
    """
    1) Uploads audio + PDF to Gemini
    2) Gets text answer
    3) Uses Gemini to synthesize TTS WAV
    Returns (answer_text, tts_filename)
    """
    #1. Configure the API key
    genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
    model = genai.GenerativeModel("gemini-1.5-flash")

    #2. Upload both files to gemini
    uploaded_audio = genai.upload_file(audio_path)
    uploaded_pdf = genai.upload_file(pdf_path)
    
    #3. create content with file references and prompt
    contents = [
        {
            "role": "user",
            "parts": [
                {
                    "file_data": {
                        "file_uri": uploaded_audio.uri,
                        "mime_type": "audio/wav"
                    }
                },
                {
                    "file_data": {
                        "file_uri": uploaded_pdf.uri,
                        "mime_type": "application/pdf"
                    }
                },
                {
                    "text": (
                        "Answer the user's query in the audio file based "
                        "on the PDF book. First transcribe the question, then "
                        "provide details using information from the book. Do not read any '*'"
                    )
                }
            ]
        }
    ]

    config = {
        "temperature": 0.7,
        "top_p": 0.95,
        "top_k": 40,
        "max_output_tokens": 8192,
        "response_mime_type": "text/plain"
    }

    

    # Generate content
    try:
        response = model.generate_content(contents, generation_config=config)
        response.resolve()
        answer_text = response.text
    except Exception as e:
        print(f"Error during content generation: {e}")
        return f"Error: {e}"
    
    # Generate TTS using Google Cloud TTS
    timestamp = datetime.now().strftime('%Y%m%d-%I%M%S%p')
    tts_filename = f"{timestamp}_response.wav"
    tts_path = os.path.join(TTS_FOLDER, tts_filename)

    text_to_speech(answer_text, tts_path)


    return answer_text, tts_path


# --- File handling helpers --- 
def allowed_file(filename, allowed_exts):
    return (
        '.' in filename and
        filename.rsplit('.', 1)[1].lower() in allowed_exts
    )

def get_uploaded_files(folder, allowed_exts):
    files = []
    for fname in os.listdir(folder):
        if allowed_file(fname, allowed_exts):
            files.append(fname)
    files.sort(reverse=True)
    return files


# --- App Routes --- 

@app.route('/')
def index():
    audio_files = get_uploaded_files(app.config['UPLOAD_FOLDER'], ALLOWED_AUDIO_EXTS)
    pdf_files   = get_uploaded_files(app.config['PDF_FOLDER'],    ALLOWED_PDF_EXTS)
    tts_files   = get_uploaded_files(app.config['TTS_FOLDER'],    ALLOWED_AUDIO_EXTS)
    return render_template(
        'index.html',
        audio_files=audio_files,
        pdf_files=pdf_files,
        tts_files=tts_files,
        current_book=os.path.basename(current_book_path) if current_book_path else None
    )

@app.route('/upload_book', methods=['POST'])
def upload_book():
    global current_book_path
    file = request.files.get('book_pdf')
    # Use PDF set here, not the WAV set:
    if file and allowed_file(file.filename, ALLOWED_PDF_EXTS):
        fname = secure_filename(file.filename)
        path = os.path.join(app.config['PDF_FOLDER'], fname)
        file.save(path)
        current_book_path = path
        return redirect(url_for('index', status='book_uploaded'))
    else:
        return redirect(url_for('index', status='book_error'))


@app.route('/upload', methods=['POST'])
def upload_audio():
    print("📥 Upload route hit.")
    #ensure your api key is working
    #set in terminal by $env:GEMINI_API_KEY=''
    print("🔑 GEMINI_API_KEY is:", os.environ.get("GEMINI_API_KEY"))

    # 1. Check if book exists
    pdf_files = get_uploaded_files(app.config['PDF_FOLDER'], ALLOWED_PDF_EXTS)
    if not pdf_files:
        print("❌ No book found.")
        return redirect(url_for('index', status='no_book'))

    pdf_filename = pdf_files[0]
    pdf_path = os.path.join(app.config['PDF_FOLDER'], pdf_filename)
    print(f"✅ Found book: {pdf_filename}")

    # 2. Validate audio file
    file = request.files.get('audio_data')
    if not file or not allowed_file(file.filename, ALLOWED_AUDIO_EXTS):
        print("❌ Invalid audio file.")
        return redirect(url_for('index', status='audio_error'))

    # 3. Save audio
    timestamp = datetime.now().strftime("%Y%m%d-%I%M%S%p")
    audio_filename = f"{timestamp}.wav"
    audio_path = os.path.join(app.config['UPLOAD_FOLDER'], audio_filename)
    file.save(audio_path)
    print(f"📁 Saved audio: {audio_path}")

    # 4. Generate response
    try:
        print("🚀 Calling Gemini generate()...")
        answer_text, tts_filename = generate(audio_path, pdf_path)
        print("✅ Gemini returned response.")

        # 5. Save transcript
        transcript_path = tts_filename + '.txt'
        with open(transcript_path, 'w') as tf:
            tf.write(answer_text)
        print(f"📝 Transcript saved: {transcript_path}")

        if tts_filename:
            print("✅ TTS file generated:", tts_filename)
            return redirect(url_for('index', status='question_ok'))
        else:
            print("⚠️ TTS failed to generate.")
            return redirect(url_for('index', status='tts_error'))

    except Exception as e:
        print("🔥 Error during Gemini response generation:", e)
        return redirect(url_for('index', status='generation_failed'))




@app.route('/books/<filename>')
def serve_book(filename):
    return send_from_directory(app.config['PDF_FOLDER'], filename)

@app.route('/uploads/<filename>')
def serve_audio(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/tts/<filename>')
def serve_tts(filename):
    return send_from_directory(app.config['TTS_FOLDER'], filename)

@app.route('/script.js')
def serve_script():
    return send_from_directory('.', 'script.js')

if __name__ == '__main__':
    app.run(debug=True)