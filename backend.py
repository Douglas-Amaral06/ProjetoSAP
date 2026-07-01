import os
import sqlite3
from datetime import datetime
from pathlib import Path
import boto3
from uuid import uuid4

S3_BUCKET = os.getenv("AWS_S3_BUCKET")
s3_client = boto3.client(
    's3',
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    region_name=os.getenv("AWS_DEFAULT_REGION", "us-east-1")
)

import pandas as pd
import numpy as np
from werkzeug.security import generate_password_hash, check_password_hash

# Imports condicionais para PostgreSQL (só carrega se necessário)
_db_type = os.getenv("DB_TYPE", "sqlite").lower()
if _db_type == "postgres":
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
    except ImportError:
        psycopg2 = None
        RealDictCursor = None


# Configurações de banco de dados
DB_TYPE = os.getenv("DB_TYPE", "sqlite").lower()  # sqlite ou postgres
DB_NAME = os.getenv("SAP_HELPDESK_DB", str(Path(__file__).with_name("sap_chamados.db")))

# Configurações PostgreSQL
PG_HOST = os.getenv("PG_HOST", "localhost")
PG_PORT = os.getenv("PG_PORT", "5432")
PG_DB = os.getenv("PG_DB", "sap_helpdesk")
PG_USER = os.getenv("PG_USER", "postgres")
PG_PASSWORD = os.getenv("PG_PASSWORD", "")

STATUS_ABERTO = "Aberto"
STATUS_EM_ATENDIMENTO = "Em Atendimento"
STATUS_AGUARDANDO_CONFIRMACAO = "Aguardando confirmação"  # [NOVO R5]
STATUS_RESOLVIDO = "Resolvido"

ORIGEM_IA = "IA"
ORIGEM_KB = "Base de Conhecimento"
ORIGEM_MANUAL = "Manual"

ROLE_CLIENTE = "cliente"
ROLE_EQUIPE = "equipe"

NOTIF_RESOLVIDO = "chamado_resolvido"
NOTIF_ATENDIMENTO = "em_atendimento"
NOTIF_REABERTO = "reaberto"
NOTIF_PRIORIDADE_DIVERGE = "prioridade_diverge"  # [NOVO R4]

# Configurações de busca semântica
SIMILARIDADE_THRESHOLD = 0.7  # Threshold mínimo para considerar uma solução similar
MODELO_EMBEDDING = "all-MiniLM-L6-v2"  # Modelo rápido e leve


def dict_factory(cursor, row):
    return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}


def get_connection():
    """[NOVO R9] Conexão com suporte a SQLite e PostgreSQL."""
    if DB_TYPE == "postgres":
        # Conexão PostgreSQL
        conn = psycopg2.connect(
            host=PG_HOST,
            port=PG_PORT,
            database=PG_DB,
            user=PG_USER,
            password=PG_PASSWORD,
            cursor_factory=RealDictCursor
        )
        # PostgreSQL já tem melhor suporte a concorrência
        return conn
    else:
        # Conexão SQLite (compatibilidade)
        conn = sqlite3.connect(DB_NAME, timeout=10)
        conn.row_factory = dict_factory
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        return conn


