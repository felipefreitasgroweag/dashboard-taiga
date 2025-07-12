import streamlit as st
import pandas as pd
import requests
import plotly.express as px
from datetime import datetime, timedelta, timezone
from dateutil.parser import parse

# --- Configuração da Página ---
st.set_page_config(
    page_title="Dashboard Taiga",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Classe da API do Taiga ---
class TaigaAPI:
    def __init__(self, base_url, username, password):
        self.base_url = base_url.rstrip('/')
        self.username = username
        self.password = password
        self.token = None
        self.headers = {'Content-Type': 'application/json'}
        
    def authenticate(self):
        try:
            auth_url = f"{self.base_url}/api/v1/auth"
            auth_data = {"username": self.username, "password": self.password, "type": "normal"}
            
            st.sidebar.write(f"🔗 Tentando conectar: {auth_url}")
            response = requests.post(auth_url, json=auth_data, headers=self.headers, timeout=10)
            st.sidebar.write(f"📡 Status da autenticação: {response.status_code}")
            
            if response.status_code == 200:
                auth_response = response.json()
                self.token = auth_response.get("auth_token")
                if self.token:
                    self.headers['Authorization'] = f'Bearer {self.token}'
                    st.sidebar.success("✅ Autenticação realizada com sucesso!")
                    return True
            st.error(f"❌ Falha na autenticação: {response.status_code} - {response.text}")
            return False
        except Exception as e:
            st.error(f"❌ Erro inesperado na autenticação: {str(e)}")
            return False
    
    def get_project_data(self, project_id):
        project_id = str(project_id)
        try:
            url = f"{self.base_url}/api/v1/projects/{project_id}"
            st.sidebar.write(f"🔍 Buscando projeto: {url}")
            response = requests.get(url, headers=self.headers, timeout=10)
            st.sidebar.write(f"📊 Status do projeto: {response.status_code}")
            
            if response.status_code ==
