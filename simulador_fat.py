import threading
import os

DB_FILE = "fat_db.txt"
GPWD    = 0
lock    = threading.Lock()


def inicializar_fat():
    if not os.path.exists(DB_FILE):
        with open(DB_FILE, "w") as f:
            f.write("0|/|DIR|-1|rwx|-\n")
        print("Sistema FAT inicializado correctamente.")
    else:
        print("Sistema FAT cargado desde archivo existente.")


def leer_registros():
    registros = []
    with open(DB_FILE, "r") as f:
        for linea in f:
            linea = linea.strip()
            if not linea:
                continue
            partes = linea.split("|")
            if len(partes) == 6:
                registros.append({
                    "id":       int(partes[0]),
                    "nombre":   partes[1],
                    "tipo":     partes[2],
                    "padre":    int(partes[3]),
                    "permisos": partes[4],
                    "tamaño":   partes[5],
                })
    return registros


def escribir_registros(registros):
    """Sobreescribe el archivo FAT con la lista de registros proporcionada."""
    with open(DB_FILE, "w") as f:
        for r in registros:
            linea = f"{r['id']}|{r['nombre']}|{r['tipo']}|{r['padre']}|{r['permisos']}|{r['tamaño']}\n"
            f.write(linea)
