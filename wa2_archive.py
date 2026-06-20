# -*- coding: utf-8 -*-
import os
import sys
import struct
import json
import argparse
from utils import wa2_elzma

def detect_extension(data: bytes) -> str:
    if len(data) < 16:
        return ".unknown"
    
    # Read first 16 bytes as little-endian ints
    magic1, magic2, magic3, magic4 = struct.unpack("<IIII", data[0:16])
    
    if magic1 == 0x67452301:
        return ".eg"
    elif magic1 == 0xFF010102:
        return ".gtf"
    elif magic1 == 0x53414E49:
        return ".inas"
    elif magic1 > 0 and magic2 == 0 and magic3 == 0 and magic4 == 0:
        return ".pkgdds"
    elif data.startswith(b"RIFF"):
        return ".at3"
    else:
        return ".unknown"

# ==============================================================================
# DAR Archive Commands
# ==============================================================================

def extract_dar(dar_path: str, output_dir: str):
    print(f"Extracting DAR: {dar_path} -> {output_dir}")
    os.makedirs(output_dir, exist_ok=True)
    
    with open(dar_path, "rb") as f:
        header = f.read(16)
        if len(header) < 16 or header[0:2] != b"\xac\x0d":
            print("Error: Bad DAR file magic.", file=sys.stderr)
            sys.exit(1)
            
        files_count = struct.unpack("<I", header[8:12])[0]
        print(f"Total files in DAR: {files_count}")
        
        # Read index table
        index_table = f.read(files_count * 32)
        
        meta_entries = []
        
        for i in range(files_count):
            entry_offset = i * 32
            entry_data = index_table[entry_offset:entry_offset+32]
            size, zsize, offset = struct.unpack("<LLQ", entry_data[0:16])
            meta_bytes = entry_data[16:32]
            
            # Read payload
            f.seek(offset)
            if zsize == 0:
                # Uncompressed
                payload = f.read(size)
                ext = ".at3" # Default uncompressed ext
                is_compressed = False
            else:
                # Compressed
                comp_data = f.read(zsize)
                is_compressed = True
                try:
                    payload = wa2_elzma.decompress_data(comp_data)
                    ext = detect_extension(payload)
                except Exception as e:
                    print(f"Warning: Failed to decompress file index {i}: {e}", file=sys.stderr)
                    payload = comp_data
                    ext = ".elzma"
                    
            out_name = f"{i:05d}{ext}"
            out_path = os.path.join(output_dir, out_name)
            
            with open(out_path, "wb") as out_f:
                out_f.write(payload)
                
            meta_entries.append({
                "index": i,
                "ext": ext,
                "meta": meta_bytes.hex(),
                "original_compressed": is_compressed
            })
            
        # Write metadata file
        meta_path = os.path.join(output_dir, "dar_meta.json")
        with open(meta_path, "w", encoding="utf-8") as meta_f:
            json.dump({
                "files_count": files_count,
                "entries": meta_entries
            }, meta_f, indent=2)
            
    print("DAR Extraction completed successfully.")

