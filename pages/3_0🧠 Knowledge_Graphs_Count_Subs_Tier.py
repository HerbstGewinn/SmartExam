import streamlit as st
import networkx as nx
from pyvis.network import Network
import streamlit.components.v1 as components
import PyPDF2
import openai
import xml.etree.ElementTree as ET
import re  # We will use this to clean up the response
import argon2
import dotenv
from st_supabase_connection import SupabaseConnection
from supabase import Client
from streamlit_supabase_auth import login_form, logout_button
from supabase import create_client, Client

# OpenAI GPT-4 Integration (Insert your OpenAI API Key via Streamlit Secrets)
openai.api_key = st.secrets["OPENAI_API_KEY"]

# Function to extract text from PDF
def extract_text_from_pdf(pdf_file):
    pdf_reader = PyPDF2.PdfReader(pdf_file)
    text = ""
    for page in pdf_reader.pages:
        text += page.extract_text()
    return text

# Function to interact with GPT-4 to summarize text (Note: This is synchronous)
def summarize_text(api_key, text):
    system_message = """
    You are an expert summarizer. Your task is to provide a concise (Sentences + bullet points) and informative summary of the given text.
    Focus on the main ideas, key points, and essential information.
    Ensure that your summary is coherent, well-structured, and captures the essence of the original text.
    Aim for a summary that is approximately 20-25% of the length of the original text.
    """
    
    prompt = f"Here is the text for summarization: {text}"

    response = openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_message},
            {"role": "user", "content": prompt}
        ],
        max_tokens=4960  # Adjust based on expected summary length
    )
    
    return response.choices[0].message.content

# Function to extract entities and relationships using GPT-4 (Note: This is synchronous)
def get_entities_and_relations(api_key, text):
    system_message = """
    You are an expert in natural language processing and knowledge extraction.
    Given a text, identify the main entities and their relationships.
    Return your response in the following XML format:
    <output>
    <entities>
    <entity>Entity1</entity>
    <entity>Entity2</entity>
    ...
    </entities>
    <relations>
    <relation>
    <source>SourceEntity</source>
    <target>TargetEntity</target>
    <type>RelationType</type>
    </relation>
    ...
    </relations>
    </output>
    Ensure that the XML is well-formed and does not contain any syntax errors. You must absolutely at all times 
    return your response in the format presented regardless of how large the document is. If the document is
    long and overwhelming then still do your best in returning as many entities as possible, without making a mistake.
    Do not include the relations about authors and their books in the knowledge graph.
    """
    
    prompt = f"Here is the text for analysis: {text}\nExtract entities and relationships from this text in the format presented."

    response = openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_message},
            {"role": "user", "content": prompt}
        ],
        max_tokens=4960
    )
    
    return response.choices[0].message.content

# Clean the XML response from GPT-4 by removing any markdown formatting
def clean_xml_response(xml_response):
    # Remove the ```xml and ``` that may wrap the response
    cleaned_response = re.sub(r"^```xml\s*|```$", "", xml_response.strip())
    return cleaned_response

# Function to parse XML response and create a knowledge graph
def generate_graph_from_xml(xml_response):
    # Clean the XML response
    cleaned_xml_response = clean_xml_response(xml_response)
    
    try:
        # Parse the cleaned XML response
        root = ET.fromstring(cleaned_xml_response)
        entities = [entity.text for entity in root.find('entities').findall('entity')]
        relationships = [(relation.find('source').text, relation.find('target').text, relation.find('type').text) 
                         for relation in root.find('relations').findall('relation')]
        
        # Initialize a graph
        G = nx.Graph()

        # Add entities as nodes
        for entity in entities:
            G.add_node(entity)

        # Add relationships as edges
        for source, target, relation in relationships:
            G.add_edge(source, target, label=relation)

        return G
    except ET.ParseError as e:
        st.error(f"Failed to parse XML: {e}")
        return None
    

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
        st.write(f"Graph Upload Count Increment Response: {response}")  # Debugging response

# Main app function
    #st.info(
    #"Thank you to everyone for the ongoing support. We have changed our login functionality, so everyone with a previous account can simply select **Don't have an account ? Sign up** for once and confirm their old credentials "
    #"- or create a new account with a preferred login method."
    #)
    # Initialize the login form with Supabase Auth
    session = login_form(
        url=SUPABASE_URL,
        apiKey=SUPABASE_KEY,
        providers=["email","apple", "facebook", "github", "google"],
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
    st.sidebar.write(f"Summaries & Knowledge Graphs created: **{graph_upload_count}**")

    # --- Check if the user has reached the usage limit ---
    # Check if the pdf_upload_count is greater than or equal to 10 (adjusted condition)
    if subscription_tier == "FREE":
        if graph_upload_count and graph_upload_count >= 10:
            st.error("Your usage limit for this month has finished. Upgrade to a higher version for an advanced study progress.")
    
            # Display the "Upgrade Now" button only when the limit is exceeded
            if st.button("Upgrade Now"):
                # Meta-refresh-based redirect
                redirect_url = "https://smartexam.streamlit.app/Pricing"
                st.markdown(f"""
                    <meta http-equiv="refresh" content="0; url={redirect_url}">
                """, unsafe_allow_html=True)

        return  # Stop further interaction if the limit is reached
    
    st.title("🧠 Upload Lectures- Generate your Knowledge Graph")
    st.write("Upload a PDF, get a summary, and generate a knowledge graph.")

    # File uploader to upload a PDF
    uploaded_pdf = st.file_uploader("Choose a PDF file", type="pdf")

    # Check if a PDF file is uploaded
    if uploaded_pdf is not None:
        # Step 1: Extract text from the uploaded PDF
        pdf_text = extract_text_from_pdf(uploaded_pdf)
        increment_graph_upload_count(user_id)
        
        
        # Step 2: Summarize the text using GPT-4
        st.subheader("Summarizing PDF content...")
        
        # Call the summarize function (synchronous)
        summary = summarize_text(openai.api_key, pdf_text)
        
        # Display the summary
        
        st.write(summary)

        # Step 3: Extract entities and relationships using GPT-4
        st.subheader("Generating Knowledge Graph...")
        
        # Call the entity and relation extraction function (synchronous)
        xml_response = get_entities_and_relations(openai.api_key, pdf_text)
        
        # Step 4: Generate a knowledge graph from the GPT-4 response
        graph = generate_graph_from_xml(xml_response)
        
        if graph:
            # Step 5: Visualize the graph using PyVis
            net = Network(height='750px', width='100%', bgcolor='#222222', font_color='white')
            net.from_nx(graph)  # Convert the NetworkX graph into a PyVis graph
            
            # Save and display the graph
            net.save_graph('knowledge_graph.html')
            HtmlFile = open('knowledge_graph.html', 'r', encoding='utf-8')
            components.html(HtmlFile.read(), height=800)
            
            # Step 6: Provide a download button for the graph
            with open('knowledge_graph.html', 'rb') as file:
                st.download_button(label="Download Knowledge Graph", data=file, file_name="knowledge_graph.html", mime="text/html")
        else:
            st.error("Failed to generate the knowledge graph.")

    else:
        st.warning("Please upload a PDF file to generate a knowledge graph.")

if __name__ == "__main__":
    main()