"""
[NOVO R11] Módulo para treinamento de modelo próprio com Databricks.

Este módulo permite:
1. Exportar histórico de chamados como dataset de treinamento
2. Treinar/fine-tunar um modelo próprio com o histórico real
3. Comparar custo/benefício vs. Gemini via API

AVISO: Esta implementação é um esqueleto para validação de conceito.
Em produção, requer integração real com Databricks ou ambiente ML.
"""

import os
import json
import pandas as pd
import numpy as np
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import backend

# Configurações Databricks
DATABRICKS_HOST = os.getenv("DATABRICKS_HOST", "https://dbc-xxxxxx.cloud.databricks.com")
DATABRICKS_TOKEN = os.getenv("DATABRICKS_TOKEN", "")
MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", f"{DATABRICKS_HOST}/mlflow")
MODEL_REGISTRY_NAME = "sap_helpdesk_model"


class DatasetExporter:
    """Classe para exportar dados do helpdesk para treinamento."""
    
    def __init__(self):
        self.backend = backend
    
    def exportar_dataset_treinamento(self, formato: str = "jsonl") -> Dict:
        """
        Exporta histórico de tickets e KB como dataset de treinamento.
        
        Args:
            formato: "jsonl" (padrão), "csv" ou "parquet"
            
        Returns:
            Dict com caminhos dos arquivos exportados e estatísticas
        """
        print("📊 Exportando dataset para treinamento...")
        
        try:
            # 1. Coletar dados do banco
            with backend.get_connection() as conn:
                # Tickets resolvidos (com soluções)
                df_tickets = pd.read_sql_query("""
                    SELECT 
                        t.id as ticket_id,
                        t.descricao as problema,
                        t.solucao_aplicada as solucao,
                        t.modulo_sap,
                        t.prioridade,
                        t.data_criacao,
                        t.data_resolucao,
                        t.origem_solucao,
                        u.username
                    FROM tickets t
                    JOIN usuarios u ON t.usuario_id = u.id
                    WHERE t.status = 'Resolvido' 
                      AND t.solucao_aplicada IS NOT NULL
                      AND t.solucao_aplicada != ''
                    ORDER BY t.data_criacao DESC
                """, conn)
                
                # Base de conhecimento
                df_kb = pd.read_sql_query("""
                    SELECT 
                        id as kb_id,
                        problema_chave as problema,
                        solucao_recomendada as solucao,
                        modulo_sap,
                        contador_uso,
                        data_registro
                    FROM knowledge_base
                    WHERE solucao_recomendada IS NOT NULL
                      AND solucao_recomendada != ''
                    ORDER BY contador_uso DESC
                """, conn)
            
            print(f"✅ Coletados {len(df_tickets)} tickets resolvidos")
            print(f"✅ Coletadas {len(df_kb)} entradas da base de conhecimento")
            
            # 2. Preparar diretório de exportação
            data_dir = Path("data/training")
            data_dir.mkdir(parents=True, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # 3. Processar e salvar dataset
            caminhos = {}
            estatisticas = {}
            
            if formato == "jsonl":
                # Tickets como JSON Lines
                tickets_jsonl_path = data_dir / f"tickets_{timestamp}.jsonl"
                with open(tickets_jsonl_path, "w", encoding="utf-8") as f:
                    for _, row in df_tickets.iterrows():
                        registro = {
                            "problema": row["problema"],
                            "solucao": row["solucao"],
                            "modulo_sap": row["modulo_sap"],
                            "prioridade": row["prioridade"],
                            "origem": row["origem_solucao"],
                            "data_criacao": str(row["data_criacao"]),
                            "usuario": row["username"]
                        }
                        f.write(json.dumps(registro, ensure_ascii=False) + "\n")
                
                # KB como JSON Lines
                kb_jsonl_path = data_dir / f"kb_{timestamp}.jsonl"
                with open(kb_jsonl_path, "w", encoding="utf-8") as f:
                    for _, row in df_kb.iterrows():
                        registro = {
                            "problema": row["problema"],
                            "solucao": row["solucao"],
                            "modulo_sap": row["modulo_sap"],
                            "contador_uso": int(row["contador_uso"]),
                            "data_registro": str(row["data_registro"])
                        }
                        f.write(json.dumps(registro, ensure_ascii=False) + "\n")
                
                caminhos["tickets"] = str(tickets_jsonl_path)
                caminhos["kb"] = str(kb_jsonl_path)
            
            elif formato == "csv":
                # Tickets como CSV
                tickets_csv_path = data_dir / f"tickets_{timestamp}.csv"
                df_tickets.to_csv(tickets_csv_path, index=False, encoding="utf-8")
                
                # KB como CSV
                kb_csv_path = data_dir / f"kb_{timestamp}.csv"
                df_kb.to_csv(kb_csv_path, index=False, encoding="utf-8")
                
                caminhos["tickets"] = str(tickets_csv_path)
                caminhos["kb"] = str(kb_csv_path)
            
            elif formato == "parquet":
                # Tickets como Parquet
                tickets_parquet_path = data_dir / f"tickets_{timestamp}.parquet"
                df_tickets.to_parquet(tickets_parquet_path, index=False)
                
                # KB como Parquet
                kb_parquet_path = data_dir / f"kb_{timestamp}.parquet"
                df_kb.to_parquet(kb_parquet_path, index=False)
                
                caminhos["tickets"] = str(tickets_parquet_path)
                caminhos["kb"] = str(kb_parquet_path)
            
            # 4. Calcular estatísticas
            estatisticas = {
                "total_tickets": len(df_tickets),
                "total_kb": len(df_kb),
                "modulos_unicos": df_tickets["modulo_sap"].nunique(),
                "tickets_por_modulo": df_tickets["modulo_sap"].value_counts().to_dict(),
                "tickets_por_origem": df_tickets["origem_solucao"].value_counts().to_dict(),
                "tickets_por_prioridade": df_tickets["prioridade"].value_counts().to_dict(),
                "kb_mais_usada": df_kb["contador_uso"].max() if not df_kb.empty else 0,
                "data_mais_antiga": str(df_tickets["data_criacao"].min()) if not df_tickets.empty else None,
                "data_mais_recente": str(df_tickets["data_criacao"].max()) if not df_tickets.empty else None
            }
            
            print(f"✅ Dataset exportado com sucesso!")
            print(f"   📁 Tickets: {caminhos.get('tickets', 'N/A')}")
            print(f"   📁 KB: {caminhos.get('kb', 'N/A')}")
            print(f"   📊 Estatísticas: {json.dumps(estatisticas, indent=2, default=str)}")
            
            return {
                "sucesso": True,
                "caminhos": caminhos,
                "estatisticas": estatisticas,
                "timestamp": timestamp
            }
            
        except Exception as e:
            print(f"❌ Erro ao exportar dataset: {e}")
            return {
                "sucesso": False,
                "erro": str(e)
            }
    
    def analisar_viabilidade_treinamento(self, custo_gemini_por_chamada: float = 0.0005) -> Dict:
        """
        Analisa custo/benefício do treinamento próprio vs. Gemini.
        
        Args:
            custo_gemini_por_chamada: Custo estimado por chamada ao Gemini (USD)
            
        Returns:
            Dict com análise de viabilidade
        """
        try:
            with backend.get_connection() as conn:
                # Estatísticas de uso
                df_tickets = pd.read_sql_query("""
                    SELECT 
                        COUNT(*) as total_chamados,
                        SUM(CASE WHEN origem_solucao = 'IA' THEN 1 ELSE 0 END) as chamados_gemini,
                        SUM(CASE WHEN origem_solucao = 'Base de Conhecimento' THEN 1 ELSE 0 END) as chamados_kb,
                        MIN(data_criacao) as data_primeiro_chamado,
                        MAX(data_criacao) as data_ultimo_chamado
                    FROM tickets
                    WHERE status = 'Resolvido'
                """, conn)
                
                df_kb = pd.read_sql_query("""
                    SELECT 
                        COUNT(*) as total_entradas,
                        SUM(contador_uso) as total_usos,
                        AVG(contador_uso) as media_usos_por_entrada
                    FROM knowledge_base
                """, conn)
            
            # Calcular custos e benefícios
            total_chamados = df_tickets.iloc[0]["total_chamados"] or 0
            chamados_gemini = df_tickets.iloc[0]["chamados_gemini"] or 0
            chamados_kb = df_tickets.iloc[0]["chamados_kb"] or 0
            
            # Custo histórico com Gemini
            custo_historico_gemini = chamados_gemini * custo_gemini_por_chamada
            
            # Economia potencial com modelo próprio
            # Supondo que 70% dos chamados poderiam ser atendidos pelo modelo próprio
            economia_potencial = chamados_gemini * custo_gemini_por_chamada * 0.7
            
            # Custo estimado do treinamento
            # Baseado em: custo GPU + armazenamento + engenharia
            custo_treinamento_base = 500  # USD (estimativa conservadora)
            
            # ROI estimado
            roi_estimado = (economia_potencial - custo_treinamento_base) / custo_treinamento_base
            
            analise = {
                "estatisticas": {
                    "total_chamados_resolvidos": int(total_chamados),
                    "chamados_atendidos_gemini": int(chamados_gemini),
                    "chamados_atendidos_kb": int(chamados_kb),
                    "porcentagem_gemini": f"{(chamados_gemini/total_chamados*100):.1f}%" if total_chamados > 0 else "0%",
                    "porcentagem_kb": f"{(chamados_kb/total_chamados*100):.1f}%" if total_chamados > 0 else "0%",
                    "total_entradas_kb": int(df_kb.iloc[0]["total_entradas"] or 0),
                    "total_usos_kb": int(df_kb.iloc[0]["total_usos"] or 0),
                    "media_usos_por_entrada": float(df_kb.iloc[0]["media_usos_por_entrada"] or 0)
                },
                "analise_custo": {
                    "custo_gemini_por_chamada_usd": custo_gemini_por_chamada,
                    "custo_historico_gemini_usd": round(custo_historico_gemini, 2),
                    "economia_potencial_anual_usd": round(economia_potencial * 12, 2),  # Projetando para ano
                    "custo_estimado_treinamento_usd": custo_treinamento_base,
                    "roi_estimado": f"{roi_estimado:.1%}",
                    "payback_period_meses": f"{(custo_treinamento_base/economia_potencial*12):.1f}" if economia_potencial > 0 else "N/A"
                },
                "recomendacao": self._gerar_recomendacao(
                    total_chamados, chamados_gemini, economia_potencial, roi_estimado
                ),
                "timestamp": datetime.now().isoformat()
            }
            
            return analise
            
        except Exception as e:
            print(f"❌ Erro na análise de viabilidade: {e}")
            return {
                "sucesso": False,
                "erro": str(e)
            }
    
    def _gerar_recomendacao(self, total_chamados: int, chamados_gemini: int, 
                           economia_potencial: float, roi_estimado: float) -> Dict:
        """Gera recomendação baseada nos dados analisados."""
        
        if total_chamados < 100:
            nivel = "BAIXO"
            recomendacao = "Volume insuficiente para justificar treinamento próprio. Continue com Gemini."
            justificativa = f"Apenas {total_chamados} chamados resolvidos. Volume mínimo recomendado: 500+ chamados."
        
        elif chamados_gemini < 50:
            nivel = "MODERADO"
            recomendacao = "Maior parte já atendida pela KB. Foque em melhorar embeddings e prompts."
            justificativa = f"Apenas {chamados_gemini} chamados usaram Gemini. KB já está sendo eficaz."
        
        elif economia_potencial < 200:
            nivel = "MODERADO"
            recomendacao = "Economia potencial baixa. Avalie em 6 meses com mais dados."
            justificativa = f"Economia anual estimada: ${economia_potencial:.2f}. Limiar recomendado: $500+."
        
        elif roi_estimado > 1.0:  # ROI > 100%
            nivel = "ALTO"
            recomendacao = "ROI atrativo. Considere iniciar POC com subset de dados."
            justificativa = f"ROI estimado: {roi_estimado:.1%}. Payback rápido justifica investimento."
        
        else:
            nivel = "MODERADO"
            recomendacao = "Caso limítrofe. Realize análise mais detalhada com dados de 3 meses."
            justificativa = f"ROI: {roi_estimado:.1%}. Volume: {total_chamados} chamados. Precisa de mais dados."
        
        return {
            "nivel_prioridade": nivel,
            "recomendacao": recomendacao,
            "justificativa": justificativa,
            "acoes_recomendadas": self._gerar_acoes_recomendadas(nivel)
        }
    
    def _gerar_acoes_recomendadas(self, nivel: str) -> List[str]:
        """Gera ações recomendadas baseadas no nível de prioridade."""
        if nivel == "ALTO":
            return [
                "1. Exportar dataset completo para análise",
                "2. Configurar ambiente Databricks/MLflow",
                "3. Iniciar POC com 20% dos dados",
                "4. Validar acurácia vs. Gemini atual",
                "5. Estimar custo operacional mensal"
            ]
        elif nivel == "MODERADO":
            return [
                "1. Monitorar crescimento por 3 meses",
                "2. Otimizar embeddings da KB atual",
                "3. Melhorar prompts do Gemini",
                "4. Coletar feedback de qualidade",
                "5. Reavaliar em 90 dias"
            ]
        else:  # BAIXO
            return [
                "1. Continuar com Gemini + KB",
                "2. Focar em aumentar volume de chamados",
                "3. Documentar casos de sucesso/fracasso",
                "4. Revisar quando atingir 500+ chamados",
                "5. Coletar métricas de satisfação"
            ]


class ModelTrainer:
    """Classe para treinamento de modelo próprio (esqueleto)."""
    
    def __init__(self):
        self.dataset_exporter = DatasetExporter()
    
    def treinar_modelo_basico(self, dataset_path: str, config: Dict = None) -> Dict:
        """
        Treina um modelo básico de NLP para suporte SAP.
        Implementação esqueleto - requer integração real com ML.
        """
        if config is None:
            config = {
                "model_name": "distilbert-base-multilingual-cased",
                "epochs": 3,
                "batch_size": 8,
                "learning_rate": 2e-5,
                "test_size": 0.2
            }
        
        print("🚀 Iniciando treinamento de modelo...")
        print(f"📋 Configuração: {json.dumps(config, indent=2)}")
        
        # Esta é uma implementação esqueleto
        # Em produção, integrar com:
        # 1. Transformers (Hugging Face)
        # 2. Databricks AutoML
        # 3. MLflow para tracking
        
        resultado = {
            "sucesso": True,
            "configuracao": config,
            "dataset": dataset_path,
            "status": "IMPLEMENTAÇÃO_ESQUELETO",
            "mensagem": "Esta funcionalidade requer integração real com ambiente ML.",
            "passos_para_producao": [
                "1. Configurar ambiente Databricks/GPU",
                "2. Implementar pipeline de pré-processamento",
                "3. Escolher arquitetura de modelo (ex: T5, BERT)",
                "4. Implementar fine-tuning com PyTorch/TensorFlow",
                "5. Configurar MLflow para experiment tracking",
                "6. Implementar avaliação de qualidade",
                "7. Criar pipeline de deployment",
                "8. Configurar A/B testing vs. Gemini"
            ],
            "estimativa_custo": {
                "treinamento": "~$200-500 USD (GPU spot instances)",
                "inferencia": "~$50-100 USD/mês (CPU instances)",
                "manutencao": "~$100-200 USD/mês (engenharia)"
            },
            "timestamp": datetime.now().isoformat()
        }
        
        return resultado
    
    def comparar_com_gemini(self, amostra_tamanho: int = 20) -> Dict:
        """
        Compara modelo próprio vs. Gemini em amostra de dados.
        """
        print(f"🔍 Comparando com Gemini (amostra: {amostra_tamanho})...")
        
        # Em produção, implementar:
        # 1. Selecionar amostra aleatória de problemas
        # 2. Gerar respostas com Gemini
        # 3. Gerar respostas com modelo próprio
        # 4. Comparar métricas (BLEU, ROUGE, human evaluation)
        
        resultado = {
            "sucesso": True,
            "amostra_tamanho": amostra_tamanho,
            "status": "IMPLEMENTAÇÃO_ESQUELETO",
            "métricas_recomendadas": {
                "qualidade": ["BLEU", "ROUGE", "METEOR"],
                "utilidade": ["Precision@K", "Recall@K", "F1-Score"],
                "custo": ["Custo por chamada", "Latência média", "Throughput"],
                "negócio": ["Satisfação do cliente", "Resolução em 1ª resposta", "Redução de escalações"]
            },
            "benchmark_sugerido": {
                "dataset": "Subset de 100 problemas reais",
                "avaliadores": "3 especialistas SAP + 5 usuários",
                "critérios": ["Correção técnica", "Clareza", "Completude", "Ação imediata"],
                "escala": "1-5 (Likert scale)"
            },
            "timestamp": datetime.now().isoformat()
        }
        
        return resultado


# Interface para uso nas aplicações
def exportar_para_treinamento():
    """Função principal para exportar dados para treinamento."""
    exporter = DatasetExporter()
    
    # 1. Exportar dataset
    resultado_export = exporter.exportar_dataset_treinamento(formato="jsonl")
    
    # 2. Analisar viabilidade
    if resultado_export.get("sucesso"):
        analise = exporter.analisar_viabilidade_treinamento()
        return {
            "export": resultado_export,
            "analise": analise
        }
    
    return resultado_export


def executar_analise_viabilidade():
    """Executa análise de viabilidade do treinamento próprio."""
    exporter = DatasetExporter()
    return exporter.analisar_viabilidade_treinamento()


if __name__ == "__main__":
    # Exemplo de uso
    print("=== SAP Helpdesk - Análise de Treinamento de Modelo ===")
    
    # 1. Analisar viabilidade
    analise = executar_analise_viabilidade()
    
    if analise.get("sucesso", True):
        print("\n📈 Análise de Viabilidade:")
        print(json.dumps(analise, indent=2, ensure_ascii=False))
        
        # 2. Se recomendado, exportar dados
        if analise.get("recomendacao", {}).get("nivel_prioridade") == "ALTO":
            print("\n📤 Exportando dataset para treinamento...")
            export_result = exportar_para_treinamento()
            print(json.dumps(export_result, indent=2, ensure_ascii=False))
    else:
        print(f"❌ Erro na análise: {analise.get('erro', 'Desconhecido')}")