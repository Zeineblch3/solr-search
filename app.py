from flask import Flask, render_template, request, redirect, send_from_directory
import os 
import requests 
from tika import parser

app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

SOLR_URL = "http://localhost:8983/solr/documents/update/json/docs"

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/upload", methods=["POST"]) 

def upload_file():
    file = request.files["file"]

    if file:
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], file.filename) 
        file.save(filepath)

        text, author = extract_text(filepath) 

        data = {
            "title": file.filename,
            "author": author, 
            "content": text,
            "suggest": file.filename,
            "file_path": filepath
        }

        requests.post(SOLR_URL, json=data)
        requests.get("http://localhost:8983/solr/documents/update?commit=true")

    return redirect("/")


def extract_text(filepath):
    parsed = parser.from_file(filepath)
    content = parsed.get("content") or ""
    metadata = parsed.get("metadata") or {}

    author = metadata.get("author", "Unknown")

    return content, author


@app.route("/autocomplete")
def autocomplete():
    term = request.args.get("term")

    url = f"http://localhost:8983/solr/documents/select?q=title:{term}*&fl=title&rows=5&wt=json"
    response = requests.get(url).json()

    suggestions = [
        doc["title"][0]
        for doc in response["response"]["docs"]
    ]

    return {"suggestions": suggestions}

@app.route("/search")
def search():

    query = request.args.get("q")
    field = request.args.get("field", "all")
    author_filter = request.args.get("author")

    docs = []
    facets = {}

    if query:

        if field == "title":
            solr_query = f"title:{query}"
        elif field == "author":
            solr_query = f"author:{query}"
        elif field == "content":
            solr_query = f"content:{query}"
        else:
            solr_query = f"title:{query} OR content:{query} OR author:{query}"

        fq = ""
        if author_filter:
            fq = f"&fq=author:{author_filter}"

        solr_url = f"http://localhost:8983/solr/documents/select?q={solr_query}&fl=*,score&facet=true&facet.field=author&wt=json{fq}"

        response = requests.get(solr_url).json()

        docs = response["response"]["docs"]

        facet_data = response.get("facet_counts", {}).get("facet_fields", {})

        for field_name, values in facet_data.items():
            facets[field_name] = []
            for i in range(0, len(values), 2):
                facets[field_name].append({
                    "value": values[i],
                    "count": values[i+1]
                })

    return render_template("search.html", docs=docs, facets=facets)

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename) 

if __name__ == "__main__":
    app.run(debug=True)