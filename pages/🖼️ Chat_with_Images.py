import streamlit as st
from openai import OpenAI
import dotenv
import os
from PIL import Image
import base64
from io import BytesIO
import random
import argon2
from st_supabase_connection import SupabaseConnection
from supabase import Client

# Page config should be the very first Streamlit command
st.set_page_config(
    page_title="Master Your Studies - Create Your Exam",
    page_icon="🧠",  
    layout="wide",
    initial_sidebar_state="expanded",
)

dotenv.load_dotenv()

openai_models = [
    "gpt-4o-mini", 
    "gpt-4-turbo", 
    "gpt-3.5-turbo-16k", 
]

# Supabase Login Functionality
def login_form(
    * ,
    title: str = "Authentication",
    user_tablename: str = "users",
    username_col: str = "username",
    password_col: str = "password",
    create_title: str = "Create new account :baby: ",
    login_title: str = "Login to existing account :prince: ",
    allow_guest: bool = False,  # Set to False to disable guest login
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
    """Creates a user login form in Streamlit apps with simpler password criteria and email validation.

    Connects to a Supabase DB using SUPABASE_URL and SUPABASE_KEY Streamlit secrets.
    Sets session_state["authenticated"] to True if the login is successful.
    Sets session_state["username"] to provided username or new or existing user.

    Returns:
        Supabase.client: The client instance for performing downstream supabase operations.
    """
    # Initialize the Supabase connection
    client = st.connection(name="supabase", type=SupabaseConnection)
    auth = argon2.PasswordHasher()

    # User Authentication
    if "authenticated" not in st.session_state:
        st.session_state["authenticated"] = False

    if "username" not in st.session_state:
        st.session_state["username"] = None

    # Display authentication form only if not authenticated
    if not st.session_state["authenticated"]:
        with st.expander(title, expanded=True):
            if allow_create:
                create_tab, login_tab = st.tabs(
                    [
                        create_title,
                        login_title,
                    ]
                )
            else:
                login_tab = st.container()

            # Create new account
            if allow_create:
                with create_tab:
                    with st.form(key="create"):
                        username = st.text_input(
                            label=create_username_label,
                            placeholder=create_username_placeholder,
                            help=create_username_help,
                        )

                        password = st.text_input(
                            label=create_password_label,
                            placeholder=create_password_placeholder,
                            help=create_password_help,
                            type="password",
                        )
                        hashed_password = auth.hash(password)
                        if st.form_submit_button(label=create_submit_label, type="primary"):
                            if "@" not in username:
                                st.error(email_constraint_fail_message)
                                st.stop()

                            try:
                                client.table(user_tablename).insert(
                                    {username_col: username, password_col: hashed_password}
                                ).execute()
                            except Exception as e:
                                st.error(e.message)
                            else:
                                st.session_state["authenticated"] = True
                                st.session_state["username"] = username
                                st.success(create_success_message)
                                st.rerun()

            # Login to existing account
            with login_tab:
                with st.form(key="login"):
                    username = st.text_input(
                        label=login_username_label,
                        placeholder=login_username_placeholder,
                        help=login_username_help,
                    )

                    password = st.text_input(
                        label=login_password_label,
                        placeholder=login_password_placeholder,
                        help=login_password_help,
                        type="password",
                    )

                    if st.form_submit_button(label=login_submit_label, type="primary"):
                        response = (
                            client.table(user_tablename)
                            .select(f"{username_col}, {password_col}")
                            .eq(username_col, username)
                            .execute()
                        )

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

# Function to query and stream the response from the LLM
def stream_llm_response(model_params, model_type="openai", api_key=None):
    response_message = ""
    if model_type == "openai":
        client = OpenAI(api_key=api_key)
        for chunk in client.chat.completions.create(
            model=model_params["model"] if "model" in model_params else "gpt-4o",
            messages=st.session_state.messages,
            temperature=model_params["temperature"] if "temperature" in model_params else 0.3,
            max_tokens=4096,
            stream=True,
        ):
            chunk_text = chunk.choices[0].delta.content or ""
            response_message += chunk_text
            yield chunk_text

    st.session_state.messages.append({
        "role": "assistant", 
        "content": [
            {
                "type": "text",
                "text": response_message,
            }
        ]})

# Function to convert file to base64
def get_image_base64(image_raw):
    buffered = BytesIO()
    image_raw.save(buffered, format=image_raw.format)
    img_byte = buffered.getvalue()
    return base64.b64encode(img_byte).decode('utf-8')

def main():
    # Authentication check
    client = login_form()

    if st.session_state["authenticated"]:
        # --- Header ---
        st.title("📝 Chat with your Handwritten Notes & Pictures")

        # --- Main Content ---
        # Checking if the user has introduced the OpenAI API Key, if not, a warning is displayed
        openai_api_key = os.getenv("OPENAI_API_KEY")
        if not openai_api_key:
            st.warning("Please set your OpenAI API Key to continue...")
            return

        client = OpenAI(api_key=openai_api_key)

        if "messages" not in st.session_state:
            st.session_state.messages = []

        # Displaying the previous messages if there are any
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                # Ensure content is a list and contains dictionaries with the expected structure
                if isinstance(message["content"], list):
                    for content in message["content"]:
                        # Check if the content is a dictionary and contains the 'type' key
                        if isinstance(content, dict) and "type" in content:
                            if content["type"] == "text":
                                st.write(content["text"])
                            elif content["type"] == "image_url":      
                                st.image(content["image_url"]["url"])
                            elif content["type"] == "video_file":
                                st.video(content["video_file"])
                            elif content["type"] == "audio_file":
                                st.audio(content["audio_file"])
                        else:
                            st.error("Unexpected content format encountered.")
                else:
                    st.error("Message content is not in the expected format.")

        # Model parameters (fixed)
        model_params = {
            "model": "gpt-4o-mini",
            "temperature": 0.7,
        }

        # --- Image Upload ---
        st.write(f"### **🖼️ Add an image:**")

        def add_image_to_messages():
            if st.session_state.uploaded_img or ("camera_img" in st.session_state and st.session_state.camera_img):
                raw_img = Image.open(st.session_state.uploaded_img or st.session_state.camera_img)
                img = get_image_base64(raw_img)
                st.session_state.messages.append({
                    "role": "user", 
                    "content": [{
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{img}"}
                    }]
                })

        cols_img = st.columns(2)

        with cols_img[0]:
            st.file_uploader(
                "Upload an image:", 
                type=["png", "jpg", "jpeg"], 
                accept_multiple_files=False,
                key="uploaded_img",
                on_change=add_image_to_messages,
            )

        with cols_img[1]:                    
            activate_camera = st.checkbox("Activate camera")
            if activate_camera:
                st.camera_input(
                    "Take a picture", 
                    key="camera_img",
                    on_change=add_image_to_messages,
                )

        # --- Chat input ---
        if prompt := st.chat_input("Hi! Ask me anything..."):
            st.session_state.messages.append({
                "role": "user", 
                "content": [{
                    "type": "text",
                    "text": prompt,
                }]
            })

            # Display the new messages
            with st.chat_message("user"):
                st.markdown(prompt)

            with st.chat_message("assistant"):
                st.write_stream(
                    stream_llm_response(
                        model_params=model_params, 
                        model_type="openai",
                        api_key=openai_api_key
                    )
                )

        # --- Sidebar --- 
        with st.sidebar:
            st.write("### 🛠️ Options")
            # Reset conversation button
            def reset_conversation():
                if "messages" in st.session_state and len(st.session_state.messages) > 0:
                    st.session_state.pop("messages", None)

            st.button(
                "🗑️ Reset conversation", 
                on_click=reset_conversation,
            )


if __name__=="__main__":
    main()
