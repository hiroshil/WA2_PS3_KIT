use std::fs::{self, File};
use std::io::{Read, Write, Seek, SeekFrom};
use std::path::{Path, PathBuf};
use std::hash::{Hash, Hasher};
use std::collections::hash_map::DefaultHasher;

fn hash_bytes(bytes: &[u8]) -> String {
    let mut hasher = DefaultHasher::new();
    bytes.hash(&mut hasher);
    hasher.finish().to_string()
}

use clap::{Parser, Subcommand};
use serde::{Serialize, Deserialize};

// ==============================================================================
// CLI Definitions
// ==============================================================================


#[derive(Parser)]
#[command(name = "wa2_archive")]
#[command(about = "White Album 2 PS3 Archive Utility in Rust", long_about = None)]
struct Cli {
    #[command(subcommand)]
    command: Commands,
    #[arg(long, global = true)]
    use_hash: bool,
}


#[derive(Subcommand)]
enum Commands {
    #[command(name = "extract-dar")]
    ExtractDar {
        dar_file: String,
        output_dir: String,
        #[arg(long)]
        clean: bool,
        #[arg(long)]
        only_image: bool,
    },
    #[command(name = "repack-dar")]
    RepackDar {
        dar_file: String,
        modified_dir: String,
        output_dar: String,
        #[arg(long)]
        clean: bool,
        #[arg(long, short = 'j')]
        threads: Option<usize>,
    },
    #[command(name = "extract-ddspack")]
    ExtractDdspack {
        pkgdds_file: String,
        output_dir: String,
        #[arg(long)]
        clean: bool,
    },
    #[command(name = "repack-ddspack")]
    RepackDdspack {
        pkgdds_file: String,
        modified_dir: String,
        output_pkgdds: String,
        #[arg(long)]
        clean: bool,
        #[arg(long, short = 'j')]
        threads: Option<usize>,
    },
    #[command(name = "extract-eg")]
    ExtractEg {
        eg_file: String,
        output_dir: String,
        #[arg(long)]
        clean: bool,
    },
    #[command(name = "repack-eg")]
    RepackEg {
        eg_file: String,
        modified_dir: String,
        output_eg: String,
        #[arg(long)]
        clean: bool,
        #[arg(long, short = 'j')]
        threads: Option<usize>,
    },
}

// ==============================================================================
// Serialization Meta Structs
// ==============================================================================

#[derive(Serialize, Deserialize, Debug, Clone)]
struct DarMetaEntry {
    index: u32,
    ext: String,
    meta: String,
    original_compressed: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    clean_type: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    dds_format: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    orig_dds_header: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub orig_gtf_header: Option<String>,
    pub png_hash: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    header_extra: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pkgdds_entries: Option<Vec<PkgddsMetaEntry>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    eg_meta: Option<EgMeta>,
}

#[derive(Serialize, Deserialize, Debug, Clone)]
struct DarMeta {
    files_count: u32,
    entries: Vec<DarMetaEntry>,
}

#[derive(Serialize, Deserialize, Debug, Clone)]
struct PkgddsMetaEntry {
    index: u32,
    meta: String,
    original_size: u32,
    #[serde(skip_serializing_if = "Option::is_none")]
    dds_format: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    orig_dds_header: Option<String>,
    pub png_hash: Option<String>,
}

#[derive(Serialize, Deserialize, Debug, Clone)]
struct PkgddsMeta {
    files_count: u32,
    base_name: String,
    header_extra: String,
    entries: Vec<PkgddsMetaEntry>,
}

#[derive(Serialize, Deserialize, Debug, Clone)]
struct EgMeta {
    base_name: String,
    null1: String,
    null2: String,
    data_offset: u32,
    files: u32,
    index_table: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    dds_format: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    orig_dds_header: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub orig_gtf_header: Option<String>,
    pub png_hash: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    header_extra: Option<String>,
}

// ==============================================================================
// Tool Lookup Utility
// ==============================================================================

fn find_tool(name: &str) -> Result<PathBuf, String> {
    let current_dir = std::env::current_dir().unwrap_or_else(|_| PathBuf::from("."));
    let exe_dir = std::env::current_exe().ok().and_then(|p| p.parent().map(|d| d.to_path_buf()));

    let mut candidates = Vec::new();

    let rel_paths = if name == "nvcompress" {
        vec![
            "PS3_Projects/3rd/NVIDIA_Texture_Tools_2024.1.1/nvcompress.exe",
            "3rd/NVIDIA_Texture_Tools_2024.1.1/nvcompress.exe",
			"PS3_Projects/tools/nvcompress.exe",
			"tools/nvcompress.exe",
            "bin/nvcompress.exe",
            "nvcompress.exe",
        ]
    } else {
        vec![
            "PS3_Projects/3rd/NVIDIA_Texture_Tools_2024.1.1/nvdecompress.exe",
            "3rd/NVIDIA_Texture_Tools_2024.1.1/nvdecompress.exe",
            "PS3_Projects/tools/nvdecompress.exe",
            "tools/nvdecompress.exe",
            "bin/nvdecompress.exe",
            "nvdecompress.exe",
        ]
    };

    let filter_keyword = if name == "nvcompress" { "nvcompress" } else { "nvdecompress" };
    let filtered_rel_paths: Vec<&str> = rel_paths.into_iter().filter(|p| p.contains(filter_keyword)).collect();

    for rp in &filtered_rel_paths {
        // Traverse up current_dir up to 4 levels
        let mut dir = Some(current_dir.clone());
        for _ in 0..4 {
            if let Some(d) = dir {
                candidates.push(d.join(rp));
                dir = d.parent().map(|p| p.to_path_buf());
            } else {
                break;
            }
        }

        // Traverse up exe_dir up to 4 levels
        if let Some(ref ed) = exe_dir {
            let mut dir = Some(ed.clone());
            for _ in 0..4 {
                if let Some(d) = dir {
                    candidates.push(d.join(rp));
                    dir = d.parent().map(|p| p.to_path_buf());
                } else {
                    break;
                }
            }
        }
    }

    for path in &candidates {
        if path.exists() {
            return Ok(fs::canonicalize(&path).unwrap_or(path.clone()));
        }
    }

    // Try finding it on system PATH using where.exe on Windows
    let output = std::process::Command::new("where.exe")
        .arg(name)
        .output();

    if let Ok(out) = output {
        if out.status.success() {
            let stdout = String::from_utf8_lossy(&out.stdout);
            if let Some(line) = stdout.lines().next() {
                return Ok(PathBuf::from(line.trim()));
            }
        }
    }

    Err(format!(
        "Error: {}.exe not found. Please place it in PS3_Projects/3rd/NVIDIA_Texture_Tools_2024.1.1/ or standard directory.",
        name
    ))
}

fn run_subprocess(tool_path: &Path, args: &[&str], cwd: Option<&Path>) -> Result<(), String> {
    let mut cmd = std::process::Command::new(tool_path);
    cmd.args(args);
    if let Some(c) = cwd {
        cmd.current_dir(c);
    }
    
    let output = cmd.output().map_err(|e| format!("Failed to run subprocess: {}", e))?;
    if !output.status.success() {
        return Err(format!(
            "Command failed with exit code {:?}\nStdout: {}\nStderr: {}",
            output.status.code(),
            String::from_utf8_lossy(&output.stdout),
            String::from_utf8_lossy(&output.stderr)
        ));
    }
    Ok(())
}

// ==============================================================================
// Custom LZMA Block Compression Logic
// ==============================================================================

const UNCOMP_BLOCK_SIZE: usize = 0x10000;

fn compress_block_raw(data: &[u8]) -> Result<Vec<u8>, Box<dyn std::error::Error>> {
    let mut props = lzma_sdk_rs::LzmaProps::for_level(5, 1 << 14);
    props.dict_size = 1 << 14;
    props.lc = 3;
    props.lp = 0;
    props.pb = 2;
    props.fb = 273;

    let dest = lzma_sdk_rs::encode(data, &props);
    Ok(dest)
}

fn decompress_block_raw(
    raw_data: &[u8],
    uncomp_size: u64,
    lc: u32,
    lp: u32,
    pb: u32,
    dict_size: u32,
) -> Result<Vec<u8>, Box<dyn std::error::Error>> {
    let prop_byte = ((pb * 5 + lp) * 9 + lc) as u8;
    
    let mut props = [0u8; 5];
    props[0] = prop_byte;
    props[1..5].copy_from_slice(&dict_size.to_le_bytes());
    
    let decompressed = lzma_sdk_rs::decode_raw(raw_data, &props, uncomp_size as usize);
    
    Ok(decompressed)
}