def coluna_existe(cursor, tabela: str, coluna: str) -> bool:
    """[NOVO R9] Verifica se coluna existe, compatível com SQLite e PostgreSQL."""
    if DB_TYPE == "postgres":
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = %s AND column_name = %s
        """, (tabela, coluna))
        return cursor.fetchone() is not None
    else:
        cursor.execute(f"PRAGMA table_info({tabela})")
    return any(campo["name"] == coluna for campo in cursor.fetchall())


def init_db():
    """[NOVO R9] Inicialização do banco com suporte a SQLite e PostgreSQL."""
    with get_connection() as conn:
        cursor = conn.cursor()

        # Determinar o tipo de auto increment
        auto_increment = "SERIAL PRIMARY KEY" if DB_TYPE == "postgres" else "INTEGER PRIMARY KEY AUTOINCREMENT"
        
        # Determinar o tipo de data/hora
        datetime_type = "TIMESTAMP" if DB_TYPE == "postgres" else "DATETIME"
        current_timestamp = "CURRENT_TIMESTAMP"

        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS usuarios (
                id {auto_increment},
                username TEXT UNIQUE NOT NULL,
                senha_hash TEXT NOT NULL,
                role TEXT NOT NULL,
                data_criacao {datetime_type} NOT NULL DEFAULT {current_timestamp}
            )
        """)

        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS tickets (
                id {auto_increment},
                usuario_id INTEGER NOT NULL,
                modulo_sap TEXT NOT NULL,
                descricao TEXT NOT NULL,
                prioridade TEXT NOT NULL DEFAULT 'Média',
                status TEXT NOT NULL DEFAULT 'Aberto',
                data_criacao {datetime_type} NOT NULL DEFAULT {current_timestamp},
                data_resolucao {datetime_type},
                prazo_limite {datetime_type} NOT NULL,
                solucao_aplicada TEXT,
                origem_solucao TEXT,
                FOREIGN KEY(usuario_id) REFERENCES usuarios(id)
            )
        """)

        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS knowledge_base (
                id {auto_increment},
                problema_chave TEXT UNIQUE NOT NULL,
                solucao_recomendada TEXT NOT NULL,
                modulo_sap TEXT,
                contador_uso INTEGER NOT NULL DEFAULT 1,
                data_registro {datetime_type} NOT NULL DEFAULT {current_timestamp},
                data_atualizacao {datetime_type} NOT NULL DEFAULT {current_timestamp},
                embedding BYTEA
            )
        """)

        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS model_norms (
                id {auto_increment},
                titulo TEXT NOT NULL,
                conteudo TEXT NOT NULL,
                ativo INTEGER NOT NULL DEFAULT 1,
                data_registro {datetime_type} NOT NULL DEFAULT {current_timestamp}
            )
        """)

        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS notificacoes (
                id {auto_increment},
                usuario_id INTEGER NOT NULL,
                ticket_id INTEGER NOT NULL,
                tipo TEXT NOT NULL,
                mensagem TEXT NOT NULL,
                lida INTEGER NOT NULL DEFAULT 0,
                data_criacao {datetime_type} NOT NULL DEFAULT {current_timestamp},
                FOREIGN KEY(usuario_id) REFERENCES usuarios(id),
                FOREIGN KEY(ticket_id) REFERENCES tickets(id)
            )
        """)

        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS ticket_interacoes (
                id {auto_increment},
                ticket_id INTEGER NOT NULL,
                usuario_id INTEGER NOT NULL,
                mensagem TEXT NOT NULL,
                data_criacao {datetime_type} NOT NULL DEFAULT {current_timestamp},
                FOREIGN KEY(ticket_id) REFERENCES tickets(id),
                FOREIGN KEY(usuario_id) REFERENCES usuarios(id)
            )
        """)

        # [NOVO R10] Tabela para anexos
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS ticket_anexos (
                id {auto_increment},
                ticket_id INTEGER NOT NULL,
                usuario_id INTEGER NOT NULL,
                nome_arquivo TEXT NOT NULL,
                caminho_arquivo TEXT NOT NULL,
                tipo_mime TEXT,
                tamanho_bytes INTEGER,
                data_upload {datetime_type} NOT NULL DEFAULT {current_timestamp},
                FOREIGN KEY(ticket_id) REFERENCES tickets(id),
                FOREIGN KEY(usuario_id) REFERENCES usuarios(id)
            )
        """)

        if not coluna_existe(cursor, "tickets", "prioridade"):
            cursor.execute("ALTER TABLE tickets ADD COLUMN prioridade TEXT NOT NULL DEFAULT 'Média'")

        if not coluna_existe(cursor, "tickets", "origem_solucao"):
            cursor.execute("ALTER TABLE tickets ADD COLUMN origem_solucao TEXT")

        if not coluna_existe(cursor, "knowledge_base", "embedding"):
            cursor.execute("ALTER TABLE knowledge_base ADD COLUMN embedding BLOB")

        if not coluna_existe(cursor, "knowledge_base", "ativo"):
            cursor.execute("ALTER TABLE knowledge_base ADD COLUMN ativo INTEGER NOT NULL DEFAULT 1")

        # Migração de tickets antigos (campo "usuario" texto para "usuario_id" FK)
        if coluna_existe(cursor, "tickets", "usuario"):
            if not coluna_existe(cursor, "tickets", "usuario_id"):
                # Cria coluna temporária
                cursor.execute("ALTER TABLE tickets ADD COLUMN usuario_id INTEGER")
                
                # Para cada ticket antigo com "usuario" preenchido, cria/vincula um usuário
                cursor.execute("SELECT DISTINCT usuario FROM tickets WHERE usuario IS NOT NULL")
                usuarios_antigos = cursor.fetchall()
                
                for row in usuarios_antigos:
                    usuario_nome = row["usuario"]
                    # Cria usuário automático com role "cliente" e senha padrão
                    cursor.execute("""
                        INSERT OR IGNORE INTO usuarios (username, senha_hash, role)
                        VALUES (?, ?, ?)
                    """, (usuario_nome, generate_password_hash("changeme"), ROLE_CLIENTE))
                    
                    # Busca o ID do usuário criado
                    cursor.execute("SELECT id FROM usuarios WHERE username = ?", (usuario_nome,))
                    usuario_id = cursor.fetchone()["id"]
                    
                    # Atualiza tickets
                    cursor.execute("UPDATE tickets SET usuario_id = ? WHERE usuario = ?", (usuario_id, usuario_nome))
                
                # Remove coluna "usuario" antiga
                # SQLite não suporta DROP COLUMN diretamente, então criamos uma nova tabela
                cursor.execute("PRAGMA foreign_keys=OFF")
                
                cursor.execute("""
                    CREATE TABLE tickets_new (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        usuario_id INTEGER NOT NULL,
                        modulo_sap TEXT NOT NULL,
                        descricao TEXT NOT NULL,
                        prioridade TEXT NOT NULL DEFAULT 'Média',
                        status TEXT NOT NULL DEFAULT 'Aberto',
                        data_criacao DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        data_resolucao DATETIME,
                        prazo_limite DATETIME NOT NULL,
                        solucao_aplicada TEXT,
                        origem_solucao TEXT,
                        FOREIGN KEY(usuario_id) REFERENCES usuarios(id)
                    )
                """)
                
                cursor.execute("""
                    INSERT INTO tickets_new (id, usuario_id, modulo_sap, descricao, prioridade, status, 
                                            data_criacao, data_resolucao, prazo_limite, solucao_aplicada, origem_solucao)
                    SELECT id, usuario_id, modulo_sap, descricao, prioridade, status,
                           data_criacao, data_resolucao, prazo_limite, solucao_aplicada, origem_solucao
                    FROM tickets
                """)
                
                cursor.execute("DROP TABLE tickets")
                cursor.execute("ALTER TABLE tickets_new RENAME TO tickets")
                cursor.execute("PRAGMA foreign_keys=ON")

        cursor.execute("""
            INSERT INTO model_norms (titulo, conteudo)
            SELECT
                'Padrão inicial de atendimento SAP',
                'Analise o incidente pelo módulo informado, priorize melhores práticas SAP, não invente transações e apresente passos objetivos de resolução.'
            WHERE NOT EXISTS (SELECT 1 FROM model_norms)
        """)


