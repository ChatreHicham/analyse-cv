import os
import json
from flask import Flask, request, jsonify
from flask_cors import CORS
from PyPDF2 import PdfReader
import requests
from dotenv import load_dotenv
import traceback

load_dotenv()

app = Flask(__name__)
CORS(app)

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

def extract_text_from_pdf(file_path):
    """Extrait le texte d'un fichier PDF."""
    with open(file_path, "rb") as file:
        reader = PdfReader(file)
        text = ""
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text
    return text

def build_prompt(cv_text, job_title):
    return f"""
Tu es un assistant expert en recrutement.

Voici un CV extrait d’un fichier PDF. Le poste ciblé est : "{job_title}".

Ta mission :
- Analyse objectivement le CV.
- Structure les informations de façon claire et organisée.
- Sois honnête : si le profil ne correspond pas au poste, dis-le.

Retourne un JSON structuré comme ceci :
{{
  "name": "Nom complet",
  "email": "Adresse email",
  "phone": "Téléphone",
  "language": "Langue du CV",
  "competences":[
  "Présente chaque compétence séparément. Ex :\n- HTML\n- CSS\n- JavaScript\n- ..."
  ],
  "langues": ["Français", "Anglais", ...],
  "formations": [
    {{
      "diplome": "Nom du diplôme",
      "ecole": "Établissement",
      "date": "Dates (ex: 2021-2023)"
    }}
  ],
  "experiences": [
    {{
      "poste": "Poste occupé",
      "entreprise": "Entreprise",
      "date": "Dates (ex: 2020-2022)"
    }}
  ],
  "autres_infos": ["Projets, publications, certifications, etc."],
  "analyse_du_profil": "Analyse critique du profil par rapport au poste visé, si le profil ne convient pas, suggere alors des formations et les competences qui peuvent aider le profil pour devenir illigible au job"
}}

Voici le contenu du CV :
{cv_text}
"""


def analyze_cv_with_openrouter(cv_text, job_title):
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:5500",  # doit correspondre à ton frontend
        "X-Title": "cv-analyzer"
    }

    prompt = build_prompt(cv_text, job_title)

    payload = {
        "model": "openai/gpt-3.5-turbo",  # ✅ Corrigé ici
        "messages": [
            {"role": "system", "content": "Tu es un assistant RH expert."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.3
    }

    response = requests.post(OPENROUTER_API_URL, headers=headers, json=payload)

    if not response.ok:
        return {
            "error": "Appel à OpenRouter échoué",
            "status_code": response.status_code,
            "response": response.text
        }

    try:
        content = response.json()['choices'][0]['message']['content']
        return json.loads(content)
    except Exception as e:
        return {
            "error": "Erreur d'analyse ou de parsing JSON",
            "details": str(e),
            "response": response.text
        }


@app.route('/upload-cv', methods=['POST'])
def upload_cv():
    try:
        if 'file' not in request.files or 'job_title' not in request.form:
            return jsonify({"error": "Fichier PDF et titre de poste requis"}), 400
        

        file = request.files['file']
        job_title = request.form['job_title']

        if file.filename == '' or not file.filename.lower().endswith('.pdf'):
            return jsonify({"error": "Fichier invalide (PDF requis)"}), 400
        

        os.makedirs("./uploads", exist_ok=True)
        file_path = os.path.join("./uploads", file.filename)
        file.save(file_path)

        cv_text = extract_text_from_pdf(file_path)
        os.remove(file_path)

        if not cv_text.strip():
            return jsonify({"error": "Le fichier PDF est vide ou illisible."}), 400

        result = analyze_cv_with_openrouter(cv_text, job_title)
        return jsonify(result)

    except Exception as e:
        return jsonify({
            "error": "Erreur serveur",
            "message": str(e),
            "trace": traceback.format_exc()
        }), 500

if __name__ == '__main__':
    app.run(debug=True, port=8000)
