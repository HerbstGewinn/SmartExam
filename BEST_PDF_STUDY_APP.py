import streamlit as st
import time  # Import the time module to use sleep

# This must be the first Streamlit command
st.set_page_config(page_title="SmartExam Creator", page_icon="📝")

from st_supabase_connection import SupabaseConnection
from stqdm import stqdm
from supabase import Client 
from openai import OpenAI
import dotenv
import os
import json
from PyPDF2 import PdfReader
from PIL import Image
from io import BytesIO
from fpdf import FPDF
import base64
import PyPDF2
from streamlit_supabase_auth import login_form, logout_button
from supabase import create_client, Client
from st_pages import show_pages_from_config

__version__ = "1.1.0"

show_pages_from_config()

hide_streamlit_style = """
<style>
div[data-testid="stToolbar"] {
visibility: hidden;
height: 0%;
position: fixed;
}
div[data-testid="stDecoration"] {
visibility: hidden;
height: 0%;
position: fixed;
}
div[data-testid="stStatusWidget"] {
visibility: hidden;
height: 0%;
position: fixed;
}
#MainMenu {
visibility: hidden;
height: 0%;
}
header {
visibility: hidden;
height: 0%;
}
footer {
visibility: hidden;
height: 0%;
}
</style>
"""
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

# Load environment variables
dotenv.load_dotenv()

hide_default_format = """
       <style>
       #MainMenu {visibility: hidden; }
       footer {visibility: hidden;}
       </style>
       """
st.markdown(hide_default_format, unsafe_allow_html=True)

#Show info banner
st.info(
" We are currently investigating a bug with the Smartexam Generator Feature. We are really sorry for the inconvenience and are working on fixing it. "
)
#st.info trying for informational banner

#Apis

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Resetting quiz state

def reset_quiz_state():
    """Resets the session state for a new quiz, ensuring fresh state for each new upload."""
    st.session_state.answers = []
    st.session_state.feedback = []
    st.session_state.correct_answers = 0
    st.session_state.mc_test_generated = False
    st.session_state.generated_questions = []
    st.session_state.content_text = None
    st.session_state.current_question_index = 0
    st.session_state.quiz_data = None
    st.session_state.quiz_active = False
    st.session_state.last_upload_content = ""

def initialize_app():
    if "app_mode" not in st.session_state:
        st.session_state.app_mode = "Upload PDF & Generate Questions"
    if "quiz_active" not in st.session_state:
        st.session_state.quiz_active = False

def sidebar_reset_button():
    if st.sidebar.button("New Exam"):
        reset_quiz_state()
        st.session_state.app_mode = "Upload PDF & Generate Questions"
        st.session_state.quiz_active = False
        st.rerun()

# Main app functions
def stream_llm_response(messages, model_params, api_key):
    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model=model_params["model"] if "model" in model_params else "gpt-4o-mini",
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

# Function to fetch the subscription tier from Supabase
def fetch_subscription_tier(user_id):
    response = supabase.table("user_data").select("subscription_tier", "mc_upload_count").eq("id", user_id).execute()
    if response.data and len(response.data) > 0:
        return response.data[0]["subscription_tier"], response.data[0]["mc_upload_count"]
    else:
        return None, None

# Function to increment pdf_upload_count in the database
def increment_mc_upload_count(user_id):
    response = supabase.rpc("increment_mc_upload_count", {"user_uuid": user_id}).execute()
    st.write(f"MC Upload Count Increment Response: {response}")  # Debugging response

def summarize_text(text, api_key=st.secrets["OPENAI_API_KEY"]):
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

def generate_mc_questions(content_text, api_key=st.secrets["OPENAI_API_KEY"]):
    # Explicitly ask for JSON output
    prompt = (
        f"You are a university professor. Using the provided lecture content, create a Master-level multiple-choice exam in strict JSON format that includes 25 questions. "
        f"Ensure the structure is:\n\n"
        f"[{{'question': '...', 'choices': ['...'], 'correct_answer': '...', 'explanation': '...'}}, ...]\n\n"
        f"Content:\n\n{content_text}"
    )
    messages = [{"role": "user", "content": prompt}]
    response = stream_llm_response(messages, model_params={"model": "gpt-4o-mini", "temperature": 0.3}, api_key=api_key)
    return response