fn decompress_data(buf: &[u8]) -> Result<Vec<u8>, Box<dyn std::error::Error>> {
    if buf.len() < 16 {
        return Ok(Vec::new());
    }

    let has_prefix;
    let prop_no_prefix = buf[8];
    let prop_with_prefix = buf[12];

    if prop_with_prefix == 0x5d && prop_no_prefix != 0x5d {
        has_prefix = true;
    } else if prop_no_prefix == 0x5d && prop_with_prefix != 0x5d {
        has_prefix = false;
    } else {
        let val1 = u32::from_le_bytes([buf[0], buf[1], buf[2], buf[3]]);
        if val1 > UNCOMP_BLOCK_SIZE as u32 {
            has_prefix = true;
        } else {
            let val2 = u32::from_le_bytes([buf[4], buf[5], buf[6], buf[7]]);
            if val1 == val2 {
                has_prefix = true;
            } else {
                has_prefix = false;
            }
        }
    }

    let total_uncomp_size = if has_prefix {
        u32::from_le_bytes([buf[0], buf[1], buf[2], buf[3]]) as usize
    } else {
        0
    };

    eprintln!("decompress_data: buf.len()={}, has_prefix={}, total_uncomp_size={}", buf.len(), has_prefix, total_uncomp_size);

    let start_pos = if has_prefix { 4 } else { 0 };
    let mut pos = start_pos;
    let mut result_data = Vec::new();

    while pos < buf.len() {
        if pos + 16 > buf.len() {
            eprintln!("decompress_data: breaking because pos + 16 > buf.len() (pos={}, buf.len()={})", pos, buf.len());
            break;
        }

        let block_uncomp_size = u32::from_le_bytes([buf[pos], buf[pos+1], buf[pos+2], buf[pos+3]]);
        let block_comp_size = u32::from_le_bytes([buf[pos+4], buf[pos+5], buf[pos+6], buf[pos+7]]);
        if block_uncomp_size == 0 || block_comp_size == 0 {
            eprintln!("decompress_data: breaking because block_uncomp_size={} or block_comp_size={}", block_uncomp_size, block_comp_size);
            break;
        }

        let lzma_params = &buf[pos+8..pos+13];
        let payload_start = pos + 16;
        let payload_end = payload_start + block_comp_size as usize;
        if payload_end > buf.len() {
            eprintln!("decompress_data: breaking because payload_end > buf.len() (payload_end={}, buf.len()={})", payload_end, buf.len());
            break;
        }

        let payload = &buf[payload_start..payload_end];

        let prop_byte = lzma_params[0];
        let pb = (prop_byte / 45) as u32;
        let temp = prop_byte - (pb * 45) as u8;
        let lp = (temp / 9) as u32;
        let lc = (temp % 9) as u32;
        let dict_size = u32::from_le_bytes([lzma_params[1], lzma_params[2], lzma_params[3], lzma_params[4]]);

        let decompressed_block = match decompress_block_raw(
            payload,
            block_uncomp_size as u64,
            lc,
            lp,
            pb,
            dict_size,
        ) {
            Ok(d) => d,
            Err(e) => {
                eprintln!("decompress_data: decompress_block_raw failed at pos={}: {}", pos, e);
                return Err(e);
            }
        };
        result_data.extend_from_slice(&decompressed_block);

        pos += ((block_comp_size as usize + 0x1f) / 0x10) * 0x10;

        if total_uncomp_size > 0 && result_data.len() >= total_uncomp_size {
            break;
        }
    }

    if total_uncomp_size > 0 && result_data.len() > total_uncomp_size {
        result_data.truncate(total_uncomp_size);
    }

    eprintln!("decompress_data: finished successfully. result_data.len()={}", result_data.len());
    Ok(result_data)
}

fn compress_data(buf: &[u8]) -> Result<Vec<u8>, Box<dyn std::error::Error>> {
    let size = buf.len();
    let mut remain = size;
    let mut pos = 0;
    let mut data = Vec::new();

    while remain > 0 {
        let block_size = if remain > UNCOMP_BLOCK_SIZE {
            UNCOMP_BLOCK_SIZE
        } else {
            remain
        };

        let block = &buf[pos..pos+block_size];
        pos += block_size;
        remain -= block_size;

        let dst = compress_block_raw(block)?;

        let mut block_head = Vec::with_capacity(16);
        block_head.extend_from_slice(&(block_size as u32).to_le_bytes());
        block_head.extend_from_slice(&(dst.len() as u32).to_le_bytes());
        block_head.extend_from_slice(b"\x5d\x00\x40\x00\x00\x00\x00\x00");

        let mut block_data = block_head;
        block_data.extend_from_slice(&dst);

        let pad = (16 - (block_data.len() % 16)) % 16;
        if pad > 0 {
            block_data.extend(std::iter::repeat(0).take(pad));
        }

        data.extend_from_slice(&block_data);
    }

    let mut result = Vec::with_capacity(4 + data.len());
    result.extend_from_slice(&(size as u32).to_le_bytes());
    result.extend_from_slice(&data);
    Ok(result)
}

// ==============================================================================
// DDS & Image Conversions
// ==============================================================================

fn detect_dds_format(dds_bytes: &[u8]) -> (String, Option<String>) {
    if dds_bytes.len() < 128 {
        return ("-rgb32".to_string(), None);
    }
    let pf_flags = u32::from_le_bytes([dds_bytes[80], dds_bytes[81], dds_bytes[82], dds_bytes[83]]);
    let pf_fourcc = &dds_bytes[84..88];
    let pf_rgb_bit_count = u32::from_le_bytes([dds_bytes[88], dds_bytes[89], dds_bytes[90], dds_bytes[91]]);

    if pf_flags & 0x04 != 0 {
        if pf_fourcc == b"DXT1" {
            return ("-bc1".to_string(), None);
        } else if pf_fourcc == b"DXT3" {
            return ("-bc2".to_string(), None);
        } else if pf_fourcc == b"DXT5" {
            return ("-bc3".to_string(), None);
        }
    }

    if pf_rgb_bit_count == 32 {
        ("-rgb32".to_string(), None)
    } else if pf_rgb_bit_count == 16 {
        ("-rgb16".to_string(), None)
    } else if pf_rgb_bit_count == 8 {
        ("-rgb8".to_string(), None)
    } else {
        ("-rgb32".to_string(), None)
    }
}

fn dds_to_png(dds_bytes: &[u8], png_path: &Path) -> Result<(), Box<dyn std::error::Error>> {
    if dds_bytes.len() < 128 || &dds_bytes[0..4] != b"DDS " {
        return Err("Invalid DDS magic".into());
    }

    let height = u32::from_le_bytes([dds_bytes[12], dds_bytes[13], dds_bytes[14], dds_bytes[15]]);
    let width = u32::from_le_bytes([dds_bytes[16], dds_bytes[17], dds_bytes[18], dds_bytes[19]]);
    let pf_flags = u32::from_le_bytes([dds_bytes[80], dds_bytes[81], dds_bytes[82], dds_bytes[83]]);
    let pf_fourcc = [dds_bytes[84], dds_bytes[85], dds_bytes[86], dds_bytes[87]];
    let pf_rgb_bit_count = u32::from_le_bytes([dds_bytes[88], dds_bytes[89], dds_bytes[90], dds_bytes[91]]);
    let r_mask = u32::from_le_bytes([dds_bytes[92], dds_bytes[93], dds_bytes[94], dds_bytes[95]]);
    let g_mask = u32::from_le_bytes([dds_bytes[96], dds_bytes[97], dds_bytes[98], dds_bytes[99]]);
    let b_mask = u32::from_le_bytes([dds_bytes[100], dds_bytes[101], dds_bytes[102], dds_bytes[103]]);
    let a_mask = u32::from_le_bytes([dds_bytes[104], dds_bytes[105], dds_bytes[106], dds_bytes[107]]);

    let body = &dds_bytes[128..];

    // Compressed DXT formats
    if pf_flags & 0x04 != 0 && pf_fourcc != [0, 0, 0, 0] {
        let tmp_dds_path = png_path.with_extension("dds_to_png.dds");
        let tmp_tga_path = png_path.with_extension("tga");
        fs::write(&tmp_dds_path, dds_bytes)?;
        
        let nvdec_tool = find_tool("nvdecompress")?;
        let tmp_dds_str = clean_win32_path(&tmp_dds_path);
        let tmp_tga_str = clean_win32_path(&tmp_tga_path);
        
        run_subprocess(
            &nvdec_tool,
            &["-format", "tga", &tmp_dds_str, &tmp_tga_str],
            None,
        ).map_err(|e| format!("nvdecompress failed: {}", e))?;
        
        // Read TGA manually because nvdecompress produces a TGA variant not supported by image crate ("Unknown(32)")
        let tga_bytes = fs::read(&tmp_tga_path).map_err(|e| format!("Failed to read TGA: {}", e))?;
        if tga_bytes.len() < 18 {
            return Err("TGA file too small".into());
        }
        let width = u16::from_le_bytes([tga_bytes[12], tga_bytes[13]]) as u32;
        let height = u16::from_le_bytes([tga_bytes[14], tga_bytes[15]]) as u32;
        let bpp = tga_bytes[16];
        if bpp != 32 {
            return Err(format!("Unsupported TGA bpp: {}", bpp).into());
        }
        
        let descriptor = tga_bytes[17];
        let origin_top_left = (descriptor & 0x20) != 0;
        
        let pixel_data = &tga_bytes[18..];
        let expected_size = (width * height * 4) as usize;
        if pixel_data.len() < expected_size {
            return Err("TGA pixel data too small".into());
        }
        
        let mut img = image::RgbaImage::new(width, height);
        for y in 0..height {
            let src_y = if origin_top_left { y } else { height - 1 - y };
            for x in 0..width {
                let offset = ((src_y * width + x) * 4) as usize;
                let b = pixel_data[offset];
                let g = pixel_data[offset + 1];
                let r = pixel_data[offset + 2];
                let a = pixel_data[offset + 3];
                img.put_pixel(x, y, image::Rgba([r, g, b, a]));
            }
        }
        
        if let Some(parent) = png_path.parent() {
            fs::create_dir_all(parent)?;
        }
        img.save(png_path)?;
        
        let _ = fs::remove_file(&tmp_tga_path);
        let _ = fs::remove_file(&tmp_dds_path);
        return Ok(());
    }

    // Generic uncompressed mask scale extractor
    let get_channel = |pixel: u32, mask: u32, default: u8| -> u8 {
        if mask == 0 {
            return default;
        }
        let shift = mask.trailing_zeros();
        let val = (pixel & mask) >> shift;
        let max_val = mask >> shift;
        if max_val == 0 {
            return 0;
        }
        ((val * 255) / max_val) as u8
    };

    let bytes_per_pixel = (pf_rgb_bit_count / 8) as usize;
    let mut rgba = vec![0u8; (width * height * 4) as usize];

    for i in 0..(width * height) as usize {
        let offset = i * bytes_per_pixel;
        if offset + bytes_per_pixel <= body.len() {
            let pixel_bytes = &body[offset..offset + bytes_per_pixel];
            let mut pixel = 0u32;
            for (j, &b) in pixel_bytes.iter().enumerate() {
                pixel |= (b as u32) << (j * 8);
            }

            let r = get_channel(pixel, r_mask, 0);
            let g = if g_mask == 0 && b_mask == 0 { r } else { get_channel(pixel, g_mask, 0) };
            let b = if g_mask == 0 && b_mask == 0 { r } else { get_channel(pixel, b_mask, 0) };
            let a = get_channel(pixel, a_mask, 255);

            rgba[i * 4] = r;
            rgba[i * 4 + 1] = g;
            rgba[i * 4 + 2] = b;
            rgba[i * 4 + 3] = a;
        }
    }

    image::save_buffer(png_path, &rgba, width, height, image::ColorType::Rgba8)?;
    Ok(())
}

fn clean_win32_path(path: &Path) -> String {
    let s = path.to_string_lossy().to_string();
    if s.starts_with(r"\\?\") {
        s[4..].to_string()
    } else {
        s
    }
}

