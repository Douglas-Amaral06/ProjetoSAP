import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
import backend

# Carrega as variáveis do arquivo .env para o sistema
load_dotenv()

DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

PRIORIDADES_VALIDAS = ["Baixa", "Média", "Alta", "Crítica"]
MAPA_PRIORIDADE = {
    "baixa": "Baixa",
    "media": "Média",
    "média": "Média",
    "alta": "Alta",
    "critica": "Crítica",
    "crítica": "Crítica",
}


def obter_llm():
    """Inicializa o motor do Gemini via LangChain."""
    # O LangChain vai buscar automaticamente a GOOGLE_API_KEY que o load_dotenv carregou
    return ChatGoogleGenerativeAI(
        model=DEFAULT_MODEL,
        temperature=0.2,
        max_tokens=None,
        timeout=None,
        max_retries=2,
    )


def montar_normas_modelo() -> str:
    normas = backend.listar_normas_modelo()

    if not normas:
        return (
            "Siga melhores práticas SAP, seja objetivo, não invente transações "
            "e entregue uma solução técnica aplicável."
        )

    return "\n".join(
        f"- {norma['titulo']}: {norma['conteudo']}"
        for norma in normas
    )


def sugerir_prioridade(descricao_chamado: str, modulo_sap: str, prioridade_cliente: str) -> dict | None:
    """
    [NOVO R4] IA sugere uma prioridade baseada na descrição do problema.
    
    Retorna dict:
    {
        "sugestao": str (uma das PRIORIDADES_VALIDAS),
        "diverge": bool (True se diferente da prioridade_cliente),
        "justificativa": str (motivo da sugestão)
    }
    
    Retorna None se houver erro na IA.
    """
    try:
        llm = obter_llm()
        
        prompt_template = ChatPromptTemplate.from_messages([
            ("system", """
Você é um classificador de severidade para incidentes SAP.

Sua função é analisar a descrição do problema e retornar uma sugestão de prioridade:
- Baixa: problemas cosméticos, sem impacto operacional
- Média: problemas que afetam um usuário ou um processo secundário
- Alta: problemas que afetam múltiplos usuários ou um processo crítico
- Crítica: sistema fora, perda de dados, impacto em negócio

Responda em JSON com a seguinte estrutura (sem markdown, apenas JSON puro):
{{
    "prioridade": "Baixa|Média|Alta|Crítica",
    "justificativa": "Breve justificativa da sugestão"
}}
"""),
            ("human", """
Módulo SAP: {modulo}
Descrição do problema: {descricao}
Prioridade escolhida pelo cliente: {prioridade_cliente}

Qual a prioridade que você sugeriria?
"""),
        ])
        
        chain = prompt_template | llm
        resposta = chain.invoke({
            "modulo": modulo_sap.strip().upper(),
            "descricao": descricao_chamado.strip(),
            "prioridade_cliente": prioridade_cliente.strip(),
        })
        
        import json
        try:
            content = resposta.content.strip()
            
            # Remove markdown code blocks se existirem
            if content.startswith("```"):
                # Remove ```json ou ``` no início
                content = content.split("\n", 1)[1] if "\n" in content else content
            if content.endswith("```"):
                # Remove ``` no final
                content = content.rsplit("\n", 1)[0] if "\n" in content else content
            
            resultado = json.loads(content)
            prioridade_sugerida = resultado.get("prioridade", "Média")
            justificativa = resultado.get("justificativa", "")
            
            # Normaliza prioridade sugerida
            prioridade_sugerida_norm = MAPA_PRIORIDADE.get(
                prioridade_sugerida.lower(), 
                "Média"
            )
            
            diverge = prioridade_sugerida_norm.lower() != prioridade_cliente.lower()
            
            return {
                "sugestao": prioridade_sugerida_norm,
                "diverge": diverge,
                "justificativa": justificativa,
            }
        except json.JSONDecodeError:
            # Se não conseguir fazer parse, retorna None (não vai gerar alerta)
            print(f"Aviso: resposta da IA não é JSON válido: {resposta.content}")
            return None
    
    except Exception as e:
        print(f"Erro ao sugerir prioridade: {e}")
        return None


