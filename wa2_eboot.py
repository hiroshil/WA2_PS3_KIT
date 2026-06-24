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

def extract_eboot(eboot_path: str, output_dir: str, clean_only: bool = False):
    print(f"Extracting EBOOT: {eboot_path} to {output_dir}")
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    eboot_dir = os.path.join(output_dir, "eboot")
    os.makedirs(eboot_dir, exist_ok=True)
    
    with open(eboot_path, "rb") as f:
        eboot_data = f.read()
        
    if len(eboot_data) < WA2_EBOOT101_INDEX or eboot_data[0:4] != b"\x7FELF":
        print("Error: Invalid EBOOT.ELF file.", file=sys.stderr)
        sys.exit(1)
        
    # Nhận diện Delimiter từ EBOOT
    eboot_delimiter = eboot_data[0x101b44]
    delimiter_patched = (eboot_delimiter != 0x2C)
    
    if delimiter_patched:
        print(f"[*] Auto-Delimiter Detected: EBOOT uses '{chr(eboot_delimiter)}' (0x{eboot_delimiter:02X}).")
        
    pos = WA2_EBOOT101_INDEX
    first_txt_checked = False
    need_delimiter_upgrade = False
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
        comp_payload = eboot_data[cpos:cpos+block_size]
        
        # Decompress
        uncomp_data = wa2_elzma.decompress_data(comp_payload)
        
        # Decide if we write this file
        is_txt = norm_name.endswith(".txt")
        
        # Kiểm tra logic Delimiter cho file TXT
        if is_txt and delimiter_patched:
            if not first_txt_checked and len(uncomp_data) > 0:
                first_txt_checked = True
                if uncomp_data[0] != eboot_delimiter:
                    need_delimiter_upgrade = True
                    print(f"[*] Kịch bản TXT đang dùng dấu ngắt cũ. Sẽ tự động nâng cấp sang '{chr(eboot_delimiter)}'.")
            
            if need_delimiter_upgrade:
                uncomp_data = uncomp_data.replace(b',', bytes([eboot_delimiter]))
        
        # Save raw binary/uncompressed file
        raw_path = os.path.join(output_dir, norm_name)
        with open(raw_path, "wb") as f:
            f.write(uncomp_data)
        
        # Clean mode for TXT files
        if clean_only and is_txt:
            # Convert to UTF-16
            text = map_sjis_to_vietnamese(uncomp_data)
            out_path = os.path.join(eboot_dir, norm_name)
            with codecs.open(out_path, "w", encoding="utf-16") as out_f:
                out_f.write(text)
                    
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
            "mode": "clean" if clean_only else "raw",
            "files": meta_entries
        }, meta_f, indent=2)
        
    print("EBOOT Extraction completed successfully.")

# ==============================================================================
# Inject EBOOT Command
# ==============================================================================

