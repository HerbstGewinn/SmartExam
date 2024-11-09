import streamlit as st
import requests
from streamlit_supabase_auth import login_form, logout_button
import streamlit.components.v1 as components
import dotenv

st.set_page_config(layout="wide")

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

# Load API keys securely from secrets
supabase_api_key = st.secrets["SUPABASE_KEY"]
supabase_url = st.secrets["SUPABASE_URL"]
webhook_url = st.secrets["SUPABASE_FUNCTION_URL"]  # replace with actual webhook URL
stripe_public_key = st.secrets["stripe_api_key"]

# Initialize the login form with Supabase
session = login_form(
    url=supabase_url,
    apiKey=supabase_api_key,
    providers=["google"],
)

# If the user is not logged in, stop the app
if not session:
    st.stop()

# Sidebar with logout button and user welcome message
with st.sidebar:
    st.write(f"Welcome {session['user']['email']}")
    logout_button()
    
# Define your plan IDs (Price IDs from Stripe)
# PREMIUM_PLAN_ID = "price_1Q9QZ6RwYqmuXQJ5wOqzdHwq" #This is the old test ID # replace with your actual Premium Price ID
PREMIUM_PLAN_ID = "price_1QJ1u8RwYqmuXQJ5kEU3DFqa"  #Live mode price ID --> NEW ONE TIME PAYMENT ! 
#PRO_PLAN_ID = "price_1QEWiVRwYqmuXQJ5VD1E53cQ" #This is the old Test mode ID # replace with your actual Pro Price ID; CHANGES TO 2-YEAR PLAN DEFAULT
PRO_PLAN_ID = "price_1QJ1v2RwYqmuXQJ5r2ORZQum"  #Live Mode price ID one time payment

# Handle Subscription Checkout
def handle_checkout(plan_id):
    try:
        # Send request to webhook to create the checkout session
        headers = {
            "Authorization": f"Bearer {session['access_token']}",  # Token of the logged-in user
            "Content-Type": "application/json",
        }
        response = requests.post(
            webhook_url,
            json={"planId": plan_id},
            headers=headers,
        )

        # If the webhook call was successful, retrieve the session ID
        if response.status_code == 200:
            session_id = response.json()["url"]     #Here it is basically now the session url and not id, but naming stays

            # Create the redirect URL to Stripe checkout
            checkout_url = f"{session_id}"

            # Display the clickable link for manual redirection --> THIS ALSO WORKS IN PROD
            st.markdown(f'[Click here to proceed to payment]({checkout_url})')

            # Optionally: Automatically redirect to Stripe checkout after some time --> THIS DOES NOT WORK IN PROD; BUT IN DEV
            #st.markdown(f"""
            #<meta http-equiv="refresh" content="1; url={checkout_url}">
            #""", unsafe_allow_html=True)

        else:
            st.error("Error creating checkout session")

    except Exception as e:
        st.error(f"Error creating checkout session: {e}")


