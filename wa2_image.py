# -*- coding: utf-8 -*-
import os
import sys
import subprocess
import argparse
import shutil

def find_tool(tool_name: str) -> str:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    if tool_name == "nvcompress":
        paths = [
            os.path.join(script_dir, "PS3_Projects", "3rd", "nvtt", "nvcompress.exe"),
            os.path.join(script_dir, "3rd", "nvtt", "nvcompress.exe"),
            os.path.join(script_dir, "bin", "nvcompress.exe"),
            os.path.join(script_dir, "nvcompress.exe")
        ]
    elif tool_name == "dds2gtf":
        paths = [
            os.path.join(script_dir, "PS3_Projects", "tools", "dds2gtf.exe"),
            os.path.join(script_dir, "tools", "dds2gtf.exe"),
            os.path.join(script_dir, "bin", "dds2gtf.exe"),
            os.path.join(script_dir, "dds2gtf.exe")
        ]
    elif tool_name == "gtf2dds":
        paths = [
            os.path.join(script_dir, "PS3_Projects", "tools", "gtf2dds.exe"),
            os.path.join(script_dir, "tools", "gtf2dds.exe"),
            os.path.join(script_dir, "bin", "gtf2dds.exe"),
            os.path.join(script_dir, "gtf2dds.exe")
        ]
    else:
        paths = []
        
    for p in paths:
        if os.path.exists(p):
            return os.path.abspath(p)
            
    p = shutil.which(tool_name)
    if p:
        return p
        
    print(f"Error: {tool_name}.exe not found.", file=sys.stderr)
    sys.exit(1)

def run_png2dds(input_png: str, format_arg: str, mask_arg: str = None):
    tool_path = find_tool("nvcompress")
    
    cmd = [
        tool_path,
        "-nomips",
        "-nocuda"
    ]
    if format_arg:
        cmd.append(format_arg)
    if mask_arg:
        cmd.append(mask_arg)
    cmd.append(os.path.abspath(input_png))
    
    print(f"Running nvcompress: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error: nvcompress failed.\nStdout: {result.stdout}\nStderr: {result.stderr}", file=sys.stderr)
        sys.exit(1)
    print("PNG to DDS conversion finished.")

def run_dds2gtf(input_dds: str):
    tool_path = find_tool("dds2gtf")
    tool_dir = os.path.dirname(tool_path)
    
    cmd = [
        tool_path,
        os.path.abspath(input_dds)
    ]
    
    print(f"Running dds2gtf: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=tool_dir, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error: dds2gtf failed.\nStdout: {result.stdout}\nStderr: {result.stderr}", file=sys.stderr)
        sys.exit(1)
    print("DDS to GTF conversion finished.")

def run_gtf2dds(input_gtf: str):
    tool_path = find_tool("gtf2dds")
    tool_dir = os.path.dirname(tool_path)
    
    cmd = [
        tool_path,
        os.path.abspath(input_gtf)
    ]
    
    print(f"Running gtf2dds: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=tool_dir, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error: gtf2dds failed.\nStdout: {result.stdout}\nStderr: {result.stderr}", file=sys.stderr)
        sys.exit(1)
    print("GTF to DDS conversion finished.")

def main():
    parser = argparse.ArgumentParser(description="White Album 2 PS3 Image Texture Conversion Tool")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # png2dds
    p2d_parser = subparsers.add_parser("png2dds", help="Convert PNG image to DDS")
    p2d_parser.add_argument("input_png", help="Path to input PNG file")
    p2d_parser.add_argument("--format", default="-rgb16", help="Compression format (e.g. -rgb32, -rgb16, -rgb8, -bc3)")
    p2d_parser.add_argument("--mask", help="Optional mask parameter (e.g. -maskffff)")
    
    # dds2gtf
    d2g_parser = subparsers.add_parser("dds2gtf", help="Convert DDS to GTF")
    d2g_parser.add_argument("input_dds", help="Path to input DDS file")
    
    # gtf2dds
    g2d_parser = subparsers.add_parser("gtf2dds", help="Convert GTF to DDS")
    g2d_parser.add_argument("input_gtf", help="Path to input GTF file")
    
    args = parser.parse_args()
    
    if args.command == "png2dds":
        run_png2dds(args.input_png, args.format, args.mask)
    elif args.command == "dds2gtf":
        run_dds2gtf(args.input_dds)
    elif args.command == "gtf2dds":
        run_gtf2dds(args.input_gtf)

if __name__ == "__main__":
    main()
