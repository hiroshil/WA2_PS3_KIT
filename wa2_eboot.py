# -*- coding: utf-8 -*-
import os
import sys
import struct
import json
import argparse
import codecs
from utils import wa2_elzma

EBOOT_OFFSET = 0x10000
WA2_EBOOT101_INDEX = 0x106EDC
YINFU_UNICODE = '\u266a' # Music char

# ==============================================================================
# Extract EBOOT Command
# ==============================================================================

def extract_eboot(eboot_path: str, output_dir: str, clean_mode: bool):
    print(f"Extracting EBOOT: {eboot_path} -> {output_dir} (Clean Mode: {clean_mode})")
    
    eboot_dir = os.path.join(output_dir, "eboot")
    os.makedirs(eboot_dir, exist_ok=True)
    
    with open(eboot_path, "rb") as f:
        eboot_data = f.read()
        
    if len(eboot_data) < WA2_EBOOT101_INDEX or eboot_data[0:4] != b"\x7FELF":
        print("Error: Invalid EBOOT.ELF file.", file=sys.stderr)
        sys.exit(1)
        
    pos = WA2_EBOOT101_INDEX
    meta_entries = []
    
    while True:
        entry = eboot_data[pos:pos+16]
        name_offset, data_offset, uncomp_size, block_size = struct.unpack(">4I", entry)
        if name_offset == 0:
            break
            
        # Extract name
        cpos = name_offset - EBOOT_OFFSET
        name_bytes = bytearray()
        while True:
            c = eboot_data[cpos]
            if c == 0:
                break
            name_bytes.append(c)
            cpos += 1
        name = name_bytes.decode('ascii')
        
        # Normalize name
        norm_name = name
        if norm_name[-4:-3] == '_':
            norm_name = norm_name[:-4] + '.' + norm_name[-3:]
            
        print(f"File: {norm_name} (compressed={block_size}, uncompressed={uncomp_size})")
        
        # Extract payload
        cpos = data_offset - EBOOT_OFFSET
        comp_payload = eboot_data[cpos:cpos+uncomp_size]
        
        # Decompress
        decomp_payload = wa2_elzma.decompress_data(comp_payload)
        
        # Decide if we write this file
        is_txt = norm_name.endswith(".txt")
        
        if not clean_mode or is_txt:
            # Write decompressed file
            if clean_mode and is_txt:
                # Convert to UTF-16
                text = decomp_payload.decode('cp932', errors='replace')
                out_path = os.path.join(eboot_dir, norm_name)
                with codecs.open(out_path, "w", encoding="utf-16") as out_f:
                    out_f.write(text)
            else:
                # Write raw binary file
                out_path = os.path.join(eboot_dir, norm_name)
                with open(out_path, "wb") as out_f:
                    out_f.write(decomp_payload)
                    
        meta_entries.append({
            "name": name,
            "norm_name": norm_name,
            "uncomp_size": uncomp_size,
            "block_size": block_size,
            "data_offset": data_offset,
            "name_offset": name_offset
        })
        
        pos += 16
        
    # Write metadata file
    meta_path = os.path.join(output_dir, "eboot_meta.json")
    with open(meta_path, "w", encoding="utf-8") as meta_f:
        json.dump({
            "mode": "clean" if clean_mode else "raw",
            "files": meta_entries
        }, meta_f, indent=2)
        
    print("EBOOT Extraction completed successfully.")

# ==============================================================================
# Inject EBOOT Command
# ==============================================================================