# Pricing Section using Bootstrap with Buttons Embedded Directly
# Premium and Pro Plan HTML
premium_plan_html = """
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0-alpha1/dist/css/bootstrap.min.css" rel="stylesheet" integrity="sha384-mQ93ldbnHPGozG5Fw5t6g6lrF0xq7r3njzLCw9lZlFHIcwimS+eK+ww5b98L2I7j" crossorigin="anonymous">
<style>
    :root {
        color-scheme: light dark;
        --card-bg-color: #1a1a1a; /* Dark card background */
        --text-color: #fff; /* White text color */
    }

    .card {
        border: 1px solid #ddd;
        border-radius: 10px;
        padding: 20px;
        background-color: var(--card-bg-color); /* Dark card background */
        box-shadow: 0 4px 8px 0 rgba(0,0,0,0.2);
        transition: 0.3s;
        color: var(--text-color);
        text-align: center; /* Center the text */
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
    }
    .card:hover {
        box-shadow: 0 8px 16px 0 rgba(0,0,0,0.3);
    }
    .price-title {
        font-size: 24px;
        font-weight: bold;
        color: var(--text-color);
        margin-bottom: 10px;
        text-align: center;
        width: 100%;  /* Ensure the title spans the entire width */
        display: block; /* Make the title behave like a block element */
        margin-left: 5px;
    }


    .price {
        font-size: 24px;
        font-weight: bold;
        color: var(--text-color);
        margin-right: 5px;
        margin-bottom: 10px; /* Add space between title and price */
    }
    .features {
        display: flex;
        flex-direction: column;
        align-items: center;  /* This ensures the bullet points are horizontally centered */
        justify-content: center;
        list-style-type: none; /* Removing the default bullet styling */
        padding: 0;            /* Remove any default padding */
        margin: 0;             /* Remove any default margin */
        text-align: center;    /* Ensure the text inside each list item is centered */
        width: 100%;           /* Ensure that the list spans the full width of the card */
    }
    .features li {
        text-align: center;    /* Center the text within each bullet point */
        margin: 5px 0;         /* Add vertical margin to space out each bullet point */
        width: 100%;           /* Ensure each list item spans the full width */
        padding: 0;            /* Ensure no extra padding */
        max-width: 90%;        /* Restrict the width of the list items to prevent overflow */
    }
</style>

<div class="card">
    <h2 class="price-title">Premium Plan</h2>
    <p class="price">$24.99</p>
    <ul class="features">
        <li>One-Time Payment. No Subscription !</li>
        <li>Unlimited Multiple Choice Exams</li>
        <li>Unlimited Chats with PDF</li>
        <li>Unlimited Chats with handwritten notes/pictures</li>
        <li>Unlimited Summaries</li>
        <li>Early Access to new Features</li>
    </ul>
</div>
"""

pro_plan_html = """
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0-alpha1/dist/css/bootstrap.min.css" rel="stylesheet" integrity="sha384-mQ93ldbnHPGozG5Fw5t6g6lrF0xq7r3njzLCw9lZlFHIcwimS+eK+ww5b98L2I7j" crossorigin="anonymous">
<style>
    :root {
        color-scheme: light dark;
        --card-bg-color: #1a1a1a;
        --text-color: #fff;
        --highlight-color: #007bff; /* Blue for highlighting */
    }

    .card {
        border: 1px solid #ddd;
        border-radius: 10px;
        padding: 20px;
        background-color: var(--card-bg-color);
        box-shadow: 0 4px 8px 0 rgba(0,0,0,0.2);
        transition: 0.3s;
        color: var(--text-color);
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
        text-align: center; /* Center the text */
    }

    .highlighted-card {
        border: 2px solid var(--highlight-color); /* Highlight border */
        box-shadow: 0 8px 16px 0 rgba(0,123,255,0.5); /* Blue shadow */
    }

    .card:hover {
        box-shadow: 0 8px 16px 0 rgba(0,0,0,0.3);
    }

    .price-title {
            font-size: 24px;
            font-weight: bold;
            color: var(--text-color);
            margin-bottom: 10px;
            text-align: center;
            width: 100%;  /* Ensure the title spans the entire width */
            display: block; /* Make the title behave like a block element */
            margin-left: 5px;
        }

    .price {
        font-size: 36px;
        font-weight: bold;
        color: var(--text-color);
        margin-bottom: 15px;
    }

    .features {
        display: flex;
        flex-direction: column;
        align-items: center;  /* This ensures the bullet points are horizontally centered */
        justify-content: center;
        list-style-type: none; /* Removing the default bullet styling */
        padding: 0;            /* Remove any default padding */
        margin: 0;             /* Remove any default margin */
        text-align: center;    /* Ensure the text inside each list item is centered */
        width: 100%;           /* Ensure that the list spans the full width of the card */
    }
    .features li {
        text-align: center;    /* Center the text within each bullet point */
        margin: 5px 0;         /* Add vertical margin to space out each bullet point */
        width: 100%;           /* Ensure each list item spans the full width */
        padding: 0;            /* Ensure no extra padding */
        max-width: 90%;        /* Restrict the width of the list items to prevent overflow */
    }


    /* Ensure all child elements are aligned properly */
    .card > * {
        margin: 0 auto; /* Force each child to center horizontally */
    }
</style>

<div class="card highlighted-card">
    <h2 class="price-title">Pro - Early Bird Deal</h2>
    <p class="price">$29.99</p>
    <ul class="features">
        <li>One-Time Payment. Access for Forever</li>
        <li>Unlimited Multiple Choice Exams</li>
        <li>Free Access to Notion x Smartexam Spaced Repetition Template</li>
        <li>Unlimited Chats with PDF</li>
        <li>Unlimited Chats with handwritten notes/pictures</li>
        <li>Unlimited Summaries</li>
        <li>Early Access to new Features</li>
    </ul>
</div>
"""