def normalizar_texto(texto: str) -> str:
    return " ".join((texto or "").strip().lower().split())


def validar_texto(valor: str, campo: str):
    if not valor or not valor.strip():
        raise ValueError(f"{campo} é obrigatório.")


def calcular_horas_sla(prioridade: str) -> int:
    mapa = {
        "baixa": 72,
        "média": 24,
        "media": 24,
        "alta": 8,
        "crítica": 4,
        "critica": 4,
    }
    return mapa.get(normalizar_texto(prioridade), 24)


def registrar_usuario(username: str, senha: str, role: str = ROLE_CLIENTE) -> int:
    """Registra um novo usuário com senha hasheada."""
    validar_texto(username, "Usuário")
    validar_texto(senha, "Senha")
    
    if role not in {ROLE_CLIENTE, ROLE_EQUIPE}:
        raise ValueError("Role inválido (use 'cliente' ou 'equipe').")
    
    if len(senha) < 6:
        raise ValueError("Senha deve ter pelo menos 6 caracteres.")
    
    senha_hash = generate_password_hash(senha)
    
    with get_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO usuarios (username, senha_hash, role)
                VALUES (?, ?, ?)
            """, (username.strip().lower(), senha_hash, role))
            return cursor.lastrowid
        except sqlite3.IntegrityError:
            raise ValueError("Usuário já existe.")


def autenticar_usuario(username: str, senha: str) -> dict | None:
    """Autentica um usuário e retorna seus dados (id, username, role) ou None."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, username, role
            FROM usuarios
            WHERE username = ?
        """, (username.strip().lower(),))
        
        usuario = cursor.fetchone()
        
        if not usuario:
            return None
        
        # Busca o hash de senha
        cursor.execute("SELECT senha_hash FROM usuarios WHERE id = ?", (usuario["id"],))
        resultado = cursor.fetchone()
        
        if resultado and check_password_hash(resultado["senha_hash"], senha):
            return usuario
        
        return None


def obter_usuario_por_id(usuario_id: int) -> dict | None:
    """Busca um usuário pelo ID."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, username, role FROM usuarios WHERE id = ?", (usuario_id,))
        return cursor.fetchone()


def enviar_notificacao(usuario_id: int, ticket_id: int, tipo: str, mensagem: str) -> int:
    """Cria uma notificação para o usuário. Retorna o ID da notificação."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO notificacoes (usuario_id, ticket_id, tipo, mensagem)
            VALUES (?, ?, ?, ?)
        """, (usuario_id, ticket_id, tipo, mensagem))
        return cursor.lastrowid


def listar_notificacoes(usuario_id: int, apenas_nao_lidas: bool = False) -> list[dict]:
    """Lista notificações de um usuário."""
    with get_connection() as conn:
        cursor = conn.cursor()
        
        if apenas_nao_lidas:
            cursor.execute("""
                SELECT *
                FROM notificacoes
                WHERE usuario_id = ? AND lida = 0
                ORDER BY data_criacao DESC
            """, (usuario_id,))
        else:
            cursor.execute("""
                SELECT *
                FROM notificacoes
                WHERE usuario_id = ?
                ORDER BY data_criacao DESC
            """, (usuario_id,))
        
        return cursor.fetchall()


