use lzma_sdk_rs::LzmaProps;

fn main() {
    let data = b"Hello World";
    let mut props = LzmaProps::for_level(5, 1 << 14);
    props.dict_size = 1 << 14;
    props.lc = 3;
    props.lp = 0;
    props.pb = 2;
    props.fb = 273;

    let dest = lzma_sdk_rs::encode(data, &props);
    println!("Dest len: {}", dest.len());
    println!("Dest bytes: {:x?}", &dest[0..20.min(dest.len())]);
}
