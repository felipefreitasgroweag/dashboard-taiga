import streamlit as st
import pandas as pd
import requests
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import json
from dateutil.parser import parse

# Configuração da página
st.set_page_config(
    page_title="Dashboard Taiga",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Classe para interagir com a API do Taiga
class TaigaAPI:
    def __init__(self, base_url, username, password):
        self.base_url = base_url.rstrip('/')
        self.username = username
        self.password = password
        self.token = None
        self.headers = {'Content-Type': 'application/json'}
        
    def authenticate(self):
        """Autentica na API do Taiga"""
        try:
            auth_url = f"{self.base_url}/api/v1/auth"
            auth_data = {
                "username": self.username,
                "password": self.password,
                "type": "normal"
            }
            
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
                else:
                    st.error("❌ Token não encontrado na resposta")
                    return False
            else:
                st.error(f"❌ Erro na autenticação: {response.status_code}")
                try:
                    error_data = response.json()
                    st.error(f"Detalhes: {error_data}")
                except:
                    st.error(f"Resposta: {response.text}")
                return False
                
        except requests.exceptions.Timeout:
            st.error("❌ Timeout na conexão com o Taiga")
            return False
        except requests.exceptions.ConnectionError:
            st.error("❌ Erro de conexão com o Taiga")
            return False
        except Exception as e:
            st.error(f"❌ Erro inesperado na autenticação: {str(e)}")
            return False
    
    def get_project_data(self, project_id):
        """Busca dados do projeto"""
        try:
            url = f"{self.base_url}/api/v1/projects/{project_id}"
            
            st.sidebar.write(f"🔍 Buscando projeto: {url}")
            
            response = requests.get(url, headers=self.headers, timeout=10)
            
            st.sidebar.write(f"📊 Status do projeto: {response.status_code}")
            
            if response.status_code == 200:
                project_data = response.json()
                st.sidebar.success(f"✅ Projeto encontrado: {project_data.get('name', 'N/A')}")
                return project_data
            elif response.status_code == 404:
                st.error(f"❌ Projeto {project_id} não encontrado")
                return None
            elif response.status_code == 403:
                st.error(f"❌ Acesso negado ao projeto {project_id}")
                return None
            else:
                st.error(f"❌ Erro ao buscar projeto: {response.status_code}")
                try:
                    error_data = response.json()
                    st.error(f"Detalhes: {error_data}")
                except:
                    st.error(f"Resposta: {response.text}")
                return None
                
        except requests.exceptions.Timeout:
            st.error("❌ Timeout ao buscar dados do projeto")
            return None
        except requests.exceptions.ConnectionError:
            st.error("❌ Erro de conexão ao buscar projeto")
            return None
        except Exception as e:
            st.error(f"❌ Erro inesperado ao buscar projeto: {str(e)}")
            return None
    
    def get_user_stories(self, project_id):
        """Busca todas as user stories do projeto"""
        try:
            url = f"{self.base_url}/api/v1/userstories"
            params = {"project": project_id}
            response = requests.get(url, headers=self.headers, params=params)
            
            if response.status_code == 200:
                return response.json()
            else:
                st.error(f"Erro ao buscar user stories: {response.status_code}")
                return []
        except Exception as e:
            st.error(f"Erro ao buscar user stories: {str(e)}")
            return []
    
    def get_tasks(self, project_id):
        """Busca todas as tasks do projeto"""
        try:
            url = f"{self.base_url}/api/v1/tasks"
            params = {"project": project_id}
            response = requests.get(url, headers=self.headers, params=params)
            
            if response.status_code == 200:
                return response.json()
            else:
                st.error(f"Erro ao buscar tasks: {response.status_code}")
                return []
        except Exception as e:
            st.error(f"Erro ao buscar tasks: {str(e)}")
            return []
    
    def get_issues(self, project_id):
        """Busca todas as issues do projeto"""
        try:
            url = f"{self.base_url}/api/v1/issues"
            params = {"project": project_id}
            response = requests.get(url, headers=self.headers, params=params)
            
            if response.status_code == 200:
                return response.json()
            else:
                st.error(f"Erro ao buscar issues: {response.status_code}")
                return []
        except Exception as e:
            st.error(f"Erro ao buscar issues: {str(e)}")
            return []

# Função para calcular métricas
@st.cache_data(ttl=300)  # Cache por 5 minutos
def fetch_and_process_data(base_url, username, password, project_id):
    """Busca e processa todos os dados do Taiga"""
    
    try:
        # Inicializa API
        api = TaigaAPI(base_url, username, password)
        
        # Autentica
        if not api.authenticate():
            st.error("❌ Falha na autenticação")
            return None
        
        # Busca dados do projeto
        project_data = api.get_project_data(project_id)
        if not project_data:
            st.error("❌ Projeto não encontrado ou sem acesso")
            return None
        
        # Busca outros dados
        user_stories = api.get_user_stories(project_id)
        tasks = api.get_tasks(project_id)
        issues = api.get_issues(project_id)
        
        # Processa dados
        metrics = calculate_metrics(project_data, user_stories, tasks, issues)
        
        return {
            'project_data': project_data,
            'user_stories': user_stories,
            'tasks': tasks,
            'issues': issues,
            'metrics': metrics,
            'last_update': datetime.now()
        }
        
    except Exception as e:
        st.error(f"❌ Erro ao buscar dados: {str(e)}")
        return None

def calculate_metrics(project_data, user_stories, tasks, issues):
    """Calcula todas as métricas do projeto"""
    
    metrics = {}
    
    # Métricas básicas
    metrics['total_user_stories'] = len(user_stories)
    metrics['total_tasks'] = len(tasks)
    metrics['total_issues'] = len(issues)
    
    # User Stories por status
    us_status = {}
    for us in user_stories:
        status = us.get('status_extra_info', {}).get('name', 'N/A')
        us_status[status] = us_status.get(status, 0) + 1
    metrics['user_stories_by_status'] = us_status
    
    # Tasks por status
    task_status = {}
    for task in tasks:
        status = task.get('status_extra_info', {}).get('name', 'N/A')
        task_status[status] = task_status.get(status, 0) + 1
    metrics['tasks_by_status'] = task_status
    
    # Issues por status
    issue_status = {}
    for issue in issues:
        status = issue.get('status_extra_info', {}).get('name', 'N/A')
        issue_status[status] = issue_status.get(status, 0) + 1
    metrics['issues_by_status'] = issue_status
    
    # Métricas de tempo (Cycle Time e Lead Time)
    metrics['cycle_times'] = calculate_cycle_times(user_stories + tasks)
    metrics['lead_times'] = calculate_lead_times(user_stories + tasks)
    
    # Métricas de qualidade
    metrics['bugs_ratio'] = calculate_bugs_ratio(issues)
    metrics['completion_rate'] = calculate_completion_rate(user_stories)
    
    # Métricas de produtividade
    metrics['throughput'] = calculate_throughput(user_stories, tasks)
    metrics['velocity'] = calculate_velocity(user_stories)
    
    return metrics

def calculate_cycle_times(items):
    """Calcula cycle time para itens"""
    cycle_times = []
    
    for item in items:
        created_date = item.get('created_date')
        finished_date = item.get('finished_date')
        
        if created_date and finished_date:
            try:
                created = parse(created_date)
                finished = parse(finished_date)
                cycle_time = (finished - created).days
                if cycle_time >= 0:
                    cycle_times.append(cycle_time)
            except:
                continue
    
    return cycle_times

def calculate_lead_times(items):
    """Calcula lead time para itens"""
    lead_times = []
    
    for item in items:
        created_date = item.get('created_date')
        modified_date = item.get('modified_date')
        
        if created_date and modified_date:
            try:
                created = parse(created_date)
                modified = parse(modified_date)
                lead_time = (modified - created).days
                if lead_time >= 0:
                    lead_times.append(lead_time)
            except:
                continue
    
    return lead_times

def calculate_bugs_ratio(issues):
    """Calcula a taxa de bugs"""
    if not issues:
        return 0
    
    bugs = sum(1 for issue in issues if 'bug' in issue.get('type', '').lower())
    return (bugs / len(issues)) * 100

def calculate_completion_rate(user_stories):
    """Calcula taxa de conclusão"""
    if not user_stories:
        return 0
    
    completed = sum(1 for us in user_stories if us.get('is_closed', False))
    return (completed / len(user_stories)) * 100

def calculate_throughput(user_stories, tasks):
    """Calcula throughput semanal"""
    completed_items = []
    
    for item in user_stories + tasks:
        if item.get('is_closed', False) and item.get('finished_date'):
            try:
                finished_date = parse(item['finished_date'])
                completed_items.append(finished_date)
            except:
                continue
    
    if not completed_items:
        return 0
    
    # Calcula throughput da última semana
    one_week_ago = datetime.now() - timedelta(days=7)
    recent_completions = [date for date in completed_items if date >= one_week_ago]
    
    return len(recent_completions)

def calculate_velocity(user_stories):
    """Calcula velocidade baseada em story points"""
    total_points = 0
    completed_points = 0
    
    for us in user_stories:
        points = us.get('total_points', 0)
        if points:
            total_points += points
            if us.get('is_closed', False):
                completed_points += points
    
    return {'total_points': total_points, 'completed_points': completed_points}

def main():
    """Função principal da aplicação"""
    
    st.title("📊 Dashboard Taiga")
    st.markdown("---")
    
    # Lê as credenciais dos secrets
    try:
        taiga_url = st.secrets.get("TAIGA_URL", "https://api.taiga.io")
        username = st.secrets["TAIGA_USERNAME"]
        password = st.secrets["TAIGA_PASSWORD"]
        project_id = st.secrets["TAIGA_PROJECT_ID"]
        
        # Debug das credenciais (sem mostrar a senha)
        st.sidebar.write("🔧 **Debug Info:**")
        st.sidebar.write(f"URL: {taiga_url}")
        st.sidebar.write(f"Username: {username}")
        st.sidebar.write(f"Project ID: {project_id}")
        
    except KeyError as e:
        st.error(f"❌ Credencial não encontrada: {e}")
        st.info("Verifique se todas as credenciais estão configuradas nos Secrets do Streamlit.")
        st.code("""
# Exemplo de configuração nos Secrets:
TAIGA_URL = "https://api.taiga.io"
TAIGA_USERNAME = "seu_email@exemplo.com"
TAIGA_PASSWORD = "sua_senha"
TAIGA_PROJECT_ID = 123456
        """)
        return
    
    # Busca e processa dados
    with st.spinner("Carregando dados do Taiga..."):
        data = fetch_and_process_data(taiga_url, username, password, project_id)
    
    if not data:
        st.error("❌ Não foi possível carregar os dados.")
        st.error("Possíveis causas:")
        st.error("1. Credenciais incorretas")
        st.error("2. Projeto não encontrado ou sem acesso")
        st.error("3. URL do Taiga incorreta")
        st.error("4. Problema de conectividade")
        return
    
    # Verifica se os dados essenciais existem
    project_data = data.get('project_data')
    metrics = data.get('metrics')
    
    if not project_data:
        st.error("❌ Dados do projeto não encontrados.")
        st.error("Verifique se o ID do projeto está correto e se você tem acesso a ele.")
        return
    
    if not metrics:
        st.error("❌ Não foi possível calcular as métricas.")
        return
    
    # Cabeçalho do projeto
    project_name = project_data.get('name', 'Projeto Sem Nome')
    project_description = project_data.get('description', 'Sem descrição')
    
    st.header(f"📋 {project_name}")
    st.write(project_description)
    
    # Métricas principais
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("📖 User Stories", metrics['total_user_stories'])
    
    with col2:
        st.metric("✅ Tasks", metrics['total_tasks'])
    
    with col3:
        st.metric("🐛 Issues", metrics['total_issues'])
    
    with col4:
        completion_rate = metrics['completion_rate']
        st.metric("📈 Taxa de Conclusão", f"{completion_rate:.1f}%")
    
    st.markdown("---")
    
    # Gráficos de status
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📊 User Stories por Status")
        if metrics['user_stories_by_status']:
            fig = px.pie(
                values=list(metrics['user_stories_by_status'].values()),
                names=list(metrics['user_stories_by_status'].keys()),
                title="Distribuição de User Stories"
            )
            st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.subheader("📊 Tasks por Status")
        if metrics['tasks_by_status']:
            fig = px.bar(
                x=list(metrics['tasks_by_status'].keys()),
                y=list(metrics['tasks_by_status'].values()),
                title="Distribuição de Tasks"
            )
            st.plotly_chart(fig, use_container_width=True)
    
    # Métricas avançadas
    st.markdown("---")
    st.subheader("📈 Métricas Avançadas")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        cycle_times = metrics['cycle_times']
        if cycle_times:
            avg_cycle_time = sum(cycle_times) / len(cycle_times)
            st.metric("⏱️ Cycle Time Médio", f"{avg_cycle_time:.1f} dias")
        else:
            st.metric("⏱️ Cycle Time Médio", "N/A")
    
    with col2:
        lead_times = metrics['lead_times']
        if lead_times:
            avg_lead_time = sum(lead_times) / len(lead_times)
            st.metric("📅 Lead Time Médio", f"{avg_lead_time:.1f} dias")
        else:
            st.metric("📅 Lead Time Médio", "N/A")
    
    with col3:
        throughput = metrics['throughput']
        st.metric("🚀 Throughput (7 dias)", f"{throughput} itens")
    
    # Gráfico de cycle time
    if cycle_times:
        st.subheader("📊 Distribuição de Cycle Times")
        fig = px.histogram(
            x=cycle_times,
            nbins=20,
            title="Distribuição de Cycle Times (dias)"
        )
        st.plotly_chart(fig, use_container_width=True)
    
    # Métricas de qualidade
    st.markdown("---")
    st.subheader("🎯 Métricas de Qualidade")
    
    col1, col2 = st.columns(2)
    
    with col1:
        bugs_ratio = metrics['bugs_ratio']
        st.metric("🐛 Taxa de Bugs", f"{bugs_ratio:.1f}%")
    
    with col2:
        velocity = metrics['velocity']
        if velocity['total_points'] > 0:
            velocity_rate = (velocity['completed_points'] / velocity['total_points']) * 100
            st.metric("⚡ Velocidade", f"{velocity_rate:.1f}%")
        else:
            st.metric("⚡ Velocidade", "N/A")
    
    # Tabelas detalhadas
    st.markdown("---")
    st.subheader("📋 Dados Detalhados")
    
    tab1, tab2, tab3 = st.tabs(["User Stories", "Tasks", "Issues"])
    
    with tab1:
        if data['user_stories']:
            df_us = pd.DataFrame(data['user_stories'])
            columns_to_show = ['subject', 'status_extra_info', 'assigned_to_extra_info', 'created_date', 'is_closed']
            df_display = df_us[columns_to_show].copy()
            df_display['status'] = df_display['status_extra_info'].apply(lambda x: x.get('name', 'N/A') if x else 'N/A')
            df_display['assigned_to'] = df_display['assigned_to_extra_info'].apply(lambda x: x.get('full_name', 'N/A') if x else 'N/A')
            df_display = df_display[['subject', 'status', 'assigned_to', 'created_date', 'is_closed']]
            st.dataframe(df_display, use_container_width=True)
    
    with tab2:
        if data['tasks']:
            df_tasks = pd.DataFrame(data['tasks'])
            columns_to_show = ['subject', 'status_extra_info', 'assigned_to_extra_info', 'created_date', 'is_closed']
            df_display = df_tasks[columns_to_show].copy()
            df_display['status'] = df_display['status_extra_info'].apply(lambda x: x.get('name', 'N/A') if x else 'N/A')
            df_display['assigned_to'] = df_display['assigned_to_extra_info'].apply(lambda x: x.get('full_name', 'N/A') if x else 'N/A')
            df_display = df_display[['subject', 'status', 'assigned_to', 'created_date', 'is_closed']]
            st.dataframe(df_display, use_container_width=True)
    
    with tab3:
        if data['issues']:
            df_issues = pd.DataFrame(data['issues'])
            columns_to_show = ['subject', 'status_extra_info', 'assigned_to_extra_info', 'created_date', 'is_closed']
            df_display = df_issues[columns_to_show].copy()
            df_display['status'] = df_display['status_extra_info'].apply(lambda x: x.get('name', 'N/A') if x else 'N/A')
            df_display['assigned_to'] = df_display['assigned_to_extra_info'].apply(lambda x: x.get('full_name', 'N/A') if x else 'N/A')
            df_display = df_display[['subject', 'status', 'assigned_to', 'created_date', 'is_closed']]
            st.dataframe(df_display, use_container_width=True)
    
    # Rodapé
    st.markdown("---")
    st.markdown(f"**Atualizado em:** {data['last_update'].strftime('%d/%m/%Y às %H:%M:%S')}")

if __name__ == "__main__":
    main()