def marcar_notificacao_como_lida(notificacao_id: int):
    """Marca uma notificação como lida."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE notificacoes
            SET lida = 1
            WHERE id = ?
        """, (notificacao_id,))


def contar_notificacoes_nao_lidas(usuario_id: int) -> int:
    """Conta quantas notificações não lidas o usuário tem."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) as total
            FROM notificacoes
            WHERE usuario_id = ? AND lida = 0
        """, (usuario_id,))
        resultado = cursor.fetchone()
        return resultado["total"] if resultado else 0


def notificar_equipe_sobre_divergencia_prioridade(ticket_id: int, prioridade_cliente: str, prioridade_sugerida: str, justificativa: str):
    """[NOVO R4] Notifica TODOS os usuários da equipe sobre divergência de prioridade.
    
    Busca todos os usuários com role='equipe' e cria uma notificação para cada um.
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Busca todos os usuários da equipe
        cursor.execute("""
            SELECT id FROM usuarios WHERE role = ?
        """, (ROLE_EQUIPE,))
        
        usuarios_equipe = cursor.fetchall()
        
        for usuario in usuarios_equipe:
            mensagem = (
                f"Divergência de prioridade no chamado #{ticket_id}: "
                f"cliente escolheu '{prioridade_cliente}', "
                f"mas IA sugeriu '{prioridade_sugerida}'. "
                f"Motivo: {justificativa}"
            )
            
            cursor.execute("""
                INSERT INTO notificacoes (usuario_id, ticket_id, tipo, mensagem)
                VALUES (?, ?, ?, ?)
            """, (
                usuario["id"],
                ticket_id,
                NOTIF_PRIORIDADE_DIVERGE,
                mensagem
            ))


# Cache global do modelo de embedding (evita recarregar múltiplas vezes)
_modelo_embedding = None

def obter_modelo_embedding():
    """Obtém o modelo de embedding (lazy load)."""
    global _modelo_embedding
    if _modelo_embedding is None:
        from sentence_transformers import SentenceTransformer
        _modelo_embedding = SentenceTransformer(MODELO_EMBEDDING)
    return _modelo_embedding


def gerar_embedding(texto: str) -> bytes:
    """Gera embedding (vetor) para um texto e retorna como bytes."""
    modelo = obter_modelo_embedding()
    embedding = modelo.encode(texto, convert_to_numpy=True)
    return embedding.astype(np.float32).tobytes()


def embedding_para_array(embedding_bytes: bytes) -> np.ndarray:
    """Converte bytes de embedding de volta para array numpy."""
    if not embedding_bytes:
        return None
    return np.frombuffer(embedding_bytes, dtype=np.float32)


def calcular_similaridade(embedding1: np.ndarray, embedding2: np.ndarray) -> float:
    """Calcula similaridade cosseno entre dois embeddings."""
    if embedding1 is None or embedding2 is None:
        return 0.0
    
    # Normaliza os vetores
    norm1 = embedding1 / (np.linalg.norm(embedding1) + 1e-8)
    norm2 = embedding2 / (np.linalg.norm(embedding2) + 1e-8)
    
    # Produto escalar (similaridade cosseno)
    return float(np.dot(norm1, norm2))


def criar_chamado(usuario_id: int, modulo_sap: str, descricao: str, prioridade: str = "Média") -> int:
    validar_texto(modulo_sap, "Módulo SAP")
    validar_texto(descricao, "Descrição")

    # Valida se o usuário existe
    usuario = obter_usuario_por_id(usuario_id)
    if not usuario:
        raise ValueError("Usuário não encontrado.")

    horas_sla = calcular_horas_sla(prioridade)
    prazo = pd.Timestamp.now() + pd.Timedelta(hours=horas_sla)
    prazo_str = prazo.strftime("%Y-%m-%d %H:%M:%S")

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO tickets (
                usuario_id,
                modulo_sap,
                descricao,
                prioridade,
                prazo_limite
            )
            VALUES (?, ?, ?, ?, ?)
        """, (
            usuario_id,
            modulo_sap.strip().upper(),
            descricao.strip(),
            prioridade.strip(),
            prazo_str,
        ))

        return cursor.lastrowid


def obter_chamado(ticket_id: int) -> dict | None:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,))
        return cursor.fetchone()


def listar_chamados(status_filtro: str | None = None) -> list[dict]:
    with get_connection() as conn:
        cursor = conn.cursor()

        if status_filtro:
            cursor.execute("""
                SELECT *
                FROM tickets
                WHERE status = ?
                ORDER BY data_criacao DESC
            """, (status_filtro,))
        else:
            cursor.execute("""
                SELECT *
                FROM tickets
                ORDER BY data_criacao DESC
            """)

        return cursor.fetchall()


