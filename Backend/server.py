import os
import flask
from flask import Flask, request, send_file, jsonify
import openai
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
port = 3000

# Path to files
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RESOURCES_DIR = os.path.join(BASE_DIR, 'resources')
os.makedirs(RESOURCES_DIR, exist_ok=True)

RECORD_FILE = os.path.join(RESOURCES_DIR, 'recording.wav')
VOICED_FILE = os.path.join(RESOURCES_DIR, 'voicedby.wav')

# API Configuration
MAX_TOKENS = 300
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

OLLAMA_BASE_URL = 'http://localhost:11434/v1'

# Initialize OpenAI and Ollama clients
openai.api_key = OPENAI_API_KEY
ollama_client = openai.OpenAI(
    base_url=OLLAMA_BASE_URL,
    api_key='ollama'
)

# Global variable to track file readiness
should_download_file = False

@app.route('/uploadAudio', methods=['POST'])
def upload_audio():
    global should_download_file
    should_download_file = False

    with open(RECORD_FILE, 'wb') as recording_file:
        recording_file.write(request.get_data())

    transcription = speech_to_text_api()
    if transcription:
        if 'on' in transcription and 'light' in transcription:
            requests.get('http://192.168.1.239/cm?cmnd=Power%20On')
            switchStatus = requests.get('http://192.168.1.239/cm?cmnd=Power').json()
            print('Switch Status:', switchStatus)
            # query = f"This is the question from the user: '{transcription}'. Here is the current status of the switch: '{switchStatus}'."          
            gpt_response_to_speech("The light is now turned on.")
        elif 'off' in transcription and 'light' in transcription:
            requests.get('http://192.168.1.239/cm?cmnd=Power%20off')
            switchStatus = requests.get('http://192.168.1.239/cm?cmnd=Power').json()
            gpt_response_to_speech("The light is now turned off.")
        else:
            query = transcription
            call_gpt(query)
        return transcription, 200
    return 'Transcription failed', 500

@app.route('/checkVariable', methods=['GET'])
def check_variable():
    print('Checking variable:', should_download_file)
    return jsonify({"ready":should_download_file})

@app.route('/broadcastAudio', methods=['GET'])
def broadcast_audio():
    try:
        return send_file(
            VOICED_FILE, 
            mimetype='audio/wav'
        )
    except FileNotFoundError:
        return 'File not found', 404

def speech_to_text_api():
    try:
        with open(RECORD_FILE, 'rb') as audio_file:
            transcription = openai.audio.transcriptions.create(
                file=audio_file,
                model="whisper-1",
                response_format="text"
            )
        print('\nYOU:', transcription)          
        return transcription
    except Exception as error:
        print('Error in speechToTextAPI:', str(error))
        return None

def call_gpt(text):
    try:
        messages = [
            {
                "role": "system",
                "content": "You are a helpful home assistant."
            },
            {
                "role": "user",
                "content": text
            }
        ]

        completion = ollama_client.chat.completions.create(
            messages=messages,
            model="llama3.2:latest",
            max_tokens=MAX_TOKENS
        )

        gpt_response = completion.choices[0].message.content
        print('ChatGPT:', gpt_response)
        gpt_response_to_speech(gpt_response)

    except Exception as error:
        print('Error calling GPT:', str(error))

def gpt_response_to_speech(gpt_response):
    global should_download_file
    try:
        speech = openai.audio.speech.create(
            model="tts-1",
            voice="alloy",
            input=gpt_response,
            response_format="wav"
        )

        speech.stream_to_file(VOICED_FILE)
        should_download_file = True
        print("Audio file saved successfully")

    except Exception as error:
        print("Error saving audio file:", str(error))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=port, debug=True)