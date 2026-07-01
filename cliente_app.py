import pandas as pd
import streamlit as st
from datetime import datetime

import backend
import aiengine
from theme import aplicar_tema_dark, tempo_relativo

try:
    from streamlit_autorefresh import st_autorefresh
    HAS_AUTOREFRESH = True
except ImportError:
    HAS_AUTOREFRESH = False


st.set_page_config(
    page_title="Portal do Cliente - Helpdesk SAP",
    page_icon="🎫",
    layout="wide",
)

backend.init_db()
aplicar_tema_dark()

# Sistema de autenticação
if "usuario_autenticado" not in st.session_state:
    st.session_state["usuario_autenticado"] = None
    st.session_state["usuario_id"] = None
    st.session_state["usuario_nome"] = None

def fazer_login(username: str, senha: str):
    usuario = backend.autenticar_usuario(username, senha)
    if usuario:
        if usuario["role"] != backend.ROLE_CLIENTE:
            st.error("Acesso restrito: este usuário não tem permissão de cliente.")
            return
        st.session_state["usuario_autenticado"] = True
        st.session_state["usuario_id"] = usuario["id"]
        st.session_state["usuario_nome"] = usuario["username"]
        st.rerun()
    else:
        st.error("Usuário ou senha incorretos.")

def fazer_registro(username: str, senha: str, confirmar_senha: str):
    if senha != confirmar_senha:
        st.error("Senhas não conferem.")
        return
    
    try:
        backend.registrar_usuario(username, senha, role=backend.ROLE_CLIENTE)
        st.success("Usuário registrado com sucesso! Faça login agora.")
    except Exception as e:
        st.error(str(e))

def fazer_logout():
    st.session_state["usuario_autenticado"] = None
    st.session_state["usuario_id"] = None
    st.session_state["usuario_nome"] = None
    st.rerun()