def listar_chamados_por_usuario(usuario_id: int, status_filtro: str | None = None) -> list[dict]:
    """Usado pela interface do cliente para mostrar apenas os próprios chamados."""
    with get_connection() as conn:
        cursor = conn.cursor()

        if status_filtro:
            cursor.execute("""
                SELECT *
                FROM tickets
                WHERE usuario_id = ? AND status = ?
                ORDER BY data_criacao DESC
            """, (usuario_id, status_filtro))
        else:
            cursor.execute("""
                SELECT *
                FROM tickets
                WHERE usuario_id = ?
                ORDER BY data_criacao DESC
            """, (usuario_id,))

        return cursor.fetchall()


def atualizar_status_chamado(ticket_id: int, status: str):
    status_validos = {STATUS_ABERTO, STATUS_EM_ATENDIMENTO, STATUS_AGUARDANDO_CONFIRMACAO, STATUS_RESOLVIDO}

    if status not in status_validos:
        raise ValueError("Status inválido.")

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE tickets
            SET status = ?
            WHERE id = ?
        """, (status, ticket_id))

        if cursor.rowcount == 0:
            raise ValueError("Chamado não encontrado.")


def resolver_chamado(ticket_id: int, solucao: str, origem_solucao: str = ORIGEM_MANUAL, fechar_chamado: bool = True):
    """
    Registra a solução de um chamado.
    
    **[MODIFICADO R5]** Agora aceita parâmetro `fechar_chamado`:
    - True (padrão): fecha como Resolvido (comportamento anterior)
    - False: apenas registra solução, mantém status (para R5 - cliente confirma depois)
    
    Args:
        ticket_id: ID do chamado
        solucao: Descrição da solução
        origem_solucao: Origem da solução (IA, KB, Manual)
        fechar_chamado: Se True, fecha como Resolvido; se False, apenas registra
    """
    validar_texto(solucao, "Solução")

    data_atual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Busca o chamado antes de atualizar
        cursor.execute("SELECT usuario_id, status FROM tickets WHERE id = ?", (ticket_id,))
        resultado = cursor.fetchone()
        
        if not resultado:
            raise ValueError("Chamado não encontrado.")
        
        usuario_id = resultado["usuario_id"]
        status_anterior = resultado["status"]
        
        # Define novo status baseado em fechar_chamado
        novo_status = STATUS_RESOLVIDO if fechar_chamado else status_anterior
        
        # Atualiza o ticket
        cursor.execute("""
            UPDATE tickets
            SET status = ?,
                solucao_aplicada = ?,
                data_resolucao = ?,
                origem_solucao = ?
            WHERE id = ?
        """, (
            novo_status,
            solucao.strip(),
            data_atual if fechar_chamado else None,
            origem_solucao,
            ticket_id,
        ))
        
        # Envia notificação ao cliente apenas se fechando
        if fechar_chamado:
            try:
                cursor.execute("""
                    INSERT INTO notificacoes (usuario_id, ticket_id, tipo, mensagem)
                    VALUES (?, ?, ?, ?)
                """, (
                    usuario_id,
                    ticket_id,
                    NOTIF_RESOLVIDO,
                    f"Seu chamado #{ticket_id} foi resolvido. Origem: {origem_solucao}"
                ))
            except Exception as e:
                # Falha no envio da notificação não deve impedir a resolução
                print(f"Aviso: notificação não foi enviada. Erro: {e}")


def salvar_solucao_na_kb(problema: str, solucao: str, modulo_sap: str | None = None):
    validar_texto(problema, "Problema")
    validar_texto(solucao, "Solução")

    problema_chave = normalizar_texto(problema)
    modulo_normalizado = modulo_sap.strip().upper() if modulo_sap else None

    # Gera embedding da solução para busca semântica futura
    try:
        embedding_bytes = gerar_embedding(solucao.strip())
    except Exception as e:
        print(f"Aviso: não foi possível gerar embedding. Erro: {e}")
        embedding_bytes = None

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO knowledge_base (
                problema_chave,
                solucao_recomendada,
                modulo_sap,
                embedding
            )
            VALUES (?, ?, ?, ?)
            ON CONFLICT(problema_chave) DO UPDATE SET
                solucao_recomendada = excluded.solucao_recomendada,
                modulo_sap = COALESCE(excluded.modulo_sap, knowledge_base.modulo_sap),
                embedding = COALESCE(excluded.embedding, knowledge_base.embedding),
                contador_uso = knowledge_base.contador_uso + 1,
                data_atualizacao = CURRENT_TIMESTAMP
        """, (
            problema_chave,
            solucao.strip(),
            modulo_normalizado,
            embedding_bytes,
        ))


