# ============================================================
# TITAN v1.0.0  Mdulo de Integrao com Obsidian
# ============================================================
import os
from datetime import datetime

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import VAULT_PATH, TITAN_NOTES_FOLDER


class ObsidianManager:
    """Gerencia a integrao com o Obsidian Vault."""

    def __init__(self, vault_path=None, notes_folder=None):
        self.vault_path = vault_path or VAULT_PATH
        self.notes_folder = notes_folder or TITAN_NOTES_FOLDER
        self.notes_dir = os.path.join(self.vault_path, self.notes_folder)
        self._garantir_pasta()

    def _garantir_pasta(self):
        """Tenta criar a pasta, mas no trava se falhar."""
        try:
            if not os.path.exists(self.vault_path):
                print(f"[Obsidian] Aviso: Vault nao encontrado em {self.vault_path}")
                return False
            
            os.makedirs(self.notes_dir, exist_ok=True)
            return True
        except Exception as e:
            print(f"[Obsidian] Nao foi possivel acessar/criar a pasta Titan: {e}")
            return False

    def criar_nota(self, titulo: str, conteudo: str, tags: list = None) -> dict:
        """
        Cria uma nota no Obsidian Vault.
        
        Args:
            titulo: Ttulo da nota
            conteudo: Contedo da nota em markdown
            tags: Lista de tags (opcional)
        
        Returns:
            dict com status e caminho do arquivo
        """
        try:
            # Limpar ttulo para nome de arquivo
            titulo_limpo = self._limpar_nome(titulo)
            arquivo = os.path.join(self.notes_dir, f"{titulo_limpo}.md")
            
            # Montar contedo com frontmatter
            now = datetime.now()
            frontmatter = "---\n"
            frontmatter += f"created: {now.strftime('%Y-%m-%d %H:%M:%S')}\n"
            frontmatter += f"source: TITAN v1.0.0\n"
            if tags:
                frontmatter += f"tags: [{', '.join(tags)}]\n"
            else:
                frontmatter += "tags: [titan, nota-automatica]\n"
            frontmatter += "---\n\n"
            
            nota_completa = frontmatter
            nota_completa += f"# {titulo}\n\n"
            nota_completa += conteudo + "\n\n"
            nota_completa += f"---\n"
            nota_completa += f"*Nota criada pelo TITAN em {now.strftime('%d/%m/%Y s %H:%M')}*\n"
            
            with open(arquivo, "w", encoding="utf-8") as f:
                f.write(nota_completa)
            
            return {
                "sucesso": True,
                "mensagem": f"Nota '{titulo}' criada com sucesso!",
                "caminho": arquivo
            }
        except Exception as e:
            return {
                "sucesso": False,
                "mensagem": f"Erro ao criar nota: {str(e)}",
                "caminho": None
            }

    def criar_nota_diario(self, conteudo: str) -> dict:
        """Cria ou atualiza a nota do dirio de hoje."""
        hoje = datetime.now()
        titulo = f"Dirio {hoje.strftime('%Y-%m-%d')}"
        
        arquivo = os.path.join(self.notes_dir, f"{titulo}.md")
        
        if os.path.exists(arquivo):
            # Adicionar ao dirio existente
            try:
                with open(arquivo, "a", encoding="utf-8") as f:
                    f.write(f"\n\n## {hoje.strftime('%H:%M')}\n\n{conteudo}\n")
                return {
                    "sucesso": True,
                    "mensagem": f"Entrada adicionada ao dirio de hoje!",
                    "caminho": arquivo
                }
            except Exception as e:
                return {
                    "sucesso": False,
                    "mensagem": f"Erro ao atualizar dirio: {str(e)}",
                    "caminho": None
                }
        else:
            return self.criar_nota(titulo, conteudo, tags=["diario", "titan"])

    def criar_nota_tarefa(self, tarefa: str, prioridade: str = "normal") -> dict:
        """Cria uma nota de tarefa no Obsidian."""
        emojis = {"alta": "", "normal": "", "baixa": ""}
        emoji = emojis.get(prioridade, "")
        
        titulo = f"Tarefa - {tarefa[:50]}"
        conteudo = f"## {emoji} Tarefa\n\n"
        conteudo += f"- [ ] **{tarefa}**\n\n"
        conteudo += f"**Prioridade:** {prioridade.capitalize()}\n"
        conteudo += f"**Status:** Pendente\n"
        
        return self.criar_nota(titulo, conteudo, tags=["tarefa", prioridade, "titan"])

    def criar_nota_ideia(self, ideia: str) -> dict:
        """Cria uma nota de ideia rpida."""
        titulo = f"Ideia - {ideia[:50]}"
        conteudo = f"##  Ideia\n\n{ideia}\n\n"
        conteudo += "### Prximos Passos\n\n- [ ] Desenvolver essa ideia\n"
        
        return self.criar_nota(titulo, conteudo, tags=["ideia", "titan"])

    def listar_notas(self) -> list:
        """Lista todas as notas criadas pelo Titan."""
        try:
            if not os.path.exists(self.notes_dir):
                return []
            notas = [f for f in os.listdir(self.notes_dir) if f.endswith(".md")]
            return sorted(notas, reverse=True)
        except Exception:
            return []

    def buscar_notas(self, termo: str) -> list:
        """Busca notas que contenham o termo no ttulo ou contedo."""
        resultados = []
        try:
            for nota in self.listar_notas():
                caminho = os.path.join(self.notes_dir, nota)
                with open(caminho, "r", encoding="utf-8") as f:
                    conteudo = f.read()
                if termo.lower() in nota.lower() or termo.lower() in conteudo.lower():
                    resultados.append(nota)
        except Exception:
            pass
        return resultados

    def _limpar_nome(self, nome: str) -> str:
        """Remove caracteres invlidos do nome do arquivo."""
        invalidos = '<>:"/\\|?*'
        for char in invalidos:
            nome = nome.replace(char, "")
        return nome.strip()

    def verificar_vault(self) -> dict:
        """Verifica se o vault est acessvel."""
        existe = os.path.exists(self.vault_path)
        return {
            "existe": existe,
            "caminho": self.vault_path,
            "notas_titan": len(self.listar_notas()) if existe else 0
        }