fn convert_gtf_to_png(gtf_bytes: &[u8], png_path: &Path) -> Result<(String, String), Box<dyn std::error::Error>> {
    let gtf = gtfdds_rs::GtfImage::from_bytes(gtf_bytes.to_vec())
        .map_err(|e| format!("gtfdds_rs parse failed: {}", e))?;
    
    if gtf.count() == 0 {
        return Err("No textures found in GTF".into());
    }

    let dds_bytes = gtf.texture(0).map_err(|e| format!("gtf texture failed: {}", e))?
        .convert_to_dds_bytes().map_err(|e| format!("convert_to_dds_bytes failed: {}", e))?;

    let (dds_format, _) = detect_dds_format(&dds_bytes);

    dds_to_png(&dds_bytes, png_path)?;

    let header_base64 = if dds_bytes.len() >= 128 {
        use base64::Engine;
        base64::engine::general_purpose::STANDARD.encode(&dds_bytes[0..128])
    } else {
        "".to_string()
    };

    Ok((dds_format, header_base64))
}

fn convert_png_to_gtf(
    png_path: &Path,
    dds_format: &str,
    orig_dds_header_b64: Option<&str>,
    orig_gtf_header: Option<&[u8]>,
) -> Result<Vec<u8>, Box<dyn std::error::Error>> {
    let tmp_dds_path = png_path.with_extension("dds.tmp");

    let mut is_dxt = dds_format.starts_with("-bc");
    let mut actual_dds_format = dds_format.to_string();

    if !is_dxt {
        if let Some(b64) = orig_dds_header_b64 {
            use base64::Engine;
            if let Ok(hdr) = base64::engine::general_purpose::STANDARD.decode(b64) {
                if hdr.len() >= 128 {
                    let pf_flags = u32::from_le_bytes([hdr[80], hdr[81], hdr[82], hdr[83]]);
                    let pf_fourcc = &hdr[84..88];
                    if pf_flags & 0x04 != 0 {
                        is_dxt = true;
                        if pf_fourcc == b"DXT1" {
                            actual_dds_format = "-bc1".to_string();
                        } else if pf_fourcc == b"DXT3" {
                            actual_dds_format = "-bc2".to_string();
                        } else if pf_fourcc == b"DXT5" {
                            actual_dds_format = "-bc3".to_string();
                        }
                    }
                }
            }
        }
    }

    if is_dxt {
        let nvcompress_tool = find_tool("nvcompress")?;
        let mut args = vec!["-nomips", "-nocuda", &actual_dds_format];
        if actual_dds_format == "-bc3" || actual_dds_format == "-bc2" {
            args.push("-alpha");
        }
        let png_abs = fs::canonicalize(png_path)?;
        let png_str = clean_win32_path(&png_abs);
        args.push(&png_str);
        let tmp_dds_str = clean_win32_path(&tmp_dds_path);
        args.push(&tmp_dds_str);
        run_subprocess(&nvcompress_tool, &args, None)
            .map_err(|e| format!("nvcompress failed: {}", e))?;
    } else {
        // Uncompressed: Manually pack using original header masks
        if let Some(b64) = orig_dds_header_b64 {
            use base64::Engine;
            let orig_hdr = base64::engine::general_purpose::STANDARD.decode(b64)?;
            if orig_hdr.len() >= 128 {
                let pf_rgb_bit_count = u32::from_le_bytes([orig_hdr[88], orig_hdr[89], orig_hdr[90], orig_hdr[91]]);
                
                if pf_rgb_bit_count == 8 {
                    // 8-bit palette textures are destroyed by PNG extraction because it converts them to grayscale.
                    // Repacking them manually as grayscale corrupts the palette.
                    // Fallback to nvcompress -rgb8 to output 32-bit truecolor, which the PS3 engine supports.
                    let nvcompress_tool = find_tool("nvcompress")?;
                    let mut args = vec!["-nomips", "-nocuda", "-rgb8"];
                    let png_abs = fs::canonicalize(png_path)?;
                    let png_str = clean_win32_path(&png_abs);
                    args.push(&png_str);
                    let tmp_dds_str = clean_win32_path(&tmp_dds_path);
                    args.push(&tmp_dds_str);
                    run_subprocess(&nvcompress_tool, &args, None)
                        .map_err(|e| format!("nvcompress failed: {}", e))?;
                } else {
                    let r_mask = u32::from_le_bytes([orig_hdr[92], orig_hdr[93], orig_hdr[94], orig_hdr[95]]);
                    let g_mask = u32::from_le_bytes([orig_hdr[96], orig_hdr[97], orig_hdr[98], orig_hdr[99]]);
                    let b_mask = u32::from_le_bytes([orig_hdr[100], orig_hdr[101], orig_hdr[102], orig_hdr[103]]);
                    let a_mask = u32::from_le_bytes([orig_hdr[104], orig_hdr[105], orig_hdr[106], orig_hdr[107]]);

                    let img = image::open(png_path)?.to_rgba8();
                    let (width, height) = img.dimensions();
                    let bytes_per_pixel = (pf_rgb_bit_count / 8) as usize;

                    let mut dds_out = orig_hdr.to_vec(); // Start with original header
                    // Update width and height in header just in case it was resized
                    dds_out[12..16].copy_from_slice(&(height as u32).to_le_bytes());
                    dds_out[16..20].copy_from_slice(&(width as u32).to_le_bytes());

                    // Clear mipmap count if we are not generating mipmaps
                    dds_out[28..32].copy_from_slice(&0u32.to_le_bytes());
                    // Remove DDSD_MIPMAPCOUNT from flags
                    let mut flags = u32::from_le_bytes([dds_out[8], dds_out[9], dds_out[10], dds_out[11]]);
                    flags &= !0x20000;
                    dds_out[8..12].copy_from_slice(&flags.to_le_bytes());

                    let put_channel = |val: u8, mask: u32| -> u32 {
                        if mask == 0 { return 0; }
                        let shift = mask.trailing_zeros();
                        let max_val = mask >> shift;
                        let scaled = ((val as u32 * max_val) + 127) / 255;
                        (scaled & max_val) << shift
                    };

                    for pixel in img.pixels() {
                        let (r, g, b, a) = (pixel[0], pixel[1], pixel[2], pixel[3]);
                        let packed = put_channel(r, r_mask) | put_channel(g, g_mask) | put_channel(b, b_mask) | put_channel(a, a_mask);
                        let packed_bytes = packed.to_le_bytes();
                        dds_out.extend_from_slice(&packed_bytes[0..bytes_per_pixel]);
                    }

                    fs::write(&tmp_dds_path, &dds_out)?;
                }
            } else {
                return Err("Original DDS header too short".into());
            }
        } else {
            return Err("Missing original DDS header for uncompressed repack".into());
        }
    }

    let dds_bytes = fs::read(&tmp_dds_path)?;
    let dds = gtfdds_rs::DdsImage::from_bytes(dds_bytes, gtfdds_rs::ConvertOptions::empty())
        .map_err(|e| format!("gtfdds_rs parse DDS failed: {}", e))?;
        
    let mut gtf_bytes = dds.convert_to_gtf_bytes()
        .map_err(|e| format!("convert_to_gtf_bytes failed: {}", e))?;

    // Preserve original GTF properties
    if let Some(orig_hdr) = orig_gtf_header {
        if orig_hdr.len() >= 128 && gtf_bytes.len() >= 128 {
            // Restore Version (some games use 02 01 01 ff instead of 02 02 00 00)
            gtf_bytes[0..4].copy_from_slice(&orig_hdr[0..4]);
            
            // Restore Format sRGB bit
            let orig_fmt = orig_hdr[24];
            let mut new_fmt = gtf_bytes[24];
            if (orig_fmt & 0x20) != 0 {
                new_fmt |= 0x20;
            }
            gtf_bytes[24] = new_fmt;
            
            // Restore TextureRemap (crucial! default 00 00 00 00 maps all channels to alpha)
            gtf_bytes[28..32].copy_from_slice(&orig_hdr[28..32]);
        }
    }

    let _ = fs::remove_file(&tmp_dds_path);

    Ok(gtf_bytes)
}

// ==============================================================================
// Format Detection
// ==============================================================================

fn detect_extension(data: &[u8]) -> &'static str {
    if data.len() < 16 {
        return ".unknown";
    }
    let magic1 = u32::from_le_bytes([data[0], data[1], data[2], data[3]]);
    let magic2 = u32::from_le_bytes([data[4], data[5], data[6], data[7]]);
    let magic3 = u32::from_le_bytes([data[8], data[9], data[10], data[11]]);
    let magic4 = u32::from_le_bytes([data[12], data[13], data[14], data[15]]);

    if magic1 == 0x67452301 {
        ".eg"
    } else if magic1 == 0xFF010102 {
        ".gtf"
    } else if magic1 == 0x53414E49 {
        ".inas"
    } else if magic1 > 0 && magic2 == 0 && magic3 == 0 && magic4 == 0 {
        ".pkgdds"
    } else if data.starts_with(b"RIFF") {
        ".at3"
    } else {
        ".unknown"
    }
}

// ==============================================================================
// DAR Commands
// ==============================================================================

