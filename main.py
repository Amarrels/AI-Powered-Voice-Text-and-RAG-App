from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, send_file, send_from_directory, flash
from werkzeug.utils import secure_filename
import os
import google.generativeai as genai

def generate(filename, prompt):
    genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

    # Set up the model
    model = genai.GenerativeModel('gemini-1.5-flash')

    # Load the audio
    try:
        with open(filename, 'rb') as file:
            audio_data = file.read()
    except FileNotFoundError:
        print(f"Error: File not found at {filename}")
        return "Error: File not found."

    audio_part = {"mime_type": "audio/wav", "data": audio_data}

    # Prepare the content
    contents = [
        audio_part,
        prompt,
    ]

    # Generate content
    try:
        response = model.generate_content(contents)
        response.resolve()
        print(response.text)
        return response.text
    except Exception as e:
        print(f"Error during content generation: {e}")
        return f"Error: {e}"

app = Flask(__name__)

# GCP Auth
project_id = "project1-amarrahouraney"

# Configure upload folder
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'wav'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Configure API key (if needed)
app.secret_key = os.environ.get('GOOGLE_APPLICATION_CREDENTIAL')

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_files():
    files = []
    for filename in os.listdir(UPLOAD_FOLDER):
        if allowed_file(filename):
            files.append(filename)
            print(filename)
    files.sort(reverse=True)
    return files

@app.route('/')
def index():
    files = get_files()
    return render_template('index.html', files=files)

@app.route('/upload', methods=['POST'])
def upload_audio():
    if 'audio_data' not in request.files:
        flash('No audio data')
        return redirect(request.url)
    file = request.files['audio_data']
    if file.filename == '':
        flash('No selected file')
        return redirect(request.url)
    if file and allowed_file(file.filename):
        filename = datetime.now().strftime("%Y%m%d-%I%M%S%p") + '.wav'
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)

        prompt = """    
        Please provide an exact transcript for the audio, followed by sentiment analysis.

        Your response should follow the format:

        Text: USERS SPEECH TRANSCRIPTION

        Sentiment Analysis: positive|neutral|negative
        """
        text = generate(file_path, prompt)
        transcript_path = file_path + '.txt'
        with open(transcript_path, 'w') as f:
            f.write(text)
        return redirect('/')
    else:
        flash('Invalid file type')
        return redirect(request.url)

@app.route('/upload/<filename>')
def get_file(filename):
    return send_file(filename)

@app.route('/script.js', methods=['GET'])
def scripts_js():
    return send_file('./script.js')

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    app.run(debug=True)