def buscar_solucao_exata_kb(problema: str) -> str | None:
    problema_chave = normalizar_texto(problema)

    if not problema_chave:
        return None

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT solucao_recomendada
            FROM knowledge_base
            WHERE problema_chave = ?
        """, (problema_chave,))

        resultado = cursor.fetchone()

        if not resultado:
            return None

        cursor.execute("""
            UPDATE knowledge_base
            SET contador_uso = contador_uso + 1,
                data_atualizacao = CURRENT_TIMESTAMP
            WHERE problema_chave = ?
        """, (problema_chave,))

        return resultado["solucao_recomendada"]


def buscar_solucao_similar_kb(problema: str, threshold: float = SIMILARIDADE_THRESHOLD) -> dict | None:
    """
    Busca por solução similar na KB usando embedding vetorial.
    Retorna: {"solucao": str, "confianca": float, "tipo": "similar"}
    Se nenhuma atinge o threshold, retorna None.
    """
    if not problema or not problema.strip():
        return None

    try:
        # Gera embedding do problema
        embedding_problema = gerar_embedding(problema.strip())
        embedding_array_problema = embedding_para_array(embedding_problema)

        if embedding_array_problema is None:
            return None

        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, solucao_recomendada, embedding
                FROM knowledge_base
                WHERE embedding IS NOT NULL
                ORDER BY data_atualizacao DESC
                LIMIT 100
            """)

            registros = cursor.fetchall()

        if not registros:
            return None

        melhor_match = None
        melhor_confianca = 0.0

        for registro in registros:
            embedding_kb = embedding_para_array(registro["embedding"])
            if embedding_kb is None:
                continue

            confianca = calcular_similaridade(embedding_array_problema, embedding_kb)

            if confianca > melhor_confianca:
                melhor_confianca = confianca
                melhor_match = {
                    "id": registro["id"],
                    "solucao": registro["solucao_recomendada"],
                    "confianca": confianca,
                }

        if melhor_confianca >= threshold and melhor_match:
            # Incrementa contador_uso
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE knowledge_base
                    SET contador_uso = contador_uso + 1,
                        data_atualizacao = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (melhor_match["id"],))

            return {
                "solucao": melhor_match["solucao"],
                "confianca": melhor_confianca,
                "tipo": "similar",
            }

        return None

    except Exception as e:
        print(f"Erro na busca semântica: {e}")
        return None


def listar_base_conhecimento() -> list[dict]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT *
            FROM knowledge_base
            ORDER BY contador_uso DESC, data_atualizacao DESC
        """)

        return cursor.fetchall()


def listar_normas_modelo() -> list[dict]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT titulo, conteudo
            FROM model_norms
            WHERE ativo = 1
            ORDER BY id
        """)

        return cursor.fetchall()


