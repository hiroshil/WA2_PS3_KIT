# WA2 PS3 KIT - Standalone Tools (Modernized Python 3)

The toolset has been completely redesigned and modernized to **Python 3.12**, dropping the dependency on Python 2.7. The kit utilizes the `pylzma` library (compiled for Python 3) to handle Aquaplus's block compression format.

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
Automatically extracts sub-packages (`.pkgdds`, `.eg`) and decodes GTF images directly into standard `.png` format (via `nvdecompress.exe`), while simultaneously generating `meta.json` files to store the original structural properties. You can add the `--use-hash` flag to record the original file hashes.
```cmd
wa2_archive.exe extract-dar data.dar output_clean_dir --clean [--use-hash]
```

**2. Filter by Format (`--only-image`)**
Only extracts image-related files to the disk, ignoring audio, scripts, etc., to save time and storage. Perfectly compatible with the Repack command via the smart Fallback mechanism.
```cmd
wa2_archive.exe extract-dar data.dar output_images_dir --clean --only-image
```

**3. Comprehensive Automated Repack**
When running the repack command (`repack-dar`), the tool automatically reads `meta.json` to determine the previous extraction structure (whether `--clean` was used or not). If it detects modified `.png` files or image directories, the tool automatically triggers the reverse-compilation pipeline: compresses DDS (via `nvcompress.exe`), crafts a standard PS3 GTF Header via native Rust library, and repacks sub-containers (PKGDDS/EG) using the game's specialized LZMA algorithm. If a file is unmodified, it safely reuses the original raw file. Furthermore, if the `--use-hash` flag is used (combined during extraction), the tool checks hashes to entirely skip the reverse-compilation of unmodified files, heavily accelerating the repack process.
```cmd
wa2_archive.exe repack-dar data.dar output_clean_dir data_new.dar [--use-hash]
```

**4. Multi-threading (`-j` / `--threads`)**
Supports maximum acceleration for the repacking process (GTF conversion and LZMA compression) by splitting the workload across multiple CPU threads simultaneously.
```cmd
wa2_archive.exe repack-dar data.dar output_clean_dir data_new.dar -j 8
```

### 3. `wa2_eboot.py` (EBOOT.ELF Patcher)
Contains compressed binaries (`.bnr`) and text script files (`.txt`), usually responsible for system dialogues (`sys_msg.txt`) or UI texts. All HEX offset logic from the original Python 2 source code has been **100% accurately recreated**. Furthermore, the old `import` and `rebuild` commands have been **merged into a single smart `inject` command** with an automatic ELF-shifting Fallback mechanism, completely preventing EBOOT corruption even when files are missing.

> [!IMPORTANT]
> **Mandatory Workflow:** You MUST run the `patch` command on the original EBOOT file to generate a new EBOOT (with Font patched and Delimiter changed) BEFORE proceeding with `extract` and `inject`. If you extract from the original EBOOT and then inject into the patched EBOOT, the `.txt` script files will have a delimiter mismatch (between the original comma `,` and the patched `$`), leading to a critical crash when loading scripts into the game.

**1. Font / Kerning / Delimiter Patching (All-in-one Patch):**
```bash
python wa2_eboot.py patch EBOOT.ELF OUTPUT.ELF [--charset <num>] --kerning {apply|remove|check}
```
This command now acts as an all-in-one patcher:
- **Automated Font Sizing and Injection:** Patches the size and structure of the new Font set via the `--charset` flag (Defaults to `2907` if omitted). The tool now automatically appends the binary of Font 1 directly into the EBOOT (at offset `0x120e00`) and hardcodes the character mapping table (tbl) directly in the source code.
- **Integrated Kerning Patch (Half-width display):** Automatically forces Vietnamese text to display as Half-width via the `--kerning` flag.
    - `--kerning apply`: Finds a safe Code Cave (`0x135120`), removes original Width Array limits, and enforces Half-width rendering for both Main Dialog and Backlog (Fixes white box errors and oversized spacing).
    - `--kerning remove`: Cleans up machine code, restoring EBOOT to factory original.
    - `--kerning check`: Quickly checks if the EBOOT has been patched.
