import streamlit as st
from openai import OpenAI
import dotenv
import os
import json
from PyPDF2 import PdfReader
from PIL import Image
from io import BytesIO
import pandas as pd
from fpdf import FPDF
import base64

#this is the potential part for the upcoming paywall


st.set_page_config(page_title="SmartExam Creator", page_icon="📝")

dotenv.load_dotenv()

# Load your OpenAI API key from the environment variable
# OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")   Use this when taking the env variables

OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]  #And this secrets, when using streamlit

openai_models = [
    "gpt-4o-mini",
    "gpt-4-turbo",
    "gpt-3.5-turbo-16k",
]

# Function to query and stream the response from the LLM
def stream_llm_response(messages, model_params, api_key=OPENAI_API_KEY):
    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model=model_params["model"] if "model" in model_params else "gpt-4o",
        messages=messages,
        temperature=model_params["temperature"] if "temperature" in model_params else 0.3,
        max_tokens=4096,
    )
    return response.choices[0].message.content

def extract_text_from_pdf(pdf_file):
    pdf_reader = PdfReader(pdf_file)
    text = ""
    for page in pdf_reader.pages:
        text += page.extract_text() + "\n"
    return text

def summarize_text(text, api_key=OPENAI_API_KEY):
    prompt = (
        "Please summarize the following text to be concise and to the point:\n\n" + text
    )
    messages = [
        {"role": "user", "content": prompt},
    ]
    summary = stream_llm_response(messages, model_params={"model": "gpt-4o-mini", "temperature": 0.3}, api_key=api_key)
    return summary

def chunk_text(text, max_tokens=3000):
    sentences = text.split('. ')
    chunks = []
    chunk = ""
    for sentence in sentences:
        if len(chunk) + len(sentence) > max_tokens:
            chunks.append(chunk)
            chunk = sentence + ". "
        else:
            chunk += sentence + ". "
    if chunk:
        chunks.append(chunk)
    return chunks

def generate_mc_questions(content_text, api_key=OPENAI_API_KEY):
    prompt = (
        "You are a professor in the field of Computational System Biology and should create an exam on the topic of the Input PDF. "
        "Using the attached lecture slides (please analyze thoroughly), create a Master-level multiple-choice exam. The exam should contain multiple-choice and single-choice questions, "
        "appropriately marked so that students know how many options to select. Create 30 realistic exam questions covering the entire content. Provide the output in JSON format. "
        "The JSON should have the structure: [{'question': '...', 'choices': ['...'], 'correct_answer': '...', 'explanation': '...'}, ...]. Ensure the JSON is valid and properly formatted."
    )
    messages = [
        {"role": "user", "content": content_text},
        {"role": "user", "content": prompt},
    ]
    response = stream_llm_response(messages, model_params={"model": "gpt-4o-mini", "temperature": 0.3}, api_key=api_key)
    return response

def parse_generated_questions(response):
    try:
        # Find the JSON part within the response string
        json_start = response.find('[')
        json_end = response.rfind(']') + 1
        json_str = response[json_start:json_end]

        questions = json.loads(json_str)
        return questions
    except json.JSONDecodeError as e:
        st.error(f"JSON parsing error: {e}")
        st.error("Response from OpenAI:")
        st.text(response)
        return None

def get_question(index, questions):
    return questions[index]

def initialize_session_state(questions):
    session_state = st.session_state
    session_state.current_question_index = 0
    session_state.quiz_data = get_question(session_state.current_question_index, questions)
    session_state.correct_answers = 0

class PDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 12)
        self.cell(0, 10, 'Generated Exam', 0, 1, 'C')

    def chapter_title(self, title):
        self.set_font('Arial', 'B', 12)
        self.multi_cell(0, 10, title)
        self.ln(5)

    def chapter_body(self, body):
        self.set_font('Arial', '', 12)
        self.multi_cell(0, 10, body)
        self.ln()

def generate_pdf(questions):
    pdf = PDF()
    pdf.add_page()
    
    for i, q in enumerate(questions):
        question = f"Q{i+1}: {q['question']}"
        pdf.chapter_title(question)
        
        choices = "\n".join(q['choices'])
        pdf.chapter_body(choices)
        
        correct_answer = f"Correct answer: {q['correct_answer']}"
        pdf.chapter_body(correct_answer)
        
        explanation = f"Explanation: {q['explanation']}"
        pdf.chapter_body(explanation)

    return pdf.output(dest="S").encode("latin1")