free_plan_html = """
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0-alpha1/dist/css/bootstrap.min.css" rel="stylesheet" integrity="sha384-mQ93ldbnHPGozG5Fw5t6g6lrF0xq7r3njzLCw9lZlFHIcwimS+eK+ww5b98L2I7j" crossorigin="anonymous">
<style>
    :root {
        color-scheme: light dark;
        --card-bg-color: #1a1a1a;
        --text-color: #fff;
    }

    .card {
        border: 1px solid #ddd;
        border-radius: 10px;
        padding: 20px;
        background-color: var(--card-bg-color);
        box-shadow: 0 4px 8px 0 rgba(0,0,0,0.2);
        transition: 0.3s;
        color: var(--text-color);
        text-align: center;
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
    }
    .card:hover {
        box-shadow: 0 8px 16px 0 rgba(0,0,0,0.3);
    }
    .price-title {
            font-size: 24px;
            font-weight: bold;
            color: var(--text-color);
            margin-bottom: 10px;
            text-align: center;
            width: 100%;  /* Ensure the title spans the entire width */
            display: block; /* Make the title behave like a block element */
            margin-left: 5px;
        }
    .price {
        font-size: 24px;
        font-weight: bold;
        color: var(--text-color);
        margin-right: 5px;
        margin-bottom: 10px; /* Add space between title and price */
    }
    .features {
        display: flex;
        flex-direction: column;
        align-items: center;  /* This ensures the bullet points are horizontally centered */
        justify-content: center;
        list-style-type: none; /* Removing the default bullet styling */
        padding: 0;            /* Remove any default padding */
        margin: 0;             /* Remove any default margin */
        text-align: center;    /* Ensure the text inside each list item is centered */
        width: 100%;           /* Ensure that the list spans the full width of the card */
    }
    .features li {
        text-align: center;    /* Center the text within each bullet point */
        margin: 5px 0;         /* Add vertical margin to space out each bullet point */
        width: 100%;           /* Ensure each list item spans the full width */
        padding: 0;            /* Ensure no extra padding */
        max-width: 90%;        /* Restrict the width of the list items to prevent overflow */
    }
</style>

<div class="card">
    <h2 class="price-title">Free Plan</h2>
    <p class="price">$0.00 / month</p>
    <ul class="features">
        <li>1 Multiple Choice Exam</li>
        <li>5 Chats with PDF</li>
        <li>5 Chats with handwritten notes/pictures</li>
        <li>5 Summaries</li>
    </ul>
</div>
"""

# Display the pricing section using st.html for all plans in the respective columns
col1, col2, col3 = st.columns([1, 1, 1], gap="large")

with col1:
    st.markdown(
        free_plan_html, unsafe_allow_html=True)
    if st.button("Stick to the Free Version", key="free-btn", use_container_width=True):
        st.success("Stick to the free version for now.Upgrade any time you want")
        st.balloons()
    

with col2:
    st.markdown(
        premium_plan_html, unsafe_allow_html=True)
    if st.button("SUBSCRIBE PREMIUM", key="premium-btn", use_container_width=True):
        handle_checkout(PREMIUM_PLAN_ID)
        st.success("You have selected the Premium plan! Click on the Payment Link to finalize your purchase !")
        st.balloons()
    
    
with col3:
    st.markdown(
        pro_plan_html, unsafe_allow_html=True)
    if st.button("BUY 2 YEAR PASS", key="pro-btn", use_container_width=True):
        handle_checkout(PRO_PLAN_ID)
        st.success("You have selected the 2 year Pass! Click on the Payment Link to finalize your purchase !")
        st.balloons()

