use std::fs;
use std::io::Write;

const UNCOMP_BLOCK_SIZE: usize = 0x10000;

fn compress_block_raw(data: &[u8]) -> Result<Vec<u8>, Box<dyn std::error::Error>> {
    let mut props = lzma_sdk_rs::LzmaProps::for_level(5, 1 << 14);
    props.dict_size = 1 << 14;
    props.lc = 3;
    props.lp = 0;
    props.pb = 2;
    props.fb = 273;
    Ok(lzma_sdk_rs::encode(data, &props))
}

fn compress_data(buf: &[u8]) -> Result<Vec<u8>, Box<dyn std::error::Error>> {
    let size = buf.len();
    let mut remain = size;
    let mut pos = 0;
    let mut data = Vec::new();

    while remain > 0 {
        let block_size = if remain > UNCOMP_BLOCK_SIZE { UNCOMP_BLOCK_SIZE } else { remain };
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

fn main() {
    let raw_data = fs::read(r"C:\Users\ASUS\.gemini\antigravity\brain\873227e2-1c44-4ce9-b00c-197852e3e2af\scratch\test217\00069_gen.gtf").unwrap();
    let comp = compress_data(&raw_data).unwrap();
    let comp_payload = &comp[4..];
    println!("Rust zsize: {}", comp_payload.len());
    fs::write(r"C:\Users\ASUS\.gemini\antigravity\brain\873227e2-1c44-4ce9-b00c-197852e3e2af\scratch\test217\00069_rs.elzma", comp_payload).unwrap();
}