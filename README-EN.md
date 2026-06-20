# WA2 PS3 KIT - Standalone Tools (Modernized Python 3)

The toolset has been completely redesigned and modernized to **Python 3.12**, completely dropping the dependency on Python 2.7 and the obsolete `pylzma` library. Instead, the kit utilizes Python 3's standard `lzma` library, perfectly backward-compatible with Aquaplus's block compression format.

## Standalone Tools

All scripts below utilize the standard `argparse` module. You can run `python <tool_name.py> -h` to view help and parameters.

### 1. `wa2_archive.py` (Archive Extractor & Repacker)
This tool is directly reverse-engineered from QuickBMS `.bms` scripts, allowing you to extract and UPDATE internal archive structures using pure Python, removing all limitations of QuickBMS:
- **Extract DAR (`data.dar`)**: 
  ```cmd
  python wa2_archive.py extract-dar data.dar output_dir
  ```
  *(Upon extraction, the tool auto-detects formats via Magic Headers:
  - `.at3`: Audio file.
  - `.gtf`: Texture image file.
  - `.pkgdds`: Texture bundle file (can be further unpacked via `extract-ddspack`).
  - `.eg`: Wrapper container file (contains `.gtf` images inside). Extraction / repacking supported via `extract-eg` and `repack-eg`.
  - `.inas`: Rare file format, direct editing not yet supported.
  - `.unknown`: Unrecognized file formats.)*
- **Repack DAR (Reimport/Repack)** (Superior feature: allows files larger than the original):
  ```cmd
  python wa2_archive.py repack-dar data.dar path\to\modified_files data_new.dar
  ```
- **Extract DDSPACK (`.pkgdds`)**:
  ```cmd
  python wa2_archive.py extract-ddspack image.pkgdds output_dir
  ```
- **Repack DDSPACK (`.pkgdds`)**:
  ```cmd
  python wa2_archive.py repack-ddspack image.pkgdds path\to\modified_files image_new.pkgdds
  ```
- **Extract EG Container (`.eg`)**:
  ```cmd
  python wa2_archive.py extract-eg image.eg output_dir
  ```
- **Repack EG Container (`.eg`)**:
  ```cmd
  python wa2_archive.py repack-eg image.eg path\to\modified_files image_new.eg
  ```

### 2. `wa2_archive.exe` (Rust Port - Optimization & Multi-threading)

The Rust port of `wa2_archive.py` compiles into the `wa2_archive.exe` executable located in the root directory. This port offers superior processing speed and introduces several automation features for image modding/localization:

#### 🌟 Technical Upgrades (vs. Old Python Scripts)
- **Native GTF & NVTT 2024 Integration**: Completely eliminates dependencies on older tools like `dds2gtf.exe`, `gtf2dds.exe`, and `texconv.exe`. Instead, the tool uses the NVIDIA Texture Tools 2024.1.1 suite combined with a GTF parser written entirely in Rust (based on the `gtfdds-rs` platform), providing deep optimizations in performance and DXT compression quality.
- **Perfected Alpha Channel (Transparency) Recreation**: General conversion tools often lose the PS3's specific `TextureRemap` byte, causing display glitches like black borders around transparent pixels. The **Original Header Preservation** feature automatically extracts and correctly applies the exact native formatting structure (`Version` and `TextureRemap` `ORDER_ARGB`), ensuring all visual effects and UI render 100% perfectly.
- **Custom Pixel Packer for Uncompressed Images**: Automatically loads PNG images and directly "bit-shifts" the RGBA channels into the exact mask position required by the game without relying on intermediary tools.
- **Optimized DAR Preservation with `--only-image`**: Extracting images only will no longer drop hidden files, but instead memorizes the entire 2000+ file structure into `meta.json`. Upon Repack, the **Fallback** feature automatically copies the original non-image files (audio, scripts) directly from the source DAR to the new DAR, keeping the game running smoothly while maximizing disk space savings.

#### 🔧 Key Features & Flags

**1. Automated Extract (`--clean`)**
Automatically extracts sub-packages (`.pkgdds`, `.eg`) and decodes GTF images directly into standard `.png` format (via `nvdecompress.exe`), while simultaneously generating `meta.json` files to store the original structural properties.
```cmd
wa2_archive.exe extract-dar data.dar output_clean_dir --clean
```

**2. Filter by Format (`--only-image`)**
Only extracts image-related files to the disk, ignoring audio, scripts, etc., to save time and storage. Perfectly compatible with the Repack command via the smart Fallback mechanism.
```cmd
wa2_archive.exe extract-dar data.dar output_images_dir --clean --only-image
```