def repack_dar(dar_path: str, modified_dir: str, output_dar: str):
    print(f"Repacking DAR: Template={dar_path}, Modified={modified_dir} -> Output={output_dar}")
    
    meta_path = os.path.join(modified_dir, "dar_meta.json")
    if not os.path.exists(meta_path):
        print(f"Error: metadata file '{meta_path}' not found.", file=sys.stderr)
        sys.exit(1)
        
    with open(meta_path, "r", encoding="utf-8") as meta_f:
        meta_data = json.load(meta_f)
        
    files_count = meta_data["files_count"]
    entries = meta_data["entries"]
    
    orig_f = open(dar_path, "rb")
    out_f = open(output_dar, "wb+")
    
    # Write placeholder header and index table
    out_f.write(b"\x00" * (16 + files_count * 32))
    
    new_index_entries = []
    
    for entry in entries:
        i = entry["index"]
        ext = entry["ext"]
        meta_hex = entry["meta"]
        meta_bytes = bytes.fromhex(meta_hex)
        was_compressed = entry["original_compressed"]
        
        # Check for modified file
        mod_name_elzma = f"{i:05d}{ext}.elzma"
        mod_name_idx_elzma = f"{i:05d}.elzma"
        mod_name_raw = f"{i:05d}{ext}"
        
        payload_written = False
        size = 0
        zsize = 0
        offset = out_f.tell()
        
        # Try modified compressed .elzma file
        for name in [mod_name_elzma, mod_name_idx_elzma]:
            path = os.path.join(modified_dir, name)
            if os.path.exists(path):
                # Contains 4-byte size header
                with open(path, "rb") as mf:
                    comp_file_data = mf.read()
                size = struct.unpack("<I", comp_file_data[0:4])[0]
                payload = comp_file_data[4:]
                zsize = len(payload)
                out_f.write(payload)
                payload_written = True
                print(f"Repacking modified compressed index {i} ({name})")
                break
                
        # Try modified uncompressed file
        if not payload_written:
            path = os.path.join(modified_dir, mod_name_raw)
            if os.path.exists(path):
                with open(path, "rb") as mf:
                    raw_data = mf.read()
                size = len(raw_data)
                if was_compressed:
                    # Compress it
                    comp_data = wa2_elzma.compress_data(raw_data)
                    payload = comp_data[4:] # Strip 4-byte uncomp size
                    zsize = len(payload)
                    out_f.write(payload)
                    print(f"Repacking modified raw index {i} (compressed on-the-fly)")
                else:
                    # Keep uncompressed
                    zsize = 0
                    out_f.write(raw_data)
                    print(f"Repacking modified raw index {i} (uncompressed)")
                payload_written = True
                
        # Fallback to original file payload
        if not payload_written:
            # Read from original template DAR
            # Get original offset and size
            orig_f.seek(16 + i * 32)
            orig_entry = orig_f.read(16)
            orig_size, orig_zsize, orig_offset = struct.unpack("<LLQ", orig_entry)
            
            orig_f.seek(orig_offset)
            read_size = orig_zsize if orig_zsize > 0 else orig_size
            payload = orig_f.read(read_size)
            
            size = orig_size
            zsize = orig_zsize
            out_f.write(payload)
            
        new_index_entries.append(struct.pack("<LLQ", size, zsize, offset) + meta_bytes)
        
    orig_f.close()
    
    # Write header and index table
    out_f.seek(0)
    # Header: Magic, 0x10000, files_count, 0
    out_f.write(struct.pack("<IIII", 0xdac, 0x10000, files_count, 0))
    for entry_bytes in new_index_entries:
        out_f.write(entry_bytes)
        
    out_f.close()
    print("DAR Repacking completed successfully.")

# ==============================================================================
# PKGDDS Archive Commands
# ==============================================================================

def extract_pkgdds(pkgdds_path: str, output_dir: str):
    print(f"Extracting PKGDDS: {pkgdds_path} -> {output_dir}")
    os.makedirs(output_dir, exist_ok=True)
    
    base_name = os.path.splitext(os.path.basename(pkgdds_path))[0]
    
    with open(pkgdds_path, "rb") as f:
        header = f.read(16)
        if len(header) < 16:
            print("Error: Invalid PKGDDS header.", file=sys.stderr)
            sys.exit(1)
            
        files_count = struct.unpack("<I", header[0:4])[0]
        print(f"Total files in PKGDDS: {files_count}")
        
        index_table = f.read(files_count * 16)
        meta_entries = []
        
        for i in range(files_count):
            entry_offset = i * 16
            entry_data = index_table[entry_offset:entry_offset+16]
            offset, size = struct.unpack("<II", entry_data[0:8])
            meta_bytes = entry_data[8:16]
            
            f.seek(offset)
            payload = f.read(size)
            
            out_name = f"{base_name}_{i:03d}.gtf"
            out_path = os.path.join(output_dir, out_name)
            
            with open(out_path, "wb") as out_f:
                out_f.write(payload)
                
            meta_entries.append({
                "index": i,
                "meta": meta_bytes.hex(),
                "original_size": size
            })
            
        # Write metadata file
        meta_path = os.path.join(output_dir, "pkgdds_meta.json")
        with open(meta_path, "w", encoding="utf-8") as meta_f:
            json.dump({
                "files_count": files_count,
                "base_name": base_name,
                "header_extra": header[4:16].hex(),
                "entries": meta_entries
            }, meta_f, indent=2)
            
    print("PKGDDS Extraction completed successfully.")

