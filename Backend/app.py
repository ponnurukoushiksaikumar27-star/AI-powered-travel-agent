from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from google import genai
from dotenv import load_dotenv
import requests
import tempfile
import base64
import os

load_dotenv()

app = Flask(__name__)
CORS(app)

FRONTEND_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "Frontend")
)

# API keys from environment variables
MURF_API_KEY = os.environ.get("MURF_API_KEY")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

if not MURF_API_KEY:
    raise RuntimeError("MURF_API_KEY is not configured")

if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY is not configured")

client = genai.Client(api_key=GEMINI_API_KEY)


PROMPTS = {
    "Summary": """
You are a professional tourist guide.

Provide a high-level overview of "{place}" in {language}.

Focus on:
- The historical significance
- Why the place is famous
- Key architectural or cultural highlights

Keep the explanation concise, engaging, and easy to follow.
Avoid excessive details and dates.
Limit the response to around 200 words.

Respond ONLY in {language}.
""",

    "Detailed": """
You are a professional tourist guide.

Provide a detailed and immersive explanation of "{place}" in {language}.

Cover:
- Historical background and timeline
- Architectural design and unique features
- Cultural importance and notable events
- Interesting facts and visitor insights

Explain concepts clearly and in a storytelling manner.
Include relevant details and examples.

Limit the response to around 400 words.

Respond ONLY in {language}.
"""
}


@app.route("/")
def home():
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.route("/<path:filename>")
def frontend_files(filename):
    return send_from_directory(FRONTEND_DIR, filename)


def generate_speech(text, voice_id, locale):

    url = "https://global.api.murf.ai/v1/speech/stream"

    headers = {
        "api-key": MURF_API_KEY,
        "Content-Type": "application/json"
    }

    data = {
        "voiceId": voice_id,
        "text": text,
        "locale": locale,
        "model": "falcon-2",
        "format": "MP3",
        "sampleRate": 24000,
        "channelType": "MONO"
    }

    response = requests.post(
        url,
        headers=headers,
        json=data,
        timeout=60
    )

    if response.status_code != 200:
        raise Exception(
            f"Murf API error {response.status_code}: {response.text}"
        )

    temp_audio = tempfile.NamedTemporaryFile(
        suffix=".mp3",
        delete=False
    )

    with open(temp_audio.name, "wb") as f:
        for chunk in response.iter_content(chunk_size=1024):
            if chunk:
                f.write(chunk)

    temp_audio.close()

    return temp_audio.name


def generate_description(place, answer_type, language):

    if answer_type not in PROMPTS:
        raise ValueError("Invalid answer type")

    prompt = PROMPTS[answer_type].format(
        place=place,
        language=language
    )

    response = client.models.generate_content(
        model="gemini-3.1-flash-lite",
        contents=prompt
    )

    return response.text


@app.route("/generate-audio-guide", methods=["POST"])
def generate_audio_guide():

    data = request.get_json()

    place = data["place"]
    answer_type = data["answerType"]
    language = data["language"]
    voice_id = data["voiceId"]
    locale = data["locale"]

    text_description = generate_description(
        place,
        answer_type,
        language
    )

    audio_path = generate_speech(
        text_description,
        voice_id,
        locale
    )

    with open(audio_path, "rb") as audio_file:
        audio_bytes = audio_file.read()

    encoded_audio = base64.b64encode(
        audio_bytes
    ).decode("utf-8")

    return jsonify({
        "description": text_description,
        "audioBase64": encoded_audio
    })


if __name__ == "__main__":
    app.run()