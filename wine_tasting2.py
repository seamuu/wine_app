import streamlit as st
import gspread
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import matplotlib.patches as mpatches  # For legend handles
from oauth2client.service_account import ServiceAccountCredentials
import google.generativeai as genai
import json

# --------------------------
#  1) LOAD SECRETS
# --------------------------
# We'll load Google Sheets credentials & Gemini API key from Streamlit Secrets.
# Make sure to add them in your Streamlit Cloud dashboard (see steps below).

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

# Load the ENTIRE JSON from your service account (as text) in Streamlit Secrets,
# then parse it with json.loads:
service_account_info = json.loads(st.secrets["GCP_SERVICE_ACCOUNT"])
credentials = ServiceAccountCredentials.from_json_keyfile_dict(service_account_info, scope)
gc = gspread.authorize(credentials)

# Gemini/Generative AI Setup
gemini_api_key = st.secrets["GEMINI_API_KEY"]
genai.configure(api_key=gemini_api_key)


# --------------------------
#  2) SET UP GOOGLE SHEET
# --------------------------
SHEET_NAME = "wine_ratings"  # Change if needed
sheet = gc.open(SHEET_NAME).sheet1

# Ensure headers exist
headers = sheet.row_values(1)
expected_headers = ["Name", "Wine", "Rating", "Category", "Taste"]
if headers != expected_headers:
    sheet.insert_row(expected_headers, 1)


# --------------------------
#  3) GENERATE SUMMARY FN
# --------------------------
def generate_summary(prompt):
    """Calls Google Gemini AI (old `genai` style) to generate a summary."""
    try:
        model = genai.GenerativeModel("gemini-pro")
        response = model.generate_content(prompt)
        if response.text:
            return response.text.strip()
        return "No response generated."
    except Exception as e:
        return f"Could not generate a summary due to an error: {e}"


# --------------------------
#  4) STREAMLIT MAIN APP
# --------------------------
st.set_page_config(
    page_title="Wine Tasting & Ratings",
    page_icon="🍷",
    layout="centered"
)

st.title("Wine Tasting & Ratings App 🍇")
st.markdown("Share your wine ratings and tasting notes, and explore what others are saying. Cheers! 🥂")

# Create two tabs
tab1, tab2 = st.tabs(["Rate a Wine & Add Tasting Notes", "View Ratings & Tasting Notes"])

# --------------------------
#           TAB 1
# --------------------------
with tab1:
    st.subheader("Rate a Wine & Add Tasting Notes 🍷")
    st.markdown("---")

    wine_options = ["Pinot Gris", "Gerwurtzraminer", "Riesling", "Dolcetto", "Cremant"]

    with st.form("input_form"):
        col1, col2 = st.columns([1, 1])
        with col1:
            name = st.text_input("Enter Your Name", key="user_name_input")
        with col2:
            wine = st.selectbox("Select a Wine", wine_options)

        col3, col4 = st.columns([1, 2])
        with col3:
            rating = st.slider("Rate the wine (1-10)", 1, 10, 5)
        with col4:
            tasting_notes = st.text_area(
                "Enter one taste per line (e.g., Apple, Citrus, Peach)",
                placeholder="Write each taste on a new line..."
            )

        submit_button = st.form_submit_button("Submit")

    if submit_button:
        if not name.strip():
            st.warning("Please enter a valid name before submitting.")
        else:
            # Save rating to Google Sheets
            sheet.append_row([name.strip(), wine, rating, "Rating", ""])

            # Save tasting notes
            if tasting_notes.strip():
                for taste in tasting_notes.splitlines():
                    if taste.strip():
                        sheet.append_row([name.strip(), wine, "", "Taste", taste.strip()])

            st.success(f"Thank you, {name.strip()}! Your inputs for {wine} have been recorded. 🍷")
            st.rerun()


