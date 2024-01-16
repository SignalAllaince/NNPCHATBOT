import pymysql
from flask import jsonify, redirect, url_for
from flask import request, Flask
from chatbot import generate_response
from jsondumps import extract_json
from sendemail import send_email
import xml.etree.ElementTree as ET
import json
import asyncio
from dotenv import load_dotenv
import os
import jwt
from waitress import serve
from hubspot import create_ticket, update_ticket, delete_ticket, get_ticket, get_all_tickets
load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY")

@app.route('/bot', methods=['POST'])
def openai_chat():
    try:
        data = request.data
        user_input = None
        content_type = request.headers.get('Content-Type')

        if content_type == 'application/json':
            user_input = request.json.get("user")
        elif content_type == 'application/xml':
            root = ET.fromstring(data)
            user_input = root.find('user').text 
        elif content_type == 'text/plain':
            user_input = data.decode('utf-8')
        elif content_type == 'text/html':
            # Process HTML data
            # Extract user_input from HTML as needed
            pass

        if user_input:
            response = generate_response(user_input)
            json_data = extract_json(response) # Extract the JSON data from the response                                                                                                                                                  
            
            if json_data:
                data = json.loads(json_data)
                # Access the values using Python variables
                content = data["Content"]
                # priority = data["Priority"]
                subject = data["Subject"]
                payload = {
                "content": content,
                "hs_pipeline": 0,
                "hs_pipeline_stage": 1,
                "hs_ticket_priority": 'High',
                "subject": subject,
                }
                asyncio.run(create_ticket(payload))
                return jsonify({'message': 'Ticket created successfully'})
        return jsonify({"response": response})
    except Exception as e:
        print(e)
        return {"message": "An error occurred."}, 500  # Return a 500 Internal Server Error response  

mode = 'prod'

if __name__ == "__main__":
    if mode == 'dev':
        app.run(host='0.0.0.0', debug=True)
    else:
        serve(app, host='0.0.0.0', port = 5000, threads = 2)
