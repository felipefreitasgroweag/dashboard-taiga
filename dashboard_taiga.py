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
            
            if response.status_code == 200:
                project_data = response.json()
                st.sidebar.success(f"✅ Projeto encontrado: {project_data.get('name', 'N/A')}")
                return project_data
            return None
        except Exception as e:
            st.error(f"❌ Erro inesperado ao buscar projeto: {str(e)}")
            return None
    
    def _get_paginated_data(self, url, params):
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
            if 'x-pagination-next' not in response.headers or not response.headers['x-pagination-next']:
                 break
            page += 1
        return results

    def get_user_stories(self, project_id):
        project_id = str(project_id)
        url = f"{self.base_url}/api/v1/userstories"
        params = {"project": project_id}
        return self._get_paginated_data(url, params)
        
    def get_tasks(self, project_id):
        project_id = str(project_id)
        url = f"{self.base_url}/api/v1/tasks"
        params = {"project": project_id}
        return self._get_paginated_data(url, params)
        
    def get_issues(self, project_id):
        project_id = str(project_id)
        url = f"{self.base_url}/api/v1/issues"
        params = {"project": project_id}
        return self._get_paginated_data(url, params)

# --- Funções de Cálculo ---
# --- Funções de Cálculo ---
def calculate_metrics(user_stories, tasks, issues):
    metrics = {}
    
    # IMPORTANTE: Configure aqui os nomes dos seus status que representam trabalho ativo
    WIP_STATUSES = ["Em Progresso", "Em Desenvolvimento", "Fazendo", "In Progress", "Doing", "Em Revisão", "Review"]
    
    all_items = user_stories + tasks
    
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
    
    wip_items = [item for item in all_items if item.get('status_extra_info', {}).get('name') in WIP_STATUSES]
    metrics['wip_by_status'] = get_status_counts(wip_items)
    metrics['total_wip'] = len(wip_items)

    aging_tasks = []
    for item in all_items:
        if not item.get('is_closed', False):
            modified_date = parse(item['modified_date'])
            age = (datetime.now(timezone.utc) - modified_date).days
            
            # AQUI ESTÁ A CORREÇÃO FINAL
            # Primeiro, pegamos o dicionário do responsável de forma segura
            assignee_info = item.get('assigned_to_extra_info') or {}
            # Agora, pegamos o nome a partir do dicionário (que pode estar vazio)
            assignee_name = assignee_info.get('full_name_display', 'Não atribuído')

            aging_tasks.append({
                "Tarefa": item['subject'],
                "Status Atual": item.get('status_extra_info', {}).get('name', 'N/A'),
                "Dias Parada": age,
                "Responsável": assignee_name
            })
            
    metrics['aging_tasks'] = sorted(aging_tasks, key=lambda x: x['Dias Parada'], reverse=True)
    
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
        first_finish_date_obj = parse(completed_items[0]['finished_date'])
        timezone_info = first_finish_date_obj.tzinfo
        one_week_ago = datetime.now(timezone_info) - timedelta(days=7)
        
        recent_completions = [item for item in completed_items if parse(item['finished_date']) >= one_week_ago]
        metrics['throughput'] = len(recent_completions)
    else:
        metrics['throughput'] = 0
        
    return metrics
    
    # NOVA MÉTRICA: WIP por status
    wip_items = [item for item in all_items if item.get('status_extra_info', {}).get('name') in WIP_STATUSES]
    metrics['wip_by_status'] = get_status_counts(wip_items)
    metrics['total_wip'] = len(wip_items)

    # NOVA MÉTRICA: Envelhecimento de Tarefas (Aging)
    aging_tasks = []
    for item in all_items:
        if not item.get('is_closed', False):
            modified_date = parse(item['modified_date'])
            age = (datetime.now(timezone.utc) - modified_date).days
            aging_tasks.append({
                "Tarefa": item['subject'],
                "Status Atual": item.get('status_extra_info', {}).get('name', 'N/A'),
                "Dias Parada": age,
                "Responsável": item.get('assigned_to_extra_info', {}).get('full_name_display', 'Não atribuído')
            })
    # Ordena as tarefas mais antigas primeiro
    metrics['aging_tasks'] = sorted(aging_tasks, key=lambda x: x['Dias Parada'], reverse=True)
    
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
        first_finish_date_obj = parse(completed_items[0]['finished_date'])
        timezone_info = first_finish_date_obj.tzinfo
        one_week_ago = datetime.now(timezone_info) - timedelta(days=7)
        
        recent_completions = [item for item in completed_items if parse(item['finished_date']) >= one_week_ago]
        metrics['throughput'] = len(recent_completions)
    else:
        metrics['throughput'] = 0
        
    return metrics

