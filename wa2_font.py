# -*- coding: utf-8 -*-
import os
import sys
import struct
import codecs
import argparse

def load_tbl(name: str) -> dict:
    tbl = {}
    with codecs.open(name, "r", encoding="utf-16") as f:
        for line in f:
            line = line.strip('\r\n')
            if not line or "=" not in line:
                continue
            code_str, char = line.split("=", 1)
            # Remove comments or handles if any
            if len(char) > 0:
                char = char[0]
            try:
                code = int(code_str, 16)
                tbl[char] = code
            except ValueError:
                continue
    return tbl

def load_tbl2(name: str) -> dict:
    tbl = {}
    with codecs.open(name, "r", encoding="utf-16") as f:
        for line in f:
            line = line.strip('\r\n')
            if not line or "=" not in line:
                continue
            code_str, char = line.split("=", 1)
            if len(char) > 0:
                char = char[0]
            try:
                code = int(code_str, 16)
                tbl[code] = char
            except ValueError:
                continue
    return tbl

def build_mini_font_tbl(txtname: str, tblname: str, output_name: str):
    print(f"Building mini font table from: text={txtname}, tbl={tblname} -> output={output_name}")
    
    tbl = load_tbl(tblname)
    tbl2 = load_tbl2(tblname)
    
    with codecs.open(txtname, "r", encoding="utf-16") as f:
        txt = f.read()
        
    mini_tbl = set()
    for char in txt:
        if char in tbl:
            mini_tbl.add(tbl[char])
        else:
            print(f"Warning: Char '{char}' not in character table.")
            
    sorted_codes = sorted(mini_tbl)
    
    mini_font_data = ""
    mini_font_bin = bytearray()
    
    for val in sorted_codes:
        if val in tbl2:
            mini_font_data += tbl2[val]
        else:
            mini_font_data += "?"
            
        if val < 0x80:
            mini_font_bin.extend(struct.pack("BB", val, 0x20))
        else:
            mini_font_bin.extend(struct.pack(">H", val))
            
    sorted_txt_path = output_name + "_sorted.txt"
    sorted_bin_path = output_name + "_sorted.bin"
    
    with codecs.open(sorted_txt_path, "w", encoding="utf-16") as f:
        f.write(mini_font_data)
        
    with open(sorted_bin_path, "wb") as f:
        f.write(mini_font_bin)
        
    print(f"Mini TBL sorted txt written to: {sorted_txt_path}")
    print(f"Mini TBL sorted bin written to: {sorted_bin_path}")

def extract_dds3(dds_path: str):
    print(f"Extracting DDS3 font channels from: {dds_path}")
    
    with open(dds_path, "rb") as f:
        data = f.read()
        
    if len(data) < 0x80:
        print("Error: Invalid DDS file size.", file=sys.stderr)
        sys.exit(1)
        
    height, width = struct.unpack("<II", data[0xc:0x14])
    print(f"DDS dimensions: {width}x{height}")
    
    cur = 0x80
    raw_r = bytearray()
    raw_g = bytearray()
    raw_b = bytearray()
    
    expected_limit = height * width * 2 + 0x80
    if len(data) < expected_limit:
        print(f"Error: DDS file payload smaller than expected ({len(data)} < {expected_limit})", file=sys.stderr)
        sys.exit(1)
        
    while cur < expected_limit:
        l1, h1, l2, h2 = struct.unpack("BBBB", data[cur:cur+4])
        g = ((l1 & 0xf0) | ((l2 & 0xf0) >> 4))
        b = (((l1 & 0x0f) << 4) | (l2 & 0x0f))
        r = (((h1 & 0x0f) << 4) | (h2 & 0x0f))
        
        raw_r.append(r)
        raw_g.append(g)
        raw_b.append(b)
        cur += 4
        
    r_path = dds_path + "_r.bin"
    g_path = dds_path + "_g.bin"
    b_path = dds_path + "_b.bin"
    
    with open(r_path, "wb") as f:
        f.write(raw_r)
    with open(g_path, "wb") as f:
        f.write(raw_g)
    with open(b_path, "wb") as f:
        f.write(raw_b)
        
    print(f"Extracted channels: {r_path}, {g_path}, {b_path}")

def make_dds3(dds_path: str, output_path: str):
    print(f"Composing DDS3 font channels: Template={dds_path} -> Output={output_path}")
    
    with open(dds_path, "rb") as f:
        data = f.read()
        
    if len(data) < 0x80:
        print("Error: Invalid template DDS file.", file=sys.stderr)
        sys.exit(1)
        
    height, width = struct.unpack("<II", data[0xc:0x14])
    if height != 128 or width != 512:
        print(f"Error: Bad size {width}x{height} (expected 512x128).", file=sys.stderr)
        sys.exit(1)
        
    r_path = dds_path + "_r.bin"
    g_path = dds_path + "_g.bin"
    b_path = dds_path + "_b.bin"
    
    if not (os.path.exists(r_path) and os.path.exists(g_path) and os.path.exists(b_path)):
        print(f"Error: Missing split channel bin files (_r.bin, _g.bin, _b.bin).", file=sys.stderr)
        sys.exit(1)
        
    with open(r_path, "rb") as f:
        data_r = f.read()
    with open(g_path, "rb") as f:
        data_g = f.read()
    with open(b_path, "rb") as f:
        data_b = f.read()
        
    raw = bytearray()
    cur = 0
    while cur < len(data_r):
        r = data_r[cur]
        g = data_g[cur]
        b = data_b[cur]
        
        l1 = (g & 0xf0) | (b >> 4)
        h1 = 0xf0 | (r >> 4)
        l2 = ((g & 0x0f) << 4) | (b & 0x0f)
        h2 = 0xf0 | (r & 0x0f)
        
        raw.extend(struct.pack("BBBB", l1, h1, l2, h2))
        cur += 1
        
    with open(output_path, "wb") as f:
        f.write(data[0:0x80] + raw)
        
    print(f"Composed DDS texture saved to: {output_path}")

def main():
    parser = argparse.ArgumentParser(description="White Album 2 PS3 Font texture and TBL processing utility")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # build-mini
    mini_parser = subparsers.add_parser("build-mini", help="Build a mini font table from a translated text file")
    mini_parser.add_argument("txt_file", help="Path to translated UTF-16 text file")
    mini_parser.add_argument("tbl_file", help="Path to character table (.tbl)")
    mini_parser.add_argument("output_name", help="Base path for output files")
    
    # extract-dds
    ex_parser = subparsers.add_parser("extract-dds", help="Split DDS3 font texture into R, G, B binary channels")
    ex_parser.add_argument("dds_file", help="Path to font texture DDS")
    
    # make-dds
    mk_parser = subparsers.add_parser("make-dds", help="Combine R, G, B channels back into a DDS3 font texture")
    mk_parser.add_argument("dds_file", help="Path to original template DDS")
    mk_parser.add_argument("output_dds", help="Path to output composed DDS")
    
    args = parser.parse_args()
    
    if args.command == "build-mini":
        build_mini_font_tbl(args.txt_file, args.tbl_file, args.output_name)
    elif args.command == "extract-dds":
        extract_dds3(args.dds_file)
    elif args.command == "make-dds":
        make_dds3(args.dds_file, args.output_dds)

if __name__ == "__main__":
    main()