def inject_eboot(in_eboot: str, out_eboot: str, input_dir: str):
    print(f"Injecting into EBOOT: {out_eboot} from template {in_eboot} with files from {input_dir}")
    
    meta_path = os.path.join(input_dir, "eboot_meta.json")
    if not os.path.exists(meta_path):
        print(f"Error: metadata file '{meta_path}' not found.", file=sys.stderr)
        sys.exit(1)
        
    with open(meta_path, "r", encoding="utf-8") as meta_f:
        meta_data = json.load(meta_f)
        
    clean_mode = False
    if "mode" in meta_data:
        clean_mode = meta_data["mode"] == "clean"
    files = meta_data["files"]
    
    with open(in_eboot, "rb") as f:
        eboot_data = f.read()
        eboot_buf = bytearray(eboot_data)
        
    pos = WA2_EBOOT101_INDEX
    cur_pos = 0
    end_pos = 0
    
    for i, file_info in enumerate(files):
        name = file_info["name"]
        norm_name = file_info["norm_name"]
        orig_uncomp = file_info["uncomp_size"]
        orig_block = file_info["block_size"]
        orig_offset = file_info["data_offset"]
        
        # Read next entry's offset to know space limit
        next_offset = 0
        if i + 1 < len(files):
            next_offset = files[i+1]["data_offset"]
            
        total_block = orig_block
        if next_offset > 0:
            total_block = next_offset - orig_offset
            
        end_pos = orig_offset - EBOOT_OFFSET + total_block
        
        # Align write position
        if cur_pos == 0:
            cur_pos = orig_offset - EBOOT_OFFSET
        else:
            aligned_pos = (cur_pos + 63) & ~63
            if aligned_pos > cur_pos:
                eboot_buf[cur_pos:aligned_pos] = b"\x00" * (aligned_pos - cur_pos)
            cur_pos = aligned_pos
            
        # Check for modified file
        payload_written = False
        new_uncomp = orig_uncomp
        new_comp = orig_block
        
        mod_txt_path = os.path.join(input_dir, "eboot", norm_name)
        mod_elzma_path = os.path.join(input_dir, "eboot", norm_name + ".elzma")

        # 1. Try clean mode translated .txt
        if clean_mode and norm_name.endswith(".txt") and os.path.exists(mod_txt_path):
            with open(mod_txt_path, "rb") as f:
                mod_data = f.read()
            if mod_data.startswith(b'\xff\xfe'):
                text_content = mod_data.decode("utf-16")
            elif mod_data.startswith(b'\xfe\xff'):
                text_content = mod_data.decode("utf-16-be")
            elif mod_data.startswith(b'\xef\xbb\xbf'):
                text_content = mod_data.decode("utf-8-sig")
            else:
                try:
                    text_content = mod_data.decode("utf-8")
                except UnicodeDecodeError:
                    text_content = mod_data.decode("cp932", errors="replace")
            # Replace custom music note unicode and encode to CP932
            text_content = text_content.replace('\u4f93', '♪')
            mapped_bytes = text_content.encode('cp932', errors='replace')
            new_uncomp = len(mapped_bytes)
            # Compress
            comp_data = wa2_elzma.compress_data(mapped_bytes)
            payload = comp_data[4:] # Strip 4-byte prefix
            new_comp = len(payload)
            
            eboot_buf[cur_pos:cur_pos+new_comp] = payload
            payload_written = True
            print(f"Injecting modified text: {norm_name} ({orig_uncomp}->{new_uncomp} bytes)")
            
        # 2. Try raw mode modified .elzma file
        elif not clean_mode and os.path.exists(mod_elzma_path):
            with open(mod_elzma_path, "rb") as f:
                comp_file_data = f.read()
            new_uncomp = struct.unpack("<I", comp_file_data[0:4])[0]
            payload = comp_file_data[4:]
            new_comp = len(payload)
            
            eboot_buf[cur_pos:cur_pos+new_comp] = payload
            payload_written = True
            print(f"Injecting modified elzma: {norm_name} ({orig_block}->{new_comp} bytes)")
            
        # 3. Fallback: Copy original compressed payload from EBOOT.ELF itself
        if not payload_written:
            orig_payload_off = orig_offset - EBOOT_OFFSET
            payload = eboot_data[orig_payload_off:orig_payload_off+orig_block]
            
            eboot_buf[cur_pos:cur_pos+orig_block] = payload
            new_uncomp = orig_uncomp
            new_comp = orig_block
            payload_written = True
            
        # Update EBOOT index entry: offset, uncompressed size, compressed size
        eboot_buf[pos+4:pos+16] = struct.pack(">3I", cur_pos + EBOOT_OFFSET, new_uncomp, new_comp)
        
        # Advance write position
        cur_pos += new_comp
        pos += 16
        
    # The warning PNG starts at absolute file offset 0x660040. We can safely grow payloads into the padding before it.
    max_payload_limit = 0x660040
    if cur_pos > max_payload_limit:
        print(f"Error: Injection failed. New size exceeds ELF limit! ({cur_pos} > {max_payload_limit})", file=sys.stderr)
        sys.exit(1)
        
    print(f"Check ELF Ok: {cur_pos} <= {max_payload_limit}")
    
    # Save back to file
    with open(out_eboot, "wb") as f:
        f.write(eboot_buf)
        
    print("EBOOT Injection completed successfully.")