# --------------------------
#           TAB 2
# --------------------------
with tab2:
    st.subheader("📊 Wine Ratings & Tasting Notes Data")

    if st.button("🔄 Refresh Data"):
        st.rerun()

    # Load your data from Google Sheets
    ratings_data = sheet.get_all_records()
    df = pd.DataFrame(ratings_data)

    if df.empty:
        st.write("No data available yet. Be the first to add your ratings!")
    else:
        # Convert rating to numeric, just in case
        df["Rating"] = pd.to_numeric(df["Rating"], errors="coerce")

        # Select user
        user_list = sorted(df["Name"].unique().tolist())
        user_options = ["All Users"] + user_list
        selected_user = st.selectbox("Select a user to highlight / compare:", options=user_options)

        # Select wine
        wine_options = ["All Wines"] + sorted(df["Wine"].unique().tolist())
        selected_wine = st.selectbox("Select a wine to view:", wine_options)

        category_filter = st.radio("Choose what to visualize:", ["Rating", "Taste"], key="category_filter")

        # ----------------------------------
        # RATINGS SECTION
        # ----------------------------------
        if category_filter == "Rating":
            st.subheader("Wine Rating Distribution")

            rating_df = df[df["Category"] == "Rating"].copy()
            if selected_wine != "All Wines":
                rating_df = rating_df[rating_df["Wine"] == selected_wine]

            if rating_df.empty:
                st.write("No ratings for the selected wine.")
            else:
                # Build histogram from 1..10
                ratings_range = range(1, 11)
                rating_counts = rating_df["Rating"].value_counts().reindex(ratings_range, fill_value=0)

                # User ratings
                if selected_user == "All Users":
                    user_rating_values = set()
                else:
                    user_rating_values = set(rating_df.loc[rating_df["Name"] == selected_user, "Rating"].dropna())

                # Color bins
                colors = []
                for r in ratings_range:
                    if r in user_rating_values:
                        colors.append("orange")
                    else:
                        colors.append("skyblue")

                fig, ax = plt.subplots()
                ax.bar(ratings_range, rating_counts, color=colors)
                ax.set_xticks(list(ratings_range))
                ax.set_title("Wine Rating Distribution")
                ax.set_xlabel("Rating")
                ax.set_ylabel("Count")

                # Legend
                patch_all = mpatches.Patch(color='skyblue', label='All Ratings')
                patch_user = mpatches.Patch(color='orange', label=selected_user)
                ax.legend(handles=[patch_all, patch_user])

                st.pyplot(fig)

                # ------------------------------
                # Comparison Summary for User
                # ------------------------------
                if selected_user != "All Users":
                    user_ratings = rating_df[rating_df["Name"] == selected_user]
                    if not user_ratings.empty:
                        user_mean = user_ratings["Rating"].mean()
                        overall_mean = rating_df["Rating"].mean()

                        prompt_cmp = f"""
                        A user named {selected_user} has rated {selected_wine} with an average rating of {user_mean:.1f}.
                        The overall average rating for this wine is {overall_mean:.1f}.
                        Summarize how this user's rating compares to the general trend.
                        """
                        comparison_summary = generate_summary(prompt_cmp)

                        st.subheader(f"📌 Comparison Summary for {selected_user}")
                        st.write(comparison_summary)
                    else:
                        st.write(f"No personal rating data found for {selected_user} on this wine.")

                # ------------------------------------------
                # Funny “Read” Summary
                # ------------------------------------------
                if selected_wine != "All Wines":
                    wine_ratings = rating_df["Rating"].dropna().tolist()
                    if len(wine_ratings) > 0:
                        overall_mean = np.mean(wine_ratings)
                        if selected_user != "All Users":
                            user_ratings = rating_df[rating_df["Name"] == selected_user]["Rating"]
                            user_mean = user_ratings.mean() if not user_ratings.empty else overall_mean
                        else:
                            user_mean = overall_mean

                        distribution_str = ", ".join(map(str, wine_ratings))

                        # Build the prompt
                        prompt_funny = f"""
                        A user named {selected_user} rated {selected_wine} with an average score of {user_mean:.1f} out of 10.
                        The overall average rating for this wine from all users is {overall_mean:.1f} out of 10.

                        Here is the full distribution of ratings for {selected_wine}: {distribution_str}.
                        The user you're talking to rated it {user_mean:.1f}.

                        Based on how they rated this wine in comparison to everyone else, write a funny "read" of this person.
                        Don't spill over into hate speech or harassment.

                        Don't refer to the quality of the wine in general. Only use the distribution of ratings you received.
                        Use funny queer slang and chronically online Gen Z references.
                        Keep it to one or two paragraphs. Don't use overly flowery language or make it too dense.
                        """

                        # If this is the first time for a prompt, store it in session_state
                        if "funny_prompt" not in st.session_state:
                            st.session_state.funny_prompt = None
                        if "funny_response" not in st.session_state:
                            st.session_state.funny_response = None

                        # If user changed, update stored prompt/response
                        if (st.session_state.get("funny_prompt") != prompt_funny):
                            st.session_state.funny_prompt = prompt_funny
                            st.session_state.funny_response = generate_summary(prompt_funny)

                        # Show the summary
                        st.subheader(f"📌 Summary of {selected_wine}")
                        st.write(st.session_state.funny_response)

                        # "Regenerate" button
                        if st.button("♻️ Regenerate AI Summary"):
                            st.session_state.funny_response = generate_summary(st.session_state.funny_prompt)
                            st.rerun()


        # ----------------------------------
        # TASTES SECTION
        # ----------------------------------
        else:
            st.subheader("Tasting Notes Distribution")

            taste_df = df[df["Category"] == "Taste"]
            if selected_wine != "All Wines":
                taste_df = taste_df[taste_df["Wine"] == selected_wine]

            if taste_df.empty:
                st.write("No tasting notes available for the selected wine.")
            else:
                taste_counts = taste_df["Taste"].value_counts()
                fig, ax = plt.subplots()
                taste_counts.plot(kind="bar", color="orange", ax=ax)
                ax.set_title("Tasting Notes Distribution")
                ax.set_xlabel("Tasting Notes")
                ax.set_ylabel("Count")
                st.pyplot(fig)
