import streamlit as st
from datetime import datetime
from enum import Enum

# ============================================================================
# 1. DESIGN TOKENS — CSS Custom Properties
# ============================================================================

DESIGN_TOKENS_CSS = """
<style>
:root {
    /* Background Colors */
    --bg-base: #060a12;
    --bg-surface: #0d1420;
    --bg-surface-raised: #121a2b;
    --border-subtle: #1e293b;
    
    /* Accent Colors */
    --accent-primary: #00e5ff;
    --accent-primary-dim: rgba(0, 229, 255, 0.35);
    --accent-secondary: #8b5cf6;
    --accent-secondary-dim: rgba(139, 92, 246, 0.35);
    
    /* Text Colors */
    --text-primary: #e6edf3;
    --text-secondary: #8b98a9;
    --text-muted: #56637a;
    
    /* Status Colors */
    --status-aberto: #ff3864;
    --status-atendimento: #ffb020;
    --status-aguardando: #38bdf8;
    --status-resolvido: #39ff88;
    --status-sla-estourado: #ff3864;
}

/* ======== Google Fonts Import ======== */
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap');

/* ======== Global Styles ======== */
html, body, .stApp {
    background-color: var(--bg-base);
    color: var(--text-primary);
}

* {
    font-family: 'Inter', sans-serif;
}

h1, h2, h3, .stMarkdown h1, .stMarkdown h2, .stMarkdown h3 {
    font-family: 'Space Grotesk', sans-serif;
    font-weight: 600;
}

/* ======== Sidebar ======== */
[data-testid="stSidebar"] {
    background-color: var(--bg-surface);
}

[data-testid="stSidebar"] [data-testid="stElementContainer"] > div:first-child {
    padding-bottom: 16px;
    border-bottom: 1px solid var(--border-subtle);
    margin-bottom: 16px;
}

.sidebar-header {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 16px;
    font-weight: 700;
    color: var(--accent-primary);
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 12px 0;
}

/* ======== Buttons ======== */
.stButton button {
    border-radius: 6px;
    font-weight: 500;
    transition: all 180ms ease;
}

.stButton button:first-child {
    background-color: var(--accent-primary);
    color: var(--bg-base);
    border: 1px solid var(--accent-primary);
}

.stButton button:first-child:hover {
    box-shadow: 0 0 20px -4px var(--accent-primary-dim),
                0 0 40px -8px var(--accent-primary-dim);
    transform: translateY(-2px);
}

/* Secondary button style (outline) */
.stButton .secondary-btn button {
    background-color: transparent;
    border: 1px solid var(--border-subtle);
    color: var(--text-secondary);
}

.stButton .secondary-btn button:hover {
    border-color: var(--accent-primary);
    color: var(--accent-primary);
}

/* ======== Inputs & Text Areas ======== */
input, textarea, [data-baseweb="input"] {
    background-color: var(--bg-surface-raised) !important;
    border-color: var(--border-subtle) !important;
    color: var(--text-primary) !important;
    border-radius: 6px !important;
}

input:focus, textarea:focus {
    border-color: var(--accent-primary) !important;
    outline: none !important;
}

/* ======== Metrics ======== */
div[data-testid="stMetric"] {
    background: var(--bg-surface);
    border: 1px solid var(--border-subtle);
    padding: 16px;
    border-radius: 10px;
    transition: all 180ms ease;
}

/* Métrica com valor "bom" — glow verde */
div[data-testid="stMetric"].metric-good {
    border-color: var(--status-resolvido);
    box-shadow: 0 0 20px -8px var(--status-resolvido);
}

/* Métrica com valor "ruim" — glow vermelho */
div[data-testid="stMetric"].metric-bad {
    border-color: var(--status-sla-estourado);
    box-shadow: 0 0 20px -8px var(--status-sla-estourado);
}

/* ======== Tabs ======== */
[data-baseweb="tab-list"] {
    gap: 4px;
}

[data-baseweb="tab"] {
    background-color: transparent;
    border-radius: 20px;
    border: 1px solid transparent;
    color: var(--text-secondary);
    font-weight: 500;
    padding: 8px 16px;
    transition: all 180ms ease;
}

[data-baseweb="tab"][aria-selected="true"] {
    background-color: var(--bg-surface-raised);
    color: var(--accent-primary);
    border-color: var(--accent-primary);
}

[data-baseweb="tab"]:hover {
    color: var(--text-primary);
}

/* ======== Expandable Container (Expander) ======== */
[data-testid="stExpander"] {
    background-color: var(--bg-surface);
    border: 1px solid var(--border-subtle);
    border-radius: 10px;
}

/* ======== Cards com Hover Interativo ======== */
.ticket-card {
    background: var(--bg-surface);
    border: 1px solid var(--border-subtle);
    border-radius: 10px;
    padding: 16px;
    cursor: pointer;
    transition: transform 180ms cubic-bezier(.2, .8, .2, 1),
                box-shadow 180ms ease,
                border-color 180ms ease;
    display: flex;
    flex-direction: column;
    gap: 12px;
}

.ticket-card:hover {
    transform: scale(1.03);
    border-color: var(--accent-primary);
    box-shadow: 0 0 0 1px var(--accent-primary),
                0 8px 24px -4px var(--accent-primary-dim),
                0 0 40px -8px var(--accent-primary-dim);
}

.ticket-card:focus-visible {
    outline: 2px solid var(--accent-primary);
    outline-offset: 2px;
}

@media (prefers-reduced-motion: reduce) {
    .ticket-card {
        transition: border-color 180ms ease, box-shadow 180ms ease;
    }
    .ticket-card:hover {
        transform: none;
    }
}

/* Card Header */
.ticket-card-header {
    display: flex;
    align-items: center;
    gap: 12px;
    flex-wrap: wrap;
}

.ticket-id {
    font-family: 'JetBrains Mono', monospace;
    font-weight: 500;
    font-size: 14px;
    color: var(--text-primary);
}

.status-ping {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    flex-shrink: 0;
}

/* Priority Badge */
.badge-priority {
    font-size: 11px;
    font-weight: 600;
    padding: 4px 8px;
    border-radius: 4px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

.badge-priority-baixa {
    background-color: rgba(139, 92, 246, 0.2);
    color: #c4b5fd;
}

.badge-priority-media {
    background-color: rgba(139, 92, 246, 0.3);
    color: #d8b4fe;
}

.badge-priority-alta {
    background-color: rgba(255, 176, 32, 0.3);
    color: #fcd34d;
}

.badge-priority-critica {
    background-color: rgba(255, 56, 100, 0.3);
    color: #ff9ecb;
}

/* Module Badge */
.badge-module {
    font-family: 'JetBrains Mono', monospace;
    font-size: 11px;
    font-weight: 500;
    padding: 4px 8px;
    background-color: var(--bg-surface-raised);
    border: 1px solid var(--border-subtle);
    border-radius: 6px;
    color: var(--text-secondary);
}

/* Description */
.ticket-description {
    font-size: 13px;
    color: var(--text-secondary);
    line-height: 1.4;
    display: -webkit-box;
    -webkit-box-orient: vertical;
    -webkit-line-clamp: 2;
    overflow: hidden;
}

/* Card Footer */
.ticket-card-footer {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 12px;
    color: var(--text-muted);
    margin-top: 8px;
    padding-top: 12px;
    border-top: 1px solid var(--border-subtle);
}

/* ======== Badges de Origem ======== */
.badge-ia {
    background-color: var(--accent-secondary-dim);
    color: #d8b4fe;
    padding: 4px 8px;
    border-radius: 4px;
    font-size: 11px;
    font-weight: 600;
}

.badge-base-conhecimento {
    background-color: rgba(139, 92, 246, 0.15);
    color: #bfb1d6;
    padding: 4px 8px;
    border-radius: 4px;
    font-size: 11px;
    font-weight: 600;
}
button[data-key^="select_ticket_"] {
    display: none !important;
}

.badge-manual {
    background-color: rgba(139, 92, 246, 0.1);
    color: #9f9cc0;
    padding: 4px 8px;
    border-radius: 4px;
    font-size: 11px;
    font-weight: 600;
}

/* ======== Login Hero ======== */
.login-container {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    min-height: 60vh;
    gap: 32px;
}

.login-header {
    text-align: center;
    gap: 12px;
    display: flex;
    flex-direction: column;
}

.login-header h1 {
    font-size: 32px;
    color: var(--text-primary);
    margin: 0;
}

.login-header p {
    font-size: 14px;
    color: var(--text-secondary);
    max-width: 400px;
}

.login-form-card {
    background: var(--bg-surface);
    border: 1px solid var(--border-subtle);
    border-radius: 10px;
    padding: 24px;
    width: 100%;
    max-width: 360px;
    box-shadow: 0 0 40px -8px var(--accent-primary-dim);
}

/* ======== Empty States ======== */
.empty-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    min-height: 400px;
    gap: 16px;
    color: var(--text-secondary);
    text-align: center;
}

.empty-state-icon {
    font-size: 48px;
    opacity: 0.6;
}

.empty-state-title {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 18px;
    font-weight: 600;
    color: var(--text-primary);
}

.empty-state-text {
    font-size: 14px;
    color: var(--text-secondary);
    max-width: 300px;
}

/* ======== Status Colors for Badges ======== */
.status-badge {
    padding: 6px 12px;
    border-radius: 4px;
    font-weight: 600;
    font-size: 12px;
    display: inline-block;
}

.status-aberto {
    background-color: rgba(255, 56, 100, 0.2);
    color: #ff9ecb;
}

.status-atendimento {
    background-color: rgba(255, 176, 32, 0.2);
    color: #fcd34d;
}

.status-aguardando {
    background-color: rgba(56, 189, 248, 0.2);
    color: #7dd3fc;
}

.status-resolvido {
    background-color: rgba(57, 255, 136, 0.2);
    color: #86efac;
}

/* ======== Toast Notifications ======== */
.toast-success {
    background-color: rgba(57, 255, 136, 0.15);
    border-left: 3px solid var(--status-resolvido);
}

.toast-error {
    background-color: rgba(255, 56, 100, 0.15);
    border-left: 3px solid var(--status-sla-estourado);
}

.toast-info {
    background-color: var(--accent-primary-dim);
    border-left: 3px solid var(--accent-primary);
}
</style>
"""