# ==============================================================================
# Patch EBOOT Command
# ==============================================================================

def patch_eboot(eboot_path: str, charset_num: int, font2_bin_path: str, font2_num: int, warning_png_path: str):
    with open(eboot_path, "rb") as f:
        buf = bytearray(f.read())
        
    with open(font2_bin_path, "rb") as f:
        buf2 = f.read()
        
    # Patch Font 1 Size & Address
    FONT1_POS = 0xfedf0
    FONT1_SIZE = 0x1524
    PATCH_FONT_POS = 0x120d00
    
    # Copy original font 1 to patch location
    buf[PATCH_FONT_POS:PATCH_FONT_POS+FONT1_SIZE] = buf[FONT1_POS:FONT1_POS+FONT1_SIZE]
    
    pos = PATCH_FONT_POS + FONT1_SIZE
    font_num = charset_num - FONT1_SIZE // 2
    font_code = 0xf043
    
    while font_num > 0:
        if (font_code & 0xff) < 0x40:
            font_code += 1
            continue
        buf[pos:pos+2] = struct.pack(">H", font_code)
        font_code += 1
        font_num -= 1
        pos += 2
        
    print(f"Total charset {charset_num}, end {hex(font_code)}")
    
    # Patch Font Size 1
    PATCH_FONT_SIZE_POS = 0xca2a
    opcode = struct.unpack(">H", buf[PATCH_FONT_SIZE_POS:PATCH_FONT_SIZE_POS+2])[0]
    if opcode != 0xa92:
        print("Error: Bad ELF magic for Font 1 size patch.", file=sys.stderr)
        sys.exit(1)
    buf[PATCH_FONT_SIZE_POS:PATCH_FONT_SIZE_POS+2] = struct.pack(">H", charset_num)
    print(f"Patched Font 1 size to {charset_num}")
    
    # Patch Font Address 1
    PATCH_FONT_ADDRESS = 0xcaa4
    if buf[PATCH_FONT_ADDRESS:PATCH_FONT_ADDRESS+8] != b"\x3C\x60\x00\x11\x30\x63\xED\xF0":
        print("Error: Bad ELF magic for Font 1 address patch.", file=sys.stderr)
        sys.exit(1)
    buf[PATCH_FONT_ADDRESS:PATCH_FONT_ADDRESS+8] = b"\x3C\x60\x00\x13\x30\x63\x0D\x00"
    print(f"Patched Font 1 address to {hex(PATCH_FONT_POS)}")
    
    # Patch Font 2 Size
    PATCH_FONT_SIZE_POS2 = 0xca12
    opcode = struct.unpack(">H", buf[PATCH_FONT_SIZE_POS2:PATCH_FONT_SIZE_POS2+2])[0]
    if opcode != 0x70:
        print("Error: Bad ELF magic for Font 2 size patch.", file=sys.stderr)
        sys.exit(1)
    buf[PATCH_FONT_SIZE_POS2:PATCH_FONT_SIZE_POS2+2] = struct.pack(">H", font2_num)
    print(f"Patched Font 2 size to {font2_num}")
    
    # Patch Font 2 Address
    PATCH_FONT_ADDRESS2 = 0xcba0
    PATCH_FONT_POS2 = 0x122c00
    if buf[PATCH_FONT_ADDRESS2:PATCH_FONT_ADDRESS2+8] != b"\x3C\x60\x00\x11\x30\x63\x03\x15":
        print("Error: Bad ELF magic for Font 2 address patch.", file=sys.stderr)
        sys.exit(1)
    buf[PATCH_FONT_ADDRESS2:PATCH_FONT_ADDRESS2+8] = b"\x3C\x60\x00\x13\x30\x63\x2c\x00"
    print(f"Patched Font 2 address to {hex(PATCH_FONT_POS2)}")
    buf[PATCH_FONT_POS2:PATCH_FONT_POS2+len(buf2)] = buf2
    
    # Patch Load Size
    LOAD_POS = 0x64
    LOAD_NEW_SIZE = 0x12B000
    opcode = struct.unpack(">I", buf[LOAD_POS:LOAD_POS+4])[0]
    if opcode != 0x120CE8:
        print("Error: Wrong ELF load size.", file=sys.stderr)
        sys.exit(1)
    buf[LOAD_POS:LOAD_POS+4] = struct.pack(">I", LOAD_NEW_SIZE)
    buf[LOAD_POS+8:LOAD_POS+12] = struct.pack(">I", LOAD_NEW_SIZE)
    print(f"Patched ELF load size to {hex(LOAD_NEW_SIZE)}")
    
    # Patch Section Size
    SECTION_POS = 0x6ccc2c
    SECTION_NEW_SIZE = 0xA358
    opcode = struct.unpack(">I", buf[SECTION_POS:SECTION_POS+4])[0]
    if opcode != 0x40:
        print("Error: Wrong ELF section size.", file=sys.stderr)
        sys.exit(1)
    buf[SECTION_POS:SECTION_POS+4] = struct.pack(">I", SECTION_NEW_SIZE)
    print(f"Patched ELF section size to {hex(SECTION_NEW_SIZE)}")
    
    # Patch Warning PNG
    with open(warning_png_path, "rb") as f:
        png_data = f.read()
    png_size = len(png_data) - 4
    PNG_WARNING_POS = 0x660040
    PNG_WARNING_SIZE = 0x2BA00
    if png_size > PNG_WARNING_SIZE:
        print(f"Error: Warning PNG size too large ({png_size} > {PNG_WARNING_SIZE})", file=sys.stderr)
        sys.exit(1)
    buf[PNG_WARNING_POS:PNG_WARNING_POS+png_size] = png_data[4:]
    print("Patched warning.png")
    
    # Save back to file
    with open(eboot_path, "wb") as f:
        f.write(buf)
        
    print("EBOOT Patched successfully.")