**3. Comprehensive Automated Repack**
When running the repack command (`repack-dar`), the tool automatically reads `meta.json` to determine the previous extraction structure (whether `--clean` was used or not). If it detects modified `.png` files or image directories, the tool automatically triggers the reverse-compilation pipeline: compresses DDS (via `nvcompress.exe`), crafts a standard PS3 GTF Header via native Rust library, and repacks sub-containers (PKGDDS/EG) using the game's specialized LZMA algorithm. If a file is unmodified, it safely reuses the original raw file.
```cmd
wa2_archive.exe repack-dar data.dar output_clean_dir data_new.dar
```

**4. Multi-threading (`-j` / `--threads`)**
Supports maximum acceleration for the repacking process (GTF conversion and LZMA compression) by splitting the workload across multiple CPU threads simultaneously.
```cmd
wa2_archive.exe repack-dar data.dar output_clean_dir data_new.dar -j 8
```

### 3. `wa2_eboot.py` (EBOOT.ELF Manipulation Kit)
Handles compressed binary files (`.bnr` extension), usually system scripts (`sys_msg.bnr`) or UI elements. This specialized tool is used for EBOOT manipulation:

**Extract EBOOT:**
```bash
python wa2_eboot.py extract "EBOOT.ELF" "output_dir"
```
By default, the tool extracts all files in their raw binary format (the `.bnr` files that control the system).

**Extract EBOOT (Translation Scripts Only):**
```bash
python wa2_eboot.py extract "EBOOT.ELF" "output_dir" --clean
```
When using the `--clean` flag, the tool automatically decompiles all `.bnr` files and **extracts them into `.txt` files** (dialogues) for easier translation. Simultaneously, it generates an `eboot_meta.json` file to mark the "translation directory in progress" state.

**Inject into EBOOT:**
```bash
python wa2_eboot.py inject "EBOOT.ELF" "input_dir"
```
Smart Inject Mechanism: The tool scans the directory and silently ELZMA-compresses valid files into their correct entries within the EBOOT. **Crucially**, the tool reads the `eboot_meta.json` generated during extraction. If it recognizes a `clean` directory (containing `.txt` scripts for translation), it will automatically recompile them into `.bnr` files; otherwise, compilation is skipped.

**Font / Warning Patching:**
```bash
python wa2_eboot.py patch EBOOT.ELF <charset_num> <font2_bin> <font2_num> <warning_png>
```

### 4. `wa2_font.py` (Font Graphics Processor)
This tool is exclusively dedicated to processing the game's font graphics files:
- **Build mini font patch table:** `python wa2_font.py build-mini input.txt input.tbl output_name` (Generates `mini_up.bin`).
- **Process dds3 images:** Use the `extract-dds` and `make-dds` commands.

### 5. `wa2_savedata.py` (Save File Fixer)
This is a standalone tool spun off from the old `import_file.py`, specialized in cleaning up and resetting corrupted memory (backlog/history) in savegame files.
- **Fix save file:** `python wa2_savedata.py BLJM60571WA2`

---
## Utilities

### 6. `wa2_sce.py` (SCE/EBOOT Decryptor / Encryptor)
A wrapper communicating with `scetool` (located in the `bin` directory) to process EBOOT and SCE formats.
- **Decrypt:** `python wa2_sce.py decrypt EBOOT.BIN EBOOT.ELF`
- **Encrypt:** `python wa2_sce.py encrypt EBOOT.ELF EBOOT.BIN`

### 7. `wa2_image.py` (GTF / DDS Image Processor)
A wrapper communicating with `nvcompress`, `dds2gtf`, and `gtf2dds` to convert PS3 Texture image formats.
- **PNG to DDS:** `python wa2_image.py png2dds image.png [--format -rgb32]`
- **DDS to GTF:** `python wa2_image.py dds2gtf image.dds`
- **GTF to DDS:** `python wa2_image.py gtf2dds image.gtf`

### `utils/` Directory
This directory contains internal files not directly used for game modification.
Example: **`utils/wa2_elzma.py`**
Since `.elzma` is not an directly editable format, this script serves as a core utility supporting Aquaplus's proprietary LZMA compression/decompression standard:
- **Compress file/directory**: `python utils\wa2_elzma.py compress input_file_or_dir`
- **Decompress file/directory**: `python utils\wa2_elzma.py decompress input_file_or_dir`

---
