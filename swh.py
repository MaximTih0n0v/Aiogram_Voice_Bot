import requests
from dotenv import load_dotenv
import os

load_dotenv()

TG_API = os.getenv('TG_API')
whook = os.getenv('WEBHOOK_HOST')

response = requests.get(f'https://api.telegram.org/bot{TG_API}/setWebhook?url=https://{whook}/webhook')
print(response.json())
