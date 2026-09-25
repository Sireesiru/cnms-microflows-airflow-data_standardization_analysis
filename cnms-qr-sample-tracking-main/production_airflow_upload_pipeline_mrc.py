#!/home/cloud/microflow_server/bin/python
import os
import sys
import json
import pathlib
import qrcode
import glob
import time
import h5py
import numpy as np
import warnings
import mrcfile
import sidpy

ROOT = pathlib.Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from datafed.CommandLib import API
from pySEA.sea_sand.seaid import SEAID

# Suppress noisy structural/formatting warnings
warnings.filterwarnings("ignore", category=UserWarning, module=r"pyNSID\.io\.hdf_io")
warnings.filterwarnings("ignore", category=FutureWarning, module=r"pyNSID\.io\.(hdf_io|hdf_utils)")

try:
    import pyNSID as nsid
    import SciFiReaders as sr
    import SciFiReaders.readers.microscopy.em.tem.mrc_reader as mrc_reader
except ImportError:
    print("[-] Dependencies Missing: Please ensure 'SciFiReaders', 'pyNSID', and 'mrcfile' are installed.")
    sys.exit(1)

# Persistent global cache to protect MRC binary stats from framework cleanup passes
MRC_STATIC_CACHE = {}

# ===================================================================
# Monkey Patch: Hardened MRCReader for Massive Writable 2D/3D EM Movies
# ===================================================================
def safe_read(self):
    try:
        #with mrcfile.open(self.file_path, mmap_mode="r+", permissive=True) as m:
        with mrcfile.mmap(self.file_path, mode="r", permissive=True) as m:
            if m.data is None:
                raise ValueError("MRC data block returned None.")
            
            data = m.data.copy() 
            if data.ndim == 2:
                data = np.expand_dims(data, 0)
                
            print(f"[safe_read] Memory-mapped and cloned {self.file_path}. Shape: {data.shape}")

            # Capture binary parameters immediately before SciFiReaders strips them
            MRC_STATIC_CACHE[self.file_path] = {
                "nx": int(m.header.nx),
                "ny": int(m.header.ny),
                "nz": int(m.header.nz),
                "mode": int(m.header.mode),
                "dmin": float(m.header.dmin),
                "dmax": float(m.header.dmax),
                "dmean": float(m.header.dmean)
            }

            dataset = sidpy.Dataset.from_array(data, name="Channel_000")
            dataset.units = "intensity"
            dataset.data_type = "image"
            dataset.title = os.path.basename(self.file_path)
            
            dataset.metadata = MRC_STATIC_CACHE[self.file_path].copy()
            return {"Channel_000": dataset}
    except Exception as e:
        print(f"[safe_read] Fallback error reading {self.file_path}: {e}")
        dummy = sidpy.Dataset.from_array(np.zeros((1, 1, 1), dtype=np.float32), name="Channel_000")
        dummy.units = "a.u."
        return {"Channel_000": dummy}

mrc_reader.MRCReader.read = safe_read

# ===================================================================
# Helper Utilities
# ===================================================================
RAW_READER_CLASSES = {
    '.ibw': sr.IgorIBWReader,
    '.mrc': sr.MRCReader,
    '.gwy': sr.GwyddionReader,
    '.czi': sr.CZIReader,
}

def _to_str_list(x):
    if x is None: return None
    if isinstance(x, bytes): return [x.decode("utf-8", errors="ignore")]
    if isinstance(x, str): return [x]
    if isinstance(x, np.ndarray):
        return [v.decode("utf-8", errors="ignore") if isinstance(v, bytes) else str(v) for v in x.reshape(-1).tolist()]
    if isinstance(x, (list, tuple)): return [str(v) for v in x]
    return [str(x)]

def _sanitize_group_for_pynxtools(group, str_dt):
    def fix_attrs(obj):
        if "DIMENSION_LIST" in obj.attrs:
            try: del obj.attrs["DIMENSION_LIST"]
            except Exception: pass
        for k in ("axes", "DIMENSION_LABELS"):
            if k in obj.attrs:
                v = obj.attrs.get(k)
                if isinstance(v, np.ndarray) and v.dtype.kind == "O":
                    as_list = _to_str_list(v)
                    if as_list is not None:
                        obj.attrs.modify(k, np.array(as_list, dtype=str_dt))
    fix_attrs(group)
    group.visititems(lambda _name, obj: fix_attrs(obj))