def analisar_e_resolver_chamado(descricao_chamado: str, modulo_sap: str) -> str:
    backend.init_db()

    # Passo 1: Tenta match exato na KB
    solucao_existente = backend.buscar_solucao_exata_kb(descricao_chamado)
    if solucao_existente:
        return f"[Solução cadastrada encontrada]\n{solucao_existente}"

    # Passo 2: Tenta busca semântica
    resultado_similar = backend.buscar_solucao_similar_kb(descricao_chamado)
    if resultado_similar:
        confianca_pct = int(resultado_similar["confianca"] * 100)
        return f"[Solução similar encontrada - confiança: {confianca_pct}%]\n{resultado_similar['solucao']}"

    # Passo 3: Se não encontrou, chama a IA
    llm = obter_llm()

    system_instruction = """
Você é um especialista de suporte avançado para sistemas SAP.

Sua função é analisar o problema relatado pelo usuário e trazer uma solução clara,
objetiva e alinhada às normas internas e melhores práticas SAP.

Regras:
- Não invente transações.
- Não assuma dados ausentes como fato.
- Seja direto na resolução técnica.
- Quando necessário, indique validação humana.
- Responda em português do Brasil.

Normas internas do modelo:
{normas}
"""

    prompt_template = ChatPromptTemplate.from_messages([
        ("system", system_instruction),
        (
            "human",
            """
Módulo SAP afetado: {modulo}

Descrição do incidente:
{incidente}

Estruture a resposta em:
1. Diagnóstico provável
2. Passos recomendados
3. Validações necessárias
4. Quando escalar para um consultor SAP
"""
        ),
    ])

    chain = prompt_template | llm

    resposta = chain.invoke({
        "normas": montar_normas_modelo(),
        "modulo": modulo_sap.strip().upper(),
        "incidente": descricao_chamado.strip(),
    })

    solucao_gerada = resposta.content.strip()

    backend.salvar_solucao_na_kb(
        problema=descricao_chamado,
        solucao=solucao_gerada,
        modulo_sap=modulo_sap,
    )

    return solucao_gerada


def resolver_ticket_com_ia(ticket_id: int) -> str:
    """
    Busca os dados do ticket no backend, passa para o Gemini
    e retorna a string com a solução, já persistindo o resultado.
    
    **[MODIFICADO R5]** Para cliente: só retorna sugestão, não fecha.
    Para equipe: fecha direto (behavior anterior).
    Usa contexto interno para decidir (TODO: refatorar com parametro).
    """
    backend.init_db()

    chamado = backend.obter_chamado(ticket_id)

    if not chamado:
        raise ValueError("Chamado não encontrado.")

    solucao = analisar_e_resolver_chamado(
        descricao_chamado=chamado["descricao"],
        modulo_sap=chamado["modulo_sap"],
    )

    if solucao.startswith("[Solução cadastrada encontrada]"):
        origem = backend.ORIGEM_KB
    elif solucao.startswith("[Solução similar encontrada"):
        origem = backend.ORIGEM_KB  # Similar também é da KB
    else:
        origem = backend.ORIGEM_IA

    # **[NOVO R5]** Só resolve se status for diferente de "Aguardando confirmação"
    # Se for cliente (status = Aguardando confirmação), apenas retorna
    # Se for equipe, resolve direto
    if chamado["status"] != backend.STATUS_AGUARDANDO_CONFIRMACAO:
        # Comportamento anterior (equipe)
        backend.resolver_chamado(
            ticket_id=ticket_id,
            solucao=solucao,
            origem_solucao=origem,
        )
    
    return solucao


def aplicar_sugestao_ia(ticket_id: int, confirmou: bool) -> None:
    """
    **[NOVO R5]** Cliente confirma ou rejeita a sugestão da IA.
    
    - confirmou=True: fecha chamado como Resolvido
    - confirmou=False: volta para Aberto (fila da equipe)
    """
    backend.init_db()
    
    chamado = backend.obter_chamado(ticket_id)
    if not chamado:
        raise ValueError("Chamado não encontrado.")
    
    if not chamado.get("solucao_aplicada"):
        raise ValueError("Sem solução para confirmar/rejeitar.")
    
    if confirmou:
        # Fecha como resolvido
        backend.atualizar_status_chamado(ticket_id, backend.STATUS_RESOLVIDO)
    else:
        # Volta para a fila (Aberto)
        backend.atualizar_status_chamado(ticket_id, backend.STATUS_ABERTO)