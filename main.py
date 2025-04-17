from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, send_from_directory
from werkzeug.utils import secure_filename
import os
import tempfile
import google.generativeai as genai
from google.cloud import texttospeech_v1, storage

# --- Flask setup ---
app = Flask(__name__)

# --- GCP Auth ---
project_id = "project1-amarrahouraney"
BUCKET_NAME = os.environ.get("GCS_BUCKET_NAME") or 'bookappuploads'

# --- GCS Prefixes ---
UPLOAD_PREFIX = "uploads/"
PDF_PREFIX = "books/"
TTS_PREFIX = "tts/"
TRANSCRIPT_PREFIX = "transcripts/"

# Initialize GCS client
try:
    storage_client = storage.Client()
    bucket = storage_client.bucket(BUCKET_NAME)
    print(f"✅ Successfully connected to GCS Bucket: {BUCKET_NAME}")
except Exception as e:
    print(f"🔥 Failed to initialize Google Cloud Storage client: {e}")
    raise

current_book_gcs_path = None
ALLOWED_AUDIO_EXTS = {'wav'}
ALLOWED_PDF_EXTS = {'pdf'}

def allowed_file(filename, allowed_exts):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_exts

def text_to_speech(text, output_blob_name):
    try:
        tts_client = texttospeech_v1.TextToSpeechClient()
        synthesis_input = texttospeech_v1.SynthesisInput(text=text)
        voice = texttospeech_v1.VoiceSelectionParams(language_code="en-US")
        audio_config = texttospeech_v1.AudioConfig(audio_encoding=texttospeech_v1.AudioEncoding.LINEAR16)
        response = tts_client.synthesize_speech(input=synthesis_input, voice=voice, audio_config=audio_config)
        blob = bucket.blob(output_blob_name)
        blob.upload_from_string(response.audio_content, content_type='audio/wav')
        return output_blob_name
    except Exception as e:
        print(f"🔥 TTS Error: {e}")
        raise

import os
import tempfile
import datetime
import google.generativeai as genai
# Assuming 'bucket', 'text_to_speech', 'TTS_PREFIX', 'storage_client'
# are defined elsewhere in your code as before.