fn extract_dar_cmd(
    dar_path: &str,
    output_dir: &str,
    clean: bool,
    only_image: bool,
    use_hash: bool,
) -> Result<(), Box<dyn std::error::Error>> {
    println!("Extracting DAR: {} -> {}", dar_path, output_dir);
    fs::create_dir_all(output_dir)?;

    let mut f = File::open(dar_path)?;
    let mut header = [0u8; 16];
    f.read_exact(&mut header)?;

    if &header[0..2] != b"\xac\x0d" {
        return Err("Error: Bad DAR file magic.".into());
    }

    let files_count = u32::from_le_bytes([header[8], header[9], header[10], header[11]]);
    println!("Total files in DAR: {}", files_count);

    let mut index_table = vec![0u8; (files_count * 32) as usize];
    f.read_exact(&mut index_table)?;

    let mut meta_entries = Vec::new();

    for i in 0..files_count {
        let entry_offset = (i * 32) as usize;
        let entry_data = &index_table[entry_offset..entry_offset + 32];
        
        let size = u32::from_le_bytes([entry_data[0], entry_data[1], entry_data[2], entry_data[3]]);
        let zsize = u32::from_le_bytes([entry_data[4], entry_data[5], entry_data[6], entry_data[7]]);
        let offset = u64::from_le_bytes([
            entry_data[8], entry_data[9], entry_data[10], entry_data[11],
            entry_data[12], entry_data[13], entry_data[14], entry_data[15]
        ]);
        let meta_bytes = &entry_data[16..32];

        f.seek(SeekFrom::Start(offset))?;
        
        let is_compressed = zsize > 0;
        let payload = if !is_compressed {
            let mut p = vec![0u8; size as usize];
            f.read_exact(&mut p)?;
            p
        } else {
            let mut comp = vec![0u8; zsize as usize];
            f.read_exact(&mut comp)?;
            match decompress_data(&comp) {
                Ok(mut decomp) => {
                    // Truncate to the declared logical size from the DAR index.
                    // The LZMA decoder may output trailing padding bytes beyond the
                    // declared size. Those extra bytes are NOT part of the file payload.
                    if decomp.len() > size as usize {
                        decomp.truncate(size as usize);
                    }
                    decomp
                },
                Err(e) => {
                    eprintln!("Warning: Failed to decompress file index {}: {}", i, e);
                    comp
                }
            }
        };

        let detected_ext = detect_extension(&payload);
        
        let mut should_extract = true;
        if only_image {
            let is_texture = detected_ext == ".gtf" || detected_ext == ".pkgdds" || detected_ext == ".eg";
            if !is_texture {
                should_extract = false;
            }
        }

        let mut entry_meta = DarMetaEntry {
            index: i,
            ext: detected_ext.to_string(),
            meta: hex::encode(meta_bytes),
            original_compressed: is_compressed,
            clean_type: None,
            dds_format: None,
            orig_dds_header: None,
            orig_gtf_header: None,
            png_hash: None,
            header_extra: None,
            pkgdds_entries: None,
            eg_meta: None,
        };

        if should_extract {
            let out_name = format!("{:05}{}", i, detected_ext);
            let out_path = Path::new(output_dir).join(&out_name);

            if clean && (detected_ext == ".gtf" || detected_ext == ".pkgdds" || detected_ext == ".eg") {
                println!("Performing clean extraction for index {} ({})", i, detected_ext);
                entry_meta.clean_type = Some(detected_ext[1..].to_string());

                if detected_ext == ".gtf" {
                    let png_name = format!("{:05}.png", i);
                    let png_path = Path::new(output_dir).join(png_name);
                    match convert_gtf_to_png(&payload, &png_path) {
                        Ok((fmt, hdr)) => {
                            entry_meta.dds_format = Some(fmt);
                            if !hdr.is_empty() {
                                entry_meta.orig_dds_header = Some(hdr);
                            }
                            if use_hash {
                                if let Ok(png_bytes) = fs::read(&png_path) {
                                    entry_meta.png_hash = Some(hash_bytes(&png_bytes));
                                }
                            }
                        }
                        Err(e) => {
                            eprintln!("Error converting GTF to PNG at index {}: {}. Saving raw.", i, e);
                            fs::write(&out_path, &payload)?;
                            entry_meta.clean_type = None;
                        }
                    }
                    if payload.len() >= 128 {
                        use base64::Engine;
                        entry_meta.orig_gtf_header = Some(base64::engine::general_purpose::STANDARD.encode(&payload[0..128]));
                    }
                } else if detected_ext == ".pkgdds" {
                    let clean_dir = Path::new(output_dir).join(format!("{:05}_clean", i));
                    fs::create_dir_all(&clean_dir)?;
                    
                    // Extract PKGDDS and convert all GTFs to PNG
                    match extract_pkgdds_internal(&payload, &clean_dir, true, use_hash) {
                        Ok(pkg_meta) => {
                            entry_meta.header_extra = Some(pkg_meta.header_extra);
                            entry_meta.pkgdds_entries = Some(pkg_meta.entries);
                        }
                        Err(e) => {
                            eprintln!("Error unpacking PKGDDS at index {}: {}. Saving raw.", i, e);
                            let _ = fs::remove_dir_all(&clean_dir);
                            fs::write(&out_path, &payload)?;
                            entry_meta.clean_type = None;
                        }
                    }
                } else if detected_ext == ".eg" {
                    let clean_dir = Path::new(output_dir).join(format!("{:05}_clean", i));
                    fs::create_dir_all(&clean_dir)?;

                    match extract_eg_internal(&payload, &clean_dir, true, use_hash) {
                        Ok(eg_meta) => {
                            entry_meta.eg_meta = Some(eg_meta);
                        }
                        Err(e) => {
                            eprintln!("Error unpacking EG container at index {}: {}. Saving raw.", i, e);
                            let _ = fs::remove_dir_all(&clean_dir);
                            fs::write(&out_path, &payload)?;
                            entry_meta.clean_type = None;
                        }
                    }
                }
            } else {
                // Write payload directly
                fs::write(&out_path, &payload)?;
            }
        }

        meta_entries.push(entry_meta);
    }

    // Write dar_meta.json
    let meta_path = Path::new(output_dir).join("dar_meta.json");
    let dar_meta = DarMeta {
        files_count: meta_entries.len() as u32,
        entries: meta_entries,
    };
    let meta_file = File::create(meta_path)?;
    serde_json::to_writer_pretty(meta_file, &dar_meta)?;

    println!("DAR Extraction completed successfully.");
    Ok(())
}