def main():
    if 'app_mode' not in st.session_state:
        st.session_state.app_mode = "Upload PDF & Generate Questions"
        
    st.sidebar.title("SmartExam Creator")
    
    app_mode_options = ["Upload PDF & Generate Questions", "Take the Quiz", "Download as PDF"]
    st.session_state.app_mode = st.sidebar.selectbox("Choose the app mode", app_mode_options, index=app_mode_options.index(st.session_state.app_mode))

    st.sidebar.markdown("## About")
    st.sidebar.info(
        """
        **SmartExam Creator** is an innovative tool designed to help students and educators alike. 
        Upload your lecture notes or handwritten notes to create personalized multiple-choice exams.

        **Story:**
        This app was developed with the vision of making exam preparation easier and more interactive for students. 
        Leveraging the power new AI models, it aims to transform traditional study methods into a more engaging and 
        efficient process. Whether you're a student looking to test your knowledge or an educator seeking to create 
        customized exams, SmartExam Creator is here to help.

        **What makes SmartExam special ?**
        Apart from other platforms that require costly subscriptions, this platform is designed from a STEM student
        for all other students, but let us be honest, we do not have money for Subscriptions. That is why it is completely free for now.
        I have designed the app as cost efficient as possible, so I can cover all business costs that are coming.  
        
        **Features:**
        - Upload PDF documents
        - Generate multiple-choice questions
        - Take interactive quizzes
        - Download generated exams as PDF

        Built with ❤️ using OpenAI's GPT-4o-mini.

        **Connect with me on [LinkedIn](https://www.linkedin.com/in/laurin-herbst/).**
        """
    )
    if st.session_state.app_mode == "Upload PDF & Generate Questions":
        pdf_upload_app()
    elif st.session_state.app_mode == "Take the Quiz":
        if 'mc_test_generated' in st.session_state and st.session_state.mc_test_generated:
            if 'generated_questions' in st.session_state and st.session_state.generated_questions:
                mc_quiz_app()
            else:
                st.warning("No generated questions found. Please upload a PDF and generate questions first.")
        else:
            st.warning("Please upload a PDF and generate questions first.")
    elif st.session_state.app_mode == "Download as PDF":
        download_pdf_app()

def pdf_upload_app():

    st.title("Upload Your Lecture - Create Your Test Exam")
    st.subheader("Show Us the Slides and We do the Rest")

    content_text = ""
    
    # Initialize session state for messages
    if 'messages' not in st.session_state:
        st.session_state.messages = []
    
    # PDF Upload
    uploaded_pdf = st.file_uploader("Upload a PDF document", type=["pdf"])
    if uploaded_pdf:
        pdf_text = extract_text_from_pdf(uploaded_pdf)
        content_text += pdf_text
        st.success("PDF content added to the session.")
    
    if len(content_text) > 3000:  # Check if the content text is too large
        content_text = summarize_text(content_text)  # Summarize if too large

    if content_text:
        st.info("Generating the exam from the uploaded content. It will take just a minute...")
        chunks = chunk_text(content_text)  # Chunk the text if necessary
        questions = []
        for chunk in chunks:
            response = generate_mc_questions(chunk)
            parsed_questions = parse_generated_questions(response)
            if parsed_questions:
                questions.extend(parsed_questions)
        if questions:
            st.session_state.generated_questions = questions
            st.session_state.content_text = content_text
            st.session_state.mc_test_generated = True
            st.success("The game has been successfully created!")
        else:
            st.error("Failed to parse the generated questions. Please check the OpenAI response.")
    else:
        st.warning("Please upload a PDF to generate the exam content.")

def submit_answer(i, quiz_data):
    user_choice = st.session_state[f"user_choice_{i}"]
    st.session_state.answers[i] = user_choice
    if user_choice == quiz_data['correct_answer']:
        st.session_state.feedback[i] = ("Correct", quiz_data.get('explanation', 'No explanation available'))
        st.session_state.correct_answers += 1
    else:
        st.session_state.feedback[i] = ("Incorrect", quiz_data.get('explanation', 'No explanation available'), quiz_data['correct_answer'])

def mc_quiz_app():
    st.title('Multiple Choice Game')
    st.subheader('Here is always one correct answer per question')

    questions = st.session_state.generated_questions

    if questions:  # Ensure questions list is not empty
        if 'answers' not in st.session_state:
            st.session_state.answers = [None] * len(questions)
            st.session_state.feedback = [None] * len(questions)
            st.session_state.correct_answers = 0

        for i, quiz_data in enumerate(questions):
            st.markdown(f"### Question {i+1}: {quiz_data['question']}")

            if st.session_state.answers[i] is None:
                user_choice = st.radio("Choose an answer:", quiz_data['choices'], key=f"user_choice_{i}")
                st.button(f"Submit your answer {i+1}", key=f"submit_{i}", on_click=submit_answer, args=(i, quiz_data))
            else:
                st.radio("Choose an answer:", quiz_data['choices'], key=f"user_choice_{i}", index=quiz_data['choices'].index(st.session_state.answers[i]), disabled=True)
                if st.session_state.feedback[i][0] == "Correct":
                    st.success(st.session_state.feedback[i][0])
                else:
                    st.error(f"{st.session_state.feedback[i][0]} - Correct answer: {st.session_state.feedback[i][2]}")
                st.markdown(f"Explanation: {st.session_state.feedback[i][1]}")

        if all(answer is not None for answer in st.session_state.answers):
            score = st.session_state.correct_answers
            total_questions = len(questions)
            st.write(f"""
                <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100vh;">
                    <h1 style="font-size: 3em; color: gold;">🏆</h1>
                    <h1>Your Score: {score}/{total_questions}</h1>
                </div>
            """, unsafe_allow_html=True)



def download_pdf_app():
    st.title('Download Your Exam as PDF')

    questions = st.session_state.generated_questions

    if questions:
        for i, q in enumerate(questions):
            st.markdown(f"### Q{i+1}: {q['question']}")
            for choice in q['choices']:
                st.write(choice)
            st.write(f"**Correct answer:** {q['correct_answer']}")
            st.write(f"**Explanation:** {q['explanation']}")
            st.write("---")  # Separator line

        pdf_bytes = generate_pdf(questions)
        st.download_button(
            label="Download PDF",
            data=pdf_bytes,
            file_name="generated_exam.pdf",
            mime="application/pdf"
        )

if __name__ == '__main__':
    main()