def generate(audio_gcs_path, pdf_gcs_path):
    """
    1) Downloads audio + PDF from GCS to temporary local files.
    2) Uploads temp files to Gemini using genai.upload_file.
    3) Cleans up temporary files.
    4) Constructs the prompt for Gemini using file references.
    5) Gets text answer from Gemini.
    6) Uses Google Cloud TTS to synthesize WAV and save directly to GCS.
    Returns (answer_text, tts_gcs_path) or (error_text, None)
    """
    print(f"🧠 Starting generation process for audio: {audio_gcs_path}, PDF: {pdf_gcs_path}")
    uploaded_audio_ref = None # Initialize references
    uploaded_pdf_ref = None
    temp_audio_path = None
    temp_pdf_path = None

    try:
        # --- Configure Gemini API ---
        # Moved configuration here to catch potential setup errors early
        genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
        model = genai.GenerativeModel("gemini-1.5-flash")

        # --- Temporary local download ---
        print("⬇️ Downloading files from GCS to temporary local storage...")
        # Using 'with' ensures files are closed even if errors occur before delete=False matters
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_audio, \
             tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_pdf:
            temp_audio_path = temp_audio.name
            temp_pdf_path = temp_pdf.name
        # Now download to the created temp file paths
        audio_blob = bucket.blob(audio_gcs_path)
        pdf_blob = bucket.blob(pdf_gcs_path)
        audio_blob.download_to_filename(temp_audio_path)
        print(f"   Downloaded audio to: {temp_audio_path}")
        pdf_blob.download_to_filename(temp_pdf_path)
        print(f"   Downloaded PDF to: {temp_pdf_path}")

        # --- Upload temporary files to Gemini ---
        print("⬆️ Uploading temporary files to Gemini API...")
        uploaded_audio_ref = genai.upload_file(path=temp_audio_path, mime_type="audio/wav")
        uploaded_pdf_ref = genai.upload_file(path=temp_pdf_path, mime_type="application/pdf")
        print(f"✅ Files uploaded to Gemini. Audio URI: {uploaded_audio_ref.uri}, PDF URI: {uploaded_pdf_ref.uri}")

    except Exception as e:
        print(f"🔥 Error during setup, download, or Gemini upload: {e}")
        # No need to return here, finally block will execute for cleanup,
        # then the exception will propagate up to the calling route.
        raise # Re-raise the exception to be caught by the calling route

    finally:
        # --- IMPORTANT: Clean up temporary files ---
        if temp_audio_path and os.path.exists(temp_audio_path):
            try:
                os.remove(temp_audio_path)
                print(f"🧹 Cleaned up temporary audio file: {temp_audio_path}")
            except Exception as e_clean:
                 print(f"⚠️ Error cleaning up temp audio file {temp_audio_path}: {e_clean}")
        if temp_pdf_path and os.path.exists(temp_pdf_path):
            try:
                os.remove(temp_pdf_path)
                print(f"🧹 Cleaned up temporary PDF file: {temp_pdf_path}")
            except Exception as e_clean:
                print(f"⚠️ Error cleaning up temp PDF file {temp_pdf_path}: {e_clean}")
        # --- End Cleanup ---

    # --- Construct Contents for Gemini API Call ---
    # This part MUST be *after* the finally block, ensuring uploads were attempted
    # and cleanup was done, but *before* calling generate_content.
    # It also assumes the try block succeeded if we reach this point without an error being raised.
    if not uploaded_audio_ref or not uploaded_pdf_ref:
         # This case should ideally not be reached if the 'try' block raises errors properly,
         # but it's a safeguard.
         print("🔥 Critical error: Gemini file references are missing after upload attempt.")
         return "Internal error: Failed to get file references.", None

    # ***** CORRECTED VARIABLE NAMES AND PLACEMENT *****
    contents = [{
        "role": "user",
        "parts": [
            {"file_data": {"file_uri": uploaded_audio_ref.uri, "mime_type": uploaded_audio_ref.mime_type}},
            {"file_data": {"file_uri": uploaded_pdf_ref.uri, "mime_type": uploaded_pdf_ref.mime_type}},
            {"text": (
                "First, transcribe the user's question from the audio file. "
                "Then, answer the transcribed question based *only* on the information "
                "contained within the provided PDF document. Provide details and context "
                "from the document. Do not mention or read any '*' characters found in the text."
                "Start your response with 'Transcription:' followed by the question, then 'Answer:' followed by the answer."
            )}
        ]
    }]
    # ***** END CORRECTION *****

    # --- Generate content text from Gemini ---
    answer_text = None
    try:
        print("🤖 Requesting text generation from Gemini...")
        response = model.generate_content(
            contents,
            generation_config={
                "temperature": 0.7,
                "top_p": 0.95,
                "top_k": 40,
                "max_output_tokens": 8192,
             }
        )
        response.resolve()
        answer_text = response.text
        print("✅ Gemini returned text response.")
        # print(f"   Response Text: {answer_text[:200]}...")

    except Exception as e:
        print(f"🔥 Error during Gemini content generation: {e}")
        # Return the error message and None for TTS path
        return f"Error generating content: {e}", None

    # --- Generate TTS ---
    tts_gcs_path = None
    if answer_text:
        timestamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
        base_audio_name = os.path.splitext(os.path.basename(audio_gcs_path))[0]
        tts_filename_base = f"{timestamp}_{base_audio_name}_response.wav"
        tts_blob_name = f"{TTS_PREFIX}{tts_filename_base}"
        try:
            tts_gcs_path = text_to_speech(answer_text, tts_blob_name)
        except Exception as e:
            print(f"🔥 TTS generation failed: {e}")
            # Return text answer even if TTS fails
            return answer_text, None
    else:
        print("⚠️ No answer text generated or previous error occurred, skipping TTS.")
        # If answer_text is None due to generation error, we already returned.
        # If answer_text is None because Gemini returned nothing, return None/None.
        return None, None

    # --- Return successful results ---
    return answer_text, tts_gcs_path

