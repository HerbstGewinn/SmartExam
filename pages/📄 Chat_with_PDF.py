import streamlit as st
from openai import OpenAI
import dotenv
import os
from io import BytesIO
import PyPDF2
import argon2
from st_supabase_connection import SupabaseConnection
from supabase import Client

# Page config should be the very first Streamlit command
st.set_page_config(
    page_title="Master Your Studies - Create Your Exam",
    page_icon="📝",
    layout="wide",
    initial_sidebar_state="expanded",
)

dotenv.load_dotenv()

openai_models = [
    "gpt-4o-mini", 
    "gpt-4-turbo", 
    "gpt-3.5-turbo-16k", 
]

# Function to query and stream the response from the LLM
def stream_llm_response(model_params, api_key=None):
    response_message = ""
    client = OpenAI(api_key=api_key)
    messages = st.session_state.messages.copy()  # Copy the conversation history

    # Prepare the messages for the API call
    api_messages = []
    for message in messages:
        if message["role"] == "system":
            api_messages.append({"role": "system", "content": message["content"]})
        else:
            # Combine all content pieces into a single string
            text_content = ""
            for content in message["content"]:
                if content["type"] == "text":
                    text_content += content["text"] + "\n"
            api_messages.append({"role": message["role"], "content": text_content})

    # Streaming response from the OpenAI API
    for chunk in client.chat.completions.create(
        model=model_params["model"],
        messages=api_messages,
        temperature=model_params["temperature"],
        max_tokens=1500,
        stream=True,
    ):
        # Properly access chunk content from the delta object
        chunk_text = chunk.choices[0].delta.content or ""
        response_message += chunk_text
        yield chunk_text

    # Append the full response to the session state messages
    st.session_state.messages.append({
        "role": "assistant", 
        "content": [
            {
                "type": "text",
                "text": response_message,
            }
        ]})

# Function to extract text from PDF
def extract_text_from_pdf(pdf_file):
    pdf_reader = PyPDF2.PdfReader(pdf_file)
    text = ""
    for page in pdf_reader.pages:
        page_text = page.extract_text()
        if page_text:
            text += page_text + "\n"
    return text

# Function to display login/signup form using Supabase
def login_form(
    * ,
    title: str = "Authentication",
    user_tablename: str = "users",
    username_col: str = "username",
    password_col: str = "password",
    create_title: str = "Create new account :baby: ",
    login_title: str = "Login to existing account :prince: ",
    allow_guest: bool = False,  
    allow_create: bool = True,
    create_username_label: str = "Create an email username",
    create_username_placeholder: str = None,
    create_username_help: str = None,
    create_password_label: str = "Create a password",
    create_password_placeholder: str = None,
    create_password_help: str = "Password cannot be recovered if lost",
    create_submit_label: str = "Create account",
    create_success_message: str = "Account created and logged-in :tada:",
    login_username_label: str = "Enter your email username",
    login_username_placeholder: str = None,
    login_username_help: str = None,
    login_password_label: str = "Enter your password",
    login_password_placeholder: str = None,
    login_password_help: str = None,
    login_submit_label: str = "Login",
    login_success_message: str = "Login succeeded :tada:",
    login_error_message: str = "Wrong username/password :x: ",
    email_constraint_fail_message: str = "Please sign up with a valid email address (must contain @).",
) -> Client:
    """Creates a user login form in Streamlit apps with simpler password criteria and email validation."""

    client = st.connection(name="supabase", type=SupabaseConnection)
    auth = argon2.PasswordHasher()

    if "authenticated" not in st.session_state:
        st.session_state["authenticated"] = False

    if "username" not in st.session_state:
        st.session_state["username"] = None

    if not st.session_state["authenticated"]:
        with st.expander(title, expanded=True):
            if allow_create:
                create_tab, login_tab = st.tabs([create_title, login_title])
            else:
                login_tab = st.container()

            if allow_create:
                with create_tab:
                    with st.form(key="create"):
                        username = st.text_input(label=create_username_label, placeholder=create_username_placeholder, help=create_username_help)
                        password = st.text_input(label=create_password_label, placeholder=create_password_placeholder, help=create_password_help, type="password")
                        hashed_password = auth.hash(password)
                        if st.form_submit_button(label=create_submit_label, type="primary"):
                            if "@" not in username:
                                st.error(email_constraint_fail_message)
                                st.stop()

                            try:
                                client.table(user_tablename).insert({username_col: username, password_col: hashed_password}).execute()
                            except Exception as e:
                                st.error(e.message)
                            else:
                                st.session_state["authenticated"] = True
                                st.session_state["username"] = username
                                st.success(create_success_message)
                                st.rerun()

            with login_tab:
                with st.form(key="login"):
                    username = st.text_input(label=login_username_label, placeholder=login_username_placeholder, help=login_username_help)
                    password = st.text_input(label=login_password_label, placeholder=login_password_placeholder, help=login_password_help, type="password")

                    if st.form_submit_button(label=login_submit_label, type="primary"):
                        response = client.table(user_tablename).select(f"{username_col}, {password_col}").eq(username_col, username).execute()

                        if len(response.data) > 0:
                            db_password = response.data[0]["password"]
                            if auth.verify(db_password, password):
                                st.session_state["authenticated"] = True
                                st.session_state["username"] = username
                                st.success(login_success_message)
                                st.rerun()
                            else:
                                st.error(login_error_message)
                        else:
                            st.error(login_error_message)

    return client