def repack_pkgdds(pkgdds_path: str, modified_dir: str, output_pkgdds: str):
    print(f"Repacking PKGDDS: Template={pkgdds_path}, Modified={modified_dir} -> Output={output_pkgdds}")
    
    # Check for metadata file
    meta_path = os.path.join(modified_dir, "pkgdds_meta.json")
    
    if os.path.exists(meta_path):
        with open(meta_path, "r", encoding="utf-8") as meta_f:
            meta_data = json.load(meta_f)
        files_count = meta_data["files_count"]
        base_name = meta_data["base_name"]
        header_extra = bytes.fromhex(meta_data["header_extra"])
        entries = meta_data["entries"]
    else:
        # Reconstruct from original
        with open(pkgdds_path, "rb") as f:
            header = f.read(16)
            files_count = struct.unpack("<I", header[0:4])[0]
            header_extra = header[4:16]
            index_table = f.read(files_count * 16)
            
        base_name = os.path.splitext(os.path.basename(pkgdds_path))[0]
        entries = []
        for i in range(files_count):
            entry_data = index_table[i*16:i*16+16]
            offset, size = struct.unpack("<II", entry_data[0:8])
            entries.append({
                "index": i,
                "meta": entry_data[8:16].hex(),
                "original_size": size
            })
            
    orig_f = open(pkgdds_path, "rb")
    out_f = open(output_pkgdds, "wb+")
    
    # Write placeholder header and index table
    out_f.write(b"\x00" * (16 + files_count * 16))
    
    new_index_entries = []
    pos = out_f.tell()
    
    for entry in entries:
        i = entry["index"]
        meta_bytes = bytes.fromhex(entry["meta"])
        
        mod_name = f"{base_name}_{i:03d}.gtf"
        mod_path = os.path.join(modified_dir, mod_name)
        
        if os.path.exists(mod_path):
            with open(mod_path, "rb") as mf:
                payload = mf.read()
            print(f"Repacking modified PKGDDS entry {i} ({mod_name})")
        else:
            # Read original
            orig_f.seek(16 + i * 16)
            orig_offset, orig_size = struct.unpack("<II", orig_f.read(8))
            orig_f.seek(orig_offset)
            payload = orig_f.read(orig_size)
            
        size = len(payload)
        out_f.write(payload)
        
        new_index_entries.append(struct.pack("<II", pos, size) + meta_bytes)
        pos += size
        
    orig_f.close()
    
    # Write header and index table
    out_f.seek(0)
    out_f.write(struct.pack("<I", files_count) + header_extra)
    for entry_bytes in new_index_entries:
        out_f.write(entry_bytes)
        
    out_f.close()
    print("PKGDDS Repacking completed successfully.")

# ==============================================================================
# EG Container Commands
# ==============================================================================

def extract_eg(eg_path: str, output_dir: str):
    print(f"Extracting EG Container: {eg_path} -> {output_dir}")
    os.makedirs(output_dir, exist_ok=True)
    
    base_name = os.path.splitext(os.path.basename(eg_path))[0]
    
    with open(eg_path, "rb") as f:
        header = f.read(28)
        if len(header) < 28 or header[0:4] != b"\x01\x23\x45\x67":
            print("Error: Invalid EG magic.", file=sys.stderr)
            sys.exit(1)
            
        # Unpack as big-endian
        null1 = header[4:12]
        size = struct.unpack(">I", header[12:16])[0]
        null2 = header[16:20]
        data_offset = struct.unpack(">I", header[20:24])[0]
        files = struct.unpack(">I", header[24:28])[0]
        
        # Read index table
        index_table = f.read(files * 4)
        
        # Determine actual file data offset
        # data_offset in header is relative from end of index table
        payload_offset = 28 + files * 4 + data_offset
        
        f.seek(payload_offset)
        payload = f.read(size)
        
        out_name = f"{base_name}_0.gtf"
        out_path = os.path.join(output_dir, out_name)
        
        with open(out_path, "wb") as out_f:
            out_f.write(payload)
            
        # Write metadata
        meta_path = os.path.join(output_dir, "eg_meta.json")
        with open(meta_path, "w", encoding="utf-8") as meta_f:
            json.dump({
                "base_name": base_name,
                "null1": null1.hex(),
                "null2": null2.hex(),
                "data_offset": data_offset,
                "files": files,
                "index_table": index_table.hex()
            }, meta_f, indent=2)
            
    print("EG Extraction completed successfully.")

