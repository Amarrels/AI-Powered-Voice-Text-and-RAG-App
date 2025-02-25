from datetime import datetime
from google.cloud import speech, texttospeech_v1
from flask import Flask, render_template, request, redirect, url_for, send_file, send_from_directory, flash
from werkzeug.utils import secure_filename

import os

#GCP Auth
project_id = "project1-amarrahouraney"

app = Flask(__name__)

# Configure upload folder
UPLOAD_FOLDER = 'uploads'
TTS_FOLDER= 'tts'
ALLOWED_EXTENSIONS = {'wav', 'txt'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['TTS_FOLDER'] = TTS_FOLDER
#configure api key , LOAD FROM ENVIRONEMENT VARIABLE YOU CONFIGURED EARLIER IN TERMINAL
#this is they key from the service account you created in google cloud
app.secret_key = os.environ.get('GOOGLE_APPLICATION_CREDENTIAL')

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(TTS_FOLDER, exist_ok=True)

#Initialize Google Cloud Clients
speech_client = speech.SpeechClient()
tts_client = texttospeech_v1.TextToSpeechClient()

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_files_with_transcripts(folder):
    audio_files = []
    for filename in os.listdir(folder):
        if filename.endswith('.wav'):
            #check if theres a corresponding transcript file
            transcript_file = filename.replace('.wav', '.txt')
            transcript_exists = os.path.exists(os.path.join(folder, transcript_file))

            audio_files.append({
                'filename': filename,
                'transcript_file': transcript_file if transcript_exists else None
            })
    audio_files.sort(key=lambda x: x['filename'], reverse=True)
    return audio_files

def get_tts_files_with_texts(folder):
    tts_files=[]
    for filename in os.listdir(folder):
        if filename.endswith('.wav'):
            #check if theres a corresponding text file
            text_file = filename.replace('.wav', '.txt')
            text_exists = os.path.exists(os.path.join(folder, text_file))

            tts_files.append({
                'filename': filename,
                'text_file': text_file if text_exists else None
            })

    tts_files.sort(key=lambda x: x['filename'], reverse=True)
    return tts_files


#changed up index function for project one to include both file types
@app.route('/')
def index():
    audio_files = get_files_with_transcripts(UPLOAD_FOLDER)
    tts_files = get_tts_files_with_texts(TTS_FOLDER)
    return render_template('index.html', audio_files=audio_files, tts_files=tts_files)

@app.route('/upload', methods=['POST'])
def upload_audio():
    if 'audio_data' not in request.files:
        flash('No audio data')
        return redirect(request.url)
    file = request.files['audio_data']
    if file.filename == '':
        flash('No selected file')
        return redirect(request.url)
    if file:
        # filename = secure_filename(file.filename)
        filename = datetime.now().strftime("%Y%m%d-%I%M%S%p") + '.wav'
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)

        #
        #Project 1
        # Modify this block to call the speech to text API
        with open(file_path, 'rb') as audio_file:
            audio_content = audio_file.read()

        audio=speech.RecognitionAudio(content=audio_content)
        config=speech.RecognitionConfig(
        # encoding=speech.RecognitionConfig.AudioEncoding.MP3,
        # sample_rate_hertz=24000,
        language_code="en-US",
        model="latest_long",
        audio_channel_count=1,
        enable_word_confidence=True,
        enable_word_time_offsets=True,
        )

        response = speech_client.recognize(config=config, audio=audio)
        transcript = '\n'.join(result.alternatives[0].transcript for result in response.results)

        # Save transcript to same filename but .txt
        transcript_path = os.path.join(app.config['UPLOAD_FOLDER'], filename.replace('.wav', '.txt'))
        with open(transcript_path, 'w') as f:
            f.write(transcript)
        #
        #
    return redirect('/') #success

@app.route('/upload/<filename>')
def get_file(filename):
    return send_file(filename)

    
@app.route('/upload_text', methods=['POST'])
def upload_text():
    text = request.form['text']
    print(text)
    #
    #
    # Modify this block to call the stext to speech API
    synthesis_input = texttospeech_v1.SynthesisInput(text=text)
    voice = texttospeech_v1.VoiceSelectionParams(language_code="en-US")
    audio_config = texttospeech_v1.AudioConfig(audio_encoding=texttospeech_v1.AudioEncoding.LINEAR16)

    response = tts_client.synthesize_speech(input=synthesis_input, voice=voice, audio_config=audio_config)
    # Save the output as a audio file in the 'tts' directory 
    filename = datetime.now().strftime("%Y%m%d-%I%M%S%p") + '.wav'
    output_path = os.path.join(app.config['TTS_FOLDER'], filename)

    # Save the original text to a text file with the same name
    text_path = os.path.join(app.config['TTS_FOLDER'], filename.replace('.wav', '.txt'))
    with open(text_path, 'w') as f:
        f.write(text)
    #
    
     # Display the audio files at the bottom and allow the user to listen to them
    with open(output_path, 'wb') as f:
        f.write(response.audio_content)

    return redirect('/') #success

@app.route('/script.js',methods=['GET'])
def scripts_js():
    return send_file('./script.js')

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/tts/<filename>')
def tts_file(filename):
    return send_from_directory(app.config['TTS_FOLDER'], filename)

if __name__ == '__main__':
    app.run(debug=True)