# --- Função Principal de Cache e Fetch ---
@st.cache_data(ttl=300)
def get_taiga_data(base_url, username, password, project_id):
    api = TaigaAPI(base_url, username, password)
    if not api.authenticate():
        return None
    
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
    
    try:
        taiga_url = st.secrets.get("TAIGA_URL", "https://api.taiga.io")
        username = st.secrets["TAIGA_USERNAME"]
        password = st.secrets["TAIGA_PASSWORD"]
        project_id = str(st.secrets["TAIGA_PROJECT_ID"])
        
        st.sidebar.title("Configuração e Debug")
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
    
    st.markdown("---")
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("📖 Total User Stories", metrics.get('total_user_stories', 0))
    col2.metric("✅ Total Tasks", metrics.get('total_tasks', 0))
    col3.metric("🐛 Total Issues", metrics.get('total_issues', 0))
    col4.metric("🚀 Throughput (7 dias)", f"{metrics.get('throughput', 0)} itens")

    # --- NOVA SEÇÃO: MÉTRICAS DE FLUXO ---
    st.markdown("---")
    st.header("🔬 Métricas de Fluxo e Eficiência")

    col1, col2 = st.columns([1, 2])

    with col1:
        st.subheader("Trabalho em Progresso (WIP)")
        total_wip = metrics.get('total_wip', 0)
        st.metric("Total de Itens em WIP", total_wip)
        
        wip_data = metrics.get('wip_by_status', {})
        if wip_data:
            fig_wip = px.bar(
                x=list(wip_data.keys()), 
                y=list(wip_data.values()),
                labels={'x': 'Status', 'y': 'Quantidade'},
                text=list(wip_data.values())
            )
            fig_wip.update_traces(textposition='outside')
            st.plotly_chart(fig_wip, use_container_width=True)

    with col2:
        st.subheader("Envelhecimento de Tarefas (Aging)")
        aging_data = metrics.get('aging_tasks', [])
        if aging_data:
            df_aging = pd.DataFrame(aging_data)
            st.dataframe(
                df_aging.head(10), # Mostra as 10 tarefas mais antigas
                use_container_width=True,
                hide_index=True
            )
        else:
            st.write("Nenhuma tarefa em aberto para analisar.")
    
    st.markdown("---")
    st.header("📊 Análise Geral de Itens")
    
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("User Stories por Status")
        us_status_data = metrics.get('user_stories_by_status', {})
        if us_status_data:
            fig = px.pie(values=list(us_status_data.values()), names=list(us_status_data.keys()))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.write("Nenhuma User Story encontrada.")

    with col2:
        st.subheader("Tasks por Status")
        task_status_data = metrics.get('tasks_by_status', {})
        if task_status_data:
            fig_tasks = px.pie(values=list(task_status_data.values()), names=list(task_status_data.keys()))
            st.plotly_chart(fig_tasks, use_container_width=True)
        else:
            st.write("Nenhuma Task encontrada.")

    st.markdown("---")
    st.header("📈 Métricas de Tempo")
    col1, col2 = st.columns(2)
    with col1:
        cycle_times = metrics.get('cycle_times', [])
        if cycle_times:
            avg_cycle_time = sum(cycle_times) / len(cycle_times)
            st.metric("⏱️ Cycle Time Médio", f"{avg_cycle_time:.1f} dias")
        else:
            st.metric("⏱️ Cycle Time Médio", "N/A")

    if cycle_times:
        st.subheader("Distribuição de Cycle Times")
        fig_cycle = px.histogram(x=cycle_times, nbins=20, labels={'x':'Cycle Time (dias)'})
        st.plotly_chart(fig_cycle, use_container_width=True)

    st.markdown("---")
    st.markdown(f"**Atualizado em:** {data['last_update'].strftime('%d/%m/%Y às %H:%M:%S')}")

if __name__ == "__main__":
    main()
