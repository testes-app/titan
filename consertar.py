import os

def find_vault():
    home = os.path.expanduser("~")
    paths_to_check = [
        os.path.join(home, "Desktop", "Cofre Terra Nova"),
        os.path.join(home, "OneDrive", "Desktop", "Cofre Terra Nova"),
        os.path.join(home, "OneDrive", "Area de Trabalho", "Cofre Terra Nova"),
        os.path.join(home, "Documents", "Cofre Terra Nova"),
        os.path.join(home, "OneDrive", "Documents", "Cofre Terra Nova")
    ]
    
    for p in paths_to_check:
        if os.path.exists(p):
            return p
            
    return r"C:\Users\Cornelio\Desktop\Cofre Terra Nova"

vault = find_vault()
print(f"Encontrado: {vault}")

with open("C:/TITAN/titan.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

with open("C:/TITAN/titan.py", "w", encoding="utf-8") as f:
    for line in lines:
        if line.startswith("VAULT_PATH"):
            # Usa barras normais para evitar erro de escape
            safe_vault = vault.replace("\\", "/")
            f.write(f'VAULT_PATH     = r"{safe_vault}"\n')
        elif "'calculadora': 'calc'" in line:
            f.write(line.replace("'calculadora': 'calc'", "'calculadora': 'calc.exe'"))
        else:
            f.write(line)