def map_vietnamese_to_sjis(text_content: str) -> bytes:
    VIETNAMESE_CHARS = [
        None, 'Á', 'À', 'Ả', 'Ã', 'Ạ', 'Ă', 'Ắ', 'Ằ', 'Ẳ', 'Ẵ', 'Ặ', 'Â', 'Ấ', 'Ầ', 'Ẩ', 'Ẫ', 'Ậ',
        None, 'É', 'È', 'Ẻ', 'Ẽ', 'Ẹ', 'Ê', 'Ế', 'Ề', 'Ể', 'Ễ', 'Ệ',
        None, 'Í', 'Ì', 'Ỉ', 'Ĩ', 'Ị',
        None, 'Ó', 'Ò', 'Ỏ', 'Õ', 'Ọ', 'Ô', 'Ố', 'Ồ', 'Ổ', 'Ỗ', 'Ộ', 'Ơ', 'Ớ', 'Ờ', 'Ở', 'Ỡ', 'Ợ',
        None, 'Ú', 'Ù', 'Ủ', 'Ũ', 'Ụ', 'Ư', 'Ứ', 'Ừ', 'Ử', 'Ữ', 'Ự',
        None, 'Ý', 'Ỳ', 'Ỷ', 'Ỹ', 'Ỵ',
        None, 'Đ',
        None, 'á', 'à', 'ả', 'ã', 'ạ', 'ă', 'ắ', 'ằ', 'ẳ', 'ẵ', 'ặ', 'â', 'ấ', 'ầ', 'ẩ', 'ẫ', 'ậ',
        None, 'é', 'è', 'ẻ', 'ẽ', 'ẹ', 'ê', 'ế', 'ề', 'ể', 'ễ', 'ệ',
        None, 'í', 'ì', 'ỉ', 'ĩ', 'ị',
        None, 'ó', 'ò', 'ỏ', 'õ', 'ọ', 'ô', 'ố', 'ồ', 'ổ', 'ỗ', 'ộ', 'ơ', 'ớ', 'ờ', 'ở', 'ỡ', 'ợ',
        None, 'ú', 'ù', 'ủ', 'ũ', 'ụ', 'ư', 'ứ', 'ừ', 'ử', 'ữ', 'ự',
        None, 'ý', 'ỳ', 'ỷ', 'ỹ', 'ỵ',
        None, 'đ'
    ]
    out = bytearray()
    for char in text_content:
        if char in VIETNAMESE_CHARS:
            # Map Vietnamese to 0xF073 onwards, nhảy cóc 0x7F (Delete)
            idx = VIETNAMESE_CHARS.index(char)
            code = 0xF073 + idx
            if (code & 0xff) >= 0x7F:
                code += 1
            out.extend(struct.pack(">H", code))
        else:
            # Giữ nguyên toàn bộ ký tự gốc (kể cả tag/control codes), chỉ encode sang cp932 bình thường
            out.extend(char.encode('cp932', errors='replace'))
    return bytes(out)