# Function to parse questions, with fallback to plain text display if parsing fails
def parse_generated_questions(response):
    try:
        # Attempt to parse JSON if it's in expected format
        json_start = response.find('[')
        json_end = response.rfind(']') + 1
        json_str = response[json_start:json_end]
        questions = json.loads(json_str)
        return questions
    except json.JSONDecodeError:
        # If parsing fails, display raw response as text output
        st.warning("Unable to parse as JSON. Displaying response as text.")
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
        question = question.replace("—", "-").encode('latin1', 'replace').decode('latin1')
        pdf.chapter_title(question)

        choices = "\n".join(q['choices'])
        choices = choices.replace("—", "-").encode('latin1', 'replace').decode('latin1')
        pdf.chapter_body(choices)

        correct_answer = f"Correct answer: {q['correct_answer']}"
        correct_answer = correct_answer.replace("—", "-").encode('latin1', 'replace').decode('latin1')
        pdf.chapter_body(correct_answer)

        explanation = f"Explanation: {q['explanation']}"
        explanation = explanation.replace("—", "-").encode('latin1', 'replace').decode('latin1')
        pdf.chapter_body(explanation)

    return pdf.output(dest="S").encode("latin1")

# Integration with the main app
def main():
    initialize_app()  # Initialize app mode and quiz state tracking
    sidebar_reset_button()  # Add "Neu Starten" button to sidebar for resetting state

    session = login_form(
        url=SUPABASE_URL,
        apiKey=SUPABASE_KEY,
        providers=["google"],
    )
    
     # If the user is not logged in, stop the app
    if not session:
           st.stop()
           


    # Sidebar with logout button and user welcome message
    with st.sidebar:
        st.write(f"Welcome {session['user']['email']}")
        logout_button()

    # Fetch and display the user's subscription tier and PDF upload count
    user_id = session['user']['id']  # Get the user ID from the session
    subscription_tier, mc_upload_count = fetch_subscription_tier(user_id)

    st.sidebar.write(f"Subscription Tier: **{subscription_tier}**")
    st.sidebar.write(f"Exams created: **{mc_upload_count}**")

    # --- Check if the user has reached the usage limit ---
    # Only enforce usage limit if the subscription tier is "FREE"
    if subscription_tier == "FREE":
        # Check if the mc_upload_count is greater than or equal to 2
        if mc_upload_count and mc_upload_count >= 3:
            st.error("You have reached your free usage limit. We want to give you a limited offer: only 19.99$ One-Time Payment for Lifetime Access to all functions.")

            # Display the "Upgrade Now" button only when the limit is exceeded
            if st.button("Upgrade Now"):
                # Meta-refresh-based redirect
                redirect_url = "https://smartexam.streamlit.app/Pricing"
                st.markdown(f"""
                    <meta http-equiv="refresh" content="0; url={redirect_url}">
                """, unsafe_allow_html=True)

            st.stop()  # Stop further interaction if the limit is reached #return changed to st.stop
       else:
              st.info("Welcome, FREE user! You still have uploads available. Enjoy the features.")       #Added to allow access to free users with less than 3 uploads
       elif subscription_tier in ["PREMIUM", "PRO"]:
              st.success("Welcome, PREMIUM/PRO user! You have unlimited access to all features.")       #Added for handling the Premium/pro users 
    # If the subscription tier is "PREMIUM" or "PRO", grant full access without restriction
       #if subscription_tier in ["PREMIUM", "PRO"]:
        # Main app content
        dotenv.load_dotenv()

        st.sidebar.title("SmartExam Creator")
        
        app_mode_options = ["Upload PDF & Generate Questions", "Take the Quiz", "Download as PDF"]
        st.session_state.app_mode = st.sidebar.selectbox(
            "Choose the app mode", 
            app_mode_options, 
            index=app_mode_options.index(st.session_state.app_mode), 
            key="app_mode_select"
        )
        
        if st.session_state.app_mode == "Upload PDF & Generate Questions":
            pdf_upload_app(user_id)
        elif st.session_state.app_mode == "Take the Quiz" and st.session_state.quiz_active:
            mc_quiz_app()
        elif st.session_state.app_mode == "Download as PDF":
            download_pdf_app()

