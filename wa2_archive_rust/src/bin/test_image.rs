use image::io::Reader as ImageReader;
use std::collections::HashSet;

fn main() {
    let img = ImageReader::open(r"C:\Users\ASUS\.gemini\antigravity\brain\873227e2-1c44-4ce9-b00c-197852e3e2af\scratch\00039_extracted\000.png").unwrap().decode().unwrap();
    let rgba = img.to_rgba8();
    let mut transparent_rgb = HashSet::new();
    for pixel in rgba.pixels() {
        if pixel[3] == 0 {
            transparent_rgb.insert((pixel[0], pixel[1], pixel[2]));
        }
    }
    println!("Distinct RGB for alpha=0: {}", transparent_rgb.len());
}