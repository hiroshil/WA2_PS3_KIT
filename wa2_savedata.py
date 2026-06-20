# -*- coding: utf-8 -*-
import os
import sys
import struct
import mmap
import fnmatch
import argparse

def fix_savedata(save_dir: str):
    print(f"Fixing save data in directory: {save_dir}")
    
    sys_bin_path = os.path.join(save_dir, "SYS.BIN")
    if not os.path.exists(sys_bin_path):
        print(f"Error: SYS.BIN not found in '{save_dir}'.", file=sys.stderr)
        sys.exit(1)
        
    # Fix SYS.BIN
    with open(sys_bin_path, "r+b") as f:
        size = os.fstat(f.fileno()).st_size
        if size < 0x269480:
            print("Error: SYS.BIN size too small.", file=sys.stderr)
            sys.exit(1)
            
        buf = mmap.mmap(f.fileno(), size, access=mmap.ACCESS_WRITE)
        
        # Check header
        if buf[0:8] != b"\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF":
            print("Warning: SYS.BIN might be encrypted or invalid header.")
            
        fixed_sys_count = 0
        # Check save structs: size of each entry is 0x1258, total 100 entries
        for pos in range(0x269480, 0x269480 + 0x1258 * 100, 0x1258):
            if pos + 0x58 > size:
                break
            if buf[pos:pos+4] == b"\x00\x00\x00\x02":
                buf[pos+0x18:pos+0x58] = b"\x00" * 0x40
                fixed_sys_count += 1
                
        buf.close()
    print(f"SYS.BIN repaired (reset {fixed_sys_count} entries).")
    
    # Fix SAVE???.BIN
    zstr = b"\x00" * (0x8A358 - 0x46358)
    fixed_save_count = 0
    
    for directory, subdirectories, files in os.walk(save_dir):
        for file in files:
            if fnmatch.fnmatch(file, 'SAVE???.BIN'):
                save_path = os.path.join(directory, file)
                with open(save_path, "r+b") as f:
                    size = os.fstat(f.fileno()).st_size
                    if size < 0x8A358:
                        print(f"Warning: {file} size too small, skipping.")
                        continue
                        
                    buf = mmap.mmap(f.fileno(), size, access=mmap.ACCESS_WRITE)
                    
                    if buf[0:4] != b"\x00\x00\x00\x02":
                        print(f"Warning: {file} might be encrypted or invalid header.")
                        
                    buf[0x18:0x58] = b"\x00" * 0x40
                    buf[0x46358:0x8A358] = zstr
                    buf.close()
                fixed_save_count += 1
                print(f"Repaired save file: {file}")
                
    print(f"Save data cleanup finished. Repaired {fixed_save_count} SAVE???.BIN files.")

def main():
    parser = argparse.ArgumentParser(description="White Album 2 PS3 Save Data Fixer")
    parser.add_argument("save_dir", help="Path to save data folder (e.g. BLJM60571WA2)")
    args = parser.parse_args()
    
    fix_savedata(args.save_dir)

if __name__ == "__main__":
    main()
