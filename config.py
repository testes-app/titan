# ============================================================
# TITAN v1.0.0  Configuraes do Sistema
# ============================================================
import os

#  Usurio 
import os
USUARIO_WINDOWS = "Cornelio"

# ── Obsidian Vault ───────────────────────────────────────────
# Busca automática no seu Desktop real
VAULT_PATH = os.path.join(os.path.expanduser("~"), "Desktop", "Cofre Terra Nova")

# Pasta dentro do vault para notas criadas pelo Titan
TITAN_NOTES_FOLDER = "Titan"

#  Voz 
# Idioma do reconhecimento de voz (pt-BR = Portugus Brasil)
IDIOMA_VOZ = "pt-BR"

# Velocidade da fala (padro: 180 palavras/minuto)
VELOCIDADE_FALA = 180

# Volume da fala (0.0 a 1.0)
VOLUME_FALA = 1.0

#  Interface 
# Ttulo da janela
TITULO_APP = " TITAN v1.0.0"

# Dimenses da janela
LARGURA_JANELA = 900
ALTURA_JANELA = 680

#  Palavras de Ativao 
PALAVRAS_ATIVACAO = ["titan", "tit", "jarvis"]

#  Cores do Tema 
CORES = {
    "bg_principal": "#0a0a0f",
    "bg_card": "#12121a",
    "bg_card_hover": "#1a1a2e",
    "bg_input": "#16162a",
    "borda": "#2a2a4a",
    "borda_ativa": "#6c5ce7",
    "accent_primario": "#6c5ce7",
    "accent_secundario": "#a855f7",
    "accent_gradient_start": "#6c5ce7",
    "accent_gradient_end": "#a855f7",
    "texto_principal": "#e8e8f0",
    "texto_secundario": "#8888aa",
    "texto_muted": "#555577",
    "sucesso": "#00d26a",
    "erro": "#ff4757",
    "aviso": "#ffa502",
    "info": "#00b4d8",
}