def map_sjis_to_vietnamese(sjis_bytes: bytes) -> str:
    VIETNAMESE_CHARS = [
        None, 'Á', 'À', 'Ả', 'Ã', 'Ạ', 'Ă', 'Ắ', 'Ằ', 'Ẳ', 'Ẵ', 'Ặ', 'Â', 'Ấ', 'Ầ', 'Ẩ', 'Ẫ', 'Ậ',
        None, 'É', 'È', 'Ẻ', 'Ẽ', 'Ẹ', 'Ê', 'Ế', 'Ề', 'Ể', 'Ễ', 'Ệ',
        None, 'Í', 'Ì', 'Ỉ', 'Ĩ', 'Ị',
        None, 'Ó', 'Ò', 'Ỏ', 'Õ', 'Ọ', 'Ô', 'Ố', 'Ồ', 'Ổ', 'Ỗ', 'Ộ', 'Ơ', 'Ớ', 'Ờ', 'Ở', 'Ỡ', 'Ợ',
        None, 'Ú', 'Ù', 'Ủ', 'Ũ', 'Ụ', 'Ư', 'Ứ', 'Ừ', 'Ử', 'Ữ', 'Ự',
        None, 'Ý', 'Ỳ', 'Ỷ', 'Ỹ', 'Ỵ',
        None, 'Đ',
        None, 'á', 'à', 'ả', 'ã', 'ạ', 'ă', 'ắ', 'ằ', 'ẳ', 'ẵ', 'ặ', 'â', 'ấ', 'ầ', 'ẩ', 'ẫ', 'ậ',
        None, 'é', 'è', 'ẻ', 'ẽ', 'ẹ', 'ê', 'ế', 'ề', 'ể', 'ễ', 'ệ',
        None, 'í', 'ì', 'ỉ', 'ĩ', 'ị',
        None, 'ó', 'ò', 'ỏ', 'õ', 'ọ', 'ô', 'ố', 'ồ', 'ổ', 'ỗ', 'ộ', 'ơ', 'ớ', 'ờ', 'ở', 'ỡ', 'ợ',
        None, 'ú', 'ù', 'ủ', 'ũ', 'ụ', 'ư', 'ứ', 'ừ', 'ử', 'ữ', 'ự',
        None, 'ý', 'ỳ', 'ỷ', 'ỹ', 'ỵ',
        None, 'đ'
    ]
    out = []
    i = 0
    length = len(sjis_bytes)
    while i < length:
        b1 = sjis_bytes[i]
        # Phát hiện ký tự 2-byte (Shift-JIS hoặc Tiếng Việt)
        if (0x81 <= b1 <= 0x9F) or (0xE0 <= b1 <= 0xFC):
            if i + 1 < length:
                b2 = sjis_bytes[i+1]
                # Kiểm tra dải ký tự Tiếng Việt (Bắt đầu bằng 0xF0)
                if b1 == 0xF0:
                    code = (b1 << 8) | b2
                    idx = code - 0xF073
                    if b2 > 0x7F:
                        idx -= 1
                    if 0 <= idx < len(VIETNAMESE_CHARS):
                        char = VIETNAMESE_CHARS[idx]
                        if char is not None:
                            out.append(char)
                            i += 2
                            continue
                # Giải mã CP932 thông thường nếu không phải tiếng Việt
                try:
                    char = sjis_bytes[i:i+2].decode('cp932')
                    out.append(char)
                except UnicodeDecodeError:
                    out.append('?')
                i += 2
            else:
                out.append('?')
                i += 1
        else:
            # Giải mã ký tự ASCII 1-byte (Bao gồm Tag/Control Codes)
            try:
                char = bytes([b1]).decode('cp932')
                out.append(char)
            except UnicodeDecodeError:
                out.append('?')
            i += 1
    return "".join(out)

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
        
    # Nhận diện Delimiter từ EBOOT mẫu
    eboot_delimiter = eboot_data[0x101b44]
    delimiter_patched = (eboot_delimiter != 0x2C)
    if delimiter_patched:
        print(f"[*] Auto-Delimiter Detected: EBOOT expects '{chr(eboot_delimiter)}' (0x{eboot_delimiter:02X}) for TXT scripts.")
        
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
        mod_raw_path = os.path.join(input_dir, norm_name)

        # 1. Try clean mode translated .txt
        if clean_mode and norm_name.endswith(".txt") and os.path.exists(mod_txt_path):
            with open(mod_txt_path, "rb") as f:
                mod_data = f.read()
            if mod_data.startswith(b'\xff\xfe'):
                text_content = mod_data.decode("utf-16-le")
            elif mod_data.startswith(b'\xfe\xff'):
                text_content = mod_data.decode("utf-16-be")
            elif mod_data.startswith(b'\xef\xbb\xbf'):
                text_content = mod_data.decode("utf-8-sig")
            else:
                try:
                    text_content = mod_data.decode("utf-8")
                except UnicodeDecodeError:
                    text_content = mod_data.decode("cp932", errors="replace")
            # Replace custom music note unicode
            text_content = text_content.replace('\u4f93', '♪')
            
            # KIỂM TRA TÍNH TƯƠNG THÍCH DELIMITER
            if text_content and delimiter_patched:
                if text_content[0] == ',':
                    print(f"\n[LỖI NGHIÊM TRỌNG] Kịch bản '{norm_name}' dùng dấu ',' làm ngắt dòng, nhưng EBOOT yêu cầu '{chr(eboot_delimiter)}'. Kịch bản không tương thích!")
                    sys.exit(1)
                # Thay '\,' bằng ','
                text_content = text_content.replace(r'\,', ',')
            
            mapped_bytes = map_vietnamese_to_sjis(text_content)
            
            new_uncomp = len(mapped_bytes)
            # Compress
            comp_data = wa2_elzma.compress_data(mapped_bytes)
            payload = comp_data[4:] # Strip 4-byte prefix
            new_comp = len(payload)
            
            eboot_buf[cur_pos:cur_pos+new_comp] = payload
            payload_written = True
            print(f"Injecting modified text: {norm_name} ({orig_uncomp}->{new_uncomp} bytes)")
            
        # 2. Try raw mode modified decompressed file
        elif not clean_mode and os.path.exists(mod_raw_path):
            with open(mod_raw_path, "rb") as f:
                raw_data = f.read()
                
            if norm_name.endswith(".txt") and delimiter_patched and len(raw_data) > 0:
                if raw_data[0] == 0x2C: # Dấu ','
                    print(f"\n[LỖI NGHIÊM TRỌNG] Kịch bản thô '{norm_name}' dùng dấu ',' làm ngắt dòng, nhưng EBOOT yêu cầu '{chr(eboot_delimiter)}'. Kịch bản không tương thích!")
                    sys.exit(1)
                # Thay b'\,' bằng b','
                raw_data = raw_data.replace(b'\\,', b',')
                
            new_uncomp = len(raw_data)
            comp_data = wa2_elzma.compress_data(raw_data)
            payload = comp_data[4:] # Strip 4-byte prefix
            new_comp = len(payload)
            
            eboot_buf[cur_pos:cur_pos+new_comp] = payload
            payload_written = True
            print(f"Injecting raw modified file: {norm_name} ({orig_uncomp}->{new_uncomp} uncompressed bytes)")
            
        # 3. Fallback: Copy original compressed payload from EBOOT.ELF itself
        if not payload_written:
            orig_payload_off = orig_offset - EBOOT_OFFSET
            payload = eboot_data[orig_payload_off:orig_payload_off+orig_block]
            
            # Nâng cấp các file TXT cũ ở Fallback để tránh Crash nếu EBOOT đã đổi Delimiter
            if norm_name.endswith(".txt") and delimiter_patched:
                uncomp_data = wa2_elzma.decompress_data(payload, orig_uncomp)
                if len(uncomp_data) > 0 and uncomp_data[0] == 0x2C:
                    uncomp_data = uncomp_data.replace(b',', bytes([eboot_delimiter]))
                    comp_data = wa2_elzma.compress_data(uncomp_data)
                    payload = comp_data[4:]
                    orig_block = len(payload)
            
            eboot_buf[cur_pos:cur_pos+orig_block] = payload
            new_uncomp = orig_uncomp
            new_comp = orig_block
            payload_written = True
            
        # Update EBOOT index entry: offset, uncompressed size, compressed size
        eboot_buf[pos+4:pos+16] = struct.pack(">3I", cur_pos + EBOOT_OFFSET, new_uncomp, new_comp)
        
        # Advance write position
        cur_pos += new_comp
        
        # Align cur_pos to 64 bytes (0x40) to match original PS3 EBOOT alignment
        aligned_pos = (cur_pos + 63) // 64 * 64
        if aligned_pos > cur_pos:
            eboot_buf[cur_pos:aligned_pos] = b'\x00' * (aligned_pos - cur_pos)
            cur_pos = aligned_pos
            
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

