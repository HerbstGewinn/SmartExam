import streamlit as st
from openai import OpenAI
import dotenv
import os
import PyPDF2
from streamlit_supabase_auth import login_form, logout_button
from supabase import create_client, Client

# Page config should be the very first Streamlit command
st.set_page_config(
    page_title="Master Your Studies - Create Your Exam",
    page_icon="📝",
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

# Load environment variables
dotenv.load_dotenv()

# Load API keys securely from secrets
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# OpenAI Models
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

# Function to fetch the subscription tier from Supabase
def fetch_subscription_tier(user_id):
    response = supabase.table("user_data").select("subscription_tier", "pdf_upload_count").eq("id", user_id).execute()
    if response.data and len(response.data) > 0:
        return response.data[0]["subscription_tier"], response.data[0]["pdf_upload_count"]
    else:
        return None, None

# Function to increment pdf_upload_count in the database
def increment_pdf_upload_count(user_id):
    response = supabase.rpc("increment_pdf_upload_count", {"user_uuid": user_id}).execute()
    st.write(f"PDF Upload Count Increment Response: {response}")  # Debugging response

# Main app function
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
    subscription_tier, pdf_upload_count = fetch_subscription_tier(user_id)

    st.sidebar.write(f"Subscription Tier: **{subscription_tier}**")
    st.sidebar.write(f"PDFs Uploaded: **{pdf_upload_count}**")

    # --- Check if the user has reached the usage limit ---
    # Check if the pdf_upload_count is greater than or equal to 3 (adjusted condition)
    if subscription_tier == "FREE":
        if pdf_upload_count and pdf_upload_count >= 100000:
            st.error("You have reached your free usage limit. Upgrade to a higher version for an advanced study progress.")
        
            # Display the "Upgrade Now" button only when the limit is exceeded
            if st.button("Upgrade Now"):
                # Meta-refresh-based redirect
                redirect_url = "https://smartexam.streamlit.app/Pricing"
                st.markdown(f"""
                    <meta http-equiv="refresh" content="0; url={redirect_url}">
                """, unsafe_allow_html=True)

            return  # Stop further interaction if the limit is reached

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

            # Increment the user's PDF upload count in the database
            increment_pdf_upload_count(user_id)

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


#def get_previous_messages():
    # Retrieve the conversation history from the session state
 #   messages = st.session_state.messages.copy()  # Copy the conversation history

    # Return the messages list for inspection
  #  return messages


#messages_list = get_previous_messages()
#
#MAYBE THINK ABOUT THIS "MESSAGES" LIST WHEN TRYING TO EVALUATE WHERE THE RANDOM SYSTEMS BIOLOGY OUTPUT SOMETIMES COMES FROM !!!
# 
# print(messages_list)
