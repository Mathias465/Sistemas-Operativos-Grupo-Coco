"""
Simulador de Sistema de Archivos tipo FAT en Python
Utiliza un archivo .txt como base de datos y threading para operaciones concurrentes.
"""

import threading
import os
import time
import stat
from datetime import datetime

#  CONFIGURACIÓN GLOBAL
DB_FILE = "filesystem.txt"   # Base de datos del sistema de archivos
GPWD    = "/"                # Directorio de trabajo actual (global)
lock    = threading.Lock()   # Mutex para acceso al archivo .txt

#  FORMATO DE REGISTRO EN filesystem.txt
#  tipo|ruta_completa|permisos|propietario|tamaño|fecha_modificacion
#  Ejemplo:
#  dir |/home             |755|root|0   |2024-01-01 00:00:00
#  file|/home/readme.txt  |644|root|1024|2024-01-01 00:00:00

FIELD_SEP = "|"
def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

#  OPERACIONES SOBRE filesystem.txt  (siempre con lock)

def _read_all():
    """Lee todos los registros del archivo de base de datos."""
    if not os.path.exists(DB_FILE):
        return []
    with open(DB_FILE, "r", encoding="utf-8") as f:
        lines = [l.rstrip("\n") for l in f if l.strip()]
    records = []
    for line in lines:
        parts = line.split(FIELD_SEP)
        if len(parts) == 6:
            records.append({
                "type": parts[0].strip(),
                "path": parts[1].strip(),
                "perms": parts[2].strip(),
                "owner": parts[3].strip(),
                "size":  parts[4].strip(),
                "mtime": parts[5].strip(),
            })
    return records

def _write_all(records):
    """Escribe todos los registros en el archivo de base de datos."""
    with open(DB_FILE, "w", encoding="utf-8") as f:
        for r in records:
            line = FIELD_SEP.join([
                r["type"].ljust(4),
                r["path"].ljust(30),
                r["perms"],
                r["owner"].ljust(8),
                r["size"].ljust(6),
                r["mtime"],
            ])
            f.write(line + "\n")

def _init_fs():
    """Inicializa el sistema de archivos con el directorio raíz."""
    with lock:
        records = _read_all()
        paths = [r["path"] for r in records]
        if "/" not in paths:
            records.insert(0, {
                "type":  "dir",
                "path":  "/",
                "perms": "755",
                "owner": "root",
                "size":  "0",
                "mtime": _now(),
            })
            _write_all(records)
            print("[init] Sistema de archivos inicializado con directorio raíz /")

#  UTILIDADES DE RUTAS
def _resolve(path):
    """Resuelve una ruta relativa o absoluta respecto a GPWD."""
    global GPWD
    if path.startswith("/"):
        resolved = path
    else:
        resolved = (GPWD.rstrip("/") + "/" + path) if GPWD != "/" else "/" + path
    # Normalizar: eliminar dobles barras y segmentos ".."
    parts = resolved.split("/")
    stack = []
    for p in parts:
        if p in ("", "."):
            continue
        if p == "..":
            if stack:
                stack.pop()
        else:
            stack.append(p)
    return "/" + "/".join(stack) if stack else "/"

def _parent(path):
    parts = path.rstrip("/").rsplit("/", 1)
    return parts[0] if parts[0] else "/"

def _perms_str(octal_str):
    """Convierte permisos octales '755' a formato rwxr-xr-x."""
    symbols = ""
    for digit in octal_str:
        d = int(digit)
        symbols += "r" if d & 4 else "-"
        symbols += "w" if d & 2 else "-"
        symbols += "x" if d & 1 else "-"
    return symbols

#  COMANDOS DEL SISTEMA DE ARCHIVOS
def cmd_pwd():
    """Muestra el directorio actual."""
    print(GPWD)

def cmd_ls(path=None, long=False):
    """Lista el contenido de un directorio."""
    global GPWD
    target = _resolve(path) if path else GPWD

    with lock:
        records = _read_all()

    # Verificar que el directorio existe
    dir_rec = next((r for r in records if r["path"] == target and r["type"] == "dir"), None)
    if not dir_rec:
        print(f"ls: no existe el directorio '{target}'")
        return

    # Hijos directos
    children = []
    for r in records:
        if r["path"] == target:
            continue
        parent = _parent(r["path"])
        if parent == target:
            children.append(r)

    if not children:
        print("(directorio vacío)")
        return

    if long:
        print(f"total {len(children)}")
        for c in children:
            tipo = "d" if c["type"] == "dir" else "-"
            perms = tipo + _perms_str(c["perms"])
            name = c["path"].rsplit("/", 1)[-1]
            print(f"{perms}  {c['owner']:<8}  {c['size']:>6} bytes  {c['mtime']}  {name}")
    else:
        names = []
        for c in children:
            name = c["path"].rsplit("/", 1)[-1]
            names.append(name + ("/" if c["type"] == "dir" else ""))
        print("  ".join(names))