# Main app function
def main():
    # Authentication check
    client = login_form()

    if st.session_state["authenticated"]:
        # --- Header ---
        st.title("📝Upload Your Study Material - Ask Unlimited Questions")

        # --- Initialize Session State ---
        if "messages" not in st.session_state:
            st.session_state.messages = []
        if "pdf_text" not in st.session_state:
            st.session_state.pdf_text = ""
        if "pdf_uploaded" not in st.session_state:
            st.session_state.pdf_uploaded = False

        # --- API Key Handling ---
        openai_api_key = os.getenv("OPENAI_API_KEY") 
        if not openai_api_key:
            openai_api_key = st.sidebar.text_input("Enter your OpenAI API Key", type="password")
            if not openai_api_key:
                st.warning("Please enter your OpenAI API Key to continue.")
                return

        # --- Upload Section ---
        st.divider()
        st.write("### Upload Your PDF Below")

        pdf_file = st.file_uploader("PDF:", type="pdf", label_visibility="collapsed")

        # Process PDF Upload
        if pdf_file and not st.session_state.pdf_uploaded:
            pdf_text = extract_text_from_pdf(pdf_file)
            if pdf_text:
                st.session_state.pdf_text = pdf_text
                st.session_state.pdf_uploaded = True
                st.session_state.messages.insert(0, {
                    "role": "system",
                    "content": f"You are provided with the following document content:\n\n{pdf_text}\n\nUse this information to answer any questions related to it."
                })
                st.success("PDF content has been processed and added to the conversation context.")

        # --- Display Conversation ---
        st.divider()
        st.write("### 💬 Conversation")

        for message in st.session_state.messages:
            if message["role"] == "system":
                continue  # Skip displaying system messages
            with st.chat_message(message["role"]):
                for content in message["content"]:
                    if content["type"] == "text":
                        st.write(content["text"])

        # --- Chat Input ---
        prompt = st.chat_input("Ask a question about your document or anything else...")
        if prompt:
            st.session_state.messages.append({
                "role": "user",
                "content": [{"type": "text", "text": prompt}]
            })
            with st.chat_message("user"):
                st.markdown(prompt)

            with st.chat_message("assistant"):
                st.write_stream(
                    stream_llm_response(
                        model_params={"model": openai_models[0], "temperature": 0.7},
                        api_key=openai_api_key
                    )
                )

        # --- Reset Conversation ---
        st.sidebar.write("### 🔄 Reset")
        if st.sidebar.button("Reset Conversation"):
            st.session_state.messages = []
            st.session_state.pdf_text = ""
            st.session_state.pdf_uploaded = False
            st.success("Conversation has been reset.")

if __name__ == "__main__":
    main()