def pdf_upload_app(user_id):
    st.title("Upload Your Lecture - Create Your Test Exam")
    st.subheader("Show Us the Slides and We do the Rest")

    content_text = ""

    if 'messages' not in st.session_state:
        st.session_state.messages = []
    
    uploaded_pdf = st.file_uploader("Upload a PDF document of up to 100 pages", type=["pdf"])
    if uploaded_pdf:
        reset_quiz_state()  # Resets quiz state when a new PDF is uploaded
        pdf_text = extract_text_from_pdf(uploaded_pdf)
        content_text += pdf_text
        st.session_state.last_upload_content = content_text  # Track the latest upload
        st.success("PDF content added to the session.")
    
    if len(content_text) > 3000:
        content_text = summarize_text(content_text)

    if content_text:
        st.info("Generating the exam from the uploaded content. It will take just a minute...")
        chunks = chunk_text(content_text)
        questions = []
        for chunk in chunks:
            response = generate_mc_questions(chunk)
            parsed_questions = parse_generated_questions(response)
            if parsed_questions:
                questions.extend(parsed_questions)
        if questions:
            st.session_state.generated_questions = questions
            st.session_state.answers = [None] * len(questions)
            st.session_state.feedback = [None] * len(questions)
            st.session_state.correct_answers = 0
            st.session_state.mc_test_generated = True
            st.session_state.quiz_active = True  # Indicate quiz is ready to be taken
            increment_mc_upload_count(user_id)
            st.success("The game has been successfully created! Switching to the quiz mode...")

            st.session_state.app_mode = "Take the Quiz"
            st.rerun()
        else:
            st.error("Failed to parse the generated questions. Please check the OpenAI response.")
    else:
        st.warning("Please upload a PDF to generate the interactive exam.")

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

    questions = st.session_state.generated_questions
    current_index = st.session_state.current_question_index

    if questions:
        if 'answers' not in st.session_state:
            st.session_state.answers = [None] * len(questions)
            st.session_state.feedback = [None] * len(questions)
            st.session_state.correct_answers = 0

        # Calculate progress and display the progress bar
        progress = (current_index + 1) / len(questions)
        st.progress(progress)
        
        quiz_data = questions[current_index]
        st.markdown(f"### Question {current_index + 1} of {len(questions)}: {quiz_data['question']}")

        # Display answer choices and buttons for navigation
        if st.session_state.answers[current_index] is None:
            user_choice = st.radio("Choose an answer:", quiz_data['choices'], key=f"user_choice_{current_index}")
            st.button("Submit", on_click=submit_answer, args=(current_index, quiz_data))
        else:
            selected_index = quiz_data['choices'].index(st.session_state.answers[current_index]) if st.session_state.answers[current_index] in quiz_data['choices'] else 0
            st.radio("Choose an answer:", quiz_data['choices'], key=f"user_choice_{current_index}", index=selected_index, disabled=True)

            if st.session_state.feedback[current_index][0] == "Correct":
                st.success(st.session_state.feedback[current_index][0])
            else:
                st.error(f"{st.session_state.feedback[current_index][0]} - Correct answer: {st.session_state.feedback[current_index][2]}")
            st.markdown(f"Explanation: {st.session_state.feedback[current_index][1]}")

        # Check if this is the last question and if the answer has been submitted
        if current_index + 1 == len(questions) and st.session_state.answers[current_index] is not None:
            # Show loading spinner and then the score screen
            with st.spinner("Calculating your score..."):
                time.sleep(2)  # Simulate processing time

            # Score display screen with trophy and styled message
            score = st.session_state.correct_answers
            total_questions = len(questions)
            st.markdown(
                f"""
                <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100vh;">
                    <h1 style="font-size: 3em; color: gold;">🏆</h1>
                    <h1>Your Score: {score}/{total_questions}</h1>
                    <p style="font-size: 1.5em; color: #4CAF50;">Well done! You’ve completed the quiz.</p>
                </div>
                """, 
                unsafe_allow_html=True
            )

            st.session_state.quiz_active = False
        elif st.button("Next Question") and current_index + 1 < len(questions):
            # If not on the last question, proceed to the next one
            st.session_state.current_question_index += 1
            st.rerun()




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
            st.write("---")

        pdf_bytes = generate_pdf(questions)
        st.download_button(
            label="Download PDF",
            data=pdf_bytes,
            file_name="generated_exam.pdf",
            mime="application/pdf"
        )

if __name__ == '__main__':
    main()