def get_gcs_files_info(prefix, allowed_exts):
    # ... (implementation remains the same - lists blobs, sorts by updated desc) ...
    files_info = []
    print(f" Lsting files in gs://{BUCKET_NAME}/{prefix}...")
    try:
        blobs = storage_client.list_blobs(BUCKET_NAME, prefix=prefix)
        count = 0
        for blob in blobs:
            if blob.name == prefix: continue
            filename = os.path.basename(blob.name)
            if allowed_file(filename, allowed_exts):
                files_info.append({
                    "blob_name": blob.name,
                    "filename": filename,
                    "updated": blob.updated
                })
                count += 1
        files_info.sort(key=lambda x: x['updated'], reverse=True)
        print(f"   Found {count} files matching criteria.")
    except Exception as e:
        print(f"🔥 Error listing files in GCS prefix '{prefix}': {e}")
    return files_info

@app.route('/')
def index():
    status = request.args.get('status')
    message = request.args.get('message')
    audio_files = [f['filename'] for f in get_gcs_files_info(UPLOAD_PREFIX, ALLOWED_AUDIO_EXTS)]
    pdf_files = [f['filename'] for f in get_gcs_files_info(PDF_PREFIX, ALLOWED_PDF_EXTS)]
    tts_files = [f['filename'] for f in get_gcs_files_info(TTS_PREFIX, ALLOWED_AUDIO_EXTS)]
    current_book_filename = os.path.basename(current_book_gcs_path) if current_book_gcs_path else None
    return render_template('index.html', audio_files=audio_files, pdf_files=pdf_files, tts_files=tts_files,
                           current_book=current_book_filename, status=status, status_message=message)

@app.route('/upload_book', methods=['POST'])
def upload_book():
    global current_book_gcs_path
    file = request.files.get('book_pdf')
    if not file or not allowed_file(file.filename, ALLOWED_PDF_EXTS):
        return redirect(url_for('index', status='error', message='Invalid or no file selected.'))
    fname = secure_filename(file.filename)
    blob_name = f"{PDF_PREFIX}{fname}"
    try:
        bucket.blob(blob_name).upload_from_file(file.stream, content_type='application/pdf')
        current_book_gcs_path = blob_name
        return redirect(url_for('index', status='success', message='Book uploaded.'))
    except Exception as e:
        return redirect(url_for('index', status='error', message=str(e)))

