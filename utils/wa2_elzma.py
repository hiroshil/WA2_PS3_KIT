# -*- coding: utf-8 -*-
import os
import sys
import struct
import lzma
import argparse

UNCOMP_BLOCK_SIZE = 0x10000

def compress_data(buf: bytes) -> bytes:
    size = len(buf)
    remain = size
    pos = 0
    data = bytearray()
    
    filters = [
        {
            "id": lzma.FILTER_LZMA1,
            "dict_size": 1 << 14,
            "lc": 3,
            "lp": 0,
            "pb": 2,
            "mode": lzma.MODE_NORMAL,
            "mf": lzma.MF_BT4,
            "nice_len": 273
        }
    ]
    
    while remain > 0:
        if remain > UNCOMP_BLOCK_SIZE:
            block_size = UNCOMP_BLOCK_SIZE
        else:
            block_size = remain
            
        block = buf[pos:pos+block_size]
        pos += block_size
        remain -= block_size
        
        # Compress block raw payload
        compressor = lzma.LZMACompressor(format=lzma.FORMAT_RAW, filters=filters)
        dst = compressor.compress(block) + compressor.flush()
        
        # Build block header: uncomp_size (4B), comp_size (4B), properties (8B)
        block_head = struct.pack("<II8s", block_size, len(dst), b"\x5d\x00\x40\x00\x00\x00\x00\x00")
        block_data = block_head + dst
        
        # Padding to multiple of 16 bytes
        pad = len(block_data)
        pad = (pad + 0xf) // 0x10 * 0x10 - pad
        if pad > 0:
            block_data += b"\x00" * pad
            
        data.extend(block_data)
        
    return struct.pack("<I", size) + bytes(data)

def decompress_data(buf: bytes) -> bytes:
    if len(buf) < 16:
        return b""
        
    # Detect 4-byte uncompressed size prefix
    has_prefix = False
    
    # Check properties byte at offset 8 (no prefix) vs offset 12 (with prefix)
    prop_no_prefix = buf[8]
    prop_with_prefix = buf[12]
    
    if prop_with_prefix == 0x5d and prop_no_prefix != 0x5d:
        has_prefix = True
    elif prop_no_prefix == 0x5d and prop_with_prefix != 0x5d:
        has_prefix = False
    else:
        # Ambiguous, fallback to size check
        val1 = struct.unpack("<I", buf[0:4])[0]
        if val1 > UNCOMP_BLOCK_SIZE:
            has_prefix = True
        else:
            # Check if val1 matches block uncompressed size at offset 4
            val2 = struct.unpack("<I", buf[4:8])[0]
            if val1 == val2:
                has_prefix = True
            else:
                has_prefix = False

    if has_prefix:
        total_uncomp_size = struct.unpack("<I", buf[0:4])[0]
        start_pos = 4
    else:
        total_uncomp_size = 0
        start_pos = 0
        
    pos = start_pos
    data = bytearray()
    
    while pos < len(buf):
        if pos + 16 > len(buf):
            break
            
        block_uncomp_size, block_comp_size = struct.unpack("<II", buf[pos:pos+8])
        if block_uncomp_size == 0 or block_comp_size == 0:
            break
            
        lzma_params = buf[pos+8:pos+13]
        payload_start = pos + 16
        payload_end = payload_start + block_comp_size
        
        if payload_end > len(buf):
            break
            
        payload = buf[payload_start:payload_end]
        
        # Decode LZMA params
        prop_byte = lzma_params[0]
        pb = prop_byte // 45
        temp = prop_byte - pb * 45
        lp = temp // 9
        lc = temp % 9
        dict_size = struct.unpack("<I", lzma_params[1:5])[0]
        
        # Reconstruct filters for raw decompression
        filters = [
            {
                "id": lzma.FILTER_LZMA1,
                "dict_size": dict_size,
                "lc": lc,
                "lp": lp,
                "pb": pb
            }
        ]
        
        try:
            decompressor = lzma.LZMADecompressor(format=lzma.FORMAT_RAW, filters=filters)
            decompressed_block = decompressor.decompress(payload)
            data.extend(decompressed_block)
        except Exception as e:
            print(f"Error decompressing block at offset {pos}: {e}", file=sys.stderr)
            break
            
        # Align pos to 16 bytes boundary
        pos += (block_comp_size + 0x1f) // 0x10 * 0x10
        
        if total_uncomp_size > 0 and len(data) >= total_uncomp_size:
            break
            
    # Trim to expected size if total_uncomp_size is specified
    if total_uncomp_size > 0:
        return bytes(data[:total_uncomp_size])
    return bytes(data)

def main():
    parser = argparse.ArgumentParser(description="Aquaplus LZMA Block Compression Utility")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # Compress command
    comp_parser = subparsers.add_parser("compress", help="Compress file or directory")
    comp_parser.add_argument("input", help="Input file or directory")
    comp_parser.add_argument("output", nargs="?", help="Output file (optional)")
    
    # Decompress command
    decomp_parser = subparsers.add_parser("decompress", help="Decompress file or directory")
    decomp_parser.add_argument("input", help="Input file or directory")
    decomp_parser.add_argument("output", nargs="?", help="Output file (optional)")
    
    args = parser.parse_args()
    
    if args.command == "compress":
        if os.path.isdir(args.input):
            # Compress all files in directory
            for root, dirs, files in os.walk(args.input):
                for file in files:
                    if file.endswith(".elzma"):
                        continue
                    in_path = os.path.join(root, file)
                    out_path = in_path + ".elzma"
                    print(f"Compressing {in_path} -> {out_path}")
                    with open(in_path, "rb") as f:
                        data = f.read()
                    comp = compress_data(data)
                    with open(out_path, "wb") as f:
                        f.write(comp)
        else:
            out_path = args.output if args.output else args.input + ".elzma"
            print(f"Compressing {args.input} -> {out_path}")
            with open(args.input, "rb") as f:
                data = f.read()
            comp = compress_data(data)
            with open(out_path, "wb") as f:
                f.write(comp)
                
    elif args.command == "decompress":
        if os.path.isdir(args.input):
            # Decompress all .elzma files in directory
            for root, dirs, files in os.walk(args.input):
                for file in files:
                    if not file.endswith(".elzma"):
                        continue
                    in_path = os.path.join(root, file)
                    out_path = os.path.splitext(in_path)[0]
                    print(f"Decompressing {in_path} -> {out_path}")
                    with open(in_path, "rb") as f:
                        data = f.read()
                    decomp = decompress_data(data)
                    with open(out_path, "wb") as f:
                        f.write(decomp)
        else:
            out_path = args.output if args.output else os.path.splitext(args.input)[0]
            print(f"Decompressing {args.input} -> {out_path}")
            with open(args.input, "rb") as f:
                data = f.read()
            decomp = decompress_data(data)
            with open(out_path, "wb") as f:
                f.write(decomp)

if __name__ == "__main__":
    main()