def _clean_dict_for_json(d):
    clean = {}
    if not isinstance(d, dict):
        return str(d)
        
    for k, v in d.items():
        clean_k = str(k).replace(".", "_").replace("$", "_")
        
        if isinstance(v, (float, np.floating)):
            if not np.isfinite(v):
                if np.isnan(v):
                    clean[clean_k] = "-NaN" if v < 0 or np.signbit(v) else "NaN"
                else:
                    clean[clean_k] = "-Infinity" if v < 0 else "Infinity"
                continue

        if isinstance(v, dict):
            clean[clean_k] = _clean_dict_for_json(v)
        elif isinstance(v, (list, tuple)):
            clean[clean_k] = [
                ("-NaN" if x < 0 or np.signbit(x) else "NaN") if isinstance(x, (float, np.floating)) and np.isnan(x)
                else ("-Infinity" if x < 0 else "Infinity") if isinstance(x, (float, np.floating)) and np.isinf(x)
                else x for x in v
            ]
        elif isinstance(v, bytes):
            clean[clean_k] = v.decode("utf-8", errors="ignore")
        elif isinstance(v, np.ndarray):
            if np.issubdtype(v.dtype, np.number):
                clean[clean_k] = [
                    str(x) if not np.isfinite(x) else x for x in v.flatten().tolist()
                ]
            else:
                clean[clean_k] = v.tolist()
        elif isinstance(v, np.integer):
            clean[clean_k] = v.item()
        elif isinstance(v, (int, bool, type(None))):
            clean[clean_k] = v
        else:
            clean[clean_k] = str(v)
            
    return clean

