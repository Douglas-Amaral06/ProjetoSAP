import pandas as pd
import streamlit as st
import json
from datetime import datetime

import backend
import aiengine
from theme import aplicar_tema_dark, tempo_relativo, STATUS_COLORS

try:
    from streamlit_autorefresh import st_autorefresh
    HAS_AUTOREFRESH = True
except ImportError:
    HAS_AUTOREFRESH = False


st.set_page_config(
    page_title="Painel da Equipe SAP",
    page_icon="🛠️",
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
        if usuario["role"] != backend.ROLE_EQUIPE:
            st.error("Acesso restrito: este usuário não tem permissão de equipe.")
            return
        st.session_state["usuario_autenticado"] = True
        st.session_state["usuario_id"] = usuario["id"]
        st.session_state["usuario_nome"] = usuario["username"]
        st.rerun()
    else:
        st.error("Usuário ou senha incorretos.")

def fazer_logout():
    st.session_state["usuario_autenticado"] = None
    st.session_state["usuario_id"] = None
    st.session_state["usuario_nome"] = None
    st.rerun()

# Se não estiver autenticado, mostra tela de login
if not st.session_state["usuario_autenticado"]:
    st.markdown("""
    <div class="login-container">
        <div class="login-header">
            <h1>🛠️ Painel da Equipe</h1>
            <p>Helpdesk SAP com Inteligência Artificial — Gerencie chamados com eficiência</p>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    col_login = st.columns([1, 2, 1])[1]  # Centraliza o formulário
    
    with col_login:
        st.markdown('<div class="login-form-card">', unsafe_allow_html=True)
        
        username = st.text_input("Usuário", key="login_username")
        senha = st.text_input("Senha", type="password", key="login_senha")
        
        if st.button("Entrar no portal", use_container_width=True):
            if username and senha:
                fazer_login(username, senha)
            else:
                st.error("Preencha todos os campos.")
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    st.divider()
    st.info("Entre em contato com um administrador para criar sua conta de equipe.")
    st.stop()

# Se chegou aqui, está autenticado
st.title("Painel da Equipe — Helpdesk SAP")

with st.sidebar:
    # Header da sidebar com marca
    st.markdown("""
    <div class="sidebar-header">
        🛠️ Helpdesk SAP
    </div>
    """, unsafe_allow_html=True)
    st.divider()
    
    st.subheader(f"🔧 {st.session_state['usuario_nome']}")
    if st.button("Sair", key="logout_btn"):
        fazer_logout()

aba_fila, aba_kb, aba_normas, aba_alertas, aba_sla, aba_ml = st.tabs([
    "Fila",
    "Base de conhecimento",
    "Normas da IA",
    "🚨 Alertas",  # [NOVO R4]
    "SLA",
    "🤖 ML",  # [NOVO R11]
])

with aba_fila:
    st.subheader("Fila de chamados")

    col_status, col_refresh = st.columns([4, 1])

    with col_status:
        status_opcoes = [
            "Todos",
            backend.STATUS_ABERTO,
            backend.STATUS_EM_ATENDIMENTO,
            backend.STATUS_AGUARDANDO_CONFIRMACAO,  # [NOVO R5]
            backend.STATUS_RESOLVIDO,
        ]
        status_filtro = st.selectbox("Status", status_opcoes)

    with col_refresh:
        st.write("")
        st.write("")
        if st.button("🔄 Atualizar"):
            st.rerun()

    if HAS_AUTOREFRESH:
        st_autorefresh(interval=15000, key="refresh_fila")

    filtro = None if status_filtro == "Todos" else status_filtro
    chamados = backend.listar_chamados(filtro)

    if not chamados:
        st.markdown("""
        <div class="empty-state">
            <div class="empty-state-icon">📭</div>
            <div class="empty-state-title">Nenhum chamado encontrado</div>
            <div class="empty-state-text">Parece que a fila está vazia. Tudo resolvido! 🎉</div>
        </div>
        """, unsafe_allow_html=True)
    else:
        # [NOVO R8] Grid de cards clicáveis para seleção de chamado
        st.markdown("### 📋 Clique em um chamado para selecionar")
        
        # Inicializa session state para chamado selecionado
        if "chamado_selecionado_r8" not in st.session_state:
            st.session_state["chamado_selecionado_r8"] = None
        
        # Cria grid de cards (3 colunas)
        cols = st.columns(3)
        
        for idx, chamado in enumerate(chamados):
            col_idx = idx % 3
            
            with cols[col_idx]:
                # Calcula tempo relativo do chamado
                try:
                    dt_criacao = datetime.strptime(chamado.get("data_criacao", ""), "%Y-%m-%d %H:%M:%S")
                    tempo_rel = tempo_relativo(dt_criacao)
                except:
                    tempo_rel = "agora"
                
                # Mapeia dados para o dicionário esperado pelo renderizador
                card_data = {
                    'id': chamado['id'],
                    'status': chamado['status'],
                    'prioridade': chamado['prioridade'],
                    'modulo': chamado['modulo_sap'],
                    'descricao': chamado['descricao'],
                    'usuario': chamado.get('usuario', 'N/A'),
                    'tempo_relativo': tempo_rel
                }
                
                # Renderiza card customizado
                card_html = f"""
                <div class="ticket-card" onclick="document.querySelector('[data-testid=\\\"stElementContainer\\\"] button[data-key=\\\"select_ticket_{chamado['id']}\\\"]')?.click()" style="cursor: pointer;">
                    <div class="ticket-card-header">
                        <span class="ticket-id">#{chamado['id']:05d}</span>
                        <span class="status-ping" style="background-color: var(--status-{chamado['status'].lower().replace(' ', '-')}); box-shadow: 0 0 10px var(--status-{chamado['status'].lower().replace(' ', '-')});"></span>
                        <span class="badge-priority badge-priority-{chamado['prioridade'].lower()}">{chamado['prioridade']}</span>
                    </div>
                    <div style="display: flex; gap: 8px; align-items: center;">
                        <span class="badge-module">{chamado['modulo_sap']}</span>
                    </div>
                    <div class="ticket-description">{chamado['descricao'][:100]}</div>
                    <div class="ticket-card-footer">
                        <span>{chamado.get('usuario', 'N/A')}</span>
                        <span>{tempo_rel}</span>
                    </div>
                </div>
                """
                
                st.markdown(card_html, unsafe_allow_html=True)
                
                # Botão invisível para seleção (mantém a lógica de session state)
                if st.button(
                    f"Selecionar #{chamado['id']}",
                    key=f"select_ticket_{chamado['id']}",
                    use_container_width=True,
                ):
                    st.session_state["chamado_selecionado_r8"] = chamado["id"]
                    st.rerun()

        # Mostra o chamado selecionado
        if st.session_state["chamado_selecionado_r8"]:
            ticket_id = st.session_state["chamado_selecionado_r8"]
            chamado_selecionado = backend.obter_chamado(ticket_id)
            
            if chamado_selecionado:
                st.success(f"✓ Chamado #{ticket_id} selecionado")
                
                st.subheader(f"Detalhes do Chamado #{ticket_id}")
                
                # SUB-TABS para organizar melhor o conteúdo
                tab_visao_geral, tab_conversa, tab_anexos = st.tabs(["Visão Geral", "💬 Conversa", "📎 Anexos"])
                
                # ========== ABA: VISÃO GERAL ==========
                with tab_visao_geral:
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Status", chamado_selecionado["status"])
                    with col2:
                        st.metric("Prioridade", chamado_selecionado["prioridade"])
                    with col3:
                        st.metric("Módulo", chamado_selecionado["modulo_sap"])
                    
                    st.write(f"**Descrição:**\n{chamado_selecionado['descricao']}")
                    
                    if chamado_selecionado.get("solucao_aplicada"):
                        st.divider()
                        st.subheader("✅ Solução Aplicada")
                        st.info(f"{chamado_selecionado['solucao_aplicada']}")
                        
                        # Determina e exibe a origem da solução
                        origem = chamado_selecionado.get("origem_solucao", backend.ORIGEM_MANUAL)
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
                            <div class="badge-manual">👤 Solução aplicada manualmente</div>
                            """, unsafe_allow_html=True)
                    
                    st.divider()
                    st.subheader("Ações")
                    
                    col_status_acao, col_ia = st.columns(2)

                    with col_status_acao:
                        novo_status = st.selectbox(
                            "Novo status",
                            [backend.STATUS_ABERTO, backend.STATUS_EM_ATENDIMENTO, backend.STATUS_AGUARDANDO_CONFIRMACAO],
                            key="novo_status_r8",
                        )

                        if st.button("Atualizar status", key="btn_atualizar_status_r8", use_container_width=True):
                            try:
                                backend.atualizar_status_chamado(ticket_id, novo_status)
                                st.success("Status atualizado.")
                                st.session_state["chamado_selecionado_r8"] = None
                                st.rerun()
                            except Exception as erro:
                                st.error(str(erro))

                    with col_ia:
                        if st.button("Resolver com IA", key="btn_resolver_ia_r8", use_container_width=True):
                            try:
                                with st.spinner("Analisando chamado..."):
                                    solucao = aiengine.resolver_ticket_com_ia(ticket_id)

                                st.success("Chamado resolvido.")
                                st.info(solucao)
                                
                                # Determina e exibe a origem da solução
                                if "[Solução cadastrada encontrada]" in solucao:
                                    st.markdown("""
                                    <div class="badge-base-conhecimento">✓ Solução idêntica encontrada na base de conhecimento</div>
                                    """, unsafe_allow_html=True)
                                elif "[Solução similar encontrada" in solucao:
                                    # Extrai a confiança da solução
                                    import re
                                    match = re.search(r'confiança: (\d+)%', solucao)
                                    confianca = match.group(1) if match else "?"
                                    st.markdown(f"""
                                    <div class="badge-base-conhecimento">≈ Solução similar encontrada (confiança: {confianca}%)</div>
                                    """, unsafe_allow_html=True)
                                else:
                                    st.markdown("""
                                    <div class="badge-ia">🤖 Solução gerada por inteligência artificial</div>
                                    """, unsafe_allow_html=True)
                                
                                st.session_state["chamado_selecionado_r8"] = None
                                st.rerun()

                            except Exception as erro:
                                st.error(str(erro))

                    with st.expander("Resolver manualmente", expanded=False):
                        solucao_manual = st.text_area("Solução aplicada", key="solucao_manual_r8")

                        if st.button("Salvar resolução manual", key="btn_resolver_manual_r8", use_container_width=True):
                            try:
                                backend.resolver_chamado(
                                    ticket_id=ticket_id,
                                    solucao=solucao_manual,
                                    origem_solucao=backend.ORIGEM_MANUAL,
                                )

                                chamado = backend.obter_chamado(ticket_id)

                                if chamado:
                                    backend.salvar_solucao_na_kb(
                                        problema=chamado["descricao"],
                                        solucao=solucao_manual,
                                        modulo_sap=chamado["modulo_sap"],
                                    )

                                st.success("Chamado resolvido e solução salva na base de conhecimento.")
                                st.session_state["chamado_selecionado_r8"] = None
                                st.rerun()

                            except Exception as erro:
                                st.error(str(erro))
                
                # ========== ABA: CONVERSA ==========
                with tab_conversa:
                    st.subheader("Histórico de Interações")
                    
                    # [NOVO R7] Seção de interações/comentários
                    interacoes = backend.listar_interacoes(ticket_id)
                    num_interacoes = len(interacoes)
                    st.caption(f"Total de mensagens: {num_interacoes}")
                    
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
                                label = f"{emoji} Cliente: {inter['username']}"
                            
                            with st.container(border=True):
                                st.markdown(f"**{label}** · {inter['data_criacao']}")
                                st.write(inter["mensagem"])
                    
                    st.divider()
                    st.subheader("Adicionar mensagem")
                    
                    with st.form(f"form_mensagem_equipe_{ticket_id}"):
                        nova_msg = st.text_area(
                            "Sua mensagem",
                            height=80,
                            placeholder="Digite aqui...",
                            key=f"msg_equipe_{ticket_id}"
                        )
                        btn_enviar = st.form_submit_button("Enviar mensagem", use_container_width=True)
                    
                    if btn_enviar:
                        try:
                            backend.criar_interacao(
                                ticket_id=ticket_id,
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
                    anexos = backend.listar_anexos(ticket_id)
                    
                    if not anexos:
                        st.markdown("""
                        <div class="empty-state">
                            <div class="empty-state-icon">📁</div>
                            <div class="empty-state-title">Nenhum anexo</div>
                            <div class="empty-state-text">Adicione anexos para compartilhar informações com o cliente</div>
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
                                                key=f"download_eq_{anexo['id']}",
                                                use_container_width=True
                                            )
                                    except Exception as e:
                                        st.error(f"Arquivo não encontrado: {e}")
                    
                    st.divider()
                    st.subheader("Adicionar anexo")
                    
                    with st.form(f"form_anexo_equipe_{ticket_id}"):
                        arquivo_upload = st.file_uploader(
                            "Selecione um arquivo",
                            type=["jpg", "jpeg", "png", "pdf", "doc", "docx", "xls", "xlsx", "txt"],
                            key=f"upload_equipe_{ticket_id}"
                        )
                        
                        btn_upload = st.form_submit_button("📤 Enviar anexo", use_container_width=True)
                    
                    if btn_upload and arquivo_upload:
                        try:
                            anexo_id = backend.salvar_anexo(
                                ticket_id=ticket_id,
                                usuario_id=st.session_state["usuario_id"],
                                arquivo_stream=arquivo_upload,
                                nome_arquivo=arquivo_upload.name,
                                tipo_mime=arquivo_upload.type
                            )
                            st.toast(f"✓ Anexo '{arquivo_upload.name}' enviado!", icon="✅")
                            st.rerun()
                        except Exception as erro:
                            st.error(f"Erro ao enviar anexo: {str(erro)}")
            else:
                st.error("Chamado não encontrado.")
        else:
            st.markdown("""
            <div class="empty-state">
                <div class="empty-state-icon">👆</div>
                <div class="empty-state-title">Selecione um chamado</div>
                <div class="empty-state-text">Clique em um dos cards acima para visualizar os detalhes</div>
            </div>
            """, unsafe_allow_html=True)

with aba_kb:
    st.subheader("Base de conhecimento")
    st.caption("[NOVO R6] Aqui você pode editar, excluir ou gerenciar as soluções armazenadas.")

    registros = backend.listar_base_conhecimento()

    if not registros:
        st.info("Nenhuma solução cadastrada ainda.")
    else:
        # Inicializa session state para edição
        if "kb_editando_id" not in st.session_state:
            st.session_state["kb_editando_id"] = None
        
        # Mostra tabela com informações de ID para seleção
        df_kb = pd.DataFrame(registros)
        st.dataframe(df_kb, use_container_width=True, hide_index=True)
        
        st.divider()
        
        # Seleção de entrada para editar/excluir
        st.subheader("Gerenciar entrada")
        
        ids_disponiveis = df_kb["id"].tolist()
        kb_selecionada = st.selectbox("Selecione uma entrada para editar/excluir", ids_disponiveis, key="kb_select")
        
        entrada_kb = None
        for reg in registros:
            if reg["id"] == kb_selecionada:
                entrada_kb = reg
                break
        
        if entrada_kb:
            st.write(f"**ID:** {entrada_kb['id']}")
            st.write(f"**Problema-chave:** {entrada_kb['problema_chave']}")
            st.write(f"**Módulo:** {entrada_kb.get('modulo_sap', 'N/A')}")
            st.write(f"**Uso:** {entrada_kb['contador_uso']} vezes")
            
            st.write("**Solução atual:**")
            st.info(entrada_kb["solucao_recomendada"])
            
            st.divider()
            
            # Abas para editar ou excluir
            tab_editar, tab_excluir = st.tabs(["✏️ Editar", "🗑️ Excluir"])
            
            with tab_editar:
                st.write("Edite a solução e o módulo SAP associado:")
                
                with st.form(f"form_editar_kb_{kb_selecionada}"):
                    nova_solucao = st.text_area(
                        "Nova solução",
                        value=entrada_kb["solucao_recomendada"],
                        height=150,
                        key=f"nova_solucao_{kb_selecionada}"
                    )
                    novo_modulo = st.text_input(
                        "Módulo SAP (opcional)",
                        value=entrada_kb.get("modulo_sap", ""),
                        key=f"novo_modulo_{kb_selecionada}"
                    )
                    
                    btn_salvar = st.form_submit_button("💾 Salvar alterações", use_container_width=True)
                
                if btn_salvar:
                    try:
                        backend.editar_solucao_kb(
                            kb_id=kb_selecionada,
                            nova_solucao=nova_solucao,
                            novo_modulo_sap=novo_modulo if novo_modulo else None
                        )
                        st.success("✓ Solução atualizada com sucesso!")
                        st.rerun()
                    except Exception as erro:
                        st.error(f"Erro ao atualizar: {str(erro)}")
            
            with tab_excluir:
                st.warning("⚠️ **Atenção:** Esta ação é irreversível!")
                st.write("Ao excluir esta entrada, ela será removida da base de conhecimento permanentemente.")
                st.write(f"**Entrada a excluir:** Problema-chave: `{entrada_kb['problema_chave']}`")
                
                if st.button("🗑️ Confirmar exclusão", use_container_width=True, type="secondary"):
                    try:
                        backend.excluir_entrada_kb(kb_selecionada)
                        st.success("✓ Entrada excluída com sucesso!")
                        st.rerun()
                    except Exception as erro:
                        st.error(f"Erro ao excluir: {str(erro)}")

with aba_normas:
    st.subheader("Normas da IA")
    st.caption("[NOVO R6] Você pode desativar normas (sem perder o histórico) ou adicionar novas.")

    todas_as_normas = backend.listar_todas_as_normas()
    
    if todas_as_normas:
        st.write("**Normas cadastradas:**")
        df_normas = pd.DataFrame(todas_as_normas)
        
        # Exibe com cor diferente as ativas e desativadas
        def colorir_status(row):
            if row["ativo"] == 1:
                return [""] * len(row)  # Sem cor (ativa é o padrão)
            else:
                return ["background-color: #555"] * len(row)  # Cinza para desativadas
        
        st.dataframe(df_normas, use_container_width=True, hide_index=True)
        
        st.divider()
        
        st.subheader("Gerenciar normas")
        
        # Seleção de norma para desativar/reativar
        norma_selecionada = st.selectbox(
            "Selecione uma norma para gerenciar",
            [(n["id"], f"{n['titulo']} {'[DESATIVADA]' if n['ativo'] == 0 else '[ATIVA]'}") for n in todas_as_normas],
            format_func=lambda x: x[1]
        )
        
        norma_id, _ = norma_selecionada
        
        # Encontra a norma selecionada
        norma_atual = None
        for n in todas_as_normas:
            if n["id"] == norma_id:
                norma_atual = n
                break
        
        if norma_atual:
            st.write(f"**Título:** {norma_atual['titulo']}")
            st.write(f"**Status:** {'🟢 Ativa' if norma_atual['ativo'] == 1 else '🔴 Desativada'}")
            st.write(f"**Conteúdo:**")
            st.info(norma_atual["conteudo"])
            
            col_ativa, col_desativa = st.columns(2)
            
            with col_ativa:
                if norma_atual["ativo"] == 0:  # Se está desativada, mostra botão para reativar
                    if st.button("🟢 Reativar norma", use_container_width=True, key="btn_reativar"):
                        try:
                            backend.reativar_norma(norma_id)
                            st.success("✓ Norma reativada!")
                            st.rerun()
                        except Exception as erro:
                            st.error(f"Erro: {str(erro)}")
                else:
                    st.write("")  # Espaço vazio se já está ativa
            
            with col_desativa:
                if norma_atual["ativo"] == 1:  # Se está ativa, mostra botão para desativar
                    if st.button("🔴 Desativar norma", use_container_width=True, key="btn_desativar"):
                        try:
                            backend.desativar_norma(norma_id)
                            st.success("✓ Norma desativada!")
                            st.rerun()
                        except Exception as erro:
                            st.error(f"Erro: {str(erro)}")
                else:
                    st.write("")  # Espaço vazio se já está desativada
    else:
        st.info("Nenhuma norma cadastrada ainda.")
    
    st.divider()
    st.subheader("Adicionar nova norma")
    
    with st.form("form_normas"):
        titulo = st.text_input("Título da norma")
        conteudo = st.text_area("Conteúdo da norma", height=120)
        salvar = st.form_submit_button("Adicionar norma")

    if salvar:
        try:
            backend.salvar_norma_modelo(titulo, conteudo)
            st.success("Norma adicionada.")
            st.rerun()
        except Exception as erro:
            st.error(str(erro))

with aba_alertas:
    st.subheader("🚨 Alertas de Divergência de Prioridade")
    st.caption("[NOVO R4] Aqui aparecem notificações de divergência entre a prioridade escolhida pelo cliente e a sugerida pela IA")
    
    # Busca notificações de divergência de prioridade
    alertas = []
    with backend.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT n.id, n.ticket_id, n.mensagem, n.data_criacao, n.lida, 
                   t.status, t.prioridade
            FROM notificacoes n
            JOIN tickets t ON n.ticket_id = t.id
            WHERE n.tipo = ?
            ORDER BY n.data_criacao DESC
        """, (backend.NOTIF_PRIORIDADE_DIVERGE,))
        alertas = cursor.fetchall()
    
    if not alertas:
        st.info("Nenhum alerta de divergência de prioridade no momento.")
    else:
        for alerta in alertas:
            with st.container(border=True):
                col_info, col_acao = st.columns([5, 1])
                
                with col_info:
                    status_leitura = "✓ Lido" if alerta["lida"] else "● Não lido"
                    st.write(f"**Chamado #{alerta['ticket_id']}** — {status_leitura}")
                    st.write(f"Status: {alerta['status']} | Prioridade atual: {alerta['prioridade']}")
                    st.write(f"📋 {alerta['mensagem']}")
                    st.caption(f"Data: {alerta['data_criacao']}")
                
                with col_acao:
                    if not alerta["lida"]:
                        if st.button("✓ Lido", key=f"mark_alert_{alerta['id']}", use_container_width=True):
                            backend.marcar_notificacao_como_lida(alerta["id"])
                            st.rerun()

with aba_sla:
    st.subheader("Indicadores de SLA")

    df_sla = backend.obter_metricas_sla()

    if df_sla.empty:
        st.info("Sem dados para calcular SLA.")
    else:
        total = len(df_sla)
        abertos = int((df_sla["status"] == backend.STATUS_ABERTO).sum())
        atendimento = int((df_sla["status"] == backend.STATUS_EM_ATENDIMENTO).sum())
        resolvidos = int((df_sla["status"] == backend.STATUS_RESOLVIDO).sum())
        estourados = int((df_sla["status_sla"] == "SLA Estourado").sum())

        col1, col2, col3, col4 = st.columns(4)

        col1.metric("Total", total)
        col2.metric("Abertos", abertos)
        col3.metric("Em atendimento", atendimento)
        col4.metric("SLA estourado", estourados)

        st.metric("Resolvidos", resolvidos)

        st.bar_chart(df_sla["status_sla"].value_counts())
        st.dataframe(df_sla, use_container_width=True, hide_index=True)


with aba_ml:
    st.subheader("🤖 Treinamento de Modelo Próprio")
    st.caption("[NOVO R11] Análise e preparação para treinamento de modelo próprio com Databricks")

    try:
        import databricks_training
        ml_disponivel = True
    except ImportError:
        ml_disponivel = False
        st.warning("⚠️ Módulo de treinamento não disponível. Execute: `pip install psycopg2-binary`")

    if ml_disponivel:
        # Seção 1: Análise de Viabilidade
        st.markdown("### 📊 Análise de Viabilidade")
        
        with st.expander("Analisar custo/benefício do treinamento próprio", expanded=True):
            custo_gemini = st.number_input(
                "Custo estimado por chamada ao Gemini (USD)",
                min_value=0.0001,
                max_value=1.0,
                value=0.0005,
                step=0.0001,
                format="%.4f",
                help="Custo médio por chamada à API do Gemini"
            )
            
            if st.button("🔍 Executar análise de viabilidade", use_container_width=True):
                with st.spinner("Analisando dados históricos..."):
                    try:
                        analise = databricks_training.executar_analise_viabilidade()
                        
                        if analise.get("sucesso", True):
                            st.success("✅ Análise concluída!")
                            
                            # Estatísticas
                            st.markdown("#### 📈 Estatísticas do Histórico")
                            stats = analise.get("estatisticas", {})
                            col1, col2, col3 = st.columns(3)
                            
                            with col1:
                                st.metric("Chamados resolvidos", stats.get("total_chamados_resolvidos", 0))
                                st.metric("Entradas KB", stats.get("total_entradas_kb", 0))
                            
                            with col2:
                                st.metric("Gemini", stats.get("chamados_atendidos_gemini", 0))
                                st.metric("KB", stats.get("chamados_atendidos_kb", 0))
                            
                            with col3:
                                st.metric("% Gemini", stats.get("porcentagem_gemini", "0%"))
                                st.metric("% KB", stats.get("porcentagem_kb", "0%"))
                            
                            # Análise de custo
                            st.markdown("#### 💰 Análise Financeira")
                            custo = analise.get("analise_custo", {})
                            col_c1, col_c2 = st.columns(2)
                            
                            with col_c1:
                                st.metric("Custo histórico Gemini", f"${custo.get('custo_historico_gemini_usd', 0):.2f}")
                                st.metric("Custo treinamento", f"${custo.get('custo_estimado_treinamento_usd', 0):.0f}")
                            
                            with col_c2:
                                st.metric("Economia potencial anual", f"${custo.get('economia_potencial_anual_usd', 0):.2f}")
                                st.metric("ROI estimado", custo.get('roi_estimado', '0%'))
                            
                            # Recomendação
                            st.markdown("#### 🎯 Recomendação")
                            recomendacao = analise.get("recomendacao", {})
                            
                            nivel_cor = {
                                "ALTO": "🟢",
                                "MODERADO": "🟡", 
                                "BAIXO": "🔴"
                            }
                            
                            st.info(f"""
                            **{nivel_cor.get(recomendacao.get('nivel_prioridade', 'MODERADO'), '🟡')} {recomendacao.get('nivel_prioridade', 'MODERADO')}**
                            
                            {recomendacao.get('recomendacao', '')}
                            
                            *{recomendacao.get('justificativa', '')}*
                            """)
                            
                            # Ações recomendadas
                            st.markdown("##### 📋 Ações Recomendadas")
                            for acao in recomendacao.get("acoes_recomendadas", []):
                                st.write(f"- {acao}")
                            
                            # Botão para exportar dados se recomendado
                            if recomendacao.get("nivel_prioridade") == "ALTO":
                                st.divider()
                                st.markdown("##### 📤 Preparar Dados para Treinamento")
                                st.write("Baseado na análise, recomenda-se iniciar POC.")
                                
                                formato = st.selectbox(
                                    "Formato do dataset",
                                    ["jsonl", "csv", "parquet"],
                                    index=0,
                                    help="JSON Lines é recomendado para ML"
                                )
                                
                                if st.button("🚀 Exportar Dataset para Treinamento", type="primary", use_container_width=True):
                                    with st.spinner("Exportando dados..."):
                                        try:
                                            resultado = databricks_training.exportar_para_treinamento()
                                            if resultado.get("export", {}).get("sucesso"):
                                                st.success("✅ Dataset exportado com sucesso!")
                                                
                                                export_info = resultado["export"]
                                                st.download_button(
                                                    label="📥 Baixar Relatório Completo",
                                                    data=json.dumps(resultado, indent=2, ensure_ascii=False),
                                                    file_name=f"analise_treinamento_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                                                    mime="application/json",
                                                    use_container_width=True
                                                )
                                                
                                                st.markdown("**Arquivos gerados:**")
                                                for tipo, caminho in export_info.get("caminhos", {}).items():
                                                    st.code(caminho)
                                            
                                            else:
                                                st.error(f"❌ Erro na exportação: {export_info.get('erro', 'Desconhecido')}")
                                        
                                        except Exception as e:
                                            st.error(f"Erro ao exportar: {str(e)}")
                        else:
                            st.error(f"❌ Erro na análise: {analise.get('erro', 'Desconhecido')}")
                    
                    except Exception as e:
                        st.error(f"Erro na análise: {str(e)}")
        
        # Seção 2: Configuração do Ambiente
        st.markdown("### ⚙️ Configuração do Ambiente")
        
        with st.expander("Configurar integração com Databricks/MLflow"):
            st.markdown("""
            #### Pré-requisitos
            
            1. **Conta Databricks** ativa
            2. **Cluster** configurado com GPU (recomendado)
            3. **MLflow Tracking Server** acessível
            4. **Credenciais** de API armazenadas no `.env`
            
            #### Configuração no `.env`
            ```env
            # Configurações Databricks
            DATABRICKS_HOST=https://dbc-xxxxxx.cloud.databricks.com
            DATABRICKS_TOKEN=seu_token_aqui
            MLFLOW_TRACKING_URI=http://localhost:5000
            ```
            
            #### Testar Conexão
            """)
            
            if st.button("🔌 Testar Configuração", use_container_width=True):
                st.info("Em produção, implementar teste de conexão com Databricks API")
        
        # Seção 3: Monitoramento
        st.markdown("### 📈 Monitoramento e Métricas")
        
        col_m1, col_m2, col_m3 = st.columns(3)
        
        with col_m1:
            st.metric("Chamados/mês", "—", delta=None)
            st.caption("Volume para análise")
        
        with col_m2:
            st.metric("Acerto Gemini", "—", delta=None)
            st.caption("Qualidade atual")
        
        with col_m3:
            st.metric("Custo/mês", "—", delta=None)
            st.caption("Despesa com IA")
        
        st.markdown("""
        #### Métricas de Avaliação Recomendadas
        
        | Métrica | Alvo | Descrição |
        |---------|------|-----------|
        | **BLEU** | >0.4 | Similaridade com soluções humanas |
        | **ROUGE-L** | >0.5 | Recall de informações importantes |
        | **Precision@1** | >0.7 | Solução correta no top 1 |
        | **Latência** | <2s | Tempo de resposta do modelo |
        | **Custo/chamada** | <$0.001 | Custo operacional |
        """)
    
    else:
        st.error("""
        ⚠️ **Módulo de treinamento não disponível**
        
        Para habilitar esta funcionalidade:
        
        1. Instale as dependências adicionais:
        ```bash
        pip install psycopg2-binary
        ```
        
        2. Configure o ambiente Databricks/MLflow no arquivo `.env`
        
        3. Certifique-se de ter dados históricos suficientes (>100 chamados resolvidos)
        """)
        
        # Botão para instalação guiada
        if st.button("📋 Mostrar Guia de Instalação Completo", use_container_width=True):
            st.markdown("""
            ### Guia de Instalação para Treinamento de Modelo
            
            #### 1. Dependências Python
            ```bash
            pip install psycopg2-binary
            pip install transformers torch
            pip install mlflow
            pip install scikit-learn pandas numpy
            ```
            
            #### 2. Configuração do Banco de Dados
            - PostgreSQL configurado (ver `postgres_setup.md`)
            - Tabelas criadas e populadas
            - Conexão testada
            
            #### 3. Ambiente Databricks
            - Cluster com GPU para treinamento
            - Workspace configurado
            - Permissões de API
            
            #### 4. Pipeline de Dados
            - Exportação automatizada
            - Pré-processamento
            - Validação de qualidade
            
            #### 5. Monitoramento
            - Métricas definidas
            - Alertas configurados
            - Dashboard de acompanhamento
            """)