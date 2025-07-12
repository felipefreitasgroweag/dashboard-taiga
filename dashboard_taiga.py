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
            url = f"{self.base_url}/api/v1/projects/by_slug?slug={project_id}"
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
        params = {"project__slug": project_id}
        return self._get_paginated_data(url, params)
        
    def get_tasks(self, project_id):
        url = f"{self.base_url}/api/v1/tasks"
        params = {"project__slug": project_id}
        return self._get_paginated_data(url, params)
        
    def get_issues(self, project_id):
        url = f"{self.base_url}/api/v1/issues"
        params = {"project__slug": project_id}
        return self._get_paginated_data(url, params)

    def get_milestones(self, project_id):
        url = f"{self.base_url}/api/v1/milestones"
        params = {"project__slug": project_id}
        return self._get_paginated_data(url, params)

    def get_item_history(self, item_id, item_type):
        # item_type deve ser 'userstory', 'task', ou 'issue'
        url = f"{self.base_url}/api/v1/history/{item_type}/{item_id}"
        try:
            response = requests.get(url, headers=self.headers, params={"project__slug": project_id})
            if response.status_code == 200:
                return response.json()
        except requests.exceptions.RequestException:
            return []
        return []

# --- Funções de Cálculo ---
def calculate_metrics(all_items, issues, status_order_map):
    metrics = {}
    WIP_STATUSES = ["Backlog", "Semanais/OnGoing", "Refine / Discovery", "UX/UI", "In Progress", "Ajuste", "Impeditivo", "Code Review", "To Do (QA)", "QA em andamento", "Business Review", "Fila de Deploy", "Validação Seara", "Concluído", "Relatórios"]
    CLOSED_STATUSES = ["Concluído"]
    
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
    
    # Métricas de Issues
    metrics['issues_by_type'] = defaultdict(int)
    metrics['issues_by_severity'] = defaultdict(int)
    for issue in issues:
        metrics['issues_by_type'][issue.get('type_extra_info', {}).get('name', 'N/A')] += 1
        metrics['issues_by_severity'][issue.get('severity_extra_info', {}).get('name', 'N/A')] += 1

    return metrics

def calculate_flowback(items_with_history, status_order_map):
    flowback_count = 0
    total_transitions = 0
    for item in items_with_history:
        for event in item.get('history', []):
            if 'status' in event.get('values_diff', {}):
                total_transitions += 1
                old_status_id, new_status_id = event['values_diff']['status']
                old_order = status_order_map.get(old_status_id, -1)
                new_order = status_order_map.get(new_status_id, -1)
                if old_order != -1 and new_order != -1 and new_order < old_order:
                    flowback_count += 1
    
    return (flowback_count / total_transitions * 100) if total_transitions > 0 else 0


# --- Função Principal de Cache e Fetch ---
@st.cache_data(ttl=600) # Cache por 10 minutos
def get_taiga_data(base_url, username, password, project_id):
    api = TaigaAPI(base_url, username, password)
    if not api.authenticate():
        return {"error": "Falha na Autenticação"}
    
    project_data = api.get_project_data(project_id)
    if not project_data:
        return {"error": "Projeto não encontrado"}
        
    user_stories = api.get_user_stories(project_id)
    tasks = api.get_tasks(project_id)
    issues = api.get_issues(project_id)
    milestones = api.get_milestones(project_id)
    
    # Mapeia a ordem dos status para cálculo de flowback
    status_order_map = {status['id']: status['order'] for status in project_data.get('us_statuses', [])}
    status_order_map.update({status['id']: status['order'] for status in project_data.get('task_statuses', [])})
    status_order_map.update({status['id']: status['order'] for status in project_data.get('issue_statuses', [])})

    # Busca histórico (pode ser lento, vamos limitar aos itens modificados recentemente)
    one_month_ago = datetime.now(timezone.utc) - timedelta(days=30)
    all_items = user_stories + tasks + issues
    items_to_check_history = [item for item in all_items if parse(item['modified_date']) > one_month_ago]
    
    with st.spinner(f"Analisando histórico de {len(items_to_check_history)} itens recentes..."):
        for item in items_to_check_history:
            item_type = item.get('item_type', 'userstory') # Adapte conforme a API
            if 'tasks' in item['project_extra_info']['slug']: item_type = 'task'
            if 'issues' in item['project_extra_info']['slug']: item_type = 'issue'
            item['history'] = api.get_item_history(item['id'], item_type)
    
    return {
        'project_data': project_data,
        'user_stories': user_stories,
        'tasks': tasks,
        'issues': issues,
        'milestones': milestones,
        'items_with_history': items_to_check_history,
        'status_order_map': status_order_map,
        'last_update': datetime.now()
    }