def salvar_norma_modelo(titulo: str, conteudo: str):
    validar_texto(titulo, "Título")
    validar_texto(conteudo, "Conteúdo")

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO model_norms (titulo, conteudo)
            VALUES (?, ?)
        """, (
            titulo.strip(),
            conteudo.strip(),
        ))


def obter_metricas_sla() -> pd.DataFrame:
    with get_connection() as conn:
        df = pd.read_sql_query("SELECT * FROM tickets", conn)

    if df.empty:
        return pd.DataFrame()

    df["data_criacao"] = pd.to_datetime(df["data_criacao"], errors="coerce")
    df["prazo_limite"] = pd.to_datetime(df["prazo_limite"], errors="coerce")
    df["data_resolucao"] = pd.to_datetime(df["data_resolucao"], errors="coerce")

    agora = pd.Timestamp.now()

    def calcular_status_sla(row):
        referencia = row["data_resolucao"] if row["status"] == STATUS_RESOLVIDO else agora
        return "Dentro do SLA" if referencia <= row["prazo_limite"] else "SLA Estourado"

    df["status_sla"] = df.apply(calcular_status_sla, axis=1)

    df["tempo_resolucao_horas"] = (
        (df["data_resolucao"] - df["data_criacao"]).dt.total_seconds() / 3600
    ).round(2)

    df["horas_ate_prazo"] = (
        (df["prazo_limite"] - agora).dt.total_seconds() / 3600
    ).round(2)

    return df


if __name__ == "__main__":
    init_db()
    print("Backend e banco de dados inicializados com sucesso.")



# =====================================================================
# [NOVO R6] Funções de Edição/Gestão da KB e Normas
# =====================================================================

def editar_solucao_kb(kb_id: int, nova_solucao: str, novo_modulo_sap: str | None = None) -> None:
    """
    [NOVO R6] Edita a solução de uma entrada da KB.
    
    - Atualiza solucao_recomendada
    - Regenera embedding da nova solução
    - Atualiza modulo_sap se informado
    - Atualiza data_atualizacao
    """
    validar_texto(nova_solucao, "Solução")
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Verifica se KB existe
        cursor.execute("SELECT id FROM knowledge_base WHERE id = ?", (kb_id,))
        if not cursor.fetchone():
            raise ValueError("Entrada da base de conhecimento não encontrada.")
        
        # Gera novo embedding
        novo_embedding = gerar_embedding(nova_solucao)
        
        # Atualiza
        if novo_modulo_sap:
            cursor.execute("""
                UPDATE knowledge_base
                SET solucao_recomendada = ?,
                    embedding = ?,
                    modulo_sap = ?,
                    data_atualizacao = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (nova_solucao, novo_embedding, novo_modulo_sap.upper(), kb_id))
        else:
            cursor.execute("""
                UPDATE knowledge_base
                SET solucao_recomendada = ?,
                    embedding = ?,
                    data_atualizacao = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (nova_solucao, novo_embedding, kb_id))
        
        conn.commit()


def excluir_entrada_kb(kb_id: int) -> None:
    """
    [NOVO R6] Exclui (deleta) uma entrada da KB.
    
    Levanta ValueError se não encontrar.
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute("SELECT id FROM knowledge_base WHERE id = ?", (kb_id,))
        if not cursor.fetchone():
            raise ValueError("Entrada da base de conhecimento não encontrada.")
        
        cursor.execute("DELETE FROM knowledge_base WHERE id = ?", (kb_id,))
        conn.commit()


def desativar_norma(norma_id: int) -> None:
    """
    [NOVO R6] Desativa (ativo = 0) uma norma sem apagar o histórico.
    
    Levanta ValueError se não encontrar.
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute("SELECT id FROM model_norms WHERE id = ?", (norma_id,))
        if not cursor.fetchone():
            raise ValueError("Norma não encontrada.")
        
        cursor.execute("UPDATE model_norms SET ativo = 0 WHERE id = ?", (norma_id,))
        conn.commit()


def reativar_norma(norma_id: int) -> None:
    """
    [NOVO R6] Reativa (ativo = 1) uma norma desativada.
    
    Levanta ValueError se não encontrar.
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute("SELECT id FROM model_norms WHERE id = ?", (norma_id,))
        if not cursor.fetchone():
            raise ValueError("Norma não encontrada.")
        
        cursor.execute("UPDATE model_norms SET ativo = 1 WHERE id = ?", (norma_id,))
        conn.commit()


def listar_todas_as_normas() -> list[dict]:
    """
    [NOVO R6] Lista TODAS as normas (ativas E desativadas).
    
    Útil para a interface de edição/desativação.
    Ordena: ativas primeiro (ativo=1), depois desativadas, por data desc.
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, titulo, conteudo, ativo, data_registro
            FROM model_norms
            ORDER BY ativo DESC, data_registro DESC
        """)
        return cursor.fetchall()



# =====================================================================
# [NOVO R7] Funções de Interações (Conversa dentro do Chamado)
# =====================================================================

def criar_interacao(ticket_id: int, usuario_id: int, mensagem: str) -> int:
    """
    [NOVO R7] Cria uma nova interação (comentário/mensagem) em um chamado.
    
    - Valida que mensagem não é vazia
    - Insere na tabela ticket_interacoes
    - Retorna o ID da interação
    """
    validar_texto(mensagem, "Mensagem")
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Verifica se ticket existe
        cursor.execute("SELECT id FROM tickets WHERE id = ?", (ticket_id,))
        if not cursor.fetchone():
            raise ValueError("Chamado não encontrado.")
        
        # Verifica se usuário existe
        cursor.execute("SELECT id FROM usuarios WHERE id = ?", (usuario_id,))
        if not cursor.fetchone():
            raise ValueError("Usuário não encontrado.")
        
        cursor.execute("""
            INSERT INTO ticket_interacoes (ticket_id, usuario_id, mensagem)
            VALUES (?, ?, ?)
        """, (ticket_id, usuario_id, mensagem))
        
        conn.commit()
        return cursor.lastrowid


def listar_interacoes(ticket_id: int) -> list[dict]:
    """
    [NOVO R7] Lista todas as interações (comentários) de um chamado.
    
    Ordena por data_criacao ASC (mais antigas primeiro).
    Inclui dados do usuário (username) para exibição.
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                ti.id,
                ti.ticket_id,
                ti.usuario_id,
                u.username,
                u.role,
                ti.mensagem,
                ti.data_criacao
            FROM ticket_interacoes ti
            JOIN usuarios u ON ti.usuario_id = u.id
            WHERE ti.ticket_id = ?
            ORDER BY ti.data_criacao ASC
        """, (ticket_id,))
        
        return cursor.fetchall()