fn repack_dar_cmd(
    dar_path: &str,
    modified_dir: &str,
    output_dar: &str,
    _clean: bool,
    _threads_opt: Option<usize>,
    use_hash: bool,
) -> Result<(), Box<dyn std::error::Error>> {
    println!("Repacking DAR: Template={}, Modified={} -> Output={}", dar_path, modified_dir, output_dar);
    
    let meta_path = Path::new(modified_dir).join("dar_meta.json");
    if !meta_path.exists() {
        return Err(format!("Error: metadata file '{:?}' not found.", meta_path).into());
    }

    let meta_file = File::open(&meta_path).map_err(|e| format!("Failed to open meta_path {:?}: {}", meta_path, e))?;
    let meta_data: DarMeta = serde_json::from_reader(meta_file)?;

    let mut orig_f = File::open(dar_path).map_err(|e| format!("Failed to open dar_path {}: {}", dar_path, e))?;
    let mut header = [0u8; 16];
    orig_f.read_exact(&mut header)?;
    let mut out_f = File::create(output_dar).map_err(|e| format!("Failed to create output_dar {}: {}", output_dar, e))?;

    // Write placeholder header and index table
    let placeholder_size = 16 + meta_data.entries.len() * 32;
    out_f.write_all(&vec![0u8; placeholder_size])?;

    // Read original entry details to get original offsets and sizes
    #[derive(Clone)]
    struct RepackEntry {
        entry: DarMetaEntry,
        original_offset: u64,
        original_size: u32,
        original_zsize: u32,
    }

    let mut repack_entries = Vec::new();
    for entry in &meta_data.entries {
        let i = entry.index;
        orig_f.seek(SeekFrom::Start(16 + i as u64 * 32))?;
        let mut orig_entry = [0u8; 16];
        orig_f.read_exact(&mut orig_entry)?;
        let orig_size = u32::from_le_bytes([orig_entry[0], orig_entry[1], orig_entry[2], orig_entry[3]]);
        let orig_zsize = u32::from_le_bytes([orig_entry[4], orig_entry[5], orig_entry[6], orig_entry[7]]);
        let orig_offset = u64::from_le_bytes([
            orig_entry[8], orig_entry[9], orig_entry[10], orig_entry[11],
            orig_entry[12], orig_entry[13], orig_entry[14], orig_entry[15]
        ]);

        repack_entries.push(RepackEntry {
            entry: entry.clone(),
            original_offset: orig_offset,
            original_size: orig_size,
            original_zsize: orig_zsize,
        });
    }

    // Sort by original offset to preserve original archive layout order
    let mut sorted_repack = repack_entries.clone();
    sorted_repack.sort_by_key(|e| e.original_offset);

    use rayon::prelude::*;

    // Vector to store output size, zsize, offset for each entry index
    let max_index = meta_data.entries.iter().map(|e| e.index).max().unwrap_or(0) as usize;
    let mut repack_results = vec![(0u32, 0u32, 0u64); max_index + 1];

    // Process sorted entries in chunks of 64 to control memory usage
    let chunk_size = 64;
    for chunk in sorted_repack.chunks(chunk_size) {
        // Parallel pre-processing phase for the current chunk
        let processed_payloads: Vec<(usize, Option<Vec<u8>>)> = chunk
            .par_iter()
            .map(|rentry| {
                let entry = &rentry.entry;
                let i = entry.index as usize;
                let ext = &entry.ext;
                let was_compressed = entry.original_compressed;

                let mut size = 0u32;
                let mut zsize = 0u32;
                let mut payload = Vec::new();
                let mut payload_written = false;

                if let Some(ref clean_type) = entry.clean_type {
                    if clean_type == "gtf" {
                        let png_name = format!("{:05}.png", i);
                        let png_path = Path::new(modified_dir).join(png_name);
                        if png_path.exists() {
                            let dds_format = entry.dds_format.as_deref().unwrap_or("-rgb32");
                            let orig_hdr = entry.orig_dds_header.as_deref();
                            let _orig_gtf_hdr = entry.orig_gtf_header.as_deref();
                            
                            // Extract original GTF header from original DAR
                            let mut orig_gtf_header = None;
                            if let Ok(mut df) = File::open(dar_path) {
                                if df.seek(SeekFrom::Start(rentry.original_offset)).is_ok() {
                                    let read_size = if rentry.original_zsize > 0 { rentry.original_zsize } else { rentry.original_size };
                                    let mut comp = vec![0u8; read_size as usize];
                                    if df.read_exact(&mut comp).is_ok() {
                                        let orig_bytes = if rentry.original_zsize > 0 {
                                            decompress_data(&comp).unwrap_or(comp)
                                        } else {
                                            comp
                                        };
                                        if orig_bytes.len() >= 128 {
                                            orig_gtf_header = Some(orig_bytes[0..128].to_vec());
                                        }
                                    }
                                }
                            }

                            if let Ok(raw_data) = convert_png_to_gtf(&png_path, dds_format, orig_hdr, orig_gtf_header.as_deref()) {
                                size = raw_data.len() as u32;
                                if was_compressed {
                                    if let Ok(comp) = compress_data(&raw_data) {
                                        let comp_payload = &comp[4..];
                                        zsize = comp_payload.len() as u32;
                                        payload.extend_from_slice(comp_payload);
                                        payload_written = true;
                                    }
                                } else {
                                    zsize = 0;
                                    payload.extend_from_slice(&raw_data);
                                    payload_written = true;
                                }
                            }
                        }
                    } else if clean_type == "pkgdds" {
                        let clean_dir = Path::new(modified_dir).join(format!("{:05}_clean", i));
                        if clean_dir.exists() {
                            let pkg_entries = entry.pkgdds_entries.as_ref().unwrap();
                            if let Ok(header_extra) = hex::decode(entry.header_extra.as_ref().unwrap()) {
                                let mut orig_pkgdds_bytes = None;
                                if let Ok(mut df) = File::open(dar_path) {
                                    if df.seek(SeekFrom::Start(rentry.original_offset)).is_ok() {
                                        let read_size = if rentry.original_zsize > 0 { rentry.original_zsize } else { rentry.original_size };
                                        let mut comp = vec![0u8; read_size as usize];
                                        if df.read_exact(&mut comp).is_ok() {
                                            if rentry.original_zsize > 0 {
                                                orig_pkgdds_bytes = decompress_data(&comp).ok();
                                            } else {
                                                orig_pkgdds_bytes = Some(comp);
                                            }
                                        }
                                    }
                                }
                                if let Ok(raw_data) = repack_pkgdds_internal(&clean_dir, pkg_entries, &header_extra, orig_pkgdds_bytes.as_deref(), use_hash) {
                                    size = raw_data.len() as u32;
                                    if was_compressed {
                                        if let Ok(comp) = compress_data(&raw_data) {
                                            let comp_payload = &comp[4..];
                                            zsize = comp_payload.len() as u32;
                                            payload.extend_from_slice(comp_payload);
                                            payload_written = true;
                                        }
                                    } else {
                                        zsize = 0;
                                        payload.extend_from_slice(&raw_data);
                                        payload_written = true;
                                    }
                                }
                            }
                        }
                    } else if clean_type == "eg" {
                        let clean_dir = Path::new(modified_dir).join(format!("{:05}_clean", i));
                        if clean_dir.exists() {
                            let eg_meta = entry.eg_meta.as_ref().unwrap();
                            let mut orig_eg_bytes = None;
                            if let Ok(mut df) = File::open(dar_path) {
                                if df.seek(SeekFrom::Start(rentry.original_offset)).is_ok() {
                                    let read_size = if rentry.original_zsize > 0 { rentry.original_zsize } else { rentry.original_size };
                                    let mut comp = vec![0u8; read_size as usize];
                                    if df.read_exact(&mut comp).is_ok() {
                                        if rentry.original_zsize > 0 {
                                            if let Ok(decomp) = decompress_data(&comp) {
                                                orig_eg_bytes = Some(decomp);
                                            }
                                        } else {
                                            orig_eg_bytes = Some(comp);
                                        }
                                    }
                                }
                            }
                            println!("calling repack_eg_internal for {}", i);
                            match repack_eg_internal(&clean_dir, eg_meta, orig_eg_bytes.as_deref(), use_hash) {
                                Ok(raw_data) => {
                                    println!("repack_eg_internal OK for {}, raw_data.len() = {}, was_compressed = {}", i, raw_data.len(), was_compressed);
                                    size = raw_data.len() as u32;
                                    if was_compressed {
                                        match compress_data(&raw_data) {
                                            Ok(comp) => {
                                                println!("compress_data OK for {}, comp.len() = {}", i, comp.len());
                                                let comp_payload = &comp[4..];
                                                zsize = comp_payload.len() as u32;
                                                payload.extend_from_slice(comp_payload);
                                                payload_written = true;
                                            }
                                            Err(e) => {
                                                eprintln!("compress_data failed for entry {}: {}", i, e);
                                            }
                                        }
                                    } else {
                                        zsize = 0;
                                        payload.extend_from_slice(&raw_data);
                                        payload_written = true;
                                    }
                                }
                                Err(e) => {
                                    eprintln!("Failed to repack EG entry {}: {}", i, e);
                                }
                            }
                        }
                    }
                }

                if !payload_written {
                    let mod_name_elzma = format!("{:05}{}.elzma", i, ext);
                    let mod_name_idx_elzma = format!("{:05}.elzma", i);
                    let mod_name_raw = format!("{:05}{}", i, ext);

                    let mut path_found = None;
                    for name in &[&mod_name_elzma, &mod_name_idx_elzma] {
                        let p = Path::new(modified_dir).join(name);
                        if p.exists() {
                            path_found = Some((p, true));
                            break;
                        }
                    }
                    if path_found.is_none() {
                        let p = Path::new(modified_dir).join(&mod_name_raw);
                        if p.exists() {
                            path_found = Some((p, false));
                        }
                    }

                    if let Some((path, is_elzma)) = path_found {
                        if let Ok(mut comp_file_data) = fs::read(path) {
                            if is_elzma {
                                size = u32::from_le_bytes([comp_file_data[0], comp_file_data[1], comp_file_data[2], comp_file_data[3]]);
                                let comp_payload = &comp_file_data[4..];
                                zsize = comp_payload.len() as u32;
                                payload.extend_from_slice(comp_payload);
                                payload_written = true;
                            } else {
                                // Recover any extra bytes (like padding or trailers)
                                let mut extra_bytes = Vec::new();
                                if let Ok(mut df) = File::open(dar_path) {
                                    if df.seek(SeekFrom::Start(rentry.original_offset)).is_ok() {
                                        let read_size = if rentry.original_zsize > 0 { rentry.original_zsize } else { rentry.original_size };
                                        let mut comp = vec![0u8; read_size as usize];
                                        if df.read_exact(&mut comp).is_ok() {
                                            let orig = if rentry.original_zsize > 0 {
                                                decompress_data(&comp).unwrap_or(comp)
                                            } else {
                                                comp
                                            };
                                            if orig.len() > rentry.original_size as usize {
                                                extra_bytes = orig[rentry.original_size as usize..].to_vec();
                                            }
                                        }
                                    }
                                }

                                if !extra_bytes.is_empty() {
                                    let comp_len = comp_file_data.len();
                                    let ex_len = extra_bytes.len();
                                    if comp_len < ex_len || &comp_file_data[comp_len - ex_len..] != extra_bytes.as_slice() {
                                        comp_file_data.extend_from_slice(&extra_bytes);
                                    }
                                }

                                size = comp_file_data.len() as u32;
                                if was_compressed {
                                    if let Ok(comp) = compress_data(&comp_file_data) {
                                        let comp_payload = &comp[4..];
                                        zsize = comp_payload.len() as u32;
                                        payload.extend_from_slice(comp_payload);
                                        payload_written = true;
                                    }
                                } else {
                                    zsize = 0;
                                    payload.extend_from_slice(&comp_file_data);
                                    payload_written = true;
                                }
                            }
                        }
                    }
                }

                if payload_written {
                    let mut full_payload = Vec::with_capacity(8 + payload.len());
                    full_payload.extend_from_slice(&size.to_le_bytes());
                    full_payload.extend_from_slice(&zsize.to_le_bytes());
                    full_payload.extend_from_slice(&payload);
                    (i, Some(full_payload))
                } else {
                    (i, None)
                }
            })
            .collect();

        // Sequential write phase for the current chunk
        for (rentry, (idx, payload_opt)) in chunk.iter().zip(processed_payloads) {
            let i = rentry.entry.index as usize;
            assert_eq!(i, idx);

            // Enforce 16-byte alignment on all payload offsets
            let current_pos = out_f.seek(SeekFrom::Current(0))?;
            let align_pad = (16 - (current_pos % 16)) % 16;
            if align_pad > 0 {
                out_f.write_all(&vec![0u8; align_pad as usize])?;
            }
            let offset = out_f.seek(SeekFrom::Current(0))?;

            let (size, zsize) = if let Some(payload_buf) = payload_opt {
                let size = u32::from_le_bytes([payload_buf[0], payload_buf[1], payload_buf[2], payload_buf[3]]);
                let zsize = u32::from_le_bytes([payload_buf[4], payload_buf[5], payload_buf[6], payload_buf[7]]);
                let payload = &payload_buf[8..];
                out_f.write_all(payload)?;
                (size, zsize)
            } else {
                // Fallback to original using rentry's original offset
                orig_f.seek(SeekFrom::Start(rentry.original_offset))?;
                let read_size = if rentry.original_zsize > 0 { rentry.original_zsize } else { rentry.original_size };
                let mut payload = vec![0u8; read_size as usize];
                orig_f.read_exact(&mut payload)?;

                out_f.write_all(&payload)?;
                (rentry.original_size, rentry.original_zsize)
            };

            repack_results[i] = (size, zsize, offset);
        }
    }

    let mut new_index_entries = Vec::new();
    for entry in &meta_data.entries {
        let i = entry.index as usize;
        let (size, zsize, offset) = repack_results[i];
        let meta_bytes = hex::decode(&entry.meta)?;

        let mut entry_buf = Vec::with_capacity(32);
        entry_buf.extend_from_slice(&size.to_le_bytes());
        entry_buf.extend_from_slice(&zsize.to_le_bytes());
        entry_buf.extend_from_slice(&offset.to_le_bytes());
        entry_buf.extend_from_slice(&meta_bytes);
        new_index_entries.push(entry_buf);
    }

    // Write final header & index table
    out_f.seek(SeekFrom::Start(0))?;
    out_f.write_all(&header)?;

    for entry_bytes in new_index_entries {
        out_f.write_all(&entry_bytes)?;
    }

    println!("DAR Repacking completed successfully.");
    Ok(())
}

// ==============================================================================
// PKGDDS Internal Functions
// ==============================================================================