def repack_eg(eg_path: str, modified_dir: str, output_eg: str):
    print(f"Repacking EG Container: Template={eg_path}, Modified={modified_dir} -> Output={output_eg}")
    
    # Check for metadata
    meta_path = os.path.join(modified_dir, "eg_meta.json")
    
    if os.path.exists(meta_path):
        with open(meta_path, "r", encoding="utf-8") as meta_f:
            meta_data = json.load(meta_f)
        base_name = meta_data["base_name"]
        null1 = bytes.fromhex(meta_data["null1"])
        null2 = bytes.fromhex(meta_data["null2"])
        data_offset = meta_data["data_offset"]
        files = meta_data["files"]
        index_table = bytes.fromhex(meta_data["index_table"])
    else:
        # Reconstruct from original
        with open(eg_path, "rb") as f:
            header = f.read(28)
            null1 = header[4:12]
            null2 = header[16:20]
            data_offset = struct.unpack(">I", header[20:24])[0]
            files = struct.unpack(">I", header[24:28])[0]
            index_table = f.read(files * 4)
        base_name = os.path.splitext(os.path.basename(eg_path))[0]
        
    mod_name = f"{base_name}_0.gtf"
    mod_path = os.path.join(modified_dir, mod_name)
    
    if os.path.exists(mod_path):
        with open(mod_path, "rb") as mf:
            payload = mf.read()
        print(f"Repacking modified EG payload ({mod_name})")
    else:
        # Read original from eg_path
        with open(eg_path, "rb") as f:
            f.seek(28 + files * 4 + data_offset)
            payload = f.read()
            
    size = len(payload)
    
    with open(output_eg, "wb") as out_f:
        # Write header (big-endian)
        out_f.write(b"\x01\x23\x45\x67") # magic
        out_f.write(null1)
        out_f.write(struct.pack(">I", size))
        out_f.write(null2)
        out_f.write(struct.pack(">I", data_offset))
        out_f.write(struct.pack(">I", files))
        
        # Write index table
        out_f.write(index_table)
        
        # Write padding/alignment if data_offset > 0
        if data_offset > 0:
            out_f.write(b"\x00" * data_offset)
            
        # Write payload
        out_f.write(payload)
        
    print("EG Repacking completed successfully.")

# ==============================================================================
# CLI Entry point
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(description="White Album 2 PS3 Archive Extractor and Repacker")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # extract-dar
    edar_parser = subparsers.add_parser("extract-dar", help="Extract data.dar archive")
    edar_parser.add_argument("dar_file", help="Path to input data.dar")
    edar_parser.add_argument("output_dir", help="Output directory for extracted files")
    
    # repack-dar
    rdar_parser = subparsers.add_parser("repack-dar", help="Repack data.dar archive")
    rdar_parser.add_argument("dar_file", help="Path to original template data.dar")
    rdar_parser.add_argument("modified_dir", help="Directory containing modified files to inject")
    rdar_parser.add_argument("output_dar", help="Path to output repack data.dar")
    
    # extract-ddspack
    edds_parser = subparsers.add_parser("extract-ddspack", help="Extract pkgdds textures package")
    edds_parser.add_argument("pkgdds_file", help="Path to input .pkgdds file")
    edds_parser.add_argument("output_dir", help="Output directory for extracted GTF files")
    
    # repack-ddspack
    rdds_parser = subparsers.add_parser("repack-ddspack", help="Repack pkgdds textures package")
    rdds_parser.add_argument("pkgdds_file", help="Path to original template .pkgdds file")
    rdds_parser.add_argument("modified_dir", help="Directory containing modified GTF files")
    rdds_parser.add_argument("output_pkgdds", help="Path to output repack .pkgdds file")
    
    # extract-eg
    eeg_parser = subparsers.add_parser("extract-eg", help="Extract EG container")
    eeg_parser.add_argument("eg_file", help="Path to input .eg file")
    eeg_parser.add_argument("output_dir", help="Output directory for extracted GTF file")
    
    # repack-eg
    reg_parser = subparsers.add_parser("repack-eg", help="Repack EG container")
    reg_parser.add_argument("eg_file", help="Path to original template .eg file")
    reg_parser.add_argument("modified_dir", help="Directory containing modified GTF file")
    reg_parser.add_argument("output_eg", help="Path to output repack .eg file")
    
    args = parser.parse_args()
    
    if args.command == "extract-dar":
        extract_dar(args.dar_file, args.output_dir)
    elif args.command == "repack-dar":
        repack_dar(args.dar_file, args.modified_dir, args.output_dar)
    elif args.command == "extract-ddspack":
        extract_pkgdds(args.pkgdds_file, args.output_dir)
    elif args.command == "repack-ddspack":
        repack_pkgdds(args.pkgdds_file, args.modified_dir, args.output_pkgdds)
    elif args.command == "extract-eg":
        extract_eg(args.eg_file, args.output_dir)
    elif args.command == "repack-eg":
        repack_eg(args.eg_file, args.modified_dir, args.output_eg)

if __name__ == "__main__":
    main()