def cmd_cd(path):
    """Cambia el directorio actual."""
    global GPWD
    if path == "~" or path == "":
        GPWD = "/"
        return

    target = _resolve(path)

    with lock:
        records = _read_all()

    exists = any(r["path"] == target and r["type"] == "dir" for r in records)
    if exists:
        GPWD = target
        print(f"Directorio actual: {GPWD}")
    else:
        print(f"cd: no existe el directorio '{target}'")

def cmd_mkdir(path):
    """Crea un nuevo directorio."""
    target = _resolve(path)

    with lock:
        records = _read_all()
        if any(r["path"] == target for r in records):
            print(f"mkdir: '{target}' ya existe")
            return
        # Verificar que el padre existe
        parent = _parent(target)
        if parent != target and not any(r["path"] == parent and r["type"] == "dir" for r in records):
            print(f"mkdir: directorio padre '{parent}' no existe")
            return
        records.append({
            "type":  "dir",
            "path":  target,
            "perms": "755",
            "owner": "user",
            "size":  "0",
            "mtime": _now(),
        })
        _write_all(records)
    print(f"Directorio '{target}' creado.")

def cmd_touch(path):
    """Crea un archivo vacio o actualiza su fecha de modificación."""
    target = _resolve(path)

    with lock:
        records = _read_all()
        existing = next((r for r in records if r["path"] == target), None)
        if existing:
            existing["mtime"] = _now()
            _write_all(records)
            print(f"touch: actualizado '{target}'")
        else:
            parent = _parent(target)
            if not any(r["path"] == parent and r["type"] == "dir" for r in records):
                print(f"touch: directorio padre '{parent}' no existe")
                return
            records.append({
                "type":  "file",
                "path":  target,
                "perms": "644",
                "owner": "user",
                "size":  "0",
                "mtime": _now(),
            })
            _write_all(records)
            print(f"Archivo '{target}' creado.")

def cmd_rm(path, recursive=False):
    """Elimina un archivo o directorio."""
    target = _resolve(path)

    with lock:
        records = _read_all()
        target_rec = next((r for r in records if r["path"] == target), None)
        if not target_rec:
            print(f"rm: no existe '{target}'")
            return

        if target_rec["type"] == "dir":
            children = [r for r in records if r["path"].startswith(target + "/") or r["path"] == target]
            if len(children) > 1 and not recursive:
                print(f"rm: '{target}' es un directorio. Usa rm -r para eliminar recursivamente.")
                return
            # Eliminar todo el árbol
            records = [r for r in records if not (r["path"] == target or r["path"].startswith(target + "/"))]
            print(f"Directorio '{target}' eliminado recursivamente." if recursive else f"Directorio vacío '{target}' eliminado.")
        else:
            records = [r for r in records if r["path"] != target]
            print(f"Archivo '{target}' eliminado.")

        _write_all(records)

def cmd_chmod(perms, path):
    """Cambia los permisos de un archivo o directorio."""
    # Validar permisos (deben ser 3 dígitos octales)
    if not (len(perms) == 3 and all(c in "01234567" for c in perms)):
        print(f"chmod: permisos inválidos '{perms}' (use formato octal, ej: 755)")
        return

    target = _resolve(path)

    with lock:
        records = _read_all()
        rec = next((r for r in records if r["path"] == target), None)
        if not rec:
            print(f"chmod: no existe '{target}'")
            return
        old = rec["perms"]
        rec["perms"] = perms
        rec["mtime"] = _now()
        _write_all(records)

    print(f"chmod: '{target}' permisos cambiados de {old} ({_perms_str(old)}) a {perms} ({_perms_str(perms)})")

#  OPERACIONES CONCURRENTES CON HILOS
def _worker(name, func, *args):
    """Función genérica para ejecutar un comando en un hilo."""
    print(f"\n[Hilo '{name}'] Iniciando: {func.__name__}{args}")
    time.sleep(0.1)  # Simula latencia de I/O
    func(*args)
    print(f"[Hilo '{name}'] Completado.")

