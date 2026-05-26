# ============================================================
# TITAN v1.0.0  Mdulo de Processamento de Comandos
# ============================================================
import os
import sys
import webbrowser
import subprocess
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import PALAVRAS_ATIVACAO


class ProcessadorComandos:
    """Processa comandos de texto/voz e executa aes."""

    def __init__(self, obsidian_manager=None):
        self.obsidian = obsidian_manager
        self.historico = []

    def processar(self, texto: str) -> dict:
        """
        Processa um comando de texto e retorna a resposta.
        
        Returns:
            dict com 'resposta', 'acao' e 'dados'
        """
        texto_lower = texto.lower().strip()
        
        # Registrar no histrico
        self.historico.append({
            "hora": datetime.now().strftime("%H:%M:%S"),
            "comando": texto
        })

        #  Saudaes 
        if any(p in texto_lower for p in ["ol", "oi", "eai", "e a", "bom dia", "boa tarde", "boa noite", "hey"]):
            hora = datetime.now().hour
            if hora < 12:
                saudacao = "Bom dia"
            elif hora < 18:
                saudacao = "Boa tarde"
            else:
                saudacao = "Boa noite"
            return self._resposta(
                f"{saudacao}! Eu sou o TITAN, seu assistente pessoal. Como posso ajudar?",
                "saudacao"
            )

        #  Hora e Data 
        if any(p in texto_lower for p in ["que horas", "hora agora", "que hora"]):
            agora = datetime.now().strftime("%H:%M")
            return self._resposta(f"Agora so {agora}.", "hora")

        if any(p in texto_lower for p in ["que dia", "data de hoje", "dia hoje"]):
            hoje = datetime.now().strftime("%d de %B de %Y")
            return self._resposta(f"Hoje  {hoje}.", "data")

        #  Obsidian: Criar Nota 
        if any(p in texto_lower for p in ["criar nota", "cria nota", "nova nota", "anotar", "anota"]):
            return self._cmd_criar_nota(texto)

        #  Obsidian: Dirio 
        if any(p in texto_lower for p in ["dirio", "diario", "registro do dia"]):
            return self._cmd_diario(texto)

        #  Obsidian: Tarefa 
        if any(p in texto_lower for p in ["criar tarefa", "nova tarefa", "adicionar tarefa", "tarefa"]):
            return self._cmd_tarefa(texto)

        #  Obsidian: Ideia 
        if any(p in texto_lower for p in ["ideia", "idia", "tive uma ideia"]):
            return self._cmd_ideia(texto)

        #  Obsidian: Listar Notas 
        if any(p in texto_lower for p in ["listar notas", "minhas notas", "mostrar notas"]):
            return self._cmd_listar_notas()

        #  Obsidian: Buscar 
        if any(p in texto_lower for p in ["buscar nota", "procurar nota", "encontrar nota"]):
            return self._cmd_buscar_nota(texto)

        #  Abrir Site 
        if any(p in texto_lower for p in ["abrir youtube", "abre youtube"]):
            webbrowser.open("https://www.youtube.com")
            return self._resposta("Abrindo YouTube!", "web")

        if any(p in texto_lower for p in ["abrir google", "abre google"]):
            webbrowser.open("https://www.google.com")
            return self._resposta("Abrindo Google!", "web")

        if "pesquisar" in texto_lower or "pesquisa" in texto_lower:
            termo = texto_lower.replace("pesquisar", "").replace("pesquisa", "").strip()
            if termo:
                webbrowser.open(f"https://www.google.com/search?q={termo}")
                return self._resposta(f"Pesquisando por '{termo}' no Google!", "web")

        #  Sistema 
        if any(p in texto_lower for p in ["abrir calculadora", "calculadora"]):
            subprocess.Popen("calc")
            return self._resposta("Abrindo a calculadora!", "sistema")

        if any(p in texto_lower for p in ["abrir bloco de notas", "notepad", "bloco de notas"]):
            subprocess.Popen("notepad")
            return self._resposta("Abrindo o Bloco de Notas!", "sistema")

        if any(p in texto_lower for p in ["abrir explorador", "explorador de arquivos"]):
            subprocess.Popen("explorer")
            return self._resposta("Abrindo o Explorador de Arquivos!", "sistema")

        #  Status do Sistema 
        if any(p in texto_lower for p in ["status", "como voc est", "como esta"]):
            return self._cmd_status()

        #  Ajuda 
        if any(p in texto_lower for p in ["ajuda", "help", "comandos", "o que voc faz"]):
            return self._cmd_ajuda()

        #  Histrico 
        if any(p in texto_lower for p in ["histrico", "historico", "ltimos comandos"]):
            return self._cmd_historico()

        #  Encerrar 
        if any(p in texto_lower for p in ["sair", "encerrar", "fechar", "desligar", "tchau"]):
            return self._resposta("At logo! Foi bom ajudar. ", "encerrar")

        #  Comando no reconhecido 
        return self._resposta(
            f"No entendi o comando. Diga 'ajuda' para ver o que posso fazer!",
            "desconhecido"
        )

    # 
    #  Comandos Obsidian
    # 

    def _cmd_criar_nota(self, texto: str) -> dict:
        """Processa comando de criar nota."""
        if not self.obsidian:
            return self._resposta("Obsidian no configurado.", "erro")
        
        # Extrair contedo do comando
        for prefix in ["criar nota", "cria nota", "nova nota", "anotar", "anota"]:
            if prefix in texto.lower():
                conteudo = texto[texto.lower().index(prefix) + len(prefix):].strip()
                break
        else:
            conteudo = texto

        if not conteudo:
            return self._resposta(
                "O que voc quer anotar? Diga: 'criar nota [seu contedo]'",
                "aguardando"
            )

        # Gerar ttulo automtico
        titulo = conteudo[:50].strip()
        resultado = self.obsidian.criar_nota(titulo, conteudo)
        
        if resultado["sucesso"]:
            return self._resposta(f" {resultado['mensagem']}", "obsidian_nota")
        else:
            return self._resposta(f" {resultado['mensagem']}", "erro")

    def _cmd_diario(self, texto: str) -> dict:
        """Adiciona entrada ao dirio."""
        if not self.obsidian:
            return self._resposta("Obsidian no configurado.", "erro")
        
        for prefix in ["dirio", "diario", "registro do dia"]:
            if prefix in texto.lower():
                conteudo = texto[texto.lower().index(prefix) + len(prefix):].strip()
                break
        else:
            conteudo = texto

        if not conteudo:
            return self._resposta(
                "O que quer registrar no dirio? Diga: 'dirio [seu registro]'",
                "aguardando"
            )

        resultado = self.obsidian.criar_nota_diario(conteudo)
        
        if resultado["sucesso"]:
            return self._resposta(f" {resultado['mensagem']}", "obsidian_diario")
        else:
            return self._resposta(f" {resultado['mensagem']}", "erro")

    def _cmd_tarefa(self, texto: str) -> dict:
        """Cria uma tarefa."""
        if not self.obsidian:
            return self._resposta("Obsidian no configurado.", "erro")
        
        for prefix in ["criar tarefa", "nova tarefa", "adicionar tarefa", "tarefa"]:
            if prefix in texto.lower():
                conteudo = texto[texto.lower().index(prefix) + len(prefix):].strip()
                break
        else:
            conteudo = texto

        if not conteudo:
            return self._resposta(
                "Qual  a tarefa? Diga: 'tarefa [descrio]'",
                "aguardando"
            )

        # Detectar prioridade
        prioridade = "normal"
        if "urgente" in conteudo.lower() or "alta" in conteudo.lower():
            prioridade = "alta"
        elif "baixa" in conteudo.lower():
            prioridade = "baixa"

        resultado = self.obsidian.criar_nota_tarefa(conteudo, prioridade)
        
        if resultado["sucesso"]:
            return self._resposta(f" {resultado['mensagem']}", "obsidian_tarefa")
        else:
            return self._resposta(f" {resultado['mensagem']}", "erro")

    def _cmd_ideia(self, texto: str) -> dict:
        """Registra uma ideia."""
        if not self.obsidian:
            return self._resposta("Obsidian no configurado.", "erro")
        
        for prefix in ["ideia", "idia", "tive uma ideia"]:
            if prefix in texto.lower():
                conteudo = texto[texto.lower().index(prefix) + len(prefix):].strip()
                break
        else:
            conteudo = texto

        if not conteudo:
            return self._resposta(
                "Qual  a ideia? Diga: 'ideia [descrio]'",
                "aguardando"
            )

        resultado = self.obsidian.criar_nota_ideia(conteudo)
        
        if resultado["sucesso"]:
            return self._resposta(f" {resultado['mensagem']}", "obsidian_ideia")
        else:
            return self._resposta(f" {resultado['mensagem']}", "erro")

    def _cmd_listar_notas(self) -> dict:
        """Lista notas do Titan."""
        if not self.obsidian:
            return self._resposta("Obsidian no configurado.", "erro")
        
        notas = self.obsidian.listar_notas()
        if not notas:
            return self._resposta(" Nenhuma nota encontrada.", "obsidian_listar")
        
        lista = " **Suas notas:**\n\n"
        for i, nota in enumerate(notas[:15], 1):
            lista += f"  {i}. {nota.replace('.md', '')}\n"
        
        if len(notas) > 15:
            lista += f"\n  ... e mais {len(notas) - 15} notas"
        
        return self._resposta(lista, "obsidian_listar")

    def _cmd_buscar_nota(self, texto: str) -> dict:
        """Busca notas."""
        if not self.obsidian:
            return self._resposta("Obsidian no configurado.", "erro")
        
        for prefix in ["buscar nota", "procurar nota", "encontrar nota"]:
            if prefix in texto.lower():
                termo = texto[texto.lower().index(prefix) + len(prefix):].strip()
                break
        else:
            termo = texto

        if not termo:
            return self._resposta(
                "O que quer buscar? Diga: 'buscar nota [termo]'",
                "aguardando"
            )

        resultados = self.obsidian.buscar_notas(termo)
        if not resultados:
            return self._resposta(f" Nenhuma nota encontrada para '{termo}'.", "obsidian_buscar")
        
        lista = f" **Resultados para '{termo}':**\n\n"
        for i, nota in enumerate(resultados[:10], 1):
            lista += f"  {i}. {nota.replace('.md', '')}\n"
        
        return self._resposta(lista, "obsidian_buscar")

    # 
    #  Comandos do Sistema
    # 

    def _cmd_status(self) -> dict:
        """Retorna status do TITAN."""
        vault_status = "Desconectado"
        notas_count = 0
        if self.obsidian:
            info = self.obsidian.verificar_vault()
            vault_status = " Conectado" if info["existe"] else " No encontrado"
            notas_count = info.get("notas_titan", 0)
        
        status = " **TITAN v1.0.0  Status**\n\n"
        status += f"   Sistema: Online\n"
        status += f"   Obsidian: {vault_status}\n"
        status += f"   Notas Titan: {notas_count}\n"
        status += f"   Sesso: {len(self.historico)} comandos\n"
        status += f"   {datetime.now().strftime('%d/%m/%Y %H:%M')}\n"
        
        return self._resposta(status, "status")

    def _cmd_ajuda(self) -> dict:
        """Mostra comandos disponveis."""
        ajuda = " **Comandos TITAN v1.0.0**\n\n"
        ajuda += "  ** Obsidian:**\n"
        ajuda += "     'criar nota [contedo]'\n"
        ajuda += "     'dirio [registro]'\n"
        ajuda += "     'tarefa [descrio]'\n"
        ajuda += "     'ideia [descrio]'\n"
        ajuda += "     'listar notas'\n"
        ajuda += "     'buscar nota [termo]'\n\n"
        ajuda += "  ** Web:**\n"
        ajuda += "     'abrir youtube / google'\n"
        ajuda += "     'pesquisar [termo]'\n\n"
        ajuda += "  ** Sistema:**\n"
        ajuda += "     'calculadora / bloco de notas'\n"
        ajuda += "     'que horas so / que dia  hoje'\n"
        ajuda += "     'status / histrico'\n\n"
        ajuda += "  ** Voz:**\n"
        ajuda += "     Clique no  para falar\n"
        
        return self._resposta(ajuda, "ajuda")

    def _cmd_historico(self) -> dict:
        """Mostra histrico recente."""
        if not self.historico:
            return self._resposta(" Nenhum comando no histrico.", "historico")
        
        hist = " **ltimos comandos:**\n\n"
        for item in self.historico[-10:]:
            hist += f"  [{item['hora']}] {item['comando']}\n"
        
        return self._resposta(hist, "historico")

    # 
    #  Utilitrios
    # 

    def _resposta(self, texto: str, acao: str, dados: dict = None) -> dict:
        return {
            "resposta": texto,
            "acao": acao,
            "dados": dados or {}
        }
