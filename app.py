from flask import Flask, render_template, request, redirect, send_from_directory #créer le serveur web
import os #gérer les fichiers et dossiers
import requests #envoyer des requêtes HTTP vers Solr
import pdfplumber #lire les fichiers pdf
from docx import Document #lire les fichiers Word
import pandas as pd #lire les fichiers Excel

app = Flask(__name__) #Ici on crée le serveur web Flask

#Les documents uploadés seront stockés dans uploads
UPLOAD_FOLDER = "uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

#application envoie les documents vers : Solr -> collection "documents"
SOLR_URL = "http://localhost:8983/solr/documents/update/json/docs"

#Si le dossier n'existe pas, il est créé.
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)


#Page principale
@app.route("/")
def index():
    return render_template("index.html")


# Upload + Indexation
@app.route("/upload", methods=["POST"]) #route reçoit le fichier envoyé par le formulaire

def upload_file():
    file = request.files["file"] #Flask récupère le fichier envoyé

    if file:
        #Le fichier est sauvegardé dans :uploads/
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], file.filename) 
        file.save(filepath)

        text = extract_text(filepath) #fonction lit le contenu du document

        #crée un document avec 4 champs
        data = {
            "title": file.filename,
            "author": "Unknown",
            "content": text,
            "suggest": file.filename,
            "file_path": filepath
        }

        #document est envoyé vers Solr
        requests.post(SOLR_URL, json=data) 

        #commit obligatoire (Solr indexe le document immédiatement)
        requests.get("http://localhost:8983/solr/documents/update?commit=true")

    return redirect("/")


# Extraction automatique
def extract_text(filepath):
    ext = filepath.split(".")[-1].lower()

    text = ""

    if ext == "pdf":
        with pdfplumber.open(filepath) as pdf:
            for page in pdf.pages:
                text += page.extract_text() or ""

    elif ext == "docx":
        doc = Document(filepath) #lit chaque paragraphe
        for para in doc.paragraphs:
            text += para.text + "\n"

    elif ext == "xlsx":
        df = pd.read_excel(filepath) #convertit les données en texte
        text = df.to_string()

    return text

@app.route("/autocomplete")
def autocomplete():

    term = request.args.get("term")

    url = f"http://localhost:8983/solr/documents/suggest?suggest.q={term}&wt=json"

    response = requests.get(url)

    return response.json()

@app.route("/search")
def search():

    query = request.args.get("q")
    docs = []

    if query:
        solr_url = f"http://localhost:8983/solr/documents/select?q=title:{query}^2 OR content:{query}&fl=*,score&wt=json"
        response = requests.get(solr_url).json()
        docs = response["response"]["docs"]

    return render_template("search.html", docs=docs)

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    #va chercher le fichier dans le dossier uploads/ et le renvoyer au navigateur
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename) 

if __name__ == "__main__":
    app.run(debug=True)