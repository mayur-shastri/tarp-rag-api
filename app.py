import os
from flask import Flask, request, jsonify
from langchain_huggingface import HuggingFaceEndpoint, HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain.chains import RetrievalQA
from langchain_core.prompts import PromptTemplate
from lessonArchitectPrompt import LESSON_ARCHITECT_PROMPT
from lessonBuilderPrompt import LESSON_BUILDER_PROMPT

# Load environment variables
HF_TOKEN = os.environ.get("HF_TOKEN")
# HUGGINGFACE_REPO_ID = "mistralai/Mistral-7B-Instruct-v0.3"
HUGGINGFACE_REPO_ID = "mistralai/Mixtral-8x7B-Instruct-v0.1"

# Initialize Flask app
app = Flask(__name__)

# Load Embeddings & FAISS Vector DB
DB_FAISS_PATH = "vectorstore/db_faiss"
embedding_model = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2")
db = FAISS.load_local(DB_FAISS_PATH, embedding_model,
                      allow_dangerous_deserialization=True)

def set_custom_prompt_architect(custom_prompt_template):
    prompt = PromptTemplate(template=custom_prompt_template, input_variables=["context", "question"])
    return prompt

def set_custom_prompt_builder(custom_prompt_template):
    prompt = PromptTemplate(template=custom_prompt_template, input_variables=["context", "question"])
    return prompt

# Load LLM Model
def load_llm(huggingface_repo_id):
    try:
        llm = HuggingFaceEndpoint(
            repo_id=huggingface_repo_id,
            temperature=0.5,  # Increased for more creativity
            task="text-generation",
            model_kwargs={
                "token": HF_TOKEN,
                "max_length": 8000  # Increased for longer responses
            }
        )
        return llm
    except Exception as e:
        print(f"Error loading LLM: {str(e)}")
        raise

qa_chain_architect = RetrievalQA.from_chain_type(
    llm=load_llm(HUGGINGFACE_REPO_ID),
    chain_type="stuff",
    retriever=db.as_retriever(search_kwargs={'k': 3}),
    return_source_documents=True,
    chain_type_kwargs={'prompt': set_custom_prompt_architect(LESSON_ARCHITECT_PROMPT)}
)

qa_chain_builder = RetrievalQA.from_chain_type(
    llm=load_llm(HUGGINGFACE_REPO_ID),
    chain_type="stuff",
    retriever=db.as_retriever(search_kwargs={'k': 3}),
    return_source_documents=True,
    chain_type_kwargs={'prompt': set_custom_prompt_builder(LESSON_BUILDER_PROMPT)}
)

def check_query_relevance(llm, query: str) -> str:
    filtering_prompt = f"""
You are a strict academic filter.

Determine if the following question is a valid conceptual or numerical question from Physics, Chemistry, Mathematics, or Biology.

Respond ONLY with:
- "proceed" if the question is appropriate
- "I cannot assist with that" if it is not

Reject questions that:
- Are not academic (e.g., name, biography, history, fact recall)
- Are not from the allowed domains
- Contain inappropriate, offensive, or vague language

Question: "{query}"
Response:
    """
    response = llm.invoke(filtering_prompt)
    result = response.strip().lower()
    return "proceed" if "proceed" in result else "I cannot assist with that"

@app.route("/", methods=["GET"])
def helloWorld():
    return jsonify({
        "message": "Hello World"
    })

@app.route("/rag-query", methods=["POST"])
def get_rag_response():
    data = request.json
    query = data.get("query")
    role = data.get("role")

    if not query:
        return jsonify({"error": "Query is required"}), 400

    # 1. Load the LLM
    llm = load_llm(HUGGINGFACE_REPO_ID)

    # 2. Check the query relevance before using RAG
    check_result = check_query_relevance(llm, query)
    if check_result != "proceed":
        return jsonify({
            "query": query,
            "response": "I cannot assist with that."
        })

    # 3. Proceed with RAG if query is valid
    if(role == "architect"):
      response = qa_chain_architect.invoke({'query': query})
      return jsonify({
          "query": query,
          "response": response["result"],
          "sources": [doc.metadata for doc in response["source_documents"]]
      })
    elif(role == "builder"):
      response = qa_chain_builder.invoke({'query': query})
      print("Builder response:", response)
      return jsonify({
          "query": query,
          "response": response["result"],
          "sources": [doc.metadata for doc in response["source_documents"]]
      })
    return jsonify({
        "error_message" : "Not a valid role"
    })

if __name__ == "__main__":
    PORT = 5000
    try:
        app.run(host="0.0.0.0", port=PORT, debug=True)
        print(f"App started : port : ${PORT}")
    except:
        print("Failed to start flask app")