import streamlit as st
import pandas as pd
import requests
import plotly.express as px
from datetime import datetime, timedelta
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
        # GARANTE QUE O ID SEJA TEXTO
        project_id = str(project_id)
        try:
            url = f"{self.base_url}/api/v1/projects/{project_id}"
            st.sidebar.write(f"🔍 Buscando projeto: {url}")
            response = requests.get(url, headers=self.headers, timeout=10)
            st.sidebar.write(f"📊 Status do projeto: {response.status_code}")
            
            if response.status_code == 200:
                project_data = response.json()
                st.sidebar.success(f"✅ Projeto encontrado: {project_data.get('name', 'N/A')}")
                return project_data
            return None
        except Exception as e:
            st.error(f"❌ Erro inesperado ao buscar projeto: {str(e)}")
            return None
    
    def _get_paginated_data(self, url, params):
        """Função auxiliar para buscar dados paginados da API."""
        results = []
        page = 1
        while True:
            params['page'] = page
            response = requests.get(url, headers=self.headers, params=params)
            if response.status_code != 200:
                break
            data = response.json()
            if not data:
                break
            results.extend(data)
            # Verifica se há uma próxima página no header 'x-pagination-next'
            if 'x-pagination-next' not in response.headers or not response.headers['x-pagination-next']:
                 break
            page += 1
        return results

    def get_user_stories(self, project_id):
        # GARANTE QUE O ID SEJA TEXTO
        project_id = str(project_id)
        url = f"{self.base_url}/api/v1/userstories"
        params = {"project": project_id}
        return self._get_paginated_data(url, params)
        
    def get_tasks(self, project_id):
        # GARANTE QUE O ID SEJA TEXTO
        project_id = str(project_id)
        url = f"{self.base_url}/api/v1/tasks"
        params = {"project": project_id}
        return self._get_paginated_data(url, params)
        
    def get_issues(self, project_id):
        # GARANTE QUE O ID SEJA TEXTO
        project_id = str(project_id)
        url = f"{self.base_url}/api/v1/issues"
        params = {"project": project_id}
        return self._get_paginated_data(url, params)

# --- Funções de Cálculo ---
def calculate_metrics(user_stories, tasks, issues):
    metrics = {}
    metrics['total_user_stories'] = len(user_stories)
    metrics['total_tasks'] = len(tasks)
    metrics['total_issues'] = len(issues)

    def get_status_counts(items):
        status_counts = {}
        for item in items:
            status = item.get('status_extra_info', {}).get('name', 'N/A')
            status_counts[status] = status_counts.get(status, 0) + 1
        return status_counts

    metrics['user_stories_by_status'] = get_status_counts(user_stories)
    metrics['tasks_by_status'] = get_status_counts(tasks)
    metrics['issues_by_status'] = get_status_counts(issues)
    
    all_items = user_stories + tasks
    
    cycle_times = []
    for item in all_items:
        if item.get('created_date') and item.get('finished_date'):
            try:
                cycle_time = (parse(item['finished_date']) - parse(item['created_date'])).days
                if cycle_time >= 0:
                    cycle_times.append(cycle_time)
            except (TypeError, ValueError):
                continue
    metrics['cycle_times'] = cycle_times

    completed_items = [item for item in all_items if item.get('is_closed') and item.get('finished_date')]
    if completed_items:
        one_week_ago = datetime.now(completed_items[0]['finished_date'].tzinfo) - timedelta(days=7)
        recent_completions = [item for item in completed_items if parse(item['finished_date']) >= one_week_ago]
        metrics['throughput'] = len(recent_completions)
    else:
        metrics['throughput'] = 0
        
    return metrics

# --- Função Principal de Cache e Fetch ---
@st.cache_data(ttl=300) # Cache por 5 minutos
def get_taiga_data(base_url, username, password, project_id):
    api = TaigaAPI(base_url, username, password)
    if not api.authenticate():
        return None
    
    # GARANTE QUE O ID SEJA TEXTO ao passar para as funções
    project_id_str = str(project_id)
    
    project_data = api.get_project_data(project_id_str)
    if not project_data:
        return None
        
    user_stories = api.get_user_stories(project_id_str)
    tasks = api.get_tasks(project_id_str)
    issues = api.get_issues(project_id_str)
    
    metrics = calculate_metrics(user_stories, tasks, issues)
    
    return {
        'project_data': project_data,
        'metrics': metrics,
        'last_update': datetime.now()
    }

# --- Interface do Usuário ---
def main():
    st.title("📊 Dashboard Taiga")
    st.markdown("---")
    
    try:
        taiga_url = st.secrets.get("TAIGA_URL", "https://api.taiga.io")
        username = st.secrets["TAIGA_USERNAME"]
        password = st.secrets["TAIGA_PASSWORD"]
        project_id = str(st.secrets["TAIGA_PROJECT_ID"]) # Conversão inicial
        
        st.sidebar.write("🔧 **Debug Info:**")
        st.sidebar.write(f"URL: {taiga_url}")
        st.sidebar.write(f"Username: {username}")
        st.sidebar.write(f"Project ID: {project_id}")
        
    except KeyError as e:
        st.error(f"❌ Credencial não encontrada nos Secrets: {e}")
        return

    data = get_taiga_data(taiga_url, username, password, project_id)
    
    if not data:
        st.error("❌ Não foi possível carregar os dados do projeto.")
        st.warning("Verifique as possíveis causas no painel de Debug à esquerda.")
        return

    project_data = data.get('project_data')
    metrics = data.get('metrics')
    
    st.header(f"📋 {project_data.get('name', 'Projeto Sem Nome')}")
    st.write(project_data.get('description', ''))
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("📖 User Stories", metrics.get('total_user_stories', 0))
    col2.metric("✅ Tasks", metrics.get('total_tasks', 0))
    col3.metric("🐛 Issues", metrics.get('total_issues', 0))
    col4.metric("🚀 Throughput (7 dias)", f"{metrics.get('throughput', 0)} itens")

    st.markdown("---")

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("📊 User Stories por Status")
        us_status_data = metrics.get('user_stories_by_status', {})
        if us_status_data:
            fig = px.pie(values=us_status_data.values(), names=us_status_data.keys())
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.write("Nenhuma User Story encontrada.")

    with col2:
        st.subheader("📊 Tasks por Status")
        task_status_data = metrics.get('tasks_by_status', {})
        if task_status_data:
            fig = px.bar(x=list(task_status_data.keys()), y=list(task_status_data.values()))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.write("Nenhuma Task encontrada.")

    st.markdown("---")
    st.subheader("📈 Métricas de Tempo")
    col1, col2 = st.columns(2)
    with col1:
        cycle_times = metrics.get('cycle_times', [])
        if cycle_times:
            avg_cycle_time = sum(cycle_times) / len(cycle_times)
            st.metric("⏱️ Cycle Time Médio", f"{avg_cycle_time:.1f} dias")
        else:
            st.metric("⏱️ Cycle Time Médio", "N/A")

    if cycle_times:
        st.subheader("📊 Distribuição de Cycle Times")
        fig = px.histogram(x=cycle_times, nbins=20, labels={'x':'Cycle Time (dias)'})
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")
    st.markdown(f"**Atualizado em:** {data['last_update'].strftime('%d/%m/%Y às %H:%M:%S')}")

if __name__ == "__main__":
    main()
