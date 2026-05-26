import winreg
import os

def unlock_daniel_user():
    try:
        # Fonte (Pasta do Sistema - Protegida)
        src_path = r"SOFTWARE\Microsoft\Speech_OneCore\Voices\Tokens\MSTTS_V110_ptBR_DanielM"
        # Destino (Pasta do Usuario - Liberada)
        dest_path = r"Software\Microsoft\Speech\Voices\Tokens\MSTTS_V110_ptBR_DanielM"
        
        # Abre a fonte no HKLM
        src_key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, src_path)
        
        # Cria no HKCU (Current User - Nao precisa de Admin!)
        dest_key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, dest_path)
        
        # Copia todos os valores (Nome, ID, etc)
        info = winreg.QueryInfoKey(src_key)
        for i in range(info[1]):
            val = winreg.EnumValue(src_key, i)
            winreg.SetValueEx(dest_key, val[0], 0, val[2], val[1])
            
        # Copia os Atributos (Genero, Idioma)
        try:
            attr_src = winreg.OpenKey(src_key, "Attributes")
            attr_dest = winreg.CreateKey(dest_key, "Attributes")
            info_attr = winreg.QueryInfoKey(attr_src)
            for i in range(info_attr[1]):
                val = winreg.EnumValue(attr_src, i)
                winreg.SetValueEx(attr_dest, val[0], 0, val[2], val[1])
        except:
            pass
            
        print("Sucesso! Daniel foi clonado para o seu usuario!")
    except Exception as e:
        print(f"Erro: {e}")

if __name__ == "__main__":
    unlock_daniel_user()