# ============================================================================
# 2. STATUS & PRIORITY ENUMS + CONFIGURATION
# ============================================================================

class StatusChamado(str, Enum):
    ABERTO = "Aberto"
    ATENDIMENTO = "Em Atendimento"
    AGUARDANDO = "Aguardando"
    RESOLVIDO = "Resolvido"

class PrioridadeChamado(str, Enum):
    BAIXA = "Baixa"
    MEDIA = "Média"
    ALTA = "Alta"
    CRITICA = "Crítica"

# Mapeamento de status para cores CSS
STATUS_COLORS = {
    StatusChamado.ABERTO: "var(--status-aberto)",
    StatusChamado.ATENDIMENTO: "var(--status-atendimento)",
    StatusChamado.AGUARDANDO: "var(--status-aguardando)",
    StatusChamado.RESOLVIDO: "var(--status-resolvido)",
}

# ============================================================================
# 3. COMPONENTES REUTILIZÁVEIS
# ============================================================================

def renderizar_status_ping(status: str) -> str:
    """
    Renderiza um ponto de status com halo de glow e animação de pulso.
    
    Args:
        status: Um dos valores de StatusChamado (Aberto, Em Atendimento, Aguardando, Resolvido)
    
    Returns:
        HTML/CSS do status ping
    """
    # Determinar cor e se deve animar
    cor_status = STATUS_COLORS.get(status, "var(--status-aguardando)")
    animar = status in [StatusChamado.ABERTO, StatusChamado.AGUARDANDO]
    sla_estourado = status == "SLA Estourado"
    
    if sla_estourado:
        cor_status = "var(--status-sla-estourado)"
        animar = True
    
    animacao = "pulse-animation" if animar else ""
    
    css_animacao = """
    @keyframes pulse-animation {
        0%, 100% {
            opacity: 1;
            box-shadow: 0 0 0 0 """ + cor_status + """;
        }
        50% {
            opacity: 0.8;
        }
        100% {
            box-shadow: 0 0 0 8px transparent;
        }
    }
    """ if animar else ""
    
    # Respeitar prefers-reduced-motion
    prefere_sem_animacao = """
    @media (prefers-reduced-motion: reduce) {
        .status-ping.""" + animacao + """ {
            animation: none !important;
        }
    }
    """
    
    html = f"""
    <style>
        {css_animacao}
        {prefere_sem_animacao}
        .status-ping.{animacao} {{
            animation: {animacao} 1.8s infinite;
        }}
    </style>
    <div class="status-ping {animacao}" style="background-color: {cor_status}; box-shadow: 0 0 10px {cor_status};"></div>
    """
    return html