# ===================================================================
# Unified Conversion Engine
# ===================================================================
def convert_to_h5(file_path, metadata=None):
    ext = os.path.splitext(file_path)[1].lower()
    if ext not in RAW_READER_CLASSES:
        return None, {}

    print(f"[convert] Reading {file_path} with {RAW_READER_CLASSES[ext].__name__}")

    try:
        reader = RAW_READER_CLASSES[ext](file_path)
        data_content = reader.read()
        
        if isinstance(data_content, list):
            if len(data_content) > 0:
                data = {f"Channel_{i:03d}": d for i, d in enumerate(data_content)}
            else:
                fallback_ds = sidpy.Dataset.from_array(np.zeros((1024, 1024), dtype=np.float32), name="Channel_000")
                data = {"Channel_000": fallback_ds}
        elif isinstance(data_content, dict):
            data = data_content
        else:
            data = {"Channel_000": data_content}

    except Exception as e:
        print(f"[-] Repo reader failed parsing raw dataset {file_path}: {e}")
        return None, {}

    # Deep Instrument Metadata Harvesting Matrix
    extracted_header_meta = {}
    try:
        # 1. Bubble up generic top-level metadata dictionaries across all channels
        for ch_name, dataset in data.items():
            if hasattr(dataset, 'metadata') and isinstance(dataset.metadata, dict):
                extracted_header_meta.update(dataset.metadata)
            if hasattr(dataset, 'original_metadata') and isinstance(dataset.original_metadata, dict):
                extracted_header_meta.update(dataset.original_metadata)
                
        # --- UNTOUCHED SOLID IBW PIPELINE ---
        if ext == '.ibw' and hasattr(reader, 'wave_header'):
            extracted_header_meta['IgorWaveHeader'] = reader.wave_header
            
        # --- ROBUST COMMON-CORE CZI PIPELINE WITH DIRECT XML MAPPING ---
        elif ext == '.czi':
            extracted_header_meta["summary_instrument"] = "Zeiss Microscopy System"
            extracted_header_meta["summary_objective"] = "Unknown Objective"
            extracted_header_meta["summary_numerical_aperture"] = "Unknown NA"
            extracted_header_meta["summary_pixel_size_x_um"] = "Unknown"
            extracted_header_meta["summary_pixel_size_y_um"] = "Unknown"

            for ch_name, dataset in data.items():
                if hasattr(dataset, 'metadata') and isinstance(dataset.metadata, dict):
                    for k, v in dataset.metadata.items():
                        if not isinstance(v, dict):
                            extracted_header_meta[f"summary_{k}"] = v
            try:
                import czifile
                import xml.etree.ElementTree as ET
                with czifile.CziFile(file_path) as czi:
                    raw_xml_string = czi.metadata()
                    if raw_xml_string:
                        extracted_header_meta['CZI_Raw_XML_Attachment'] = str(raw_xml_string)
                        root = ET.fromstring(raw_xml_string)
                        
                        obj_node = root.find(".//Objective")
                        if obj_node is not None and obj_node.text:
                            extracted_header_meta["summary_objective"] = obj_node.text.strip()
                            
                        na_node = root.find(".//LensNA")
                        if na_node is not None and na_node.text:
                            extracted_header_meta["summary_numerical_aperture"] = na_node.text.strip()

                        tube_node = root.find(".//TubeLensPosition")
                        scope_node = root.find(".//MicroscopeType")
                        if tube_node is not None and tube_node.text:
                            extracted_header_meta["summary_instrument"] = f"Zeiss Confocal ({tube_node.text.strip()})"
                        elif scope_node is not None and scope_node.text:
                            extracted_header_meta["summary_instrument"] = f"Zeiss {scope_node.text.strip()}"

                        val_x = root.find(".//Scaling/Distance[@Id='X']/Value")
                        val_y = root.find(".//Scaling/Distance[@Id='Y']/Value")
                        if val_x is not None and val_x.text:
                            extracted_header_meta["summary_pixel_size_x_um"] = str(float(val_x.text) * 1e6)
                        if val_y is not None and val_y.text:
                            extracted_header_meta["summary_pixel_size_y_um"] = str(float(val_y.text) * 1e6)
            except Exception as czi_err:
                print(f"    [metadata harvest][warn] Direct common-core parsing skipped: {czi_err}")
                
        # --- CRYO-EM MRC PIPELINE WITH HARDENED CACHE RETRIEVAL ---
        elif ext == '.mrc':
            extracted_header_meta["summary_instrument"] = "Cryo-Electron Microscope"
            extracted_header_meta["summary_data_mode"] = "Unknown"
            extracted_header_meta["summary_volume_dimensions"] = "Unknown"
            extracted_header_meta["summary_intensity_mean"] = "Unknown"

            # Pull straight from the un-wiped persistent cache map using the absolute file path
            if file_path in MRC_STATIC_CACHE:
                m_meta = MRC_STATIC_CACHE[file_path]
                
                extracted_header_meta["summary_data_mode"] = f"Mode {m_meta.get('mode', 'Unknown')}"
                extracted_header_meta["summary_volume_dimensions"] = f"{m_meta.get('nx', 0)} x {m_meta.get('ny', 0)} x {m_meta.get('nz', 0)}"
                extracted_header_meta["summary_intensity_mean"] = str(m_meta.get('dmean', 'Unknown'))
                
                extracted_header_meta['MRC_Header_Summary'] = {
                    "nx": int(m_meta.get('nx', 0)),
                    "ny": int(m_meta.get('ny', 0)),
                    "nz": int(m_meta.get('nz', 0)),
                    "mode": int(m_meta.get('mode', 0)),
                    "dmin": float(m_meta.get('dmin', 0.0)),
                    "dmax": float(m_meta.get('dmax', 0.0)),
                    "dmean": float(m_meta.get('dmean', 0.0))
                }
    except Exception as meta_err:
        print(f"[metadata harvest][warn] Deep extraction skipped: {meta_err}")

    h5_name = file_path.rsplit('.', 1)[0] + '.h5.nxs'

    try:
        with h5py.File(h5_name, 'w') as h5_f:
            str_dt = h5py.string_dtype(encoding='utf-8')

            entry = h5_f.create_group('entry')
            entry.attrs['NX_class'] = 'NXentry'

            def_dset = entry.create_dataset('definition', data="NXem", dtype=str_dt)
            def_dset.attrs["url"] = "https://github.com/FAIRmat-NFDI/nexus_definitions"
            def_dset.attrs["version"] = "v2024.02"

            h5_group = entry.create_group('Measurement_Nexus')
            h5_group.attrs['NX_class'] = 'NXsubentry'

            if metadata:
                for key, value in metadata.items():
                    h5_group.attrs[key] = str(value)

            clean_headers = _clean_dict_for_json(extracted_header_meta)
            for key, value in clean_headers.items():
                if isinstance(value, (dict, list)):
                    h5_group.attrs[f"instrument_{key}"] = json.dumps(value)
                else:
                    h5_group.attrs[f"instrument_{key}"] = str(value)

            for key in list(data.keys()):
                h5_g = h5_group.create_group(key)
                h5_g.attrs["NX_class"] = "NXdata"
                
                
                current_dataset = data[key]                
                if isinstance(current_dataset, sidpy.Dataset):
                    print("***** USING PYNSID *****")              
                    if not hasattr(current_dataset, 'title') or not current_dataset.title:
                        current_dataset.title = str(key)
                    try:
                        nsid.hdf_io.write_nsid_dataset(current_dataset, h5_g)
                        _sanitize_group_for_pynxtools(h5_g, str_dt)
                        print("[DEBUG] pyNSID write succeeded")
                    except Exception as write_err:
                        print(f"[!] pyNSID wrapper alert on {key}: {write_err}")
                        print("[DEBUG] Falling back to standard HDF5 dataset creation")
                        h5_g.create_dataset('data', data=np.array(current_dataset))
                else:
                    print("***** FALLING BACK ON H5PY *****")
                    h5_g.create_dataset('data', data=current_dataset)
            _sanitize_group_for_pynxtools(h5_group, str_dt)
            
            #    current_dataset = data[key]
            #    print(type(current_dataset),hasattr(current_dataset, 'values'))
            #    if hasattr(current_dataset, 'values'):
            #        if not hasattr(current_dataset, 'title') or not current_dataset.title:
            #            current_dataset.title = str(key)
            #        try:
            #            nsid.hdf_io.write_nsid_dataset(current_dataset, h5_g)
            #            _sanitize_group_for_pynxtools(h5_g, str_dt)
            #            
            #        except Exception as write_err:
            #            print(f"[!] pyNSID wrapper alert on {key}: {write_err}. Falling back to standard dataset creation.")
            #            h5_g.create_dataset('data', data=current_dataset.values)
            #    else:
            #        h5_g.create_dataset('data', data=current_dataset)
            #        
            #_sanitize_group_for_pynxtools(h5_group, str_dt)

        print(f"---Converted {ext[1:].upper()} file to h5 successfully---")
        return h5_name, extracted_header_meta
    except Exception as e:
        print(f"[-] Failed to execute repo H5 compilation matrix: {e}")
        return None, {}
