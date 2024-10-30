import streamlit as st
import networkx as nx
from pyvis.network import Network
import streamlit.components.v1 as components
import PyPDF2
import openai
import xml.etree.ElementTree as ET
import re
import dotenv
from st_supabase_connection import SupabaseConnection
from supabase import create_client, Client
from streamlit_supabase_auth import login_form, logout_button

# Configure Streamlit app settings
st.set_page_config(layout="wide")
dotenv.load_dotenv()

# Initialize API keys
openai.api_key = st.secrets["OPENAI_API_KEY"]
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

# Initialize Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def extract_text_from_pdf(pdf_file):
    """Extracts text from an uploaded PDF file."""
    pdf_reader = PyPDF2.PdfReader(pdf_file)
    text = ""
    for page in pdf_reader.pages:
        text += page.extract_text() or ""
    return text

def summarize_text(text):
    """Summarizes text using OpenAI's GPT-4."""
    system_message = """
    You are an expert summarizer. Provide a concise (Sentences + bullet points) and informative summary.
    Focus on main ideas and key points.
    Ensure that your summary is coherent, well-structured, and captures the essence of the original text.
    Aim for a summary that is approximately 20-25% of the length of the original text.
    """
    prompt = f"Here is the text for summarization: {text}"

    response = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_message},
            {"role": "user", "content": prompt}
        ],
        max_tokens=4960
    )
    return response.choices[0].message.content

def get_entities_and_relations(text):
    """Extracts entities and relationships from text in XML format using GPT-4."""
    system_message = """
    Extract main entities and their relationships in XML format.
    """
    prompt = f"Here is the text for analysis: {text}"

    response = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_message},
            {"role": "user", "content": prompt}
        ],
        max_tokens=4960
    )
    return response.choices[0].message.content

def clean_xml_response(xml_response):
    """Cleans up XML response format from OpenAI."""
    return re.sub(r"^```xml\s*|```$", "", xml_response.strip())

def generate_graph_from_xml(xml_response):
    """Generates a knowledge graph from cleaned XML data."""
    cleaned_xml_response = clean_xml_response(xml_response)
    try:
        root = ET.fromstring(cleaned_xml_response)
        entities = [entity.text for entity in root.find('entities').findall('entity')]
        relationships = [
            (relation.find('source').text, relation.find('target').text, relation.find('type').text)
            for relation in root.find('relations').findall('relation')
        ]
        
        # Initialize graph
        G = nx.Graph()
        for entity in entities:
            G.add_node(entity)
        for source, target, relation in relationships:
            G.add_edge(source, target, label=relation)
        
        return G
    except ET.ParseError as e:
        st.error(f"Failed to parse XML: {e}")
        return None

def fetch_subscription_tier(user_id):
    """Fetches the user's subscription tier and graph upload count."""
    response = supabase.table("user_data").select("subscription_tier", "graph_upload_count").eq("id", user_id).execute()
    if response.data and len(response.data) > 0:
        return response.data[0]["subscription_tier"], response.data[0]["graph_upload_count"]
    return None, None

def increment_graph_upload_count(user_id):
    """Increments the graph upload count for the user in Supabase."""
    supabase.rpc("increment_graph_upload_count", {"user_uuid": user_id}).execute()

def main():
    """Main function to run the app."""
    # Login form
    session = login_form(
        url=SUPABASE_URL,
        apiKey=SUPABASE_KEY,
        providers=["email", "apple", "facebook", "github", "google"],
    )

    if not session:
        st.stop()

    user_id = session['user']['id']
    subscription_tier, graph_upload_count = fetch_subscription_tier(user_id)

    # Sidebar setup
    with st.sidebar:
        st.write(f"Welcome {session['user']['email']}")
        logout_button()
        st.write(f"Subscription Tier: **{subscription_tier}**")
        st.write(f"Summaries & Knowledge Graphs created: **{graph_upload_count}**")

    # Check subscription and usage limits
    if subscription_tier == "FREE" and graph_upload_count >= 10:
        st.error("Monthly usage limit reached. Upgrade for unlimited access.")
        if st.button("Upgrade Now"):
            redirect_url = "https://smartexam.streamlit.app/Pricing"
            st.markdown(f"<meta http-equiv='refresh' content='0; url={redirect_url}'>", unsafe_allow_html=True)
        return

    # Main content area for PDF upload and processing
    st.title("🧠 Upload Lectures - Generate Your Knowledge Graph")
    uploaded_pdf = st.file_uploader("Choose a PDF file", type="pdf")

    if uploaded_pdf is not None:
        # Step 1: Extract text from PDF
        pdf_text = extract_text_from_pdf(uploaded_pdf)
        increment_graph_upload_count(user_id)

        # Step 2: Summarize the text
        st.subheader("Summarizing PDF content...")
        summary = summarize_text(pdf_text)
        st.write(summary)

        # Step 3: Generate knowledge graph
        st.subheader("Generating Knowledge Graph...")
        xml_response = get_entities_and_relations(pdf_text)
        graph = generate_graph_from_xml(xml_response)

        if graph:
            # Visualize graph
            net = Network(height='750px', width='100%', bgcolor='#222222', font_color='white')
            net.from_nx(graph)
            net.save_graph('knowledge_graph.html')
            HtmlFile = open('knowledge_graph.html', 'r', encoding='utf-8')
            components.html(HtmlFile.read(), height=800)
            with open('knowledge_graph.html', 'rb') as file:
                st.download_button("Download Knowledge Graph", data=file, file_name="knowledge_graph.html", mime="text/html")
        else:
            st.error("Failed to generate the knowledge graph.")
    else:
        st.warning("Please upload a PDF file to generate a knowledge graph.")

if __name__ == "__main__":
    main()
