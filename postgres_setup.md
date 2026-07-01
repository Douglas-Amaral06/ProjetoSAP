# Configuração PostgreSQL para Helpdesk SAP IA

## [NOVO R9] - Migração para PostgreSQL

### Por que PostgreSQL?
- Melhor suporte a concorrência (múltiplos atendentes simultâneos)
- Performance superior em produção
- Recursos avançados (triggers, views, stored procedures)
- Escalabilidade horizontal mais fácil

### Configuração

#### 1. Instalar PostgreSQL
```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install postgresql postgresql-contrib

# macOS (via Homebrew)
brew install postgresql

# Windows (via installer)
# Download: https://www.postgresql.org/download/windows/
```

#### 2. Criar banco de dados e usuário
```sql
-- Conectar ao PostgreSQL
sudo -u postgres psql

-- Criar banco de dados
CREATE DATABASE sap_helpdesk;

-- Criar usuário (ajuste a senha)
CREATE USER sap_user WITH PASSWORD 'sua_senha_segura';

-- Conceder privilégios
GRANT ALL PRIVILEGES ON DATABASE sap_helpdesk TO sap_user;

-- Conceder privilégios para criar tabelas
ALTER USER sap_user CREATEDB;
```

#### 3. Configurar variáveis de ambiente
Crie/edite o arquivo `.env`:

```env
# Escolha entre 'sqlite' (padrão) ou 'postgres'
DB_TYPE=postgres

# Configurações PostgreSQL
PG_HOST=localhost
PG_PORT=5432
PG_DB=sap_helpdesk
PG_USER=sap_user
PG_PASSWORD=sua_senha_segura

# Para SQLite (opcional, se quiser voltar)
SAP_HELPDESK_DB=sap_chamados.db

# Configurações Gemini
GOOGLE_API_KEY=sua_chave_aqui
GEMINI_MODEL=gemini-2.5-flash
```

#### 4. Migração de dados (SQLite → PostgreSQL)

**Opção A: Migração automática (recomendada)**
```bash
# Instalar ferramentas necessárias
pip install pgloader

# Criar arquivo de configuração do pgloader
cat > migracao.load << EOF
LOAD DATABASE
    FROM sqlite:///sap_chamados.db
    INTO postgresql://sap_user:sua_senha_segura@localhost:5432/sap_helpdesk
    WITH include drop, create tables, create indexes, reset sequences
    SET work_mem to '16MB', maintenance_work_mem to '512 MB';
EOF

# Executar migração
pgloader migracao.load
```

**Opção B: Migração manual**
```bash
# 1. Exportar SQLite para SQL
sqlite3 sap_chamados.db .dump > backup_sqlite.sql

# 2. Converter sintaxe SQLite → PostgreSQL
# Use ferramentas como sqlite3-to-postgres ou adapte manualmente

# 3. Importar para PostgreSQL
psql -U sap_user -d sap_helpdesk -f backup_postgres.sql
```

### Recursos PostgreSQL específicos implementados

#### 1. Índices para performance
```sql
-- Índices para buscas frequentes
CREATE INDEX idx_tickets_status ON tickets(status);
CREATE INDEX idx_tickets_usuario_id ON tickets(usuario_id);
CREATE INDEX idx_tickets_data_criacao ON tickets(data_criacao DESC);
CREATE INDEX idx_kb_problema_chave ON knowledge_base(problema_chave);
CREATE INDEX idx_notificacoes_usuario_id ON notificacoes(usuario_id);
```

#### 2. Views para relatórios
```sql
-- View para dashboard SLA
CREATE VIEW vw_sla_analise AS
SELECT 
    status,
    COUNT(*) as total,
    SUM(CASE WHEN data_resolucao <= prazo_limite THEN 1 ELSE 0 END) as dentro_sla,
    AVG(EXTRACT(EPOCH FROM (data_resolucao - data_criacao))/3600) as tempo_medio_resolucao_horas
FROM tickets
WHERE status = 'Resolvido'
GROUP BY status;
```

#### 3. Triggers para auditoria
```sql
-- Tabela de auditoria
CREATE TABLE auditoria_tickets (
    id SERIAL PRIMARY KEY,
    ticket_id INTEGER,
    acao VARCHAR(20),
    usuario_id INTEGER,
    dados_antigos JSONB,
    dados_novos JSONB,
    data_alteracao TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Trigger para auditoria de tickets
CREATE OR REPLACE FUNCTION auditar_ticket()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO auditoria_tickets (ticket_id, acao, usuario_id, dados_antigos, dados_novos)
    VALUES (NEW.id, TG_OP, NEW.usuario_id, row_to_json(OLD), row_to_json(NEW));
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_auditoria_tickets
AFTER INSERT OR UPDATE OR DELETE ON tickets
FOR EACH ROW EXECUTE FUNCTION auditar_ticket();
```

### Validação da migração

#### 1. Testar conexão
```python
import psycopg2

try:
    conn = psycopg2.connect(
        host="localhost",
        database="sap_helpdesk",
        user="sap_user",
        password="sua_senha_segura"
    )
    print("✅ Conexão PostgreSQL bem-sucedida!")
    conn.close()
except Exception as e:
    print(f"❌ Erro na conexão: {e}")
```

#### 2. Verificar tabelas
```sql
-- Conectar ao banco
psql -U sap_user -d sap_helpdesk

-- Listar tabelas
\dt

-- Contar registros
SELECT 'tickets' as tabela, COUNT(*) as total FROM tickets
UNION ALL
SELECT 'usuarios', COUNT(*) FROM usuarios
UNION ALL
SELECT 'knowledge_base', COUNT(*) FROM knowledge_base
ORDER BY tabela;
```

### Rollback para SQLite (se necessário)

```bash
# No arquivo .env, altere:
DB_TYPE=sqlite

# Ou remova as variáveis PostgreSQL para usar SQLite padrão
```

### Performance esperada

| Operação | SQLite | PostgreSQL | Melhoria |
|----------|--------|------------|----------|
| 10 usuários simultâneos | ~2-3s | ~0.5s | 4-6x |
| 1000 registros busca | ~1s | ~0.2s | 5x |
| Escrita concorrente | Lock issues | Smooth | Significativa |
| Backup/restore | Manual | Automático | Muito melhor |

### Próximos passos (após migração)

1. **Backup automático**: Configurar `pg_dump` agendado
2. **Replicação**: Configurar replica para alta disponibilidade
3. **Connection pooling**: Usar PgBouncer para muitas conexões
4. **Monitoramento**: Configurar alertas para performance

### Suporte

Para problemas:
1. Verificar logs do PostgreSQL: `sudo tail -f /var/log/postgresql/*.log`
2. Testar conexão básica
3. Verificar permissões do usuário
4. Confirmar que o banco existe e está acessível