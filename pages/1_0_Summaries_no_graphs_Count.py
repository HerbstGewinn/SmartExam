import streamlit as st
import PyPDF2
import openai
import dotenv
from st_supabase_connection import SupabaseConnection
from supabase import Client
from streamlit_supabase_auth import login_form, logout_button
from supabase import create_client

st.set_page_config(
    page_title="Master Your Studies - Create Your Summary",
    page_icon = "🧠",
    layout="centered",
    initial_sidebar_state="expanded",
)

# OpenAI GPT-4 Integration (Insert your OpenAI API Key via Streamlit Secrets)
openai.api_key = st.secrets["OPENAI_API_KEY"]

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


# Function to extract text from PDF
def extract_text_from_pdf(pdf_file):
    pdf_reader = PyPDF2.PdfReader(pdf_file)
    text = ""
    for page in pdf_reader.pages:
        text += page.extract_text()
    return text

# Function to interact with GPT-4 to summarize text
def summarize_text(api_key, text):
    system_message = """
    You are an expert summarizer. Your task is to provide a concise (Sentences + bullet points) and informative summary of the given text.
    Focus on the main ideas, key points, and essential information.
    Ensure that your summary is coherent, well-structured, and captures the essence of the original text.
    Aim for a summary that is approximately 20-25% of the length of the original text.
    """
    
    prompt = f"Here is the text for summarization: {text}"

    response = openai.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": system_message},
            {"role": "user", "content": prompt}
        ],
        max_tokens=4960
    )
    
    return response.choices[0].message.content

# Main app function
def main():
    # Load environment variables
    dotenv.load_dotenv()

    # Load API keys securely from secrets
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

    # Function to fetch the subscription tier from Supabase
    def fetch_subscription_tier(user_id):
        response = supabase.table("user_data").select("subscription_tier", "graph_upload_count").eq("id", user_id).execute()
        if response.data and len(response.data) > 0:
            return response.data[0]["subscription_tier"], response.data[0]["graph_upload_count"]
        else:
            return None, None

    # Function to increment pdf_upload_count in the database
    def increment_graph_upload_count(user_id):
        response = supabase.rpc("increment_graph_upload_count", {"user_uuid": user_id}).execute()
        st.write(f"Graph Upload Count Increment Response: {response}")

    # Initialize the login form with Supabase Auth
    session = login_form(
        url=SUPABASE_URL,
        apiKey=SUPABASE_KEY,
        providers=["email", "github", "google"],
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
    subscription_tier, graph_upload_count = fetch_subscription_tier(user_id)

    st.sidebar.write(f"Subscription Tier: **{subscription_tier}**")
    st.sidebar.write(f"Summaries Created: **{graph_upload_count}**")

    # --- Check if the user has reached the usage limit ---
    if subscription_tier == "FREE":
        if graph_upload_count and graph_upload_count >= 10:
            st.error("Your usage limit for this month has finished. Upgrade to a higher version for an advanced study progress.")
    
            # Display the "Upgrade Now" button only when the limit is exceeded
            if st.button("Upgrade Now"):
                redirect_url = "https://smartexam.streamlit.app/Pricing"
                st.markdown(f"""
                    <meta http-equiv="refresh" content="0; url={redirect_url}">
                """, unsafe_allow_html=True)

            return  # Stop further interaction if the limit is reached
    
    st.title("🧠 Upload Lectures - Generate Your Summary")
    st.write("Upload a PDF, and get a summary of the content.")

    # File uploader to upload a PDF
    uploaded_pdf = st.file_uploader("Choose a PDF file", type="pdf")

    # Check if a PDF file is uploaded
    if uploaded_pdf is not None:
        # Extract text from the uploaded PDF
        pdf_text = extract_text_from_pdf(uploaded_pdf)
        increment_graph_upload_count(user_id)
        
        # Summarize the text using GPT-4
        st.subheader("Summarizing PDF content...")
        summary = summarize_text(openai.api_key, pdf_text)
        
        # Display the summary
        st.write(summary)

    else:
        st.warning("Please upload a PDF file to generate a summary.")

if __name__ == "__main__":
    main()