def patch_eboot(eboot_path: str, charset_num: int, kerning_action: str, font2_bin_path: str = None, font2_num: int = 0, warning_png_path: str = None):
    with open(eboot_path, "rb") as f:
        buf = bytearray(f.read())
        
    # ==========================================
    # KERNING PATCH LOGIC (V4 - MAIN & RUBY HALF-WIDTH FOR VIETNAMESE)
    # ==========================================
    HOOK_V2_FILE = 0x40E3C
    
    print(f"\n--- KERNING PATCH ({kerning_action.upper()}) ---")
    if kerning_action == "check":
        print("[+] Patch V4 sẽ được kiểm tra. Hiện tại script tự động nạp Patch V4 khi apply.")
        return

    elif kerning_action == "remove":
        # Restore RUBY EXTSB NOPs
        buf[0x44504:0x44508] = b"\x7C\x63\x07\x74"
        buf[0x44514:0x44518] = b"\x7C\x63\x07\x74"
        # Restore MAIN EXTSB NOPs
        buf[0x4086c:0x40870] = b"\x7C\x63\x07\x74"
        buf[0x4087c:0x40880] = b"\x7C\x63\x07\x74"

        # Restore RUBY Hook
        buf[0x44524:0x44540] = b"\x7c\x63\x07\x74\x2c\x03\x00\xa1\x41\x80\x00\x2c\x88\x61\x02\x38\x7c\x63\x07\x74\x2c\x03\x00\xdf\x41\x81\x00\x1c"
        # Restore MAIN Hook
        buf[0x4088c:0x408a8] = b"\x88\x61\x02\x34\x7c\x63\x07\x74\x2c\x03\x00\xa1\x41\x80\x00\x28\x88\x61\x02\x34\x7c\x63\x07\x74\x2c\x03\x00\xdf\x41\x81\x00\x18"
        
        # Restore Cursor Advance Hook and Clean Caves
        buf[0x41c8c:0x41c8c+8] = b"\x80\x61\x01\xa0\x3c\x80\x00\x00"
        buf[0x125000:0x125000+80] = b"\x00" * 80
        buf[0x125050:0x125050+80] = b"\x00" * 80
        buf[0x1250A0:0x1250A0+128] = b"\x00" * 128
        
        print("=> GỠ PATCH KERNING THÀNH CÔNG! EBOOT đã trở về nguyên bản gốc.")

    elif kerning_action == "apply":
        # 1. Restore the bad Kerning Patch V2 at 0x50E3C if it existed
        if bytes(buf[HOOK_V2_FILE:HOOK_V2_FILE+4]) == b"\x4B\xF2\xF6\x4C":
            buf[HOOK_V2_FILE:HOOK_V2_FILE+4] = b"\x80\x63\x00\x00"

        # 2. NOP extsb cho RUBY (0x54504, 0x54514)
        buf[0x44504:0x44508] = b"\x60\x00\x00\x00"
        buf[0x44514:0x44518] = b"\x60\x00\x00\x00"
        
        # 3. NOP extsb cho MAIN (0x5086c, 0x5087c)
        buf[0x4086c:0x40870] = b"\x60\x00\x00\x00"
        buf[0x4087c:0x40880] = b"\x60\x00\x00\x00"

        # 4. RUBY Hook tại 0x54524 (offset 0x44524)
        buf[0x44524:0x44524+28] = b"\x48\x0e\x0a\xdc" + (b"\x60\x00\x00\x00" * 6)

        # 5. MAIN Hook tại 0x5088c (offset 0x4088c)
        buf[0x4088c:0x4088c+28] = b"\x48\x0e\x47\xc4" + (b"\x60\x00\x00\x00" * 6)

        # 6. Ghi RUBY Cave tại 0x135000 (offset 0x125000)
        RUBY_CAVE = [
            0x88610238, 0x2C030081, 0x41800010, 0x2C03009F,
            0x41810008, 0x4BF1F52C, 0x2C0300A1, 0x41800010,
            0x2C0300DF, 0x41810008, 0x4BF1F518, 0x2C0300E0,
            0x41800010, 0x2C0300FC, 0x41810008, 0x4BF1F504,
            0x4BF1F4E8
        ]
        for i, inst in enumerate(RUBY_CAVE):
            buf[0x125000 + i*4 : 0x125000 + i*4 + 4] = inst.to_bytes(4, byteorder='big')

        # 7. Ghi MAIN Cave tại 0x135050 (offset 0x125050)
        MAIN_CAVE = [
            0x88610234, 0x2C030081, 0x41800010, 0x2C03009F,
            0x41810008, 0x4BF1B844, 0x2C0300A1, 0x41800010,
            0x2C0300DF, 0x41810008, 0x4BF1B830, 0x2C0300E0,
            0x41800010, 0x2C0300FC, 0x41810008, 0x4BF1B81C,
            0x4BF1B830
        ]
        for i, inst in enumerate(MAIN_CAVE):
            buf[0x125050 + i*4 : 0x125050 + i*4 + 4] = inst.to_bytes(4, byteorder='big')

        # 8. Ghi Hook Cursor Advance tại 0x51c8c (offset 0x41c8c)
        buf[0x41c8c:0x41c8c+8] = b"\x48\x0e\x34\x14\x60\x00\x00\x00"

        # 9. Ghi Cave Cursor Advance tại 0x1350A0 (offset 0x1250A0)
        CURSOR_CAVE = [
    0x806101A0, # lwz r3, 0x1a0(r1)
    0x48000010, # b half_width (skip 3 nops)
    0x60000000,
    0x60000000,
    0x60000000,
    # half_width:
    0x7C630E70, # srawi r3, r3, 1
    0x7C630194, # addze r3, r3
    # do_full:
    0x3C800000, # lis r4, 0
    0x4BF1CBDC  # b 0x51c9c
]
        for i, inst in enumerate(CURSOR_CAVE):
            buf[0x1250A0 + i*4 : 0x1250A0 + i*4 + 4] = inst.to_bytes(4, byteorder='big')

        print("Đã áp dụng Patch V7: Cập nhật CURSOR_CAVE bao gồm cả ASCII (0x21-0x7E) cho nửa chiều rộng!")
            
    print("\n--- GENERAL EBOOT PATCH ---")
        
    # Xử lý Font 2 (Nếu người dùng cung cấp)
    if font2_bin_path and os.path.exists(font2_bin_path) and font2_bin_path.lower() != "none":
        with open(font2_bin_path, "rb") as f:
            buf2 = f.read()
    else:
        buf2 = None
        print("[*] Skipping Font 2 patch (No valid font2_bin provided)")
        
    # Patch Font 1 Size & Address
    FONT1_POS = 0xfe3f0
    FONT1_SIZE = 0x1524
    PATCH_FONT_POS = 0x120e00
    
    # Copy original font 1 to patch location
    buf[PATCH_FONT_POS:PATCH_FONT_POS+FONT1_SIZE] = buf[FONT1_POS:FONT1_POS+FONT1_SIZE]
    
    pos = PATCH_FONT_POS + FONT1_SIZE
    
    # Cho phép điền tịnh tiến trực tiếp từ 0xF043 để duy trì mảng Sorted. 
    # 48 mã đầu tiên (0xF043-0xF072) sẽ chiếu tự động vào 48 ô trắng cuối hàng 54.
    font_num = charset_num - (FONT1_SIZE // 2)
    font_code = 0xf043
    
    while font_num > 0:
        if (font_code & 0xff) < 0x40:
            font_code += 1
            continue
        if (font_code & 0xff) == 0x7F:
            font_code += 1
            continue
            
        buf[pos:pos+2] = struct.pack(">H", font_code)
        font_code += 1
        font_num -= 1
        pos += 2
        
    print(f"Total charset {charset_num}, end {hex(font_code)}")
    
    # Patch Font Size 1
    PATCH_FONT_SIZE_POS = 0xc98a
    opcode = struct.unpack(">H", buf[PATCH_FONT_SIZE_POS:PATCH_FONT_SIZE_POS+2])[0]
    if opcode == charset_num:
        print(f"Font 1 size already patched to {charset_num}")
    elif opcode != 0xa92:
        print(f"Error: Bad ELF magic for Font 1 size patch (Found {hex(opcode)}).", file=sys.stderr)
        sys.exit(1)
    else:
        buf[PATCH_FONT_SIZE_POS:PATCH_FONT_SIZE_POS+2] = struct.pack(">H", charset_num)
        print(f"Patched Font 1 size to {charset_num}")
    
    # Patch Font Address 1
    PATCH_FONT_ADDRESS = 0xca04
    if buf[PATCH_FONT_ADDRESS:PATCH_FONT_ADDRESS+8] == b"\x3C\x60\x00\x13\x30\x63\x0E\x00":
        print(f"Font 1 address already patched.")
    elif buf[PATCH_FONT_ADDRESS:PATCH_FONT_ADDRESS+8] != b"\x3C\x60\x00\x11\x30\x63\xE3\xF0":
        print("Error: Bad ELF magic for Font 1 address patch.", file=sys.stderr)
        sys.exit(1)
    else:
        buf[PATCH_FONT_ADDRESS:PATCH_FONT_ADDRESS+8] = b"\x3C\x60\x00\x13\x30\x63\x0E\x00"
        print(f"Patched Font 1 address to {hex(PATCH_FONT_POS)}")
    
    # Patch Font 2 Size & Address (Nếu có)
    if buf2 and font2_num > 0:
        PATCH_FONT_SIZE_POS2 = 0xc972
        opcode = struct.unpack(">H", buf[PATCH_FONT_SIZE_POS2:PATCH_FONT_SIZE_POS2+2])[0]
        if opcode != 0x70:
            print("Error: Bad ELF magic for Font 2 size patch.", file=sys.stderr)
            sys.exit(1)
        buf[PATCH_FONT_SIZE_POS2:PATCH_FONT_SIZE_POS2+2] = struct.pack(">H", font2_num)
        print(f"Patched Font 2 size to {font2_num}")
        
        PATCH_FONT_ADDRESS2 = 0xcb00
        PATCH_FONT_POS2 = 0x122c00
        if buf[PATCH_FONT_ADDRESS2:PATCH_FONT_ADDRESS2+8] != b"\x3C\x60\x00\x11\x30\x63\xF9\x15":
            print("Error: Bad ELF magic for Font 2 address patch.", file=sys.stderr)
            sys.exit(1)
        buf[PATCH_FONT_ADDRESS2:PATCH_FONT_ADDRESS2+8] = b"\x3C\x60\x00\x13\x30\x63\x2c\x00"
        print(f"Patched Font 2 address to {hex(PATCH_FONT_POS2)}")
        buf[PATCH_FONT_POS2:PATCH_FONT_POS2+len(buf2)] = buf2
    
    # Patch Load Size
    LOAD_POS = 0x64
    LOAD_NEW_SIZE = 0x12B000
    if buf[LOAD_POS:LOAD_POS+4] == struct.pack(">I", LOAD_NEW_SIZE):
        print("ELF load size already patched.")
    elif buf[LOAD_POS:LOAD_POS+4] not in (b"\x00\x12\x61\xA0", b"\x00\x12\x0D\xE8"):
        print("Error: Wrong ELF load size.", file=sys.stderr)
        sys.exit(1)
    else:
        buf[LOAD_POS:LOAD_POS+4] = struct.pack(">I", LOAD_NEW_SIZE)
        buf[LOAD_POS+8:LOAD_POS+12] = struct.pack(">I", LOAD_NEW_SIZE) # Update p_memsz at 0x6C
        print(f"Patched ELF load size to {hex(LOAD_NEW_SIZE)}")
    
    # (Removed) Patch Section Size - Out of bounds for this EBOOT version
    
    # (Removed) Patch Warning PNG - Out of bounds for this EBOOT version
    
    # Extra patch for comma delimiter
    try:
        buf[0x101b44] = 0x24
        buf[0x4aec7] = 0x24
        buf[0x4af23] = 0x24
        print("Patched EBOOT delimiter ',' to '$'.")
    except Exception as e:
        print(f"Warning: Could not patch delimiter: {e}", file=sys.stderr)
        
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
    pat_parser = subparsers.add_parser("patch", help="Patch EBOOT.ELF font, warning data, and kerning")
    pat_parser.add_argument("eboot_file", help="Path to EBOOT.ELF")
    pat_parser.add_argument("--charset", type=int, default=2907, help="Charset count (Mặc định: 2907)")
    pat_parser.add_argument("--kerning", choices=["apply", "remove", "check"], required=True, help="Hành động cho Kerning Patch (bắt buộc)")
    pat_parser.add_argument("font2_bin", nargs="?", default="none", help="Path to font2.bin (Optional)")
    pat_parser.add_argument("font2_num", nargs="?", type=int, default=0, help="Font2 size (Optional)")
    pat_parser.add_argument("warning_png", nargs="?", default="none", help="Path to warning.png (Optional)")
    
    args = parser.parse_args()
    
    if args.command == "extract":
        extract_eboot(args.eboot_file, args.output_dir, args.clean)
    elif args.command == "inject":
        inject_eboot(args.in_eboot, args.out_eboot, args.input_dir)
    elif args.command == "patch":
        patch_eboot(args.eboot_file, args.charset, args.kerning, args.font2_bin, args.font2_num, args.warning_png)

if __name__ == "__main__":
    main()