fn extract_pkgdds_internal(
    pkgdds_bytes: &[u8],
    output_dir: &Path,
    clean: bool,
    use_hash: bool,
) -> Result<PkgddsMeta, Box<dyn std::error::Error>> {
    if pkgdds_bytes.len() < 16 {
        return Err("Invalid PKGDDS data size".into());
    }

    let files_count = u32::from_le_bytes([pkgdds_bytes[0], pkgdds_bytes[1], pkgdds_bytes[2], pkgdds_bytes[3]]);
    let header_extra = &pkgdds_bytes[4..16];

    let mut entries = Vec::new();
    
    for i in 0..files_count {
        let entry_offset = (16 + i * 16) as usize;
        let offset = u32::from_le_bytes([
            pkgdds_bytes[entry_offset], pkgdds_bytes[entry_offset+1],
            pkgdds_bytes[entry_offset+2], pkgdds_bytes[entry_offset+3]
        ]) as usize;
        let size = u32::from_le_bytes([
            pkgdds_bytes[entry_offset+4], pkgdds_bytes[entry_offset+5],
            pkgdds_bytes[entry_offset+6], pkgdds_bytes[entry_offset+7]
        ]) as usize;
        let meta_bytes = &pkgdds_bytes[entry_offset+8..entry_offset+16];

        let payload = &pkgdds_bytes[offset..offset+size];

        let mut entry_meta = PkgddsMetaEntry {
            index: i,
            meta: hex::encode(meta_bytes),
            original_size: size as u32,
            dds_format: None,
            orig_dds_header: None,
            png_hash: None,
        };

        if clean {
            let png_name = format!("{:03}.png", i);
            let png_path = output_dir.join(png_name);
            let (fmt, hdr) = convert_gtf_to_png(payload, &png_path)?;
            entry_meta.dds_format = Some(fmt);
            if !hdr.is_empty() {
                entry_meta.orig_dds_header = Some(hdr);
            }
            if use_hash {
                if let Ok(png_bytes) = fs::read(&png_path) {
                    entry_meta.png_hash = Some(hash_bytes(&png_bytes));
                }
            }
        } else {
            let out_name = format!("pkg_{:03}.gtf", i);
            fs::write(output_dir.join(out_name), payload)?;
        }

        entries.push(entry_meta);
    }

    Ok(PkgddsMeta {
        files_count,
        base_name: "pkg".to_string(),
        header_extra: hex::encode(header_extra),
        entries,
    })
}

fn repack_pkgdds_internal(
    clean_dir: &Path,
    entries: &[PkgddsMetaEntry],
    header_extra: &[u8],
    orig_pkgdds_bytes: Option<&[u8]>,
    use_hash: bool,
) -> Result<Vec<u8>, Box<dyn std::error::Error>> {
    let files_count = entries.len() as u32;
    
    let mut out_data = Vec::new();
    // Placeholder for header & index table
    let header_size = 16 + files_count * 16;
    out_data.extend(std::iter::repeat(0).take(header_size as usize));

    let mut new_index_entries = Vec::new();
    let mut pos = header_size;

    use rayon::prelude::*;

    let processed_payloads: Result<Vec<(u32, Vec<u8>)>, String> = entries
        .par_iter()
        .map(|entry| {
            let i = entry.index;
            let png_name = format!("{:03}.png", i);
            let png_path = clean_dir.join(&png_name);
            let gtf_name = format!("pkg_{:03}.gtf", i);
            let gtf_path = clean_dir.join(gtf_name);

            let mut orig_gtf_header = None;
            if let Some(orig_pkg) = orig_pkgdds_bytes {
                if orig_pkg.len() >= 16 {
                    let entry_offset = (16 + i * 16) as usize;
                    if entry_offset + 8 <= orig_pkg.len() {
                        let offset = u32::from_le_bytes([orig_pkg[entry_offset], orig_pkg[entry_offset+1], orig_pkg[entry_offset+2], orig_pkg[entry_offset+3]]) as usize;
                        let size = u32::from_le_bytes([orig_pkg[entry_offset+4], orig_pkg[entry_offset+5], orig_pkg[entry_offset+6], orig_pkg[entry_offset+7]]) as usize;
                        if offset + size <= orig_pkg.len() && size >= 128 {
                            orig_gtf_header = Some(orig_pkg[offset..offset+128].to_vec());
                        }
                    }
                }
            }

                        let rgb8_png_name = format!("{:03}_rgb8.png", i);
            let rgb8_png_path = clean_dir.join(&rgb8_png_name);
            let mut actual_png_path = png_path.clone();
            let mut use_png = false;
            let mut dds_format_override = None;
            
            if rgb8_png_path.exists() {
                use_png = true;
                actual_png_path = rgb8_png_path;
                dds_format_override = Some("-rgb8".to_string());
            } else if png_path.exists() {
                use_png = true;
            }

            if use_hash && use_png && dds_format_override.is_none() {
                if let Some(ref saved_hash) = entry.png_hash {
                    if let Ok(png_bytes) = fs::read(&actual_png_path) {
                        if *saved_hash == hash_bytes(&png_bytes) {
                            use_png = false;
                        }
                    }
                }
            }
            let payload = if use_png {
                let mut dds_format = entry.dds_format.as_deref().unwrap_or("-rgb32");
                if let Some(ref ow) = dds_format_override { dds_format = ow; }
                let orig_hdr = entry.orig_dds_header.as_deref();
                convert_png_to_gtf(&actual_png_path, dds_format, orig_hdr, orig_gtf_header.as_deref()).map_err(|e| e.to_string())?
            } else if gtf_path.exists() {
                fs::read(gtf_path).map_err(|e| e.to_string())?
            } else {
                return Err(format!("Missing clean texture PNG or raw GTF in: {:?}", clean_dir));
            };
            Ok((i, payload))
        })
        .collect();

    let processed_payloads = processed_payloads.map_err(|e| Box::<dyn std::error::Error>::from(e))?;
    let mut payload_map: std::collections::HashMap<u32, Vec<u8>> = processed_payloads.into_iter().collect();

    for entry in entries {
        let i = entry.index;
        let meta_bytes = hex::decode(&entry.meta)?;

        let payload = payload_map.remove(&i).unwrap();

        // Align pos to 16-byte boundary
        let align_pad = (16 - (pos % 16)) % 16;
        if align_pad > 0 {
            out_data.extend(std::iter::repeat(0).take(align_pad as usize));
            pos += align_pad;
        }

        let size = payload.len() as u32;
        out_data.extend_from_slice(&payload);

        let mut index_entry = Vec::with_capacity(16);
        index_entry.extend_from_slice(&pos.to_le_bytes());
        index_entry.extend_from_slice(&size.to_le_bytes());
        index_entry.extend_from_slice(&meta_bytes);
        new_index_entries.push(index_entry);

        pos += size;
    }

    // Write final header
    out_data[0..4].copy_from_slice(&files_count.to_le_bytes());
    out_data[4..16].copy_from_slice(header_extra);

    for (i, entry_bytes) in new_index_entries.iter().enumerate() {
        let offset = 16 + i * 16;
        out_data[offset..offset+16].copy_from_slice(entry_bytes);
    }

    Ok(out_data)
}

// ==============================================================================
// EG Internal Functions
// ==============================================================================

fn extract_eg_internal(
    eg_bytes: &[u8],
    output_dir: &Path,
    clean: bool,
    use_hash: bool,
) -> Result<EgMeta, Box<dyn std::error::Error>> {
    if eg_bytes.len() < 28 || &eg_bytes[0..4] != b"\x01\x23\x45\x67" {
        return Err("Invalid EG magic".into());
    }

    let null1 = &eg_bytes[4..12];
    let size = u32::from_be_bytes([eg_bytes[12], eg_bytes[13], eg_bytes[14], eg_bytes[15]]) as usize;
    let null2 = &eg_bytes[16..20];
    let data_offset = u32::from_be_bytes([eg_bytes[20], eg_bytes[21], eg_bytes[22], eg_bytes[23]]) as usize;
    let files = u32::from_be_bytes([eg_bytes[24], eg_bytes[25], eg_bytes[26], eg_bytes[27]]);

    let index_table_size = (files * 4) as usize;
    let index_table = &eg_bytes[28..28 + index_table_size];

    let payload_offset = 28 + index_table_size + data_offset;
    if payload_offset + size > eg_bytes.len() {
        return Err("EG container payload boundary overflow".into());
    }
    let payload = &eg_bytes[payload_offset..payload_offset + size];

    let mut eg_meta = EgMeta {
        base_name: "eg".to_string(),
        null1: hex::encode(null1),
        null2: hex::encode(null2),
        data_offset: data_offset as u32,
        files,
        index_table: hex::encode(index_table),
        dds_format: None,
        orig_dds_header: None,
        orig_gtf_header: None,
        png_hash: None,
        header_extra: None,
    };

    if clean {
        let png_path = output_dir.join("000.png");
        let (fmt, hdr) = convert_gtf_to_png(payload, &png_path)?;
        eg_meta.dds_format = Some(fmt);
        if !hdr.is_empty() {
            eg_meta.orig_dds_header = Some(hdr);
        }
        if use_hash {
            if let Ok(png_bytes) = fs::read(&png_path) {
                eg_meta.png_hash = Some(hash_bytes(&png_bytes));
            }
        }
        if payload.len() >= 128 {
            use base64::Engine;
            eg_meta.orig_gtf_header = Some(base64::engine::general_purpose::STANDARD.encode(&payload[0..128]));
        }
        let extra_data = &eg_bytes[28 + index_table_size .. payload_offset];
        if !extra_data.is_empty() {
            eg_meta.header_extra = Some(hex::encode(extra_data));
        }
    } else {
        let out_path = output_dir.join("eg_0.gtf");
        fs::write(out_path, payload)?;
    }

    Ok(eg_meta)
}