# --- Interface do Usuário ---
def main():
    st.sidebar.title("Configuração e Filtros")
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
    st.title(f"🚀 Dashboard Taiga: {project_data.get('name', 'Projeto')}")
    st.markdown("---")
    
    user_stories = data.get('user_stories', [])
    tasks = data.get('tasks', [])
    issues = data.get('issues', [])
    milestones = data.get('milestones', [])
    items_with_history = data.get('items_with_history', [])
    status_order_map = data.get('status_order_map', {})

    for us in user_stories: us['item_type'] = 'User Story'
    for task in tasks: task['item_type'] = 'Task'
    for issue in issues: issue['item_type'] = 'Issue'
    all_items_unfiltered = user_stories + tasks + issues

    # --- PAINEL DE FILTROS ---
    st.sidebar.header("Filtros de Visualização")
    
    # Filtro por Sprints/Milestones
    milestone_names = {ms['name']: ms['id'] for ms in milestones}
    selected_milestone_names = st.sidebar.multiselect("Filtrar por Sprint:", options=milestone_names.keys())
    selected_milestone_ids = [milestone_names[name] for name in selected_milestone_names]

    # Filtro por Tags
    all_tags = set()
    for item in all_items_unfiltered:
        if item.get('tags'):
            all_tags.update(tag[0] for tag in item['tags'])
    selected_tags = st.sidebar.multiselect("Filtrar por Tags:", options=sorted(list(all_tags)))

    # Filtro por Intervalo de Datas
    date_range = st.sidebar.date_input("Filtrar por Data de Criação:", value=(datetime.now() - timedelta(days=90), datetime.now()))

    # --- LÓGICA DE FILTRAGEM ---
    filtered_items = all_items_unfiltered
    if selected_milestone_ids:
        filtered_items = [item for item in filtered_items if item.get('milestone') in selected_milestone_ids]
    if selected_tags:
        filtered_items = [item for item in filtered_items if item.get('tags') and any(tag[0] in selected_tags for tag in item['tags'])]
    if len(date_range) == 2:
        start_date, end_date = date_range
        start_datetime = datetime.combine(start_date, datetime.min.time()).replace(tzinfo=timezone.utc)
        end_datetime = datetime.combine(end_date, datetime.max.time()).replace(tzinfo=timezone.utc)
        filtered_items = [item for item in filtered_items if start_datetime <= parse(item['created_date']) <= end_datetime]

    filtered_issues = [item for item in filtered_items if item['item_type'] == 'Issue']
    metrics = calculate_metrics(filtered_items, filtered_issues, status_order_map)
    flowback_rate = calculate_flowback(items_with_history, status_order_map) # Calculado sobre itens recentes

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
            st.dataframe(pd.DataFrame(aging_data).head(10), use_container_width=True, hide_index=True)
        else:
            st.info("Nenhum item em aberto para analisar.")
    
    # --- SEÇÃO QUALIDADE ---
    st.markdown("---")
    st.header("🎯 Qualidade do Projeto")
    col1, col2 = st.columns([1, 2])
    with col1:
        st.metric("Taxa de Flowback (Retrabalho)", f"{flowback_rate:.1f}%")
        st.info("Mede a % de vezes que um item voltou para uma etapa anterior no fluxo (baseado em itens recentes).")
    with col2:
        st.subheader("Issues por Tipo")
        issues_by_type = metrics.get('issues_by_type', {})
        if issues_by_type:
            fig_type = px.pie(values=list(issues_by_type.values()), names=list(issues_by_type.keys()), hole=0.3)
            st.plotly_chart(fig_type, use_container_width=True)
        else:
            st.info("Nenhuma issue encontrada.")
    st.subheader("Issues por Severidade")
    issues_by_severity = metrics.get('issues_by_severity', {})
    if issues_by_severity:
        fig_sev = px.bar(x=list(issues_by_severity.keys()), y=list(issues_by_severity.values()), labels={'x':'Severidade', 'y':'# Issues'}, text=list(issues_by_severity.values()))
        st.plotly_chart(fig_sev, use_container_width=True)
    
    st.markdown("---")
    st.markdown(f"**Atualizado em:** {data['last_update'].strftime('%d/%m/%Y às %H:%M:%S')}")

if __name__ == "__main__":
    main()