def contar_interacoes(ticket_id: int) -> int:
    """
    [NOVO R7] Conta quantas interações um chamado tem.
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as cnt FROM ticket_interacoes WHERE ticket_id = ?", (ticket_id,))
        result = cursor.fetchone()
        return result["cnt"] if result else 0


# =====================================================================
# [NOVO R10] Funções para Anexos nos Chamados
# =====================================================================

def salvar_anexo(ticket_id: int, usuario_id: int, arquivo_stream, nome_arquivo: str, tipo_mime: str = None) -> int:
    """
    [MODIFICADO R10] Salva um arquivo anexado diretamente no AWS S3.
    
    Args:
        ticket_id: ID do chamado
        usuario_id: ID do usuário que está anexando
        arquivo_stream: Stream do arquivo (do Streamlit)
        nome_arquivo: Nome original do arquivo
        tipo_mime: Tipo MIME do arquivo (opcional)
    
    Returns:
        ID do anexo salvo
    """
    if not ticket_id or not usuario_id or not nome_arquivo.strip():
        raise ValueError("Dados incompletos para salvar anexo.")
    
    nome_unico = f"{uuid4()}_{nome_arquivo}"
    conteudo = arquivo_stream.read()
    tamanho_bytes = len(conteudo)
    
    # Upload para o S3
    try:
        s3_client.put_object(
            Bucket=S3_BUCKET,
            Key=nome_unico,
            Body=conteudo,
            ContentType=tipo_mime
        )
    except Exception as e:
        raise ValueError(f"Erro ao fazer upload para a nuvem: {e}")
    
    # Salvar metadados no banco (SQLite/Postgres)
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO ticket_anexos (ticket_id, usuario_id, nome_arquivo, caminho_arquivo, tipo_mime, tamanho_bytes)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (ticket_id, usuario_id, nome_arquivo.strip(), nome_unico, tipo_mime, tamanho_bytes))
        conn.commit()
        return cursor.lastrowid


def listar_anexos(ticket_id: int) -> list[dict]:
    """
    [NOVO R10] Lista todos os anexos de um chamado.
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                ta.id,
                ta.ticket_id,
                ta.usuario_id,
                u.username,
                ta.nome_arquivo,
                ta.caminho_arquivo,
                ta.tipo_mime,
                ta.tamanho_bytes,
                ta.data_upload
            FROM ticket_anexos ta
            JOIN usuarios u ON ta.usuario_id = u.id
            WHERE ta.ticket_id = ?
            ORDER BY ta.data_upload DESC
        """, (ticket_id,))
        
        return cursor.fetchall()


def obter_anexo(anexo_id: int) -> dict | None:
    """
    [NOVO R10] Obtém informações de um anexo específico.
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM ticket_anexos WHERE id = ?
        """, (anexo_id,))
        
        return cursor.fetchone()


def baixar_conteudo_anexo(chave_s3: str) -> bytes:
    """
    [NOVO R10] Faz o download do arquivo do S3 para a memória do Streamlit.
    
    Args:
        chave_s3: Chave do arquivo no S3 (armazenada em caminho_arquivo)
    
    Returns:
        Conteúdo do arquivo em bytes
    """
    try:
        response = s3_client.get_object(Bucket=S3_BUCKET, Key=chave_s3)
        return response['Body'].read()
    except Exception as e:
        raise ValueError(f"Erro ao baixar do S3: {e}")


def excluir_anexo(anexo_id: int) -> None:
    """
    [MODIFICADO R10] Exclui um anexo do banco e do AWS S3.
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT caminho_arquivo FROM ticket_anexos WHERE id = ?", (anexo_id,))
        resultado = cursor.fetchone()
        
        if not resultado:
            raise ValueError("Anexo não encontrado.")
        
        chave_s3 = resultado["caminho_arquivo"]
        
        # Excluir registro do banco
        cursor.execute("DELETE FROM ticket_anexos WHERE id = ?", (anexo_id,))
        conn.commit()
        
        # Excluir do S3
        try:
            s3_client.delete_object(Bucket=S3_BUCKET, Key=chave_s3)
        except Exception as e:
            print(f"Aviso: Não foi possível excluir arquivo físico {chave_s3} no S3. Erro: {e}")


def contar_anexos(ticket_id: int) -> int:
    """
    [NOVO R10] Conta quantos anexos um chamado tem.
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as cnt FROM ticket_anexos WHERE ticket_id = ?", (ticket_id,))
        result = cursor.fetchone()
        return result["cnt"] if result else 0


def formatar_tamanho_bytes(tamanho_bytes: int) -> str:
    """
    [NOVO R10] Formata tamanho em bytes para formato legível.
    """
    if tamanho_bytes < 1024:
        return f"{tamanho_bytes} B"
    elif tamanho_bytes < 1024 * 1024:
        return f"{tamanho_bytes / 1024:.1f} KB"
    elif tamanho_bytes < 1024 * 1024 * 1024:
        return f"{tamanho_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{tamanho_bytes / (1024 * 1024 * 1024):.1f} GB"