fn repack_eg_internal(
    clean_dir: &Path,
    meta: &EgMeta,
    orig_eg_bytes: Option<&[u8]>,
    use_hash: bool,
) -> Result<Vec<u8>, Box<dyn std::error::Error>> {
    let null1 = hex::decode(&meta.null1)?;
    let null2 = hex::decode(&meta.null2)?;
    let index_table = hex::decode(&meta.index_table)?;
    let data_offset = meta.data_offset as usize;
    
    let png_path = clean_dir.join("000.png");
    let gtf_path = clean_dir.join("eg_0.gtf");

    let mut orig_gtf_header = None;
    if let Some(orig) = orig_eg_bytes {
        if orig.len() >= 28 {
            let orig_files = u32::from_be_bytes([orig[24], orig[25], orig[26], orig[27]]) as usize;
            let orig_data_offset = u32::from_be_bytes([orig[20], orig[21], orig[22], orig[23]]) as usize;
            let orig_payload_offset = 28 + orig_files * 4 + orig_data_offset;
            let orig_eg_size = u32::from_be_bytes([orig[12], orig[13], orig[14], orig[15]]) as usize;
            if orig_payload_offset + orig_eg_size <= orig.len() && orig_eg_size >= 128 {
                orig_gtf_header = Some(orig[orig_payload_offset..orig_payload_offset+128].to_vec());
            }
        }
    }

        let rgb8_png_name = "000_rgb8.png";
    let rgb8_png_path = clean_dir.join(rgb8_png_name);
    let mut actual_png_path = png_path.clone();
    let mut use_png = false;
    let mut dds_format_override = None;

    if rgb8_png_path.exists() {
        use_png = true;
        actual_png_path = rgb8_png_path;
        dds_format_override = Some("-rgb8".to_string());
    } else if png_path.exists() {
        use_png = true;
    }

    if use_hash && use_png && dds_format_override.is_none() {
        if let Some(ref saved_hash) = meta.png_hash {
            if let Ok(png_bytes) = fs::read(&actual_png_path) {
                if *saved_hash == hash_bytes(&png_bytes) {
                    use_png = false;
                }
            }
        }
    }

    // Safety check for EG files:
    // If the texture is 8-bit palette, repacking it via nvcompress -rgb8 will change its size (to 32-bit),
    // which breaks the EG container offsets (like MOTI payload).
    // Manual packing also breaks it because the PNG extraction lost the palette.
    // So we MUST force skip repacking for 8-bit EG textures!
    if use_png && dds_format_override.is_none() {
        if let Some(b64) = meta.orig_dds_header.as_deref() {
            use base64::Engine;
            if let Ok(hdr) = base64::engine::general_purpose::STANDARD.decode(b64) {
                if hdr.len() >= 128 {
                    let pf_rgb_bit_count = u32::from_le_bytes([hdr[88], hdr[89], hdr[90], hdr[91]]);
                    if pf_rgb_bit_count == 8 {
                        use_png = false;
                        println!("Notice: Skipping repack for 8-bit EG effect texture {:?} to prevent palette corruption and size mismatch.", actual_png_path);
                    }
                }
            }
        }
    }
    let payload = if use_png {
        let mut dds_format = meta.dds_format.as_deref().unwrap_or("-rgb32");
        if let Some(ref ow) = dds_format_override { dds_format = ow; }
        let orig_hdr = meta.orig_dds_header.as_deref();
        convert_png_to_gtf(&actual_png_path, dds_format, orig_hdr, orig_gtf_header.as_deref())?
    } else if gtf_path.exists() {
        fs::read(gtf_path)?
    } else {
        return Err(format!("Missing clean EG texture PNG or raw GTF in: {:?}", clean_dir).into());
    };

    let size = payload.len() as u32;

    let mut out_bytes = Vec::new();
    out_bytes.extend_from_slice(b"\x01\x23\x45\x67");
    out_bytes.extend_from_slice(&null1);
    out_bytes.extend_from_slice(&size.to_be_bytes());
    out_bytes.extend_from_slice(&null2);
    out_bytes.extend_from_slice(&(data_offset as u32).to_be_bytes());
    out_bytes.extend_from_slice(&meta.files.to_be_bytes());
    out_bytes.extend_from_slice(&index_table);
    
    if let Some(extra) = &meta.header_extra {
        out_bytes.extend_from_slice(&hex::decode(extra)?);
    } else if data_offset > 0 {
        out_bytes.extend(std::iter::repeat(0).take(data_offset));
    }
    out_bytes.extend_from_slice(&payload);

    // Append original extra payload (e.g. MOTI file) if available
    if let Some(orig) = orig_eg_bytes {
        if orig.len() >= 28 {
            let orig_files = u32::from_be_bytes([orig[24], orig[25], orig[26], orig[27]]) as usize;
            let orig_data_offset = u32::from_be_bytes([orig[20], orig[21], orig[22], orig[23]]) as usize;
            let orig_eg_size = u32::from_be_bytes([orig[12], orig[13], orig[14], orig[15]]) as usize;
            let orig_payload_start = 28 + orig_files * 4 + orig_data_offset;
            let orig_extra_offset = orig_payload_start + orig_eg_size;
            if orig.len() > orig_extra_offset {
                let extra_payload = &orig[orig_extra_offset..];
                out_bytes.extend_from_slice(extra_payload);
            }
        }
    }

    Ok(out_bytes)
}

// ==============================================================================
// Standalone CLI Handlers
// ==============================================================================

fn handle_extract_dar(dar_file: &str, output_dir: &str, clean: bool, only_image: bool, use_hash: bool) {
    if let Err(e) = extract_dar_cmd(dar_file, output_dir, clean, only_image, use_hash) {
        eprintln!("Error: {}", e);
        std::process::exit(1);
    }
}

fn handle_repack_dar(dar_file: &str, modified_dir: &str, output_dar: &str, clean: bool, use_hash: bool) {
    if let Err(e) = repack_dar_cmd(dar_file, modified_dir, output_dar, clean, None, use_hash) {
        eprintln!("Error: {}", e);
        std::process::exit(1);
    }
}

fn handle_extract_ddspack(pkgdds_file: &str, output_dir: &str, clean: bool, use_hash: bool) {
    println!("Extracting PKGDDS: {} -> {}", pkgdds_file, output_dir);
    if let Err(e) = fs::create_dir_all(output_dir) {
        eprintln!("Error creating output directory: {}", e);
        std::process::exit(1);
    }

    let bytes = match fs::read(pkgdds_file) {
        Ok(b) => b,
        Err(e) => {
            eprintln!("Error reading file: {}", e);
            std::process::exit(1);
        }
    };

    match extract_pkgdds_internal(&bytes, Path::new(output_dir), clean, use_hash) {
        Ok(meta) => {
            let meta_path = Path::new(output_dir).join("pkgdds_meta.json");
            if let Ok(meta_file) = File::create(meta_path) {
                let _ = serde_json::to_writer_pretty(meta_file, &meta);
            }
            println!("PKGDDS Extraction completed successfully.");
        }
        Err(e) => {
            eprintln!("Error: {}", e);
            std::process::exit(1);
        }
    }
}

fn handle_repack_ddspack(pkgdds_file: &str, modified_dir: &str, output_pkgdds: &str, _clean: bool, use_hash: bool) {
    println!("Repacking PKGDDS: Template={}, Modified={} -> Output={}", pkgdds_file, modified_dir, output_pkgdds);
    
    let meta_path = Path::new(modified_dir).join("pkgdds_meta.json");
    let (files_count, header_extra, entries) = if meta_path.exists() {
        match File::open(meta_path) {
            Ok(file) => {
                let meta_data: PkgddsMeta = serde_json::from_reader(file).unwrap();
                (
                    meta_data.files_count,
                    hex::decode(&meta_data.header_extra).unwrap(),
                    meta_data.entries,
                )
            }
            Err(e) => {
                eprintln!("Error reading metadata: {}", e);
                std::process::exit(1);
            }
        }
    } else {
        // Reconstruct template from original
        let bytes = fs::read(pkgdds_file).unwrap();
        let files_count = u32::from_le_bytes([bytes[0], bytes[1], bytes[2], bytes[3]]);
        let header_extra = bytes[4..16].to_vec();
        
        let mut entries = Vec::new();
        for i in 0..files_count {
            let entry_offset = (16 + i * 16) as usize;
            let size = u32::from_le_bytes([
                bytes[entry_offset+4], bytes[entry_offset+5],
                bytes[entry_offset+6], bytes[entry_offset+7]
            ]);
            let meta_bytes = &bytes[entry_offset+8..entry_offset+16];
            entries.push(PkgddsMetaEntry {
                index: i,
                meta: hex::encode(meta_bytes),
                original_size: size,
                dds_format: None,
                orig_dds_header: None,
            png_hash: None,
            });
        }
        (files_count, header_extra, entries)
    };

    let mut out_data = Vec::new();
    let header_size = 16 + files_count * 16;
    out_data.extend(std::iter::repeat(0).take(header_size as usize));

    let mut new_index_entries = Vec::new();
    let mut pos = header_size;

    let orig_bytes = fs::read(pkgdds_file).unwrap();

    use rayon::prelude::*;

    let processed_payloads: Vec<(u32, Vec<u8>)> = entries
        .par_iter()
        .map(|entry| {
            let i = entry.index;
            let png_name = format!("{:03}.png", i);
            let png_path = Path::new(modified_dir).join(png_name);
            
            let mut orig_gtf_header = None;
            let entry_offset = (16 + i * 16) as usize;
            if entry_offset + 8 <= orig_bytes.len() {
                let offset = u32::from_le_bytes([orig_bytes[entry_offset], orig_bytes[entry_offset+1], orig_bytes[entry_offset+2], orig_bytes[entry_offset+3]]) as usize;
                let size = u32::from_le_bytes([orig_bytes[entry_offset+4], orig_bytes[entry_offset+5], orig_bytes[entry_offset+6], orig_bytes[entry_offset+7]]) as usize;
                if offset + size <= orig_bytes.len() && size >= 128 {
                    orig_gtf_header = Some(orig_bytes[offset..offset+128].to_vec());
                }
            }

                let mut use_png = png_path.exists();
    if use_hash && use_png {
        if let Some(ref saved_hash) = entry.png_hash {
            if let Ok(png_bytes) = fs::read(&png_path) {
                if *saved_hash == hash_bytes(&png_bytes) {
                    use_png = false;
                }
            }
        }
    }
    let payload = if use_png {
                let dds_format = entry.dds_format.as_deref().unwrap_or("-rgb32");
                let orig_hdr = entry.orig_dds_header.as_deref();
                convert_png_to_gtf(&png_path, dds_format, orig_hdr, orig_gtf_header.as_deref()).unwrap()
            } else {
                let out_name = format!("pkg_{:03}.gtf", i);
                let path = Path::new(modified_dir).join(out_name);
                if path.exists() {
                    fs::read(path).unwrap()
                } else {
                    // Read original
                    let entry_offset = (16 + i * 16) as usize;
                    let orig_offset = u32::from_le_bytes([
                        orig_bytes[entry_offset], orig_bytes[entry_offset+1],
                        orig_bytes[entry_offset+2], orig_bytes[entry_offset+3]
                    ]) as usize;
                    let orig_size = u32::from_le_bytes([
                        orig_bytes[entry_offset+4], orig_bytes[entry_offset+5],
                        orig_bytes[entry_offset+6], orig_bytes[entry_offset+7]
                    ]) as usize;
                    
                    orig_bytes[orig_offset..orig_offset+orig_size].to_vec()
                }
            };
            (i, payload)
        })
        .collect();

    let mut payload_map: std::collections::HashMap<u32, Vec<u8>> = processed_payloads.into_iter().collect();

    for entry in entries {
        let i = entry.index;
        let meta_bytes = hex::decode(&entry.meta).unwrap();

        let payload = payload_map.remove(&i).unwrap();

        // Align pos to 16-byte boundary
        let align_pad = (16 - (pos % 16)) % 16;
        if align_pad > 0 {
            out_data.extend(std::iter::repeat(0).take(align_pad as usize));
            pos += align_pad;
        }

        let size = payload.len() as u32;
        out_data.extend_from_slice(&payload);

        let mut index_entry = Vec::with_capacity(16);
        index_entry.extend_from_slice(&pos.to_le_bytes());
        index_entry.extend_from_slice(&size.to_le_bytes());
        index_entry.extend_from_slice(&meta_bytes);
        new_index_entries.push(index_entry);

        pos += size;
    }

    out_data[0..4].copy_from_slice(&files_count.to_le_bytes());
    out_data[4..16].copy_from_slice(&header_extra);

    for (i, entry_bytes) in new_index_entries.iter().enumerate() {
        let offset = 16 + i * 16;
        out_data[offset..offset+16].copy_from_slice(entry_bytes);
    }

    fs::write(output_pkgdds, out_data).unwrap();
    println!("PKGDDS Repacking completed successfully.");
}

