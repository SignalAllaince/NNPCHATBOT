from flask import Flask, jsonify, request
from jsondumps import extract_json
from sendemail import send_email
import xml.etree.ElementTree as ET
import json
from dotenv import load_dotenv
import os
from waitress import serve
import openai
from docfreader import intelligent_response

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY")

# Set up OpenAI
openai.api_type = os.environ.get('OPENAI_API_TYPE')
openai.api_base = os.environ.get('OPENAI_API_BASE')
openai.api_version = os.environ.get('OPENAI_API_VERSION')
openai.api_key = os.environ.get('OPENAI_API_KEY')

# Initialize an empty conversation with a system message
name = "Uchenna Nnamani"
content = f'''
                2. You introduce yourself at the beginning of the conversation like this - 'Hello {name}, I am the NNPC service desk assistant, do you need technical information or something else?' You must mention the user's name which is {name} and always start the conversation with this.
                3. If the user chooses technical information in 2: Ask what information is needed.
                4. Search for the required information after the user inputs a relevant prompt by calling the function 'intelligent_response'.
                5. Where information is not in the knowledge base, tell the user I am sorry but I do not currently have information regarding your inquiry.
                6. If the user chooses something else in 2, Ask if it is a service request or an incident.
                7. If the user responds with an incident: Ask details of the incident.
                8. After the user responds, ask the user if they would like to escalate the incident to a service request.
                9. If the user decides to escalate, generate details of the service request from the prior interaction, such as the subject of the request and the description of the problem as content and display it to the user in this format 'Subject: '', Content: '' ' as the details of their escalated ticket.
                10. If it's a service request in 6: Ask for details of the service request, which is the service description of the problem as content.
                12. After the user responds, ask the user if they would like to escalate the information to a service request.
                13. If the user decides to escalate, generate details of the service request from the prior interaction, such as the subject of the request and the description of the problem as content and display it to the user in this format 'Subject: '', Content: '' ' as the details of their escalated ticket.
                14. If the user responds, end the conversation with 'I am happy I could help, have a great day!'
                
                '''
conversation = [
    {
        "role": "system",
        "content": content
    }
]


def generate_response(prompt):
    global conversation  # Access the global conversation variable
    conversation.append({"role": "user", "content": prompt})

    # Generate a response using the conversation history
    response = openai.ChatCompletion.create(
        engine="servicedesk",
        messages=conversation,
        temperature=0.7,
        functions=[
            {
                # function to check if the solution is within available documents
                "name": "intelligent_response",  # Name of the function
                "description": "Check the knowledge base using this function",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "prompts": {
                            "type": "string",
                            "description": "This is the problem the user is facing"
                        },
                    },
                    "required": ["prompts"],
                },
            }
        ],
        function_call="auto",
        max_tokens=1000,
        top_p=0.95,
        frequency_penalty=0,
        presence_penalty=0,
        stop=None
    )

    check_response = response["choices"][0]["message"]
    print(check_response)
    if check_response.get("function_call"):
        function_name = check_response["function_call"]["name"]
        if function_name == "intelligent_response":
            available_functions = {
                "intelligent_response": intelligent_response,
            }
            function_to_call = available_functions[function_name]
            function_args = json.loads(check_response["function_call"]["arguments"])
            function_response = function_to_call(
                prompts=function_args.get("prompts"),
            )
            conversation.append(
                {
                    "role": "function",
                    "name": function_name,
                    "content": function_response,
                }
            )

            return function_response
    else:
        assistant_response = response.choices[0].message['content'].strip() if response.choices else ""
        conversation.append({"role": "assistant", "content": assistant_response})
        return assistant_response


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
            json_data = extract_json(response)  # Extract the JSON data from the response

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
                print(payload)
                send_email('Uchenna.Nnamani@nnpcgroup.com', subject, content)
                # asyncio.run(create_ticket(payload))

                return jsonify({'message': 'Your service request has been logged to the service desk successfully'})
        return jsonify({"response": response})
    except Exception as e:
        print(e)
        return {"message": "An error occurred."}, 500  # Return a 500 Internal Server Error response


if __name__ == "__main__":
    serve(app, host='0.0.0.0', port=8000, threads=2)
