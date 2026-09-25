#!/home/cloud/microflow_server/bin/python
import os
import sys
import json
import pathlib
import qrcode
import subprocess
import glob
import time
import h5py
import numpy as np
import warnings

ROOT = pathlib.Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from datafed.CommandLib import API
from pySEA.sea_sand.seaid import SEAID

# Suppress pyNSID / NeXus string alignment formatting warnings
warnings.filterwarnings(
    "ignore",
    message=r"main_data_name should not contain the \"-\" character.*",
    category=UserWarning,
    module=r"pyNSID\.io\.hdf_io",
)
warnings.filterwarnings(
    "ignore",
    message=r"validate_h5_dimension may be removed in a future version",
    category=FutureWarning,
    module=r"pyNSID\.io\.(hdf_io|hdf_utils)",
)

try:
    import pyNSID as nsid
    import SciFiReaders as sr
except ImportError:
    print("[-] Dependencies Missing: Please ensure 'SciFiReaders', 'pyNSID', and 'igor2' are installed.")
    sys.exit(1)

def get_target_collection_interactive(df_api, root_repo):
    """
    Handles folder placement via existing ID or prompts for a new nested subcollection.
    """
    print("\n" + "="*60)
    print(" DATAFIX Dual-Asset BATCH ROUTING")
    print("="*60)
    print(f"[*] Root Repository Context: {root_repo}")
    print(" -> To upload directly to an existing collection, paste its ID")
    print(" -> To create a brand new subcollection folder, type: new")
    print("="*60)
    
    try:
        user_input = input("Enter Collection ID or 'new': ").strip()
        
        if user_input.lower() == 'new':
            parent_id = input(f"Enter Parent Collection ID (Leave blank for root '{root_repo}'): ").strip()
            if not parent_id:
                parent_id = root_repo
                
            new_title = input("Enter a title for your new subcollection: ").strip()
            if not new_title:
                new_title = "Batch_Subcollection"
                
            print(f"[*] Provisioning subcollection '{new_title}' under parent '{parent_id}'...")
            create_resp = df_api.collectionCreate(title=new_title, parent_id=parent_id)
            
            new_id = None
            try:
                lk_resp = df_api.collectionLookup(f"{parent_id}/{new_title}")
                if lk_resp and hasattr(lk_resp[0], "coll") and hasattr(lk_resp[0].coll, "id"):
                    new_id = lk_resp[0].coll.id
            except Exception:
                pass
                
            if not new_id:
                try: new_id = create_resp[0].item.id
                except Exception:
                    try: new_id = create_resp[0].coll.id
                    except Exception: new_id = getattr(create_resp[0], "id", None)
                    
            if not new_id:
                raise RuntimeError("DataFed created the folder but its ID could not be parsed.")
                
            print(f"[+] Successfully created new workspace: '{new_title}' ({new_id})")
            return new_id

        if not user_input:
            print("[-] Error: No collection target specified. Exiting.")
            sys.exit(1)
            
        print(f"[*] Validating target collection context for ID: {user_input} ...")
        view_resp = df_api.collectionView(user_input)
        if view_resp and len(view_resp) > 0:
            print(f"[+] Target collection verified. Ready for streaming.")
            return user_input
            
    except KeyboardInterrupt:
        print("\n[-] Operation cancelled by user.")
        sys.exit(0)
    except Exception as e:
        print(f"[-] DataFed Routing Error: {e}")
        sys.exit(1)

def _first_dataset_path_from_channel(ch: h5py.Group, root: h5py.File):
    """Find a plausible signal dataset under a channel group."""
    if ch is None:
        return None
    mdn = ch.attrs.get("main_data_name")
    if isinstance(mdn, (bytes, bytearray)):
        mdn = mdn.decode("utf-8", errors="ignore")
    if mdn:
        cand = ch.get(mdn) or (ch.get(mdn[2:]) if mdn.startswith("./") else None)
        if isinstance(cand, h5py.Dataset):
            return cand.name
    for name in ("generic", "Main_Data", "main", "data"):
        obj = ch.get(name)
        if isinstance(obj, h5py.Dataset):
            return obj.name
    pref, anyds = [None], [None]
    def visitor(_, obj):
        if isinstance(obj, h5py.Dataset):
            if obj.ndim in (2, 3) and pref[0] is None:
                pref[0] = obj.name
                return True
            if anyds[0] is None:
                anyds[0] = obj.name
        return False
    ch.visititems(lambda n, o: visitor(n, o))
    return pref[0] or anyds[0]