def renderizar_ticket_card(chamado: dict, clicavel: bool = False, callback_id: str = None) -> str:
    """
    Renderiza um card de chamado com todas as informações e hover interativo.
    
    Args:
        chamado: Dicionário com chaves: id, status, prioridade, modulo, descricao, usuario, tempo_relativo
        clicavel: Se True, retorna um link clicável; se False, retorna apenas o card (usa session_state)
        callback_id: ID para usar em query params se clicavel=True
    
    Returns:
        HTML do ticket card
    """
    id_formatado = f"#{chamado.get('id', '0'):05d}"
    status = chamado.get('status', 'Aguardando')
    prioridade = chamado.get('prioridade', 'Média')
    modulo = chamado.get('modulo', 'N/A')
    descricao = chamado.get('descricao', '')[:100]
    usuario = chamado.get('usuario', 'Anônimo')
    tempo_relativo = chamado.get('tempo_relativo', 'agora')
    
    # Classes CSS para prioridade
    prioridade_classe = f"badge-priority-{prioridade.lower()}"
    
    # Status ping HTML (será renderizado inline)
    status_ping_html = renderizar_status_ping(status)
    
    card_html = f"""
    <div class="ticket-card" tabindex="0" role="button">
        <div class="ticket-card-header">
            <span class="ticket-id">{id_formatado}</span>
            {status_ping_html}
            <span class="badge-priority {prioridade_classe}">{prioridade}</span>
        </div>
        <div style="display: flex; gap: 8px; align-items: center;">
            <span class="badge-module">{modulo}</span>
        </div>
        <div class="ticket-description">{descricao}</div>
        <div class="ticket-card-footer">
            <span>{usuario}</span>
            <span>{tempo_relativo}</span>
        </div>
    </div>
    """
    return card_html


def tempo_relativo(dt: datetime) -> str:
    """
    Converte um datetime para uma string de tempo relativo (ex. 'há 3h', 'há 2 dias').
    """
    agora = datetime.now()
    diferenca = agora - dt
    
    segundos = diferenca.total_seconds()
    
    if segundos < 60:
        return "agora"
    elif segundos < 3600:
        minutos = int(segundos / 60)
        return f"há {minutos}min"
    elif segundos < 86400:
        horas = int(segundos / 3600)
        return f"há {horas}h"
    elif segundos < 604800:
        dias = int(segundos / 86400)
        return f"há {dias}d"
    else:
        semanas = int(segundos / 604800)
        return f"há {semanas}sem"


# ============================================================================
# 4. FUNÇÃO DE INICIALIZAÇÃO — APLICAR TEMA
# ============================================================================

def aplicar_tema_dark():
    """Injeta todos os estilos CSS do tema no app Streamlit."""
    st.markdown(DESIGN_TOKENS_CSS, unsafe_allow_html=True)