@app.route('/upload', methods=['POST'])
def upload_audio():
    global current_book_gcs_path # Declare global as we might modify it here
    print("📥 Audio upload route hit.")

    # --- Determine which PDF to use ---
    pdf_gcs_path_to_use = None

    if current_book_gcs_path:
        # 1. A book was explicitly uploaded/selected in this session. Use it.
        pdf_gcs_path_to_use = current_book_gcs_path
        print(f"✅ Using explicitly selected book: gs://{BUCKET_NAME}/{pdf_gcs_path_to_use}")
    else:
        # 2. No book explicitly selected. Find the latest uploaded PDF in GCS.
        print("⚠️ No book selected in session. Searching GCS for the latest PDF...")
        pdf_files_info = get_gcs_files_info(PDF_PREFIX, ALLOWED_PDF_EXTS)

        if not pdf_files_info:
            # 2a. No PDFs found in the bucket at all. Error out.
            print("❌ No PDF books found in the GCS bucket.")
            # Redirect with a specific message
            return redirect(url_for('index', status='error', message='No books have been uploaded yet. Please upload a book first.'))
        else:
            # 2b. Found PDFs. Use the latest one (the first item after sorting).
            latest_book_info = pdf_files_info[0]
            pdf_gcs_path_to_use = latest_book_info['blob_name']
            # IMPORTANT: Update the global state so the UI shows this book as selected
            # on the next page load.
            current_book_gcs_path = pdf_gcs_path_to_use
            print(f"✅ Automatically selected latest uploaded book: gs://{BUCKET_NAME}/{pdf_gcs_path_to_use} (Uploaded: {latest_book_info['updated']})")

    # --- Now we have 'pdf_gcs_path_to_use' set ---

    # 3. Validate audio file (same as before)
    file = request.files.get('audio_data')
    if not file or not file.filename:
        return redirect(url_for('index', status='error', message='No audio file provided.'))

    # --- Filename handling (same as before) ---
    audio_filename_base = ""
    if file.filename == 'blob' or not allowed_file(file.filename, ALLOWED_AUDIO_EXTS):
        timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        audio_filename_base = f"{timestamp}_query.wav"
        content_type = file.content_type if file.content_type and file.content_type.startswith('audio/') else 'audio/wav'
        print(f"⚠️ Filename ambiguous or invalid, using generated name: {audio_filename_base} with type {content_type}")
    elif not allowed_file(file.filename, ALLOWED_AUDIO_EXTS):
        return redirect(url_for('index', status='error', message='Invalid audio file type (WAV only).'))
    else:
        audio_filename_base = secure_filename(file.filename)
        content_type = file.content_type or 'audio/wav'

    # 4. Save audio to GCS (same as before)
    audio_blob_name = f"{UPLOAD_PREFIX}{audio_filename_base}"
    audio_blob = bucket.blob(audio_blob_name)
    try:
        print(f"☁️ Uploading audio query to gs://{BUCKET_NAME}/{audio_blob_name}...")
        audio_blob.upload_from_file(file.stream, content_type=content_type)
        print(f"✅ Saved audio query: {audio_blob_name}")
    except Exception as e:
        print(f"🔥 Error uploading audio query to GCS: {e}")
        return redirect(url_for('index', status='error', message=f"Error saving audio file: {e}"))

    # 5. Generate response using the determined PDF path
    try:
        print("🚀 Calling Gemini generate()...")
        # *** Use the determined path here ***
        answer_text, tts_gcs_path = generate(audio_blob_name, pdf_gcs_path_to_use)
        print("✅ Gemini process finished.")

        # --- Save transcript (optional, same as before) ---
        if answer_text and tts_gcs_path:
             transcript_filename = os.path.basename(tts_gcs_path).replace('.wav', '.txt')
             transcript_blob_name = f"{TRANSCRIPT_PREFIX}{transcript_filename}"
             try:
                 transcript_blob = bucket.blob(transcript_blob_name)
                 print(f"☁️ Saving transcript to gs://{BUCKET_NAME}/{transcript_blob_name}...")
                 transcript_blob.upload_from_string(answer_text, content_type='text/plain; charset=utf-8')
                 print(f"📝 Transcript saved to GCS: {transcript_blob_name}")
             except Exception as e:
                 print(f"⚠️ Error saving transcript to GCS: {e}")

        # --- Redirect with status based on outcome (same as before) ---
        redirect_status = 'error'
        redirect_message = 'Processing failed.'
        if tts_gcs_path:
            redirect_status = 'success'
            redirect_message = 'Question processed successfully!'
        elif answer_text:
             redirect_status = 'warning'
             redirect_message = 'Question processed, but audio generation failed.'
        else:
            redirect_status = 'error'
            redirect_message = 'Failed to generate response.'

        return redirect(url_for('index', status=redirect_status, message=redirect_message))

    except Exception as e:
        print(f"🔥 Error during Gemini/TTS processing: {e}")
        # Ensure error context is passed if possible
        error_message = f"Error processing request: {str(e)[:100]}" # Limit error length
        return redirect(url_for('index', status='error', message=error_message))
    


@app.route('/view/<path:blob_path>')
def serve_gcs_file_redirect(blob_path):
    blob = bucket.get_blob(blob_path)
    if not blob:
        return redirect(url_for('index', status='error', message='File not found.')), 404
    try:
        signed_url = blob.generate_signed_url(version="v4", expiration=timedelta(minutes=15), method="GET")
        return redirect(signed_url)
    except Exception as e:
        return redirect(url_for('index', status='error', message='Signed URL error.')), 500

@app.route('/script.js')
def serve_script():
    return send_from_directory('.', 'script.js')

if __name__ == '__main__':
    app.run(debug=True)