# Se não estiver autenticado, mostra tela de login/registro
if not st.session_state["usuario_autenticado"]:
    st.markdown("""
    <div class="login-container">
        <div class="login-header">
            <h1>🎫 Portal do Cliente</h1>
            <p>Helpdesk SAP com Inteligência Artificial — Abra chamados e acompanhe soluções</p>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    tab_login, tab_registro = st.tabs(["Login", "Registrar"])
    
    col_form = st.columns([1, 2, 1])[1]  # Centraliza
    
    with col_form:
        with tab_login:
            st.markdown('<div class="login-form-card">', unsafe_allow_html=True)
            st.subheader("Fazer login", anchor=False)
            
            username = st.text_input("Usuário", key="login_username")
            senha = st.text_input("Senha", type="password", key="login_senha")
            
            if st.button("Entrar no portal", use_container_width=True):
                if username and senha:
                    fazer_login(username, senha)
                else:
                    st.error("Preencha todos os campos.")
            
            st.markdown('</div>', unsafe_allow_html=True)
        
        with tab_registro:
            st.markdown('<div class="login-form-card">', unsafe_allow_html=True)
            st.subheader("Criar nova conta", anchor=False)
            
            novo_username = st.text_input("Usuário", key="registro_username")
            nova_senha = st.text_input("Senha", type="password", key="registro_senha")
            confirmar = st.text_input("Confirmar senha", type="password", key="registro_confirmar")
            
            if st.button("Registrar", use_container_width=True):
                if novo_username and nova_senha and confirmar:
                    fazer_registro(novo_username, nova_senha, confirmar)
                else:
                    st.error("Preencha todos os campos.")
            
            st.markdown('</div>', unsafe_allow_html=True)
    
    st.stop()

# Se chegou aqui, está autenticado
st.title("Portal do Cliente — Helpdesk SAP")

with st.sidebar:
    # Header da sidebar com marca
    st.markdown("""
    <div class="sidebar-header">
        🎫 Helpdesk SAP
    </div>
    """, unsafe_allow_html=True)
    st.divider()
    
    st.subheader(f"👤 {st.session_state['usuario_nome']}")
    
    # Exibe número de notificações não lidas
    notif_nao_lidas = backend.contar_notificacoes_nao_lidas(st.session_state["usuario_id"])
    if notif_nao_lidas > 0:
        st.metric("🔔 Notificações", notif_nao_lidas)
    
    if st.button("Sair", key="logout_btn"):
        fazer_logout()

aba_novo, aba_meus, aba_notif = st.tabs(["Abrir chamado", "Meus chamados", "🔔 Notificações"])

with aba_novo:
    st.subheader("Abrir novo chamado")

    with st.form("form_novo_chamado_cliente", clear_on_submit=True):
        modulo = st.selectbox(
            "Módulo SAP",
            ["FI", "CO", "MM", "SD", "PP", "QM", "PM", "HCM", "BASIS", "ABAP", "Outro"],
        )
        prioridade = st.selectbox("Prioridade", ["Baixa", "Média", "Alta", "Crítica"], index=1)
        descricao = st.text_area("Descreva o problema com o máximo de detalhes", height=160)
        acionar_ia = st.checkbox("Tentar resolução automática com IA agora", value=True)

        enviado = st.form_submit_button("Abrir chamado")

    if enviado:
        try:
            ticket_id = backend.criar_chamado(
                usuario_id=st.session_state["usuario_id"],
                modulo_sap=modulo,
                descricao=descricao,
                prioridade=prioridade,
            )

            st.success(f"Chamado #{ticket_id} aberto com sucesso.")

            # [NOVO R4] Valida prioridade escolhida pelo cliente
            with st.spinner("Validando prioridade..."):
                resultado_prioridade = aiengine.sugerir_prioridade(
                    descricao_chamado=descricao,
                    modulo_sap=modulo,
                    prioridade_cliente=prioridade,
                )
            
            if resultado_prioridade and resultado_prioridade["diverge"]:
                st.warning(
                    f"⚠️ **Atenção**: A IA sugeriu prioridade **{resultado_prioridade['sugestao']}** "
                    f"(você escolheu **{prioridade}**). "
                    f"Motivo: {resultado_prioridade['justificativa']}\n\n"
                    f"A equipe de SAP foi notificada desta divergência."
                )
                # Notifica a equipe
                backend.notificar_equipe_sobre_divergencia_prioridade(
                    ticket_id=ticket_id,
                    prioridade_cliente=prioridade,
                    prioridade_sugerida=resultado_prioridade["sugestao"],
                    justificativa=resultado_prioridade["justificativa"],
                )

            if acionar_ia:
                with st.spinner("Analisando chamado..."):
                    # [NOVO R5] Obter sugestão da IA sem resolver logo
                    solucao = aiengine.resolver_ticket_com_ia(ticket_id)
                    
                    # Determina origem da solução para registrar corretamente
                    if "[Solução cadastrada encontrada]" in solucao:
                        origem = backend.ORIGEM_KB
                        tipo_origem = "✓ Solução idêntica encontrada na base de conhecimento"
                    elif "[Solução similar encontrada" in solucao:
                        origem = backend.ORIGEM_KB
                        import re
                        match = re.search(r'confiança: (\d+)%', solucao)
                        confianca = match.group(1) if match else "?"
                        tipo_origem = f"≈ Solução similar encontrada (confiança: {confianca}%)"
                    else:
                        origem = backend.ORIGEM_IA
                        tipo_origem = "🤖 Solução gerada por inteligência artificial"
                    
                    # Grava a solução com status "Aguardando confirmação"
                    backend.atualizar_status_chamado(ticket_id, backend.STATUS_AGUARDANDO_CONFIRMACAO)
                    backend.resolver_chamado(
                        ticket_id=ticket_id,
                        solucao=solucao,
                        origem_solucao=origem,
                        fechar_chamado=False,  # [NOVO R5] Não fecha ainda
                    )
                
                st.info(solucao)
                st.caption(tipo_origem)
                
                # [NOVO R5] Botões de confirmação do cliente
                st.write("**Essa solução resolveu seu problema?**")
                col_sim, col_nao = st.columns(2)
                
                with col_sim:
                    if st.button("✓ Sim, resolveu!", key=f"confirm_{ticket_id}", use_container_width=True):
                        try:
                            aiengine.aplicar_sugestao_ia(ticket_id, confirmou=True)
                            st.success("Chamado fechado como resolvido! Obrigado por usar o SAP Helpdesk.")
                            st.rerun()
                        except Exception as e:
                            st.error(str(e))
                
                with col_nao:
                    if st.button("✗ Não, preciso da equipe", key=f"reject_{ticket_id}", use_container_width=True):
                        try:
                            aiengine.aplicar_sugestao_ia(ticket_id, confirmou=False)
                            st.warning("Chamado retornou para a fila. A equipe SAP em breve entrará em contato.")
                            st.rerun()
                        except Exception as e:
                            st.error(str(e))
            else:
                st.caption("Acompanhe o andamento na aba 'Meus chamados'.")

        except Exception as erro:
            st.error(str(erro))

with aba_meus:
    st.subheader("Meus chamados")

    col_status, col_refresh = st.columns([4, 1])

    with col_status:
        status_opcoes = [
            "Todos",
            backend.STATUS_ABERTO,
            backend.STATUS_EM_ATENDIMENTO,
            backend.STATUS_RESOLVIDO,
        ]
        status_filtro = st.selectbox("Status", status_opcoes)

    with col_refresh:
        st.write("")
        st.write("")
        if st.button("🔄 Atualizar"):
            st.rerun()

    if HAS_AUTOREFRESH:
        st_autorefresh(interval=15000, key="refresh_meus_chamados")

    filtro = None if status_filtro == "Todos" else status_filtro
    chamados = backend.listar_chamados_por_usuario(st.session_state["usuario_id"], filtro)

    if not chamados:
        st.markdown("""
        <div class="empty-state">
            <div class="empty-state-icon">📭</div>
            <div class="empty-state-title">Nenhum chamado encontrado</div>
            <div class="empty-state-text">Você ainda não tem chamados nessa situação. Abra um novo na aba "Abrir chamado"</div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("### 📋 Selecione um chamado para ver os detalhes")
        
        # Lista de seleção
        ids_disponiveis = [c["id"] for c in chamados]
        ticket_selecionado = st.selectbox(
            "Ver detalhes do chamado",
            ids_disponiveis,
            format_func=lambda x: f"#{x:05d} — {next((c['status'] for c in chamados if c['id'] == x), 'N/A')}"
        )
        
        chamado = backend.obter_chamado(int(ticket_selecionado))

        if chamado:
            st.subheader(f"Detalhes do Chamado #{ticket_selecionado}")
            
            # SUB-TABS para organizar conteúdo
            tab_visao, tab_conversa, tab_anexos = st.tabs(["Visão Geral", "💬 Conversa", "📎 Anexos"])
            
            # ========== ABA: VISÃO GERAL ==========
            with tab_visao:
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Status", chamado['status'])
                with col2:
                    st.metric("Prioridade", chamado['prioridade'])
                with col3:
                    st.metric("Módulo", chamado['modulo_sap'])
                
                st.subheader("Descrição")
                st.write(chamado['descricao'])

                if chamado.get("solucao_aplicada"):
                    st.divider()
                    st.subheader("✅ Solução Proposta")
                    st.info(chamado["solucao_aplicada"])
                    
                    # Exibe origem da solução
                    origem = chamado.get('origem_solucao', '-')
                    if origem == "IA":
                        st.markdown("""
                        <div class="badge-ia">🤖 Solução gerada por Inteligência Artificial</div>
                        """, unsafe_allow_html=True)
                    elif origem == "Base de Conhecimento":
                        st.markdown("""
                        <div class="badge-base-conhecimento">📚 Solução encontrada na Base de Conhecimento</div>
                        """, unsafe_allow_html=True)
                    else:
                        st.markdown("""
                        <div class="badge-manual">👤 Solução aplicada pela equipe SAP</div>
                        """, unsafe_allow_html=True)
                else:
                    st.divider()
                    st.info("⏳ Aguardando análise da equipe SAP...")
            
            # ========== ABA: CONVERSA ==========
            with tab_conversa:
                st.subheader("Histórico de Interações")
                
                # [NOVO R7] Seção de interações/comentários
                interacoes = backend.listar_interacoes(int(ticket_selecionado))
                
                if not interacoes:
                    st.markdown("""
                    <div class="empty-state">
                        <div class="empty-state-icon">💬</div>
                        <div class="empty-state-title">Nenhuma mensagem</div>
                        <div class="empty-state-text">Seja o primeiro a comentar neste chamado</div>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    for inter in interacoes:
                        # Determina cor/emoji baseado no role
                        if inter["role"] == backend.ROLE_EQUIPE:
                            emoji = "👨‍💼"
                            label = f"{emoji} Equipe: {inter['username']}"
                        else:
                            emoji = "👤"
                            label = f"{emoji} Você ({inter['username']})"
                        
                        with st.container(border=True):
                            st.markdown(f"**{label}** · {inter['data_criacao']}")
                            st.write(inter["mensagem"])
                
                st.divider()
                st.subheader("Adicionar mensagem")
                
                with st.form(f"form_mensagem_cliente_{int(ticket_selecionado)}"):
                    nova_msg = st.text_area(
                        "Sua mensagem",
                        height=80,
                        placeholder="Digite aqui...",
                        key=f"msg_cliente_{int(ticket_selecionado)}"
                    )
                    btn_enviar = st.form_submit_button("Enviar mensagem", use_container_width=True)
                
                if btn_enviar:
                    try:
                        backend.criar_interacao(
                            ticket_id=int(ticket_selecionado),
                            usuario_id=st.session_state["usuario_id"],
                            mensagem=nova_msg
                        )
                        st.toast("✓ Mensagem enviada!", icon="✅")
                        st.rerun()
                    except Exception as erro:
                        st.error(f"Erro: {str(erro)}")
            
            # ========== ABA: ANEXOS ==========
            with tab_anexos:
                st.subheader("Anexos")
                
                # Listar anexos existentes
                anexos = backend.listar_anexos(int(ticket_selecionado))
                
                if not anexos:
                    st.markdown("""
                    <div class="empty-state">
                        <div class="empty-state-icon">📁</div>
                        <div class="empty-state-title">Nenhum anexo</div>
                        <div class="empty-state-text">Adicione anexos para compartilhar informações com a equipe</div>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.write(f"**Total de anexos:** {len(anexos)}")
                    for anexo in anexos:
                        with st.container(border=True):
                            col_info, col_acao = st.columns([4, 1])
                            
                            with col_info:
                                tamanho_formatado = backend.formatar_tamanho_bytes(anexo.get("tamanho_bytes", 0))
                                st.write(f"📄 **{anexo['nome_arquivo']}** ({tamanho_formatado})")
                                st.caption(f"Enviado por {anexo['username']} em {anexo['data_upload']}")
                            
                            with col_acao:
                                # Botão para download
                                try:
                                    with open(anexo["caminho_arquivo"], "rb") as f:
                                        conteudo = f.read()
                                        st.download_button(
                                            label="⬇️",
                                            data=conteudo,
                                            file_name=anexo["nome_arquivo"],
                                            mime=anexo.get("tipo_mime", "application/octet-stream"),
                                            key=f"download_{anexo['id']}",
                                            use_container_width=True
                                        )
                                except Exception as e:
                                    st.error(f"Arquivo não encontrado: {e}")
                
                st.divider()
                st.subheader("Adicionar anexo")
                
                with st.form(f"form_anexo_cliente_{int(ticket_selecionado)}"):
                    arquivo_upload = st.file_uploader(
                        "Selecione um arquivo",
                        type=["jpg", "jpeg", "png", "pdf", "doc", "docx", "xls", "xlsx", "txt"],
                        key=f"upload_cliente_{int(ticket_selecionado)}"
                    )
                    
                    btn_upload = st.form_submit_button("📤 Enviar anexo", use_container_width=True)
                
                if btn_upload and arquivo_upload:
                    try:
                        anexo_id = backend.salvar_anexo(
                            ticket_id=int(ticket_selecionado),
                            usuario_id=st.session_state["usuario_id"],
                            arquivo_stream=arquivo_upload,
                            nome_arquivo=arquivo_upload.name,
                            tipo_mime=arquivo_upload.type
                        )
                        st.toast(f"✓ Anexo '{arquivo_upload.name}' enviado!", icon="✅")
                        st.rerun()
                    except Exception as erro:
                        st.error(f"Erro ao enviar anexo: {str(erro)}")


with aba_notif:
    st.subheader("Notificações")
    
    col_refresh_notif, col_limpar = st.columns([4, 1])
    
    with col_refresh_notif:
        if st.button("🔄 Atualizar notificações", key="refresh_notif"):
            st.rerun()
    
    with col_limpar:
        pass
    
    notificacoes = backend.listar_notificacoes(st.session_state["usuario_id"])
    
    if not notificacoes:
        st.markdown("""
        <div class="empty-state">
            <div class="empty-state-icon">🔔</div>
            <div class="empty-state-title">Nenhuma notificação</div>
            <div class="empty-state-text">Você está em dia com todas as notificações</div>
        </div>
        """, unsafe_allow_html=True)
    else:
        for notif in notificacoes:
            with st.container(border=True):
                col_msg, col_acao = st.columns([5, 1])
                
                with col_msg:
                    status_leitura = "✓ Lida" if notif["lida"] else "● Não lida"
                    st.write(f"**{notif['tipo'].replace('_', ' ').title()}** — {status_leitura}")
                    st.write(notif["mensagem"])
                    st.caption(f"Chamado #{notif['ticket_id']} • {notif['data_criacao']}")
                
                with col_acao:
                    if not notif["lida"]:
                        if st.button("Marcar como lida", key=f"mark_read_{notif['id']}", use_container_width=True):
                            backend.marcar_notificacao_como_lida(notif["id"])
                            st.rerun()