def demo_concurrente():
    """
    Demuestra el uso de hilos concurrentes sobre el sistema de archivos.
    Varios hilos intentan crear, listar y modificar archivos al mismo tiempo.
    """
    print("\n" + "═"*60)
    print("  DEMOSTRACIÓN DE OPERACIONES CONCURRENTES CON HILOS")
    print("═"*60)

    # Estructura inicial
    cmd_mkdir("/concurrent_test")

    hilos = [
        threading.Thread(target=_worker, args=("T1", cmd_touch, "/concurrent_test/file_a.txt")),
        threading.Thread(target=_worker, args=("T2", cmd_touch, "/concurrent_test/file_b.txt")),
        threading.Thread(target=_worker, args=("T3", cmd_mkdir, "/concurrent_test/subdir")),
        threading.Thread(target=_worker, args=("T4", cmd_touch, "/concurrent_test/file_c.log")),
        threading.Thread(target=_worker, args=("T5", cmd_chmod, "600", "/concurrent_test/file_a.txt")),
    ]

    print(f"\n→ Lanzando {len(hilos)} hilos simultáneamente...\n")
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()

    print("\n→ Estado final del directorio /concurrent_test:")
    cmd_ls("/concurrent_test", long=True)

#  SHELL INTERACTIVO
HELP_TEXT = """
Comandos disponibles:
  pwd                  Muestra el directorio actual
  ls [ruta]            Lista archivos del directorio
  ls -l [ruta]         Lista con detalles (permisos, dueño, tamaño)
  cd <ruta>            Cambia de directorio
  mkdir <ruta>         Crea un directorio
  touch <ruta>         Crea un archivo vacío (o actualiza fecha)
  rm <ruta>            Elimina archivo o directorio vacío
  rm -r <ruta>         Elimina directorio y su contenido recursivamente
  chmod <perm> <ruta>  Cambia permisos (ej: chmod 755 /dir)
  demo                 Ejecuta demostración concurrente con hilos
  cat db               Muestra el contenido raw de filesystem.txt
  help                 Muestra esta ayuda
  exit / quit          Sale del simulador
"""

def cmd_cat_db():
    """Muestra el contenido raw de la base de datos."""
    print(f"\n{'─'*70}")
    print(f"  Contenido de '{DB_FILE}':")
    print(f"{'─'*70}")
    with lock:
        records = _read_all()
    for r in records:
        tipo  = "[DIR] " if r["type"] == "dir" else "[FILE]"
        perms = _perms_str(r["perms"])
        print(f"  {tipo} {r['path']:<35} {r['perms']} ({perms})  {r['owner']:<8}  {r['mtime']}")
    print(f"{'─'*70}\n")

def shell():
    global GPWD
    print("╔══════════════════════════════════════════════╗")
    print("║   Simulador FAT – Python + Threading         ║")
    print("║   Escribe 'help' para ver los comandos       ║")
    print("╚══════════════════════════════════════════════╝\n")

    _init_fs()

    while True:
        try:
            prompt = f"\033[1;32m{GPWD}\033[0m $ "
            line = input(prompt).strip()
        except (EOFError, KeyboardInterrupt):
            print("\nSaliendo...")
            break

        if not line:
            continue

        tokens = line.split()
        cmd = tokens[0]

        if cmd in ("exit", "quit"):
            print("Hasta luego.")
            break

        elif cmd == "help":
            print(HELP_TEXT)

        elif cmd == "pwd":
            cmd_pwd()

        elif cmd == "ls":
            long = "-l" in tokens
            paths = [t for t in tokens[1:] if t != "-l"]
            target = paths[0] if paths else None
            cmd_ls(target, long=long)

        elif cmd == "cd":
            if len(tokens) < 2:
                GPWD = "/"
            else:
                cmd_cd(tokens[1])

        elif cmd == "mkdir":
            if len(tokens) < 2:
                print("mkdir: falta el nombre del directorio")
            else:
                cmd_mkdir(tokens[1])

        elif cmd == "touch":
            if len(tokens) < 2:
                print("touch: falta el nombre del archivo")
            else:
                cmd_touch(tokens[1])

        elif cmd == "rm":
            recursive = "-r" in tokens
            paths = [t for t in tokens[1:] if t != "-r"]
            if not paths:
                print("rm: falta la ruta")
            else:
                cmd_rm(paths[0], recursive=recursive)

        elif cmd == "chmod":
            if len(tokens) < 3:
                print("chmod: uso: chmod <permisos> <ruta>")
            else:
                cmd_chmod(tokens[1], tokens[2])

        elif cmd == "demo":
            demo_concurrente()

        elif cmd == "cat" and len(tokens) > 1 and tokens[1] == "db":
            cmd_cat_db()

        else:
            print(f"Comando no reconocido: '{cmd}'. Escribe 'help'.")


#  PUNTO DE ENTRADA
if __name__ == "__main__":
    shell()
