import os
import argparse
import sys

def parse_txt(file_path):
    with open(file_path, "rb") as f:
        data = f.read()
    
    if data.startswith(b'\xff\xfe'):
        text = data.decode("utf-16")
    elif data.startswith(b'\xfe\xff'):
        text = data.decode("utf-16-be")
    elif data.startswith(b'\xef\xbb\xbf'):
        text = data.decode("utf-8-sig")
    else:
        text = data.decode("cp932", errors="replace")
    
    parts = text.split(",")
    return parts

def dump_text(input_file, output_dir):
    os.makedirs(output_dir, exist_ok=True)
    basename = os.path.basename(input_file)
    output_file = os.path.join(output_dir, basename)
    
    parts = parse_txt(input_file)
    
    with open(output_file, "w", encoding="utf-8") as f:
        for i, part in enumerate(parts):
            f.write(f"//{i:08d}\n")
            f.write(f"{part}\n")
            f.write(f"<{i:08d}>\n")
            f.write(f"{part}\n\n")

    print(f"Dumped {len(parts)} strings to {output_file}")

def build_text(input_file, original_file, output_file):
    parts = parse_txt(original_file)
    
    with open(input_file, "r", encoding="utf-8") as f:
        lines = f.readlines()
        
    current_idx = -1
    current_translation = []
    in_translation = False
    
    for line in lines:
        line = line.strip('\n')
        if line.startswith("//"):
            in_translation = False
            continue
        if line.startswith("<") and line.endswith(">"):
            try:
                idx_str = line[1:-1]
                current_idx = int(idx_str)
                current_translation = []
                in_translation = True
                continue
            except ValueError:
                pass
        
        if in_translation:
            current_translation.append(line)
            if current_idx >= 0 and current_idx < len(parts):
                # Remove the trailing empty line if it was added for padding
                if len(current_translation) > 0 and current_translation[-1] == "":
                    parts[current_idx] = '\n'.join(current_translation[:-1])
                else:
                    parts[current_idx] = '\n'.join(current_translation)
                
    output_text = ",".join(parts)
    
    with open(output_file, "wb") as f:
        f.write(output_text.encode("cp932", errors="replace"))
        
    print(f"Built {output_file} from {input_file} (Total parts: {len(parts)})")

def main():
    parser = argparse.ArgumentParser(description="WA2 PS3 Text Parser")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    parser_dump = subparsers.add_parser("dump")
    parser_dump.add_argument("input", help="Original .txt file")
    parser_dump.add_argument("outdir", help="Output directory for dumped text")
    
    parser_build = subparsers.add_parser("build")
    parser_build.add_argument("translated", help="Translated .txt file")
    parser_build.add_argument("original", help="Original .txt file")
    parser_build.add_argument("output", help="Compiled .txt file")
    
    args = parser.parse_args()
    
    if args.command == "dump":
        dump_text(args.input, args.outdir)
    elif args.command == "build":
        build_text(args.translated, args.original, args.output)

if __name__ == "__main__":
    main()
