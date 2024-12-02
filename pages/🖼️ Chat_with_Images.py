import streamlit as st
from openai import OpenAI
import dotenv
import os
from PIL import Image
import base64
from io import BytesIO
import random
import argon2
from streamlit_supabase_auth import login_form, logout_button
from supabase import create_client, Client

# Page config should be the very first Streamlit command
st.set_page_config(
    page_title="Master Your Studies - Create Your Exam",
    page_icon="🧠",  
    layout="centered",
    initial_sidebar_state="expanded",
)

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

dotenv.load_dotenv()

# Load API keys securely from secrets
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

openai_models = [
    "gpt-4o-mini", 
    "gpt-4-turbo", 
    "gpt-3.5-turbo-16k", 
]

# Supabase Login Form removed


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

# Function to fetch the subscription tier from Supabase
def fetch_subscription_tier(user_id):
    response = supabase.table("user_data").select("subscription_tier", "img_upload_count").eq("id", user_id).execute()
    if response.data and len(response.data) > 0:
        return response.data[0]["subscription_tier"], response.data[0]["img_upload_count"]
    else:
        return None, None

# Function to increment pdf_upload_count in the database
def increment_img_upload_count(user_id):
    response = supabase.rpc("increment_img_upload_count", {"user_uuid": user_id}).execute()
    st.write(f"Img Upload Count Increment Response: {response}")  # Debugging response


def main():
# Initialize the login form with Supabase Auth

    #st.info(
    #"Thank you to everyone for the ongoing support. We have changed our login functionality, so everyone with a previous account can simply select **Don't have an account ? Sign up** for once and confirm their old credentials "
    #"- or create a new account with a preferred login method."
    #)

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
    subscription_tier, img_upload_count = fetch_subscription_tier(user_id)

    
    st.sidebar.write(f"Images Uploaded: **{img_upload_count}**")

    # --- Check if the user has reached the usage limit ---
    # Check if the pdf_upload_count is greater than or equal to 10 (adjusted condition)
    if subscription_tier == "FREE":
        if img_upload_count and img_upload_count >= 100000:
            st.error("You have reached your free usage limit. Upgrade to a higher version for an advanced study progress.")
        
            # Display the "Upgrade Now" button only when the limit is exceeded
            if st.button("Upgrade Now"):
                # Meta-refresh-based redirect --> Redirect to pricing section
                redirect_url = "https://smartexam.streamlit.app/Pricing"
                st.markdown(f"""
                    <meta http-equiv="refresh" content="0; url={redirect_url}">
                """, unsafe_allow_html=True)
            return  # Stop further interaction if the limit is reached
        
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
            increment_img_upload_count(user_id)
            

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
