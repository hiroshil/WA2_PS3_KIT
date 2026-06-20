use std::path::Path;
use std::fs;

fn main() {
    let png_path = Path::new(r"D:\White Album 2 Shiawase no Mukougawa [BLJM60571]\PS3_GAME\USRDIR\WA2_PS3_KIT\output_clean_dir\00039_clean\000.png");
    let dds_format = "-rgb32";
    
    let tmp_dds_path = png_path.with_extension("dds.tmp");
    let tmp_gtf_path = png_path.with_extension("gtf.tmp");

    let nvcompress_tool = r"D:\White Album 2 Shiawase no Mukougawa [BLJM60571]\PS3_GAME\USRDIR\WA2_PS3_KIT\PS3_Projects\3rd\nvtt\nvcompress.exe";
    let dds2gtf_tool = r"D:\White Album 2 Shiawase no Mukougawa [BLJM60571]\PS3_GAME\USRDIR\WA2_PS3_KIT\PS3_Projects\tools\dds2gtf.exe";

    std::process::Command::new(nvcompress_tool)
        .args(&["-nomips", "-nocuda", dds_format, png_path.to_str().unwrap(), tmp_dds_path.to_str().unwrap()])
        .output().unwrap();

    std::process::Command::new(dds2gtf_tool)
        .args(&[tmp_dds_path.to_str().unwrap(), "-o", tmp_gtf_path.to_str().unwrap()])
        .output().unwrap();

    let gtf_data = fs::read(&tmp_gtf_path).unwrap();
    fs::write(r"D:\White Album 2 Shiawase no Mukougawa [BLJM60571]\PS3_GAME\USRDIR\WA2_PS3_KIT\output_clean_dir\00039_clean\000_rust.gtf", gtf_data).unwrap();
    
    let _ = fs::remove_file(&tmp_dds_path);
    let _ = fs::remove_file(&tmp_gtf_path);
    println!("Done");
}
