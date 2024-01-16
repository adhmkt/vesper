from celery import Celery
import os
from openai import OpenAI
import logging
import time
from dotenv import load_dotenv

load_dotenv()

def make_celery():
    # Use os.environ.get() to retrieve the Redis URL from the environment variable
    broker_url = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
    
    # broker_url ="rediss://:p0f52f84ba145e38dfa7b66fd8d53a436cec08b566f32a4082e383667ca8c1d84@ec2-3-226-149-176.compute-1.amazonaws.com:31320"
    # another comment
    
    
    celery = Celery(
        'tasks',
        backend=broker_url,
        broker=broker_url
    )
    celery.conf.update(
        task_serializer='json',
        accept_content=['json'],
        result_serializer='json'
    )
    return celery

celery = make_celery()

# OpenAI client setup
client = OpenAI(api_key=os.environ.get('OPENAI_API_KEY'))

@celery.task
def get_bot_response(thread_id, message, assistant_id):
    try:
        # Send the user's message to the thread
        client.beta.threads.messages.create(
            thread_id=thread_id,
            role="user",
            content=message
        )
        logging.info("Message sent to thread")

        # Run the assistant on the thread
        run = client.beta.threads.runs.create(
            thread_id=thread_id,
            assistant_id=assistant_id
        )
        logging.info(f"Run created: {run}")

        # Add a timeout mechanism for the loop
        timeout = time.time() + 60  # 60 seconds from now
        while True:
            if time.time() > timeout:
                logging.error("Timeout while waiting for run to complete")
                return "Sorry, the request timed out."

            run = client.beta.threads.runs.retrieve(
                thread_id=thread_id,
                run_id=run.id
            )
            if run.status == 'completed':
                break

        # Retrieve all messages from the thread
        messages_response = client.beta.threads.messages.list(
            thread_id=thread_id
        )

        # Extract the bot's response from the messages
        # response = " ".join(content.text.value for msg in messages_response.data if msg.role == 'assistant' for content in msg.content if hasattr(content, 'text'))
        # latest_message = next((msg for msg in reversed(messages_response.data) if msg.role == 'assistant'), None)
        # response = latest_message.content[0].text.value if latest_message and hasattr(latest_message.content[0], 'text') else ""
        
        

        # Find the timestamp of the latest user message
        latest_user_msg = next((msg for msg in reversed(messages_response.data) if msg.role == 'user'), None)
        latest_user_msg_timestamp = latest_user_msg.created_at if latest_user_msg else None

        # Find the first assistant message after the latest user message
        response = ""
        for msg in messages_response.data:
            if msg.role == 'assistant' and msg.created_at > latest_user_msg_timestamp:
                response = msg.content[0].text.value if hasattr(msg.content[0], 'text') else ""
                break
    
        return response

    except Exception as e:
        logging.error(f"Error in asynchronous bot response: {e}")
        return "Sorry, an error occurred."
  