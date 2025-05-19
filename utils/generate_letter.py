import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

# Set the API key from your .env
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# Load the Gemini 1.5 Pro model
model = genai.GenerativeModel(model_name="gemini-1.5-pro-latest")

def generate_cover_letter(resume, job_desc, tone):
    prompt = f"""
You are an AI assistant that writes cover letters. Generate a {tone} cover letter using the following resume and job description.

Resume:
{resume}

Job Description:
{job_desc}

Cover Letter:
"""
    response = model.generate_content(prompt)
    return response.text
