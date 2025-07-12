import streamlit as st
import pandas as pd
import requests
import plotly.express as px
from datetime import datetime, timedelta, timezone
from dateutil.parser import parse
from collections import defaultdict

# --- Configuração da Página ---
st.set_page_config(
    page_title="Dashboard Taiga Avançado",
    page_icon="🚀",
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
            response = requests.post(auth_url, json=auth_data, headers=self.headers, timeout=15)
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
            response = requests.get(url, headers=self.headers, timeout=15)
            if response.status_code == 200:
                return response.json()
            return None
        except Exception:
            return None
    
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
                if 'x-pagination-next' in response.headers and response.headers['x-pagination-next'].lower() == 'false':
                    break
                page += 1
            except requests.exceptions.RequestException:
                break
        return results

    def get_user_stories(self, project_id):
        url = f"{self.base_url}/api/v1/userstories"
        params = {"project": project_id}
        return self._get_paginated_data(url, params)
        
    def get_tasks(self, project_id):
        url = f"{self.base_url}/api/v1/tasks"
        params = {"project": project_id}
        return self._get_paginated_data(url, params)
        
    def get_issues(self, project_id):
        url = f"{self.base_url}/api/v1/issues"
        params = {"project": project_id}
        return self._get_paginated_data(url, params)

# --- Funções de Cálculo ---
def calculate_metrics(all_items, issues):
    metrics = {}
    WIP_STATUSES = ["Em Progresso", "Em Desenvolvimento", "Fazendo", "In Progress", "Doing", "Em Revisão", "Review"]
    CLOSED_STATUSES = ["Concluído", "Done", "Fechado", "Closed", "Arquivado", "Archived"]
    
    def get_status_counts(items):
        status_counts = defaultdict(int)
        for item in items:
            status = item.get('status_extra_info', {}).get('name', 'N/A')
            status_counts[status] += 1
        return dict(status_counts)

    metrics['status_counts'] = get_status_counts(all_items)
    
    wip_items = [item for item in all_items if item.get('status_extra_info', {}).get('name') in WIP_STATUSES]
    metrics['wip_by_status'] = get_status_counts(wip_items)
    metrics['total_wip'] = len(wip_items)

    aging_tasks = []
    for item in all_items:
        if not item.get('is_closed', False) and item.get('status_extra_info', {}).get('name') not in CLOSED_STATUSES:
            modified_date = parse(item['modified_date'])
            age = (datetime.now(timezone.utc) - modified_date).days
            assignee_info = item.get('assigned_to_extra_info') or {}
            assignee_name = assignee_info.get('full_name_display', 'Não atribuído')
            aging_tasks.append({
                "Tarefa": item['subject'],
                "Status Atual": item.get('status_extra_info', {}).get('name', 'N/A'),
                "Dias Parada": age,
                "Responsável": assignee_name,
                "Ref": item['ref']
            })
    metrics['aging_tasks'] = sorted(aging_tasks, key=lambda x: x['Dias Parada'], reverse=True)
    
    metrics['issues_by_type'] = defaultdict(int)
    metrics['issues_by_severity'] = defaultdict(int)
    for issue in issues:
        metrics['issues_by_type'][issue.get('type_extra_info', {}).get('name', 'N/A')] += 1
        metrics['issues_by_severity'][issue.get('severity_extra_info', {}).get('name', 'N/A')] += 1

    return metrics

# --- Função Principal de Cache e Fetch ---
@st.cache_data(ttl=600)
def get_taiga_data(base_url, username, password, project_id):
    st.sidebar.title("Configuração e Status")
    api = TaigaAPI(base_url, username, password)
    if not api.authenticate():
        st.sidebar.error("Falha na Autenticação"); return {"error": "Falha na Autenticação"}
    st.sidebar.success("Autenticação OK")
    
    project_data = api.get_project_data(project_id)
    if not project_data:
        st.sidebar.error("Projeto não encontrado"); return {"error": "Projeto não encontrado"}
    st.sidebar.success(f"Projeto: {project_data.get('name', 'N/A')}")
        
    with st.spinner("Buscando todos os itens do projeto..."):
        user_stories = api.get_user_stories(project_id)
        tasks = api.get_tasks(project_id)
        issues = api.get_issues(project_id)
    
    return {
        'project_data': project_data,
        'user_stories': user_stories,
        'tasks': tasks,
        'issues': issues,
        'last_update': datetime.now()
    }

# --- Interface do Usuário ---
def main():
    st.title("🚀 Dashboard Taiga")
    
    try:
        taiga_url = st.secrets.get("TAIGA_URL", "https://api.taiga.io")
        username = st.secrets["TAIGA_USERNAME"]
        password = st.secrets["TAIGA_PASSWORD"]
        project_id = str(st.secrets["TAIGA_PROJECT_ID"])
    except KeyError as e:
        st.error(f"❌ Credencial não encontrada nos Secrets: {e}"); return

    data = get_taiga_data(taiga_url, username, password, project_id)
    
    if data.get("error"):
        st.error(f"❌ {data['error']}"); return

    project_data = data.get('project_data')
    st.header(f"Projeto: {project_data.get('name', 'N/A')}")
    st.markdown("---")
    
    user_stories = data.get('user_stories', [])
    tasks = data.get('tasks', [])
    issues = data.get('issues', [])

    for us in user_stories: us['item_type'] = 'User Story'
    for task in tasks: task['item_type'] = 'Task'
    for issue in issues: issue['item_type'] = 'Issue'
    all_items_unfiltered = user_stories + tasks + issues

    # --- PAINEL DE FILTROS APRIMORADO ---
    st.sidebar.header("Filtros de Visualização")
    
    # Filtro por Responsável
    assignee_list = sorted(list(set(
        (item.get('assigned_to_extra_info') or {}).get('full_name_display', 'Não atribuído')
        for item in all_items_unfiltered
    )))
    selected_assignees = st.sidebar.multiselect("Responsável:", options=assignee_list, placeholder="Selecione um ou mais responsáveis")

    # <<< FILTRO DE STATUS ADICIONADO DE VOLTA >>>
    status_list = sorted(list(set(
        (item.get('status_extra_info') or {}).get('name', 'N/A')
        for item in all_items_unfiltered
    )))
    selected_statuses = st.sidebar.multiselect("Status:", options=status_list, placeholder="Selecione um ou mais status")

    # Filtro por Prioridade
    priority_list = sorted(list(set(
        (item.get('priority_extra_info') or {}).get('name', 'N/A')
        for item in all_items_unfiltered
    )))
    selected_priorities = st.sidebar.multiselect("Prioridade:", options=priority_list, placeholder="Selecione uma ou mais prioridades")
    
    # Filtro por Tags
    all_tags = sorted(list(set(
        tag[0] for item in all_items_unfiltered if item.get('tags') for tag in item['tags']
    )))
    selected_tags = st.sidebar.multiselect("Tags:", options=all_tags, placeholder="Selecione uma ou mais tags")

    # Filtros Booleanos (checkbox)
    is_blocked = st.sidebar.checkbox("Mostrar apenas itens bloqueados")
    is_unassigned = st.sidebar.checkbox("Mostrar apenas itens não atribuídos")
    
    # --- LÓGICA DE FILTRAGEM ---
    filtered_items = all_items_unfiltered
    if selected_assignees:
        filtered_items = [item for item in filtered_items if (item.get('assigned_to_extra_info') or {}).get('full_name_display', 'Não atribuído') in selected_assignees]
    
    # <<< LÓGICA DO FILTRO DE STATUS ADICIONADA DE VOLTA >>>
    if selected_statuses:
        filtered_items = [item for item in filtered_items if (item.get('status_extra_info') or {}).get('name', 'N/A') in selected_statuses]
        
    if selected_priorities:
        filtered_items = [item for item in filtered_items if (item.get('priority_extra_info') or {}).get('name', 'N/A') in selected_priorities]
    if selected_tags:
        filtered_items = [item for item in filtered_items if item.get('tags') and any(tag[0] in selected_tags for tag in item['tags'])]
    if is_blocked:
        filtered_items = [item for item in filtered_items if item.get('is_blocked')]
    if is_unassigned:
        filtered_items = [item for item in filtered_items if not item.get('assigned_to')]

    filtered_issues = [item for item in filtered_items if item['item_type'] == 'Issue']
    metrics = calculate_metrics(filtered_items, filtered_issues)

    # --- SEÇÃO SAÚDE DO FLUXO ---
    st.header("❤️‍🩹 Saúde do Fluxo")
    col1, col2 = st.columns([1,2])
    with col1:
        st.metric("Total de Itens em WIP", metrics.get('total_wip', 0))
        wip_data = metrics.get('wip_by_status', {})
        if wip_data:
            fig_wip = px.bar(x=list(wip_data.values()), y=list(wip_data.keys()), orientation='h', labels={'x': '# Itens', 'y': 'Status'}, text=list(wip_data.values()))
            fig_wip.update_layout(showlegend=False)
            st.plotly_chart(fig_wip, use_container_width=True)
    with col2:
        st.subheader("Envelhecimento de Itens em Aberto (Top 10)")
        aging_data = metrics.get('aging_tasks', [])
        if aging_data:
            st.dataframe(pd.DataFrame(aging_data).head(10), use_container_width=True, hide_index=True, column_config={"Ref": st.column_config.NumberColumn(format="%d")})
        else:
            st.info("Nenhum item em aberto para analisar (conforme filtros aplicados).")
    
    # --- SEÇÃO QUALIDADE ---
    st.markdown("---")
    st.header("🎯 Qualidade do Projeto")
    col1, col2 = st.columns([1, 1])
    with col1:
        st.subheader("Issues por Tipo")
        issues_by_type = metrics.get('issues_by_type', {})
        if issues_by_type:
            fig_type = px.pie(values=list(issues_by_type.values()), names=list(issues_by_type.keys()), hole=0.3)
            st.plotly_chart(fig_type, use_container_width=True)
        else:
            st.info("Nenhuma issue encontrada (conforme filtros).")
    with col2:
        st.subheader("Issues por Severidade")
        issues_by_severity = metrics.get('issues_by_severity', {})
        if issues_by_severity:
            fig_sev = px.bar(x=list(issues_by_severity.keys()), y=list(issues_by_severity.values()), labels={'x':'Severidade', 'y':'# Issues'}, text=list(issues_by_severity.values()))
            st.plotly_chart(fig_sev, use_container_width=True)
    
    st.markdown("---")
    st.markdown(f"**Atualizado em:** {data['last_update'].strftime('%d/%m/%Y às %H:%M:%S')}")

if __name__ == "__main__":
    main()