# ==============================================================================
# CLI Entry point
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(description="White Album 2 PS3 EBOOT.ELF Extractor and Injector")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # extract
    ext_parser = subparsers.add_parser("extract", help="Extract files from EBOOT.ELF")
    ext_parser.add_argument("eboot_file", help="Path to EBOOT.ELF")
    ext_parser.add_argument("output_dir", help="Output directory")
    ext_parser.add_argument("--clean", action="store_true", help="Extract in clean translation mode (only dialogue TXT files)")
    
    # inject
    inj_parser = subparsers.add_parser("inject", help="Inject modified files back into EBOOT.ELF")
    inj_parser.add_argument("in_eboot", help="Path to input original EBOOT.ELF template")
    inj_parser.add_argument("out_eboot", help="Path to output modified EBOOT.ELF")
    inj_parser.add_argument("input_dir", help="Directory containing modified files")
    
    # patch
    pat_parser = subparsers.add_parser("patch", help="Patch EBOOT.ELF font and warning data")
    pat_parser.add_argument("eboot_file", help="Path to EBOOT.ELF")
    pat_parser.add_argument("charset_num", type=int, help="Charset count")
    pat_parser.add_argument("font2_bin", help="Path to font2.bin")
    pat_parser.add_argument("font2_num", type=int, help="Font2 size")
    pat_parser.add_argument("warning_png", help="Path to warning.png")
    
    args = parser.parse_args()
    
    if args.command == "extract":
        extract_eboot(args.eboot_file, args.output_dir, args.clean)
    elif args.command == "inject":
        inject_eboot(args.in_eboot, args.out_eboot, args.input_dir)
    elif args.command == "patch":
        patch_eboot(args.eboot_file, args.charset_num, args.font2_bin, args.font2_num, args.warning_png)

if __name__ == "__main__":
    main()