def convert_ibw_to_h5_nexus(file_path, metadata=None):
    """
    Translates binary wave data maps into standardized structured NeXus HDF5 
    datasets using NumPy 2.0 compliant encoding variables.
    """
    try:
        out_path = os.path.splitext(file_path)[0] + ".h5"
        print(f"    [*] Translating Binary Waves: {os.path.basename(file_path)} -> {os.path.basename(out_path)}")
        
        reader = sr.IgorIBWReader(file_path)
        while True:
            try:
                data = reader.read()  # dict[str, sidpy.Dataset]
                break
            except PermissionError:
                time.sleep(1)

        if isinstance(data, list):
            data = {f"Channel_{i:03d}": d for i, d in enumerate(data)}

        with h5py.File(out_path, "w") as f:
            meas = f.create_group("Measurement_Nexus")

            # Minimal NeXus baseline configuration
            f.attrs["default"] = "entry"
            entry = f.require_group("entry")
            entry.attrs["NX_class"] = "NXentry"
            def_dset = entry.require_dataset("definition", shape=(), dtype="S10")
            
            # FIXED: Migrated from np.string_ to np.bytes_ to support NumPy 2.x
            def_dset[...] = np.bytes_("NXem")
            def_dset.attrs["url"] = "https://github.com/FAIRmat-NFDI/nexus_definitions"
            def_dset.attrs["version"] = "v2024.02"

            # Inject tracked runtime configuration settings if provided
            if metadata:
                for k, v in metadata.items():
                    meas.attrs[k] = str(v)

            # Write data channels sequentially via pyNSID
            for key in list(data.keys()):
                ch = meas.create_group(key)
                nsid.hdf_io.write_nsid_dataset(data[key], ch)
                ch.attrs["NX_class"] = "NXdata"

                g = ch.get("generic")
                if isinstance(g, h5py.Group) and "x" in g and "y" in g:
                    if "axis_i" in ch: del ch["axis_i"]
                    if "axis_j" in ch: del ch["axis_j"]
                    g.copy("x", ch, "axis_i")
                    g.copy("y", ch, "axis_j")
                else:
                    ds_path = _first_dataset_path_from_channel(ch, f)
                    if ds_path and isinstance(f[ds_path], h5py.Dataset):
                        ds = f[ds_path]
                        H = int(ds.shape[-2]) if ds.ndim >= 2 else 1
                        W = int(ds.shape[-1]) if ds.ndim >= 1 else 1
                    else:
                        H, W = 1, 1
                    ch.create_dataset("axis_i", data=np.arange(W)).attrs.update(
                        {"units": "pixels", "long_name": "Width"}
                    )
                    ch.create_dataset("axis_j", data=np.arange(H)).attrs.update(
                        {"units": "pixels", "long_name": "Height"}
                    )

            # Establish default view link layout structures
            nxdata = entry.require_group("data")
            nxdata.attrs["NX_class"] = "NXdata"

            chan = meas.get("Channel_000") or (meas[sorted(meas.keys())[0]] if len(meas.keys()) else None)
            sig_path = _first_dataset_path_from_channel(chan, f) if chan is not None else None
            if sig_path and isinstance(f[sig_path], h5py.Dataset):
                if "signal" in nxdata: del nxdata["signal"]
                nxdata["signal"] = h5py.SoftLink(sig_path)
                ax_i = f"{chan.name}/axis_i"
                ax_j = f"{chan.name}/axis_j"
                if ax_i in f and ax_j in f:
                    for nm, tgt in (("axis_i", ax_i), ("axis_j", ax_j)):
                        if nm in nxdata: del nxdata[nm]
                        nxdata[nm] = h5py.SoftLink(tgt)
                    nxdata.attrs["axes"] = np.array(["axis_j", "axis_i"], dtype=object)
                    nxdata.attrs["signal"] = "signal"
                else:
                    ds = f[sig_path]
                    H = int(ds.shape[-2]) if ds.ndim >= 2 else 1
                    W = int(ds.shape[-1]) if ds.ndim >= 1 else 1
                    nxdata.create_dataset("axis_i", data=np.arange(W))
                    nxdata.create_dataset("axis_j", data=np.arange(H))
                    nxdata.attrs["axes"] = np.array(["axis_j", "axis_i"], dtype=object)
                    nxdata.attrs["signal"] = "signal"

        print(f"    [+] Conversion Complete! Saved locally.")
        return out_path
    except Exception as e:
        print(f"    [-] Local HDF5/NeXus compilation step failed: {e}")
        return None

