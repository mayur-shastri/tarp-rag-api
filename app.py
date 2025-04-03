import os
from flask import Flask, request, jsonify
from langchain_huggingface import HuggingFaceEndpoint, HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain.chains import RetrievalQA
from langchain_core.prompts import PromptTemplate

# Load environment variables
HF_TOKEN = os.environ.get("HF_TOKEN")
HUGGINGFACE_REPO_ID = "mistralai/Mistral-7B-Instruct-v0.3"

# Initialize Flask app
app = Flask(__name__)

# Load Embeddings & FAISS Vector DB
DB_FAISS_PATH = "vectorstore/db_faiss"
embedding_model = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2")
db = FAISS.load_local(DB_FAISS_PATH, embedding_model,
                      allow_dangerous_deserialization=True)

# Define Custom Prompt
CUSTOM_PROMPT_TEMPLATE = """
Use the pieces of information provided in the context to answer the user's question.
If you don't know the answer, just say that you don't know. Don't try to make up an answer.
Only use the given context.

Context: {context}
Question: {question}

Start the answer directly. No small talk please.
"""


def set_custom_prompt(custom_prompt_template):
    prompt = PromptTemplate(template=custom_prompt_template, input_variables=[
                            "context", "question"])
    return prompt

# Load LLM Model


def load_llm(huggingface_repo_id):
    try:
        llm = HuggingFaceEndpoint(
            repo_id=huggingface_repo_id,
            temperature=0.5,
            task="text-generation",
            model_kwargs={
                "token": HF_TOKEN,
                "max_length": 512
            }
        )
        return llm
    except Exception as e:
        print(f"Error loading LLM: {str(e)}")
        raise


qa_chain = RetrievalQA.from_chain_type(
    llm=load_llm(HUGGINGFACE_REPO_ID),
    chain_type="stuff",
    retriever=db.as_retriever(search_kwargs={'k': 3}),
    return_source_documents=True,
    chain_type_kwargs={'prompt': set_custom_prompt(CUSTOM_PROMPT_TEMPLATE)}
)


@app.route("/", methods=["GET"])
def helloWorld():
    return jsonify({
        "message": "Hello World"
    })


@app.route("/rag-query", methods=["POST"])
def get_rag_response():
    data = request.json
    query = data.get("query")

    if not query:
        return jsonify({"error": "Query is required"}), 400

    response = qa_chain.invoke({'query': query})

    return jsonify({
        "query": query,
        "response": response["result"],
        "sources": [doc.metadata for doc in response["source_documents"]]
    })


if __name__ == "__main__":
    PORT = 5000
    try:
        app.run(host="0.0.0.0", port=PORT, debug=True)
        print(f"App started : port : ${PORT}")
    except:
        print("Failed to start flask app")