import streamlit as st
import pandas as pd
import requests
import plotly.express as px
from datetime import datetime, timedelta, timezone
from dateutil.parser import parse

# --- Configuração da Página ---
st.set_page_config(
    page_title="Dashboard Taiga Interativo",
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
            response = requests.post(auth_url, json=auth_data, headers=self.headers, timeout=10)
            if response.status_code == 200:
                self.token = response.json().get("auth_token")
                if self.token:
                    self.headers['Authorization'] = f'Bearer {self.token}'
                    return True
            return False
        except Exception:
            return False
    
    def get_project_data(self, project_id):
        project_id = str(project_id)
        try:
            url = f"{self.base_url}/api/v1/projects/{project_id}"
            response = requests.get(url, headers=self.headers, timeout=10)
            if response.status_code == 200:
                return response.json()
            return None
        except Exception:
            return None
    
    # NOVA FUNÇÃO PARA BUSCAR TODAS AS PÁGINAS DE DADOS
    def _get_paginated_data(self, url, params):
        results = []
        page = 1
        while True:
            params['page'] = page
            try:
                response = requests.get(url, headers=self.headers, params=params)
                if response.status_code != 200:
                    break
                data = response.json()
                if not data:
                    break
                results.extend(data)
                # O Taiga usa o header 'x-pagination-next' para indicar se há mais páginas
                if 'x-pagination-next' in response.headers and response.headers['x-pagination-next'].lower() == 'false':
                    break
                page += 1
            except requests.exceptions.RequestException:
                break
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
def calculate_metrics(all_items):
    # A função agora recebe uma lista de itens já filtrada
    metrics = {}
    
    WIP_STATUSES = ["Em Progresso", "Em Desenvolvimento", "Fazendo", "In Progress", "Doing", "Em Revisão", "Review"]
    
    def get_status_counts(items):
        status_counts = {}
        for item in items:
            status = item.get('status_extra_info', {}).get('name', 'N/A')
            status_counts[status] = status_counts.get(status, 0) + 1
        return status_counts

    metrics['status_counts'] = get_status_counts(all_items)
    
    wip_items = [item for item in all_items if item.get('status_extra_info', {}).get('name') in WIP_STATUSES]
    metrics['wip_by_status'] = get_status_counts(wip_items)
    metrics['total_wip'] = len(wip_items)

    aging_tasks = []
    for item in all_items:
        if not item.get('is_closed', False):
            modified_date = parse(item['modified_date'])
            age = (datetime.now(timezone.utc) - modified_date).days
            assignee_info = item.get('assigned_to_extra_info') or {}
            assignee_name = assignee_info.get('full_name_display', 'Não atribuído')
            aging_tasks.append({
                "Tarefa": item['subject'],
                "Status Atual": item.get('status_extra_info', {}).get('name', 'N/A'),
                "Dias Parada": age,
                "Responsável": assignee_name
            })
    metrics['aging_tasks'] = sorted(aging_tasks, key=lambda x: x['Dias Parada'], reverse=True)
        
    return metrics

# --- Função Principal de Cache e Fetch ---
@st.cache_data(ttl=300)
def get_taiga_data(base_url, username, password, project_id):
    st.sidebar.title("Debug e Status")
    api = TaigaAPI(base_url, username, password)
    if not api.authenticate():
        st.sidebar.error("Falha na Autenticação")
        return None
    st.sidebar.success("Autenticação OK")
    
    project_id_str = str(project_id)
    
    project_data = api.get_project_data(project_id_str)
    if not project_data:
        st.sidebar.error("Projeto não encontrado")
        return None
    st.sidebar.success(f"Projeto: {project_data.get('name', 'N/A')}")
        
    with st.spinner("Buscando todos os itens do projeto (pode levar um momento)..."):
        user_stories = api.get_user_stories(project_id_str)
        tasks = api.get_tasks(project_id_str)
    
    return {
        'project_data': project_data,
        'user_stories': user_stories,
        'tasks': tasks,
        'last_update': datetime.now()
    }

# --- Interface do Usuário ---
def main():
    try:
        taiga_url = st.secrets.get("TAIGA_URL", "https://api.taiga.io")
        username = st.secrets["TAIGA_USERNAME"]
        password = st.secrets["TAIGA_PASSWORD"]
        project_id = str(st.secrets["TAIGA_PROJECT_ID"])
    except KeyError as e:
        st.error(f"❌ Credencial não encontrada nos Secrets: {e}")
        return

    data = get_taiga_data(taiga_url, username, password, project_id)
    
    if not data:
        st.error("❌ Não foi possível carregar os dados. Verifique o painel de Debug na barra lateral.")
        return

    project_data = data.get('project_data')
    user_stories = data.get('user_stories', [])
    tasks = data.get('tasks', [])
    
    # Adiciona o tipo a cada item para facilitar a filtragem
    for us in user_stories: us['item_type'] = 'User Story'
    for task in tasks: task['item_type'] = 'Task'
    all_items = user_stories + tasks
    
    st.title(f"📊 Dashboard: {project_data.get('name', 'Projeto Taiga')}")
    
    # --- Adicionados Filtros Interativos ---
    st.sidebar.title("Filtros")
    
    # Filtro por tipo de item
    item_types = ["User Story", "Task"]
    selected_types = st.sidebar.multiselect("Filtrar por Tipo de Item:", options=item_types, default=item_types)
    
    # Filtro por responsável
    assignee_list = sorted(list(set(
        (item.get('assigned_to_extra_info') or {}).get('full_name_display', 'Não atribuído')
        for item in all_items
    )))
    selected_assignees = st.sidebar.multiselect("Filtrar por Responsável:", options=assignee_list)

    # Filtro por status
    status_list = sorted(list(set(
        (item.get('status_extra_info') or {}).get('name', 'N/A')
        for item in all_items
    )))
    selected_statuses = st.sidebar.multiselect("Filtrar por Status:", options=status_list)

    # Aplica os filtros aos dados
    filtered_items = all_items
    if selected_types:
        filtered_items = [item for item in filtered_items if item['item_type'] in selected_types]
    if selected_assignees:
        filtered_items = [item for item in filtered_items if (item.get('assigned_to_extra_info') or {}).get('full_name_display', 'Não atribuído') in selected_assignees]
    if selected_statuses:
        filtered_items = [item for item in filtered_items if (item.get('status_extra_info') or {}).get('name', 'N/A') in selected_statuses]

    # Recalcula as métricas com os dados filtrados
    metrics = calculate_metrics(filtered_items)

    st.markdown("---")
    
    # --- Exibição das Métricas ---
    col1, col2, col3 = st.columns(3)
    col1.metric("Total de Itens Exibidos", len(filtered_items))
    col2.metric("Itens em WIP (Trabalho em Progresso)", metrics.get('total_wip', 0))
    col3.metric("Throughput (Não implementado com filtros)", "N/A") # Nota: Throughput complexo com filtros dinâmicos
    
    st.markdown("---")
    st.header("🔬 Métricas de Fluxo e Eficiência")
    col1, col2 = st.columns([1, 2])
    with col1:
        st.subheader("Trabalho em Progresso (WIP)")
        wip_data = metrics.get('wip_by_status', {})
        if wip_data:
            fig_wip = px.bar(
                x=list(wip_data.values()), 
                y=list(wip_data.keys()),
                orientation='h',
                labels={'x': 'Quantidade', 'y': 'Status'},
                text=list(wip_data.values())
            )
            fig_wip.update_traces(textposition='outside')
            st.plotly_chart(fig_wip, use_container_width=True)
    with col2:
        st.subheader("Envelhecimento de Tarefas (Aging)")
        aging_data = metrics.get('aging_tasks', [])
        if aging_data:
            df_aging = pd.DataFrame(aging_data)
            st.dataframe(df_aging.head(10), use_container_width=True, hide_index=True)
        else:
            st.write("Nenhuma tarefa em aberto para analisar (conforme filtros aplicados).")

    st.markdown("---")
    st.header("📊 Análise Geral de Itens")
    status_data = metrics.get('status_counts', {})
    if status_data:
        fig_pie = px.pie(values=list(status_data.values()), names=list(status_data.keys()), title="Distribuição Geral por Status")
        st.plotly_chart(fig_pie, use_container_width=True)
    else:
        st.write("Nenhum item encontrado com os filtros selecionados.")
    
    st.markdown("---")
    st.markdown(f"**Atualizado em:** {data['last_update'].strftime('%d/%m/%Y às %H:%M:%S')}")

if __name__ == "__main__":
    main()