- **Script Delimiter Replacement:** Changes from `,` (0x2C) to `$` (0x24) for Vietnamese/English compatibility.
    - During `extract`: The tool detects if EBOOT uses `$`, then safely clears out old `,` signs in `.txt` files to `$`.
    - During `inject`: The tool runs security checks. If an incorrect script containing `,` is used, it throws a fatal error preventing a crash. If the script is valid, it converts `\,` characters (typed by the user) into true commas `,` for in-game display.

**2. Extract EBOOT (Clean Translation Mode `--clean`):**
```bash
python wa2_eboot.py extract "OUTPUT.ELF" "output_dir" --clean [--use-hash]
```
The `--clean` flag helps the tool extract strictly `.txt` scripts (available in EBOOT) and **automatically converts the encoding to UTF-16** for translators' convenience. Unnecessary `.bnr` binary files are skipped, and the tool generates an `eboot_meta.json`.

**3. Extract EBOOT (Raw Binary):**
```bash
python wa2_eboot.py extract "OUTPUT.ELF" "output_dir" [--use-hash]
```
By default, the tool extracts all files contained within the EBOOT (`.bnr`, `.txt`, etc.) in their raw uncompressed form, allowing for direct hex editing. If `--use-hash` is used, the tool records the original hash to assist the inject process in skipping unmodified files.

**4. Comprehensive Automated Inject:**
```bash
python wa2_eboot.py inject "OUTPUT.ELF" "input_dir" "OUTPUT_NEW.ELF" [--use-hash]
```
The automated Inject mechanism operates based on `eboot_meta.json`. If it detects `clean` mode, it automatically processes your modified `.txt` scripts and injects them into the EBOOT. Crucially, for any files missing from the disk (skipped during `--clean` extraction), the tool automatically triggers the **Fallback** feature (safely copying the original binary payload from the source EBOOT to shift the data blocks), completely eliminating the "Rebuild failed" crashes of previous versions. If `--use-hash` is used, the tool checks file hashes and skips unchanged files, drastically speeding up the injection process by reusing existing compressed payloads.

### 4. `wa2_savedata.py` (Save File Fixer)
This is a standalone tool spun off from the old `import_file.py`, specialized in cleaning up and resetting corrupted memory (backlog/history) in savegame files.
- **Fix save file:** `python wa2_savedata.py BLJM60571WA2`

---
## Utilities

### 5. `wa2_sce.py` (SCE/EBOOT Decryptor / Encryptor)
A wrapper communicating with `scetool` (located in the `bin` directory) to process EBOOT and SCE formats.
- **Decrypt:** `python wa2_sce.py decrypt EBOOT.BIN EBOOT.ELF`
- **Encrypt:** `python wa2_sce.py encrypt EBOOT.ELF EBOOT.BIN`

### 6. `wa2_image.py` (GTF / DDS Image Processor)
A wrapper communicating with `nvcompress`, `dds2gtf`, and `gtf2dds` to convert PS3 Texture image formats.
- **PNG to DDS:** `python wa2_image.py png2dds image.png [--format -rgb32]`
- **DDS to GTF:** `python wa2_image.py dds2gtf image.dds`
- **GTF to DDS:** `python wa2_image.py gtf2dds image.gtf`

### 7. `wa2_text.py` (Text Dumper / Builder)
A utility to dump text files (typically comma-separated strings) into a human-readable translation format and build them back.
- **Dump:** `python wa2_text.py dump input.txt output_dir`
- **Build:** `python wa2_text.py build translated.txt original.txt output.txt`

### `utils/` Directory
This directory contains internal files not directly used for game modification.
Example: **`utils/wa2_elzma.py`**
Since `.elzma` is not an directly editable format, this script serves as a core utility supporting Aquaplus's proprietary LZMA compression/decompression standard:
- **Compress file/directory**: `python utils\wa2_elzma.py compress input_file_or_dir`
- **Decompress file/directory**: `python utils\wa2_elzma.py decompress input_file_or_dir`

---
