import subprocess
import winreg
import ctypes

HIDDEN_PROCESS_FLAGS = 0x08000000

def is_admin():
    try:
        if bool(ctypes.windll.shell32.IsUserAnAdmin()):
            return True
    except Exception:
        pass
    try:
        result = subprocess.run(
            "net session",
            shell=True,
            capture_output=True,
            text=True,
            check=False,
            creationflags=HIDDEN_PROCESS_FLAGS,
        )
        return result.returncode == 0
    except Exception:
        return False

def disable_telemetry_all():
    """Отключение телеметрии и Cortana"""
    if not is_admin(): 
        return "❌ Ошибка безопасности (нужен запуск от Администратора)"
    try:
        path = r"SOFTWARE\Policies\Microsoft\Windows\DataCollection"
        key = winreg.CreateKey(winreg.HKEY_LOCAL_MACHINE, path)
        winreg.SetValueEx(key, "AllowTelemetry", 0, winreg.REG_DWORD, 0)
        winreg.CloseKey(key)
        
        # Остановка службы слежки
        subprocess.run(
            'sc config DiagTrack start=disabled',
            shell=True,
            capture_output=True,
            creationflags=HIDDEN_PROCESS_FLAGS,
        )
        subprocess.run(
            'sc stop DiagTrack',
            shell=True,
            capture_output=True,
            creationflags=HIDDEN_PROCESS_FLAGS,
        )
        
        return "🛡️ Приватность: Телеметрия и слежка отключены"
    except Exception as e: 
        return f"❌ Ошибка безопасности: {e}"