fn handle_extract_eg(eg_file: &str, output_dir: &str, clean: bool, use_hash: bool) {
    println!("Extracting EG Container: {} -> {}", eg_file, output_dir);
    if let Err(e) = fs::create_dir_all(output_dir) {
        eprintln!("Error creating output directory: {}", e);
        std::process::exit(1);
    }

    let bytes = match fs::read(eg_file) {
        Ok(b) => b,
        Err(e) => {
            eprintln!("Error reading file: {}", e);
            std::process::exit(1);
        }
    };

    match extract_eg_internal(&bytes, Path::new(output_dir), clean, use_hash) {
        Ok(meta) => {
            let meta_path = Path::new(output_dir).join("eg_meta.json");
            if let Ok(meta_file) = File::create(meta_path) {
                let _ = serde_json::to_writer_pretty(meta_file, &meta);
            }
            println!("EG Extraction completed successfully.");
        }
        Err(e) => {
            eprintln!("Error: {}", e);
            std::process::exit(1);
        }
    }
}

fn handle_repack_eg(eg_file: &str, modified_dir: &str, output_eg: &str, _clean: bool, use_hash: bool) {
    println!("Repacking EG Container: Template={}, Modified={} -> Output={}", eg_file, modified_dir, output_eg);
    
    let meta_path = Path::new(modified_dir).join("eg_meta.json");
    let eg_meta = if meta_path.exists() {
        let file = File::open(meta_path).unwrap();
        let meta: EgMeta = serde_json::from_reader(file).unwrap();
        meta
    } else {
        // Reconstruct from original
        let bytes = fs::read(eg_file).unwrap();
        let null1 = &bytes[4..12];
        let null2 = &bytes[16..20];
        let data_offset = u32::from_be_bytes([bytes[20], bytes[21], bytes[22], bytes[23]]);
        let files = u32::from_be_bytes([bytes[24], bytes[25], bytes[26], bytes[27]]);
        let index_table = &bytes[28..28 + (files * 4) as usize];
        
        EgMeta {
            base_name: "eg".to_string(),
            null1: hex::encode(null1),
            null2: hex::encode(null2),
            data_offset,
            files,
            index_table: hex::encode(index_table),
            dds_format: None,
            orig_dds_header: None,
            orig_gtf_header: None,
            png_hash: None,
            header_extra: None,
        }
    };

    let orig_bytes = fs::read(eg_file).ok();

    match repack_eg_internal(Path::new(modified_dir), &eg_meta, orig_bytes.as_deref(), use_hash) {
        Ok(bytes) => {
            fs::write(output_eg, bytes).unwrap();
            println!("EG Repacking completed successfully.");
        }
        Err(e) => {
            eprintln!("Error: {}", e);
            std::process::exit(1);
        }
    }
}

// ==============================================================================
// CLI Main
// ==============================================================================

fn main() {
    let cli = Cli::parse();

    let threads_opt = match &cli.command {
        Commands::RepackDar { threads, .. } => *threads,
        Commands::RepackDdspack { threads, .. } => *threads,
        Commands::RepackEg { threads, .. } => *threads,
        _ => None,
    };

    let default_threads = std::thread::available_parallelism()
        .map(|n| (n.get() / 2).max(1).min(8))
        .unwrap_or(4);
    let mut t = threads_opt.unwrap_or(default_threads);
    if t > 10 {
        t = 10;
    }
    rayon::ThreadPoolBuilder::new().num_threads(t).build_global().ok();

    match cli.command {
        Commands::ExtractDar { dar_file, output_dir, clean, only_image } => {
            handle_extract_dar(&dar_file, &output_dir, clean, only_image, cli.use_hash);
        }
        Commands::RepackDar { dar_file, modified_dir, output_dar, clean, .. } => {
            handle_repack_dar(&dar_file, &modified_dir, &output_dar, clean, cli.use_hash);
        }
        Commands::ExtractDdspack { pkgdds_file, output_dir, clean } => {
            handle_extract_ddspack(&pkgdds_file, &output_dir, clean, cli.use_hash);
        }
        Commands::RepackDdspack { pkgdds_file, modified_dir, output_pkgdds, clean, .. } => {
            handle_repack_ddspack(&pkgdds_file, &modified_dir, &output_pkgdds, clean, cli.use_hash);
        }
        Commands::ExtractEg { eg_file, output_dir, clean } => {
            handle_extract_eg(&eg_file, &output_dir, clean, cli.use_hash);
        }
        Commands::RepackEg { eg_file, modified_dir, output_eg, clean, .. } => {
            handle_repack_eg(&eg_file, &modified_dir, &output_eg, clean, cli.use_hash);
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_decompress_block() {
        let dar_path = "C:/Users/ASUS/.gemini/antigravity/scratch/test_cargo/dar_test/mini_data.dar";
        if !std::path::Path::new(dar_path).exists() {
            println!("mini_data.dar not found, skipping");
            return;
        }
        let mut f = File::open(dar_path).unwrap();
        f.seek(SeekFrom::Start(48)).unwrap();
        let mut entry = [0u8; 16];
        f.read_exact(&mut entry).unwrap();
        let _size = u32::from_le_bytes([entry[0], entry[1], entry[2], entry[3]]);
        let zsize = u32::from_le_bytes([entry[4], entry[5], entry[6], entry[7]]);
        let offset = u64::from_le_bytes([entry[8], entry[9], entry[10], entry[11], entry[12], entry[13], entry[14], entry[15]]);
        
        f.seek(SeekFrom::Start(offset)).unwrap();
        let mut comp = vec![0u8; zsize as usize];
        f.read_exact(&mut comp).unwrap();
        
        let pos = 4;
        let block_uncomp_size = u32::from_le_bytes([comp[pos], comp[pos+1], comp[pos+2], comp[pos+3]]);
        let block_comp_size = u32::from_le_bytes([comp[pos+4], comp[pos+5], comp[pos+6], comp[pos+7]]);
        let lzma_params = &comp[pos+8..pos+13];
        let payload_start = pos + 16;
        let payload_end = payload_start + block_comp_size as usize;
        let payload = &comp[payload_start..payload_end];
        
        let prop_byte = lzma_params[0];
        let mut header = Vec::new();
        header.push(prop_byte);
        header.extend_from_slice(&lzma_params[1..5]);
        header.extend_from_slice(&(block_uncomp_size as u64).to_le_bytes());
        header.extend_from_slice(payload);

        let mut reader = Cursor::new(header);
        let mut decomp_out = Vec::new();
        let res = lzma_rs::lzma_decompress(&mut reader, &mut decomp_out);
        println!("lzma-rs result: {:?}", res);
        if res.is_ok() {
            println!("lzma-rs decompressed size: {}", decomp_out.len());
        }
        
        let decomp = decompress_data(&comp);
        assert!(decomp.is_ok(), "Decompression failed: {:?}", decomp.err());
    }

    #[test]
    fn test_compress_original() {
        let dar_path = "D:/White Album 2 Shiawase no Mukougawa [BLJM60571]/PS3_GAME/USRDIR/data.dar";
        if !std::path::Path::new(dar_path).exists() {
            println!("data.dar not found, skipping");
            return;
        }
        let mut f = File::open(dar_path).unwrap();
        f.seek(SeekFrom::Start(16)).unwrap();
        let mut entry = [0u8; 16];
        f.read_exact(&mut entry).unwrap();
        let size = u32::from_le_bytes([entry[0], entry[1], entry[2], entry[3]]);
        let zsize = u32::from_le_bytes([entry[4], entry[5], entry[6], entry[7]]);
        let offset = u64::from_le_bytes([entry[8], entry[9], entry[10], entry[11], entry[12], entry[13], entry[14], entry[15]]);
        
        println!("Index 0: size={}, zsize={}, offset={}", size, zsize, offset);
        
        f.seek(SeekFrom::Start(offset)).unwrap();
        let mut original_comp = vec![0u8; zsize as usize];
        f.read_exact(&mut original_comp).unwrap();
        
        let decomp = decompress_data(&original_comp).unwrap();
        assert!(decomp.len() >= size as usize, "Decompressed length {} is smaller than declared size {}", decomp.len(), size);
        
        let recompressed = compress_data(&decomp).unwrap();
        println!("Original compressed size (with prefix u32): {}", original_comp.len());
        println!("Recompressed size (with prefix u32): {}", recompressed.len());
        
        if original_comp.len() != recompressed.len() {
            println!("Sizes differ! original={}, recompressed={}", original_comp.len(), recompressed.len());
        } else {
            println!("Sizes match!");
        }
    }
}
