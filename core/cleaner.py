import os
import shutil

def run_deep_clean():
    """Глубокая очистка временных файлов и кэша"""
    total_cleaned = 0
    folders = [
        os.environ.get('TEMP'), 
        r'C:\Windows\Temp', 
        r'C:\Windows\Prefetch',
        os.path.join(os.environ.get('LocalAppData', ''), r'NVIDIA\DXCache'),
        os.path.join(os.environ.get('LocalAppData', ''), r'Steam\htmlcache')
    ]
    
    for folder in folders:
        if not folder or not os.path.exists(folder): 
            continue
        try:
            for item in os.listdir(folder):
                path = os.path.join(folder, item)
                try:
                    size = os.path.getsize(path) if os.path.isfile(path) else 0
                    if os.path.isfile(path) or os.path.islink(path): 
                        os.unlink(path)
                    elif os.path.isdir(path): 
                        shutil.rmtree(path)
                    total_cleaned += size
                except Exception: 
                    continue
        except Exception: 
            continue
            
    return f"🧹 Глубокая очистка: {total_cleaned // (1024*1024)} MB удалено"