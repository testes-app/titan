import winreg

def copy_voice():
    try:
        # Caminho da voz OneCore (escondida)
        src_path = r"SOFTWARE\Microsoft\Speech_OneCore\Voices\Tokens\MSTTS_V110_ptBR_DanielM"
        # Caminho da voz SAPI5 (visivel)
        dest_path = r"SOFTWARE\Microsoft\Speech\Voices\Tokens\MSTTS_V110_ptBR_DanielM"
        
        # Abre a fonte
        src_key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, src_path)
        
        # Cria o destino
        dest_key = winreg.CreateKey(winreg.HKEY_LOCAL_MACHINE, dest_path)
        
        # Copia valores
        info = winreg.QueryInfoKey(src_key)
        for i in range(info[1]):
            val = winreg.EnumValue(src_key, i)
            winreg.SetValueEx(dest_key, val[0], 0, val[2], val[1])
            
        # Copia sub-chaves (como Attributes)
        try:
            attr_src = winreg.OpenKey(src_key, "Attributes")
            attr_dest = winreg.CreateKey(dest_key, "Attributes")
            info_attr = winreg.QueryInfoKey(attr_src)
            for i in range(info_attr[1]):
                val = winreg.EnumValue(attr_src, i)
                winreg.SetValueEx(attr_dest, val[0], 0, val[2], val[1])
        except:
            pass
            
        print("Sucesso: Daniel destravado!")
    except Exception as e:
        print(f"Erro: {e}")

if __name__ == "__main__":
    copy_voice()