# ===================================================================
# Execution Pipeline Loop
# ===================================================================
def execute_automated_pipeline():
    config_path = "/home/cloud/cnms-qr-sample-tracking-main/config.json"
    if not os.path.exists(config_path):
        print(f"[-] Configuration missing at {config_path}")
        sys.exit(1)

    with open(config_path, "r") as f:
        config_data = json.load(f)

    repo_id = config_data["datafed"].get("repo_id", "").strip()
    context = config_data["datafed"].get("context", "").strip()
    user_meta = config_data.get("user", {})
    src_collection = config_data["globus"].get("src_collection", "").strip()
    seaid_role = config_data.get("provenance", {}).get("seaid_role", "E0").strip()

    if len(sys.argv) < 2:
        print("[-] Error: Missing target directory path argument.")
        sys.exit(1)

    target_folder = os.path.abspath(sys.argv[1])

    raw_source_files = []
    for ext in RAW_READER_CLASSES.keys():
        raw_source_files.extend(glob.glob(os.path.join(target_folder, f"*{ext}")))
    raw_source_files = sorted(raw_source_files)

    if not raw_source_files:
        print(f"[-] No raw source datasets found inside target folder: {target_folder}")
        sys.exit(1)

    print(f"[+] Batch Discovery Complete: Processing {len(raw_source_files)} source records.")

    df_api = API()
    if context: df_api.setContext(context)
    
    print("\n" + "="*60)
    print(" DATAFLOW TESTING ENSEMBLE EXECUTION READY")
    print("="*60)
    target_collection = input("Enter Collection ID or 'new': ").strip()

    if target_collection.lower() == 'new':
        coll_name = input("Enter a name for the new DataFed Collection: ").strip()
        if not coll_name:
            coll_name = f"Automated_Ingest_{int(time.time())}"
            
        print(f"[-->] Communicating with DataFed Server to generate collection: '{coll_name}'")
        
        parent_target = repo_id if repo_id else context
        try:
            coll_res = df_api.collectionCreate(coll_name, parent_id=parent_target)
            target_collection = coll_res[0].data[0].id
            print(f"[+] Collection Created Successfully! DataFed ID: {target_collection}")
        except Exception as e:
            print(f"[!] Primary allocation path failed ({e}). Retrying creation directly in user Root space...")
            try:
                coll_res = df_api.collectionCreate(coll_name)
                target_collection = coll_res[0].data[0].id
                print(f"[+] Collection Created Successfully in Root! DataFed ID: {target_collection}")
            except Exception as fatal_e:
                print(f"[-] Fatal error creating collection: {fatal_e}")
                sys.exit(1)

    for idx, raw_file_path in enumerate(raw_source_files, start=1):
        raw_filename = os.path.basename(raw_file_path)
        print(f"\n[*] Processing Pair [{idx}/{len(raw_source_files)}]: {raw_filename}")

        raw_h5_path, extracted_headers = convert_to_h5(raw_file_path, metadata=user_meta)
        if not raw_h5_path or not os.path.exists(raw_h5_path):
            print("    [-] Skipped: Conversion failed to produce an active writable H5 asset.")
            continue
            
        h5_filename = os.path.basename(raw_h5_path)

        integrated_meta = json.loads(json.dumps(user_meta))
        integrated_meta["instrument_header_metadata"] = _clean_dict_for_json(extracted_headers)

        try:
            seaid_obj = SEAID(org="0R", grp="CN", instr="TEM01", role=seaid_role)
            integrated_meta["seaid"] = seaid_obj.seaid
            integrated_meta["seaid_hierarchy"] = {
                "organization": {"seaid": seaid_obj.org_seaid, "uuid": str(seaid_obj.org_uuid)},
                "instrument": {"seaid": seaid_obj.instr_seaid, "uuid": str(seaid_obj.instr_uuid)},
                "data_item": {"seaid": seaid_obj.seaid, "uuid": str(seaid_obj.uuid)}
            }
        except Exception as e:
            print(f"    [-] SEAID tracking mapping skipped: {e}")

        final_metadata_json = json.dumps(integrated_meta)

        # --- ASSET 1: STREAM ORIGINAL RAW FILE ---
        raw_tracking_id = "N/A"
        print(f"    [-->] Registering Raw File Record: {raw_filename}")
        try:
            raw_dc = df_api.dataCreate(raw_filename, metadata=final_metadata_json, parent_id=target_collection)
            raw_tracking_id = raw_dc[0].data[0].id
            
            container_raw_path = raw_file_path.replace("/home/cloud/Globus-Personal-Docker/data/", "/home/gridftp/data/")
            df_api.dataPut(raw_tracking_id, f"{src_collection}{container_raw_path}")
            print(f"          Success -> DataFed ID: {raw_tracking_id}")
        except Exception as e:
            print(f"          [-] Raw ingestion streaming error: {e}")

        # --- ASSET 2: STREAM CONVERTED .h5 FILE ---
        h5_tracking_id = "N/A"
        print(f"    [-->] Registering Converted H5 Record: {h5_filename}")
        try:
            h5_dc = df_api.dataCreate(h5_filename, metadata=final_metadata_json, parent_id=target_collection)
            h5_tracking_id = h5_dc[0].data[0].id
            
            container_h5_path = raw_h5_path.replace("/home/cloud/Globus-Personal-Docker/data/", "/home/gridftp/data/")
            df_api.dataPut(h5_tracking_id, f"{src_collection}{container_h5_path}")
            print(f"          Success -> DataFed ID: {h5_tracking_id}")
        except Exception as e:
            print(f"          [-] H5 ingestion streaming error: {e}")

        if raw_tracking_id != "N/A" or h5_tracking_id != "N/A":
            try:
                qr = qrcode.QRCode(version=None, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=6, border=0)
                qr_payload = f"DataFed_H5_ID: {h5_tracking_id}\nDataFed_Raw_ID: {raw_tracking_id}"
                if "seaid" in integrated_meta:
                    qr_payload += f"\nSEAID: {integrated_meta['seaid']}"
                qr.add_data(qr_payload)
                qr.make(fit=True)
                qr_img = qr.make_image(fill_color="black", back_color="white")
                qr_img.save(os.path.splitext(raw_file_path)[0] + "_qr.png")
                print(f"    [+] Generated exactly ONE unified QR code for this dataset pair.")
            except Exception as e:
                print(f"    [-] Failed generating combined QR code: {e}")

    print("\n" + "="*60)
    print(" PRODUCTION PIPELINE EXECUTION COMPLETE")
    print("="*60)

if __name__ == "__main__":
    execute_automated_pipeline()