def execute_automated_pipeline():
    # 1. Load config settings
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
    
    provenance_defaults = config_data.get("provenance", {})
    seaid_role = provenance_defaults.get("seaid_role", "E0").strip()

    # 2. Gather Batch Files
    if len(sys.argv) < 2:
        print("[-] Error: Missing file or directory argument path.")
        sys.exit(1)

    input_path = os.path.abspath(sys.argv[1])
    if os.path.isdir(input_path):
        target_folder = input_path
    else:
        target_folder = os.path.dirname(input_path)

    search_pattern = os.path.join(target_folder, "*.ibw")
    ibw_files = sorted(glob.glob(search_pattern))

    if not ibw_files:
        print(f"[-] No valid target .ibw files detected inside workspace: {target_folder}")
        sys.exit(1)

    print(f"[+] Batch Discovery Complete: Identified {len(ibw_files)} datasets to process.")

    # 3. Connect to DataFed API
    df_api = API()
    if context:
        df_api.setContext(context)

    # 4. Route Collection target
    target_collection = get_target_collection_interactive(df_api, repo_id)

    print("\n" + "="*60)
    print(f" RUNNING DUAL-UPLOAD PIPELINE INTO: {target_collection}")
    print("="*60)

    # 5. Iterative Processing and Translation Loop
    for idx, raw_ibw_path in enumerate(ibw_files, start=1):
        ibw_filename = os.path.basename(raw_ibw_path)
        print(f"\n[*] Processing Group [{idx}/{len(ibw_files)}]: {ibw_filename}")

        # A. Run Local Conversion Pass
        raw_h5_path = convert_ibw_to_h5_nexus(raw_ibw_path, metadata=user_meta)
        if not raw_h5_path or not os.path.exists(raw_h5_path):
            print(f"    [-] Skipping file sequence due to conversion layout break.")
            continue
            
        h5_filename = os.path.basename(raw_h5_path)

        # B. Calculate shared system SEAID for this experimental dataset pair
        current_meta = json.loads(json.dumps(user_meta))
        try:
            seaid_obj = SEAID(
                org="0R",
                grp="CN",
                instr="TEM01",
                role=seaid_role
            )
            generated_seaid = seaid_obj.seaid
            print(f"    [+] Assigned Dataset SEAID: {generated_seaid}")
            
            current_meta["seaid"] = generated_seaid
            current_meta["seaid_hierarchy"] = {
                "organization": {"seaid": seaid_obj.org_seaid, "uuid": str(seaid_obj.org_uuid)},
                "instrument": {"seaid": seaid_obj.instr_seaid, "uuid": str(seaid_obj.instr_uuid)},
                "data_item": {"seaid": seaid_obj.seaid, "uuid": str(seaid_obj.uuid)}
            }
        except Exception as e:
            print(f"    [-] System tracking framework omitted: {e}")
            generated_seaid = None

        # --- ASSET 1: STREAM ORIGINAL RAW .ibw FILE ---
        print(f"    [-->] Registering Raw File: {ibw_filename}")
        try:
            ibw_dc = df_api.dataCreate(
                ibw_filename,
                metadata=json.dumps(current_meta),
                parent_id=target_collection
            )
            ibw_tracking_id = ibw_dc[0].data[0].id
            print(f"          DataFed ID: {ibw_tracking_id}")
            
            df_api.dataPut(ibw_tracking_id, f"{src_collection}{raw_ibw_path}")
            print(f"          Globus raw stream initiated.")
        except Exception as e:
            print(f"          [-] Raw file upload segment skipped: {e}")

        # --- ASSET 2: STREAM CONVERTED .h5 FILE ---
        print(f"    [-->] Registering Converted File: {h5_filename}")
        try:
            h5_dc = df_api.dataCreate(
                h5_filename,
                metadata=json.dumps(current_meta),
                parent_id=target_collection
            )
            h5_tracking_id = h5_dc[0].data[0].id
            print(f"          DataFed ID: {h5_tracking_id}")
            
            df_api.dataPut(h5_tracking_id, f"{src_collection}{raw_h5_path}")
            print(f"          Globus H5 stream initiated.")
        except Exception as e:
            print(f"          [-] Converted file upload segment skipped: {e}")

        # D. Save single verification text tracker locally
        if generated_seaid:
            try:
                txt_output_name = os.path.splitext(ibw_filename)[0] + "_seaid.txt"
                txt_output_path = os.path.join(target_folder, txt_output_name)
                with open(txt_output_path, "w") as txt_file:
                    txt_file.write(generated_seaid)
            except Exception as e:
                pass

        # E. Generate single tracking QR code for the pair
        try:
            qr = qrcode.QRCode(version=None, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=6, border=0)
            qr_payload = f"DataFed_H5_ID: {h5_tracking_id}\nDataFed_IBW_ID: {ibw_tracking_id}"
            if generated_seaid:
                qr_payload += f"\nSEAID: {generated_seaid}"
                
            qr.add_data(qr_payload)
            qr.make(fit=True)
            qr_img = qr.make_image(fill_color="black", back_color="white")

            qr_output_path = os.path.splitext(raw_ibw_path)[0] + "_qr.png"
            qr_img.save(qr_output_path)
            print(f"    [+] Combined QR Code Asset Saved Locally.")
        except Exception as e:
            print(f"    [-] Failed generating QR code grid layer: {e}")

    print("\n" + "="*60)
    print(" DUAL-ASSET PIPELINE STREAM COMPLETE")
    print("="*60)

if __name__ == "__main__":
    execute_automated_pipeline()