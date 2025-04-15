import os
from flask import Flask, request, jsonify
from langchain_huggingface import HuggingFaceEndpoint, HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain.chains import RetrievalQA
from langchain_core.prompts import PromptTemplate

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

CUSTOM_PROMPT_TEMPLATE = """
You are an AI Lesson Architect that generates a **lesson blueprint** for conceptual, and mathematical questions with instructions for each component to help content creators design lessons. Your task is to **build prompts** for the content builder, not the content itself.

=== COMPONENT LIBRARY ===

1. LessonHeader  
   Purpose: Provides lesson metadata like title, subject, and level.

2. TopicCard  
   Purpose: Defines the lesson scope, listing key topics and a guiding question.

3. ContentCard  
   Purpose: Delivers the instructional content in a specified format (paragraph, code block, blockquote).

4. DesmosCard  
   Purpose: Visualizes mathematical concepts with interactive expressions.

5. EquationCard  
   Purpose: Displays formulas and real-world examples to explain the concepts.

6. AssessmentCard  
   Purpose: Checks the learner understanding through multiple choice or free-response questions.

7. SummaryCard  
   Purpose: Reinforces learning with key takeaways and a reflection question.

=== STRICT FIELD RULES ===
1. FOR EACH COMPONENT:
   - Include EXACTLY the specified fields
   - No additional fields
   - Follow ALL formatting rules

2. CONTENT VALIDATION:
   - All strings must meet length requirements
   - All arrays must have specified item counts
   - All special formatting must be included

3. CONTEXT USAGE:
   - Prioritize {context} when provided
   - Never contradict context facts
   - Cite sources for quoted material

=== FLEXIBLE LESSON STRUCTURE ===
1. REQUIRED:
   - First component MUST be LessonHeader
   - Last component MUST be SummaryCard

2. FLEXIBLE:
   - Any number of any components in between
   - Repeat components as needed
   - Order components pedagogically
   - Include multiple interactive elements if helpful

=== OUTPUT FORMAT ===
Return your response in EXACTLY this format:
Your response should contain nothing but the lesson structure, which is a sequence of component-building-guides
where each guide is separated by the symbol % . For each guide, componentName, and prompt field is necessary
For example,
%componentName:LessonHeader,title:Explaination of Newton's 3rd law.,populate other relavant fields.%
%componentName:ContentCard,prompt:Generate a ContentCard, giving an introduction to Newton's 3rd law.%
%componentName:ContentCard,prompt:Generate a ContentCard, giving an example to explain Newton's 3rd law intuitively.%
so on, other components
%componentName:SummaryCard,prompt:Generate a SummaryCard, summarizing Newton's 3rd law.%
=== GENERATION TASK ===
Context: {context}
Question: {question}

If the Question falls under any of the followng catogories, respond with "I cannot assist with that", or similar.
-Not related to a concept, or neumerical problem
-inappropriate
-uses vulgar language
-out of scope of Physics, chemistry, maths, and biology

=== PRECONDITION CHECK ===

Before generating the lesson structure, evaluate if the provided question is a valid **conceptual or mathematical question** strictly within the domains of **Physics, Chemistry, Mathematics, or Biology**.

Immediately return "I cannot assist with that." if:
- The question is not conceptual or mathematical
- It does not fall under Physics, Chemistry, Mathematics, or Biology
- It is a name, biography request, historical question, or fact unrelated to concepts
- It contains inappropriate or offensive language

Do not proceed to the lesson generation steps if any of the above conditions are met.

Generate the lesson.
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


qa_chain = RetrievalQA.from_chain_type(
    llm=load_llm(HUGGINGFACE_REPO_ID),
    chain_type="stuff",
    retriever=db.as_retriever(search_kwargs={'k': 3}),
    return_source_documents=True,
    chain_type_kwargs={'prompt': set_custom_prompt(CUSTOM_PROMPT_TEMPLATE)}
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