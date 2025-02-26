import os
import requests
from dotenv import load_dotenv

load_dotenv()

API_BASE_URL = os.getenv('API_BASE_URL')
API_STAGING_URL = os.getenv('API_STAGING_URL')
API_USERNAME = os.getenv('API_USERNAME')
API_PASSWORD = os.getenv('API_PASSWORD')
API_STAGING_PASSWORD = os.getenv('API_STAGING_PASSWORD')
LOCAL_ORDERS_DIR = os.getenv('LOCAL_ORDERS_DIR')

class APIError(Exception):
    def __init__(self, data):
        self.title = data.get('title', 'API Error')
        self.status = data.get('status')
        self.code = data.get('code')
        self.inner = data.get('inner')
        self.json = data
        message = f"{self.title} (status: {self.status}, code: {self.code})"
        super().__init__(message)

def get_jwt():
    auth_url = f'{API_BASE_URL}/auth/login'
    payload = {
        "username": API_USERNAME,
        "password": API_PASSWORD,
    }
    response = requests.post(auth_url, json=payload)
    data = response.json()
    if response.ok:
        token = data.get('data', {}).get('jwt', {}).get('token')
        return token
    else:
        raise APIError(data)