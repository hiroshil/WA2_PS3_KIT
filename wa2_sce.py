# -*- coding: utf-8 -*-
import os
import sys
import subprocess
import argparse

def find_scetool() -> str:
    # Look in various directories
    script_dir = os.path.dirname(os.path.abspath(__file__))
    paths = [
        os.path.join(script_dir, "PS3_Projects", "tools", "scetool.exe"),
        os.path.join(script_dir, "tools", "scetool.exe"),
        os.path.join(script_dir, "bin", "scetool.exe"),
        os.path.join(script_dir, "..", "scetool.exe"),
        os.path.join(script_dir, "scetool.exe")
    ]
    for p in paths:
        if os.path.exists(p):
            return os.path.abspath(p)
            
    # Try system PATH
    import shutil
    p = shutil.which("scetool")
    if p:
        return p
        
    print("Error: scetool.exe not found in known paths.", file=sys.stderr)
    sys.exit(1)

def decrypt_eboot(eboot_bin: str, eboot_elf: str):
    scetool_path = find_scetool()
    scetool_dir = os.path.dirname(scetool_path)
    
    cmd = [
        scetool_path,
        "--decrypt",
        os.path.abspath(eboot_bin),
        os.path.abspath(eboot_elf)
    ]
    
    print(f"Running scetool decrypt: {' '.join(cmd)}")
    # Run with Cwd set to scetool directory so it finds keyfiles in ./data/
    result = subprocess.run(cmd, cwd=scetool_dir, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error: Decryption failed.\nStdout: {result.stdout}\nStderr: {result.stderr}", file=sys.stderr)
        sys.exit(1)
    print("EBOOT Decrypted successfully.")

def encrypt_eboot(eboot_elf: str, eboot_bin: str, npdrm: bool):
    scetool_path = find_scetool()
    scetool_dir = os.path.dirname(scetool_path)
    
    if npdrm:
        self_args = [
            "--self-type=NPDRM",
            "--np-license-type=FREE",
            "--np-app-type=UEXEC",
            "--np-content-id=JP0761-BLJM60571_00-GAMEUPDATE000002",
            "--np-real-fname=EBOOT.BIN"
        ]
    else:
        self_args = [
            "--self-type=APP"
        ]
        
    cmd = [
        scetool_path,
        "--sce-type=SELF",
    ] + self_args + [
        "--skip-sections=FALSE",
        "--key-revision=1c",
        "--self-auth-id=1010000001000003",
        "--self-vendor-id=01000002",
        "--self-app-version=0001000000000000",
        "--encrypt",
        os.path.abspath(eboot_elf),
        os.path.abspath(eboot_bin)
    ]
    
    print(f"Running scetool encrypt: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=scetool_dir, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error: Encryption failed.\nStdout: {result.stdout}\nStderr: {result.stderr}", file=sys.stderr)
        sys.exit(1)
    print("EBOOT Encrypted successfully.")

def main():
    parser = argparse.ArgumentParser(description="scetool wrapper for White Album 2 PS3 EBOOT decryption and encryption")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # Decrypt command
    dec_parser = subparsers.add_parser("decrypt", help="Decrypt EBOOT.BIN to EBOOT.ELF")
    dec_parser.add_argument("eboot_bin", help="Path to input EBOOT.BIN")
    dec_parser.add_argument("eboot_elf", help="Path to output decrypted EBOOT.ELF")
    
    # Encrypt command
    enc_parser = subparsers.add_parser("encrypt", help="Encrypt EBOOT.ELF to EBOOT.BIN")
    enc_parser.add_argument("eboot_elf", help="Path to input decrypted EBOOT.ELF")
    enc_parser.add_argument("eboot_bin", help="Path to output encrypted EBOOT.BIN")
    enc_parser.add_argument("--npdrm", action="store_true", help="Encrypt as NPDRM update executable")
    
    args = parser.parse_args()
    
    if args.command == "decrypt":
        decrypt_eboot(args.eboot_bin, args.eboot_elf)
    elif args.command == "encrypt":
        encrypt_eboot(args.eboot_elf, args.eboot_bin, args.npdrm)

if __name__ == "__main__":
    main()
